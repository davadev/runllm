# Onboarding Guide

This document provides copy-paste onboarding flows for Release 1.

Canonical stacked onboarding composition example:
- `examples/onboarding/onboarding_workflow.rllm`

## Flow 1: Missing credential path

Use this when provider credentials are not set yet.

```bash
unset OPENAI_API_KEY
runllm onboard --model openai/gpt-4o-mini
```

Expected interactive path:
- Prompts for missing key setup
- Requires explicit confirmation before writing `.env`
- Runs connectivity check
- Captures app purpose, schemas, params, prompt/recovery draft
- Shows one refine pass: `approve|purpose|input|output|params|prompt`
- Returns JSON payload with:
  - `generated_file`
  - `session_file`
  - `scaffold_file` (unless `--no-save-scaffold`)

Then verify generated app:

```bash
runllm inspect <generated_file_from_payload>
runllm validate <generated_file_from_payload>
runllm run <generated_file_from_payload> --input '{"text":"hello"}'
runllm stats <generated_file_from_payload>
```

Expected results:
- `inspect` prints contract and llm params
- `validate` returns `{ "ok": true, ... }`
- `run` returns JSON matching output schema
- `stats` includes total runs and compliance metrics

## Flow 2: Credential already configured path

Use this when credentials are already in environment.

```bash
export OPENAI_API_KEY="sk-..."
runllm onboard --model openai/gpt-4o-mini
```

Expected interactive path:
- Skips missing-credential setup prompts
- Runs connectivity check
- Captures app fields and params (`temperature`, optional `top_p`, `format`)
- Runs one bounded refine pass
- Returns JSON payload with generated app + scaffold profile paths

Then verify generated app:

```bash
runllm inspect <generated_file_from_payload>
runllm validate <generated_file_from_payload>
runllm run <generated_file_from_payload> --input '{"text":"hello"}'
runllm stats <generated_file_from_payload>
```

## Optional scaffold flags

Custom scaffold output path:

```bash
runllm onboard --model openai/gpt-4o-mini --scaffold-file .runllm/my-profile.json
```

Disable scaffold write:

```bash
runllm onboard --model openai/gpt-4o-mini --no-save-scaffold
```
