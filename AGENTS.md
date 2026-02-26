# AGENTS.md

Operational guide for coding agents working in this repository.

## Scope

- Applies to the entire repository.
- There are currently no additional Cursor or Copilot instruction files in this repo.
- Checked and not found:
  - `.cursorrules`
  - `.cursor/rules/`
  - `.github/copilot-instructions.md`

## Project Overview

- Package: `runllm`
- Language: Python 3.10+
- Runtime type: CLI + library
- CLI entrypoint: `runllm = runllm.cli:main` (from `pyproject.toml`)
- Primary domains:
  - `.rllm` file parsing and validation
  - typed input/output contract enforcement
  - LiteLLM execution and retry/recovery
  - composition (`uses`) across `.rllm` apps
  - runtime stats persistence (SQLite)

## Environment and Install Commands

- Install package in editable mode:
  - `pip install -e .`
- Install dev dependencies:
  - `pip install -e .[dev]`
- Alternative global CLI install:
  - `pipx install runllm`
- Local editable via pipx:
  - `pipx install --editable .`

## Build / Lint / Test Commands

This repo does not currently define dedicated lint or formatter tools in `pyproject.toml`.

- Run all tests:
  - `python3 -m pytest -q`
- Run verbose test output:
  - `python3 -m pytest -vv`
- Run one test file:
  - `python3 -m pytest -q tests/test_parser.py`
- Run one test case:
  - `python3 -m pytest -q tests/test_executor.py::test_retry_then_success`
- Run tests by keyword expression:
  - `python3 -m pytest -q -k "composition or retry"`
- Run live Ollama integration tests:
  - `RUNLLM_OLLAMA_TESTS=1 python3 -m pytest -q tests/test_examples_ollama_live.py`

## CLI Smoke Test Commands

- Validate example:
  - `python3 -m runllm.cli validate examples/summary.rllm`
- Run example with inline input:
  - `python3 -m runllm.cli run examples/summary.rllm --input '{"text":"hello"}'`
- Inspect app contract:
  - `python3 -m runllm.cli inspect examples/summary.rllm`
- Show stats:
  - `python3 -m runllm.cli stats examples/summary.rllm`

## Repository Layout

- Source package: `runllm/`
- Tests: `tests/`
- Example apps: `examples/`
- Project docs: `docs/`

Key implementation files:

- `runllm/cli.py` command wiring and argument parsing
- `runllm/parser.py` `.rllm` parsing and metadata validation
- `runllm/executor.py` execution flow and retry logic
- `runllm/validation.py` JSON parsing and JSON Schema validation
- `runllm/errors.py` structured error payload helpers
- `runllm/stats.py` SQLite stats storage and aggregation

## Code Style Guidelines

Follow existing style in this codebase.

### Imports

- Use absolute imports from package root (for example `from runllm.errors import ...`).
- Group imports in this order when possible:
  1. stdlib
  2. third-party
  3. local package imports
- Keep imports explicit; avoid wildcard imports.

### Formatting

- Use 4-space indentation.
- Keep functions focused and small.
- Prefer readable, explicit branching.
- Maintain current quote and spacing conventions from surrounding file.
- Preserve ASCII unless file already requires non-ASCII.

### Types and Dataclasses

- Add type hints for public and internal functions.
- Use built-in generics (`dict[str, Any]`, `list[str]`, etc.).
- Keep dataclass fields typed and explicit.
- Prefer narrow return types where practical.

### Naming Conventions

- Modules/functions/variables: `snake_case`.
- Classes/dataclasses: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Test names: `test_<behavior>`.

### Error Handling

- Prefer structured errors via `make_error(...)` and `RunLLMError`.
- Include actionable `recovery_hint` whenever raising domain errors.
- Preserve current error code taxonomy (`RLLM_00x`) and docs references.
- Do not swallow exceptions silently.

### Schema and Validation Practices

- Validate input before model execution.
- Validate output schema after parsing model output.
- Keep retry behavior deterministic and consistent with current executor flow.
- If changing parsing behavior, update docs in the same change.

### CLI Behavior

- CLI outputs JSON payloads for both success and failure.
- Keep exit codes stable:
  - `0` success
  - `1` failure
- New CLI flags must be reflected in `docs/cli.md`.

### Stats and Persistence

- Keep SQLite schema backward compatible unless migration is intentional.
- If schema changes, update `SCHEMA_VERSION` and migration docs.

## Test Guidance for Agents

- Always run targeted tests for changed modules first.
- Then run full suite:
  - `python3 -m pytest -q`
- Also run Ollama live integration tests on every test pass:
  - `RUNLLM_OLLAMA_TESTS=1 python3 -m pytest -q tests/test_examples_ollama_live.py`
  - `RUNLLM_OLLAMA_TESTS=1 python3 -m pytest -q tests/test_onboarding_ollama_live.py`
- For non-deterministic LLM behavior, assert schema/structure, not exact wording.

## Documentation Sync Requirements

When behavior changes, update docs in same PR/commit.

Minimum docs to evaluate:

- `ROADMAP.md` (when release scope/milestones change)
- `README.md`
- `docs/rllm-spec.md`
- `docs/cli.md`
- `docs/errors.md`
- `docs/composition.md` (if `uses` behavior changed)

## Change Management Notes

- Keep changes scoped; avoid unrelated refactors.
- Do not introduce new dependencies unless necessary.
- Match existing implementation patterns before inventing new abstractions.
- Prefer incremental, test-backed edits.

## LLM Contribution Workflow (Short)

Use this branch strategy for all coding-agent changes.

### Branches

- `main`: always releasable; no direct agent commits unless explicitly requested.
- `release/<major>.<minor>`: staging/stabilization branch for next release.
- `feature/<name>`: new capability; branch from active `release/*` (or `main` if no release branch).
- `bugfix/<name>`: non-urgent bug fix for upcoming release; branch from active `release/*`.
- `hotfix/<name>`: urgent production fix; branch from `main`.

### PR Targets

- `feature/*` -> active `release/*`
- `bugfix/*` -> active `release/*`
- `hotfix/*` -> `main` first, then merge/cherry-pick into active `release/*`
- Release completion: `release/*` -> `main`

### Core Agent Rules

- One logical change per branch/PR.
- Keep commits atomic; use intent prefixes (`feat:`, `fix:`, `docs:`, `test:`).
- Update docs in same change when behavior changes.
- Add/update tests for changed behavior.
- Never force-push protected branches (`main`, `release/*`).
- Never amend pushed commits unless explicitly requested.
- Never bypass hooks unless explicitly requested.
- Never commit secrets (`.env`, API keys, credentials).
- Do not revert unrelated user changes; only modify relevant scope.

### Required Validation Before PR

Run at minimum:

- `python3 -m pytest -q`

If release gate requires live tests, also run:

- `RUNLLM_OLLAMA_TESTS=1 python3 -m pytest -q tests/test_examples_ollama_live.py`
- `RUNLLM_OLLAMA_TESTS=1 python3 -m pytest -q tests/test_onboarding_ollama_live.py`

### Release Steps (High-Level)

1. Merge `feature/*` and `bugfix/*` into `release/*`.
2. Stabilize (tests/docs/changelog).
3. Merge `release/*` into `main`.
4. Tag release on `main` (for example `v0.1.0`).
5. Publish release notes.
