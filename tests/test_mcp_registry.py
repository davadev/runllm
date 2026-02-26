from __future__ import annotations

from pathlib import Path

from runllm.mcp_registry import list_programs_for_project


def _write_app(path: Path, *, name: str, description: str) -> None:
    content = f"""---
name: {name}
description: {description}
version: 0.1.0
author: tester
max_context_window: 8000
input_schema:
  type: object
  properties:
    text: {{ type: string }}
    tone: {{ type: string }}
  required: [text]
  additionalProperties: false
output_schema:
  type: object
  properties:
    summary: {{ type: string }}
    confidence: {{ type: number }}
  required: [summary]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Return JSON only.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_custom_app(path: Path, *, name: str, description: str, input_schema: str, output_schema: str) -> None:
    content = f"""---
name: {name}
description: {description}
version: 0.1.0
author: tester
max_context_window: 8000
input_schema:
{input_schema}
output_schema:
{output_schema}
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Return JSON only.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_registry_lists_userlib_project_with_contract_hints(tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice_summary.rllm", name="invoice_summary", description="Summarize invoice text.")

    result = list_programs_for_project(tmp_path, "billing")

    assert result["project"] == "billing"
    assert result["count"] == 1
    app = result["programs"][0]
    assert app["description"] == "Summarize invoice text."
    assert app["input_required"] == [{"name": "text", "type": "string", "required": True}]
    assert app["input_optional"] == [{"name": "tone", "type": "string", "required": False}]
    assert app["returns"] == [
        {"name": "summary", "type": "string", "required": True},
        {"name": "confidence", "type": "number", "required": False},
    ]
    assert app["invocation_template"] == {"text": "<string>"}


def test_registry_ignores_userlib_root_level_apps(tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "orphan.rllm", name="orphan", description="Should not be indexed.")
    _write_app(tmp_path / "userlib" / "support" / "ticket_reply.rllm", name="ticket_reply", description="Reply to support ticket.")

    result = list_programs_for_project(tmp_path, "support")

    assert result["count"] == 1
    assert result["programs"][0]["name"] == "ticket_reply"


def test_registry_treats_rllmlib_as_single_project(tmp_path: Path) -> None:
    _write_app(tmp_path / "rllmlib" / "scaffold_docs.rllm", name="scaffold_docs", description="Draft docs scaffold plan.")

    result = list_programs_for_project(tmp_path, "rllmlib")

    assert result["count"] == 1
    assert result["programs"][0]["project"] == "rllmlib"


def test_registry_pagination_cursor(tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "ops" / "a.rllm", name="a", description="A")
    _write_app(tmp_path / "userlib" / "ops" / "b.rllm", name="b", description="B")
    _write_app(tmp_path / "userlib" / "ops" / "c.rllm", name="c", description="C")

    first = list_programs_for_project(tmp_path, "ops", limit=2)
    second = list_programs_for_project(tmp_path, "ops", limit=2, cursor=first["next_cursor"])

    assert first["count"] == 2
    assert first["next_cursor"] == "2"
    assert second["count"] == 1
    assert second["next_cursor"] is None


def test_registry_negative_cursor_is_clamped_to_zero(tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "ops" / "a.rllm", name="a", description="A")
    _write_app(tmp_path / "userlib" / "ops" / "b.rllm", name="b", description="B")

    result = list_programs_for_project(tmp_path, "ops", limit=1, cursor="-1")

    assert result["count"] == 1
    assert result["programs"][0]["name"] == "a"


def test_registry_non_numeric_cursor_defaults_to_zero(tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "ops" / "a.rllm", name="a", description="A")
    _write_app(tmp_path / "userlib" / "ops" / "b.rllm", name="b", description="B")

    result = list_programs_for_project(tmp_path, "ops", limit=1, cursor="abc")

    assert result["count"] == 1
    assert result["programs"][0]["name"] == "a"


def test_registry_query_is_case_insensitive(tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "support" / "ticket_reply.rllm", name="ticket_reply", description="Reply to SUPPORT ticket.")
    _write_app(tmp_path / "userlib" / "support" / "invoice.rllm", name="invoice", description="Billing summary")

    result = list_programs_for_project(tmp_path, "support", query="support ticket")

    assert result["count"] == 1
    assert result["programs"][0]["name"] == "ticket_reply"


def test_registry_type_hints_cover_union_array_enum_and_unknown(tmp_path: Path) -> None:
    _write_custom_app(
        tmp_path / "userlib" / "ops" / "types_demo.rllm",
        name="types_demo",
        description="Demonstrate type rendering.",
        input_schema="""
  type: object
  properties:
    nullable_text:
      type: [string, 'null']
    labels:
      type: array
      items:
        type: string
    mode:
      enum: [fast, slow]
    mystery: {}
  required: [nullable_text]
  additionalProperties: false
""".rstrip(),
        output_schema="""
  type: object
  properties:
    status:
      type: string
  required: [status]
  additionalProperties: false
""".rstrip(),
    )

    result = list_programs_for_project(tmp_path, "ops")
    app = result["programs"][0]

    assert {row["name"]: row["type"] for row in app["input_required"]} == {"nullable_text": "string|null"}
    assert {row["name"]: row["type"] for row in app["input_optional"]} == {
        "labels": "array<string>",
        "mode": "enum",
        "mystery": "unknown",
    }


def test_registry_skips_invalid_rllm_files(tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "ops" / "valid.rllm", name="valid", description="Valid app")
    broken = tmp_path / "userlib" / "ops" / "broken.rllm"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("---\nname: broken\n---\n", encoding="utf-8")

    result = list_programs_for_project(tmp_path, "ops")

    assert result["count"] == 1
    assert result["programs"][0]["name"] == "valid"


def test_registry_logs_warning_for_invalid_rllm_files(tmp_path: Path, caplog) -> None:
    _write_app(tmp_path / "userlib" / "ops" / "valid.rllm", name="valid", description="Valid app")
    broken = tmp_path / "userlib" / "ops" / "broken.rllm"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("---\nname: broken\n---\n", encoding="utf-8")

    with caplog.at_level("WARNING"):
        result = list_programs_for_project(tmp_path, "ops")

    assert result["count"] == 1
    assert "Skipping invalid .rllm file during MCP registry build" in caplog.text


def test_registry_invocation_template_uses_enum_and_const_values(tmp_path: Path) -> None:
    _write_custom_app(
        tmp_path / "userlib" / "ops" / "enum_const_template.rllm",
        name="enum_const_template",
        description="Required enum/const placeholders",
        input_schema="""
  type: object
  properties:
    mode:
      enum: [fast, slow]
    api_version:
      const: v1
  required: [mode, api_version]
  additionalProperties: false
""".rstrip(),
        output_schema="""
  type: object
  properties:
    ok:
      type: boolean
  required: [ok]
  additionalProperties: false
""".rstrip(),
    )

    result = list_programs_for_project(tmp_path, "ops")
    app = result["programs"][0]

    assert app["invocation_template"] == {"api_version": "v1", "mode": "fast"}


def test_registry_invocation_template_recurses_for_required_nested_fields(tmp_path: Path) -> None:
    _write_custom_app(
        tmp_path / "userlib" / "ops" / "nested_template.rllm",
        name="nested_template",
        description="Nested placeholder template",
        input_schema="""
  type: object
  properties:
    config:
      type: object
      properties:
        mode:
          enum: [fast, slow]
        threshold:
          type: number
      required: [mode, threshold]
    items:
      type: array
      minItems: 2
      items:
        type: object
        properties:
          key: { type: string }
        required: [key]
  required: [config, items]
  additionalProperties: false
""".rstrip(),
        output_schema="""
  type: object
  properties:
    ok:
      type: boolean
  required: [ok]
  additionalProperties: false
""".rstrip(),
    )

    result = list_programs_for_project(tmp_path, "ops")
    app = result["programs"][0]

    assert app["invocation_template"] == {
        "config": {"mode": "fast", "threshold": 0.0},
        "items": [{"key": "<string>"}, {"key": "<string>"}],
    }


def test_registry_invocation_template_caps_large_min_items(tmp_path: Path) -> None:
    _write_custom_app(
        tmp_path / "userlib" / "ops" / "large_min_items.rllm",
        name="large_min_items",
        description="Large minItems template",
        input_schema="""
  type: object
  properties:
    batch:
      type: array
      minItems: 500
      items:
        type: object
        properties:
          id: { type: string }
        required: [id]
  required: [batch]
  additionalProperties: false
""".rstrip(),
        output_schema="""
  type: object
  properties:
    ok:
      type: boolean
  required: [ok]
  additionalProperties: false
""".rstrip(),
    )

    result = list_programs_for_project(tmp_path, "ops")
    app = result["programs"][0]

    assert len(app["invocation_template"]["batch"]) == 3
