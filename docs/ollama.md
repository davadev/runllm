# Ollama Integration

If app model is `ollama/<model>`, runllm can verify local model availability.

Default:
- Missing model returns `OllamaModelMissingError`.

Opt-in auto-download:

```bash
runllm run app.rllm --ollama-auto-pull
```

This performs:
- `ollama list` to verify model
- `ollama pull <model>` if missing and auto-pull enabled
