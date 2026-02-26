from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runllm.cli import main
from runllm.config import reset_runtime_config_for_tests
from runllm.errors import make_error
from runllm.onboarding import _onboarding_app_path


def _set_input_responses(monkeypatch, responses: list[str]) -> None:
    iterator = iter(responses)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(iterator))


def _parse_json_payload(output: str) -> dict[str, Any]:
    start = output.find("{")
    assert start >= 0
    return json.loads(output[start:])


def test_onboard_generates_app_file(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    generated = tmp_path / "starter.rllm"
    _set_input_responses(
        monkeypatch,
        [
            "summarize support tickets",  # purpose
            "starter_app",  # app name
            "starter description",  # description
            "tester",  # author
            "text",  # input keys
            "summary",  # output keys
            "8000",  # max_context_window
            "0",  # temperature
            "",  # top_p
            "",  # format
            str(generated),  # output path
            "",  # approve draft
        ],
    )
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 0
    json.loads(out)
    payload = _parse_json_payload(out)
    assert payload["ok"] is True
    assert generated.exists()
    scaffold_path = Path(payload["scaffold_file"])
    assert scaffold_path.exists()
    scaffold_payload = json.loads(scaffold_path.read_text(encoding="utf-8"))
    assert scaffold_payload["app_name"] == "starter_app"
    assert scaffold_payload["purpose"]
    assert scaffold_payload["llm_params"]["format"] == "json"
    text = generated.read_text(encoding="utf-8")
    assert "name: starter_app" in text
    assert "model: openai/gpt-4o-mini" in text


def test_onboard_missing_credential_can_abort(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_runtime_config_for_tests()

    _set_input_responses(
        monkeypatch,
        [
            "n",  # do not set credential now
        ],
    )

    code = main(["onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 1
    assert '"error_code": "RLLM_014"' in out


def test_onboard_credential_session_only_continues(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_runtime_config_for_tests()

    _set_input_responses(
        monkeypatch,
        [
            "y",  # set credential now
            "",  # env path default (.env)
            "n",  # do not write to file
            "summarize support tickets",
            "session_only_app",
            "session only",
            "tester",
            "text",
            "summary",
            "8000",
            "0",
            "",
            "",
            str(tmp_path / "session_only_app.rllm"),
            "",
        ],
    )
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "sk-session-only-key")
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _parse_json_payload(out)
    assert payload["credential_written"] is False
    assert payload["credential_path"] is None
    assert '"ok": true' in out.lower()
    assert not (tmp_path / ".env").exists()


def test_onboard_reports_google_for_gemini_models(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    _set_input_responses(
        monkeypatch,
        [
            "summarize support tickets",
            "gemini_app",
            "gemini app",
            "tester",
            "text",
            "summary",
            "8000",
            "0",
            "",
            "",
            str(tmp_path / "gemini_app.rllm"),
            "",
        ],
    )
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--model", "gemini/gemini-1.5-flash"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _parse_json_payload(out)
    assert payload["provider"] == "google"


def test_onboard_credential_path_expands_user_home(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_runtime_config_for_tests()

    _set_input_responses(
        monkeypatch,
        [
            "y",  # set credential now
            "~/.runllm-onboard.env",  # env path
            "y",  # confirm file write
            "summarize support tickets",
            "expanduser_app",
            "expanduser app",
            "tester",
            "text",
            "summary",
            "8000",
            "0",
            "",
            "",
            str(tmp_path / "expanduser_app.rllm"),
            "",
        ],
    )
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "sk-home-write-key")
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _parse_json_payload(out)
    assert payload["credential_written"] is True
    env_path = home_dir / ".runllm-onboard.env"
    assert env_path.exists()


def test_onboard_next_steps_quote_paths_with_spaces(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    generated = tmp_path / "My Apps" / "starter app.rllm"
    _set_input_responses(
        monkeypatch,
        [
            "summarize support tickets",
            "starter_app",
            "starter description",
            "tester",
            "text",
            "summary",
            "8000",
            "0",
            "",
            "",
            str(generated),
            "",
        ],
    )
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _parse_json_payload(out)
    assert payload["next_steps"][0].startswith("runllm inspect '")
    assert "starter app.rllm'" in payload["next_steps"][0]


def test_onboard_resume_uses_saved_defaults(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    session_path = tmp_path / ".runllm" / "onboarding-session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    saved_output = tmp_path / "resume_app.rllm"
    session_path.write_text(
        json.dumps(
            {
                "initial_goal": "summarize messages",
                "app_name": "resume_app",
                "description": "resume app",
                "author": "tester",
                "input_keys": ["text"],
                "output_keys": ["summary"],
                "max_context_window": 8000,
                "temperature": 0,
                "output_path": str(saved_output),
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    responses = iter(["", "", "", "", "", "", "", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--resume", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _parse_json_payload(out)
    assert payload["ok"] is True
    assert saved_output.exists()


def test_onboard_invalid_numeric_input_returns_structured_error(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    responses = iter(
        [
            "summarize support tickets",
            "starter_app",
            "starter description",
            "tester",
            "text",
            "summary",
            "not-an-int",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 1
    assert '"error_code": "RLLM_002"' in out


def test_onboard_non_interactive_input_returns_structured_error(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    def _raise_eof(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 1
    assert '"error_code": "RLLM_011"' in out


def test_onboard_credential_guidance_fallback_has_setup_step(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_runtime_config_for_tests()

    responses = iter(
        [
            "y",  # set credential now
            "",  # .env path default
            "n",  # do not write to disk
            "summarize support tickets",
            "fallback_app",
            "fallback description",
            "tester",
            "text",
            "summary",
            "8000",
            "0",
            "",
            "",
            str(tmp_path / "fallback_app.rllm"),
            "",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "sk-session-only-key")

    def fake_run_program(program_path, input_payload, options, **kwargs):
        name = str(program_path)
        if "credential_check.rllm" in name:
            raise make_error(
                error_code="RLLM_013",
                error_type="RetryExhaustedError",
                message="simulated step failure",
                details={"step": "credential_check"},
                recovery_hint="retry",
                doc_ref="docs/errors.md#RLLM_013",
            )
        return {"summary": "ok", "message": "ok", "ok": True}

    monkeypatch.setattr("runllm.onboarding.run_program", fake_run_program)

    code = main(["onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _parse_json_payload(out)
    guidance = payload["credential_guidance"]
    assert isinstance(guidance.get("setup_steps"), list)
    assert len(guidance["setup_steps"]) >= 1


def test_onboarding_app_path_ignores_cwd_examples(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fake = tmp_path / "examples" / "onboarding" / "app_goal_capture.rllm"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text("invalid", encoding="utf-8")

    selected = _onboarding_app_path("app_goal_capture", tmp_path)

    assert selected != fake.resolve()
    assert selected.name == "app_goal_capture.rllm"


def test_onboard_scaffold_file_override(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    generated = tmp_path / "scaffold_override.rllm"
    custom_scaffold = tmp_path / "profiles" / "starter-profile.json"
    _set_input_responses(
        monkeypatch,
        [
            "summarize support tickets",
            "scaffold_override",
            "scaffold override",
            "tester",
            "text",
            "summary",
            "8000",
            "0",
            "",
            "",
            str(generated),
            "",
        ],
    )
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(
        [
            "onboard",
            "--model",
            "openai/gpt-4o-mini",
            "--scaffold-file",
            str(custom_scaffold),
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    payload = _parse_json_payload(out)
    assert payload["scaffold_file"] == str(custom_scaffold)
    assert custom_scaffold.exists()


def test_onboard_no_save_scaffold(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    generated = tmp_path / "no_scaffold.rllm"
    _set_input_responses(
        monkeypatch,
        [
            "summarize support tickets",
            "no_scaffold",
            "no scaffold",
            "tester",
            "text",
            "summary",
            "8000",
            "0",
            "",
            "",
            str(generated),
            "",
        ],
    )
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--model", "openai/gpt-4o-mini", "--no-save-scaffold"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _parse_json_payload(out)
    assert payload["scaffold_file"] is None
    assert not (tmp_path / ".runllm" / "scaffold-profile.json").exists()


def test_onboard_refinement_revise_output_updates_generated_file(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    generated = tmp_path / "revise_output.rllm"
    _set_input_responses(
        monkeypatch,
        [
            "summarize support tickets",
            "revise_output",
            "revise output",
            "tester",
            "text",
            "summary",
            "8000",
            "0",
            "",
            "",
            str(generated),
            "output",
            "summary,priority",
        ],
    )
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _parse_json_payload(out)
    assert payload["ok"] is True
    text = generated.read_text(encoding="utf-8")
    assert "priority:" in text
    assert "required:" in text


def test_onboard_extended_llm_params_written(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_runtime_config_for_tests()

    generated = tmp_path / "params_app.rllm"
    _set_input_responses(
        monkeypatch,
        [
            "summarize support tickets",
            "params_app",
            "params app",
            "tester",
            "text",
            "summary",
            "8000",
            "0.1",
            "0.7",
            "text",
            "y",
            str(generated),
            "",
        ],
    )
    monkeypatch.setattr("runllm.onboarding.run_program", lambda *args, **kwargs: {"summary": "ok"})

    code = main(["onboard", "--model", "openai/gpt-4o-mini"])
    out = capsys.readouterr().out

    assert code == 0
    payload = _parse_json_payload(out)
    scaffold_path = Path(payload["scaffold_file"])
    scaffold_payload = json.loads(scaffold_path.read_text(encoding="utf-8"))
    assert scaffold_payload["llm_params"]["temperature"] == 0.1
    assert scaffold_payload["llm_params"]["top_p"] == 0.7
    assert scaffold_payload["llm_params"]["format"] == "text"
    app_text = generated.read_text(encoding="utf-8")
    assert "top_p: 0.7" in app_text
    assert "format: text" in app_text
