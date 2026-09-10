import pytest
from pydantic import ValidationError

from marketing_collateral.domain import (
    TEMPLATE_CONTRACTS,
    ArticleResult,
    Section,
    count_words,
    normalize_generation_context,
    validate_article_template,
    validate_word_limit,
)


def test_word_count_is_calculated_deterministically() -> None:
    assert count_words("One   two\nthree") == 3
    assert validate_word_limit("One two", 2) == 2


def test_section_schema_accepts_compliant_output() -> None:
    section = Section(
        section_id="intro",
        text="A short article.",
        word_limit=3,
        word_count=3,
    )
    assert section.word_count <= section.word_limit


def test_section_schema_rejects_word_limit_violation() -> None:
    with pytest.raises(ValidationError):
        Section(section_id="intro", text="Too long.", word_limit=1, word_count=2)


def test_section_ignores_untrusted_model_word_count() -> None:
    section = Section(
        section_id="intro",
        text="One two three",
        word_limit=3,
        word_count=99,
    )
    assert section.word_count == 3


def test_word_limit_validator_rejects_text_that_is_too_long() -> None:
    with pytest.raises(ValueError, match="text exceeds word_limit"):
        validate_word_limit("One two three", 2)


def test_generation_context_normalization_is_deterministic_and_preserves_order(
) -> None:
    text = "Header\n\nFirst fact.\n  First   fact.\nSecond fact.\nHeader\n"

    assert normalize_generation_context(text) == "Header\nFirst fact.\nSecond fact."


def test_generation_context_normalization_respects_character_limit() -> None:
    text = "\n".join(f"Fact number {number} is supported." for number in range(100))
    compact = normalize_generation_context(text, max_chars=40)

    assert len(compact) <= 40
    assert compact.startswith("Fact number 0")


def article(template_id: str, sections: list[dict[str, object]]) -> ArticleResult:
    contract = TEMPLATE_CONTRACTS[template_id]
    return ArticleResult(
        template_id=template_id,
        sections=sections,
        images=[
            {"placeholder": slot, "alt_text": "Contextual marketing visual"}
            for slot in contract.image_slots
        ],
        theme=contract.theme,
    )


def test_template_allowlist_and_validation() -> None:
    assert set(TEMPLATE_CONTRACTS) == {
        "newsletter",
        "brochure",
        "slogan",
        "case_study",
        "event_invitation",
    }
    result = article(
        "newsletter",
        [
            {"section_id": "headline", "text": "A headline", "word_limit": 14},
            {"section_id": "body", "text": "A concise body", "word_limit": 120},
            {"section_id": "cta", "text": "Learn more", "word_limit": 24},
        ],
    )
    assert validate_article_template(result) == result


def test_template_validation_rejects_invalid_layout() -> None:
    with pytest.raises(ValueError):
        validate_article_template(
            article(
                "slogan",
                [{"section_id": "slogan", "text": "One\nTwo\nThree", "word_limit": 20}],
            )
        )


def test_template_validation_rejects_an_unknown_image_asset() -> None:
    result = article(
        "newsletter",
        [
            {"section_id": "headline", "text": "A headline", "word_limit": 14},
            {"section_id": "body", "text": "A concise body", "word_limit": 120},
            {"section_id": "cta", "text": "Learn more", "word_limit": 24},
        ],
    )
    result.images[0].asset_id = "a" * 64
    result.images[0].source_company_id = "sender"

    with pytest.raises(ValueError, match="not available"):
        validate_article_template(result, allowed_image_sources={})
