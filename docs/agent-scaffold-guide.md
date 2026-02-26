# Agent Scaffold Guide

This file is written for coding LLM agents that generate `.rllm` apps.

Related docs:

- Canonical schema/metadata rules: `rllm-spec.md`
- Proven authoring workflow: `authoring-guide.md`
- Reusable output schema patterns: `schema-cookbook.md`
- Retry prompt patterns: `recovery-playbook.md`
- Composition and multi-step scaffolding: `composition.md`, `multistep-apps.md`
- Runtime and failures: `cli.md`, `errors.md`

## Objective

Given a user request, produce a valid `.rllm` file that passes:

```bash
runllm validate <file.rllm>
```

## Hard requirements

- Include all required frontmatter keys.
- Define strict `input_schema` and `output_schema`.
- Prompt must request JSON object only.
- Add `<<<RECOVERY>>>` block for structured retries.
- Use one atomic task per app.

## Scaffold algorithm

1. Extract one core task from user request.
2. Define minimal input contract.
3. Define explicit output contract.
4. Choose model for task complexity.
5. Add `llm_params` with `temperature: 0` and `format: json` when possible.
6. Write concise prompt with explicit output keys.
7. Write strict recovery prompt.
8. Validate and iterate.

## Generation checklist

- Required metadata present.
- `max_context_window` set.
- `required` fields present in schemas.
- `additionalProperties: false` where strictness is needed.
- Prompt references only existing template variables.
- Composition mappings match child input schema types.
- Recovery prompt forbids prose/markdown/schema output.

## Minimal agent output template

```yaml
---
name: <snake_case_name>
description: <one sentence>
version: 0.1.0
author: <author>
max_context_window: <int>
input_schema:
  type: object
  properties: {}
  required: []
  additionalProperties: false
output_schema:
  type: object
  properties: {}
  required: []
  additionalProperties: false
llm:
  model: <provider/model>
llm_params:
  temperature: 0
  format: json
---
Return ONLY valid JSON object matching output schema.

<<<RECOVERY>>>
Previous response failed validation. Return ONLY a valid JSON object matching output schema.
```

## Definition of done for agent-generated app

- `runllm validate` succeeds.
- At least one sample `runllm run` call succeeds.
- Output JSON conforms to schema on repeated runs.
