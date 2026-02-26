from pathlib import Path

import pytest

from runllm.errors import RunLLMError
import runllm.parser as parser_module
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


def _app_with_runtime_compat(runllm_compat_block: str) -> str:
    return f"""---
name: compat_app
description: compat_app
version: 0.1.0
author: test
max_context_window: 1000
input_schema:
  type: object
  properties: {{}}
  additionalProperties: false
output_schema:
  type: object
  properties: {{}}
  additionalProperties: false
llm:
  model: openai/gpt-4o-mini
llm_params: {{}}
{runllm_compat_block}
---
Hello
"""


def test_parse_runllm_compat_within_range(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_text = _app_with_runtime_compat(
        """runllm_compat:
  min: 0.1.0
  max_exclusive: 0.2.0
"""
    )
    app = tmp_path / "compat_ok.rllm"
    app.write_text(app_text, encoding="utf-8")
    monkeypatch.setattr(parser_module, "_runtime_version_from_pyproject", lambda: None)
    monkeypatch.setattr(parser_module, "package_version", lambda _: "0.1.5")

    program = parse_rllm_file(app)

    assert program.name == "compat_app"


def test_parse_runllm_compat_fails_below_minimum(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_text = _app_with_runtime_compat(
        """runllm_compat:
  min: 0.2.0
"""
    )
    app = tmp_path / "compat_below_min.rllm"
    app.write_text(app_text, encoding="utf-8")
    monkeypatch.setattr(parser_module, "_runtime_version_from_pyproject", lambda: None)
    monkeypatch.setattr(parser_module, "package_version", lambda _: "0.1.9")

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_015"


def test_parse_runllm_compat_fails_at_max_exclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_text = _app_with_runtime_compat(
        """runllm_compat:
  min: 0.1.0
  max_exclusive: 0.2.0
"""
    )
    app = tmp_path / "compat_at_max.rllm"
    app.write_text(app_text, encoding="utf-8")
    monkeypatch.setattr(parser_module, "_runtime_version_from_pyproject", lambda: None)
    monkeypatch.setattr(parser_module, "package_version", lambda _: "0.2.0")

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_015"


def test_parse_runllm_compat_requires_object(tmp_path: Path) -> None:
    app_text = _app_with_runtime_compat("runllm_compat: bad\n")
    app = tmp_path / "compat_not_object.rllm"
    app.write_text(app_text, encoding="utf-8")

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_002"


def test_parse_runllm_compat_requires_semver_strings(tmp_path: Path) -> None:
    app_text = _app_with_runtime_compat(
        """runllm_compat:
  min: 0.1
"""
    )
    app = tmp_path / "compat_bad_semver.rllm"
    app.write_text(app_text, encoding="utf-8")

    with pytest.raises(RunLLMError) as exc:
        parse_rllm_file(app)

    assert exc.value.payload.error_code == "RLLM_002"


def test_parse_runllm_compat_accepts_prerelease_below_max_exclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_text = _app_with_runtime_compat(
        """runllm_compat:
  min: 0.1.0
  max_exclusive: 0.2.0
"""
    )
    app = tmp_path / "compat_prerelease_ok.rllm"
    app.write_text(app_text, encoding="utf-8")
    monkeypatch.setattr(parser_module, "_runtime_version_from_pyproject", lambda: None)
    monkeypatch.setattr(parser_module, "package_version", lambda _: "0.2.0rc1")

    program = parse_rllm_file(app)

    assert program.name == "compat_app"


def test_parse_runllm_compat_prefers_local_version_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_text = _app_with_runtime_compat(
        """runllm_compat:
  min: 0.1.0
  max_exclusive: 0.2.0
"""
    )
    app = tmp_path / "compat_local_source_preferred.rllm"
    app.write_text(app_text, encoding="utf-8")
    monkeypatch.setattr(parser_module, "_runtime_version_from_pyproject", lambda: "0.1.0")
    monkeypatch.setattr(parser_module, "package_version", lambda _: "9.9.9")

    program = parse_rllm_file(app)

    assert program.name == "compat_app"


def test_parse_runllm_compat_accepts_postrelease_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_text = _app_with_runtime_compat(
        """runllm_compat:
  min: 0.1.0
"""
    )
    app = tmp_path / "compat_postrelease_ok.rllm"
    app.write_text(app_text, encoding="utf-8")
    monkeypatch.setattr(parser_module, "_runtime_version_from_pyproject", lambda: None)
    monkeypatch.setattr(parser_module, "package_version", lambda _: "0.1.0.post1")

    program = parse_rllm_file(app)

    assert program.name == "compat_app"


def test_parse_runllm_compat_accepts_devrelease_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_text = _app_with_runtime_compat(
        """runllm_compat:
  min: 0.1.0
  max_exclusive: 0.2.0
"""
    )
    app = tmp_path / "compat_devrelease_ok.rllm"
    app.write_text(app_text, encoding="utf-8")
    monkeypatch.setattr(parser_module, "_runtime_version_from_pyproject", lambda: None)
    monkeypatch.setattr(parser_module, "package_version", lambda _: "0.2.0.dev1")

    program = parse_rllm_file(app)

    assert program.name == "compat_app"
