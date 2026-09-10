---
name: gcp-observability
description: >
  Add metrics, dashboards, and alerting for a GCP-hosted service (Cloud Run
  or similar) using push-based OpenTelemetry to Cloud Monitoring, with
  Grafana as an optional read-only visualization layer. Use when a task
  requires production observability beyond basic uptime/logs. Do not
  self-host Prometheus for Cloud Run or other scale-to-zero serverless
  compute — see "Why push, not pull" below. Not for local-only debug
  logging in a prototype.
---

# GCP Observability

Use this skill together with `gcp-terraform-deploy` and the applicable `AGENTS.md`.

## Why push, not pull

Prometheus is pull-based: a server scrapes stable, known targets on an
interval. Serverless compute that scales to zero (Cloud Run, Cloud
Functions) has no stable target to scrape — instances start, serve, and
disappear. Running a self-hosted Prometheus server against this compute
model requires either a Pushgateway (extra stateful component to operate)
or moving the workload to persistent compute (GKE, Compute Engine), which
is a compute-architecture change, not an observability add-on.

The fit for serverless is push-based: the service pushes metrics itself.
Two managed options, in order of preference:

1. **Cloud Run built-in metrics** (Cloud Monitoring) — request count,
   latency, CPU/memory, concurrency. Zero setup, already collected for
   every Cloud Run service.
2. **Custom application metrics** (token usage, validation failures,
   grounding failures, human-review rate, etc.) — instrument with
   OpenTelemetry and export via the Cloud Monitoring exporter. The app
   pushes; nothing needs to be scraped.

Do not run Prometheus, a Pushgateway, or a metrics database (Postgres,
InfluxDB) for this. Cloud Monitoring is the time-series store.

## Where Grafana fits

If Grafana's dashboarding/query UX is preferred over Cloud Monitoring's own
dashboards: point Grafana at Cloud Monitoring as a **data source** (Google
Cloud Monitoring plugin, built into Grafana core). Grafana becomes a
read-only viewer — it queries Cloud Monitoring's API, it does not store or
scrape anything itself. This gets Grafana's UI without a Prometheus server
or a database to operate.

Self-hosted Grafana for this purpose is a single stateless container (no
volume required beyond dashboard JSON, which can be provisioned as code).
Grafana Cloud's free tier is an alternative if not self-hosting even that.

## Workflow

1. Confirm the task actually needs this (`AGENTS.md`: no infra without a
   concrete reason). Cloud Run's built-in metrics alone cover
   uptime/latency/error-rate; only add custom instrumentation for metrics
   that matter to the specific system (e.g. LLM token cost,
   validation/grounding failure rate).
2. Add `opentelemetry-sdk` and `opentelemetry-exporter-gcp-monitoring` via
   the project's dependency manager.
3. Define custom metrics at the application/adapter boundary where the
   event actually happens (e.g. after a validation failure, after a
   grounding check) — not scattered ad hoc through business logic.
4. Use a Counter for discrete events (failures, retries, review triggers)
   and a Histogram for durations (LLM latency, total job latency). Attach
   low-cardinality labels only (e.g. `template_id`, `failure_type`) — never
   unbounded labels like `job_id` or `company_id` (Cloud Monitoring bills
   and limits by time-series cardinality).
5. Grant the Cloud Run service account `roles/monitoring.metricWriter` —
   nothing broader.
6. If using Grafana: add the Cloud Monitoring data source pointed at the
   same GCP project, using a service account with `roles/monitoring.viewer`
   only (read-only, separate from the metric-writing identity).
7. Build dashboards/alerts for the metrics that matter operationally, not
   every metric collected. Alert on symptoms (rising failure rate, latency
   SLO breach), not on every possible signal.

## Explicitly out of scope

- Self-hosted Prometheus server or Pushgateway
- A dedicated metrics/time-series database (Postgres, InfluxDB, etc.)
- Long-term raw-event storage for analytics — that's a data-warehouse
  concern (BigQuery), not observability
- Log-based metrics unless Cloud Monitoring's native metrics genuinely
  can't express the signal

## Verification

- Trigger the instrumented code path (e.g. force a validation failure) and
  confirm the metric actually appears in Cloud Monitoring — do not assume
  the exporter is wired correctly from code review alone.
- If Grafana is added, confirm the dashboard renders real data from the
  data source, not a placeholder/mock panel.

## Reporting and handoff

Report concisely:

- metrics added, and why each one (tied to a real operational question,
  not "nice to have")
- IAM roles granted and to which identity (writer vs viewer separation)
- whether Grafana was added, and confirmation it was verified against live
  data
- cost note: Cloud Monitoring's free tier covers low-volume prototype/demo
  traffic; state this as an assumption, not a guarantee

Use `gcp-terraform-deploy` for provisioning the service account and IAM
bindings this skill assumes.
