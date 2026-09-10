# AGENTS.md

Repository-wide instructions for AI coding agents.

Keep this file small, stable, and language-agnostic. Detailed workflows belong
in `.agents/skills/`.

## Instruction precedence

Within this repository, follow:

1. explicit task requirements
2. the nearest applicable nested `AGENTS.md`
3. the applicable `SKILL.md`
4. the generic defaults in this file

If instructions conflict, prefer the more specific applicable instruction.

The `Never` list below is absolute and is not subject to this ordering, no task requirement, AGENTS.md, or SKILL.md can override it.

## Principles

- Prefer correctness, simplicity, maintainability, and testability.
- Make the smallest change that fully satisfies the task.
- Inspect `README.md`, task briefs, specifications, schemas, and data documentation when present, the project manifest/lockfile, relevant code, tests, and
  applicable skills before editing.
- Preserve existing conventions unless the task requires changing them.
- Do not add abstractions, dependencies, or infrastructure without a concrete reason.
- Never fabricate tests, metrics, benchmarks, or observations.
- Do not perform unrelated refactors.

## Architecture

For new non-trivial services prefer hexagonal architecture:
("Non-trivial" = more than one adapter/integration, or expected to persist
beyond a single task.)

```text
src/<service>/
├── domain/
├── application/
└── adapters/

tests/
├── unit/
└── integration/
```

Dependency direction:

```text
adapters -> application -> domain
```

- `domain`: business rules; independent of frameworks and infrastructure
- `application`: use cases and ports
- `adapters`: HTTP, persistence, messaging, external APIs, and infrastructure integrations

Keep business logic out of transport and infrastructure code.
Keep infrastructure dependencies out of the domain.

Do not force hexagonal layers onto trivial scripts or very small services.

For data/ML projects, add only when needed:

```text
analysis/       # exploratory analysis; not production logic
pipelines/      # reproducible data/training/evaluation orchestration
```

Reusable and testable logic should remain under `src/`, not only in notebooks
or pipeline definitions.

## Project conventions

Use the repository's existing:

- language/runtime version
- package/dependency manager
- project manifest and lockfile
- formatter/linter
- type checker
- test framework
- build system

Do not introduce a second toolchain without a concrete reason.

## Skills

Reusable workflows live in:

```text
.agents/skills/<skill-name>/SKILL.md
```

Read only skills relevant to the current task.

When creating a new microservice, first look for:

```text
.agents/skills/bootstrap-<language>-microservice/SKILL.md
```

and use it when present.

For other specialized tasks, inspect `.agents/skills/` and load the matching
skill, for example deployment, Docker, ML experiments, persistence, messaging,
or observability.

`AGENTS.md` defines stable repository rules.
Skills define language-, framework-, infrastructure-, and workflow-specific details.

## Verification

Before finishing:

- run the repository's applicable lint/format checks
- run type checking when configured
- run relevant tests
- run build/package checks when applicable
- run additional checks required by the active skill
- remove dead code, unused imports, and unused dependencies introduced during the task
- remove scaffolding, placeholder files, or speculative modules not required by real behavior
- confirm `git status` shows no stray/untracked files before reporting completion

The `Never` list below is absolute and is not subject to this ordering.

## Never

- commit secrets
- fabricate tests, metrics, benchmarks, or observations
- disable tests or validation to hide failures
- silently swallow failures
- claim a check passed unless it was actually executed
- claim completion with known failures without reporting them
