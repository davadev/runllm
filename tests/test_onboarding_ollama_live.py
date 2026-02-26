from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from runllm.cli import main
from runllm.config import reset_runtime_config_for_tests


pytestmark = pytest.mark.skipif(
    os.environ.get("RUNLLM_OLLAMA_TESTS") != "1",
    reason="Set RUNLLM_OLLAMA_TESTS=1 to run live Ollama integration tests.",
)


def _ollama_model() -> str:
    return os.environ.get("RUNLLM_OLLAMA_MODEL", "llama3.1:8b")


@pytest.fixture(autouse=True)
def _reset_config_cache() -> None:
    reset_runtime_config_for_tests()


def test_onboard_live_ollama_end_to_end(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    model = _ollama_model()
    generated = tmp_path / "ollama_starter.rllm"

    responses = iter(
        [
            "Summarize short support ticket text",  # purpose
            "ollama_starter",  # app name
            "starter app for ollama",  # description
            "live_tester",  # author
            "text",  # input keys
            "summary",  # output keys
            "8000",  # max_context_window
            "0",  # temperature
            "",  # top_p
            "",  # format
            str(generated),  # output path
            "",  # approve draft
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    code = main(["onboard", "--model", f"ollama/{model}"])
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["provider"] == "ollama"
    assert payload["model"] == f"ollama/{model}"
    assert payload["scaffold_file"]
    assert Path(payload["scaffold_file"]).exists()

    assert generated.exists()
    text = generated.read_text(encoding="utf-8")
    assert "name: ollama_starter" in text
    assert f"model: ollama/{model}" in text

    sample_output = payload["sample_output"]
    assert isinstance(sample_output, dict)
    assert "summary" in sample_output
    assert isinstance(sample_output["summary"], str)
    assert len(sample_output["summary"].strip()) > 0
