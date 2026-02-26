# .rllm Spec v0.1

## Shape

`.rllm` files contain YAML frontmatter followed by prompt body.

```text
---
<yaml metadata>
---
<prompt body>
```

Optional sections in body:
- `<<<RECOVERY>>>` splits main prompt and retry recovery prompt
- ```` ```rllm-python pre ```` and ```` ```rllm-python post ```` blocks

## Required frontmatter keys

- `name` (string)
- `description` (string)
- `version` (string)
- `author` (string)
- `max_context_window` (positive integer)
- `input_schema` (object, JSON Schema subset)
- `output_schema` (object, JSON Schema subset)
- `llm` (object, must include `model`)
- `llm_params` (object, validated against supported LiteLLM params)

## Optional keys

- `metadata` (object, free-form)
- `recommended_models` (string list)
- `tags` (string list)
- `uses` (list of dependency apps)

`uses` item shape:

```yaml
uses:
  - name: summary_app
    path: ./summary.rllm
    with:
      text: "{{input.text}}"
```

## Template Variables

- `{{input.<key>}}` for app input
- `{{uses.<dep_name>.<key>}}` for dependency outputs

## Python Blocks

`pre` block runs before prompt rendering and can inject context keys.

`post` block runs after output validation and can append fields to output.

Python block contract:
- Receives `context` dict
- Must set `result` as dict (or leave empty)

Default mode uses restricted builtins and timeout.
