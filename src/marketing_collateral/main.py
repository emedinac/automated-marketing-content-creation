from fastapi import FastAPI

from marketing_collateral.adapters import http
from marketing_collateral.adapters.http import router
from marketing_collateral.adapters.llm import (
    FallbackArticleGenerator,
    FallbackOnErrorGenerator,
    GeminiArticleGenerator,
    UnconfiguredArticleGenerator,
)
from marketing_collateral.adapters.pdf import PdfPlumberContextExtractor
from marketing_collateral.adapters.tracking import PostgresUsageStore
from marketing_collateral.application import (
    GenerateArticle,
    InMemoryAssetStore,
    InMemoryProfileStore,
    UploadContext,
)
from marketing_collateral.settings import Settings
from marketing_collateral.tracking import InMemoryUsageStore, UsageStore


def create_app(
    settings: Settings | None = None,
    usage_store: UsageStore | None = None,
) -> FastAPI:
    settings = settings or Settings()
    store = InMemoryProfileStore()
    assets = InMemoryAssetStore()
    http.asset_store = assets
    http.upload_context = UploadContext(store, PdfPlumberContextExtractor(), assets)
    active_usage_store = usage_store or (
        PostgresUsageStore(settings.database_url)
        if settings.database_url
        else InMemoryUsageStore()
    )
    http.usage_store = active_usage_store
    http.usage_is_durable = bool(settings.database_url)
    project = settings.google_cloud_project
    primary_generator = (
        GeminiArticleGenerator.from_environment(
            project=project,
            location=settings.google_cloud_location,
            model=settings.gemini_model,
            usage_store=active_usage_store,
            prompt_version=settings.prompt_version,
        )
        if project
        else UnconfiguredArticleGenerator()
    )
    generator = FallbackOnErrorGenerator(primary_generator, FallbackArticleGenerator())
    http.generate_article = GenerateArticle(store, generator)
    app = FastAPI(title="Automated Generative Marketing Collateral")
    app.include_router(router)
    return app


app = create_app()
