# Authoring Guide

This guide helps you design `.rllm` apps that are easy for humans and coding agents to scaffold.

## Design workflow

1. Define `input_schema` first.
2. Define `output_schema` second.
3. Pick a single narrow task for the app.
4. Write prompt that returns only one JSON object.
5. Add `<<<RECOVERY>>>` with explicit correction instructions.
6. Set conservative `llm_params` (`temperature: 0`, `format: json` when available).

## Gold template

```yaml
---
name: classify_ticket
description: Classify support ticket into one intent.
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
      enum: [billing, technical, refund, sales, other]
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
Classify the ticket.
Return ONLY JSON object with keys intent and confidence.

Ticket:
{{input.text}}

<<<RECOVERY>>>
Previous response failed schema.
Return ONLY JSON object with keys intent and confidence.
```

## Good prompt patterns

- Say "Return ONLY JSON object" once near top.
- Include expected keys explicitly.
- Keep instructions short and non-conflicting.

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
