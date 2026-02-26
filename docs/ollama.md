# Ollama Integration

If app model is `ollama/<model>`, runllm can verify local model availability.

Related docs:

- Command flags and runtime usage: `cli.md`
- Provider setup and env variables: `provider-credentials.md`, `configuration.md`
- Recommended model metadata fields: `rllm-spec.md`
- Missing-model error details (`RLLM_010`): `errors.md`

Examples:
- `ollama/llama3.1:8b`
- `ollama/qwen2.5-coder:7b`

Default:
- Missing model returns `OllamaModelMissingError`.

Opt-in auto-download:

```bash
runllm run app.rllm --ollama-auto-pull
```

This performs:
- `ollama list` to verify model
- `ollama pull <model>` if missing and auto-pull enabled

## Recommended model strategy

- Put preferred local models in `recommended_models` for each app.
- Keep `llm.model` as the default for that app's task profile.
- Override per run when needed:

```bash
runllm run app.rllm --model ollama/llama3.1:8b
```

## Local testing pattern

Use live tests for schema compliance, not exact text matching.

```bash
RUNLLM_OLLAMA_TESTS=1 python3 -m pytest -q tests/test_examples_ollama_live.py
```
