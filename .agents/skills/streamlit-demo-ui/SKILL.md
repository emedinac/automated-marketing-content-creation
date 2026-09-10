---
name: streamlit-demo-ui
description: >
  Build a lightweight Streamlit app to demo the /upload and /generate FastAPI
  endpoints live during a presentation. Use only as a presentation/demo aid,
  never as the production client — Customer C's actual client is a separate
  system outside this repo's scope. Do not use for a persisted, authenticated,
  or production-facing UI.
---

# Streamlit Demo UI

Use this skill together with the applicable `AGENTS.md`.

## Scope guardrail

This UI exists to make the presentation demo-able live instead of walking
through Swagger/curl. It is not part of the architecture design and must
never be presented as "the client" — the diagram's `Client` node is Customer
C's own system, not this app.

Only build this once both endpoints work correctly against real requests
(same "verify first" principle as `gcp-terraform-deploy`) — a polished demo
UI in front of a broken backend is worse than no UI at all. The backend is
the actual interview deliverable; this is a thin wrapper around it.

## Workflow

1. Single-file `streamlit_app.py`, calling the FastAPI backend over HTTP via
   `requests`/`httpx` — never import backend modules and call functions
   in-process. The demo must exercise the real API contract, not bypass it.
2. Backend base URL from an env var (`BACKEND_URL`, default
   `http://localhost:8000`), never hardcoded.
3. Upload view: form for `sender_id`, `receiver_id`, `role`, a
   `st.file_uploader(accept_multiple_files=True)` for PDFs, POST to
   `/upload`, display the raw JSON response.
4. Generate view: form for `sender_id`, `receiver_id`, `prompt`,
   `template_id`, POST to `/generate`. The prototype's `/generate` is
   synchronous — render the result directly, no polling/job-status UI (that
   only applies to the async production design, not this prototype).
5. Render the result readably: sections with word count vs. word limit
   (flag over-limit), image placeholders, theme color swatches. This is
   where the demo value actually is — showing the constraints being
   respected, not just "an LLM replied."
6. Wrap each request in try/except and show `st.error(...)` with the actual
   backend error body — don't let the demo silently hang or crash mid
   presentation.

## Explicitly out of scope

Do not add these — each is effort spent on the demo instead of the actual
deliverable:

- Authentication or session persistence across reloads
- Custom theming/branding beyond Streamlit defaults
- Multi-page app structure — one page, two forms is enough
- Deployment (Cloud Run, Streamlit Community Cloud, etc.) — run locally
  during the presentation; nothing to deploy or tear down
- Any business logic (validation, retries, grounding checks) — that
  belongs in the backend; this app only calls it and renders the response

## Verification

- Start the real FastAPI backend locally, then run the Streamlit app
  against it — never verify against mocked responses.
- Actually upload a real PDF and generate an article through the UI before
  calling it done; confirm the rendered output matches what the backend
  actually returned, not what you expect it to return.

## Reporting and handoff

Report concisely:

- the two flows implemented, and confirmation both were exercised against
  the live backend, not just written
- the env var used for the backend URL
- explicit note that this is a demo aid, excluded from the architecture
  diagram and from the production-considerations discussion
