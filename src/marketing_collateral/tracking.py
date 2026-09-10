from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True)
class LlmUsageRecord:
    request_id: str
    attempt: int
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_input_tokens: int | None
    estimated_cost_usd: float | None
    latency_ms: float
    status: str
    template_id: str
    prompt_version: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class TrackingSummary:
    total_attempts: int
    successful_attempts: int
    failed_attempts: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None
    average_latency_ms: float | None


@dataclass(frozen=True)
class ModelPricing:
    input_cost_per_million_tokens: float
    output_cost_per_million_tokens: float
    cached_input_cost_per_million_tokens: float | None = None


class UsageStore(Protocol):
    def record(self, usage: LlmUsageRecord) -> None: ...

    def summary(self) -> TrackingSummary: ...

    def pricing_for(self, model: str) -> ModelPricing | None: ...


class InMemoryUsageStore:
    """Non-durable fallback used when PostgreSQL is not configured."""

    def __init__(self, prices: dict[str, ModelPricing] | None = None) -> None:
        self.records: list[LlmUsageRecord] = []
        self.prices = prices or {}

    def record(self, usage: LlmUsageRecord) -> None:
        self.records.append(usage)

    def summary(self) -> TrackingSummary:
        records = self.records
        costs = [record.estimated_cost_usd for record in records]
        known_costs = [cost for cost in costs if cost is not None]
        return TrackingSummary(
            total_attempts=len(records),
            successful_attempts=sum(record.status == "success" for record in records),
            failed_attempts=sum(record.status == "failure" for record in records),
            input_tokens=sum(record.input_tokens or 0 for record in records),
            output_tokens=sum(record.output_tokens or 0 for record in records),
            total_tokens=sum(record.total_tokens or 0 for record in records),
            estimated_cost_usd=sum(known_costs) if known_costs else None,
            average_latency_ms=(
                sum(record.latency_ms for record in records) / len(records)
                if records
                else None
            ),
        )

    def pricing_for(self, model: str) -> ModelPricing | None:
        return self.prices.get(model)
