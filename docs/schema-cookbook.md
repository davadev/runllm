# Schema Cookbook

Use these schema patterns to improve output compliance and reduce retries.

## Classification

```yaml
type: object
properties:
  label:
    type: string
    enum: [a, b, c]
  confidence:
    type: number
    minimum: 0
    maximum: 1
required: [label, confidence]
additionalProperties: false
```

## Extraction list

```yaml
type: object
properties:
  items:
    type: array
    items:
      type: string
required: [items]
additionalProperties: false
```

## Nested extraction

```yaml
type: object
properties:
  action_items:
    type: array
    items:
      type: object
      properties:
        owner: { type: string }
        task: { type: string }
        due_date:
          type: [string, "null"]
      required: [owner, task]
      additionalProperties: false
required: [action_items]
additionalProperties: false
```

## Planner output

```yaml
type: object
properties:
  plan_steps:
    type: array
    items: { type: string }
  files_to_touch:
    type: array
    items: { type: string }
  risks:
    type: array
    items: { type: string }
required: [plan_steps, files_to_touch, risks]
additionalProperties: false
```

## Compliance checker

```yaml
type: object
properties:
  is_compliant: { type: boolean }
  violations:
    type: array
    items: { type: string }
  fixed_text: { type: string }
required: [is_compliant, violations, fixed_text]
additionalProperties: false
```

## Anti-patterns

- Missing `required` list.
- No `additionalProperties: false` for strict contracts.
- Overly deep object graphs for small local models.
- Large unions unless needed.

## Practical schema tips

- Prefer enums to free-form strings where possible.
- Use nullable fields (`type: [string, "null"]`) when information may be absent.
- Keep key names short and stable across versions.
