"""Presentation-only usage summary for the local observability stack."""

import os

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")


def compact_number(value: int | float) -> str:
    """Format large dashboard values using Grafana-style suffixes."""
    absolute_value = abs(value)
    if absolute_value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if absolute_value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return f"{value:,.0f}"


st.set_page_config(page_title="LLM Tracking", page_icon="📈")
st.title("LLM tracking")
st.caption("Usage and cost summary from the FastAPI backend.")

try:
    response = httpx.get(f"{BACKEND_URL}/tracking/summary", timeout=15)
    response.raise_for_status()
    summary = response.json()
except Exception as error:
    st.error(f"Could not load tracking data: {error}")
    st.stop()

if not summary["durable"]:
    st.warning("PostgreSQL is not configured; displayed usage is not durable.")

attempts, successes, failures = st.columns(3)
attempts.metric("Attempts (count)", compact_number(summary["total_attempts"]))
successes.metric("Successful (count)", compact_number(summary["successful_attempts"]))
failures.metric("Failed (count)", compact_number(summary["failed_attempts"]))

input_tokens, output_tokens, total_tokens = st.columns(3)
input_tokens.metric("Input tokens (tokens)", compact_number(summary["input_tokens"]))
output_tokens.metric("Output tokens (tokens)", compact_number(summary["output_tokens"]))
total_tokens.metric("Total tokens (tokens)", compact_number(summary["total_tokens"]))

attempt_count = summary["total_attempts"]
average_input = summary["input_tokens"] / attempt_count if attempt_count else 0
average_output = summary["output_tokens"] / attempt_count if attempt_count else 0
average_input_column, average_output_column = st.columns(2)
average_input_column.metric(
    "Average input (tokens/call)", compact_number(average_input)
)
average_output_column.metric(
    "Average output (tokens/call)", compact_number(average_output)
)

cost, latency = st.columns(2)
cost.metric(
    "Estimated cost (USD)",
    "Pricing not configured"
    if summary["estimated_cost_usd"] is None
    else f"${summary['estimated_cost_usd']:.6f}",
)
latency.metric(
    "Average latency (ms/call)",
    "No attempts yet"
    if summary["average_latency_ms"] is None
    else f"{summary['average_latency_ms']:.0f} ms",
)

st.link_button("Open Grafana dashboard", GRAFANA_URL)
