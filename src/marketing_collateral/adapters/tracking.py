from contextlib import closing
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from marketing_collateral.adapters.metrics import (
    DB_ATTEMPTS,
    DB_AVERAGE_INPUT_TOKENS,
    DB_AVERAGE_LATENCY_MS,
    DB_AVERAGE_OUTPUT_TOKENS,
    DB_INPUT_TOKENS,
    DB_OUTPUT_TOKENS,
    DB_P95_LATENCY_MS,
    DB_RETRIES,
    DB_TEMPLATE_ATTEMPTS,
    DB_TOTAL_COST_USD,
)
from marketing_collateral.domain import TEMPLATE_CONTRACTS
from marketing_collateral.tracking import LlmUsageRecord, ModelPricing, TrackingSummary


class PostgresUsageStore:
    """Durable usage ledger for local PostgreSQL and Cloud SQL."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._initialize_schema()

    def _connect(self) -> psycopg.Connection[dict[str, object]]:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_usage (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL,
                    request_id UUID NOT NULL,
                    attempt SMALLINT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    cached_input_tokens INTEGER,
                    estimated_cost_usd NUMERIC(18, 8),
                    latency_ms DOUBLE PRECISION NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('success', 'failure')),
                    template_id TEXT NOT NULL,
                    prompt_version TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS model_pricing (
                    model TEXT PRIMARY KEY,
                    input_cost_per_million_tokens NUMERIC(18, 8) NOT NULL,
                    output_cost_per_million_tokens NUMERIC(18, 8) NOT NULL,
                    cached_input_cost_per_million_tokens NUMERIC(18, 8)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS llm_usage_created_at_idx
                ON llm_usage (created_at DESC)
                """
            )
            connection.commit()

    def pricing_for(self, model: str) -> ModelPricing | None:
        with closing(self._connect()) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    input_cost_per_million_tokens,
                    output_cost_per_million_tokens,
                    cached_input_cost_per_million_tokens
                FROM model_pricing
                WHERE model = %s
                """,
                (model,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        values = cast(dict[str, Any], row)
        return ModelPricing(
            input_cost_per_million_tokens=float(
                values["input_cost_per_million_tokens"]
            ),
            output_cost_per_million_tokens=float(
                values["output_cost_per_million_tokens"]
            ),
            cached_input_cost_per_million_tokens=(
                float(values["cached_input_cost_per_million_tokens"])
                if values["cached_input_cost_per_million_tokens"] is not None
                else None
            ),
        )

    def record(self, usage: LlmUsageRecord) -> None:
        with closing(self._connect()) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO llm_usage (
                    created_at, request_id, attempt, model, input_tokens,
                    output_tokens, total_tokens, cached_input_tokens,
                    estimated_cost_usd, latency_ms, status, template_id,
                    prompt_version
                ) VALUES (
                    %(created_at)s, %(request_id)s, %(attempt)s, %(model)s,
                    %(input_tokens)s, %(output_tokens)s, %(total_tokens)s,
                    %(cached_input_tokens)s, %(estimated_cost_usd)s,
                    %(latency_ms)s, %(status)s, %(template_id)s,
                    %(prompt_version)s
                )
                """,
                usage.__dict__,
            )
            connection.commit()

    def summary(self) -> TrackingSummary:
        with closing(self._connect()) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    count(*) AS total_attempts,
                    count(*) FILTER (WHERE status = 'success') AS successful_attempts,
                    count(*) FILTER (WHERE status = 'failure') AS failed_attempts,
                    coalesce(sum(input_tokens), 0) AS input_tokens,
                    coalesce(sum(output_tokens), 0) AS output_tokens,
                    coalesce(sum(total_tokens), 0) AS total_tokens,
                    sum(estimated_cost_usd) AS estimated_cost_usd,
                    avg(latency_ms) AS average_latency_ms
                FROM llm_usage
                """
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Usage summary query returned no row")
        values = cast(dict[str, Any], row)
        return TrackingSummary(
            total_attempts=int(values["total_attempts"]),
            successful_attempts=int(values["successful_attempts"]),
            failed_attempts=int(values["failed_attempts"]),
            input_tokens=int(values["input_tokens"]),
            output_tokens=int(values["output_tokens"]),
            total_tokens=int(values["total_tokens"]),
            estimated_cost_usd=(
                float(values["estimated_cost_usd"])
                if values["estimated_cost_usd"] is not None
                else None
            ),
            average_latency_ms=(
                float(values["average_latency_ms"])
                if values["average_latency_ms"] is not None
                else None
            ),
        )

    def refresh_prometheus_metrics(self) -> None:
        """Refresh historical template counts for Prometheus/Grafana."""
        for template_id in TEMPLATE_CONTRACTS:
            for status in ("success", "failure"):
                DB_TEMPLATE_ATTEMPTS.labels(template_id=template_id, status=status).set(
                    0
                )
        with closing(self._connect()) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*) AS attempts,
                       coalesce(sum(input_tokens), 0) AS input_tokens,
                       coalesce(sum(output_tokens), 0) AS output_tokens,
                       coalesce(avg(input_tokens), 0) AS average_input_tokens,
                       coalesce(avg(output_tokens), 0) AS average_output_tokens,
                       coalesce(sum(estimated_cost_usd), 0) AS cost,
                       coalesce(avg(latency_ms), 0) AS latency,
                       coalesce(
                           percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms),
                           0
                       ) AS p95_latency,
                       count(*) FILTER (WHERE attempt > 1) AS retries
                FROM llm_usage
                """
            )
            totals = cast(dict[str, Any], cursor.fetchone())
            cursor.execute(
                """
                SELECT template_id, status, count(*) AS attempts
                FROM llm_usage
                GROUP BY template_id, status
                """
            )
            rows = cursor.fetchall()
        DB_ATTEMPTS.set(float(totals["attempts"]))
        DB_INPUT_TOKENS.set(float(totals["input_tokens"]))
        DB_OUTPUT_TOKENS.set(float(totals["output_tokens"]))
        DB_AVERAGE_INPUT_TOKENS.set(float(totals["average_input_tokens"]))
        DB_AVERAGE_OUTPUT_TOKENS.set(float(totals["average_output_tokens"]))
        DB_TOTAL_COST_USD.set(float(totals["cost"]))
        DB_AVERAGE_LATENCY_MS.set(float(totals["latency"]))
        DB_P95_LATENCY_MS.set(float(totals["p95_latency"]))
        DB_RETRIES.set(float(totals["retries"]))
        for row in rows:
            values = cast(dict[str, Any], row)
            DB_TEMPLATE_ATTEMPTS.labels(
                template_id=str(values["template_id"]),
                status=str(values["status"]),
            ).set(float(values["attempts"]))
