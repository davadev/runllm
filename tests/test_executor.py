import os
from pathlib import Path
from types import SimpleNamespace

from runllm.executor import run_program
from runllm.models import RunOptions


class FakeCompletion:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._i = 0

    def __call__(self, **kwargs):
        content = self._responses[self._i]
        self._i += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=6, total_tokens=16),
        )


def test_retry_then_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = Path("examples/summary.rllm").resolve()
    fake = FakeCompletion(["not json", '{"summary":"ok"}'])
    out = run_program(
        app,
        {"text": "abc"},
        RunOptions(max_retries=2),
        completion_fn=fake,
    )
    assert out["summary"] == "ok"


def test_composition(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = Path("examples/compose_summary_keywords.rllm").resolve()
    fake = FakeCompletion(
        [
            '{"summary":"small"}',
            '{"keywords":["a","b"]}',
            '{"summary":"small","keywords":["a","b"]}',
        ]
    )
    out = run_program(app, {"text": "abc"}, RunOptions(max_retries=0), completion_fn=fake)
    assert out["summary"] == "small"
    assert out["keywords"] == ["a", "b"]
