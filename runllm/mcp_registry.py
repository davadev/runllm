from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from runllm.mcp_utils import (
    get_schema_fields,
    infer_project,
    matches_query,
    placeholder_for_schema,
)
from runllm.models import RLLMProgram
from runllm.parser import parse_rllm_file


USERLIB_DIR = "userlib"
RLLMLIB_DIR = "rllmlib"
LOGGER = logging.getLogger(__name__)


@dataclass
class ProgramEntry:
    id: str
    project: str
    path: Path
    card: dict[str, Any]


def _program_id(project: str, path: Path, repo_root: Path) -> str:
    rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    return f"{project}:{rel}"


def _card_from_program(program: RLLMProgram, project: str, repo_root: Path) -> dict[str, Any]:
    input_required, input_optional, invocation_template = get_schema_fields(program.input_schema)
    output_required, output_optional, _ = get_schema_fields(program.output_schema)
    returns = output_required + output_optional
    rel_path = program.path.resolve().relative_to(repo_root.resolve()).as_posix()
    card = {
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
    if program.tags:
        card["tags"] = program.tags
    if "suggestions" in program.metadata:
        card["suggestions"] = program.metadata["suggestions"]
    return card


def build_registry(repo_root: Path) -> list[ProgramEntry]:
    entries: list[ProgramEntry] = []
    # Search in library dirs and examples/onboarding for runllm project scope
    search_dirs = [USERLIB_DIR, RLLMLIB_DIR, "examples"]
    for library in search_dirs:
        base = repo_root / library
        if not base.exists() or not base.is_dir():
            continue
        for app_path in sorted(base.rglob("*.rllm")):
            project = infer_project(app_path, repo_root)
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
    cursor: int | None = None,
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
        "programs": page,
    }


def resolve_program_id(repo_root: Path, project: str, program_id: str) -> Path | None:
    return resolve_program_id_from_entries(entries=build_registry(repo_root), project=project, program_id=program_id)


def resolve_program_id_from_entries(*, entries: list[ProgramEntry], project: str, program_id: str) -> Path | None:
    for entry in entries:
        if entry.project == project and entry.id == program_id:
            return entry.path
    return None
