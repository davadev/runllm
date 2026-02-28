from __future__ import annotations

import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

from runllm.errors import make_error


_SAFE_MCP_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


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

# Execution Rules
- To run a project (for example `jw_deep_research`), use the bundled command or `runllm run`.
- Do not expect project-level MCP tools for research execution.

# MCP Rules
- Do not invent program ids; get ids from `list_programs`.
- Use `help_topic` when you need canonical runllm guidance.
"""


def _upsert_mcp_entry(
    *,
    mcp_payload: dict[str, Any],
    mcp_key: str,
    command: list[str],
    force: bool,
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
    
    if merged_entry != existing_entry:
        mcp_payload[mcp_key] = merged_entry
        changed = True
    return changed


def install_opencode_integration(
    *,
    repo_root: str | None = None,
    runllm_bin: str = "runllm",
    agent_file: str = "runllm-rllm-builder.md",
    force: bool = False,
) -> dict[str, Any]:
    repo_root_value: str | None = None
    if repo_root is not None:
        repo_root_text = str(repo_root).strip()
        if not repo_root_text:
            raise make_error(
                error_code="RLLM_002",
                error_type="MetadataValidationError",
                message="repo_root must be a non-empty string when provided.",
                details={"repo_root": repo_root},
                recovery_hint="Pass --repo-root with a valid path or omit it.",
                doc_ref="docs/errors.md#RLLM_002",
            )
        repo_root_value = str(Path(repo_root_text).resolve())

    runllm_bin_value = _validated_runllm_bin(runllm_bin)
    builder_mcp_key = "runllm"

    agent_filename = _validated_agent_filename(agent_file)

    # Pin the repo root into the command array to ensure deterministic app discovery
    # when the MCP server is launched from an external agent (like opencode).
    repo_root_to_pin = repo_root_value or str(Path.cwd().resolve())

    builder_command = [
        runllm_bin_value,
        "mcp",
        "serve",
        "--project",
        "runllm",
        "--repo-root",
        repo_root_to_pin,
    ]

    opencode_root = _opencode_root()
    config_path = opencode_root / "opencode.json"
    builder_agent_path = opencode_root / "agent" / agent_filename

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

    return {
        "ok": True,
        "builder_mcp_name": builder_mcp_key,
        "opencode_json": str(config_path),
        "agent_file": str(builder_agent_path),
        "mcp_updated": config_changed,
        "agent_updated": builder_agent_changed,
        "force": force,
    }


def bundle_project(
    project_name: str,
    *,
    repo_root: str | None = None,
    bin_dir: str | None = None,
) -> dict[str, Any]:
    project = project_name.strip()
    if not project:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="project name must be provided.",
            recovery_hint="Pass project name as the first argument to bundle.",
            doc_ref="docs/errors.md#RLLM_002",
        )

    resolved_root = Path(repo_root or os.getcwd()).resolve()
    userlib = resolved_root / "userlib"
    project_dir = userlib / project
    
    if not project_dir.exists() or not project_dir.is_dir():
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message=f"Project directory not found: {project_dir}",
            details={"project": project, "path": str(project_dir)},
            recovery_hint=f"Ensure the project exists under {userlib}.",
            doc_ref="docs/errors.md#RLLM_002",
        )

    staging_script = project_dir / f"{project}.py"
    if not staging_script.exists():
        # Fallback to common entry points
        for fallback in ["main.py", "run.py"]:
            candidate = project_dir / fallback
            if candidate.exists():
                staging_script = candidate
                break
    
    if not staging_script.exists():
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message=f"Staging script not found in {project_dir}",
            details={"project": project, "path": str(project_dir)},
            recovery_hint=f"Ensure a python script named {project}.py, main.py, or run.py exists in the project directory.",
            doc_ref="docs/errors.md#RLLM_002",
        )

    # Determine where to place the bundle
    # If bin_dir is provided, use it. Otherwise, use a '.bin' folder in the repo root.
    if bin_dir:
        target_dir = Path(bin_dir).resolve()
    else:
        target_dir = resolved_root / ".bin"
    
    target_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = target_dir / project
    
    # Create the shim script
    python_exe = sys.executable
    content = f"""#!/bin/bash
export PYTHONPATH="{resolved_root}:$PYTHONPATH"
"{python_exe}" "{staging_script}" "$@"
"""
    bundle_path.write_text(content, encoding="utf-8")
    
    # Make it executable
    current_mode = bundle_path.stat().st_mode
    bundle_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return {
        "ok": True,
        "project": project,
        "bundle_path": str(bundle_path),
        "repo_root": str(resolved_root),
        "staging_script": str(staging_script),
    }
