from marketing_collateral.application import (
    ExtractedPdf,
    InMemoryProfileStore,
    UploadContext,
)
from marketing_collateral.domain import CompanyRole


class FakeExtractor:
    def extract(self, pdf_bytes: bytes) -> ExtractedPdf:
        return ExtractedPdf(
            text="Header\nImportant fact.\nHeader\nImportant fact.",
            images=[],
        )


def test_upload_preserves_raw_text_and_stores_compact_generation_context() -> None:
    store = InMemoryProfileStore()
    raw_text = "Header\nImportant fact.\nHeader\nImportant fact."

    UploadContext(store, FakeExtractor()).upload("sender", "sender", [b"pdf"])
    profile = store.get("sender", CompanyRole.SENDER.value)

    assert profile is not None
    assert profile.extracted_text == raw_text
    assert profile.generation_context == "Header\nImportant fact."
