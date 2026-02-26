from __future__ import annotations

import pytest

from runllm.errors import RunLLMError
from runllm.validation import (
    extract_json_object_candidates,
    parse_model_json_payload,
    validate_json_schema_instance,
)


def test_validate_json_schema_instance_input_error_code() -> None:
    with pytest.raises(RunLLMError) as exc:
        validate_json_schema_instance(
            instance={"count": "bad"},
            schema={
                "type": "object",
                "properties": {"count": {"type": "integer"}},
                "required": ["count"],
                "additionalProperties": False,
            },
            phase="input",
        )

    assert exc.value.payload.error_code == "RLLM_004"
    assert exc.value.payload.error_type == "InputSchemaError"
    assert exc.value.payload.details["path"] == ["count"]


def test_validate_json_schema_instance_output_error_code() -> None:
    with pytest.raises(RunLLMError) as exc:
        validate_json_schema_instance(
            instance={"ok": "yes"},
            schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
            phase="output",
        )

    assert exc.value.payload.error_code == "RLLM_005"
    assert exc.value.payload.error_type == "OutputSchemaError"


def test_parse_model_json_payload_invalid_json_raises() -> None:
    with pytest.raises(RunLLMError) as exc:
        parse_model_json_payload("this is not json")

    assert exc.value.payload.error_code == "RLLM_006"


def test_parse_model_json_payload_non_object_json_raises() -> None:
    with pytest.raises(RunLLMError) as exc:
        parse_model_json_payload("[1,2,3]")

    assert exc.value.payload.error_code == "RLLM_007"


def test_parse_model_json_payload_extracts_embedded_object() -> None:
    out = parse_model_json_payload("prefix text {\"summary\":\"ok\"} trailing text")
    assert out == {"summary": "ok"}


def test_extract_json_object_candidates_deduplicates() -> None:
    text = "{\"a\":1} noise {\"a\":1} and {\"b\":2}"
    out = extract_json_object_candidates(text)
    assert out == [{"a": 1}, {"b": 2}]


def test_extract_json_object_candidates_returns_empty_for_no_object() -> None:
    out = extract_json_object_candidates("no json object here")
    assert out == []
