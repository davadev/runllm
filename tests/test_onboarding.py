from __future__ import annotations

import json
from typing import Any

from runllm.cli import main
from runllm.config import reset_runtime_config_for_tests
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
            str(generated),  # output path
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
            str(tmp_path / "session_only_app.rllm"),
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
            str(tmp_path / "gemini_app.rllm"),
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
            str(tmp_path / "expanduser_app.rllm"),
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
            str(generated),
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

    responses = iter(["", "", "", "", "", "", "", "", ""])
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


def test_onboarding_app_path_ignores_cwd_examples(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fake = tmp_path / "examples" / "onboarding" / "app_goal_capture.rllm"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text("invalid", encoding="utf-8")

    selected = _onboarding_app_path("app_goal_capture", tmp_path)

    assert selected != fake.resolve()
    assert selected.name == "app_goal_capture.rllm"
