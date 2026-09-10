from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class CompanyRole(StrEnum):
    SENDER = "sender"
    RECEIVER = "receiver"


class CompanyProfile(BaseModel):
    company_id: str
    role: CompanyRole
    extracted_text: str
    generation_context: str | None = None
    images: list["SourceImage"] = Field(default_factory=list)


class SourceImage(BaseModel):
    """A content-addressed image extracted from an uploaded context PDF."""

    asset_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    page_number: int = Field(ge=1)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


MAX_GENERATION_CONTEXT_CHARS = 6_000


def normalize_generation_context(
    text: str, max_chars: int = MAX_GENERATION_CONTEXT_CHARS
) -> str:
    """Create a bounded, deterministic context string for generation.

    PDF extraction often repeats page headers, footers, and wrapped lines. Exact
    normalized duplicates are removed while preserving the first occurrence and
    the source order. The raw extracted text remains available separately.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be at least 1")

    normalized_lines: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized_lines.append(line)

    compact = "\n".join(normalized_lines)
    if len(compact) <= max_chars:
        return compact

    bounded = compact[:max_chars].rstrip()
    last_break = max(bounded.rfind("\n"), bounded.rfind(" "))
    if last_break > 0:
        bounded = bounded[:last_break]
    return bounded.rstrip(" ,;:")


class GenerateRequest(BaseModel):
    sender_id: str = Field(min_length=1)
    receiver_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    event: "EventDetails | None" = None


class EventDetails(BaseModel):
    date: str | None = None
    time: str | None = None
    location: str | None = None
    registration_url: str | None = None


@dataclass(frozen=True)
class SectionRule:
    section_id: str
    word_limit: int


@dataclass(frozen=True)
class TemplateContract:
    sections: tuple[SectionRule, ...]
    image_slots: tuple[str, ...]
    theme: dict[str, str]
    max_non_empty_lines: int | None = None


TEMPLATE_CONTRACTS: dict[str, TemplateContract] = {
    "newsletter": TemplateContract(
        sections=(
            SectionRule("headline", 14),
            SectionRule("body", 120),
            SectionRule("cta", 24),
        ),
        image_slots=("main_image",),
        theme={"primary": "#0F172A", "secondary": "#2563EB", "accent": "#F59E0B"},
    ),
    "brochure": TemplateContract(
        sections=(
            SectionRule("headline", 12),
            SectionRule("summary", 60),
            SectionRule("cta", 20),
        ),
        image_slots=("cover_image",),
        theme={"primary": "#0F172A", "secondary": "#2563EB", "accent": "#F59E0B"},
    ),
    "slogan": TemplateContract(
        sections=(SectionRule("slogan", 20),),
        image_slots=(),
        theme={"primary": "#0F172A", "secondary": "#2563EB", "accent": "#F59E0B"},
        max_non_empty_lines=2,
    ),
    "case_study": TemplateContract(
        sections=(
            SectionRule("headline", 12),
            SectionRule("challenge", 50),
            SectionRule("solution", 50),
            SectionRule("outcome", 50),
            SectionRule("cta", 20),
        ),
        image_slots=("main_image", "supporting_image"),
        theme={"primary": "#0F172A", "secondary": "#2563EB", "accent": "#F59E0B"},
    ),
    "event_invitation": TemplateContract(
        sections=(
            SectionRule("headline", 12),
            SectionRule("details", 30),
            SectionRule("value", 30),
            SectionRule("cta", 20),
        ),
        image_slots=("event_image",),
        theme={"primary": "#0F172A", "secondary": "#2563EB", "accent": "#F59E0B"},
    ),
}


def get_template_contract(template_id: str) -> TemplateContract:
    try:
        return TEMPLATE_CONTRACTS[template_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported template_id: {template_id}") from exc


def count_words(text: str) -> int:
    """Count words using the layout contract's whitespace-based definition."""
    return len(text.split())


def validate_word_limit(text: str, word_limit: int) -> int:
    """Return the trusted count or reject text that cannot fit its slot."""
    word_count = count_words(text)
    if word_count > word_limit:
        raise ValueError("text exceeds word_limit")
    return word_count


class Section(BaseModel):
    section_id: str
    text: str = Field(min_length=1)
    word_limit: int = Field(ge=1)
    word_count: int = Field(default=0, ge=0)
    sources: list["SourceReference"] = Field(default_factory=list)

    @model_validator(mode="after")
    def calculate_and_validate_word_count(self) -> "Section":
        self.word_count = validate_word_limit(self.text, self.word_limit)
        return self


class ArticleResult(BaseModel):
    template_id: str
    sections: list[Section] = Field(min_length=1)
    images: list["ImagePlacement"] = Field(default_factory=list)
    theme: dict[str, str] = Field(min_length=1)
    # Production should set this from a configurable review policy.
    review_required: bool = True
    review_reasons: list[str] = Field(default_factory=list)


class SourceReference(BaseModel):
    company_id: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    evidence: str | None = None


class ImagePlacement(BaseModel):
    placeholder: str
    asset_id: str | None = None
    source_company_id: str | None = None
    alt_text: str = Field(min_length=1)


def validate_article_template(
    result: ArticleResult, allowed_image_sources: dict[str, str] | None = None
) -> ArticleResult:
    contract = get_template_contract(result.template_id)
    expected_sections = tuple(rule.section_id for rule in contract.sections)
    actual_sections = tuple(section.section_id for section in result.sections)
    if actual_sections != expected_sections:
        raise ValueError(
            f"sections must be ordered as {expected_sections}, got {actual_sections}"
        )

    for section, rule in zip(result.sections, contract.sections, strict=True):
        if section.word_limit != rule.word_limit:
            raise ValueError(
                f"{section.section_id} word_limit must be {rule.word_limit}"
            )
        validate_word_limit(section.text, rule.word_limit)

    if contract.max_non_empty_lines is not None:
        line_count = sum(
            bool(line.strip()) for line in result.sections[0].text.splitlines()
        )
        if line_count > contract.max_non_empty_lines:
            raise ValueError(
                "slogan must contain at most "
                f"{contract.max_non_empty_lines} non-empty lines"
            )
    if result.theme != contract.theme:
        raise ValueError("theme must match the selected template")

    expected_slots = contract.image_slots
    actual_slots = tuple(image.placeholder for image in result.images)
    if actual_slots != expected_slots:
        raise ValueError(
            "image placeholders must be ordered as "
            f"{expected_slots}, got {actual_slots}"
        )
    if allowed_image_sources is not None:
        for image in result.images:
            if image.asset_id is None:
                if image.source_company_id is not None:
                    raise ValueError("source_company_id requires an asset_id")
                continue
            expected_company = allowed_image_sources.get(image.asset_id)
            if expected_company is None:
                raise ValueError("image asset_id is not available in uploaded context")
            if image.source_company_id != expected_company:
                raise ValueError("image source_company_id does not match the asset")
    return result


class GenerateResponse(BaseModel):
    result: ArticleResult


class TrackingSummaryResponse(BaseModel):
    total_attempts: int
    successful_attempts: int
    failed_attempts: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None
    average_latency_ms: float | None
    durable: bool


class UploadResponse(BaseModel):
    profile_id: str
    status: str = "processed"
