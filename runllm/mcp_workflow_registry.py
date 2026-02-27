from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import yaml


USERLIB_DIR = "userlib"
RLLMLIB_DIR = "rllmlib"
MAX_ARRAY_TEMPLATE_ITEMS = 3
LOGGER = logging.getLogger(__name__)


@dataclass
class WorkflowEntry:
    id: str
    project: str
    path: Path
    card: dict[str, Any]
    entrypoint: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


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


def _workflow_id(project: str, path: Path, repo_root: Path) -> str:
    rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    return f"{project}:{rel}"


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
        out: dict[str, Any] = {}
        for key in required_keys:
            key_name = str(key)
            subschema = properties.get(key_name)
            if not isinstance(subschema, dict):
                subschema = {}
            out[key_name] = _placeholder_for_schema(subschema)
        return out
    return None


def _invocation_template(schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return {}
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    required = schema.get("required", [])
    required_keys = required if isinstance(required, list) else []
    template: dict[str, Any] = {}
    for key in required_keys:
        key_name = str(key)
        subschema = properties.get(key_name)
        if not isinstance(subschema, dict):
            subschema = {}
        template[key_name] = _placeholder_for_schema(subschema)
    return template


def build_workflow_registry(repo_root: Path) -> list[WorkflowEntry]:
    entries: list[WorkflowEntry] = []
    for library in (USERLIB_DIR, RLLMLIB_DIR):
        base = repo_root / library
        if not base.exists() or not base.is_dir():
            continue
        for spec_path in sorted(base.rglob("workflow.yaml")):
            project = _infer_project(spec_path, repo_root)
            if project is None:
                continue
            try:
                raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
            except Exception as exc:
                LOGGER.warning("Skipping invalid workflow spec: %s (%s)", spec_path, exc)
                continue
            if not isinstance(raw, dict):
                LOGGER.warning("Skipping workflow spec with non-object payload: %s", spec_path)
                continue

            name = raw.get("name")
            description = raw.get("description")
            entrypoint = raw.get("entrypoint")
            input_schema = raw.get("input_schema")
            output_schema = raw.get("output_schema")
            if not isinstance(name, str) or not name.strip():
                LOGGER.warning("Skipping workflow spec with invalid name: %s", spec_path)
                continue
            if not isinstance(description, str) or not description.strip():
                LOGGER.warning("Skipping workflow spec with invalid description: %s", spec_path)
                continue
            if not isinstance(entrypoint, str) or ":" not in entrypoint:
                LOGGER.warning("Skipping workflow spec with invalid entrypoint: %s", spec_path)
                continue
            if not isinstance(input_schema, dict) or not isinstance(output_schema, dict):
                LOGGER.warning("Skipping workflow spec with invalid schemas: %s", spec_path)
                continue

            workflow_id = _workflow_id(project, spec_path, repo_root)
            rel_path = spec_path.resolve().relative_to(repo_root.resolve()).as_posix()
            card = {
                "id": workflow_id,
                "name": name.strip(),
                "description": description.strip(),
                "project": project,
                "path": rel_path,
                "invocation_template": _invocation_template(input_schema),
            }
            entries.append(
                WorkflowEntry(
                    id=workflow_id,
                    project=project,
                    path=spec_path,
                    card=card,
                    entrypoint=entrypoint,
                    input_schema=input_schema,
                    output_schema=output_schema,
                )
            )
    entries.sort(key=lambda item: (item.card["name"], item.card["path"]))
    return entries


def list_workflows_from_entries(
    *,
    entries: list[WorkflowEntry],
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
        "workflows": page,
    }


def resolve_workflow_id_from_entries(*, entries: list[WorkflowEntry], project: str, workflow_id: str) -> WorkflowEntry | None:
    for entry in entries:
        if entry.project == project and entry.id == workflow_id:
            return entry
    return None
