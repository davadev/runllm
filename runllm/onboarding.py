from __future__ import annotations

import getpass
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any

from runllm.config import required_provider_key
from runllm.errors import make_error
from runllm.executor import run_program
from runllm.models import RunOptions
from runllm.parser import parse_rllm_file


PROVIDER_DEFAULT_MODEL: dict[str, str] = {
    "openai": "openai/gpt-4o-mini",
    "anthropic": "anthropic/claude-3-5-sonnet-20241022",
    "google": "google/gemini-1.5-flash",
    "mistral": "mistral/mistral-small-latest",
    "cohere": "cohere/command-r",
    "ollama": "ollama/llama3.1:8b",
}

DEFAULT_SESSION_PATH = Path(".runllm") / "onboarding-session.json"

EMBEDDED_ONBOARDING_APPS: dict[str, str] = {
    "app_goal_capture": """---
name: app_goal_capture
description: Refine user app goal into a clear micro-app objective.
version: 0.1.0
author: runllm
max_context_window: 8000
input_schema:
  type: object
  properties:
    raw_goal: { type: string }
  required: [raw_goal]
  additionalProperties: false
output_schema:
  type: object
  properties:
    app_name_hint: { type: string }
    purpose: { type: string }
    acceptance_criteria:
      type: array
      items: { type: string }
      minItems: 2
  required: [app_name_hint, purpose, acceptance_criteria]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Refine the user goal into one atomic app objective.
Return ONLY JSON object with keys app_name_hint, purpose, acceptance_criteria.

Goal: {{input.raw_goal}}

<<<RECOVERY>>>
Return ONLY JSON object with keys app_name_hint, purpose, acceptance_criteria.
""",
    "prompt_builder": """---
name: prompt_builder
description: Draft concise JSON-first main prompt for the new app.
version: 0.1.0
author: runllm
max_context_window: 9000
input_schema:
  type: object
  properties:
    purpose: { type: string }
    output_keys:
      type: array
      items: { type: string }
      minItems: 1
  required: [purpose, output_keys]
  additionalProperties: false
output_schema:
  type: object
  properties:
    prompt: { type: string }
  required: [prompt]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Generate a concise main prompt.
Return ONLY JSON object with key prompt.

Purpose: {{input.purpose}}
Output keys: {{input.output_keys}}

<<<RECOVERY>>>
Return ONLY JSON object with key prompt.
""",
    "recovery_builder": """---
name: recovery_builder
description: Draft strict recovery prompt for schema retry.
version: 0.1.0
author: runllm
max_context_window: 9000
input_schema:
  type: object
  properties:
    output_keys:
      type: array
      items: { type: string }
      minItems: 1
  required: [output_keys]
  additionalProperties: false
output_schema:
  type: object
  properties:
    recovery_prompt: { type: string }
  required: [recovery_prompt]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Create strict recovery prompt text for schema retries.
Return ONLY JSON object with key recovery_prompt.

Output keys: {{input.output_keys}}

<<<RECOVERY>>>
Return ONLY JSON object with key recovery_prompt.
""",
}


def _normalize_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value.strip().lower())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_")
    return cleaned or "first_app"


def _prompt(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    print(f"{prompt}{suffix}: ", end="", file=sys.stderr, flush=True)
    try:
        raw = input().strip()
    except EOFError as exc:
        raise make_error(
            error_code="RLLM_011",
            error_type="ExecutionError",
            message="Interactive input unavailable during onboarding.",
            details={"prompt": prompt},
            recovery_hint="Run onboarding in an interactive terminal.",
            doc_ref="docs/errors.md#RLLM_011",
        ) from exc
    if raw:
        return raw
    return default or ""


def _prompt_yes_no(prompt: str, *, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    print(f"{prompt} ({hint}): ", end="", file=sys.stderr, flush=True)
    try:
        raw = input().strip().lower()
    except EOFError as exc:
        raise make_error(
            error_code="RLLM_011",
            error_type="ExecutionError",
            message="Interactive input unavailable during onboarding.",
            details={"prompt": prompt},
            recovery_hint="Run onboarding in an interactive terminal.",
            doc_ref="docs/errors.md#RLLM_011",
        ) from exc
    if not raw:
        return default
    return raw in {"y", "yes"}


def _provider_for_model(model: str) -> str:
    lowered = model.strip().lower()
    if lowered.startswith("ollama/"):
        return "ollama"
    required = required_provider_key(model)
    if required is not None:
        provider, _key_name = required
        return provider
    for provider in PROVIDER_DEFAULT_MODEL:
        if lowered.startswith(f"{provider}/"):
            return provider
    return "custom"


def _detect_credential(model: str) -> tuple[bool, str | None]:
    required = required_provider_key(model)
    if required is None:
        return True, None
    _provider, key_name = required
    return bool(os.environ.get(key_name)), key_name


def _upsert_env_file(path: Path, key: str, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    replaced = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f'{key}="{value}"')
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f'{key}="{value}"')
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _parse_key_list(raw: str, fallback: str) -> list[str]:
    source = raw.strip() or fallback
    items = [x.strip() for x in source.split(",") if x.strip()]
    normalized = [_normalize_name(x) for x in items]
    unique: list[str] = []
    for item in normalized:
        if item not in unique:
            unique.append(item)
    return unique or [fallback]


def _prompt_int(prompt: str, default: int) -> int:
    raw = _prompt(prompt, default=str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message=f"{prompt} must be an integer.",
            details={"value": raw},
            recovery_hint=f"Provide an integer value for {prompt}.",
            doc_ref="docs/errors.md#RLLM_002",
        ) from exc
    return value


def _prompt_float(prompt: str, default: float) -> float:
    raw = _prompt(prompt, default=str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message=f"{prompt} must be a number.",
            details={"value": raw},
            recovery_hint=f"Provide a numeric value for {prompt}.",
            doc_ref="docs/errors.md#RLLM_002",
        ) from exc
    return value


def _session_path(args: Any) -> Path:
    configured = getattr(args, "session_file", None)
    if isinstance(configured, str) and configured.strip():
        return Path(configured).expanduser().resolve()
    return (Path.cwd() / DEFAULT_SESSION_PATH).resolve()


def _load_session(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _save_session(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _onboarding_app_path(name: str, temp_dir: Path) -> Path:
    packaged = Path(__file__).resolve().parents[1] / "examples" / "onboarding" / f"{name}.rllm"
    if packaged.exists():
        return packaged.resolve()
    text = EMBEDDED_ONBOARDING_APPS.get(name)
    if not text:
        raise make_error(
            error_code="RLLM_011",
            error_type="ExecutionError",
            message=f"Missing onboarding app template: {name}",
            details={"step": name},
            recovery_hint="Install a build with onboarding templates or run from repository root.",
            doc_ref="docs/errors.md#RLLM_011",
        )
    out = temp_dir / f"{name}.rllm"
    out.write_text(text, encoding="utf-8")
    return out


def _schema_for_keys(keys: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {k: {"type": "string"} for k in keys},
        "required": keys,
        "additionalProperties": False,
    }


def _render_rllm_text(
    *,
    app_name: str,
    description: str,
    author: str,
    model: str,
    temperature: float,
    max_context_window: int,
    input_keys: list[str],
    output_keys: list[str],
    purpose: str,
) -> str:
    input_schema = _schema_for_keys(input_keys)
    output_schema = _schema_for_keys(output_keys)
    prompt_keys = ", ".join(output_keys)
    first_output = output_keys[0]
    prompt_body = (
        f"You are a focused micro-app for: {purpose}.\n"
        f"Return ONLY JSON object with keys: {prompt_keys}.\n\n"
        "Input values:\n"
        + "\n".join(f"- {k}: {{{{input.{k}}}}}" for k in input_keys)
    )
    recovery = (
        "Previous response failed validation.\n"
        f"Return ONLY JSON object with keys: {prompt_keys}.\n"
        "No markdown, prose, or code blocks."
    )
    frontmatter = {
        "name": app_name,
        "description": description,
        "version": "0.1.0",
        "author": author,
        "max_context_window": max_context_window,
        "input_schema": input_schema,
        "output_schema": output_schema,
        "llm": {"model": model},
        "llm_params": {"temperature": temperature, "format": "json"},
        "recommended_models": [model],
        "tags": ["onboarding-generated"],
        "metadata": {"starter_output_key": first_output},
    }
    import yaml

    yaml_text = yaml.safe_dump(frontmatter, sort_keys=False)
    return f"---\n{yaml_text}---\n{prompt_body}\n\n<<<RECOVERY>>>\n{recovery}\n"


def _render_connectivity_probe_app_text(model: str) -> str:
    return f"""---
name: onboarding_connectivity_probe
description: Connectivity probe for onboarding.
version: 0.1.0
author: runllm
max_context_window: 2000
input_schema:
  type: object
  properties:
    text:
      type: string
  required: [text]
  additionalProperties: false
output_schema:
  type: object
  properties:
    ok:
      type: boolean
    message:
      type: string
  required: [ok, message]
  additionalProperties: false
llm:
  model: {model}
llm_params:
  temperature: 0
  format: json
---
Return ONLY JSON object with keys ok and message.
Set ok to true.
Input: {{{{input.text}}}}

<<<RECOVERY>>>
Return ONLY JSON object with keys ok and message.
"""


def _replace_prompt_and_recovery(base_text: str, *, prompt_text: str, recovery_text: str) -> str:
    close_idx = base_text.find("\n---\n", 4)
    if close_idx == -1:
        return base_text
    frontmatter = base_text[: close_idx + 5]
    return f"{frontmatter}{prompt_text.strip()}\n\n<<<RECOVERY>>>\n{recovery_text.strip()}\n"


def _is_usable_prompt(draft: str, output_keys: list[str]) -> bool:
    text = draft.strip().lower()
    if not text:
        return False
    if "json" not in text:
        return False
    return all(key.lower() in text for key in output_keys)


def run_onboarding(args: Any) -> dict[str, Any]:
    print("runllm onboarding: create your first .rllm app", file=sys.stderr)

    autoload_config = getattr(args, "_autoload_config", None)
    session_path = _session_path(args)
    session_data = _load_session(session_path) if getattr(args, "resume", False) else {}

    def persist(**updates: Any) -> None:
        session_data.update(updates)
        _save_session(session_path, session_data)

    if args.model:
        model = args.model.strip()
    else:
        provider = _prompt(
            "Choose provider (openai, anthropic, google, mistral, cohere, ollama)",
            default=str(session_data.get("provider") or "openai"),
        ).lower()
        model = PROVIDER_DEFAULT_MODEL.get(provider, PROVIDER_DEFAULT_MODEL["openai"])
        model = _prompt("Model to use", default=str(session_data.get("model") or model)).strip() or model

    provider_name = _provider_for_model(model)
    persist(model=model, provider=provider_name)
    has_cred, missing_key = _detect_credential(model)

    credential_written = False
    credential_path: str | None = None
    if not has_cred and missing_key is not None:
        print(f"Missing credential: {missing_key}", file=sys.stderr)
        if not _prompt_yes_no("Set credential now", default=True):
            raise make_error(
                error_code="RLLM_014",
                error_type="MissingProviderCredentialError",
                message="Onboarding requires provider credential to continue.",
                details={"missing_env_var": missing_key, "model": model},
                recovery_hint=f"Set {missing_key} and rerun onboarding.",
                doc_ref="docs/errors.md#RLLM_014",
            )
        key_value = getpass.getpass(f"Enter {missing_key}: ").strip()
        if not key_value:
            raise make_error(
                error_code="RLLM_014",
                error_type="MissingProviderCredentialError",
                message="Credential input was empty.",
                details={"missing_env_var": missing_key, "model": model},
                recovery_hint=f"Provide a non-empty {missing_key} value.",
                doc_ref="docs/errors.md#RLLM_014",
            )
        os.environ[missing_key] = key_value
        env_path = Path(_prompt("Write credential to .env path", default=".env")).expanduser().resolve()
        if _prompt_yes_no(f"Write {missing_key} to {env_path}", default=False):
            _upsert_env_file(env_path, missing_key, key_value)
            credential_written = True
            credential_path = str(env_path)
        else:
            print("Using credential for current session only (not written to disk).", file=sys.stderr)

    print("Running connectivity check...", file=sys.stderr)
    with tempfile.TemporaryDirectory(prefix="runllm-onboard-") as tmp_dir:
        temp_dir = Path(tmp_dir)
        probe_path = Path(tmp_dir) / "connectivity_probe.rllm"
        probe_path.write_text(_render_connectivity_probe_app_text(model), encoding="utf-8")
        run_program(
            probe_path,
            {"text": "hello from runllm onboarding"},
            RunOptions(model_override=model, max_retries=1),
            autoload_config=autoload_config,
        )

        initial_goal = _prompt(
            "Describe what your app should do (chat style)",
            default=str(session_data.get("initial_goal") or "summarize support messages"),
        )
        persist(initial_goal=initial_goal)

        goal_step = run_program(
            _onboarding_app_path("app_goal_capture", temp_dir),
            {"raw_goal": initial_goal},
            RunOptions(model_override=model, max_retries=1),
            autoload_config=autoload_config,
        )

        suggested_name = _normalize_name(str(goal_step.get("app_name_hint") or "first_app"))
        suggested_purpose = str(goal_step.get("purpose") or initial_goal)
        print(f"Proposed purpose: {suggested_purpose}", file=sys.stderr)
        print(f"Proposed app name: {suggested_name}", file=sys.stderr)

        purpose = str(session_data.get("purpose") or suggested_purpose)
        print(f"Using purpose: {purpose}", file=sys.stderr)
        app_name = _normalize_name(_prompt("App name", default=str(session_data.get("app_name") or suggested_name)))
        description = _prompt("Short description", default=str(session_data.get("description") or purpose))
        author_default = os.environ.get("USER") or os.environ.get("USERNAME") or "runllm_user"
        author = _prompt("Author", default=str(session_data.get("author") or author_default))
        input_keys = _parse_key_list(
            _prompt(
                "Input keys (comma-separated)",
                default=",".join(session_data.get("input_keys", ["text"])),
            ),
            "text",
        )
        output_keys = _parse_key_list(
            _prompt(
                "Output keys (comma-separated)",
                default=",".join(session_data.get("output_keys", ["result"])),
            ),
            "result",
        )
        max_context_window = _prompt_int(
            "max_context_window",
            int(session_data.get("max_context_window") or 8000),
        )
        temperature = _prompt_float(
            "temperature",
            float(session_data.get("temperature") or 0.0),
        )
        default_output_path = str(session_data.get("output_path") or f"{app_name}.rllm")
        output_path = Path(_prompt("Output .rllm path", default=default_output_path)).expanduser().resolve()

        prompt_step = run_program(
            _onboarding_app_path("prompt_builder", temp_dir),
            {"purpose": purpose, "output_keys": output_keys},
            RunOptions(model_override=model, max_retries=1),
            autoload_config=autoload_config,
        )
        recovery_step = run_program(
            _onboarding_app_path("recovery_builder", temp_dir),
            {"output_keys": output_keys},
            RunOptions(model_override=model, max_retries=1),
            autoload_config=autoload_config,
        )

        llm_prompt = str(prompt_step.get("prompt") or "")
        llm_recovery = str(recovery_step.get("recovery_prompt") or "")
        if llm_prompt.strip():
            print("Draft prompt generated by onboarding micro-app.", file=sys.stderr)
        if llm_recovery.strip():
            print("Draft recovery prompt generated by onboarding micro-app.", file=sys.stderr)

        fallback_prompt = (
            f"You are a focused micro-app for: {purpose}.\n"
            f"Return ONLY JSON object with keys: {', '.join(output_keys)}.\n\n"
            "Input values:\n"
            + "\n".join(f"- {k}: {{{{input.{k}}}}}" for k in input_keys)
        )
        fallback_recovery = (
            "Previous response failed validation.\n"
            f"Return ONLY JSON object with keys: {', '.join(output_keys)}.\n"
            "No markdown, prose, or code blocks."
        )

        if not _is_usable_prompt(llm_prompt, output_keys):
            llm_prompt = ""
        if not _is_usable_prompt(llm_recovery, output_keys):
            llm_recovery = ""

        persist(
            purpose=purpose,
            app_name=app_name,
            description=description,
            author=author,
            input_keys=input_keys,
            output_keys=output_keys,
            max_context_window=max_context_window,
            temperature=temperature,
            output_path=str(output_path),
        )

        rllm_text = _render_rllm_text(
            app_name=app_name,
            description=description,
            author=author,
            model=model,
            temperature=temperature,
            max_context_window=max_context_window,
            input_keys=input_keys,
            output_keys=output_keys,
            purpose=purpose,
        )
        if llm_prompt.strip() or llm_recovery.strip():
            final_prompt = llm_prompt if llm_prompt.strip() else fallback_prompt
            final_recovery = llm_recovery if llm_recovery.strip() else fallback_recovery
            rllm_text = _replace_prompt_and_recovery(
                rllm_text,
                prompt_text=final_prompt,
                recovery_text=final_recovery,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rllm_text, encoding="utf-8")

        parse_rllm_file(output_path)

        sample_input = {k: f"sample {k}" for k in input_keys}
        test_output = run_program(
            output_path,
            sample_input,
            RunOptions(model_override=model, max_retries=2),
            autoload_config=autoload_config,
        )
    print("Connectivity check passed.", file=sys.stderr)

    payload = {
        "ok": True,
        "provider": provider_name,
        "model": model,
        "credential_written": credential_written,
        "credential_path": credential_path,
        "generated_file": str(output_path),
        "sample_input": sample_input,
        "sample_output": test_output,
        "session_file": str(session_path),
        "next_steps": [
            f"runllm inspect {shlex.quote(str(output_path))}",
            f"runllm run {shlex.quote(str(output_path))} --input {shlex.quote(json.dumps(sample_input))}",
        ],
    }
    return payload


def cmd_onboard(args: Any) -> int:
    payload = run_onboarding(args)
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0
