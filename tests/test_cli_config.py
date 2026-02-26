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
