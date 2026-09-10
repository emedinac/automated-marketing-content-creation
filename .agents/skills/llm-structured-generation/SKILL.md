---
name: llm-structured-generation
description: >
  Generate schema-validated structured output (JSON) from an LLM given
  retrieved context. Use when a task requires an LLM call whose output must
  conform to a defined contract for downstream consumption (e.g. populating
  a template, a database row, or an API response). Not for training or
  evaluating predictive models (use `ml-experiment`) and not for validating
  a self-trained model's serving characteristics (use
  `ml-serving-validation`) — this skill is for calling a pretrained LLM API.
---

# LLM Structured Generation

Use this skill together with the applicable `AGENTS.md`.

## Core principle

Do not hand-roll "prompt the model to return JSON, then `json.loads` and
hope." That is the least reliable tier of structured output and belongs
only as a last-resort fallback. Default to schema-first generation with
enforced validation.

## Workflow

1. Define the target output as a Pydantic model **first** — this is both
   the validation contract and the documentation of what the LLM must
   produce. Keep nesting to 2–3 levels max; deeper schemas measurably
   increase error rates.
2. Choose an enforcement method and document why:
   - **Provider-native structured output** (e.g. passing a Pydantic model
     directly, or JSON-schema-constrained decoding) when locked to one
     provider and a zero-retry guarantee matters.
   - **Instructor** (Pydantic-based, provider-agnostic) when portability
     across providers matters, or when using a free/low-cost provider that
     may need to be swapped. It wraps the call, validates against the
     Pydantic model, and on failure feeds the validation error back to the
     model as a follow-up prompt — a materially more effective recovery
     loop than catching a bare JSON parse exception and retrying blind.
   - Raw prompt-only JSON as a fallback only, if no schema-enforcement
     path is available for the chosen provider.
3. Keep Pydantic validators simple and deterministic. Their job is to catch
   model errors and drive a retry — not to implement business logic that
   belongs in the application layer.
4. Set a bounded retry count (2–3) with the validation error fed back to
   the model. Do not retry indefinitely, and do not silently return
   best-effort malformed content if all retries fail — surface a clear
   error to the caller.
5. Encode task-specific constraints in the schema itself wherever possible
   (e.g. a length-bounded field for a word limit, an `Enum` for allowed
   theme colors, a required field for an image placeholder) rather than
   relying on the prompt alone to produce compliant output.
6. Keep the LLM call behind a port/interface in the application layer; the
   concrete client (Instructor-wrapped SDK, provider SDK) is an adapter and
   should be swappable.
7. Never fabricate a "successful" generation in tests, logs, or reporting.

## Prompt construction

- Separate retrieved context (e.g. extracted sender/receiver company data)
  from instructions clearly in the prompt — don't interleave them.
- State factual-grounding constraints explicitly when the task requires
  factual correctness (e.g. "only use facts present in the provided
  context; do not invent claims about either company").

## Testing

- Unit test schema validation independently of any live LLM call: construct
  known-good and known-bad payloads and assert the Pydantic model accepts/
  rejects correctly. This does not require API access and should always run.
- Integration test the real call only if time/API budget allows. Otherwise
  mock the LLM client at the port boundary and say so explicitly in the
  handoff — never imply an untested live call path was verified.

## Verification

Confirm schema validation tests were actually executed, and confirm the
retry/error path has at least one test (a forced validation failure) rather
than being assumed to work.

## Reporting and handoff

Report concisely:

- provider/model used, and the enforcement library chosen and why
- the output schema (or a pointer to it)
- retry policy (count, what triggers it)
- what was tested against a live API vs. mocked
- known failure modes (e.g. behavior when context is insufficient to
  satisfy a required field)

Use `pdf-context-extraction` for how the input context was produced and
`http-api-service` for how this is exposed.
