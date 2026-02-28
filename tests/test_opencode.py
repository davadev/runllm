from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

from runllm.cli import main
from runllm.config import reset_runtime_config_for_tests


def _read_payload(out: str) -> dict[str, Any]:
    return json.loads(out)


def test_install_opencode_creates_builder_mcp_entry_and_agent(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    assert payload["ok"] is True
    assert payload["builder_mcp_name"] == "runllm"

    opencode_json = Path(payload["opencode_json"])
    assert opencode_json.exists()
    config_payload = json.loads(opencode_json.read_text(encoding="utf-8"))
    assert config_payload["mcp"]["runllm"]["type"] == "local"
    command = config_payload["mcp"]["runllm"]["command"]
    assert command[0] == "runllm"
    assert command[1:5] == ["mcp", "serve", "--project", "runllm"]
    assert "--repo-root" in command
    # Verify it pinned some absolute path
    repo_root_idx = command.index("--repo-root") + 1
    assert Path(command[repo_root_idx]).is_absolute()

    assert config_payload["mcp"]["runllm"]["enabled"] is True

    builder_agent_file = Path(payload["agent_file"])
    assert builder_agent_file.exists()
    text = builder_agent_file.read_text(encoding="utf-8")
    assert "mcp.runllm" in text
    assert "help_topic" in text
    assert "list_programs" in text
    assert "invoke_program" in text
    assert "bash: true" in text
    assert "bundled command" in text


def test_install_opencode_preserves_existing_builder_entry_without_force(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    opencode_root = tmp_path / "config" / "opencode"
    opencode_root.mkdir(parents=True)
    opencode_json = opencode_root / "opencode.json"
    opencode_json.write_text(
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "mcp": {
                    "runllm": {
                        "type": "local",
                        "command": ["custom-runllm", "mcp", "serve", "--project", "custom"],
                        "enabled": False,
                    }
                },
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    code = main(["mcp", "install-opencode"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    config_payload = json.loads(opencode_json.read_text(encoding="utf-8"))
    assert config_payload["mcp"]["runllm"]["command"] == ["custom-runllm", "mcp", "serve", "--project", "custom"]
    assert config_payload["mcp"]["runllm"]["enabled"] is False
    assert payload["mcp_updated"] is False


def test_install_opencode_force_overwrites_existing_builder_entry_and_agent(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    opencode_root = tmp_path / "config" / "opencode"
    (opencode_root / "agent").mkdir(parents=True)
    opencode_json = opencode_root / "opencode.json"
    opencode_json.write_text(
        json.dumps(
            {
                "mcp": {
                    "runllm": {
                        "type": "local",
                        "command": ["custom-runllm", "mcp", "serve", "--project", "custom"],
                        "enabled": False,
                    }
                }
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    agent_file = opencode_root / "agent" / "runllm-rllm-builder.md"
    agent_file.write_text("old agent", encoding="utf-8")

    code = main(["mcp", "install-opencode", "--force"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    config_payload = json.loads(opencode_json.read_text(encoding="utf-8"))
    assert config_payload["mcp"]["runllm"]["command"] == ["runllm", "mcp", "serve", "--project", "runllm"]
    assert config_payload["mcp"]["runllm"]["enabled"] is True
    assert payload["mcp_updated"] is True
    assert payload["agent_updated"] is True
    assert "list_programs" in agent_file.read_text(encoding="utf-8")


def test_bundle_creates_executable_shim(tmp_path, monkeypatch, capsys) -> None:
    reset_runtime_config_for_tests()
    
    project_name = "jw_deep_research"
    userlib = tmp_path / "userlib"
    project_dir = userlib / project_name
    project_dir.mkdir(parents=True)
    staging_script = project_dir / f"{project_name}.py"
    staging_script.write_text("print('hello')", encoding="utf-8")
    
    bin_dir = tmp_path / "custom_bin"
    
    code = main([
        "bundle", 
        project_name, 
        "--repo-root", str(tmp_path),
        "--bin-dir", str(bin_dir)
    ])
    out = capsys.readouterr().out
    
    assert code == 0
    payload = _read_payload(out)
    assert payload["ok"] is True
    assert payload["project"] == project_name
    
    bundle_path = Path(payload["bundle_path"])
    assert bundle_path.exists()
    assert bundle_path.parent == bin_dir
    
    # Check content
    content = bundle_path.read_text(encoding="utf-8")
    assert "PYTHONPATH=" in content
    assert str(staging_script.resolve()) in content
    
    # Check executable bit
    assert (bundle_path.stat().st_mode & stat.S_IXUSR)


def test_bundle_rejects_missing_project(tmp_path, monkeypatch, capsys) -> None:
    reset_runtime_config_for_tests()
    code = main(["bundle", "missing", "--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"


def test_bundle_rejects_missing_staging_script(tmp_path, monkeypatch, capsys) -> None:
    reset_runtime_config_for_tests()
    project_name = "jw_deep_research"
    userlib = tmp_path / "userlib"
    project_dir = userlib / project_name
    project_dir.mkdir(parents=True)
    # No .py script
    
    code = main(["bundle", project_name, "--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"
