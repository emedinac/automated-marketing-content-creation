# Local observability

Set a Grafana password, then start the local PostgreSQL, Prometheus, and Grafana services:

```bash
export GRAFANA_ADMIN_PASSWORD="choose-a-local-password"
docker compose up -d
```

Configure the API to use the Compose PostgreSQL instance before starting it:

```bash
export DATABASE_URL="postgresql://marketing:marketing@localhost:5432/marketing_collateral"
export PROMPT_VERSION="v1"
```

With `DATABASE_URL` configured, the API creates the `llm_usage` and `model_pricing` tables at startup. Add or update the price for the configured model after the API has started:

```bash
docker compose exec postgres psql \
  -U marketing \
  -d marketing_collateral \
  -c "INSERT INTO model_pricing
      (model, input_cost_per_million_tokens, output_cost_per_million_tokens)
      VALUES ('gemini-2.5-flash', 0.30, 2.50)
      ON CONFLICT (model) DO UPDATE SET
      input_cost_per_million_tokens = EXCLUDED.input_cost_per_million_tokens,
      output_cost_per_million_tokens = EXCLUDED.output_cost_per_million_tokens;"
```

Replace the model name and prices with the provider's current rates. Prices are stored per one million tokens. Existing usage records keep the cost that was calculated when they were created; changing this table affects future generations only.

If a model has no pricing row, token usage is still stored but its estimated cost is `NULL`.

Start the applications in separate terminals:

```bash
# Run this in a shell where DATABASE_URL is exported.
poetry run uvicorn marketing_collateral.main:app --host 0.0.0.0 --port 8000
poetry run streamlit run streamlit_app.py
```

Without `DATABASE_URL`, the API still runs but stores usage only in memory; the tracking dashboard marks that data as non-durable.

Useful local URLs:

- Streamlit: <http://localhost:8501>
- Tracking page: <http://localhost:8501/tracking>
- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000>

Grafana uses `admin` and the password in `GRAFANA_ADMIN_PASSWORD`.
