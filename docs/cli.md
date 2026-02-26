# CLI Reference

Related docs:

- File format and frontmatter contract: `rllm-spec.md`
- Interactive first-run flow: `onboarding.md`
- Provider credentials and config autoload: `provider-credentials.md`, `configuration.md`
- Error payload reference: `errors.md`
- Composition patterns: `composition.md`, `multistep-apps.md`

## `runllm run`

Execute a `.rllm` app.

```bash
runllm [--no-config-autoload] run <file.rllm> [--input JSON] [--input-file path] [--model model] [--max-retries N] [--verbose] [--ollama-auto-pull] [--trusted-python] [--python-memory-limit-mb MB]
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

## `runllm inspect`

Show normalized metadata, schemas, and dependencies.

```bash
runllm inspect <file.rllm>
```

Use this to inspect schemas, `uses`, recommended models, and metadata.

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

## Exit behavior

- Success returns exit code `0` and JSON output payload.
- Validation/runtime failure returns exit code `1` and structured error JSON (see `docs/errors.md`).

## Provider credentials

`runllm` uses LiteLLM providers. Configure credentials via environment variables (for example `OPENAI_API_KEY`).
See `docs/provider-credentials.md` and `docs/configuration.md`.
