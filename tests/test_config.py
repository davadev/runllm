from __future__ import annotations

import os
from pathlib import Path

import pytest

from runllm.config import load_runtime_config, reset_runtime_config_for_tests
from runllm.errors import RunLLMError
from runllm.executor import run_program
from runllm.models import RunOptions


@pytest.fixture(autouse=True)
def _reset_config() -> None:
    reset_runtime_config_for_tests()


def test_autoload_reads_cwd_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from-cwd\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    cfg = load_runtime_config(autoload=True)

    assert "OPENAI_API_KEY" in os.environ
    assert os.environ["OPENAI_API_KEY"] == "from-cwd"
    assert any(str(tmp_path / ".env") == src for src in (cfg.loaded_sources or []))


def test_process_env_has_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from-cwd\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "from-process")

    load_runtime_config(autoload=True)

    assert os.environ["OPENAI_API_KEY"] == "from-process"


def test_autoload_does_not_create_config_dir_on_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_home = tmp_path / "cfg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg_home))
    monkeypatch.chdir(tmp_path)

    load_runtime_config(autoload=True)

    assert not (cfg_home / "runllm").exists()


def test_cache_reloads_when_cwd_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / ".env").write_text("OPENAI_API_KEY=first-key\n", encoding="utf-8")
    (second / ".env").write_text("OPENAI_API_KEY=second-key\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    monkeypatch.chdir(first)
    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "first-key"

    monkeypatch.chdir(second)
    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "second-key"


def test_cache_reloads_when_xdg_config_home_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    cfg_a = tmp_path / "cfg_a" / "runllm"
    cfg_b = tmp_path / "cfg_b" / "runllm"
    cfg_a.mkdir(parents=True)
    cfg_b.mkdir(parents=True)
    (cfg_a / ".env").write_text("OPENAI_API_KEY=from-a\n", encoding="utf-8")
    (cfg_b / ".env").write_text("OPENAI_API_KEY=from-b\n", encoding="utf-8")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg_a"))
    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "from-a"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg_b"))
    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "from-b"


def test_autoload_false_clears_previously_injected_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "from-dotenv"

    load_runtime_config(autoload=False)
    assert "OPENAI_API_KEY" not in os.environ


def test_cache_reloads_when_env_file_contents_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=first\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "first"

    env_path.write_text("OPENAI_API_KEY=second\n", encoding="utf-8")
    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "second"


def test_process_override_after_injection_is_preserved_on_reload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=dotenv-value\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "dotenv-value"

    os.environ["OPENAI_API_KEY"] = "process-override"
    env_path.write_text("OPENAI_API_KEY=new-dotenv\n", encoding="utf-8")
    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "process-override"


def test_autoload_false_does_not_delete_process_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-value\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "dotenv-value"

    os.environ["OPENAI_API_KEY"] = "process-override"
    load_runtime_config(autoload=False)
    assert os.environ["OPENAI_API_KEY"] == "process-override"


def test_reload_reconciles_after_process_override_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "from-dotenv"

    os.environ["OPENAI_API_KEY"] = "from-process"
    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "from-process"

    del os.environ["OPENAI_API_KEY"]
    load_runtime_config(autoload=True)
    assert os.environ["OPENAI_API_KEY"] == "from-dotenv"


def test_missing_provider_key_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = Path("examples/summary.rllm").resolve()

    with pytest.raises(RunLLMError) as exc:
        run_program(app, {"text": "abc"}, RunOptions(max_retries=0), completion_fn=lambda **kwargs: None)

    assert exc.value.payload.error_code == "RLLM_014"
