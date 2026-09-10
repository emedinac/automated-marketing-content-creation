---
name: bootstrap-python-microservice
description: >
  Bootstrap or structure a Python microservice. Use when creating,
  initializing, or scaffolding a Python service. Preserve an existing
  toolchain; otherwise use Poetry 2.X and the repository architecture defaults.
---

# Bootstrap Python Microservice

Use this skill together with the applicable `AGENTS.md`.

## Workflow

1. Read `AGENTS.md`, the task requirements, and existing repository files.
2. Decide whether the task is a service, an experiment, or both.
3. Identify required inbound/outbound boundaries and explicit runtime, latency, memory, or portability constraints.
4. Detect and preserve the existing Python toolchain. If none exists, use the defaults below.
5. Follow the project structure and architecture rules defined in `AGENTS.md`.
6. Scaffold only modules required by real behavior; do not create empty layers or placeholder files solely to match a template.
7. Add tests with the first implementation and concise run/test instructions.
8. Run the verification commands before completion.

Do not overwrite existing files or configuration unless the task requires changing them.

If the task does not require a running service, do not invent an API or deployment layer.

## New-project defaults

When no existing Python toolchain is present, use:

- Python 3.12+ unless constrained by the task
- Poetry 2.X with `pyproject.toml` and committed `poetry.lock`
- PEP 621 metadata in a `[project]` table
- Keep `[tool.poetry]` only for Poetry-specific settings such as `packages`
- Keep development groups under `[tool.poetry.group.<name>.dependencies]`
- Never put `name`, `version`, `description`, `authors`, `readme`, runtime dependencies, or scripts under `[tool.poetry]`
- `src/` package layout
- pytest + pytest-cov
- Ruff
- mypy

Use an import-safe package name (`my-service` -> `my_service`).

Use conventional module names appropriate to the behavior being implemented.
Do not create modules speculatively.

Configure pytest, Ruff, and mypy in `pyproject.toml` when no repository
configuration already exists.

Ensure the generated `pyproject.toml` uses this structure:

```toml
[project]
name = "package-name"
version = "0.1.0"
description = "..."
readme = "README.md"
requires-python = ">=3.12,<4.0"
dependencies = []

[project.scripts]
serve = "package.main:run"

[tool.poetry]
packages = [{ include = "package", from = "src" }]

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
```

Initialize dependencies through Poetry:

```bash
poetry init -n
poetry add --group dev pytest pytest-cov ruff mypy
poetry install
```

Add runtime dependencies only when the task requires them. Do not add FastAPI,
SQLAlchemy, Kafka clients, Redis, Docker tooling, cloud SDKs, or ML frameworks
by default.

Do not use unmanaged `pip install` to modify project dependencies.

## Data / ML tasks

Use the data/ML layout defined in `AGENTS.md` when applicable. Additionally:

- inspect provided schemas/data dictionaries before relying on columns, labels, category values, or missing-value behavior
- treat provided raw datasets as read-only unless explicitly asked otherwise
- keep reusable preprocessing, validation, feature, model, and evaluation logic under `src/`

Do not add serving infrastructure merely because a later deployment discussion
may be required.

## Tests and README

At minimum, add:

- one meaningful unit test for core behavior
- one important edge/failure test when applicable
- integration tests only for boundaries that actually exist

Keep `README.md` concise: installation, run command, test command, and material assumptions.

## Verification

If step 4 found an existing toolchain, run its equivalent checks instead of the commands below.

For a Poetry-based project, run the applicable checks:

```bash
poetry check --strict
poetry install
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src
poetry run pytest
```

If the project is packaged, also run:

```bash
poetry build
```

Never report a check as passing unless it was actually executed.

## Handoff

Briefly report what was created, dependencies added and why, checks executed,
and intentionally deferred work.

Use specialized skills for API frameworks, Docker, persistence, messaging,
observability, deployment, and ML experimentation when those concerns are
actually required.
