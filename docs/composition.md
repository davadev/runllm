# Composition Guide

Use `uses` in frontmatter to call child `.rllm` apps before parent prompt execution.

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

Rules:
- Child path resolves relative to parent `.rllm` file.
- Circular dependencies are rejected.
- Child input should satisfy child `input_schema`.
