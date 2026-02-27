from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runllm.cli import main
from runllm.config import reset_runtime_config_for_tests


def _read_payload(out: str) -> dict[str, Any]:
    return json.loads(out)


def test_install_opencode_creates_mcp_entry_and_agent(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--project", "billing"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    assert payload["ok"] is True
    assert payload["project"] == "billing"
    assert payload["builder_mcp_name"] == "runllm"
    assert payload["mcp_name"] == "runllm-project"

    opencode_json = Path(payload["opencode_json"])
    assert opencode_json.exists()
    config_payload = json.loads(opencode_json.read_text(encoding="utf-8"))
    assert config_payload["mcp"]["runllm"]["type"] == "local"
    assert config_payload["mcp"]["runllm"]["command"] == [
        "runllm",
        "mcp",
        "serve",
        "--project",
        "runllm",
    ]
    assert config_payload["mcp"]["runllm"]["enabled"] is True
    assert config_payload["mcp"]["runllm-project"]["command"] == [
        "runllm",
        "mcp",
        "serve",
        "--project",
        "billing",
    ]
    assert config_payload["mcp"]["runllm-project"]["enabled"] is True

    builder_agent_file = Path(payload["agent_file"])
    assert builder_agent_file.exists()
    text = builder_agent_file.read_text(encoding="utf-8")
    assert "mcp.runllm" in text
    assert "help_topic" in text
    assert "list_programs" in text
    assert "invoke_program" in text
    assert "bash: true" in text
    assert "skill:" not in text

    project_agent_file = Path(payload["project_agent_file"])
    assert project_agent_file.exists()
    assert project_agent_file.name == "billing-agent.md"
    project_text = project_agent_file.read_text(encoding="utf-8")
    assert "mcp.runllm-project" in project_text
    assert "mcp.runllm: deny" in project_text
    assert "mcp.*: deny" not in project_text
    assert "read: true" in project_text
    assert "Use `mcp.runllm-project` first" in project_text


def test_install_opencode_project_agent_explicitly_denies_discovered_mcps(tmp_path, monkeypatch, capsys) -> None:
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
                    "external": {
                        "type": "local",
                        "command": ["external-mcp"],
                        "enabled": True,
                    }
                },
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    code = main(["mcp", "install-opencode", "--project", "billing"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    project_text = Path(payload["project_agent_file"]).read_text(encoding="utf-8")
    assert "mcp.external: deny" in project_text
    assert "mcp.runllm: deny" in project_text
    assert "mcp.runllm-project: allow" in project_text


def test_install_opencode_preserves_existing_entry_without_force(tmp_path, monkeypatch, capsys) -> None:
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

    code = main(["mcp", "install-opencode", "--project", "billing"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    config_payload = json.loads(opencode_json.read_text(encoding="utf-8"))
    assert config_payload["mcp"]["runllm"]["command"] == ["custom-runllm", "mcp", "serve", "--project", "custom"]
    assert config_payload["mcp"]["runllm"]["enabled"] is False
    assert config_payload["mcp"]["runllm-project"]["command"] == ["runllm", "mcp", "serve", "--project", "billing"]
    assert config_payload["mcp"]["runllm-project"]["enabled"] is True
    assert payload["mcp_updated"] is True


def test_install_opencode_force_overwrites_existing_entry_and_agent(tmp_path, monkeypatch, capsys) -> None:
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

    code = main(["mcp", "install-opencode", "--project", "billing", "--force"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    config_payload = json.loads(opencode_json.read_text(encoding="utf-8"))
    assert config_payload["mcp"]["runllm"]["command"] == ["runllm", "mcp", "serve", "--project", "runllm"]
    assert config_payload["mcp"]["runllm"]["enabled"] is True
    assert config_payload["mcp"]["runllm-project"]["command"] == ["runllm", "mcp", "serve", "--project", "billing"]
    assert config_payload["mcp"]["runllm-project"]["enabled"] is True
    assert payload["mcp_updated"] is True
    assert payload["agent_updated"] is True
    assert "list_programs" in agent_file.read_text(encoding="utf-8")
    project_agent_file = Path(payload["project_agent_file"])
    assert project_agent_file.exists()
    assert payload["project_agent_updated"] is True


def test_install_opencode_rejects_agent_file_path_traversal(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--agent-file", "../escape.md"])
    out = capsys.readouterr().out

    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"


def test_install_opencode_rejects_agent_file_absolute_path(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--agent-file", str(tmp_path / "outside.md")])
    out = capsys.readouterr().out

    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"


def test_install_opencode_rejects_agent_file_dot_segments(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--agent-file", ".."])
    out = capsys.readouterr().out

    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"

    code = main(["mcp", "install-opencode", "--agent-file", "."])
    out = capsys.readouterr().out

    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"


def test_install_opencode_empty_xdg_config_home_falls_back_to_home_config(tmp_path, monkeypatch, capsys) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--project", "billing"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    assert payload["opencode_json"] == str(home_dir / ".config" / "opencode" / "opencode.json")


def test_install_opencode_relative_xdg_config_home_falls_back_to_home_config(tmp_path, monkeypatch, capsys) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative-config")
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--project", "billing"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    assert payload["opencode_json"] == str(home_dir / ".config" / "opencode" / "opencode.json")


def test_install_opencode_rejects_unsafe_mcp_name_characters(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--mcp-name", "foo: bar"])
    out = capsys.readouterr().out

    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"


def test_install_opencode_rejects_unsafe_mcp_name_newline(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--mcp-name", "foo\nbar"])
    out = capsys.readouterr().out

    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"


def test_install_opencode_rejects_blank_runllm_bin(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--runllm-bin", "   "])
    out = capsys.readouterr().out

    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"


def test_install_opencode_rejects_blank_project_agent_file(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--project-agent-file", "   "])
    out = capsys.readouterr().out

    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"


def test_install_opencode_rejects_same_builder_and_project_agent_filenames(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(
        [
            "mcp",
            "install-opencode",
            "--agent-file",
            "shared.md",
            "--project-agent-file",
            "shared.md",
        ]
    )
    out = capsys.readouterr().out

    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"


def test_install_opencode_trims_runllm_bin_value(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--project", "billing", "--runllm-bin", "  runllm  "])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    config_payload = json.loads(Path(payload["opencode_json"]).read_text(encoding="utf-8"))
    assert config_payload["mcp"]["runllm"]["command"][0] == "runllm"
    assert config_payload["mcp"]["runllm-project"]["command"][0] == "runllm"


def test_install_opencode_can_enable_trusted_workflows_flag(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--project", "billing", "--trusted-workflows"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    config_payload = json.loads(Path(payload["opencode_json"]).read_text(encoding="utf-8"))
    assert "--trusted-workflows" in config_payload["mcp"]["runllm-project"]["command"]
    assert "--trusted-workflows" not in config_payload["mcp"]["runllm"]["command"]


def test_install_opencode_trusted_workflows_updates_existing_command_without_force(tmp_path, monkeypatch, capsys) -> None:
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
                    "runllm-project": {
                        "type": "local",
                        "command": ["runllm", "mcp", "serve", "--project", "billing"],
                        "enabled": True,
                    }
                },
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    code = main(["mcp", "install-opencode", "--project", "billing", "--trusted-workflows"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    config_payload = json.loads(opencode_json.read_text(encoding="utf-8"))
    assert "--trusted-workflows" in config_payload["mcp"]["runllm-project"]["command"]
    assert payload["mcp_updated"] is True


def test_install_opencode_rejects_project_mcp_name_runllm_for_non_runllm_project(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--project", "billing", "--mcp-name", "runllm"])
    out = capsys.readouterr().out

    assert code == 1
    payload = _read_payload(out)
    assert payload["error_code"] == "RLLM_002"


def test_install_opencode_allows_runllm_mcp_name_for_runllm_project_with_trusted_workflows(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(
        [
            "mcp",
            "install-opencode",
            "--project",
            "runllm",
            "--mcp-name",
            "runllm",
            "--trusted-workflows",
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    config_payload = json.loads(Path(payload["opencode_json"]).read_text(encoding="utf-8"))
    assert "--trusted-workflows" in config_payload["mcp"]["runllm"]["command"]


def test_install_opencode_can_customize_project_agent_filename(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(
        [
            "mcp",
            "install-opencode",
            "--project",
            "billing",
            "--mcp-name",
            "runllm-jw",
            "--project-agent-file",
            "jw-project-agent.md",
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    assert Path(payload["project_agent_file"]).name == "jw-project-agent.md"
    project_text = Path(payload["project_agent_file"]).read_text(encoding="utf-8")
    assert "mcp.runllm-jw" in project_text


def test_install_opencode_default_project_agent_filename_uses_project_name(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["mcp", "install-opencode", "--project", "jw_deep_research"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _read_payload(out)
    assert Path(payload["project_agent_file"]).name == "jw_deep_research-agent.md"
