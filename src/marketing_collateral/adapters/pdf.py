from hashlib import sha256
from io import BytesIO
from typing import Any

import pdfplumber
import pytesseract  # type: ignore[import-untyped]
from pypdf import PdfReader
from pytesseract import TesseractNotFoundError

from marketing_collateral.application import ExtractedPdf
from marketing_collateral.domain import SourceImage


class PdfPlumberContextExtractor:
    """Extract text, tables, and content-addressed image metadata from a PDF.

    ``pdfplumber`` is MIT licensed and is used for text/table extraction.
    ``pypdf`` (BSD-3-Clause) extracts the original embedded image bytes. OCR is
    attempted only for image-only documents and needs the host Tesseract binary.
    """

    def extract(self, pdf_bytes: bytes) -> ExtractedPdf:
        if not pdf_bytes:
            raise ValueError("PDF is empty")
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                text = self._extract_text_and_tables(pdf)
            images, assets = self._extract_images(pdf_bytes)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Could not parse PDF") from exc

        if not text:
            text = self._ocr_images(pdf_bytes)
        if not text:
            raise ValueError(
                "PDF has no extractable text or OCR-readable image content"
            )
        return ExtractedPdf(text=text, images=images, assets=assets)

    @staticmethod
    def _extract_text_and_tables(pdf: Any) -> str:
        pages: list[str] = []
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            parts = [page_text]
            for table_number, table in enumerate(page.extract_tables(), start=1):
                rows = [
                    " | ".join((cell or "").strip() for cell in row) for row in table
                ]
                rows = [row for row in rows if row.strip(" |")]
                # Some PDFs expose table text through ``extract_text`` as well.
                # Only append the flattened representation when it is not
                # already present in the page text.
                table_text = "\n".join(rows)
                if rows and table_text not in page_text:
                    parts.append(
                        f"[TABLE page={page_number} index={table_number}]\n"
                        + table_text
                        + "\n[/TABLE]"
                    )
            page_text = "\n".join(part for part in parts if part.strip())
            if page_text:
                pages.append(page_text)
        return "\n\n".join(pages).strip()

    @staticmethod
    def _extract_images(
        pdf_bytes: bytes,
    ) -> tuple[list[SourceImage], dict[str, tuple[bytes, str]]]:
        reader = PdfReader(BytesIO(pdf_bytes))
        images: list[SourceImage] = []
        assets: dict[str, tuple[bytes, str]] = {}
        seen_assets: set[str] = set()
        for page_number, page in enumerate(reader.pages, start=1):
            for image in page.images:
                asset_id = sha256(image.data).hexdigest()
                if asset_id in seen_assets:
                    continue
                seen_assets.add(asset_id)
                pil_image = image.image
                if pil_image is None:
                    raise ValueError("Could not decode an embedded PDF image")
                images.append(
                    SourceImage(
                        asset_id=asset_id,
                        page_number=page_number,
                        width=pil_image.width,
                        height=pil_image.height,
                    )
                )
                media_type = "image/png" if pil_image.format == "PNG" else "image/jpeg"
                assets[asset_id] = (image.data, media_type)
        return images, assets

    @staticmethod
    def _ocr_images(pdf_bytes: bytes) -> str:
        """OCR scanned pages represented by full-page embedded images."""
        reader = PdfReader(BytesIO(pdf_bytes))
        text_parts: list[str] = []
        try:
            for page in reader.pages:
                for image in page.images:
                    candidate = pytesseract.image_to_string(image.image).strip()
                    if candidate:
                        text_parts.append(candidate)
        except TesseractNotFoundError as exc:
            raise ValueError(
                "PDF has no text layer and OCR requires the Tesseract binary; "
                "install tesseract-ocr and retry"
            ) from exc
        return "\n\n".join(text_parts)
