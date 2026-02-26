from __future__ import annotations

import json
from typing import Any

import jsonschema

from runllm.errors import make_error


def validate_json_schema_instance(
    *, instance: dict[str, Any], schema: dict[str, Any], phase: str
) -> None:
    try:
        jsonschema.validate(instance=instance, schema=schema)
    except jsonschema.ValidationError as exc:
        error_code = "RLLM_004" if phase == "input" else "RLLM_005"
        error_type = "InputSchemaError" if phase == "input" else "OutputSchemaError"
        raise make_error(
            error_code=error_code,
            error_type=error_type,
            message=f"{phase} schema validation failed.",
            details={
                "validator": exc.validator,
                "path": list(exc.absolute_path),
                "schema_path": list(exc.absolute_schema_path),
                "reason": exc.message,
            },
            expected_schema=schema,
            received_payload=instance,
            recovery_hint="Return a payload that exactly matches the required schema.",
            doc_ref=f"docs/errors.md#{error_code}",
        )


def parse_model_json_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise make_error(
            error_code="RLLM_006",
            error_type="OutputSchemaError",
            message="Model output is not valid JSON.",
            details={"json_error": str(exc)},
            received_payload=stripped,
            recovery_hint="Respond with only a valid JSON object matching output_schema.",
            doc_ref="docs/errors.md#RLLM_006",
        )
    if not isinstance(obj, dict):
        raise make_error(
            error_code="RLLM_007",
            error_type="OutputSchemaError",
            message="Model output must be a JSON object.",
            details={"actual_type": type(obj).__name__},
            received_payload=obj,
            recovery_hint="Respond with a top-level JSON object.",
            doc_ref="docs/errors.md#RLLM_007",
        )
    return obj
