# Development

Requires Python 3.12+ and Poetry.

## Setup

```bash
poetry install
```

## Configure Gemini

```bash
export GOOGLE_CLOUD_PROJECT="your-gcp-project"
export GOOGLE_CLOUD_LOCATION="global"
export GEMINI_MODEL="gemini-2.5-flash"
gcloud auth application-default login
```

Enable `aiplatform.googleapis.com`, billing, and Vertex AI User access. Leave `GOOGLE_CLOUD_PROJECT` empty to use the fallback generator.

## Run

```bash
poetry run uvicorn marketing_collateral.main:app --host 0.0.0.0 --port 8000 --reload
poetry run streamlit run streamlit_app.py
```

API docs: `http://localhost:8000/docs`. Set `BACKEND_URL` for a non-default API URL.

## API examples

```bash
curl -F sender_id=ibm -F receiver_id=dhl -F role=sender \
  -F files=@eval/cases/01_ibm_dhl/sender.pdf \
  http://localhost:8000/upload
```

```bash
curl -X POST http://localhost:8000/generate \
  -H 'content-type: application/json' \
  -d '{"sender_id":"ibm","receiver_id":"dhl","prompt":"Write a grounded B2B article","template_id":"newsletter"}'
```

Profiles and assets are in memory. Fetch an extracted asset with:

```bash
curl -o asset.bin http://localhost:8000/assets/{asset_id}
```

## Observability

Set the Grafana password and database URL before starting the services and API:

```bash
export GRAFANA_ADMIN_PASSWORD="choose-a-local-password"
export DATABASE_URL="postgresql://marketing:marketing@localhost:5432/marketing_collateral"
export PROMPT_VERSION="v1"
docker compose up -d
```

Start the API in the same shell so it uses PostgreSQL. Without `DATABASE_URL`,
the API uses in-memory tracking and the tracking dashboard labels it non-durable.

See [local observability](docs/local-observability.md). URLs: Streamlit `:8501/tracking`, Prometheus `:9090`, Grafana `:3000`.

## Verify

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src
poetry run pytest
```
