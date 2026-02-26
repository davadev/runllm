# Provider Credentials

`runllm` delegates model calls to LiteLLM, so provider credentials are expected via environment variables.

`runllm` now autoloads `.env` and config files by default. See `docs/configuration.md` for precedence and disable options.

## OpenAI setup

If your app uses an OpenAI model (for example `openai/gpt-4o-mini`), set:

```bash
export OPENAI_API_KEY="sk-..."
```

Then run:

```bash
runllm run examples/summary.rllm --model openai/gpt-4o-mini --input '{"text":"hello"}'
```

## Local `.env` workflow

For local development:

1. Copy `.env.example` to `.env`
2. Fill your keys
3. Load environment variables in your shell before running `runllm`

macOS/Linux example:

```bash
set -a
source .env
set +a
```

Windows PowerShell example:

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^[A-Za-z_][A-Za-z0-9_]*=') {
    $name, $value = $_ -split '=', 2
    [Environment]::SetEnvironmentVariable($name, $value, 'Process')
  }
}
```

## Ollama setup

For `ollama/<model>` targets, API keys are usually not required.

- Ensure Ollama is installed and running.
- Optional: set `OLLAMA_API_BASE` when using non-default host/port.

## Security rules

- Never commit `.env` or real keys.
- Keep secrets in environment variables, not inside `.rllm` files.
- If a secret was committed, rotate it immediately and remove it from git history.

## Missing credential errors

If you select a provider model and the required key is missing, runtime raises:

- `RLLM_014` `MissingProviderCredentialError`

The error payload includes missing env var name and checked config sources.
