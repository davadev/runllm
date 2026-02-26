# runllm MVP Plan

## 1) Goal

Build `runllm`, a lightweight Python library + CLI that executes `.rllm` files as single-iteration LLM apps with strict typed I/O validation, retry-based schema recovery, and execution stats.

Primary UX target:
- `runllm run app.rllm --input-file in.yaml`
- Similar mental model to `python app.py`
- Simple enough for non-coders

## 2) Core MVP Outcomes

By MVP completion, the project must support:

- Parse and validate `.rllm` file syntax
- Validate declared metadata and LLM parameters (against LiteLLM-accepted params)
- Validate input variables against declared schema before execution
- Execute one-shot LLM call via LiteLLM
- Validate output schema and retry with recovery prompt on mismatch
- Return helpful, machine-readable, and human-readable errors
- Track per-app and per-model execution stats
- Provide basic app composition (`uses` of other `.rllm` programs)
- Enforce context limit declared by app (`max_context_window`)
- Include one working example app (`summary.rllm`)
- Include optional Ollama assist mode for missing recommended local model

## 3) Scope and Non-Goals

In scope:
- CLI runner/interpreter
- `.rllm` file format v0.1
- Typed I/O with robust validation
- Retry/recovery loop
- Stats capture + estimation command
- Minimal composition primitives
- Python inline blocks (safe, constrained MVP version)

Out of scope (post-MVP):
- GUI
- Multi-agent orchestration engine
- Distributed execution
- Advanced sandbox hardening beyond practical MVP constraints
- Full plugin ecosystem

## 4) Proposed `.rllm` Format v0.1

Design principle:
- Human-readable, low-token, easy to author
- Strictly parseable
- Extensible metadata

Decision for MVP:
- Use YAML frontmatter + prompt body
- Use JSON output format for model responses by default for strict parsing reliability
- Allow optional `output_format: yaml` later (post-MVP)

File shape:
- YAML frontmatter block with required and optional fields
- Prompt template body
- Optional recovery prompt template
- Optional python blocks

Required metadata:
- `name`
- `description`
- `version`
- `author`
- `max_context_window`
- `input_schema`
- `output_schema`
- `llm` (model + provider info)
- `llm_params` (validated against LiteLLM accepted params)

Flexible metadata:
- `metadata` free-form map for custom fields
- `recommended_models` list
- `tags` optional

Composition metadata:
- `uses` list of other `.rllm` files and exposed contracts

Python blocks:
- Optional named blocks for pre/post transforms
- Explicit declaration of input/output vars used by block
- MVP safety mode: restricted globals + deterministic timeout

## 5) Runtime Architecture

Modules:
- `parser`: parse `.rllm` and validate schema structure
- `contracts`: input/output typing and context rules
- `executor`: LiteLLM call orchestration
- `recovery`: retry loop with recovery prompt injection
- `stats`: local persistence and aggregation
- `compose`: resolve and execute dependent `.rllm` units
- `ollama`: optional model presence checks + pull flow
- `errors`: standardized error classes/codes/messages
- `cli`: command interface

Execution lifecycle:
1. Load `.rllm`
2. Validate file schema + metadata + LLM params
3. Resolve dependencies (`uses`)
4. Validate input schema
5. Estimate input token/context usage
6. Enforce `max_context_window`
7. Execute optional pre-python block
8. Render prompt
9. Call LiteLLM
10. Parse model output
11. Validate output schema
12. Retry with recovery prompt if invalid
13. Execute optional post-python block
14. Emit output
15. Persist metrics

## 6) CLI Contract (MVP)

Commands:
- `runllm run <file.rllm> --input <json|yaml|string> [--model override] [--max-retries N]`
- `runllm validate <file.rllm>`
- `runllm inspect <file.rllm>`
- `runllm stats <file.rllm> [--model X]`
- `runllm exectime <file.rllm> [--model X] [--input <...>]`

Behavior:
- Default output in JSON
- `--verbose` for detailed trace
- Non-zero exit codes on failures with typed error payload

## 7) Error Design Standard

All errors must be:
- Explicit
- Recoverable when possible
- LLM-readable
- Structured

Error payload shape:
- `error_code`
- `error_type`
- `message`
- `details`
- `expected_schema`
- `received_payload`
- `recovery_hint`
- `doc_ref`

Key error classes:
- ParseError
- MetadataValidationError
- LLMParamValidationError
- InputSchemaError
- OutputSchemaError
- ContextWindowExceededError
- RetryExhaustedError
- DependencyResolutionError
- PythonBlockExecutionError
- OllamaModelMissingError

## 8) Stats and Observability (MVP)

Store local app stats (per app and model):
- total runs
- success count
- failure count
- output schema compliance %
- input schema compliance %
- average latency
- average prompt tokens
- average completion tokens
- max completion tokens
- estimated ms per 1k tokens

Use stats for:
- `runllm exectime` prediction for single app
- composition-level estimate by summing dependency estimates

Persistence:
- SQLite in user config dir
- include schema version for forward migration

## 9) Composition Model (MVP)

Goal:
- Compose `.rllm` apps like functions

MVP composition rules:
- A parent app can call child apps declared in `uses`
- Child app contracts must be imported and type-checked
- Parent mapping declares how parent vars feed child inputs
- Parent can consume child outputs as typed variables
- Detect circular dependencies

## 10) Ollama Integration (MVP)

Support:
- If app has `recommended_models` containing an Ollama model and user enables auto-pull:
  - Check local availability
  - If missing, execute `ollama pull <model>`

Default behavior:
- no implicit download unless enabled by flag/config

CLI option:
- `--ollama-auto-pull` to allow automatic pull

## 11) Testing Strategy

Unit tests:
- parser and schema validation
- LLM params allowlist/validation
- input/output typing checks
- recovery retry logic
- context window enforcement
- stats aggregator calculations
- dependency resolution

Integration tests:
- execute sample `.rllm` end-to-end with mocked LiteLLM
- retry success after malformed first response
- composition app invoking two child apps
- CLI command contract and exit codes

Golden tests:
- snapshot expected error payloads
- snapshot `.rllm` parse tree for reference files

## 12) Security and Safety (MVP)

- Python blocks run in restricted execution context
- Timeout and memory guard for Python block execution
- Disable filesystem/network access by default for blocks (if full isolation is not feasible, clearly document this limit)
- Never execute shell from `.rllm` in MVP
- Log redaction for secrets in error traces

## 13) Milestones and Task Breakdown

Milestone 1: Repo bootstrap
- Python package structure
- CLI skeleton
- dependency setup (`litellm`, schema validation libs, testing stack)

Milestone 2: `.rllm` parser and metadata validator
- YAML frontmatter parser
- required fields validator
- custom metadata passthrough
- strict diagnostics

Milestone 3: Contracts and runtime validation
- input/output schema engine
- context window estimation and guard
- typed variable coercion policy

Milestone 4: LiteLLM execution engine
- call adapter
- llm params validation
- model override behavior
- deterministic response extraction

Milestone 5: Recovery loop
- retry policy
- recovery prompt templating
- retry-exhausted failure handling

Milestone 6: Stats engine
- storage layer
- update on success/failure
- `stats` and `exectime` CLI outputs

Milestone 7: Composition
- `uses` resolution
- contract import and variable mapping
- cycle detection

Milestone 8: Ollama support
- model existence check
- optional pull flow
- CLI/config flag behavior

Milestone 9: Examples and docs
- `summary.rllm`
- `extract_keywords.rllm`
- `compose_summary_keywords.rllm`
- quickstart and troubleshooting docs

Milestone 10: Hardening and release prep
- full test run
- lint/type checks
- packaging and versioning
- changelog and release notes

## 14) Definition of Done (MVP)

MVP is complete when:
- All core commands work end-to-end
- Example `.rllm` files execute successfully
- Retry loop can recover malformed output in test scenario
- Error responses are structured and informative
- Stats accumulate and `exectime` returns reasonable estimate
- Composition app can call two child apps and return merged typed output
- Documentation enables first-time user success in <10 minutes

## 15) Documentation Deliverables

Required docs:
- `README.md` quickstart
- `.rllm` spec v0.1 reference
- CLI reference
- error code reference
- composition guide
- Ollama integration guide
- migration/versioning notes for future spec updates

## 16) Risks and Mitigations

Risk:
- LLMs not consistently honoring schema
Mitigation:
- strict parser + retries + strong schema instructions + examples

Risk:
- context estimation mismatch across models
Mitigation:
- conservative estimator and clear failure diagnostics

Risk:
- unsafe Python block behavior
Mitigation:
- restricted runtime + disabled capabilities + explicit warnings

Risk:
- complexity creep in MVP
Mitigation:
- freeze v0.1 scope and defer advanced features

## 17) Final Product Decisions for MVP

1. Output standard default
- **Decision:** JSON is the default output contract.
- **Reason:** Highest parse reliability and strict schema validation support.

2. Input/output type system
- **Decision:** Use a JSON Schema subset (draft-compatible) for `input_schema` and `output_schema`.
- **Reason:** Familiar standard, strong validator ecosystem, easy machine-readable errors.

3. Stats backend
- **Decision:** SQLite as default local stats store.
- **Reason:** Durable, queryable, safe for repeated CLI writes, migration-friendly.

4. Python block safety level
- **Decision:** Restricted execution mode by default with explicit limitations; optional trusted mode later.
- **Reason:** Better default safety while preserving extensibility.

5. Auto-retry default
- **Decision:** Enabled by default with `max_retries = 2`.
- **Reason:** Balances resilience and cost while improving schema compliance out of the box.

6. Ollama model downloads
- **Decision:** Disabled by default, enabled only via `--ollama-auto-pull` or config opt-in.
- **Reason:** Prevents surprise downloads and resource usage.
