---
name: ml-serving-validation
description: >
  Validate whether a trained ML model is ready for practical inference.
  Use after model selection when latency, memory, portability, serving cost,
  confidence handling, or deployment feasibility matter. Prefer small
  evidence-producing checks over unnecessary serving infrastructure.
---

# ML Serving Validation

Use with the applicable `AGENTS.md` and `ml-experiment` skill when relevant.

## Workflow

1. Identify the selected model and target inference environment.
2. Define the serving constraints that matter.
3. Create or reuse a deterministic inference entrypoint.
4. Measure relevant runtime characteristics.
5. Test export or optimization only when it addresses a real constraint.
6. Compare quality before and after optimization.
7. Recommend a serving approach and state remaining risks.

## Inference boundary

Keep inference reusable and independent from transport code:

```text
input -> preprocessing -> model -> postprocessing -> prediction
```

Load the model once per process where practical.

Do not add an API, Docker, cloud infrastructure, or orchestration merely to
demonstrate familiarity with those tools.

## Runtime evidence

When relevant, measure directly:

- CPU inference latency, preferably p50/p95 after warm-up
- model load/cold-start time
- artifact size and memory usage
- prediction quality after optimization

For constraints that cannot be reproduced meaningfully locally, such as
production-scale throughput or concurrency, discuss expected implications and
how they would be validated before deployment.

Record enough context to interpret results: hardware, runtime, model version,
and measurement method.

Do not present local measurements as production guarantees.

## Confidence handling

If production behavior depends on confidence or uncertainty, use the evidence
from model evaluation to define safe handling.

Consider:

- low-confidence abstention or fallback
- escalation or human review where appropriate
- avoiding high-confidence actions when calibration is poor
- monitoring confidence distributions after deployment

Do not assume a confidence score is trustworthy unless it has been evaluated.

## Optimization

Consider only when justified by a constraint, for example:

- model/runtime export
- quantization or reduced precision
- smaller model variants
- batching when appropriate

Compare optimized and original models on the same evaluation data.

Report both quality and runtime impact. Do not accept a faster model without
checking for meaningful quality loss.

## Deployment considerations

For server-side inference, consider latency, throughput, worker memory, model
loading, scaling cost, and failure behavior.

For edge/mobile inference, consider runtime compatibility, model size, device
memory, CPU latency, export/quantization support, and quality loss.

Implementation is optional unless explicitly required.

## Verification

Before finishing:

- run inference on representative samples
- verify outputs after export/optimization
- confirm reported benchmarks were actually measured
- confirm quality and confidence behavior remain acceptable
- run relevant repository checks

Never fabricate benchmark, deployment, or optimization results.

## Reporting and handoff

Report concisely:

- target environment and constraints
- measured evidence
- optimizations tested
- quality/runtime tradeoffs
- confidence-handling approach when relevant
- recommended serving approach
- remaining risks or next validation step

Use specialized API, Docker, deployment, or observability skills only when
those concerns actually need implementation.
