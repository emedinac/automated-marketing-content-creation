# Automated Generative Marketing Collateral

It creates grounded B2B marketing collateral from "sender" and "receiver" company context. Currently, this process is highly manual, tedious, and difficult to scale for personalized marketing materials (like physical newsletters and brochures).

## Flow

1. Upload company PDFs.
2. Extract company context.
3. Generate structured, template-ready content.
4. Validate output and flag drafts for review when needed.

## Architecture

The proposed production design uses Cloud Run, Cloud Storage, Pub/Sub, Document AI, Firestore, Vertex AI Gemini, grounding checks, human review, and observability. These cloud components are a target architecture; the local prototype remains synchronous and in-memory for profiles/assets.

- [Architecture diagram](docs/architecture/system-architecture.mmd)
- [Architecture source](docs/architecture/system-architecture.eraserdiagram)
- [Design decisions](docs/architecture/decisions.md)

## Prototype

The local prototype provides `/upload`, `/generate`, `/assets/{asset_id}`, `/tracking/summary`, `/metrics`, and a Streamlit demo. `POST /generate` returns the article synchronously; it does not create a job or expose a status endpoint. Gemini is used only when `GOOGLE_CLOUD_PROJECT` is configured; otherwise, or if Gemini fails, the service returns a safe fallback draft marked `review_required`.

PDF extraction uses `pdfplumber` (MIT) for text and tables, `pypdf` for embedded image assets, and Tesseract OCR for supported image-only PDFs. OCR attempts text extraction from embedded page images; it does not render arbitrary scanned PDF pages, so unsupported scans are rejected clearly.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for setup, configuration, running, observability, and verification commands.
