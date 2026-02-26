from __future__ import annotations

from types import SimpleNamespace

import pytest

from runllm.errors import RunLLMError
from runllm.ollama import ensure_ollama_model, ollama_has_model


def test_ollama_has_model_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "runllm.ollama._run_ollama",
        lambda _cmd: SimpleNamespace(returncode=0, stdout="llama3.1:8b 1GB\n", stderr=""),
    )

    assert ollama_has_model("llama3.1:8b") is True


def test_ollama_has_model_false_on_failed_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "runllm.ollama._run_ollama",
        lambda _cmd: SimpleNamespace(returncode=1, stdout="", stderr="failed"),
    )

    assert ollama_has_model("llama3.1:8b") is False


def test_ensure_ollama_model_missing_without_auto_pull_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("runllm.ollama.ollama_has_model", lambda _model: False)

    with pytest.raises(RunLLMError) as exc:
        ensure_ollama_model("llama3.1:8b", auto_pull=False)

    assert exc.value.payload.error_code == "RLLM_010"


def test_ensure_ollama_model_pull_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("runllm.ollama.ollama_has_model", lambda _model: False)
    monkeypatch.setattr(
        "runllm.ollama._run_ollama",
        lambda _cmd: SimpleNamespace(returncode=1, stdout="", stderr="pull failed"),
    )

    with pytest.raises(RunLLMError) as exc:
        ensure_ollama_model("llama3.1:8b", auto_pull=True)

    assert exc.value.payload.error_code == "RLLM_010"
    assert "pull failed" in exc.value.payload.details["stderr"]


def test_ensure_ollama_model_skips_pull_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"pull": False}
    monkeypatch.setattr("runllm.ollama.ollama_has_model", lambda _model: True)

    def _should_not_run(_cmd):
        called["pull"] = True
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("runllm.ollama._run_ollama", _should_not_run)
    ensure_ollama_model("llama3.1:8b", auto_pull=True)
    assert called["pull"] is False
