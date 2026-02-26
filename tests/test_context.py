from pathlib import Path

import pytest

from runllm.errors import RunLLMError
from runllm.executor import run_program
from runllm.models import RunOptions


def _fake_completion(**kwargs):
    raise AssertionError("Should not call model when context exceeds")


def test_context_exceeded(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    app_text = """---
name: tiny
description: tiny
version: 0.1.0
author: test
max_context_window: 10
input_schema:
  type: object
  properties:
    text: {type: string}
  required: [text]
  additionalProperties: false
output_schema:
  type: object
  properties:
    out: {type: string}
  required: [out]
  additionalProperties: false
llm:
  model: openai/gpt-4o-mini
llm_params: {}
---
{{input.text}}
"""
    path = Path(tmp_path) / "tiny.rllm"
    path.write_text(app_text, encoding="utf-8")

    with pytest.raises(RunLLMError) as exc:
        run_program(path, {"text": "x" * 400}, RunOptions(), completion_fn=_fake_completion)

    assert exc.value.payload.error_code == "RLLM_012"
