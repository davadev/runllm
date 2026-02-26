from __future__ import annotations

import json

import pytest

from runllm.cli import main
from runllm.config import reset_runtime_config_for_tests


@pytest.fixture(autouse=True)
def _reset_config_cache() -> None:
    reset_runtime_config_for_tests()


def test_help_topic_rllm_text(capsys) -> None:
    code = main(["help", "rllm", "--format", "text"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Required frontmatter keys" in out
    assert "max_context_window" in out


def test_help_topic_defaults_to_json(capsys) -> None:
    code = main(["help", "rllm"])
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(out)
    assert payload["topic"] == "rllm"
    assert "required_fields" in payload["content"]


def test_help_topic_schema_json(capsys) -> None:
    code = main(["help", "schema", "--format", "json"])
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(out)
    assert payload["topic"] == "schema"
    assert "recommendations" in payload["content"]


def test_top_level_help_includes_help_command(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    out = capsys.readouterr().out

    assert exc.value.code == 0
    assert "help" in out
    assert "LLM authoring help" in out


def test_run_help_describes_key_flags(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["run", "--help"])
    out = capsys.readouterr().out

    assert exc.value.code == 0
    assert "--max-retries" in out
    assert "--trusted-python" in out
    assert "--python-memory-limit-mb" in out
    assert "--ollama-auto-pull" in out


def test_onboard_help_describes_resume_flags(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["onboard", "--help"])
    out = capsys.readouterr().out

    assert exc.value.code == 0
    assert "--resume" in out
    assert "--session-file" in out
    assert "--scaffold-file" in out
    assert "--no-save-scaffold" in out


def test_mcp_help_describes_project_scope(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["mcp", "serve", "--help"])
    out = capsys.readouterr().out

    assert exc.value.code == 0
    assert "list_programs" in out
    assert "--project" in out
