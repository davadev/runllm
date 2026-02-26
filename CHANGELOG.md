# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

- No changes yet.

## [0.1.0] - 2026-02-26

### Added

- Core `.rllm` runtime with parse/validate/inspect/run command flow.
- Strict input/output schema validation and structured JSON errors.
- Retry and recovery prompt support for schema-mismatch handling.
- Composition support via `uses` dependency execution.
- Runtime stats persistence and execution-time estimation.
- Provider credential autoload and missing-credential checks.
- Interactive onboarding flow that scaffolds and validates a first app.
- LLM-focused CLI help topics and onboarding docs.
- Strict `llm_params` allowlist validation against supported LiteLLM parameters.
- Optional `rllm-python` pre/post blocks with restricted mode and trusted override.
- Context window estimation and enforcement against `max_context_window`.
- Ollama missing-model handling with explicit opt-in auto-pull behavior.
- Runtime compatibility metadata for apps via optional `runllm_compat` (`min` required, optional `max_exclusive`).
- Runtime compatibility enforcement with structured `RLLM_015` errors.
- PEP 440-aware runtime version parsing for compatibility checks (supports prerelease/post/dev versions).
- Example and onboarding-generated apps now include `runllm_compat.min` defaults.
- Release engineering baseline:
  - GitHub Actions CI workflow for automated test runs.
  - Release process documentation and reusable release notes template.
- Python block runtime memory guard to complement timeout safety controls.

### Notes

- Live Ollama integration tests are environment-dependent and run when `RUNLLM_OLLAMA_TESTS=1`.
