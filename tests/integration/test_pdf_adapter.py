from pathlib import Path

import pytest

from marketing_collateral.adapters.pdf import PdfPlumberContextExtractor

CASES = {
    "01_ibm_dhl": ("IBM", "DHL Logistics Trend Radar"),
    "03_sap_dhl": ("SAP", "DHL Logistics Trend Radar"),
    "05_ibm_bosch": ("IBM", "Bosch"),
}
EVAL_ROOT = Path(__file__).parents[2] / "eval" / "cases"


@pytest.mark.parametrize("case, expected_terms", CASES.items())
def test_real_case_pdfs_extract_text(
    case: str, expected_terms: tuple[str, str]
) -> None:
    extractor = PdfPlumberContextExtractor()
    case_dir = EVAL_ROOT / case

    sender = extractor.extract((case_dir / "sender.pdf").read_bytes())
    receiver = extractor.extract((case_dir / "receiver.pdf").read_bytes())

    assert len(sender.text) > 100
    assert len(receiver.text) > 100
    assert expected_terms[0].lower() in sender.text.lower()
    assert expected_terms[1].lower() in receiver.text.lower()
    assert receiver.images
    assert all(len(image.asset_id) == 64 for image in receiver.images)


def test_extractor_rejects_corrupt_pdf() -> None:
    with pytest.raises(ValueError, match="Could not parse PDF"):
        PdfPlumberContextExtractor().extract(b"not a PDF")
