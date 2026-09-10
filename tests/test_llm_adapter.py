import json
from dataclasses import dataclass

import pytest

from marketing_collateral.adapters.llm import GeminiArticleGenerator
from marketing_collateral.domain import (
    TEMPLATE_CONTRACTS,
    ArticleResult,
    CompanyProfile,
    CompanyRole,
    GenerateRequest,
)
from marketing_collateral.tracking import InMemoryUsageStore, ModelPricing


@dataclass
class FakeResponse:
    text: str | None = None
    parsed: ArticleResult | None = None
    usage_metadata: object | None = None


@dataclass
class FakeUsage:
    prompt_token_count: int
    candidates_token_count: int
    total_token_count: int
    cached_content_token_count: int | None = None


class FakeModels:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def generate_content(self, **kwargs: object) -> FakeResponse:
        self.prompts.append(str(kwargs["contents"]))
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.models = FakeModels(responses)


def request() -> GenerateRequest:
    return GenerateRequest(
        sender_id="sender",
        receiver_id="receiver",
        prompt="Write an article",
        template_id="newsletter",
    )


def profile(company_id: str, role: CompanyRole) -> CompanyProfile:
    return CompanyProfile(
        company_id=company_id, role=role, extracted_text=f"Facts about {company_id}"
    )


def valid_result() -> ArticleResult:
    return ArticleResult(
        template_id="newsletter",
        sections=[
            {
                "section_id": "headline",
                "text": "Grounded draft",
                "word_limit": 14,
            },
            {"section_id": "body", "text": "Grounded draft", "word_limit": 120},
            {"section_id": "cta", "text": "Learn more", "word_limit": 24},
        ],
        images=[
            {
                "placeholder": "main_image",
                "alt_text": "Contextual marketing visual",
            }
        ],
        theme=TEMPLATE_CONTRACTS["newsletter"].theme,
    )


def test_adapter_requests_provider_native_schema_and_returns_pydantic_model() -> None:
    client = FakeClient([FakeResponse(parsed=valid_result())])
    result = GeminiArticleGenerator(client).generate(
        request(),
        profile("sender", CompanyRole.SENDER),
        profile("receiver", CompanyRole.RECEIVER),
    )

    assert result.template_id == "newsletter"
    assert result.review_required is True
    assert result.review_reasons == [
        "No section-level source references were returned; verify claims against "
        "the uploaded PDFs."
    ]
    assert client.models.prompts
    assert "headline: at most 14 words" in client.models.prompts[0]
    assert "source reference" in client.models.prompts[0]


def test_adapter_prefers_compact_generation_context() -> None:
    client = FakeClient([FakeResponse(parsed=valid_result())])
    sender = CompanyProfile(
        company_id="sender",
        role=CompanyRole.SENDER,
        extracted_text="raw sender context",
        generation_context="compact sender context",
    )
    receiver = profile("receiver", CompanyRole.RECEIVER)

    GeminiArticleGenerator(client).generate(request(), sender, receiver)

    assert "compact sender context" in client.models.prompts[0]
    assert "raw sender context" not in client.models.prompts[0]


def test_adapter_retries_with_validation_feedback() -> None:
    invalid = '{"template_id":"newsletter","sections":[]}'
    client = FakeClient([
        FakeResponse(text=invalid),
        FakeResponse(parsed=valid_result()),
    ])
    result = GeminiArticleGenerator(client).generate(
        request(),
        profile("sender", CompanyRole.SENDER),
        profile("receiver", CompanyRole.RECEIVER),
    )

    assert result.template_id == "newsletter"
    assert len(client.models.prompts) == 2
    assert "VALIDATION FEEDBACK" in client.models.prompts[1]


def test_adapter_trims_only_word_limit_near_miss_without_retrying() -> None:
    payload = valid_result().model_dump()
    payload["sections"][0]["text"] = (
        "One two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen"
    )
    client = FakeClient([FakeResponse(text=json.dumps(payload))])

    result = GeminiArticleGenerator(client).generate(
        request(),
        profile("sender", CompanyRole.SENDER),
        profile("receiver", CompanyRole.RECEIVER),
    )

    assert len(client.models.prompts) == 1
    assert result.sections[0].text == (
        "One two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen"
    )
    assert result.sections[0].word_count == 14


def test_adapter_surfaces_exhausted_validation_retries() -> None:
    invalid = '{"template_id":"newsletter","sections":[]}'
    client = FakeClient([FakeResponse(text=invalid)] * 3)

    with pytest.raises(RuntimeError, match="after 3 attempts"):
        GeminiArticleGenerator(client).generate(
            request(),
            profile("sender", CompanyRole.SENDER),
            profile("receiver", CompanyRole.RECEIVER),
        )


def test_adapter_records_usage_and_cost_for_each_attempt() -> None:
    invalid = '{"template_id":"newsletter","sections":[]}'
    store = InMemoryUsageStore(
        prices={
            "gemini-2.5-flash": ModelPricing(
                input_cost_per_million_tokens=2.0,
                output_cost_per_million_tokens=4.0,
            )
        }
    )
    client = FakeClient([
        FakeResponse(
            text=invalid,
            usage_metadata=FakeUsage(100, 20, 120, cached_content_token_count=10),
        ),
        FakeResponse(parsed=valid_result(), usage_metadata=FakeUsage(80, 15, 95)),
    ])

    GeminiArticleGenerator(client, usage_store=store).generate(
        request(),
        profile("sender", CompanyRole.SENDER),
        profile("receiver", CompanyRole.RECEIVER),
    )

    assert [record.status for record in store.records] == ["failure", "success"]
    assert store.records[0].cached_input_tokens == 10
    assert store.records[0].estimated_cost_usd == pytest.approx(0.00028)
    assert store.records[1].attempt == 2
