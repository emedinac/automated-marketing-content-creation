from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from marketing_collateral.adapters.llm import LlmRateLimitError
from marketing_collateral.application import (
    AssetStore,
    GenerateArticle,
    UploadContext,
)
from marketing_collateral.domain import (
    CompanyRole,
    GenerateRequest,
    GenerateResponse,
    TrackingSummaryResponse,
    UploadResponse,
)
from marketing_collateral.tracking import UsageStore

MAX_PDF_BYTES = 12 * 1024 * 1024  # 12 MB maximum
router = APIRouter()
upload_context: UploadContext | None = None
generate_article: GenerateArticle | None = None
usage_store: UsageStore | None = None
usage_is_durable = False
asset_store: AssetStore | None = None


async def _read_pdf(file: UploadFile) -> bytes:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only application/pdf is supported")
    data = await file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds 12 MB limit")
    return data


@router.post("/upload", response_model=UploadResponse)
async def upload(
    sender_id: str = Form(min_length=1),
    receiver_id: str = Form(min_length=1),
    role: CompanyRole = Form(),
    files: list[UploadFile] = File(min_length=1),
) -> UploadResponse:
    company_id = sender_id if role is CompanyRole.SENDER else receiver_id
    documents = [await _read_pdf(file) for file in files]
    try:
        context = upload_context
        if context is None:
            raise RuntimeError("Upload service is not configured")
        profile_id = context.upload(company_id, role.value, documents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UploadResponse(profile_id=profile_id)


@router.get("/assets/{asset_id}")
async def get_asset(asset_id: str) -> Response:
    store = asset_store
    asset = store.get(asset_id) if store is not None else None
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    data, media_type = asset
    return Response(content=data, media_type=media_type)


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    try:
        generator = generate_article
        if generator is None:
            raise RuntimeError("Generation service is not configured")
        return GenerateResponse(result=generator.execute(request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LlmRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/tracking/summary", response_model=TrackingSummaryResponse)
async def tracking_summary() -> TrackingSummaryResponse:
    store = usage_store
    if store is None:
        raise HTTPException(status_code=503, detail="Usage tracking is not configured")
    summary = store.summary()
    return TrackingSummaryResponse(
        total_attempts=summary.total_attempts,
        successful_attempts=summary.successful_attempts,
        failed_attempts=summary.failed_attempts,
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
        total_tokens=summary.total_tokens,
        estimated_cost_usd=summary.estimated_cost_usd,
        average_latency_ms=summary.average_latency_ms,
        durable=usage_is_durable,
    )


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    store = usage_store
    refresh = getattr(store, "refresh_prometheus_metrics", None)
    if refresh is not None:
        refresh()
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
