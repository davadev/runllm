import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from runllm.errors import RunLLMError
from runllm.executor import run_program
from runllm.models import RunOptions
from runllm.stats import StatsStore


class FakeCompletion:
    def __init__(self, responses: list[object]) -> None:
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


def test_negative_max_retries_raises_metadata_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = Path("examples/summary.rllm").resolve()
    fake = FakeCompletion(['{"summary":"ok"}'])

    with pytest.raises(RunLLMError) as exc:
        run_program(app, {"text": "abc"}, RunOptions(max_retries=-1), completion_fn=fake)

    assert exc.value.payload.error_code == "RLLM_002"
    assert fake._i == 0


def test_python_post_error_is_not_retried(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app_text = """---
name: post_fail
description: post_fail
version: 0.1.0
author: test
max_context_window: 8000
input_schema:
  type: object
  properties:
    text: {type: string}
  required: [text]
  additionalProperties: false
output_schema:
  type: object
  properties:
    summary: {type: string}
  required: [summary]
  additionalProperties: false
llm:
  model: openai/gpt-4o-mini
llm_params: {}
---
Return only JSON.
Input: {{input.text}}

```rllm-python post
raise RuntimeError("boom")
```
"""
    app = tmp_path / "post_fail.rllm"
    app.write_text(app_text, encoding="utf-8")
    fake = FakeCompletion(['{"summary":"ok"}'])

    with pytest.raises(RunLLMError) as exc:
        run_program(app, {"text": "abc"}, RunOptions(max_retries=3), completion_fn=fake)

    assert exc.value.payload.error_code == "RLLM_009"
    assert fake._i == 1
    model_stats = StatsStore().aggregate(app_path=str(app.resolve()), model="openai/gpt-4o-mini")
    assert model_stats["failure_count"] == 1


def test_non_string_provider_content_raises_execution_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = Path("examples/summary.rllm").resolve()
    fake = FakeCompletion([[{"type": "text", "text": "not a plain string"}]])

    with pytest.raises(RunLLMError) as exc:
        run_program(app, {"text": "abc"}, RunOptions(max_retries=0), completion_fn=fake)

    assert exc.value.payload.error_code == "RLLM_011"
