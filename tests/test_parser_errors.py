from __future__ import annotations

from pathlib import Path

import pytest

from runllm.errors import RunLLMError
from runllm.parser import parse_rllm_file


def test_parse_requires_opening_frontmatter_delimiter(tmp_path: Path) -> None:
    app = tmp_path / "bad_opening.rllm"
    app.write_text("name: bad\n---\nhello\n", encoding="utf-8")

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_001"


def test_parse_requires_closing_frontmatter_delimiter(tmp_path: Path) -> None:
    app = tmp_path / "bad_closing.rllm"
    app.write_text(
        """---
name: bad
description: bad
version: 0.1.0
author: test
max_context_window: 100
input_schema: {}
output_schema: {}
llm: {model: openai/gpt-4o-mini}
llm_params: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_001"


def test_parse_invalid_yaml_frontmatter_raises(tmp_path: Path) -> None:
    app = tmp_path / "bad_yaml.rllm"
    app.write_text("---\nname: [\n---\nhello\n", encoding="utf-8")

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_001"


def test_parse_empty_prompt_body_raises(tmp_path: Path) -> None:
    app = tmp_path / "empty_prompt.rllm"
    app.write_text(
        """---
name: empty_prompt
description: empty_prompt
version: 0.1.0
author: test
max_context_window: 100
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
---
""",
        encoding="utf-8",
    )

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_001"


def test_parse_invalid_llm_params_key_raises(tmp_path: Path) -> None:
    app = tmp_path / "bad_llm_params.rllm"
    app.write_text(
        """---
name: bad_llm_params
description: bad_llm_params
version: 0.1.0
author: test
max_context_window: 100
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
llm_params:
  unknown_flag: true
---
Hello
""",
        encoding="utf-8",
    )

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_003"


def test_parse_uses_entry_requires_name_and_path(tmp_path: Path) -> None:
    app = tmp_path / "bad_uses_entry.rllm"
    app.write_text(
        """---
name: bad_uses_entry
description: bad_uses_entry
version: 0.1.0
author: test
max_context_window: 100
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
  - path: ./child.rllm
---
Hello
""",
        encoding="utf-8",
    )

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_008"
