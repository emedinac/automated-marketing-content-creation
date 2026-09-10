---
name: http-api-service
description: >
  Expose HTTP endpoints for a Python service using FastAPI. Use when a task
  requires a running API — request/response models, routing, and file
  uploads. `bootstrap-python-microservice` excludes FastAPI by default;
  this skill is the concrete reason to add it.
---

# HTTP API Service

Use this skill together with `bootstrap-python-microservice` and the
applicable `AGENTS.md`.

## Workflow

1. Read `AGENTS.md`, `bootstrap-python-microservice`, and the task requirements.
2. Confirm the task actually needs a running service (it must — this skill's
   presence is the justification for adding FastAPI).
3. Add `fastapi`, `uvicorn`, and `python-multipart` (required for
   file/form uploads) via Poetry — not unmanaged `pip install`.
4. Define a Pydantic model for every request and response body. Never accept
   or return raw `dict`.
5. Place routers under `adapters/http/`. Handlers stay thin: parse the
   request, call the application/use-case layer, return a response model.
   Business logic does not live in the route handler.
6. Implement the endpoints per task spec.
7. Add tests for the happy path, a validation failure, and at least one
   real boundary case (oversized input, wrong content-type, missing field).
8. Run verification.

## Endpoint design

- If one endpoint produces context that another endpoint must later
  consume (e.g. upload vs. generate), own that state explicitly: an
  in-memory store keyed by the relevant domain identifiers is enough for a
  prototype — document it as a prototype limitation (lost on restart, not
  multi-instance safe) rather than leaving it unowned.
- CPU-bound synchronous work called from an `async def` handler (e.g. PDF
  parsing) blocks the event loop. Either run it via a thread pool
  (`run_in_executor`) or accept and state the blocking tradeoff explicitly
  for a low-concurrency prototype — don't leave it undecided.
- One router per resource/domain concept.
- Return typed error responses with correct HTTP status codes (422 for
  validation, 4xx for client error, 5xx only for genuine server failure).
  Never leak stack traces in the response body.
- Version or namespace routes only if the task requires it — do not add
  speculative API versioning to a prototype.

## File uploads

- Use `UploadFile`, not `bytes = File()` — it streams instead of loading
  the full file into memory, which matters for anything beyond a trivial
  fixture.
- Validate content-type and enforce an explicit max size **before**
  processing. Reject early with a 4xx; do not let unbounded uploads reach
  disk or a parsing library.
- Never trust the client-supplied filename for a storage path — sanitize it
  or, better, discard it and store by a generated ID (path traversal risk).
- Write with `aiofiles` or stream in chunks for non-trivial files. A
  synchronous `open()` call blocks the event loop under concurrent load.
- Store uploaded files under a location the service controls, keyed by a
  generated ID and any domain metadata (e.g. sender/receiver identifiers)
  the task needs — not by original filename.

## Testing

- Use FastAPI's `TestClient` (or `httpx.AsyncClient` for async flows).
- Cover: valid request => correct response shape; invalid/missing fields =>
  422; oversized or wrong-type file => 4xx; the endpoint's actual business
  behavior, not just that it returns 200.

## Verification

Run the applicable checks from `bootstrap-python-microservice`
(`ruff`, `mypy`, `pytest`), plus the endpoint tests specifically. Never
report a check as passing unless it was executed.

## Reporting and handoff

Report concisely:

- endpoints added and their contracts (request/response models)
- upload constraints chosen (max size, allowed content-types) and why
- what is real vs. mocked behind each endpoint
- checks executed

Use `pdf-context-extraction`, `llm-structured-generation`, or
`gcp-terraform-deploy` for concerns behind or beyond the HTTP boundary.
