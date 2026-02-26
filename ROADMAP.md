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

### Release 1 MVP Parity Additions

To preserve parity with MVP implementation scope, Release 1 also includes:

- strict `llm_params` allowlist validation against supported LiteLLM params
- structured JSON error payloads (`error_code`, `details`, `recovery_hint`, `doc_ref`)
- context window estimation and enforcement against `max_context_window`
- optional `rllm-python` pre/post blocks with restricted default mode and trusted override
- Ollama missing-model handling with explicit opt-in auto-pull behavior

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
- Core runtime integration tests cover retries, composition, contracts, and structured failures.
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

## Release 3: Public Packaging + Rename to ModuLLM (v0.3.x)

Status: planned.

### Objectives

- Make the project installable through standard Python tooling for broad adoption.
- Rename project identity from `runllm` to `ModuLLM` to avoid naming conflicts in public ecosystems.
- Preserve continuity for existing users with a documented migration path.

### Distribution and Packaging Scope

- Publish distributable artifacts (`sdist` + `wheel`) for public installation.
- Support installation paths:
  - `pip install modullm`
  - `pipx install modullm`
  - editable install for contributors
- Verify CLI entrypoint behavior after installation in clean environments.
- Keep library + CLI behavior aligned across install methods.

### Rename and Migration Scope

- Update project/package/CLI branding to `ModuLLM`.
- Provide command migration guidance (`runllm` -> `modullm`).
- Provide package migration guidance for scripts, CI, and docs.
- Prefer a transition window with compatibility notices before full cutover.

### Release 3 Exit Criteria

- Users can install and run the tool via Python package tooling without local checkout.
- Public naming consistently uses `ModuLLM`.
- Migration guidance is published and validated with smoke tests.
- Core command behavior remains stable (`validate`, `inspect`, `run`, `stats`, `help`).

---

## Release 4: Security Hardening + AuthZ and Prompt-Containment (v0.4.x)

Status: planned.

### Objectives

- Establish authenticated user execution controls (not only provider API credentials).
- Enforce policy-based authorization for which users can run which `.rllm` programs.
- Prevent unauthorized cross-system data transfer in stacked workflows and MCP contexts.
- Reduce prompt-injection blast radius with capability and data-flow constraints.

### Identity, Authorization, and Capability Model

- Introduce authenticated runtime principal context (user/session/tenant/role).
- Add app-level authorization policies with default-deny behavior.
- Mint per-run least-privilege capabilities and delegate only explicit subsets to `uses` children.
- Block privilege escalation and unauthorized transitive delegation.

### Data Domain and Flow Controls

- Classify apps/tools/outputs by domain (for example: support, finance, hr, security).
- Enforce explicit flow policy matrix between domains.
- Deny cross-domain transfer by default unless explicitly allowed by policy.
- Add safeguards for "user may access both systems, but transfer between them is not permitted."

### MCP and Prompt-Injection Guardrails

- Add MCP policy gateway for discovery/invoke filtering by principal capabilities.
- Treat model output and tool instructions as untrusted input.
- Require policy checks before every tool invocation and before sensitive output egress.
- Add output egress guardrails (redaction/blocking) when policy forbids transfer.
- Add high-risk action gating for export/exfiltration-like operations.

### Auditability and Operations

- Produce structured allow/deny decision logs with policy reasons.
- Record domain-flow events for security review and compliance.
- Add incident-response and disclosure workflow to documentation.

### Release 4 Exit Criteria

- Unauthorized program execution is denied with structured policy errors.
- Cross-domain transfer is blocked by default and only allowed by explicit policy.
- `uses` chains cannot escalate privileges or bypass domain boundaries.
- Red-team prompt-injection tests validate containment and no unauthorized exfiltration.
- Security checks and policy tests are integrated into CI release gates.

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
- `v0.3.x`: packaging for Python tooling + rename to `ModuLLM`.
- `v0.4.x`: security hardening + authorization and prompt-containment controls.
