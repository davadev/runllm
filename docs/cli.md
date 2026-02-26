# CLI Reference

## `runllm run`

Execute a `.rllm` app.

```bash
runllm run <file.rllm> [--input JSON] [--input-file path] [--model model] [--max-retries N] [--ollama-auto-pull] [--trusted-python]
```

## `runllm validate`

Validate syntax and metadata.

```bash
runllm validate <file.rllm>
```

## `runllm inspect`

Show normalized metadata, schemas, and dependencies.

```bash
runllm inspect <file.rllm>
```

## `runllm stats`

Show observed runtime stats from local SQLite store.

```bash
runllm stats <file.rllm> [--model model]
```

## `runllm exectime`

Estimate runtime from observed average latency of app + dependencies.

```bash
runllm exectime <file.rllm> [--model model]
```
