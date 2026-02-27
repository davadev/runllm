import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from runllm.errors import RunLLMError
from runllm.executor import run_program
from runllm.models import RunOptions
from runllm.stats import StatsStore


class FakeCompletion:
    def __init__(self, responses: list[object]) -> None:
        self._responses = responses
        self._i = 0
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
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


def test_first_attempt_includes_output_contract_block(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = Path("examples/summary.rllm").resolve()
    fake = FakeCompletion(['{"summary":"ok"}'])

    run_program(app, {"text": "abc"}, RunOptions(max_retries=0), completion_fn=fake)

    prompt = str(fake.calls[0]["messages"][0]["content"])
    assert "Output contract:" in prompt
    assert "Output schema (JSON):" in prompt
    assert "Example output (JSON):" in prompt


def test_retry_prompt_keeps_contract_and_includes_recovery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = Path("examples/summary.rllm").resolve()
    fake = FakeCompletion(["not json", '{"summary":"ok"}'])

    run_program(app, {"text": "abc"}, RunOptions(max_retries=1), completion_fn=fake)

    retry_prompt = str(fake.calls[1]["messages"][0]["content"])
    assert "Output contract:" in retry_prompt
    assert "Example output (JSON):" in retry_prompt
    assert "Recovery instruction:" in retry_prompt


def test_debug_prompt_file_contains_wrapped_and_raw_sections(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = Path("examples/summary.rllm").resolve()
    fake = FakeCompletion(['{"summary":"ok"}'])
    debug_file = tmp_path / "prompt_debug.txt"

    run_program(
        app,
        {"text": "abc"},
        RunOptions(max_retries=0, debug_prompt_file=str(debug_file), debug_prompt_wrap=80),
        completion_fn=fake,
    )

    content = debug_file.read_text(encoding="utf-8")
    assert "===== Attempt 1/1 =====" in content
    assert "----- Prompt (wrapped) -----" in content
    assert "----- Prompt (raw) -----" in content


def test_debug_prompt_stdout_writes_to_stderr_not_stdout(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = Path("examples/summary.rllm").resolve()
    fake = FakeCompletion(['{"summary":"ok"}'])

    run_program(
        app,
        {"text": "abc"},
        RunOptions(max_retries=0, debug_prompt_stdout=True),
        completion_fn=fake,
    )

    captured = capsys.readouterr()
    assert "===== Attempt 1/1 =====" in captured.err
    assert captured.out == ""


def test_debug_prompt_wrap_non_positive_raises_metadata_error_in_library_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = Path("examples/summary.rllm").resolve()
    fake = FakeCompletion(['{"summary":"ok"}'])

    with pytest.raises(RunLLMError) as exc:
        run_program(
            app,
            {"text": "abc"},
            RunOptions(max_retries=0, debug_prompt_stdout=True, debug_prompt_wrap=0),
            completion_fn=fake,
        )

    assert exc.value.payload.error_code == "RLLM_002"
    assert fake._i == 0
