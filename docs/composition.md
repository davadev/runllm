# Composition Guide

Use `uses` in frontmatter to call child `.rllm` apps before parent prompt execution.

Related docs:

- Full multi-step architecture examples: `multistep-apps.md`
- File format details for `uses`: `rllm-spec.md`
- Authoring workflow and contract-first setup: `authoring-guide.md`
- CLI validation/inspection commands: `cli.md`
- Dependency and schema error codes: `errors.md`

Composition is function-like:

- Parent defines child calls.
- Parent maps inputs to each child.
- Parent prompt consumes typed child outputs.

## Example

```yaml
uses:
  - name: summary_app
    path: ./summary.rllm
    with:
      text: "{{input.text}}"
```

Child output is available in parent prompt as:

- `{{uses.summary_app.summary}}`

## Typed mapping rules

- If `with` value is a template string, rendered value is string.
- If `with` value is YAML literal (number, bool, list, object), type is preserved.

Example with mixed mapping:

```yaml
uses:
  - name: scorer
    path: ./scorer.rllm
    with:
      text: "{{input.text}}"     # becomes string
      threshold: 0.8              # stays number
      flags: [fast, strict]       # stays list
```

Rules:
- Child path resolves relative to parent `.rllm` file.
- Circular dependencies are rejected.
- Child input should satisfy child `input_schema`.

## Interface stability rules

For robust composition over time:

- Keep intermediate field names stable across stages.
- Prefer additive schema evolution; avoid breaking key renames.
- Preserve provenance fields through intermediate artifacts when stages extract evidence.
- Avoid hidden coupling where downstream logic depends on free-form prose conventions.

## Common pitfalls

- Passing objects through template interpolation when child expects object type.
- Name collisions in `uses` entries.
- Missing required child input keys.
- Stage outputs that change shape between versions without corresponding parent updates.

## Debug workflow

1. `runllm validate parent.rllm`
2. `runllm inspect parent.rllm`
3. Run each child directly with sample payload.
4. Run parent and inspect error payload (`expected_schema`, `received_payload`).
