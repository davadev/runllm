from pathlib import Path

import pytest

from runllm.errors import RunLLMError
from runllm.parser import parse_rllm_file


def test_parse_summary_example() -> None:
    p = Path("examples/summary.rllm").resolve()
    program = parse_rllm_file(p)
    assert program.name == "summary"
    assert "text" in program.input_schema["properties"]
    assert "summary" in program.output_schema["properties"]


def test_parse_requires_llm_model(tmp_path: Path) -> None:
    app_text = """---
name: bad_app
description: bad_app
version: 0.1.0
author: test
max_context_window: 1000
input_schema:
  type: object
  properties: {}
  additionalProperties: false
output_schema:
  type: object
  properties: {}
  additionalProperties: false
llm: {}
llm_params: {}
---
Hello
"""
    app = tmp_path / "bad_llm_model.rllm"
    app.write_text(app_text, encoding="utf-8")

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_002"


def test_parse_uses_with_must_be_object(tmp_path: Path) -> None:
    app_text = """---
name: bad_uses
description: bad_uses
version: 0.1.0
author: test
max_context_window: 1000
input_schema:
  type: object
  properties: {}
  additionalProperties: false
output_schema:
  type: object
  properties: {}
  additionalProperties: false
llm:
  model: openai/gpt-4o-mini
llm_params: {}
uses:
  - name: child
    path: ./child.rllm
    with: bad
---
Hello
"""
    app = tmp_path / "bad_uses_with.rllm"
    app.write_text(app_text, encoding="utf-8")

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_008"
