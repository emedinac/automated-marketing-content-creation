from pathlib import Path

import httpx
import pytest

from marketing_collateral.main import create_app
from marketing_collateral.tracking import InMemoryUsageStore, LlmUsageRecord


@pytest.mark.anyio
async def test_upload_accepts_pdf_context() -> None:
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    )
    pdf = Path("genai-medior-ai-engineer-challenge.pdf").read_bytes()
    response = await client.post(
        "/upload",
        data={"sender_id": "sender-a", "receiver_id": "receiver-b", "role": "sender"},
        files={"files": ("context.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["profile_id"]
    await client.aclose()


@pytest.mark.anyio
async def test_upload_rejects_wrong_content_type() -> None:
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    )
    response = await client.post(
        "/upload",
        data={"sender_id": "sender-a", "receiver_id": "receiver-b", "role": "sender"},
        files={"files": ("context.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 415
    await client.aclose()


@pytest.mark.anyio
async def test_generate_requires_profiles() -> None:
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    )
    response = await client.post(
        "/generate",
        json={
            "sender_id": "sender-a",
            "receiver_id": "receiver-b",
            "prompt": "Write a short article",
            "template_id": "newsletter",
        },
    )
    assert response.status_code == 404
    await client.aclose()


@pytest.mark.anyio
async def test_tracking_summary_returns_recorded_usage() -> None:
    store = InMemoryUsageStore()
    store.record(
        LlmUsageRecord(
            request_id="5e850957-73e6-4a37-92cc-2b403e93f3d7",
            attempt=1,
            model="gemini-2.5-flash",
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            cached_input_tokens=None,
            estimated_cost_usd=0.00028,
            latency_ms=150.0,
            status="success",
            template_id="newsletter",
            prompt_version="v1",
        )
    )
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(usage_store=store)),
        base_url="http://test",
    )

    response = await client.get("/tracking/summary")

    assert response.status_code == 200
    assert response.json() == {
        "total_attempts": 1,
        "successful_attempts": 1,
        "failed_attempts": 0,
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "estimated_cost_usd": 0.00028,
        "average_latency_ms": 150.0,
        "durable": False,
    }
    await client.aclose()
