# Configuration

`runllm` supports automatic loading of provider settings and runtime defaults.

## Autoload behavior

By default, `runllm` autoloads configuration in this precedence order (highest first):

1. Process environment variables (already exported)
2. Project `.env` in current working directory
3. User `.env` at `~/.config/runllm/.env` (or `$XDG_CONFIG_HOME/runllm/.env`)
4. User config YAML at `~/.config/runllm/config.yaml`

Process environment values always win.

## Disable autoload

Disable for one command:

```bash
runllm --no-config-autoload run app.rllm --input '{"text":"hello"}'
```

Disable for session:

```bash
export RUNLLM_NO_CONFIG_AUTOLOAD=1
```

## `.env` files

Example `.env`:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=...
```

Use `.env.example` as template. Do not commit real secrets.

## `config.yaml` (non-secret defaults)

Path:

- `~/.config/runllm/config.yaml`

Example:

```yaml
runtime:
  default_model: ollama/llama3.1:8b
  default_max_retries: 2
  default_ollama_auto_pull: false

provider:
  ollama_api_base: http://localhost:11434
```

Notes:

- Keep API keys in env or `.env`, not in `config.yaml`.
- `default_model` applies when `--model` is not provided.
- `default_max_retries` applies when `--max-retries` is not provided.
