# .rllm Spec v0.1

This document is the canonical file-format reference for `.rllm` apps.

Related docs:

- Authoring workflow: `authoring-guide.md`
- Schema patterns: `schema-cookbook.md`
- Recovery prompt design: `recovery-playbook.md`
- Composition details: `composition.md`
- CLI command usage: `cli.md`
- Error codes: `errors.md`

## File shape

`.rllm` files are plain text with YAML frontmatter and a prompt body.

```text
---
<yaml metadata>
---
<prompt body>
```

Optional sections in body:
- `<<<RECOVERY>>>` splits main prompt and retry recovery prompt.
- ` ```rllm-python pre ` and ` ```rllm-python post ` code blocks.

## Minimal valid template

```yaml
---
name: my_app
description: One sentence purpose.
version: 0.1.0
runllm_compat:
  min: 0.1.0
author: your_name
max_context_window: 8000
input_schema:
  type: object
  properties:
    text:
      type: string
  required: [text]
  additionalProperties: false
output_schema:
  type: object
  properties:
    result:
      type: string
  required: [result]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Return only valid JSON:
{"result":"..."}

Input:
{{input.text}}
```

## Required frontmatter keys

- `name` string
- `description` string
- `version` string
- `author` string
- `max_context_window` positive integer
- `input_schema` object (JSON Schema subset)
- `output_schema` object (JSON Schema subset)
- `llm` object (must include `model`)
- `llm_params` object (keys must be supported)

## Optional frontmatter keys

- `metadata` object (free-form)
- `recommended_models` string array
- `tags` string array
- `uses` array (composition)
- `recovery_prompt` string (alternative to `<<<RECOVERY>>>` block)
- `runllm_compat` object (runtime compatibility bounds)

`runllm_compat` shape:

```yaml
runllm_compat:
  min: 0.1.0
```

Rules:

- `min` is required when `runllm_compat` is present.
- `max_exclusive` is optional.
- Both values must be semantic versions in `X.Y.Z` format.
- Runtime enforces: `min <= installed_runllm_version < max_exclusive` (when max is provided).
- If `runllm_compat` is omitted, no runtime-version bound is enforced.
- Recommended default: set only `min`; add `max_exclusive` only when you need an explicit upper bound.

## Supported `llm_params` keys

Supported keys in this runtime:

- `temperature`
- `top_p`
- `max_tokens`
- `frequency_penalty`
- `presence_penalty`
- `stop`
- `n`
- `stream`
- `response_format`
- `seed`
- `timeout`
- `logit_bias`
- `user`
- `tools`
- `tool_choice`
- `parallel_tool_calls`
- `format`

If unsupported keys are present, parse fails with `RLLM_003`.

## Prompt templating

Template syntax:

- `{{input.<path>}}` from input payload
- `{{uses.<dep_name>.<path>}}` from dependency outputs

Behavior notes:

- Missing paths resolve to empty string.
- Dict/list values are rendered as JSON text.

## Composition (`uses`)

`uses` lets a parent app execute child apps first.

```yaml
uses:
  - name: summary_app
    path: ./summary.rllm
    with:
      text: "{{input.text}}"
```

Rules:

- Child paths resolve relative to parent file.
- Circular dependencies are rejected (`RLLM_008`).
- `with` must be an object when provided.
- `with` mapping values can be literals or templates.
- Template values are rendered strings; use literals for typed non-strings.

## Recovery behavior

Retries happen when output schema validation fails.

- With `<<<RECOVERY>>>` (or `recovery_prompt`), retries append your recovery instruction.
- Without custom recovery, runtime appends schema + default recovery instruction.

## Python blocks

Two optional block types:

- `pre`: runs before prompt rendering
- `post`: runs after output validation

Syntax:

````text
```rllm-python pre
result = {"normalized": "..."}
```
````

Contract:

- Runtime injects `context` dict.
- Block should set `result` as dict (or leave empty).
- In default mode, builtins are restricted and execution is time-limited.
- Untrusted mode also applies a best-effort memory cap (default `256 MB`, configurable via `--python-memory-limit-mb`; use `0` to disable).
- `--trusted-python` enables broader execution.

## JSON output parsing behavior

Runtime expects a JSON object.

- Best case: model returns exactly one JSON object.
- Robustness: if model includes extra text, runtime attempts to extract JSON object candidates and validate each.

## Context window guard

Before model call, runtime estimates total context tokens from prompt + input.
If estimate exceeds `max_context_window`, run fails with `RLLM_012`.
