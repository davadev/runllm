# Authoring Guide

This guide helps you design `.rllm` apps that are easy for humans and coding agents to scaffold.

Related docs:

- Canonical format reference: `rllm-spec.md`
- Reusable schema shapes: `schema-cookbook.md`
- Recovery strategy: `recovery-playbook.md`
- Multi-step composition patterns: `multistep-apps.md`
- Agent-focused generation rules: `agent-scaffold-guide.md`

## Design workflow

1. Define `input_schema` first.
2. Define `output_schema` second.
3. Pick a single narrow task for the app.
4. Write prompt that returns only one JSON object.
5. Add `<<<RECOVERY>>>` with explicit correction instructions.
6. Set conservative `llm_params` (`temperature: 0`, `format: json` when available).

## Stage contract checklist

Use this checklist for every stage in a composed workflow:

1. One stage = one primary responsibility.
2. Input/output schemas are minimal, strict, and explicit.
3. Downstream-required fields are present with stable key names.
4. Failure behavior is explicit (retryable vs non-retryable).
5. Stage output is verifiable by deterministic checks where possible.

## Gold template

```yaml
---
name: classify_request
description: Classify an input request into one intent.
version: 0.1.0
author: team
max_context_window: 6000
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
    intent:
      type: string
      enum: [type_a, type_b, type_c, other]
    confidence:
      type: number
      minimum: 0
      maximum: 1
  required: [intent, confidence]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
recommended_models:
  - ollama/llama3.1:8b
tags: [classification]
---
Classify the request.
Return ONLY JSON object with keys intent and confidence.

Input:
{{input.text}}

<<<RECOVERY>>>
Previous response failed schema.
Return ONLY JSON object with keys intent and confidence.
```

## Good prompt patterns

- Say "Return ONLY JSON object" once near top.
- Include expected keys explicitly.
- Keep instructions short and non-conflicting.
- Keep schema compact; runtime now appends output schema + deterministic example on every attempt.

## Runtime prompt contract

At runtime, `runllm` appends an output contract to the model prompt on every attempt:
- output schema JSON,
- deterministic example output JSON,
- strict JSON-only response instruction.

This means app prompts should stay concise and task-focused; avoid duplicating long schema text in prompt body.

## Runtime budgeting guidance

- Cap discovery fan-out early (for example, number of planned questions/leads).
- Avoid aggressive evidence truncation late in the pipeline once evidence is verified.
- Measure stage timings during development and track dominant latency contributors.
- Set stage timeouts based on expected payload size rather than one global default.

## Avoid

- Multi-task prompts (classify + summarize + rewrite) in one app.
- Loose schemas with missing `required` and `additionalProperties: false`.
- Recovery prompts that restate vague goals without schema constraints.

## Validation loop

Use this loop when creating new apps:

```bash
runllm validate app.rllm
runllm inspect app.rllm
runllm run app.rllm --input '{"text":"sample"}'
runllm stats app.rllm
```
