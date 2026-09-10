from prometheus_client import Counter, Gauge, Histogram

LLM_ATTEMPTS = Counter(
    "marketing_collateral_llm_attempts_total",
    "Number of LLM generation attempts.",
    ["model", "status"],
)
LLM_TEMPLATE_ATTEMPTS = Counter(
    "marketing_collateral_llm_template_attempts_total",
    "Number of LLM generation attempts by template.",
    ["template_id", "status"],
)
DB_TEMPLATE_ATTEMPTS = Gauge(
    "marketing_collateral_db_template_attempts",
    "Historical LLM attempts loaded from the PostgreSQL usage ledger.",
    ["template_id", "status"],
)
DB_ATTEMPTS = Gauge("marketing_collateral_db_attempts", "Historical LLM attempts.")
DB_INPUT_TOKENS = Gauge(
    "marketing_collateral_db_input_tokens", "Historical input tokens."
)
DB_OUTPUT_TOKENS = Gauge(
    "marketing_collateral_db_output_tokens", "Historical output tokens."
)
DB_AVERAGE_INPUT_TOKENS = Gauge(
    "marketing_collateral_db_average_input_tokens",
    "Average input tokens per historical attempt.",
)
DB_AVERAGE_OUTPUT_TOKENS = Gauge(
    "marketing_collateral_db_average_output_tokens",
    "Average output tokens per historical attempt.",
)
DB_TOTAL_COST_USD = Gauge(
    "marketing_collateral_db_estimated_cost_usd", "Historical estimated LLM cost."
)
DB_AVERAGE_LATENCY_MS = Gauge(
    "marketing_collateral_db_average_latency_ms", "Historical average LLM latency."
)
DB_P95_LATENCY_MS = Gauge(
    "marketing_collateral_db_p95_latency_ms", "Historical p95 LLM latency."
)
DB_RETRIES = Gauge("marketing_collateral_db_retries", "Historical validation retries.")
LLM_TOKENS = Counter(
    "marketing_collateral_llm_tokens_total",
    "Number of LLM tokens reported by the provider.",
    ["model", "direction"],
)
LLM_COST_USD = Counter(
    "marketing_collateral_llm_estimated_cost_usd_total",
    "Estimated LLM cost in US dollars.",
    ["model"],
)
LLM_LATENCY_SECONDS = Histogram(
    "marketing_collateral_llm_latency_seconds",
    "LLM generation-attempt latency.",
    ["model", "status"],
)
LLM_RETRIES = Counter(
    "marketing_collateral_llm_retries_total",
    "Number of LLM validation retries.",
    ["model"],
)


def record_attempt_metrics(
    *,
    model: str,
    status: str,
    input_tokens: int | None,
    output_tokens: int | None,
    estimated_cost_usd: float | None,
    latency_ms: float,
    retry: bool,
    template_id: str,
) -> None:
    LLM_ATTEMPTS.labels(model=model, status=status).inc()
    LLM_TEMPLATE_ATTEMPTS.labels(template_id=template_id, status=status).inc()
    LLM_LATENCY_SECONDS.labels(model=model, status=status).observe(latency_ms / 1000)
    if input_tokens is not None:
        LLM_TOKENS.labels(model=model, direction="input").inc(input_tokens)
    if output_tokens is not None:
        LLM_TOKENS.labels(model=model, direction="output").inc(output_tokens)
    if estimated_cost_usd is not None:
        LLM_COST_USD.labels(model=model).inc(estimated_cost_usd)
    if retry:
        LLM_RETRIES.labels(model=model).inc()
