# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

### Added

- Minimal MCP server command: `runllm mcp serve --project <name>`.
- Project-scoped MCP tool surface with two tools only: `list_programs` and `invoke_program`.
- MCP program registry over `userlib/<project>/**/*.rllm` and `rllmlib/**/*.rllm`.
- Flat discovery cards that include app description, required input parameters with type hints, output fields with type hints, and invocation templates.
- Registry and pagination tests for project inference and contract-summary generation.
- MCP protocol-level error signaling (`isError`) with structured `runllm` error payloads for validation/runtime failures.
- MCP invoke behavior aligned with runtime config defaults by delegating `RunOptions` construction to core runtime.
- Recursive invocation template placeholders for required nested object fields and constrained arrays.
- Array placeholder cap for large `minItems` schemas to keep discovery payloads compact.
- MCP registry is built once per server session to reduce repeated filesystem/parse overhead.
- Expanded MCP regression coverage in `tests/test_mcp_server.py` for validation, scoping, error paths, and autoload behavior.

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
