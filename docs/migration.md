# Versioning and Migration

Related docs:

- Release planning and milestones: `../ROADMAP.md`
- Release execution workflow: `release-process.md`
- Runtime command behavior: `cli.md`
- Format compatibility source of truth: `rllm-spec.md`

Current `.rllm` spec version: `0.1`.

Compatibility rules:
- Runtime should remain backward compatible with `0.1.x` files.
- Any breaking file-format changes require `0.2`+ and migration notes.
- Apps can declare runtime bounds with optional `runllm_compat` metadata:
  - `min` (required when present)
  - `max_exclusive` (optional)
- Runtime enforces compatibility bounds during parse/validate/run.

Stats DB:
- `schema_version` is tracked in `meta` table.
- Future upgrades should include migration scripts before runtime writes.

## Documentation compatibility note

This repository keeps runtime behavior and docs aligned.

When runtime behavior changes (for example retry logic, parsing behavior, or supported params), update:

- `ROADMAP.md` (if planned scope/milestones change)
- `docs/rllm-spec.md`
- `docs/cli.md`
- `docs/errors.md`

in the same PR/commit to preserve agent-scaffold reliability.

## Recent compatibility notes

- `llm.model` is now enforced during parse/validate (`RLLM_002`) instead of only at runtime.
- Impact: apps that omitted `llm.model` and relied on `runllm run --model ...` now fail validation until `llm.model` is added to frontmatter.
- Runtime now appends an output contract to model prompts on every attempt (first attempt included): output schema JSON, deterministic example output JSON, and JSON-only instruction.
- Impact: improved first-pass schema compliance; context-window estimation now effectively includes this contract text.
- New CLI debug flags for prompt review:
  - `--debug-prompt-file PATH`
  - `--debug-prompt-stdout` (writes debug blocks to stderr to keep stdout JSON clean)
  - `--debug-prompt-wrap N`

## v0.1 onboarding updates

- `runllm onboard` now saves a reusable scaffold profile by default at `.runllm/scaffold-profile.json`.
- New onboarding flags:
  - `--scaffold-file PATH`
  - `--no-save-scaffold`
- Onboarding now captures extended model params:
  - `temperature` (must be `>= 0`)
  - optional `top_p` (must be in `(0, 1]`)
  - `format` defaults to `json` unless explicitly overridden
- Onboarding includes one bounded refinement pass before generating final app output.
- JSON payload now includes `scaffold_file` when scaffold persistence is enabled.
