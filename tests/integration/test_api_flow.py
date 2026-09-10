from pathlib import Path

import httpx
import pytest

from marketing_collateral import adapters, domain
from marketing_collateral.main import create_app


class RecordingGenerator:
    def __init__(self) -> None:
        self.calls: list[
            tuple[domain.GenerateRequest, domain.CompanyProfile, domain.CompanyProfile]
        ] = []

    def generate(
        self,
        request: domain.GenerateRequest,
        sender: domain.CompanyProfile,
        receiver: domain.CompanyProfile,
    ) -> domain.ArticleResult:
        self.calls.append((request, sender, receiver))
        return domain.ArticleResult(
            template_id=request.template_id,
            sections=[
                domain.Section(
                    section_id="headline",
                    text="Grounded draft",
                    word_limit=14,
                    word_count=2,
                ),
                domain.Section(
                    section_id="body",
                    text="Grounded draft",
                    word_limit=120,
                    word_count=2,
                ),
                domain.Section(
                    section_id="cta",
                    text="Learn more",
                    word_limit=24,
                    word_count=2,
                ),
            ],
            images=[
                {
                    "placeholder": "main_image",
                    "alt_text": "Contextual marketing visual",
                }
            ],
            theme=domain.TEMPLATE_CONTRACTS[request.template_id].theme,
        )


@pytest.mark.anyio
async def test_upload_then_generate_passes_profiles_to_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    generator = RecordingGenerator()
    assert adapters.http.generate_article is not None
    monkeypatch.setattr(adapters.http.generate_article, "generator", generator)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    fixture = Path(__file__).parents[2] / "genai-medior-ai-engineer-challenge.pdf"
    sender_pdf = fixture.read_bytes()
    receiver_pdf = fixture.read_bytes()

    async with client:
        sender_response = await client.post(
            "/upload",
            data={"sender_id": "ibm", "receiver_id": "dhl", "role": "sender"},
            files={"files": ("sender.pdf", sender_pdf, "application/pdf")},
        )
        receiver_response = await client.post(
            "/upload",
            data={"sender_id": "ibm", "receiver_id": "dhl", "role": "receiver"},
            files={"files": ("receiver.pdf", receiver_pdf, "application/pdf")},
        )
        generate_response = await client.post(
            "/generate",
            json={
                "sender_id": "ibm",
                "receiver_id": "dhl",
                "prompt": "Write a grounded article",
                "template_id": "newsletter",
            },
        )

    assert sender_response.status_code == 200
    assert receiver_response.status_code == 200
    assert generate_response.status_code == 200
    assert generate_response.json()["result"]["template_id"] == "newsletter"
    assert len(generator.calls) == 1
    request, sender, receiver = generator.calls[0]
    assert request.sender_id == "ibm"
    assert sender.role is domain.CompanyRole.SENDER
    assert receiver.role is domain.CompanyRole.RECEIVER
    assert sender.extracted_text
    assert receiver.extracted_text
    assert sender.generation_context
    assert receiver.generation_context
    assert len(sender.generation_context) <= domain.MAX_GENERATION_CONTEXT_CHARS
    assert len(receiver.generation_context) <= domain.MAX_GENERATION_CONTEXT_CHARS
