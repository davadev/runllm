from __future__ import annotations

from runllm.cli import main
from runllm.config import reset_runtime_config_for_tests


def test_cli_returns_json_error_for_bad_config_yaml(tmp_path, monkeypatch, capsys) -> None:
    cfg_root = tmp_path / "config" / "runllm"
    cfg_root.mkdir(parents=True)
    (cfg_root / "config.yaml").write_text("runtime: [\n", encoding="utf-8")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["validate", "examples/summary.rllm"])
    out = capsys.readouterr().out

    assert code == 1
    assert '"error_code": "RLLM_999"' in out


def test_no_config_autoload_is_passed_to_run(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")
    reset_runtime_config_for_tests()

    captured: dict[str, object] = {}

    def fake_run_program(program_path, input_payload, options, **kwargs):
        captured["autoload_config"] = kwargs.get("autoload_config")
        return {"ok": True}

    monkeypatch.setattr("runllm.cli.run_program", fake_run_program)

    code = main(
        [
            "--no-config-autoload",
            "run",
            "examples/summary.rllm",
            "--input",
            '{"text":"hello"}',
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert '"ok": true' in out.lower()
    assert captured["autoload_config"] is False


def test_python_memory_limit_is_passed_to_run_options(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_program(program_path, input_payload, options, **kwargs):
        captured["python_memory_limit_mb"] = options.python_memory_limit_mb
        return {"ok": True}

    monkeypatch.setattr("runllm.cli.run_program", fake_run_program)

    code = main(
        [
            "run",
            "examples/summary.rllm",
            "--input",
            '{"text":"hello"}',
            "--python-memory-limit-mb",
            "512",
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert '"ok": true' in out.lower()
    assert captured["python_memory_limit_mb"] == 512


def test_help_works_even_with_bad_config_yaml(tmp_path, monkeypatch, capsys) -> None:
    cfg_root = tmp_path / "config" / "runllm"
    cfg_root.mkdir(parents=True)
    (cfg_root / "config.yaml").write_text("runtime: [\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    reset_runtime_config_for_tests()

    code = main(["help", "rllm"])
    out = capsys.readouterr().out

    assert code == 0
    assert '"topic": "rllm"' in out


def test_run_rejects_negative_max_retries(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {"called": False}

    def fake_run_program(program_path, input_payload, options, **kwargs):
        captured["called"] = True
        return {"ok": True}

    monkeypatch.setattr("runllm.cli.run_program", fake_run_program)

    code = main(
        [
            "run",
            "examples/summary.rllm",
            "--input",
            '{"text":"hello"}',
            "--max-retries",
            "-1",
        ]
    )
    out = capsys.readouterr().out

    assert code == 1
    assert '"error_code": "RLLM_002"' in out
    assert captured["called"] is False


def test_run_rejects_negative_python_memory_limit(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {"called": False}

    def fake_run_program(program_path, input_payload, options, **kwargs):
        captured["called"] = True
        return {"ok": True}

    monkeypatch.setattr("runllm.cli.run_program", fake_run_program)

    code = main(
        [
            "run",
            "examples/summary.rllm",
            "--input",
            '{"text":"hello"}',
            "--python-memory-limit-mb",
            "-1",
        ]
    )
    out = capsys.readouterr().out

    assert code == 1
    assert '"error_code": "RLLM_002"' in out
    assert captured["called"] is False


def test_no_config_autoload_is_passed_to_onboard_runs(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    responses = iter(
        [
            "purpose",
            "starter_app",
            "starter description",
            "tester",
            "text",
            "summary",
            "8000",
            "0",
            "",
            "",
            str(tmp_path / "starter.rllm"),
            "",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    captured: list[object] = []

    def fake_run_program(program_path, input_payload, options, **kwargs):
        captured.append(kwargs.get("autoload_config"))
        return {"ok": True, "message": "probe"}

    monkeypatch.setattr("runllm.onboarding.run_program", fake_run_program)

    code = main(["--no-config-autoload", "onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 0
    assert '"ok": true' in out.lower()
    assert len(captured) >= 2
    assert all(value is False for value in captured)
