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


def test_openai_json_format_translation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    
    app_text = """---
name: json_test
description: test
version: 0.1.0
author: test
max_context_window: 8000
input_schema: {type: object}
output_schema: {type: object}
llm:
  model: openai/gpt-4o
llm_params:
  format: json
---
Return JSON.
"""
    app = tmp_path / "json_test.rllm"
    app.write_text(app_text, encoding="utf-8")
    
    fake = FakeCompletion(['{}'])
    run_program(app, {}, RunOptions(max_retries=0), completion_fn=fake)
    
    # Verify the call to litellm included response_format
    last_call = fake.calls[0]
    assert last_call["model"] == "openai/gpt-4o"
    assert last_call["response_format"] == {"type": "json_object"}
    # Verify original format remains (LiteLLM usually ignores it for OpenAI but keeps it for Ollama)
    assert last_call["format"] == "json"


def test_ollama_json_format_preservation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    app_text = """---
name: ollama_json
description: test
version: 0.1.0
author: test
max_context_window: 8000
input_schema: {type: object}
output_schema: {type: object}
llm:
  model: ollama/llama3
llm_params:
  format: json
---
Return JSON.
"""
    app = tmp_path / "ollama_json.rllm"
    app.write_text(app_text, encoding="utf-8")
    
    fake = FakeCompletion(['{}'])
    
    # Mock ensure_ollama_model to avoid subprocess calls
    import runllm.executor
    monkeypatch.setattr(runllm.executor, "ensure_ollama_model", lambda *a, **kw: None)
    
    run_program(app, {}, RunOptions(max_retries=0), completion_fn=fake)
    
    last_call = fake.calls[0]
    assert last_call["model"] == "ollama/llama3"
    # Ollama should NOT have response_format injected
    assert "response_format" not in last_call
    assert last_call["format"] == "json"

