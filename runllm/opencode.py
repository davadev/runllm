from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from runllm.errors import make_error


_SAFE_MCP_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def _default_project_agent_filename(project_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", project_name.strip()).strip(".-")
    if not slug:
        slug = "project"
    return f"{slug}-agent.md"


def _opencode_root() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base: Path
    if isinstance(xdg_config_home, str) and xdg_config_home.strip():
        candidate = Path(xdg_config_home.strip()).expanduser()
        if candidate.is_absolute():
            base = candidate
        else:
            base = Path.home() / ".config"
    else:
        base = Path.home() / ".config"
    return base / "opencode"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise make_error(
            error_code="RLLM_011",
            error_type="ExecutionError",
            message="Failed to parse opencode.json; file is not valid JSON.",
            details={"path": str(path), "error": str(exc)},
            recovery_hint="Fix JSON syntax in opencode.json and retry installation.",
            doc_ref="docs/errors.md#RLLM_011",
        ) from exc
    if not isinstance(parsed, dict):
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="opencode.json must contain a top-level JSON object.",
            details={"path": str(path), "top_level_type": type(parsed).__name__},
            recovery_hint="Replace opencode.json with an object-based JSON document.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    return parsed


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _validated_agent_filename(agent_file: str) -> str:
    candidate = agent_file.strip()
    if not candidate:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="agent file must be a non-empty filename.",
            details={"agent_file": agent_file},
            recovery_hint="Pass --agent-file with a simple filename like runllm-rllm-builder.md.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    parsed = Path(candidate)
    if candidate in {".", ".."}:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="agent file must be a regular filename, not '.' or '..'.",
            details={"agent_file": agent_file},
            recovery_hint="Pass --agent-file with a simple filename like runllm-rllm-builder.md.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    if parsed.is_absolute() or parsed.name != candidate or "/" in candidate or "\\" in candidate:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="agent file must be a simple filename, not a path.",
            details={"agent_file": agent_file},
            recovery_hint="Pass --agent-file with only a filename (no directories).",
            doc_ref="docs/errors.md#RLLM_002",
        )
    return candidate


def _validated_mcp_name(mcp_name: str) -> str:
    candidate = mcp_name.strip()
    if not candidate:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="mcp name must be a non-empty string.",
            details={"mcp_name": mcp_name},
            recovery_hint="Pass --mcp-name with a non-empty value.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    if _SAFE_MCP_NAME.fullmatch(candidate) is None:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="mcp name must contain only letters, numbers, underscore, or dash.",
            details={"mcp_name": mcp_name},
            recovery_hint="Use --mcp-name matching pattern [A-Za-z0-9_-]+.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    return candidate


def _validated_runllm_bin(runllm_bin: str) -> str:
    candidate = runllm_bin.strip()
    if not candidate:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="runllm binary must be a non-empty command or path.",
            details={"runllm_bin": runllm_bin},
            recovery_hint="Pass --runllm-bin with a non-empty executable path or command.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    return candidate


def _render_builder_agent_content(mcp_name: str) -> str:
    return f"""---
description: runllm builder agent that scaffolds and validates .rllm apps
mode: primary
tools:
  mcp.{mcp_name}: true
  bash: true
  read: true
  write: true
  edit: true
  glob: true
  grep: true
  skill: true
  task: true
  todowrite: true
permission:
  mcp.{mcp_name}: allow
  bash: allow
  read: allow
  write: allow
  edit: allow
  glob: allow
  grep: allow
  skill: allow
  task: allow
  todowrite: allow
reasoning_effort: medium
temperature: 0.0
---

# Role
You are the execution-capable runllm app builder. Build valid `.rllm` apps end-to-end.

# Required Workflow
1. Call `help_topic` for `rllm`, `schema`, and `recovery` before scaffolding a new app.
2. Call `list_programs` to discover reusable scoped apps.
3. Create or update `.rllm` files.
4. Run `runllm validate <file.rllm>` and fix all failures.
5. Run `runllm run <file.rllm> --input '<json>'` with realistic sample input.
6. If needed, call `invoke_program` for reusable scoped app execution.

# App Quality Rules
- One atomic task per app.
- Strict `input_schema` and `output_schema` with explicit required keys.
- Set `additionalProperties: false` for strict contracts.
- Prompt and `<<<RECOVERY>>>` must enforce JSON object-only output.
- Prefer `llm_params.format: json` and low temperature for deterministic structure.

# MCP Rules
- Do not invent program ids; get ids from `list_programs`.
- Use `help_topic` when you need canonical runllm guidance.
"""


def _render_project_agent_content(mcp_name: str) -> str:
    return f"""---
description: project execution agent limited to one scoped runllm MCP
mode: primary
tools:
  mcp.{mcp_name}: true
  read: true
  write: true
  edit: true
  glob: true
  grep: true
permission:
  mcp.*: deny
  mcp.{mcp_name}: allow
  read: allow
  write: allow
  edit: allow
  glob: allow
  grep: allow
reasoning_effort: medium
temperature: 0.0
---

# Role
You are the project execution agent for one scoped MCP only.

# Rules
1. Use `mcp.{mcp_name}` first for project task completion.
2. Use `read`, `write`, `edit`, `glob`, and `grep` only when needed for local files.
3. Start MCP discovery via `list_programs` or `list_workflows`.
4. Use returned ids exactly as provided.
5. Call `invoke_program` or `invoke_workflow` with JSON object input.
6. Never assume hidden tools or cross-project MCP access.
"""


def _upsert_mcp_entry(
    *,
    mcp_payload: dict[str, Any],
    mcp_key: str,
    command: list[str],
    force: bool,
    trusted_workflows: bool,
) -> bool:
    desired_entry: dict[str, Any] = {
        "type": "local",
        "command": command,
        "enabled": True,
    }

    changed = False
    existing_entry = mcp_payload.get(mcp_key)
    if force or not isinstance(existing_entry, dict):
        if existing_entry != desired_entry:
            mcp_payload[mcp_key] = desired_entry
            changed = True
        return changed

    merged_entry = dict(existing_entry)
    for key, value in desired_entry.items():
        if key not in merged_entry:
            merged_entry[key] = value
    if trusted_workflows:
        existing_command = merged_entry.get("command")
        if isinstance(existing_command, list):
            if "--trusted-workflows" not in [str(item) for item in existing_command]:
                merged_entry["command"] = [*existing_command, "--trusted-workflows"]
        else:
            merged_entry["command"] = list(command)
    if merged_entry != existing_entry:
        mcp_payload[mcp_key] = merged_entry
        changed = True
    return changed


def install_opencode_integration(
    *,
    project: str,
    mcp_name: str = "runllm-project",
    runllm_bin: str = "runllm",
    agent_file: str = "runllm-rllm-builder.md",
    project_agent_file: str | None = None,
    force: bool = False,
    trusted_workflows: bool = False,
) -> dict[str, Any]:
    project_name = project.strip()
    if not project_name:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="project must be a non-empty string.",
            details={"project": project},
            recovery_hint="Pass --project with a non-empty value.",
            doc_ref="docs/errors.md#RLLM_002",
        )

    mcp_key = _validated_mcp_name(mcp_name)
    runllm_bin_value = _validated_runllm_bin(runllm_bin)
    builder_mcp_key = "runllm"

    agent_filename = _validated_agent_filename(agent_file)
    if project_agent_file is None:
        project_agent_filename = _validated_agent_filename(_default_project_agent_filename(project_name))
    else:
        project_agent_filename = _validated_agent_filename(project_agent_file)
    if project_agent_filename == agent_filename:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="builder and project agent files must be different filenames.",
            details={"agent_file": agent_filename, "project_agent_file": project_agent_filename},
            recovery_hint="Use distinct --agent-file and --project-agent-file values.",
            doc_ref="docs/errors.md#RLLM_002",
        )

    builder_command = [runllm_bin_value, "mcp", "serve", "--project", "runllm"]
    project_command = [runllm_bin_value, "mcp", "serve", "--project", project_name]
    if trusted_workflows:
        project_command.append("--trusted-workflows")

    if mcp_key == builder_mcp_key and project_name != "runllm":
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="project mcp name conflicts with reserved builder mcp name 'runllm'.",
            details={"mcp_name": mcp_key, "project": project_name},
            recovery_hint="Use --mcp-name with a value other than 'runllm' for project MCP scope.",
            doc_ref="docs/errors.md#RLLM_002",
        )

    opencode_root = _opencode_root()
    config_path = opencode_root / "opencode.json"
    builder_agent_path = opencode_root / "agent" / agent_filename
    project_agent_path = opencode_root / "agent" / project_agent_filename

    config_payload = _load_json_object(config_path)
    config_changed = False

    if "$schema" not in config_payload:
        config_payload["$schema"] = "https://opencode.ai/config.json"
        config_changed = True

    mcp_payload = config_payload.get("mcp")
    if mcp_payload is None:
        mcp_payload = {}
        config_payload["mcp"] = mcp_payload
        config_changed = True
    elif not isinstance(mcp_payload, dict):
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="opencode.json field 'mcp' must be an object.",
            details={"path": str(config_path), "field_type": type(mcp_payload).__name__},
            recovery_hint="Change mcp to an object mapping MCP names to server definitions.",
            doc_ref="docs/errors.md#RLLM_002",
        )

    if _upsert_mcp_entry(
        mcp_payload=mcp_payload,
        mcp_key=builder_mcp_key,
        command=builder_command,
        force=force,
        trusted_workflows=False,
    ):
        config_changed = True
    if _upsert_mcp_entry(
        mcp_payload=mcp_payload,
        mcp_key=mcp_key,
        command=project_command,
        force=force,
        trusted_workflows=trusted_workflows,
    ):
        config_changed = True

    if config_changed:
        _save_json(config_path, config_payload)

    builder_agent_text = _render_builder_agent_content(builder_mcp_key)
    builder_agent_changed = False
    if force or not builder_agent_path.exists():
        if not builder_agent_path.exists() or builder_agent_path.read_text(encoding="utf-8") != builder_agent_text:
            builder_agent_path.parent.mkdir(parents=True, exist_ok=True)
            builder_agent_path.write_text(builder_agent_text, encoding="utf-8")
            builder_agent_changed = True

    project_agent_text = _render_project_agent_content(mcp_key)
    project_agent_changed = False
    if force or not project_agent_path.exists():
        if not project_agent_path.exists() or project_agent_path.read_text(encoding="utf-8") != project_agent_text:
            project_agent_path.parent.mkdir(parents=True, exist_ok=True)
            project_agent_path.write_text(project_agent_text, encoding="utf-8")
            project_agent_changed = True

    return {
        "ok": True,
        "project": project_name,
        "mcp_name": mcp_key,
        "builder_mcp_name": builder_mcp_key,
        "opencode_json": str(config_path),
        "agent_file": str(builder_agent_path),
        "project_agent_file": str(project_agent_path),
        "mcp_updated": config_changed,
        "agent_updated": builder_agent_changed,
        "project_agent_updated": project_agent_changed,
        "force": force,
    }
