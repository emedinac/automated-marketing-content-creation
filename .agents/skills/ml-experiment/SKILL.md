---
name: ml-experiment
description: >
  Run disciplined ML experiments from data inspection through model comparison
  and reporting. Use when training, evaluating, comparing, or selecting
  predictive models. Emphasize leakage-safe evaluation, reproducibility,
  simple baselines, and evidence-backed conclusions.
---

# ML Experiment

Use this skill together with the applicable `AGENTS.md`.

## Workflow

1. Read the task, data documentation, existing code, and project rules.
2. Define the prediction target, evaluation goal, and operational constraints.
3. Inspect the data before modeling.
4. Define a leakage-safe validation strategy and simple baseline.
5. Build the simplest credible model first.
6. Compare alternatives only when they test a meaningful hypothesis.
7. Evaluate aggregate and relevant subgroup performance.
8. Record reproducible settings and results.
9. Select the model based on evidence and task constraints, not complexity.
10. Report limitations, uncertainty, and the highest-value next step.

## Environment

Preserve the repository's existing Python toolchain and lockfile. If none
exists, default to Python 3.12+ and Poetry 2.X with committed `pyproject.toml` and
`poetry.lock`.

Add only dependencies required by the experiment.

If the task also requires creating a service, use the
`bootstrap-python-microservice` skill as well.

## Data checks

Before training, inspect:

- schema and target semantics
- missing/invalid values and duplicates
- target/class distribution
- important categorical or subgroup distributions
- suspicious identifiers or leakage paths
- train/validation/test representativeness

Use documented categorical domains when available, not only values observed in
the sample. Do not modify raw source data in place.

Follow the data/ML layout in `AGENTS.md`. Keep reusable preprocessing,
validation, feature, model, and evaluation logic under `src/`.

## Evaluation and model comparison

Always include:

- a simple baseline
- a clearly defined validation/test strategy
- primary metric(s) and why they matter
- relevant subgroup/slice results when meaningful

Do not repeatedly tune against the final test set.

When labels contain uncertainty, disagreement, or noise, account for it when
interpreting results.

Compare models using the same split and evaluation protocol. Prefer the
simplest model that performs credibly under the task constraints.

A more complex model should justify its additional cost with measurable value.

When relevant, consider predictive quality, inference latency, memory,
training/serving cost, portability, interpretability, and operational complexity.

## Confidence and uncertainty

When predictions expose confidence or uncertainty, verify that it is trustworthy
and useful for downstream decisions.

Depending on the model, consider:

- probability calibration for classification
- prediction intervals or uncertainty coverage for regression
- performance on low-confidence vs high-confidence predictions
- confidently wrong predictions

If confidence affects an action, identify how low-confidence cases should be
handled rather than treating every prediction equally.

## Reproducibility and discipline

When practical:

- fix random seeds
- record split logic and preprocessing choices
- record model parameters and material package/model versions
- save results in a structured, comparable form

Do not rely on undocumented notebook state. Move reusable notebook or pipeline
logic into importable code under `src/`.

Establish a baseline before large hyperparameter searches. Change one meaningful
factor at a time when possible.

Treat unexpectedly strong results as suspicious until leakage and split issues
have been checked. Never fabricate or infer unmeasured results.

## Verification

Before finishing:

- rerun the selected experiment from a clean entrypoint when practical
- confirm reported metrics match generated outputs
- run relevant project tests/checks
- verify that training does not improperly use target or test information

Never claim an experiment, metric, or benchmark was run unless it was executed.

## Reporting and handoff

Report concisely:

- data issues and limitations
- baseline and models compared
- primary and relevant subgroup metrics
- confidence/uncertainty findings when relevant
- selected model and tradeoff rationale
- constraints affecting the decision
- one high-value next step
- intentionally deferred work

Separate measured results from assumptions or hypotheses.

Use specialized skills for serving, APIs, Docker, persistence, messaging,
observability, deployment, or platform-specific MLOps only when required.
