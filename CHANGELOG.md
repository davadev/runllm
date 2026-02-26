# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

### Added

- Release engineering baseline:
  - GitHub Actions CI workflow for automated test runs.
  - Release process documentation and reusable release notes template.
- Python block runtime memory guard to complement timeout safety controls.

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

### Notes

- Live Ollama integration tests are environment-dependent and run when `RUNLLM_OLLAMA_TESTS=1`.
