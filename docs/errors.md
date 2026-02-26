# Error Codes

All runtime failures are emitted as structured JSON.

Related docs:

- CLI behavior and exit codes: `cli.md`
- Core format and metadata validation rules: `rllm-spec.md`
- Schema design to reduce validation failures: `schema-cookbook.md`
- Recovery prompt strategy for `RLLM_005/006/007/013`: `recovery-playbook.md`
- Dependency debugging context: `composition.md`

## Error catalog

- `RLLM_001` ParseError
  - Trigger: invalid file shape/frontmatter/prompt.
  - Fix: ensure opening and closing `---` frontmatter and non-empty prompt body.

- `RLLM_002` MetadataValidationError
  - Trigger: missing required keys or invalid metadata types.
  - Fix: provide all required keys with correct types.

- `RLLM_003` LLMParamValidationError
  - Trigger: unsupported `llm_params` keys.
  - Fix: use only supported keys listed in `docs/rllm-spec.md`.

- `RLLM_004` InputSchemaError
  - Trigger: runtime input does not satisfy `input_schema`.
  - Fix: inspect `expected_schema` + `details.path` and correct payload.

- `RLLM_005` OutputSchemaError
  - Trigger: parsed model JSON object fails `output_schema`.
  - Fix: tighten prompt/recovery prompt and model choice.

- `RLLM_006` OutputSchemaError (invalid JSON)
  - Trigger: model output cannot be parsed as JSON object.
  - Fix: enforce JSON-only response and set `llm_params.format: json` where possible.

- `RLLM_007` OutputSchemaError (non-object JSON)
  - Trigger: top-level JSON is not object.
  - Fix: require object wrapper in prompt.

- `RLLM_008` DependencyResolutionError
  - Trigger: invalid `uses`, missing keys, or cycle.
  - Fix: validate `uses` structure and break circular references.

- `RLLM_009` PythonBlockExecutionError
  - Trigger: python block exception/timeout/non-dict result/memory-limit failure.
  - Fix: keep block deterministic, short, and assign `result` as object.

- `RLLM_010` OllamaModelMissingError
  - Trigger: requested local model not found/pull failed.
  - Fix: `ollama pull <model>` or run with `--ollama-auto-pull`.

- `RLLM_011` ExecutionError
  - Trigger: unexpected provider response shape.
  - Fix: verify provider/model compatibility and LiteLLM setup.

- `RLLM_012` ContextWindowExceededError
  - Trigger: estimated prompt + input tokens exceed `max_context_window`.
  - Fix: shrink input or raise `max_context_window`.

- `RLLM_013` RetryExhaustedError
  - Trigger: all retry attempts failed output JSON/schema validation (`RLLM_005/006/007`).
  - Fix: improve `<<<RECOVERY>>>`, simplify schema, or switch model.

- `RLLM_014` MissingProviderCredentialError
  - Trigger: provider model selected without required API key in environment/autoloaded config.
  - Fix: set missing env var (for example `OPENAI_API_KEY`) and retry.

- `RLLM_015` RuntimeCompatibilityError
  - Trigger: `.rllm` `runllm_compat` bounds do not include installed `runllm` version.
  - Fix: upgrade/downgrade `runllm` runtime or adjust `runllm_compat` metadata.

- `RLLM_999` UnknownUnhandledError
  - Trigger: non-classified exception.
  - Fix: inspect message and reproduce with smaller input.

All errors are emitted as structured JSON:

```json
{
  "error_code": "RLLM_004",
  "error_type": "InputSchemaError",
  "message": "input schema validation failed.",
  "details": {},
  "expected_schema": {},
  "received_payload": {},
  "recovery_hint": "...",
  "doc_ref": "docs/errors.md#RLLM_004"
}
```

## Fast triage checklist

1. Check `error_code` and `message`.
2. Compare `received_payload` with `expected_schema`.
3. Use `details.path` and `details.reason` to locate mismatch.
4. Rerun with simpler sample input.
5. Improve recovery prompt before increasing retries.
