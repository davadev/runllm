# CLI Reference

## `runllm run`

Execute a `.rllm` app.

```bash
runllm [--no-config-autoload] run <file.rllm> [--input JSON] [--input-file path] [--model model] [--max-retries N] [--verbose] [--ollama-auto-pull] [--trusted-python]
```

Options:
- `--input` inline JSON object string.
- `--input-file` JSON/YAML file with top-level object.
- `--model` override frontmatter `llm.model`.
- `--max-retries` output-schema retry count (default: `2`).
- `--verbose` print verbose mode (reserved for richer traces).
- `--ollama-auto-pull` allow `ollama pull` for missing models.
- `--trusted-python` run python blocks with broad builtins.

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

## Exit behavior

- Success returns exit code `0` and JSON output payload.
- Validation/runtime failure returns exit code `1` and structured error JSON (see `docs/errors.md`).

## Provider credentials

`runllm` uses LiteLLM providers. Configure credentials via environment variables (for example `OPENAI_API_KEY`).
See `docs/provider-credentials.md` and `docs/configuration.md`.
