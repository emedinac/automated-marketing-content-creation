---
name: gcp-terraform-deploy
description: >
  Deploy a containerized service to GCP Cloud Run using Terraform. Use only
  when a task requires provisioning real GCP infrastructure, as opposed to
  designing/documenting a cloud architecture. Do not use for architecture
  diagrams or design-only deliverables.
---

# GCP Terraform Deploy

Use this skill together with the applicable `AGENTS.md`.

## Scope guardrail

Only invoke this skill once the service being deployed runs and is tested
locally. Building deployment infrastructure for an unverified backend is
infrastructure without a concrete reason (`AGENTS.md`) — verify first,
deploy second.

## Workflow

1. Confirm the container builds and runs locally before writing any
   Terraform. If no `Dockerfile` exists yet: use a slim official Python
   base image, multi-stage build (install deps in a build stage, copy only
   the built venv/artifacts + source into a slim runtime stage), run as a
   non-root user, and expose the port Cloud Run injects via `$PORT` (do
   not hardcode 8080 in the app if Cloud Run overrides it).
2. Scaffold a single Terraform root module. For a prototype, **local
   state is sufficient** — do not introduce a GCS remote backend or state
   locking unless multi-person or multi-environment use is a real,
   stated requirement. That complexity is unjustified otherwise.
3. Define the minimum required resources only:
   - Artifact Registry repository for the container image
   - A **dedicated service account** for the Cloud Run service — never
     the default compute service account — with the minimum IAM roles it
     actually needs (not `roles/editor`)
   - `google_cloud_run_v2_service` referencing the built image
   - `google_cloud_run_v2_service_iam_member` granting `allUsers` +
     `roles/run.invoker` **only if the endpoint is genuinely meant to be
     public**; otherwise scope invocation to specific principals
4. Put any secrets (LLM provider API key) in Secret Manager, referenced by
   the Cloud Run service. Never as plaintext Terraform variables, `.tfvars`
   committed to the repo, or environment variables in source.
5. Set explicit `min_instance_count`/`max_instance_count` sized for a
   prototype (e.g. min 0 to avoid idle billing, small max to cap cost
   exposure).
6. Run `terraform plan` and review the diff before `apply`. Never apply
   unreviewed.
7. Document the teardown command (`terraform destroy`) so the prototype
   doesn't leave billable resources running after a demo/interview.

## Explicitly out of scope for a prototype

Do not add these unless the task states they're required — each is
unjustified complexity at this scale:

- CI/CD pipeline for the Terraform itself
- Multi-environment (dev/staging/prod) structure
- VPC connector / private networking
- Custom domain mapping
- Terragrunt or any multi-stack orchestration layer

## Verification

- Run `terraform validate` and `terraform plan`; capture and report the
  actual output.
- After `apply`, make a real request against the deployed Cloud Run URL
  and confirm the two required endpoints actually respond before claiming
  the deployment succeeded. Never report "deployed" based on `apply`
  exiting 0 alone.

## Reporting and handoff

Report concisely:

- resources created and the dedicated service account's granted roles
  (and why each is minimal, not broad)
- secret handling approach
- expected cost exposure (should be ~$0 at prototype traffic under the
  free tier; state the assumption)
- the teardown command, so cost doesn't continue after handoff

`AGENTS.md`'s rule — never claim a check passed unless it was actually
executed — applies directly here: never claim "deployed" unless a live
request against the Cloud Run URL was actually made and succeeded.
