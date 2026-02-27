# CLI Reference

Related docs:

- File format and frontmatter contract: `rllm-spec.md`
- Interactive first-run flow: `onboarding.md`
- Provider credentials and config autoload: `provider-credentials.md`, `configuration.md`
- Error payload reference: `errors.md`
- Composition patterns: `composition.md`, `multistep-apps.md`
- MCP usage and project scoping: `mcp.md`

## `runllm run`

Execute a `.rllm` app.

```bash
runllm [--no-config-autoload] run <file.rllm> [--input JSON] [--input-file path] [--model model] [--max-retries N] [--verbose] [--ollama-auto-pull] [--trusted-python] [--python-memory-limit-mb MB] [--debug-prompt-file path] [--debug-prompt-stdout] [--debug-prompt-wrap N]
```

Options:
- `--input` inline JSON object string.
- `--input-file` JSON/YAML file with top-level object.
- `--model` override frontmatter `llm.model` at execution time (the frontmatter `llm.model` field is still required for validation).
- `--max-retries` output-schema retry count, non-negative integer (default: `2`).
- `--verbose` print verbose mode (reserved for richer traces).
- `--ollama-auto-pull` allow `ollama pull` for missing models.
- `--trusted-python` run python blocks with broad builtins.
- `--python-memory-limit-mb` memory cap for untrusted python blocks (default: `256`; set `0` to disable).
- `--debug-prompt-file` append exact prompts sent to model to a human-readable debug file.
- `--debug-prompt-stdout` print exact prompts sent to model to stderr (so stdout remains pure JSON).
- `--debug-prompt-wrap` wrap width for debug prompt rendering (default: `100`).

Global options:
- `--no-config-autoload` disable automatic loading of `.env` and config files.

Example:

```bash
runllm run examples/summary.rllm --model ollama/llama3.1:8b --input '{"text":"hello world"}'
```

## `runllm validate`

Validate syntax and metadata.

```bash
runllm validate <file.rllm>
```

Returns normalized metadata fields and `ok: true` on success.
When `runllm_compat` is present, `validate` also enforces runtime-version bounds.

## `runllm inspect`

Show normalized metadata, schemas, and dependencies.

```bash
runllm inspect <file.rllm>
```

Use this to inspect schemas, `uses`, recommended models, and metadata.
`inspect` also enforces `runllm_compat` bounds during parse.

## `runllm stats`

Show observed runtime stats from local SQLite store.

```bash
runllm stats <file.rllm> [--model model]
```

Common fields:
- `total_runs`
- `success_count`
- `failure_count`
- `output_schema_compliance_pct`
- `avg_latency_ms`
- `avg_prompt_tokens`
- `avg_completion_tokens`
- `max_completion_tokens`
- `ms_per_1k_tokens`

## `runllm exectime`

Estimate runtime from observed average latency of app + dependencies.

```bash
runllm exectime <file.rllm> [--model model]
```

Returns estimated latency from observed averages of parent + direct dependencies.

## `runllm help`

Show detailed authoring help topics designed for both humans and coding agents.

Default output format is JSON for automation-friendly consumption.

```bash
runllm help <topic> [--format text|json]
```

Topics:
- `rllm`
- `schema`
- `recovery`
- `composition`
- `examples`
- `credentials`
- `config`

Examples:

```bash
runllm help rllm
runllm help rllm --format text
runllm help schema --format json
```

## `runllm onboard`

Interactive chat-style onboarding flow to configure credentials and generate a first app.

```bash
runllm [--no-config-autoload] onboard [--model model] [--resume] [--session-file path] [--scaffold-file path] [--no-save-scaffold]
```

Behavior:
- chat-style goal capture and iterative app draft defaults
- prompts for provider/model (unless `--model` is provided)
- checks required provider credential
- optionally writes missing key to selected `.env` path after explicit confirmation
- runs connectivity check
- uses onboarding `.rllm` micro-app steps to draft purpose/prompt/recovery
- includes one bounded refine pass (approve or revise one area)
- scaffolds a first `.rllm` file and validates it
- runs a sample execution using gathered sample input
- writes reusable scaffold profile JSON by default

Session options:
- `--resume` load defaults from prior session state
- `--session-file` custom state path (default: `.runllm/onboarding-session.json`)

Scaffold options:
- `--scaffold-file` custom scaffold output path (default: `.runllm/scaffold-profile.json`)
- `--no-save-scaffold` opt out of writing scaffold profile file

## `runllm mcp serve`

Start minimal MCP stdio server for one project scope.

```bash
runllm mcp serve --project <name>
```

To enable Python workflow entrypoint execution via `invoke_workflow` (trusted repositories only):

```bash
runllm mcp serve --project <name> --trusted-workflows
```

Behavior:
- serves MCP tools: `list_programs`, `invoke_program`, `list_workflows`, `invoke_workflow`, `help_topic`
- scope is fixed to one project per process
- programs are discovered from:
  - `userlib/<project>/**/*.rllm`
  - `rllmlib/**/*.rllm` (project name: `rllmlib`)
- `list_programs` returns compact contract hints (required params and returns with types)
- `list_programs` accepts optional `refresh` to rebuild the in-memory registry
- `list_workflows` returns project-scoped workflow entrypoints for one-call orchestration
- `invoke_workflow` runs one workflow with typed input/output validation
- `invoke_workflow` is disabled unless server starts with `--trusted-workflows`
- `help_topic` returns runllm authoring guidance for one topic (`rllm`, `schema`, `recovery`, `composition`, `examples`, `credentials`, `config`)

Examples:

```bash
runllm mcp serve --project runllm
runllm mcp serve --project rllmlib
```

## `runllm mcp install-opencode`

Install or update OpenCode MCP config for `runllm` and add an agent prompt file.

```bash
runllm mcp install-opencode [--project name] [--mcp-name name] [--runllm-bin path_or_cmd] [--agent-file filename] [--force] [--trusted-workflows]
```

Behavior:
- resolves OpenCode config at `$XDG_CONFIG_HOME/opencode` or `~/.config/opencode`
- upserts `opencode.json` `mcp.<mcp-name>` entry for `runllm mcp serve --project <project>`
- creates a builder agent file under `agent/<agent-file>` with guidance to use `help_topic`, `list_programs`, `list_workflows`, `invoke_program`, and `invoke_workflow`
- requires `--mcp-name` to match `[A-Za-z0-9_-]+`
- requires `--agent-file` to be a plain filename (no paths, no `.`/`..`)
- requires `--runllm-bin` to be a non-empty command/path
- preserves existing `mcp.<mcp-name>` values unless fields are missing
- use `--force` to overwrite existing `mcp.<mcp-name>` and agent file content

Example:

```bash
runllm mcp install-opencode --project runllm
```

To install OpenCode MCP command with workflow execution enabled:

```bash
runllm mcp install-opencode --project runllm --trusted-workflows
```

## Exit behavior

- Success returns exit code `0` and JSON output payload.
- Validation/runtime failure returns exit code `1` and structured error JSON (see `docs/errors.md`).
- Exception: `runllm mcp serve` is a long-running stdio server command; it does not emit one-shot JSON command payloads.

## Provider credentials

`runllm` uses LiteLLM providers. Configure credentials via environment variables (for example `OPENAI_API_KEY`).
See `docs/provider-credentials.md` and `docs/configuration.md`.
