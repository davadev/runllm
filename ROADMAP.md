# ROADMAP

This roadmap defines staged releases for `runllm` with a focus on atomic LLM steps, strict contracts, and composable workflows.

## Product Principles

- Keep each LLM call atomic and schema-bounded.
- Compose larger behavior via multiple `.rllm` programs.
- Prefer deterministic validation over prompt-only assumptions.
- Keep CLI outputs machine-usable (JSON-first).
- Make onboarding reusable, not one-off.

---

## Release 1: Core Runtime + Interactive Onboarding Builder (v0.1.x)

Status: first stable baseline.

### Objectives

- Ship current runtime as stable release.
- Add an interactive onboarding workflow that helps users create their first `.rllm` app.
- Keep onboarding itself composable from small `.rllm` units.
- Support users both with and without preconfigured API credentials.

### Included Platform Features

- `.rllm` parse / validate / inspect / run
- typed input/output schema enforcement
- retry + recovery prompts
- composition via `uses`
- runtime stats + `exectime`
- provider config autoload + credential checks
- LLM-oriented CLI help topics (`runllm help ...`)

### Interactive Onboarding Workflow

Release 1 must include one canonical stacked workflow that acts as onboarding.

#### User journey

1. Ask which provider/model user wants to use.
2. Check whether required credential is already configured.
3. If missing, guide user through secure key setup.
4. Run a "hello world" connectivity check.
5. Guide user through first app creation step-by-step:
   - app purpose
   - input schema
   - output schema
   - max context window
   - model and params
   - prompt and recovery prompt
6. Generate `.rllm` file.
7. Validate and test-run generated app.
8. Offer reusable scaffold for creating future apps.

### Atomic Subprogram Design (example structure)

- `examples/onboarding/provider_select.rllm`
- `examples/onboarding/credential_check.rllm`
- `examples/onboarding/hello_test.rllm`
- `examples/onboarding/app_goal_capture.rllm`
- `examples/onboarding/input_schema_builder.rllm`
- `examples/onboarding/output_schema_builder.rllm`
- `examples/onboarding/context_window_picker.rllm`
- `examples/onboarding/prompt_builder.rllm`
- `examples/onboarding/recovery_builder.rllm`
- `examples/onboarding/file_assembler.rllm`
- `examples/onboarding/validate_and_test.rllm`

A parent onboarding workflow composes these units with minimal orchestration.

### Two onboarding phases

#### Phase A: setup-first (no credential yet)
- Use simple guided steps to configure provider credential.
- Require explicit user confirmation before writing secret files.

#### Phase B: app-builder (credential available)
- Use composed `.rllm` steps to generate and validate first app.
- Offer save/reuse template path for future app generation.

### Release 1 Exit Criteria

- New user can install and create first valid app in one flow.
- Generated app passes `runllm validate` and a sample `runllm run`.
- Onboarding has both paths tested:
  - missing credentials
  - credentials already present
- Documentation includes copy-paste onboarding sequence.

---

## Release 2: MCP Integration + Program Discovery Tree (v0.2.x)

Status: planned.

### Objectives

- Expose user-created `.rllm` programs through MCP.
- Avoid flat, unbounded tool lists that consume context.
- Provide category/tree discovery that is agent-friendly.

### MCP Scope

- MCP server integration for runllm program registry.
- Operations:
  - list categories
  - list programs in category
  - inspect program contract/metadata
  - get invocation hints
- Discovery should default to compact tree output.

### LLM-assisted organization

Use LLM classification to group apps, for example by:

- domain (support, coding, extraction, compliance)
- task type (classification, summarization, planning, transformation)
- schema shape family
- complexity/latency profiles

Output must remain deterministic enough for agents to navigate reliably.

### Context-window safety requirements

- top-level MCP listing returns categories only
- detailed expansion is on demand
- pagination/filtering for large app libraries
- compact metadata summaries for each node

### Release 2 Exit Criteria

- Agent can discover relevant apps through category tree without context bloat.
- MCP discovery/inspect/invoke flow has integration tests.
- Non-MCP workflows remain backward compatible.
- Docs include setup, usage, and failure handling guidance.

---

## Cross-Release Quality Gates

For every release:

1. Full test suite passes.
2. CLI help and docs are synchronized.
3. Structured error behavior remains stable.
4. Examples are runnable and versioned with docs.
5. Release notes include migration guidance when behavior changes.

---

## Versioning Path

- `v0.1.x`: core runtime + interactive onboarding builder.
- `v0.2.x`: MCP integration + categorized tool discovery.
