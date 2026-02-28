# Recovery Playbook

Use `<<<RECOVERY>>>` to improve schema compliance when a response fails validation.

Related docs:

- Prompt and authoring baseline: `authoring-guide.md`
- Output schema design patterns: `schema-cookbook.md`
- File format and `<<<RECOVERY>>>` syntax: `rllm-spec.md`
- Error codes for retry failures: `errors.md`

## Principle

Recovery should be short, direct, and schema-focused.

Runtime behavior note:

- `runllm` now appends an output contract on every attempt (including first attempt):
  - output schema JSON
  - deterministic example output JSON
  - JSON-only response rule
- Recovery text should therefore focus on correcting mistakes, not restating full schema.

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

## Inspect exact prompt sent to model

Use prompt debug flags when tuning compliance:

```bash
runllm run app.rllm --input '{"text":"sample"}' --debug-prompt-file temp/prompt-debug.txt
```

Useful flags:
- `--debug-prompt-file PATH` appends formatted wrapped + raw prompt blocks.
- `--debug-prompt-stdout` prints debug prompt blocks to stderr (stdout stays valid JSON).
- `--debug-prompt-wrap N` controls wrapped preview width.
