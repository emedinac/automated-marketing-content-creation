# Architecture Decisions

## Purpose

This document captures the main architecture choices behind the Automated Generative Marketing Collateral system.

The production design is more complete than the take-home prototype. The prototype is intentionally smaller and synchronous in some places, mainly to avoid spending time reproducing cloud infrastructure that is not needed to demonstrate the core solution.

## Prototype status

Implemented locally:

* synchronous in-memory PDF ingestion with text, table, image-metadata and OCR support
* synchronous Gemini generation with structured-output and deterministic validation
* five fixed text templates: newsletter, brochure, slogan, case study and event invitation
* PDF size/MIME validation, optional PostgreSQL usage tracking, Prometheus/Grafana metrics and evaluation fixtures
* lightweight grounding checks, source-reference prompts and explicit human-review flags
* deterministic profile-context compression for generation while retaining raw extracted text

Production design only:

* GCP infrastructure, durable asynchronous workers and job state
* durable profiles/assets, full asset matching, sentence-level provenance and semantic grounding checks
* authentication, tenant authorization, a human-review queue and production rollout controls

---

## 1. GCP for the production stack

For production I would use:

* Cloud Run for the API and workers
* Pub/Sub for asynchronous jobs
* Cloud Storage for PDFs and extracted assets
* Document AI for parsing PDFs
* Firestore for company profiles and job state
* Vertex AI / Gemini for generation
* Cloud Logging and Monitoring for observability
* Cloud Build for CI

This workload fits managed services quite well, so I do not see a reason to introduce Kubernetes at this stage.

One downside is the dependency on GCP services. Because of that, provider-specific implementations should stay behind adapters instead of leaking into the application logic.

---

## 2. Keep application logic independent from infrastructure

The project follows a lightweight hexagonal structure:

```text
adapters -> application -> domain
```

FastAPI, Gemini, Firestore, Pub/Sub and PDF parsing are infrastructure concerns.

The actual use cases, for example uploading company context or generating an article, should not depend directly on GCP SDKs or LangChain-specific classes.

This also makes the prototype easier to test because cloud implementations can be replaced with local adapters.

---

## 3. Production generation should be asynchronous

In production, `POST /generate` creates a job and returns a `job_id`.

A Pub/Sub message then triggers a Cloud Run worker which performs the actual generation and updates the job state.

A simple state flow could be:

```text
queued -> processing |-> review_required -> complete
                     |-> failed
```

The prototype can stay synchronous because the scope is much smaller.

The local prototype intentionally has no authentication or tenant authorization. Those belong at the production API Gateway/service boundary.

For production, however, parsing, LLM calls, retries, grounding and potentially human review can take too long for a normal HTTP request.

---

## 4. Firestore first, semantic search only when needed

The generation request already tells us which sender and receiver are involved.

Because of that, the normal retrieval path is simply:

```text
sender_id / receiver_id -> Firestore company profiles
```

I would not add vector search by default.

Vertex AI Search becomes useful when one company has many large documents and retrieving only a relevant subset improves generation quality or reduces the amount of context sent to Gemini.

Otherwise it adds indexing, embeddings, retrieval tuning and another component to operate without a clear benefit.

The prototype applies deterministic context normalization (deduplication, header/footer removal, 6,000-character cap per profile) before prompting, so direct lookup uses a compact, bounded context rather than raw extracted text. This is not a substitute for retrieval - it lowers token cost and reduces noise. Retrieval remains the right upgrade if profiles grow, span multiple documents, or claims require source-level citations.

---

## 5. Keep company profiles and source evidence separate

I would store:

* normalized `CompanyProfile` objects in Firestore
* parsed source content and extracted assets in Cloud Storage

The profile is optimized for fast generation-time lookup.

The source documents remain the actual evidence used for grounding, provenance and potentially reprocessing later.

Source references should ideally identify the document, page and asset or section.

This is important because the normalized profile should not become the only source of truth.

---

## 6. Structured output still needs Python validation

Gemini should return schema-constrained structured output.

But the application should still validate:

* required fields
* section/template identifiers
* word limits
* image placeholders
* layout and theme fields

The LLM should not be responsible for enforcing deterministic rules.

Retries should also be bounded. After the retry limit, only an otherwise valid response with a word-limit violation should receive a deterministic correction; an invalid schema should fail explicitly instead of being truncated.

For example, if the article is already correct except that a section contains three extra words, I would rather fix that deterministically than call the model again.

This also avoids unnecessary token usage and makes the behaviour easier to predict.

---

## 7. PDFs and prompts are untrusted input

I would keep three things clearly separated:

1. application/system instructions
2. the user's request
3. retrieved company context

Content extracted from a PDF should always be treated as data, not as instructions.

I would use explicit prompt sections, sanitization, restricted tool access, schema validation and least-privilege permissions.

This reduces prompt-injection risk, although it obviously does not make prompt injection impossible.

---

## 8. Grounding, provenance and human review

A structurally valid JSON response can still contain unsupported facts.

After generation I would:

1. validate the structure
2. check factual claims against the source material
3. attach source references where possible
4. apply the review policy

Human review should be configurable instead of always required.

For example, a customer may want certain templates to be automatically published while others still require editorial approval.

If grounding repeatedly fails, the job should go to review or fail explicitly instead of publishing questionable content.

I would also avoid using the model's own "confidence" as if it was a calibrated probability of being correct.

---

## 9. Evaluation and versioning

Production logs should not automatically become the evaluation dataset.

I would start with a small curated golden set (I took n=5 for simplicity, after spending 30-45min seaching for data) containing approved sender/receiver examples and expected outputs.

At minimum I would evaluate:

* faithfulness to the source material
* relevance to the sender and receiver
* template correctness
* constraint compliance

Prompt, model and template changes should be evaluated before they are promoted.

Each generation job should also record which prompt, model and template version produced it.

If a candidate performs worse than the current version, it simply does not get promoted.

The current production version stays active.

---

## 10. Observability

For this system, HTTP uptime alone is not enough.

I would monitor:

* total job latency
* LLM latency
* token usage and estimated cost
* validation failures
* retries
* grounding failures
* terminal job failures
* human-review rate
* prompt/model/template versions

A sudden increase in grounding failures or human review requests can be just as important as a normal infrastructure alert.

The production design should log request metadata, status, versions, latency, token usage and cost by default. Raw prompts, PDF content and model responses should not be logged unless explicitly redacted and justified. The prototype exports Prometheus metrics for LLM attempts, tokens, estimated cost, latency and validation retries; when `DATABASE_URL` is configured it also exposes historical PostgreSQL usage through the tracking dashboard.

---

## Others

There are a few additional production concerns I would account for, but I would not make each of them a separate architecture block:

* **Idempotency:** Pub/Sub workers must handle duplicate messages.
* **DLQ:** repeatedly failing jobs need a dead-letter path.
* **Tenant isolation:** documents, profiles, assets and jobs must belong to a tenant.
* **Authorization:** knowing a `job_id` or `company_id` must not be enough to access it.
* **IAM:** Cloud Run services should use dedicated service accounts.
* **Secrets:** credentials belong in Secret Manager.
* **Retention:** define how long PDFs, outputs and logs are stored.
* **Retries:** retry transient failures with bounded backoff.
* **Rate limits:** protect both the API and expensive model calls.
* **Cost:** monitor model cost per generation.
* **Fallback models:** only use a fallback that has been evaluated beforehand.
* **Rollout:** important prompt/model changes can use a small canary first.
* **File validation:** enforce file type and size limits before parsing.
* **Data residency:** depends on the customer's requirements.
* **SLOs:** numerical targets should come from customer requirements, not be guessed.
* **Backpressure:** workers should not overload downstream services when the queue grows.

These are important for a real deployment, but drawing every one in the main diagram would make it harder to understand the actual AI pipeline.

---

## Open questions

Questions I would ask during the interview before deploying a validated system:

1. What does "factually correct" mean for the customer?
2. Can they provide examples of approved sender/receiver articles?
3. Is human review mandatory, configurable or not needed?
4. Can the system use external images, or only assets found in the PDFs?
5. What is the exact publishing-template JSON schema?
6. What volume, document size and latency should the system support?
7. Are there specific retention or regional data requirements?

Without these answers I would not claim guaranteed factual correctness, zero hallucinations or specific production SLOs.
