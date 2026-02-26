# Recovery Playbook

Use `<<<RECOVERY>>>` to improve schema compliance when first response fails.

Related docs:

- Prompt and authoring baseline: `authoring-guide.md`
- Output schema design patterns: `schema-cookbook.md`
- File format and `<<<RECOVERY>>>` syntax: `rllm-spec.md`
- Error codes for retry failures: `errors.md`

## Principle

Recovery should be short, direct, and schema-focused.

Bad:
- "Please try again and do better."

Good:
- "Return ONLY a JSON object with keys `summary` and `keywords` (`keywords` is string array)."

## Recovery template

```text
<<<RECOVERY>>>
Previous response failed validation.
Return ONLY JSON object with exact keys: <k1>, <k2>, ...
Do not include markdown, prose, or schema definitions.
```

## Common failure modes

- Model outputs prose before/after JSON.
- Model outputs schema instead of instance.
- Model omits required keys.
- Model returns wrong top-level type.

## Mitigations

- Set `llm_params.format: json` where provider supports it.
- Keep output schema compact.
- Use defaults like `temperature: 0` for structured tasks.
- Increase retries only after improving recovery instruction.

## Retry strategy

- Start with `--max-retries 2`.
- If still failing, improve prompt/recovery first.
- Switch model only after prompt + schema simplification.
