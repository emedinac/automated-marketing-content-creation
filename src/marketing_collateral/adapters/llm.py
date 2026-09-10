import json
import re
from collections.abc import Mapping
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from marketing_collateral.adapters.metrics import record_attempt_metrics
from marketing_collateral.application import ArticleGenerator
from marketing_collateral.domain import (
    ArticleResult,
    CompanyProfile,
    GenerateRequest,
    get_template_contract,
    validate_article_template,
)
from marketing_collateral.tracking import LlmUsageRecord, ModelPricing, UsageStore

# Keep the prototype request small; production should retrieve relevant chunks.
MAX_CONTEXT_CHARS = 12_000
NUMBER_PATTERN = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?%?(?![\w])")


class LlmRateLimitError(RuntimeError):
    """The provider rejected a request because of quota or rate limits."""


class GeminiArticleGenerator:
    """Vertex AI Gemini adapter using provider-native structured output.

    The Google SDK is intentionally kept in this adapter. The application only
    depends on the ``ArticleGenerator`` protocol and the domain models.
    """

    def __init__(
        self,
        client: Any,
        model: str = "gemini-2.5-flash",
        max_attempts: int = 3,
        usage_store: UsageStore | None = None,
        prompt_version: str = "v1",
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.client = client
        self.model = model
        self.max_attempts = max_attempts
        self.usage_store = usage_store
        self.prompt_version = prompt_version

    @classmethod
    def from_environment(
        cls,
        *,
        project: str,
        location: str = "global",
        model: str = "gemini-2.5-flash",
        max_attempts: int = 3,
        usage_store: UsageStore | None = None,
        prompt_version: str = "v1",
    ) -> "GeminiArticleGenerator":
        from google import genai

        client = genai.Client(vertexai=True, project=project, location=location)
        return cls(
            client,
            model=model,
            max_attempts=max_attempts,
            usage_store=usage_store,
            prompt_version=prompt_version,
        )

    def generate(
        self, request: GenerateRequest, sender: CompanyProfile, receiver: CompanyProfile
    ) -> ArticleResult:
        base_prompt = self._build_prompt(request, sender, receiver)
        feedback = ""
        request_id = str(uuid4())

        for attempt in range(self.max_attempts):
            prompt = base_prompt
            if feedback:
                prompt += (
                    "\n\nVALIDATION FEEDBACK FROM THE PREVIOUS ATTEMPT:\n"
                    f"{feedback}\nCorrect every issue and return the complete "
                    "object again."
                )
            response: Any | None = None
            started_at = perf_counter()
            try:
                response = self._call_model(prompt)
                result = self._parse_response(response)
                if result.template_id != request.template_id:
                    raise ValueError(
                        f"template_id must be {request.template_id!r}, "
                        f"got {result.template_id!r}"
                    )
                validate_article_template(
                    result,
                    {
                        image.asset_id: company_id
                        for company_id, profile in (
                            (sender.company_id, sender),
                            (receiver.company_id, receiver),
                        )
                        for image in profile.images
                    },
                )
                # Minimal guard; production should use semantic claim checking.
                self._reject_unsupported_numbers(result, sender, receiver, request)
                self._apply_review_policy(result)
                self._record_attempt(
                    request_id=request_id,
                    attempt=attempt + 1,
                    request=request,
                    response=response,
                    status="success",
                    latency_ms=(perf_counter() - started_at) * 1000,
                    retry=attempt > 0,
                )
                return result
            except (ValidationError, ValueError) as exc:
                self._record_attempt(
                    request_id=request_id,
                    attempt=attempt + 1,
                    request=request,
                    response=response,
                    status="failure",
                    latency_ms=(perf_counter() - started_at) * 1000,
                    retry=attempt > 0,
                )
                feedback = str(exc)
                print(f"Gemini validation failure on attempt {attempt + 1}: {feedback}")
                if attempt == self.max_attempts - 1:
                    raise RuntimeError(
                        "Gemini returned output that failed ArticleResult validation "
                        f"after {self.max_attempts} attempts"
                    ) from exc
            except Exception as exc:
                self._record_attempt(
                    request_id=request_id,
                    attempt=attempt + 1,
                    request=request,
                    response=response,
                    status="failure",
                    latency_ms=(perf_counter() - started_at) * 1000,
                    retry=attempt > 0,
                )
                if getattr(exc, "status_code", None) == 429:
                    raise LlmRateLimitError(
                        "The LLM provider quota is exhausted or rate limited; "
                        "wait and retry, or check Vertex AI quotas and billing."
                    ) from exc
                raise

        raise AssertionError("unreachable")

    @staticmethod
    def _reject_unsupported_numbers(
        result: ArticleResult,
        sender: CompanyProfile,
        receiver: CompanyProfile,
        request: GenerateRequest,
    ) -> None:
        context = " ".join(
            (sender.extracted_text, receiver.extracted_text, request.prompt)
        )
        # Treat common equivalent forms such as "30 percent" and "30%" alike.
        normalized_context = re.sub(r"(\d+)\s*percent", r"\1%", context.lower())
        normalized_context = re.sub(r"(\d+)\s*%", r"\1%", normalized_context)
        unsupported = {
            token
            for section in result.sections
            for token in NUMBER_PATTERN.findall(section.text)
            if token.lower() not in normalized_context
        }
        if unsupported:
            raise ValueError(
                "output contains unsupported numeric claims: "
                + ", ".join(sorted(unsupported))
            )

    @staticmethod
    def _apply_review_policy(result: ArticleResult) -> None:
        """Keep review explicit when provenance is incomplete in this prototype."""
        reasons = list(dict.fromkeys(result.review_reasons))
        references = [
            source for section in result.sections for source in section.sources
        ]
        if not result.review_required:
            reasons.append("The model requested review before publication.")
        if not references:
            reasons.append(
                "No section-level source references were returned; verify claims "
                "against the uploaded PDFs."
            )
        elif any(source.evidence is None for source in references):
            reasons.append(
                "Some source references have no evidence excerpt; verify claims "
                "against the uploaded PDFs."
            )
        if not reasons:
            reasons.append("Human review is required before publication.")
        result.review_required = True
        result.review_reasons = list(dict.fromkeys(reasons))

    def _call_model(self, prompt: str) -> Any:
        return self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "response_schema": ArticleResult,
            },
        )

    @staticmethod
    def _parse_response(response: Any) -> ArticleResult:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, ArticleResult):
            return parsed
        if isinstance(parsed, dict):
            payload = parsed
        else:
            text = getattr(response, "text", None)
            if not text:
                raise ValueError("Gemini response did not contain structured output")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("Gemini response was not valid JSON") from exc

        try:
            return ArticleResult.model_validate(payload)
        except ValidationError as exc:
            repaired = GeminiArticleGenerator._repair_word_limit_violation(
                payload, exc
            )
            if repaired is None:
                raise
            return ArticleResult.model_validate(repaired)

    @staticmethod
    def _repair_word_limit_violation(
        payload: Any, error: ValidationError
    ) -> dict[str, Any] | None:
        """Trim an otherwise valid payload whose only failures are word limits.

        This deliberately operates on the raw payload because Section's schema
        validator rejects over-limit text before an ArticleResult exists. Any
        other schema error keeps the normal bounded retry behaviour.
        """
        if not isinstance(payload, Mapping):
            return None

        errors = error.errors()
        if not errors or any(
            item.get("type") != "value_error"
            or item.get("msg") != "Value error, text exceeds word_limit"
            or len(item.get("loc", ())) != 2
            or item["loc"][0] != "sections"
            or not isinstance(item["loc"][1], int)
            for item in errors
        ):
            return None

        sections = payload.get("sections")
        if not isinstance(sections, list):
            return None

        repaired: dict[str, Any] = dict(payload)
        repaired_sections = [
            dict(section) if isinstance(section, Mapping) else section
            for section in sections
        ]
        for item in errors:
            location = item["loc"]
            index = location[1]
            if not isinstance(index, int):
                return None
            if index >= len(repaired_sections):
                return None
            section = repaired_sections[index]
            if not isinstance(section, dict):
                return None
            text = section.get("text")
            word_limit = section.get("word_limit")
            if not isinstance(text, str) or not isinstance(word_limit, int):
                return None
            section["text"] = " ".join(text.split()[:word_limit])

        repaired["sections"] = repaired_sections
        return repaired

    def _record_attempt(
        self,
        *,
        request_id: str,
        attempt: int,
        request: GenerateRequest,
        response: Any | None,
        status: str,
        latency_ms: float,
        retry: bool,
    ) -> None:
        input_tokens, output_tokens, total_tokens, cached_input_tokens = (
            self._usage_from_response(response)
        )
        pricing = self.usage_store.pricing_for(self.model) if self.usage_store else None
        estimated_cost_usd = self._estimated_cost(
            pricing, input_tokens, output_tokens, cached_input_tokens
        )
        usage = LlmUsageRecord(
            request_id=request_id,
            attempt=attempt,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cached_input_tokens=cached_input_tokens,
            estimated_cost_usd=estimated_cost_usd,
            latency_ms=latency_ms,
            status=status,
            template_id=request.template_id,
            prompt_version=self.prompt_version,
        )
        if self.usage_store is not None:
            self.usage_store.record(usage)
        record_attempt_metrics(
            model=self.model,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            latency_ms=latency_ms,
            retry=retry,
            template_id=request.template_id,
        )

    @staticmethod
    def _usage_from_response(
        response: Any | None,
    ) -> tuple[int | None, int | None, int | None, int | None]:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return None, None, None, None

        def value(*names: str) -> int | None:
            for name in names:
                candidate = getattr(usage, name, None)
                if candidate is not None:
                    return int(candidate)
            return None

        return (
            value("prompt_token_count", "input_tokens"),
            value("candidates_token_count", "output_tokens"),
            value("total_token_count", "total_tokens"),
            value("cached_content_token_count", "cached_input_tokens"),
        )

    def _estimated_cost(
        self,
        pricing: ModelPricing | None,
        input_tokens: int | None,
        output_tokens: int | None,
        cached_input_tokens: int | None,
    ) -> float | None:
        if pricing is None or input_tokens is None or output_tokens is None:
            return None
        cached_tokens = cached_input_tokens or 0
        uncached_tokens = max(input_tokens - cached_tokens, 0)
        cached_rate = (
            pricing.cached_input_cost_per_million_tokens
            or pricing.input_cost_per_million_tokens
        )
        return (
            uncached_tokens * pricing.input_cost_per_million_tokens
            + cached_tokens * cached_rate
            + output_tokens * pricing.output_cost_per_million_tokens
        ) / 1_000_000

    @staticmethod
    def _build_prompt(
        request: GenerateRequest, sender: CompanyProfile, receiver: CompanyProfile
    ) -> str:
        contract = get_template_contract(request.template_id)
        sections = "\n".join(
            f"- {rule.section_id}: at most {rule.word_limit} words"
            for rule in contract.sections
        )
        image_assets = (
            "\n".join(
                f"- asset_id={image.asset_id}, company_id={company_id}, "
                f"page={image.page_number}, size={image.width}x{image.height}"
                for company_id, profile in (
                    (sender.company_id, sender),
                    (receiver.company_id, receiver),
                )
                for image in profile.images
            )
            or "- No extracted image assets are available."
        )
        slogan_constraint = (
            "\n- The slogan must contain at most two non-empty lines."
            if contract.max_non_empty_lines is not None
            else ""
        )
        event_details = (
            request.event.model_dump(exclude_none=True)
            if request.event
            else "None supplied; use 'To be announced'."
        )
        return f"""
You create concise, factually grounded B2B marketing collateral.

Return only the supplied ArticleResult JSON schema. Use only facts from the
company context; frame connections as potential fits. Never invent
partnerships, customers, deployments, outcomes, numbers, dates, locations, or
links. Include supported facts about both companies. For each section with a
company-specific fact, include a source reference with company_id, page_number
when known, and a short evidence excerpt. Follow the exact section,
word-limit, theme, and image-placeholder contract. Use "To be announced" when
event details are missing. Return no text outside the JSON object.

TEMPLATE:
template_id={request.template_id!r}
Return these sections in exactly this order, with the stated word_limit values:
{sections}{slogan_constraint}
theme={contract.theme}
image_placeholders={contract.image_slots}

TEMPLATE GUIDANCE:
{GeminiArticleGenerator._template_guidance(request.template_id)}

EVENT DETAILS:
{event_details}

AVAILABLE IMAGE ASSETS:
{image_assets}

USER REQUEST:
<user_request>
{request.prompt}
</user_request>

SENDER CONTEXT (company_id={sender.company_id!r}):
<sender_context>
{(sender.generation_context or sender.extracted_text)[:MAX_CONTEXT_CHARS]}
</sender_context>

RECEIVER CONTEXT (company_id={receiver.company_id!r}):
<receiver_context>
{(receiver.generation_context or receiver.extracted_text)[:MAX_CONTEXT_CHARS]}
</receiver_context>
"""

    @staticmethod
    def _template_guidance(template_id: str) -> str:
        return {
            "newsletter": "Use a concise headline, body, and CTA.",
            "brochure": "Use benefit-oriented brochure copy.",
            "slogan": "Keep the slogan to at most two non-empty lines.",
            "case_study": "Keep the connection hypothetical; do not invent outcomes.",
            "event_invitation": (
                "Use supplied event details; otherwise say 'To be announced'."
            ),
        }[template_id]


class UnconfiguredArticleGenerator:
    """Explicit seam for a provider-native structured-output LLM adapter."""

    def generate(
        self, request: GenerateRequest, sender: CompanyProfile, receiver: CompanyProfile
    ) -> ArticleResult:
        raise RuntimeError("No LLM adapter configured")


class FallbackArticleGenerator:
    """Deterministic safe draft used when the provider is unavailable."""

    def generate(
        self, request: GenerateRequest, sender: CompanyProfile, receiver: CompanyProfile
    ) -> ArticleResult:
        contract = get_template_contract(request.template_id)
        texts = {
            "headline": f"{sender.company_id} and {receiver.company_id}: potential fit",
            "body": (
                "This is a fallback draft based on the uploaded company context. "
                "Review the source documents before publication."
            ),
            "summary": (
                "This is a fallback summary based on the uploaded company context. "
                "Review the source documents before publication."
            ),
            "challenge": (
                "Receiver priorities require review against the source context."
            ),
            "solution": (
                "Sender capabilities require review against the source context."
            ),
            "outcome": "Potential outcomes are not asserted in this fallback draft.",
            "details": "Event details: To be announced.",
            "value": "The potential value requires human review of the source context.",
            "cta": "Review the source documents before publication.",
            "slogan": f"Potential fit: {sender.company_id} + {receiver.company_id}",
        }
        sections = [
            {
                "section_id": rule.section_id,
                "text": texts[rule.section_id],
                "word_limit": rule.word_limit,
            }
            for rule in contract.sections
        ]
        result = ArticleResult(
            template_id=request.template_id,
            sections=sections,
            images=[
                {
                    "placeholder": slot,
                    "alt_text": "Relevant visual to be selected during human review.",
                }
                for slot in contract.image_slots
            ],
            theme=contract.theme,
            review_reasons=["Gemini unavailable; fallback draft requires review."],
        )
        return validate_article_template(result)


class FallbackOnErrorGenerator:
    """Use the real generator when available and a safe draft on failure."""

    def __init__(self, primary: ArticleGenerator, fallback: ArticleGenerator) -> None:
        self.primary = primary
        self.fallback = fallback

    def generate(
        self, request: GenerateRequest, sender: CompanyProfile, receiver: CompanyProfile
    ) -> ArticleResult:
        try:
            return self.primary.generate(request, sender, receiver)
        except Exception as exc:
            print(f"Primary generator failed; using fallback: {exc}")
            return self.fallback.generate(request, sender, receiver)
