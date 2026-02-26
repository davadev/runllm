# Multi-Step Apps Guide

Build multi-step `.rllm` workflows by composing child apps with `uses` and adding deterministic transforms with optional `rllm-python` blocks.

Related docs:

- Base composition contract: `composition.md`
- Canonical `.rllm` syntax and optional python blocks: `rllm-spec.md`
- Prompt/recovery writing guidance: `authoring-guide.md`, `recovery-playbook.md`
- Runtime command workflow: `cli.md`
- Failure diagnostics: `errors.md`

This guide is written for both:

- Humans authoring apps manually.
- Coding agents scaffolding apps automatically.

## 1) When to use multi-step apps

Use a multi-step app when one prompt would otherwise do too many jobs.

Good fit:

- Extract + classify + summarize as separate steps.
- Policy checks before final answer generation.
- Deterministic post-processing (for example score recompute, field normalization).

Keep one-step apps for narrow tasks with stable schema compliance.

## 2) Architecture pattern

Recommended pattern:

1. Child apps do one atomic task each.
2. Parent app orchestrates children with `uses`.
3. Parent prompt consumes `{{uses.<name>...}}` outputs.
4. Optional `rllm-python pre` block normalizes prompt context.
5. Optional `rllm-python post` block performs deterministic output adjustments.

## 3) Contract-first workflow

Design contracts before prompts:

1. Parent `input_schema`
2. Child `input_schema` + `output_schema`
3. Parent `output_schema`
4. `uses.with` mapping
5. Prompt/recovery text

Rules to remember:

- `llm.model` is required in each app.
- `uses.with` must be an object when provided.
- Template mappings render strings.
- YAML literals preserve type (number, bool, list, object).

## 4) Composition and typing rules

`uses` is function-like:

- `name`: child handle used under `{{uses.<name>...}}`
- `path`: child app path relative to parent file
- `with`: mapping from child input keys to template/literal values

Example typing behavior:

````yaml
uses:
  - name: scorer
    path: ./scorer.rllm
    with:
      text: "{{input.text}}"     # string after render
      threshold: 0.8              # number
      tags: [fast, strict]        # list
````

## 5) Python blocks in pipelines

Use python blocks for deterministic logic only.

- `pre` runs before prompt render and can add context fields.
- `post` runs after model output validates and can return patch fields.

Best practices:

- Keep code small, pure, and deterministic.
- Always set `result` to an object (or leave as `{}`).
- Do not depend on network/filesystem side effects.
- Keep `post` patches schema-safe: preserve output types/keys required by `output_schema`.

Important runtime note:

- Current runtime does not run a second `output_schema` validation after `python_post` merges patch fields.
- If `python_post` changes types or adds unexpected keys, schema-invalid payloads can escape without `RLLM_005`.

Failure mode:

- Python block exceptions return `RLLM_009` and are not schema-retried.

## 6) Worked example (3 apps)

### Child A: `summary.rllm`

````yaml
---
name: summary
description: Summarize text into one sentence.
version: 0.1.0
author: team
max_context_window: 6000
input_schema:
  type: object
  properties:
    text: { type: string }
  required: [text]
  additionalProperties: false
output_schema:
  type: object
  properties:
    summary: { type: string }
  required: [summary]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Return ONLY JSON object with key summary.
Input: {{input.text}}
````

### Child B: `keyword_extract.rllm`

```yaml
---
name: keyword_extract
description: Extract 3-6 short keywords.
version: 0.1.0
author: team
max_context_window: 6000
input_schema:
  type: object
  properties:
    text: { type: string }
  required: [text]
  additionalProperties: false
output_schema:
  type: object
  properties:
    keywords:
      type: array
      items: { type: string }
      minItems: 3
      maxItems: 6
  required: [keywords]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Return ONLY JSON object with key keywords.
Input: {{input.text}}
```

### Parent: `briefing_pipeline.rllm`

````yaml
---
name: briefing_pipeline
description: Compose summary + keywords into one briefing payload.
version: 0.1.0
author: team
max_context_window: 12000
input_schema:
  type: object
  properties:
    text: { type: string }
    max_keywords: { type: integer, minimum: 1, maximum: 10 }
  required: [text, max_keywords]
  additionalProperties: false
output_schema:
  type: object
  properties:
    summary: { type: string }
    keywords:
      type: array
      items: { type: string }
      minItems: 1
      maxItems: 10
    word_count: { type: integer, minimum: 0 }
  required: [summary, keywords, word_count]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
uses:
  - name: summary_app
    path: ./summary.rllm
    with:
      text: "{{input.text}}"
  - name: keyword_app
    path: ./keyword_extract.rllm
    with:
      text: "{{input.text}}"
---
Create a final briefing payload.
Return ONLY JSON object with keys: summary, keywords, word_count.

Summary source:
{{uses.summary_app.summary}}

Keyword source:
{{uses.keyword_app.keywords}}

Max keywords allowed:
{{input.max_keywords}}

<<<RECOVERY>>>
Previous output failed validation.
Return ONLY JSON with keys summary, keywords, word_count.

```rllm-python post
output = context.get("output", {})
summary = str(output.get("summary", ""))
keywords = output.get("keywords", [])
if not isinstance(keywords, list):
    keywords = []
max_keywords = int(context.get("input", {}).get("max_keywords", 5))
trimmed = [str(x) for x in keywords][:max_keywords]
result = {"keywords": trimmed, "word_count": len(summary.split())}
```
````

## 7) Validation and debug loop

Run this sequence:

```bash
runllm validate summary.rllm
runllm validate keyword_extract.rllm
runllm validate briefing_pipeline.rllm

runllm inspect briefing_pipeline.rllm

runllm run summary.rllm --input '{"text":"sample"}'
runllm run keyword_extract.rllm --input '{"text":"sample"}'
runllm run briefing_pipeline.rllm --input '{"text":"sample","max_keywords":5}'

runllm stats briefing_pipeline.rllm
runllm exectime briefing_pipeline.rllm
```

## 8) Error-driven triage

- `RLLM_008`: bad `uses` structure, missing `name/path`, invalid `with`, or cycle.
- `RLLM_009`: python block failed or returned non-object `result`.
- `RLLM_005`: output JSON object failed schema validation.
- `RLLM_006`: output could not be parsed as JSON.
- `RLLM_007`: output JSON was not an object.
- `RLLM_013`: all schema-retry attempts failed.

## 9) Agent checklist (copy/paste)

When generating multi-step apps automatically:

1. Keep each child app atomic.
2. Define strict input/output schemas first.
3. Ensure every app sets non-empty `llm.model`.
4. Ensure each `uses.with` is an object.
5. Use templates only for values intended as strings.
6. Add explicit JSON-only prompt + recovery.
7. Keep python blocks deterministic and return dict `result`.
8. Keep `python_post` patches schema-safe.
9. Validate child apps before parent app.
