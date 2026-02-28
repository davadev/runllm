from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import yaml

from runllm.mcp_utils import (
    infer_project,
    matches_query,
    placeholder_for_schema,
)


USERLIB_DIR = "userlib"
RLLMLIB_DIR = "rllmlib"
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


def _workflow_id(project: str, path: Path, repo_root: Path) -> str:
    rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    return f"{project}:{rel}"


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
        template[key_name] = placeholder_for_schema(subschema)
    return template


def build_workflow_registry(repo_root: Path) -> list[WorkflowEntry]:
    entries: list[WorkflowEntry] = []
    # Workflows are expected in userlib/<project> or rllmlib
    for library in (USERLIB_DIR, RLLMLIB_DIR):
        base = repo_root / library
        if not base.exists() or not base.is_dir():
            continue
        for spec_path in sorted(base.rglob("workflow.yaml")):
            project = infer_project(spec_path, repo_root)
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
    cursor: int | None = None,
) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 100))
    start = 0
    if cursor is not None:
        start = max(cursor, 0)
    scoped_entries = [item for item in entries if item.project == project]
    cards = [item.card for item in scoped_entries if matches_query(item.card, query)]
    page = cards[start : start + safe_limit]
    next_cursor: int | None = None
    if start + safe_limit < len(cards):
        next_cursor = start + safe_limit
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
