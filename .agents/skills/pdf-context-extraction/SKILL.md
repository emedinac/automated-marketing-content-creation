---
name: pdf-context-extraction
description: >
  Extract text, tables, and images from PDF documents for downstream use
  (e.g. as LLM context). Use when a task requires reading structured or
  unstructured content out of PDF files. Not for PDF creation, form
  filling, merging, or watermarking.
---

# PDF Context Extraction

Use this skill together with the applicable `AGENTS.md`.

## Workflow

1. Read the task requirements — extract only what's actually needed
   (text only? tables? images?). Do not extract everything speculatively.
2. Choose and document the extraction library (see "Library choice" below)
   as an explicit, written assumption — do not pick silently.
3. Build a single ingestion boundary: PDF bytes in => a structured document
   object out (text blocks, tables, image references with metadata). Keep
   this in the domain/application layer, independent of the HTTP adapter
   that receives the upload.
4. Extract text preserving reading order. If source documents may be
   multi-column, verify against a multi-column fixture — some libraries
   silently interleave columns.
5. Extract tables only if the task needs structured tabular data
   downstream; otherwise flatten to text and note the limitation.
6. Extract embedded images to a content-addressed store (hash-based name)
   with page/position metadata — not the file's internal embedded name.
7. Never fabricate extracted content. If a page or section fails cleanly,
   return a partial result and flag it explicitly. Do not silently return
   empty text as if extraction succeeded on an empty document.
8. Treat uploaded PDFs as read-only input.

## Library choice

Decision to make explicit and document, not default silently:

- **PyMuPDF (`fitz`)** — fastest option, strong text and image extraction,
  usable table extraction. **Licensed AGPL-3.0.** For a real client
  deliverable this requires either open-sourcing the service or a
  commercial license — flag this as a decision point, do not absorb it
  silently into a client-facing prototype.
- **pdfplumber** — MIT licensed, strong table extraction on ruling-line
  tables via fine-grained character/line geometry, but materially slower
  and has documented reading-order issues on multi-column layouts.
- **Default for a prototype**: PyMuPDF for text and image extraction
  (speed, single dependency); layer pdfplumber only if table accuracy on
  ruled tables matters more than speed and the AGPL tradeoff on the text
  path is acceptable or already decided. State the choice and its
  licensing implication in the README.

## Robustness

- Handle scanned/image-only PDFs (no text layer) explicitly — fail clearly
  and say so, or state OCR is out of scope. Do not silently return an
  empty result as if it were successful.
- Cap input file size before parsing. Malformed PDFs must raise a clear
  domain error, not crash the process — do not silently swallow the
  failure (per `AGENTS.md`).
- Do not trust page count or structure blindly; wrap parsing calls with
  explicit error handling.

## Testing

- Unit test extraction against a small fixture PDF with known text/table/
  image content — assert against known values, not just "did not throw."
- Test the failure path explicitly: corrupt file, empty file, scanned-only
  file.

## Verification

Run the repository's standard checks plus the fixture-based extraction
tests, actually executed. Never claim extraction accuracy that wasn't
measured against a fixture.

## Reporting and handoff

Report concisely:

- library and version chosen, and the licensing note if PyMuPDF is used
- what is extracted vs. intentionally skipped (e.g. OCR out of scope)
- known limitations (multi-column edge cases, scanned PDFs, etc.)

Use `http-api-service` for the upload boundary and
`llm-structured-generation` for what happens to the extracted content next.
