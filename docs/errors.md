# Error Codes

- `RLLM_001` ParseError
- `RLLM_002` MetadataValidationError
- `RLLM_003` LLMParamValidationError
- `RLLM_004` InputSchemaError
- `RLLM_005` OutputSchemaError
- `RLLM_006` OutputSchemaError (invalid JSON)
- `RLLM_007` OutputSchemaError (non-object JSON)
- `RLLM_008` DependencyResolutionError
- `RLLM_009` PythonBlockExecutionError
- `RLLM_010` OllamaModelMissingError
- `RLLM_011` ExecutionError (provider response shape)
- `RLLM_012` ContextWindowExceededError
- `RLLM_013` RetryExhaustedError
- `RLLM_999` UnknownUnhandledError

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
