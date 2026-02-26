from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from runllm.models import RLLMProgram
from runllm.parser import parse_rllm_file


USERLIB_DIR = "userlib"
RLLMLIB_DIR = "rllmlib"
MAX_ARRAY_TEMPLATE_ITEMS = 3
LOGGER = logging.getLogger(__name__)


@dataclass
class ProgramEntry:
    id: str
    project: str
    path: Path
    card: dict[str, Any]


def _render_schema_type(schema: dict[str, Any]) -> str:
    raw_type = schema.get("type")
    if isinstance(raw_type, str):
        if raw_type == "array":
            items = schema.get("items")
            if isinstance(items, dict):
                return f"array<{_render_schema_type(items)}>"
            return "array<unknown>"
        return raw_type
    if isinstance(raw_type, list):
        return "|".join(str(t) for t in raw_type)
    if "enum" in schema:
        return "enum"
    return "unknown"


def _placeholder_for_schema(schema: dict[str, Any]) -> Any:
    if "const" in schema:
        return schema.get("const")
    if "enum" in schema:
        enum_values = schema.get("enum")
        if isinstance(enum_values, list) and enum_values:
            return enum_values[0]
        return None

    raw_type = schema.get("type")
    chosen: str | None = None
    if isinstance(raw_type, str):
        chosen = raw_type
    elif isinstance(raw_type, list):
        for candidate in raw_type:
            if candidate != "null":
                chosen = str(candidate)
                break
        if chosen is None and raw_type:
            chosen = str(raw_type[0])
    if chosen == "string":
        return "<string>"
    if chosen == "integer":
        return 0
    if chosen == "number":
        return 0.0
    if chosen == "boolean":
        return False
    if chosen == "array":
        items = schema.get("items")
        item_schema = items if isinstance(items, dict) else {}
        min_items_raw = schema.get("minItems", 0)
        min_items = min_items_raw if isinstance(min_items_raw, int) and min_items_raw > 0 else 0
        if min_items == 0:
            return []
        render_count = min(min_items, MAX_ARRAY_TEMPLATE_ITEMS)
        return [_placeholder_for_schema(item_schema) for _ in range(render_count)]
    if chosen == "object":
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        required = schema.get("required", [])
        required_keys = required if isinstance(required, list) else []
        result: dict[str, Any] = {}
        for key in required_keys:
            key_name = str(key)
            subschema = properties.get(key_name)
            if not isinstance(subschema, dict):
                subschema = {}
            result[key_name] = _placeholder_for_schema(subschema)
        return result
    return None


def _schema_fields(schema: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(schema, dict):
        return [], [], {}
    if schema.get("type") != "object":
        field = {
            "name": "value",
            "type": _render_schema_type(schema),
            "required": True,
        }
        return [field], [], {}

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    required = set(schema.get("required", [])) if isinstance(schema.get("required", []), list) else set()

    required_fields: list[dict[str, Any]] = []
    optional_fields: list[dict[str, Any]] = []
    invocation_template: dict[str, Any] = {}

    for key in sorted(properties.keys()):
        subschema = properties.get(key)
        if not isinstance(subschema, dict):
            subschema = {}
        row = {
            "name": key,
            "type": _render_schema_type(subschema),
            "required": key in required,
        }
        if key in required:
            required_fields.append(row)
            invocation_template[key] = _placeholder_for_schema(subschema)
        else:
            optional_fields.append(row)

    return required_fields, optional_fields, invocation_template


def _infer_project(path: Path, repo_root: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 2:
        return None
    if parts[0] == USERLIB_DIR:
        if len(parts) < 3:
            return None
        return parts[1]
    if parts[0] == RLLMLIB_DIR:
        return RLLMLIB_DIR
    return None


def _program_id(project: str, path: Path, repo_root: Path) -> str:
    rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    return f"{project}:{rel}"


def _card_from_program(program: RLLMProgram, project: str, repo_root: Path) -> dict[str, Any]:
    input_required, input_optional, invocation_template = _schema_fields(program.input_schema)
    output_required, output_optional, _ = _schema_fields(program.output_schema)
    returns = output_required + output_optional
    rel_path = program.path.resolve().relative_to(repo_root.resolve()).as_posix()
    return {
        "id": _program_id(project, program.path, repo_root),
        "name": program.name,
        "description": program.description,
        "project": project,
        "path": rel_path,
        "input_required": input_required,
        "input_optional": input_optional,
        "returns": returns,
        "invocation_template": invocation_template,
    }


def _matches_query(card: dict[str, Any], query: str | None) -> bool:
    if query is None:
        return True
    q = query.strip().lower()
    if not q:
        return True
    haystack = " ".join(
        [
            str(card.get("name", "")),
            str(card.get("description", "")),
            str(card.get("project", "")),
        ]
    ).lower()
    return q in haystack


def build_registry(repo_root: Path) -> list[ProgramEntry]:
    entries: list[ProgramEntry] = []
    for library in (USERLIB_DIR, RLLMLIB_DIR):
        base = repo_root / library
        if not base.exists() or not base.is_dir():
            continue
        for app_path in sorted(base.rglob("*.rllm")):
            project = _infer_project(app_path, repo_root)
            if project is None:
                continue
            try:
                program = parse_rllm_file(app_path)
            except Exception as exc:
                LOGGER.warning("Skipping invalid .rllm file during MCP registry build: %s (%s)", app_path, exc)
                continue
            card = _card_from_program(program, project, repo_root)
            entries.append(
                ProgramEntry(
                    id=card["id"],
                    project=project,
                    path=app_path,
                    card=card,
                )
            )
    entries.sort(key=lambda item: (item.card["name"], item.card["path"]))
    return entries


def list_programs_for_project(
    repo_root: Path,
    project: str,
    *,
    query: str | None = None,
    limit: int = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    return list_programs_from_entries(
        entries=build_registry(repo_root),
        project=project,
        query=query,
        limit=limit,
        cursor=cursor,
    )


def list_programs_from_entries(
    *,
    entries: list[ProgramEntry],
    project: str,
    query: str | None = None,
    limit: int = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 100))
    start = 0
    if cursor is not None:
        try:
            start = max(int(cursor), 0)
        except (TypeError, ValueError):
            start = 0
    scoped_entries = [item for item in entries if item.project == project]
    cards = [item.card for item in scoped_entries if _matches_query(item.card, query)]
    page = cards[start : start + safe_limit]
    next_cursor: str | None = None
    if start + safe_limit < len(cards):
        next_cursor = str(start + safe_limit)
    return {
        "project": project,
        "count": len(page),
        "total": len(cards),
        "next_cursor": next_cursor,
        "programs": page,
    }


def resolve_program_id(repo_root: Path, project: str, program_id: str) -> Path | None:
    return resolve_program_id_from_entries(entries=build_registry(repo_root), project=project, program_id=program_id)


def resolve_program_id_from_entries(*, entries: list[ProgramEntry], project: str, program_id: str) -> Path | None:
    for entry in entries:
        if entry.project == project and entry.id == program_id:
            return entry.path
    return None
