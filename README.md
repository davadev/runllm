# runllm

`runllm` is a lightweight Python CLI/runtime for `.rllm` files: single-iteration LLM apps with typed input/output contracts, schema retries, composition, and execution stats.

## Install

```bash
pip install -e .
```

## Quickstart

Validate an app:

```bash
runllm validate examples/summary.rllm
```

Run an app:

```bash
runllm run examples/summary.rllm --input '{"text":"Large language models are useful."}'
```

Inspect metadata and schemas:

```bash
runllm inspect examples/summary.rllm
```

View stats and execution estimate:

```bash
runllm stats examples/summary.rllm
runllm exectime examples/compose_summary_keywords.rllm
```

## Files

- `.rllm` format spec: `docs/rllm-spec.md`
- CLI reference: `docs/cli.md`
- Error reference: `docs/errors.md`
- Composition guide: `docs/composition.md`
- Ollama guide: `docs/ollama.md`

## Notes

- Output contract defaults to JSON object for strict parsing reliability.
- Schemas use a JSON Schema subset for both input and output.
- Stats are stored in SQLite under `~/.config/runllm/stats.db`.
- Ollama auto-pull is opt-in (`--ollama-auto-pull`).
