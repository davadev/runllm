from __future__ import annotations

import asyncio
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runllm import mcp_server
from runllm.errors import make_error


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
  required: [text]
  additionalProperties: false
output_schema:
  type: object
  properties:
    summary: {{ type: string }}
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


@dataclass
class _FakeTextContent:
    type: str
    text: str


@dataclass
class _FakeCallToolResult:
    content: list[_FakeTextContent]
    isError: bool = False


@dataclass
class _FakeTool:
    name: str
    description: str
    inputSchema: dict[str, Any]


class _FakeServer:
    last_instance: "_FakeServer | None" = None

    def __init__(self, _name: str) -> None:
        self.list_tools_handler: Any = None
        self.call_tool_handler: Any = None
        self.call_tool_validate_input: bool | None = None
        _FakeServer.last_instance = self

    def list_tools(self):
        def decorator(func):
            self.list_tools_handler = func
            return func

        return decorator

    def call_tool(self, validate_input: bool = True):
        self.call_tool_validate_input = validate_input

        def decorator(func):
            self.call_tool_handler = func
            return func

        return decorator

    def create_initialization_options(self) -> dict[str, Any]:
        return {}

    async def run(self, _read_stream: Any, _write_stream: Any, _init: dict[str, Any]) -> None:
        return None


class _FakeStdioContext:
    async def __aenter__(self) -> tuple[object, object]:
        return object(), object()

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _install_fake_mcp(monkeypatch) -> None:
    mcp_pkg = types.ModuleType("mcp")
    server_mod = types.ModuleType("mcp.server")
    stdio_mod = types.ModuleType("mcp.server.stdio")
    types_mod = types.ModuleType("mcp.types")

    setattr(server_mod, "Server", _FakeServer)
    setattr(stdio_mod, "stdio_server", lambda: _FakeStdioContext())
    setattr(types_mod, "Tool", _FakeTool)
    setattr(types_mod, "TextContent", _FakeTextContent)
    setattr(types_mod, "CallToolResult", _FakeCallToolResult)

    setattr(mcp_pkg, "server", server_mod)
    setattr(mcp_pkg, "types", types_mod)

    monkeypatch.setitem(sys.modules, "mcp", mcp_pkg)
    monkeypatch.setitem(sys.modules, "mcp.server", server_mod)
    monkeypatch.setitem(sys.modules, "mcp.server.stdio", stdio_mod)
    monkeypatch.setitem(sys.modules, "mcp.types", types_mod)


def _decode_result(result: _FakeCallToolResult) -> tuple[bool, dict[str, Any]]:
    payload = json.loads(result.content[0].text)
    return result.isError, payload


def _boot_server(monkeypatch, tmp_path: Path, *, project: str, autoload_config: bool | None = None) -> _FakeServer:
    _install_fake_mcp(monkeypatch)
    asyncio.run(mcp_server.serve_mcp(project=project, repo_root=tmp_path, autoload_config=autoload_config))
    server = _FakeServer.last_instance
    assert server is not None
    return server


def test_mcp_list_programs_is_project_scoped(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    _write_app(tmp_path / "userlib" / "support" / "reply.rllm", name="reply", description="Support reply")

    server = _boot_server(monkeypatch, tmp_path, project="billing")
    assert server.call_tool_validate_input is False

    result = asyncio.run(server.call_tool_handler("list_programs", {}))
    is_error, payload = _decode_result(result)

    assert is_error is False
    assert payload["ok"] is True
    assert payload["project"] == "billing"
    assert payload["total"] == 1
    card = payload["programs"][0]
    assert card["name"] == "invoice"
    assert "input_required" in card
    assert "returns" in card


def test_mcp_errors_use_protocol_error_flag(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("invoke_program", {"id": "", "input": {}}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"


def test_mcp_list_programs_rejects_non_numeric_cursor(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("list_programs", {"cursor": "abc"}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"


def test_mcp_invoke_program_propagates_runllm_error(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    listed = asyncio.run(server.call_tool_handler("list_programs", {}))
    _, listed_payload = _decode_result(listed)
    program_id = listed_payload["programs"][0]["id"]

    def _raise_runllm_error(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise make_error(
            error_code="RLLM_005",
            error_type="OutputSchemaError",
            message="output failed",
            details={"reason": "schema"},
            recovery_hint="Fix schema.",
            doc_ref="docs/errors.md#RLLM_005",
        )

    monkeypatch.setattr(mcp_server, "run_program", _raise_runllm_error)

    result = asyncio.run(server.call_tool_handler("invoke_program", {"id": program_id, "input": {"text": "hello"}}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_005"


def test_mcp_list_programs_accepts_null_arguments(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("list_programs", None))
    is_error, payload = _decode_result(result)

    assert is_error is False
    assert payload["ok"] is True
    assert payload["total"] == 1


def test_mcp_invoke_program_passes_autoload_config(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing", autoload_config=False)

    listed = asyncio.run(server.call_tool_handler("list_programs", {}))
    _, listed_payload = _decode_result(listed)
    program_id = listed_payload["programs"][0]["id"]

    captured: dict[str, Any] = {}

    def _fake_run_program(program_path: str, input_payload: dict[str, Any], options: Any, **kwargs: Any) -> dict[str, Any]:
        captured["autoload_config"] = kwargs.get("autoload_config")
        captured["options"] = options
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "run_program", _fake_run_program)

    result = asyncio.run(server.call_tool_handler("invoke_program", {"id": program_id, "input": {"text": "hello"}}))
    is_error, payload = _decode_result(result)

    assert is_error is False
    assert payload["ok"] is True
    assert captured["autoload_config"] is False
    assert captured["options"] is None


def test_mcp_list_programs_rejects_non_string_query(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("list_programs", {"query": 123}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"


def test_mcp_invoke_program_rejects_non_string_id(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("invoke_program", {"id": None, "input": {"text": "hello"}}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"


def test_mcp_list_programs_rejects_boolean_limit(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("list_programs", {"limit": True}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"


def test_mcp_list_programs_rejects_boolean_cursor(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("list_programs", {"cursor": False}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"


def test_mcp_list_programs_rejects_float_limit(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("list_programs", {"limit": 1.9}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"


def test_mcp_list_programs_rejects_float_cursor(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("list_programs", {"cursor": 1.9}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"


def test_mcp_builds_registry_once_per_server_session(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")

    counter = {"calls": 0}
    original_build = mcp_server.build_registry

    def _counting_build_registry(repo_root: Path):
        counter["calls"] += 1
        return original_build(repo_root)

    monkeypatch.setattr(mcp_server, "build_registry", _counting_build_registry)
    monkeypatch.setattr(mcp_server, "run_program", lambda *_a, **_kw: {"ok": True, "summary": "done"})
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    listed = asyncio.run(server.call_tool_handler("list_programs", {}))
    _, listed_payload = _decode_result(listed)
    program_id = listed_payload["programs"][0]["id"]
    asyncio.run(server.call_tool_handler("list_programs", {}))
    asyncio.run(server.call_tool_handler("invoke_program", {"id": program_id, "input": {"text": "hello"}}))

    assert counter["calls"] == 1


def test_mcp_list_programs_refresh_reloads_registry(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    baseline = asyncio.run(server.call_tool_handler("list_programs", {}))
    _, baseline_payload = _decode_result(baseline)
    assert baseline_payload["total"] == 1

    _write_app(tmp_path / "userlib" / "billing" / "new_offer.rllm", name="new_offer", description="New offer summary")

    stale = asyncio.run(server.call_tool_handler("list_programs", {}))
    _, stale_payload = _decode_result(stale)
    assert stale_payload["total"] == 1

    refreshed = asyncio.run(server.call_tool_handler("list_programs", {"refresh": True}))
    is_error, refreshed_payload = _decode_result(refreshed)
    assert is_error is False
    assert refreshed_payload["total"] == 2


def test_mcp_list_programs_rejects_non_boolean_refresh(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("list_programs", {"refresh": "yes"}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"


def test_mcp_invoke_program_auto_refreshes_on_id_miss(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    new_app_path = tmp_path / "userlib" / "billing" / "late_added.rllm"
    _write_app(new_app_path, name="late_added", description="Late added app")
    program_id = "billing:userlib/billing/late_added.rllm"

    monkeypatch.setattr(mcp_server, "run_program", lambda *_a, **_kw: {"ok": True, "summary": "done"})
    result = asyncio.run(server.call_tool_handler("invoke_program", {"id": program_id, "input": {"text": "hello"}}))
    is_error, payload = _decode_result(result)

    assert is_error is False
    assert payload["ok"] is True
    assert payload["id"] == program_id


def test_mcp_help_topic_returns_json_content(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("help_topic", {"topic": "rllm"}))
    is_error, payload = _decode_result(result)

    assert is_error is False
    assert payload["ok"] is True
    assert payload["topic"] == "rllm"
    assert payload["format"] == "json"
    assert "required_fields" in payload["content"]


def test_mcp_help_topic_supports_text_format(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("help_topic", {"topic": "schema", "format": "text"}))
    is_error, payload = _decode_result(result)

    assert is_error is False
    assert payload["ok"] is True
    assert payload["topic"] == "schema"
    assert payload["format"] == "text"
    assert "JSON Schema guidance" in payload["content"]


def test_mcp_help_topic_rejects_unknown_topic(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("help_topic", {"topic": "nope"}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"


def test_mcp_help_topic_rejects_invalid_format(monkeypatch, tmp_path: Path) -> None:
    _write_app(tmp_path / "userlib" / "billing" / "invoice.rllm", name="invoice", description="Billing invoice summary")
    server = _boot_server(monkeypatch, tmp_path, project="billing")

    result = asyncio.run(server.call_tool_handler("help_topic", {"topic": "rllm", "format": "xml"}))
    is_error, payload = _decode_result(result)

    assert is_error is True
    assert payload["ok"] is False
    assert payload["error"]["error_code"] == "RLLM_002"
