---
name: self-hosted-observability
description: >
  Stand up self-hosted Prometheus + Grafana (docker-compose) for a service
  running on persistent compute you control (a VPS, a long-running
  container host, bare metal, or GKE) — never for scale-to-zero serverless
  compute. Use only when the target deployment is confirmed to be
  persistent compute; otherwise use `gcp-observability` (Cloud Run and
  other GCP-managed serverless targets).
---

# Self-Hosted Observability (Prometheus + Grafana)

Use this skill together with the applicable `AGENTS.md`.

## Scope guardrail — read first

This skill assumes the service being monitored is **long-running and
scrapable**: it stays up between scrapes at a known address. That is true
for a VPS, a persistent container/VM, or a GKE deployment. It is **false**
for Cloud Run, Cloud Functions, Lambda, or any compute that scales to
zero — Prometheus cannot scrape a target that doesn't exist between
requests. If the target is serverless, stop and use `gcp-observability`
instead; do not adapt this skill with a Pushgateway workaround unless that
workaround is the explicit, stated requirement.

Do not invoke this skill speculatively "in case it's needed later." Only
use it once the deployment target is confirmed persistent.

## Workflow

1. Confirm the compute target is persistent (per guardrail above) before
   writing any config.
2. Instrument the application with a Prometheus client library
   (`prometheus_client` for Python), exposing a `/metrics` endpoint on the
   app itself. Use Counters for discrete events, Histograms for durations.
   Low-cardinality labels only — never a label with unbounded values
   (request IDs, user IDs); this is what causes Prometheus memory blowups.
3. `docker-compose` with three services: the app, Prometheus, Grafana.
   Prometheus scrapes the app's `/metrics` on an interval (start at 15s);
   config lives in a committed `prometheus.yml`, not inline in compose.
4. Grafana: provision the Prometheus data source and starter dashboards
   as code (YAML provisioning files under `grafana/provisioning/`), not
   clicked together manually — manual dashboards don't survive a
   container recreate.
5. Grafana's own internal state (users, dashboard metadata) defaults to
   embedded SQLite. **Do not add Postgres for this** unless running
   multiple Grafana instances behind a load balancer — a single-instance
   setup has no concrete reason for an external database (`AGENTS.md`).
6. Set Prometheus retention explicitly (`--storage.tsdb.retention.time`);
   local disk retention is not "long-term storage" — decide and state the
   window (e.g. 15d) rather than leaving the default unexamined.
7. Do not expose Prometheus or Grafana's admin interface publicly without
   auth. Grafana ships with a default admin password — change it via env
   var, never leave it default even for a demo.

## Explicitly out of scope

- Long-term metrics retention beyond local disk (that's a remote-write /
  Thanos / Mimir decision — only take it on if retention needs actually
  exceed what local Prometheus disk can hold, and say so explicitly)
- Postgres or any external DB for Grafana state, unless multi-instance
  Grafana is a real, stated requirement
- Alertmanager clustering, federation, or HA Prometheus — single-instance
  is sufficient until a stated requirement says otherwise
- Using this for Cloud Run or any scale-to-zero target (see guardrail)

## Verification

- Confirm Prometheus's own `/targets` page shows the app target as `UP`,
  not just that `docker-compose up` exited 0.
- Trigger an instrumented code path and confirm the metric value changes
  in Prometheus's query UI before checking the Grafana dashboard.
- Confirm the Grafana dashboard renders from the provisioned data source,
  not a hardcoded/mock panel.

## Reporting and handoff

Report concisely:

- confirmed deployment target (persistent compute) and why this skill
  applied instead of `gcp-observability`
- metrics instrumented and why
- retention window chosen for Prometheus
- confirmation Grafana admin credentials were changed from default
- explicit note that Postgres was not added, and why (or why it was, if a
  real multi-instance requirement existed)

Use `gcp-observability` instead if the target compute is serverless or
scale-to-zero.
