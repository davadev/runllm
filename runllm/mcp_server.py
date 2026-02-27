from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types
from typing import Any

from runllm.errors import RunLLMError
from runllm.executor import run_program
from runllm.help_content import HELP_TOPICS, help_topics_json, help_topics_text
from runllm.mcp_registry import (
    build_registry,
    list_programs_from_entries,
    resolve_program_id_from_entries,
)
from runllm.mcp_workflow_registry import (
    WorkflowEntry,
    build_workflow_registry,
    list_workflows_from_entries,
    resolve_workflow_id_from_entries,
)
from runllm.validation import validate_json_schema_instance


async def serve_mcp(
    project: str,
    repo_root: Path | None = None,
    *,
    autoload_config: bool | None = None,
    trusted_workflows: bool = False,
) -> None:
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import CallToolResult, TextContent, Tool
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MCP dependency is not installed. Install package 'mcp' to use `runllm mcp serve`."
        ) from exc

    def _ok_payload(**kwargs: Any) -> CallToolResult:
        payload = json.dumps({"ok": True, **kwargs}, ensure_ascii=True)
        return CallToolResult(content=[TextContent(type="text", text=payload)], isError=False)

    def _err_payload(payload: dict[str, Any]) -> CallToolResult:
        error_payload = json.dumps({"ok": False, "error": payload}, ensure_ascii=True)
        return CallToolResult(content=[TextContent(type="text", text=error_payload)], isError=True)

    root = (repo_root or Path.cwd()).resolve()
    registry_entries = build_registry(root)
    workflow_entries = build_workflow_registry(root)

    def _refresh_registry() -> None:
        nonlocal registry_entries
        registry_entries = build_registry(root)

    def _refresh_workflow_registry() -> None:
        nonlocal workflow_entries
        workflow_entries = build_workflow_registry(root)

    def _invoke_workflow_entry(entry: WorkflowEntry, input_payload: dict[str, Any]) -> dict[str, Any]:
        spec_file, func_name = entry.entrypoint.split(":", 1)
        base_dir = entry.path.parent.resolve()
        module_path = (base_dir / spec_file).resolve()
        try:
            module_path.relative_to(base_dir)
        except ValueError as exc:
            raise RuntimeError("Workflow entrypoint must resolve under workflow spec directory.") from exc
        if module_path.suffix != ".py":
            raise RuntimeError("Workflow entrypoint must target a .py file.")
        if not module_path.exists() or not module_path.is_file():
            raise RuntimeError(f"Workflow entrypoint module not found: {module_path}")

        rel_module_parts = module_path.relative_to(base_dir).with_suffix("").parts
        package_root = f"runllm_workflow_pkg_{abs(hash(str(base_dir)))}"

        package_name = package_root
        package_path = base_dir
        if package_name not in sys.modules:
            pkg_mod = types.ModuleType(package_name)
            pkg_mod.__path__ = [str(package_path)]
            sys.modules[package_name] = pkg_mod
        for part in rel_module_parts[:-1]:
            package_name = f"{package_name}.{part}"
            package_path = package_path / part
            if package_name not in sys.modules:
                pkg_mod = types.ModuleType(package_name)
                pkg_mod.__path__ = [str(package_path)]
                sys.modules[package_name] = pkg_mod

        module_name = ".".join([package_root, *rel_module_parts])
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load workflow module: {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        fn = getattr(module, func_name, None)
        if not callable(fn):
            raise RuntimeError(f"Workflow function not found: {func_name}")
        result = fn(input_payload)
        if not isinstance(result, dict):
            raise RuntimeError("Workflow function must return a JSON object (dict).")
        return result

    server = Server("runllm")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        tools: list[Tool] = [
            Tool(
                name="list_programs",
                description=(
                    "List available runllm programs for the scoped project. "
                    "Response includes description, required input params, and return fields with type hints."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional plain-text filter against name/description.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Page size (default: 25, max: 100).",
                            "default": 25,
                        },
                        "cursor": {
                            "type": "string",
                            "description": "Pagination cursor from previous response.",
                        },
                        "refresh": {
                            "type": "boolean",
                            "description": "Rebuild registry before listing programs.",
                        },
                    },
                },
            ),
            Tool(
                name="invoke_program",
                description="Invoke one program by id using JSON input object.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Program id returned by list_programs.",
                        },
                        "input": {
                            "type": "object",
                            "description": "Input payload object that satisfies the program input schema.",
                        },
                    },
                    "required": ["id", "input"],
                },
            ),
            Tool(
                name="list_workflows",
                description=(
                    "List available workflow entrypoints for the scoped project. "
                    "Workflows provide one-call orchestration interfaces."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional plain-text filter against name/description.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Page size (default: 25, max: 100).",
                            "default": 25,
                        },
                        "cursor": {
                            "type": "string",
                            "description": "Pagination cursor from previous response.",
                        },
                        "refresh": {
                            "type": "boolean",
                            "description": "Rebuild workflow registry before listing workflows.",
                        },
                    },
                },
            ),
            Tool(
                name="help_topic",
                description=(
                    "Return runllm authoring reference content for one topic. "
                    "Use this before scaffolding new .rllm apps."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Help topic name.",
                            "enum": list(HELP_TOPICS),
                        },
                        "format": {
                            "type": "string",
                            "description": "Response format.",
                            "enum": ["json", "text"],
                            "default": "json",
                        },
                    },
                    "required": ["topic"],
                },
            ),
        ]
        if trusted_workflows:
            tools.append(
                Tool(
                    name="invoke_workflow",
                    description="Invoke one workflow by id using JSON input object.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Workflow id returned by list_workflows.",
                            },
                            "input": {
                                "type": "object",
                                "description": "Input payload object that satisfies workflow input schema.",
                            },
                        },
                        "required": ["id", "input"],
                    },
                )
            )
        return tools

    @server.call_tool(validate_input=False)  # type: ignore[arg-type]
    async def call_tool(name: str, arguments: Any) -> Any:
        try:
            args = arguments if isinstance(arguments, dict) else {}
            if name == "list_programs":
                query = args.get("query")
                if query is not None and not isinstance(query, str):
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "list_programs query must be a string when provided.",
                            "details": {"query_type": type(query).__name__},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Pass query as a string or omit it.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                refresh_value = args.get("refresh", False)
                if not isinstance(refresh_value, bool):
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "list_programs refresh must be a boolean when provided.",
                            "details": {"refresh_type": type(refresh_value).__name__},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Pass refresh as true/false or omit it.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                if refresh_value:
                    _refresh_registry()
                limit_value = args.get("limit", 25)
                if isinstance(limit_value, bool):
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "list_programs limit must be a positive integer.",
                            "details": {"limit": limit_value},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Pass a positive integer for limit.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                if isinstance(limit_value, int):
                    limit = limit_value
                elif isinstance(limit_value, str) and limit_value.strip().isdigit():
                    limit = int(limit_value.strip())
                else:
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "list_programs limit must be a positive integer.",
                            "details": {"limit": limit_value},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Pass a positive integer for limit.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                cursor = args.get("cursor")
                if limit < 1:
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "list_programs limit must be a positive integer.",
                            "details": {"limit": limit},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Pass a positive integer for limit.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                cursor_for_registry: str | None = None
                if cursor is not None:
                    if isinstance(cursor, bool):
                        return _err_payload(
                            {
                                "error_code": "RLLM_002",
                                "error_type": "MetadataValidationError",
                                "message": "list_programs cursor must be a non-negative integer.",
                                "details": {"cursor": cursor},
                                "expected_schema": None,
                                "received_payload": arguments,
                                "recovery_hint": "Pass cursor from prior list_programs response.",
                                "doc_ref": "docs/errors.md#RLLM_002",
                            }
                        )
                    if isinstance(cursor, int):
                        parsed_cursor = cursor
                    elif isinstance(cursor, str) and cursor.strip().isdigit():
                        parsed_cursor = int(cursor.strip())
                    else:
                        return _err_payload(
                            {
                                "error_code": "RLLM_002",
                                "error_type": "MetadataValidationError",
                                "message": "list_programs cursor must be a non-negative integer.",
                                "details": {"cursor": cursor},
                                "expected_schema": None,
                                "received_payload": arguments,
                                "recovery_hint": "Pass cursor from prior list_programs response.",
                                "doc_ref": "docs/errors.md#RLLM_002",
                            }
                        )
                    if parsed_cursor < 0:
                        return _err_payload(
                            {
                                "error_code": "RLLM_002",
                                "error_type": "MetadataValidationError",
                                "message": "list_programs cursor must be a non-negative integer.",
                                "details": {"cursor": cursor},
                                "expected_schema": None,
                                "received_payload": arguments,
                                "recovery_hint": "Pass cursor from prior list_programs response.",
                                "doc_ref": "docs/errors.md#RLLM_002",
                            }
                        )
                    cursor_for_registry = str(parsed_cursor)
                result = list_programs_from_entries(
                    entries=registry_entries,
                    project=project,
                    query=query,
                    limit=limit,
                    cursor=str(cursor_for_registry) if cursor_for_registry is not None else None,
                )
                return _ok_payload(**result)

            if name == "invoke_program":
                raw_id = args.get("id")
                if not isinstance(raw_id, str):
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "invoke_program id must be a string.",
                            "details": {"id_type": type(raw_id).__name__},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Use id value returned by list_programs.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                program_id = raw_id.strip()
                input_payload = args.get("input")
                if not program_id:
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "invoke_program requires a non-empty id.",
                            "details": {"id": program_id},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Use id value returned by list_programs.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                if not isinstance(input_payload, dict):
                    return _err_payload(
                        {
                            "error_code": "RLLM_004",
                            "error_type": "InputSchemaError",
                            "message": "invoke_program input must be a JSON object.",
                            "details": {"actual_type": type(input_payload).__name__},
                            "expected_schema": {"type": "object"},
                            "received_payload": input_payload,
                            "recovery_hint": "Pass a JSON object as input.",
                            "doc_ref": "docs/errors.md#RLLM_004",
                        }
                    )

                resolved = resolve_program_id_from_entries(
                    entries=registry_entries,
                    project=project,
                    program_id=program_id,
                )
                if resolved is None:
                    _refresh_registry()
                    resolved = resolve_program_id_from_entries(
                        entries=registry_entries,
                        project=project,
                        program_id=program_id,
                    )
                if resolved is None:
                    return _err_payload(
                        {
                            "error_code": "RLLM_008",
                            "error_type": "DependencyResolutionError",
                            "message": "Program id not found in scoped project.",
                            "details": {"id": program_id, "project": project},
                            "expected_schema": None,
                            "received_payload": None,
                            "recovery_hint": "Call list_programs to refresh ids for this project scope.",
                            "doc_ref": "docs/errors.md#RLLM_008",
                        }
                    )

                result = await asyncio.to_thread(
                    run_program,
                    str(resolved),
                    input_payload,
                    None,
                    autoload_config=autoload_config,
                )
                return _ok_payload(project=project, id=program_id, result=result)

            if name == "list_workflows":
                query = args.get("query")
                if query is not None and not isinstance(query, str):
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "list_workflows query must be a string when provided.",
                            "details": {"query_type": type(query).__name__},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Pass query as a string or omit it.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                refresh_value = args.get("refresh", False)
                if not isinstance(refresh_value, bool):
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "list_workflows refresh must be a boolean when provided.",
                            "details": {"refresh_type": type(refresh_value).__name__},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Pass refresh as true/false or omit it.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                if refresh_value:
                    _refresh_workflow_registry()
                limit_value = args.get("limit", 25)
                if isinstance(limit_value, bool):
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "list_workflows limit must be a positive integer.",
                            "details": {"limit": limit_value},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Pass a positive integer for limit.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                if isinstance(limit_value, int):
                    limit = limit_value
                elif isinstance(limit_value, str) and limit_value.strip().isdigit():
                    limit = int(limit_value.strip())
                else:
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "list_workflows limit must be a positive integer.",
                            "details": {"limit": limit_value},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Pass a positive integer for limit.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                cursor = args.get("cursor")
                if limit < 1:
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "list_workflows limit must be a positive integer.",
                            "details": {"limit": limit},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Pass a positive integer for limit.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                cursor_for_registry: str | None = None
                if cursor is not None:
                    if isinstance(cursor, bool):
                        return _err_payload(
                            {
                                "error_code": "RLLM_002",
                                "error_type": "MetadataValidationError",
                                "message": "list_workflows cursor must be a non-negative integer.",
                                "details": {"cursor": cursor},
                                "expected_schema": None,
                                "received_payload": arguments,
                                "recovery_hint": "Pass cursor from prior list_workflows response.",
                                "doc_ref": "docs/errors.md#RLLM_002",
                            }
                        )
                    if isinstance(cursor, int):
                        parsed_cursor = cursor
                    elif isinstance(cursor, str) and cursor.strip().isdigit():
                        parsed_cursor = int(cursor.strip())
                    else:
                        return _err_payload(
                            {
                                "error_code": "RLLM_002",
                                "error_type": "MetadataValidationError",
                                "message": "list_workflows cursor must be a non-negative integer.",
                                "details": {"cursor": cursor},
                                "expected_schema": None,
                                "received_payload": arguments,
                                "recovery_hint": "Pass cursor from prior list_workflows response.",
                                "doc_ref": "docs/errors.md#RLLM_002",
                            }
                        )
                    if parsed_cursor < 0:
                        return _err_payload(
                            {
                                "error_code": "RLLM_002",
                                "error_type": "MetadataValidationError",
                                "message": "list_workflows cursor must be a non-negative integer.",
                                "details": {"cursor": cursor},
                                "expected_schema": None,
                                "received_payload": arguments,
                                "recovery_hint": "Pass cursor from prior list_workflows response.",
                                "doc_ref": "docs/errors.md#RLLM_002",
                            }
                        )
                    cursor_for_registry = str(parsed_cursor)
                result = list_workflows_from_entries(
                    entries=workflow_entries,
                    project=project,
                    query=query,
                    limit=limit,
                    cursor=str(cursor_for_registry) if cursor_for_registry is not None else None,
                )
                return _ok_payload(**result)

            if name == "invoke_workflow":
                if not trusted_workflows:
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "invoke_workflow is disabled unless trusted workflow execution is enabled.",
                            "details": {"trusted_workflows": trusted_workflows},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Restart MCP server with --trusted-workflows to enable workflow execution.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                raw_id = args.get("id")
                if not isinstance(raw_id, str):
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "invoke_workflow id must be a string.",
                            "details": {"id_type": type(raw_id).__name__},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Use id value returned by list_workflows.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                workflow_id = raw_id.strip()
                input_payload = args.get("input")
                if not workflow_id:
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "invoke_workflow requires a non-empty id.",
                            "details": {"id": workflow_id},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Use id value returned by list_workflows.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                if not isinstance(input_payload, dict):
                    return _err_payload(
                        {
                            "error_code": "RLLM_004",
                            "error_type": "InputSchemaError",
                            "message": "invoke_workflow input must be a JSON object.",
                            "details": {"actual_type": type(input_payload).__name__},
                            "expected_schema": {"type": "object"},
                            "received_payload": input_payload,
                            "recovery_hint": "Pass a JSON object as input.",
                            "doc_ref": "docs/errors.md#RLLM_004",
                        }
                    )

                resolved = resolve_workflow_id_from_entries(entries=workflow_entries, project=project, workflow_id=workflow_id)
                if resolved is None:
                    _refresh_workflow_registry()
                    resolved = resolve_workflow_id_from_entries(entries=workflow_entries, project=project, workflow_id=workflow_id)
                if resolved is None:
                    return _err_payload(
                        {
                            "error_code": "RLLM_008",
                            "error_type": "DependencyResolutionError",
                            "message": "Workflow id not found in scoped project.",
                            "details": {"id": workflow_id, "project": project},
                            "expected_schema": None,
                            "received_payload": None,
                            "recovery_hint": "Call list_workflows to refresh ids for this project scope.",
                            "doc_ref": "docs/errors.md#RLLM_008",
                        }
                    )

                validate_json_schema_instance(instance=input_payload, schema=resolved.input_schema, phase="input")
                output_payload = await asyncio.to_thread(_invoke_workflow_entry, resolved, input_payload)
                validate_json_schema_instance(instance=output_payload, schema=resolved.output_schema, phase="output")
                return _ok_payload(project=project, id=workflow_id, result=output_payload)

            if name == "help_topic":
                raw_topic = args.get("topic")
                if not isinstance(raw_topic, str):
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "help_topic topic must be a string.",
                            "details": {"topic_type": type(raw_topic).__name__},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": f"Pass one of: {', '.join(HELP_TOPICS)}.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                topic = raw_topic.strip()
                if topic not in HELP_TOPICS:
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "help_topic topic is not supported.",
                            "details": {"topic": topic, "supported_topics": list(HELP_TOPICS)},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": f"Pass one of: {', '.join(HELP_TOPICS)}.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                raw_format = args.get("format", "json")
                if not isinstance(raw_format, str):
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "help_topic format must be a string.",
                            "details": {"format_type": type(raw_format).__name__},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Use format 'json' or 'text'.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )
                render_format = raw_format.strip().lower()
                if render_format not in {"json", "text"}:
                    return _err_payload(
                        {
                            "error_code": "RLLM_002",
                            "error_type": "MetadataValidationError",
                            "message": "help_topic format must be 'json' or 'text'.",
                            "details": {"format": raw_format},
                            "expected_schema": None,
                            "received_payload": arguments,
                            "recovery_hint": "Use format 'json' or 'text'.",
                            "doc_ref": "docs/errors.md#RLLM_002",
                        }
                    )

                if render_format == "json":
                    return _ok_payload(topic=topic, format="json", content=help_topics_json()[topic])
                return _ok_payload(topic=topic, format="text", content=help_topics_text()[topic])

            return _err_payload(
                {
                    "error_code": "RLLM_999",
                    "error_type": "UnknownUnhandledError",
                    "message": f"Unknown tool: {name}",
                    "details": {"tool": name},
                    "expected_schema": None,
                    "received_payload": arguments,
                    "recovery_hint": "Use list_programs, invoke_program, list_workflows, invoke_workflow, or help_topic.",
                    "doc_ref": "docs/errors.md#RLLM_999",
                }
            )
        except RunLLMError as exc:
            return _err_payload(exc.payload.to_dict())
        except Exception as exc:
            return _err_payload(
                {
                    "error_code": "RLLM_999",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "details": {"project": project},
                    "expected_schema": None,
                    "received_payload": arguments,
                    "recovery_hint": "Inspect server logs and retry with simpler input.",
                    "doc_ref": "docs/errors.md#RLLM_999",
                }
            )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run_mcp_server(
    project: str,
    repo_root: Path | None = None,
    *,
    autoload_config: bool | None = None,
    trusted_workflows: bool = False,
) -> None:
    asyncio.run(
        serve_mcp(
            project=project,
            repo_root=repo_root,
            autoload_config=autoload_config,
            trusted_workflows=trusted_workflows,
        )
    )
