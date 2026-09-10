from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from marketing_collateral.domain import (
    ArticleResult,
    CompanyProfile,
    CompanyRole,
    GenerateRequest,
    SourceImage,
    get_template_contract,
    normalize_generation_context,
)


class ProfileStore(Protocol):
    def save(self, profile: CompanyProfile) -> None: ...

    def get(self, company_id: str, role: str) -> CompanyProfile | None: ...


class ArticleGenerator(Protocol):
    def generate(
        self, request: GenerateRequest, sender: CompanyProfile, receiver: CompanyProfile
    ) -> ArticleResult: ...


class InMemoryProfileStore:
    def __init__(self) -> None:
        self._profiles: dict[tuple[str, str], CompanyProfile] = {}

    def save(self, profile: CompanyProfile) -> None:
        self._profiles[(profile.company_id, profile.role.value)] = profile

    def get(self, company_id: str, role: str) -> CompanyProfile | None:
        return self._profiles.get((company_id, role))


@dataclass(frozen=True)
class ExtractedPdf:
    text: str
    images: list[SourceImage]
    assets: dict[str, tuple[bytes, str]] = field(default_factory=dict)


class PdfContextExtractor(Protocol):
    def extract(self, pdf_bytes: bytes) -> ExtractedPdf: ...


class AssetStore(Protocol):
    def save(self, asset_id: str, data: bytes, media_type: str) -> None: ...

    def get(self, asset_id: str) -> tuple[bytes, str] | None: ...


class InMemoryAssetStore:
    def __init__(self) -> None:
        self._assets: dict[str, tuple[bytes, str]] = {}

    def save(self, asset_id: str, data: bytes, media_type: str) -> None:
        self._assets[asset_id] = (data, media_type)

    def get(self, asset_id: str) -> tuple[bytes, str] | None:
        return self._assets.get(asset_id)


@dataclass
class UploadContext:
    store: ProfileStore
    extractor: PdfContextExtractor
    asset_store: AssetStore | None = None

    def upload(self, company_id: str, role: str, documents: list[bytes]) -> str:
        extracted_documents = [self.extractor.extract(data) for data in documents]
        if self.asset_store is not None:
            for document in extracted_documents:
                for asset_id, (asset_data, media_type) in document.assets.items():
                    self.asset_store.save(asset_id, asset_data, media_type)
        text = "\n\n".join(document.text for document in extracted_documents)
        profile_id = str(uuid4())
        profile = CompanyProfile(
            company_id=company_id,
            role=CompanyRole(role),
            extracted_text=text,
            generation_context=normalize_generation_context(text),
            images=[
                image for document in extracted_documents for image in document.images
            ],
        )
        self.store.save(profile)
        return profile_id


class GenerateArticle:
    def __init__(
        self,
        store: ProfileStore,
        generator: ArticleGenerator,
    ) -> None:
        self.store = store
        self.generator = generator

    def execute(self, request: GenerateRequest) -> ArticleResult:
        get_template_contract(request.template_id)
        sender = self.store.get(request.sender_id, "sender")
        receiver = self.store.get(request.receiver_id, "receiver")
        if sender is None or receiver is None:
            raise LookupError(
                "Both sender and receiver profiles must be uploaded first"
            )
        return self.generator.generate(request, sender, receiver)
