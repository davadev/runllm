from __future__ import annotations

import getpass
import json
import os
import shlex
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runllm.config import required_provider_key
from runllm.errors import RunLLMError, make_error
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
DEFAULT_SCAFFOLD_PATH = Path(".runllm") / "scaffold-profile.json"

EMBEDDED_ONBOARDING_APPS: dict[str, str] = {
    "provider_select": """---
name: provider_select
description: Recommend a provider/model pair based on user constraints.
version: 0.1.0
author: runllm
max_context_window: 8000
input_schema:
  type: object
  properties:
    preferred_provider: { type: string }
    priority: { type: string, enum: [speed, quality, cost, local] }
  required: [preferred_provider, priority]
  additionalProperties: false
output_schema:
  type: object
  properties:
    provider: { type: string }
    model: { type: string }
    rationale: { type: string }
  required: [provider, model, rationale]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Recommend one provider/model pair.
Return ONLY JSON object with keys provider, model, rationale.

Preferred provider: {{input.preferred_provider}}
Priority: {{input.priority}}

<<<RECOVERY>>>
Return ONLY JSON object with keys provider, model, rationale.
""",
    "credential_check": """---
name: credential_check
description: Produce setup guidance for provider credential status.
version: 0.1.0
author: runllm
max_context_window: 8000
input_schema:
  type: object
  properties:
    provider: { type: string }
    model: { type: string }
    credential_present: { type: boolean }
    env_var_name: { type: string }
  required: [provider, model, credential_present, env_var_name]
  additionalProperties: false
output_schema:
  type: object
  properties:
    status: { type: string, enum: [present, missing] }
    next_action: { type: string }
    setup_steps:
      type: array
      items: { type: string }
      minItems: 1
  required: [status, next_action, setup_steps]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Create concise credential setup guidance.
Return ONLY JSON object with keys status, next_action, setup_steps.

Provider: {{input.provider}}
Model: {{input.model}}
Credential present: {{input.credential_present}}
Env var: {{input.env_var_name}}

<<<RECOVERY>>>
Return ONLY JSON object with keys status, next_action, setup_steps.
""",
    "hello_test": """---
name: hello_test
description: Generate a deterministic hello-world connectivity payload.
version: 0.1.0
author: runllm
max_context_window: 8000
input_schema:
  type: object
  properties:
    user_name: { type: string }
  required: [user_name]
  additionalProperties: false
output_schema:
  type: object
  properties:
    message: { type: string }
    ok: { type: boolean }
  required: [message, ok]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Return ONLY JSON object with keys message and ok.
Message should be a short hello-world line for {{input.user_name}}.
ok must be true.

<<<RECOVERY>>>
Return ONLY JSON object with keys message and ok.
""",
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
    "input_schema_builder": """---
name: input_schema_builder
description: Draft strict input schema structure from a purpose statement.
version: 0.1.0
author: runllm
max_context_window: 9000
input_schema:
  type: object
  properties:
    purpose: { type: string }
    required_inputs:
      type: array
      items: { type: string }
      minItems: 1
  required: [purpose, required_inputs]
  additionalProperties: false
output_schema:
  type: object
  properties:
    properties:
      type: object
      additionalProperties:
        type: object
    required:
      type: array
      items: { type: string }
    notes: { type: string }
  required: [properties, required, notes]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Draft input-schema components only.
Return ONLY JSON object with keys properties, required, notes.

Purpose: {{input.purpose}}
Required inputs: {{input.required_inputs}}

<<<RECOVERY>>>
Return ONLY JSON object with keys properties, required, notes.
""",
    "output_schema_builder": """---
name: output_schema_builder
description: Draft strict output schema structure from app purpose.
version: 0.1.0
author: runllm
max_context_window: 9000
input_schema:
  type: object
  properties:
    purpose: { type: string }
    required_outputs:
      type: array
      items: { type: string }
      minItems: 1
  required: [purpose, required_outputs]
  additionalProperties: false
output_schema:
  type: object
  properties:
    properties:
      type: object
      additionalProperties:
        type: object
    required:
      type: array
      items: { type: string }
    notes: { type: string }
  required: [properties, required, notes]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Draft output-schema components only.
Return ONLY JSON object with keys properties, required, notes.

Purpose: {{input.purpose}}
Required outputs: {{input.required_outputs}}

<<<RECOVERY>>>
Return ONLY JSON object with keys properties, required, notes.
""",
    "context_window_picker": """---
name: context_window_picker
description: Recommend max_context_window based on task profile.
version: 0.1.0
author: runllm
max_context_window: 7000
input_schema:
  type: object
  properties:
    task_size: { type: string, enum: [small, medium, large] }
    expected_input_length: { type: string }
  required: [task_size, expected_input_length]
  additionalProperties: false
output_schema:
  type: object
  properties:
    recommended_max_context_window:
      type: integer
      minimum: 1024
    rationale: { type: string }
  required: [recommended_max_context_window, rationale]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Recommend max_context_window for this app.
Return ONLY JSON object with keys recommended_max_context_window and rationale.

Task size: {{input.task_size}}
Expected input length: {{input.expected_input_length}}

<<<RECOVERY>>>
Return ONLY JSON object with keys recommended_max_context_window and rationale.
""",
    "file_assembler": """---
name: file_assembler
description: Assemble final .rllm text from onboarding components.
version: 0.1.0
author: runllm
max_context_window: 12000
input_schema:
  type: object
  properties:
    app_name: { type: string }
    description: { type: string }
    model: { type: string }
    prompt: { type: string }
    recovery_prompt: { type: string }
  required: [app_name, description, model, prompt, recovery_prompt]
  additionalProperties: false
output_schema:
  type: object
  properties:
    rllm_text: { type: string }
    notes: { type: string }
  required: [rllm_text, notes]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Assemble a complete .rllm file content string from user-provided parts.
Return ONLY JSON object with keys rllm_text and notes.

App name: {{input.app_name}}
Description: {{input.description}}
Model: {{input.model}}
Prompt: {{input.prompt}}
Recovery prompt: {{input.recovery_prompt}}

<<<RECOVERY>>>
Return ONLY JSON object with keys rllm_text and notes.
""",
    "validate_and_test": """---
name: validate_and_test
description: Produce runbook steps for validating and smoke-testing generated app.
version: 0.1.0
author: runllm
max_context_window: 9000
input_schema:
  type: object
  properties:
    app_path: { type: string }
    sample_input: { type: string }
  required: [app_path, sample_input]
  additionalProperties: false
output_schema:
  type: object
  properties:
    checklist:
      type: array
      items: { type: string }
      minItems: 3
    troubleshooting: { type: string }
  required: [checklist, troubleshooting]
  additionalProperties: false
llm:
  model: ollama/llama3.1:8b
llm_params:
  temperature: 0
  format: json
---
Return validation and smoke-test checklist.
Return ONLY JSON object with keys checklist and troubleshooting.

App path: {{input.app_path}}
Sample input: {{input.sample_input}}

<<<RECOVERY>>>
Return ONLY JSON object with keys checklist and troubleshooting.
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


def _prompt_optional_float(prompt: str, default: float | None = None) -> float | None:
    default_text = None if default is None else str(default)
    raw = _prompt(prompt, default=default_text).strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message=f"{prompt} must be a number when provided.",
            details={"value": raw},
            recovery_hint=f"Provide a numeric value for {prompt}, or leave empty.",
            doc_ref="docs/errors.md#RLLM_002",
        ) from exc
    return value


def _session_path(args: Any) -> Path:
    configured = getattr(args, "session_file", None)
    if isinstance(configured, str) and configured.strip():
        return Path(configured).expanduser().resolve()
    return (Path.cwd() / DEFAULT_SESSION_PATH).resolve()


def _scaffold_path(args: Any) -> Path:
    configured = getattr(args, "scaffold_file", None)
    if isinstance(configured, str) and configured.strip():
        return Path(configured).expanduser().resolve()
    return (Path.cwd() / DEFAULT_SCAFFOLD_PATH).resolve()


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


def _save_scaffold(path: Path, data: dict[str, Any]) -> None:
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


def _sanitize_schema_from_builder(builder_output: dict[str, Any], fallback_keys: list[str]) -> dict[str, Any]:
    fallback = [_normalize_name(k) for k in fallback_keys if _normalize_name(k)]
    fallback_set = set(fallback)
    raw_properties = builder_output.get("properties", {})
    properties: dict[str, dict[str, Any]] = {}
    if isinstance(raw_properties, dict):
        for key, value in raw_properties.items():
            normalized_key = _normalize_name(str(key))
            if not normalized_key:
                continue
            if normalized_key not in fallback_set:
                continue
            if isinstance(value, dict):
                prop = dict(value)
                if "type" not in prop or not isinstance(prop.get("type"), str):
                    prop["type"] = "string"
                properties[normalized_key] = prop

    required = builder_output.get("required", [])
    required_keys: list[str] = []
    if isinstance(required, list):
        for item in required:
            key = _normalize_name(str(item))
            if key and key in fallback_set and key not in required_keys:
                required_keys.append(key)

    if not properties:
        properties = {k: {"type": "string"} for k in fallback}
    for key in fallback:
        properties.setdefault(key, {"type": "string"})
    if not required_keys:
        required_keys = list(fallback)
    else:
        required_keys = [key for key in required_keys if key in properties]
        for key in fallback:
            if key not in required_keys:
                required_keys.append(key)

    return {
        "type": "object",
        "properties": properties,
        "required": required_keys,
        "additionalProperties": False,
    }


def _render_rllm_text(
    *,
    app_name: str,
    description: str,
    author: str,
    model: str,
    temperature: float,
    top_p: float | None,
    response_format: str,
    max_context_window: int,
    input_keys: list[str],
    output_keys: list[str],
    purpose: str,
    input_schema_override: dict[str, Any] | None = None,
    output_schema_override: dict[str, Any] | None = None,
) -> str:
    input_schema = input_schema_override if isinstance(input_schema_override, dict) else _schema_for_keys(input_keys)
    output_schema = output_schema_override if isinstance(output_schema_override, dict) else _schema_for_keys(output_keys)
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
        "llm_params": {
            "temperature": temperature,
            "format": response_format,
            **({"top_p": top_p} if top_p is not None else {}),
        },
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
    save_scaffold = not bool(getattr(args, "no_save_scaffold", False))
    scaffold_path = _scaffold_path(args)
    session_data = _load_session(session_path) if getattr(args, "resume", False) else {}
    preferred_provider = str(
        session_data.get("preferred_provider") or session_data.get("provider") or "openai"
    )
    priority = str(session_data.get("priority") or "quality")

    def persist(**updates: Any) -> None:
        session_data.update(updates)
        _save_session(session_path, session_data)

    if args.model:
        model = args.model.strip()
        preferred_provider = _provider_for_model(model)
    else:
        preferred_provider = _prompt(
            "Choose provider (openai, anthropic, google, mistral, cohere, ollama)",
            default=preferred_provider,
        ).lower()
        priority = _prompt(
            "Priority (speed, quality, cost, local)",
            default=priority,
        ).lower()
        model = PROVIDER_DEFAULT_MODEL.get(preferred_provider, PROVIDER_DEFAULT_MODEL["openai"])
        model = _prompt("Model to use", default=str(session_data.get("model") or model)).strip() or model

    provider_name = _provider_for_model(model)
    persist(model=model, provider=provider_name, preferred_provider=preferred_provider, priority=priority)
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
        has_cred = True
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

        def run_step(name: str, payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
            try:
                out = run_program(
                    _onboarding_app_path(name, temp_dir),
                    payload,
                    RunOptions(model_override=model, max_retries=1),
                    autoload_config=autoload_config,
                )
                if isinstance(out, dict):
                    return out
                return fallback
            except RunLLMError:
                print(f"Onboarding step '{name}' failed; using fallback.", file=sys.stderr)
                return fallback

        provider_plan = run_step(
            "provider_select",
            {"preferred_provider": preferred_provider, "priority": priority},
            {"provider": provider_name, "model": model, "rationale": "Using selected model."},
        )
        rationale = str(provider_plan.get("rationale") or "")
        if rationale:
            print(f"Provider guidance: {rationale}", file=sys.stderr)

        credential_guidance: dict[str, Any] = {}
        if missing_key is not None:
            credential_guidance = run_step(
                "credential_check",
                {
                    "provider": provider_name,
                    "model": model,
                    "credential_present": bool(has_cred),
                    "env_var_name": missing_key,
                },
                {
                    "status": "present" if has_cred else "missing",
                    "next_action": "Continue",
                    "setup_steps": [
                        f"Set {missing_key} in your environment and rerun onboarding."
                        if not has_cred
                        else f"{missing_key} is already available; continue onboarding."
                    ],
                },
            )
            next_action = str(credential_guidance.get("next_action") or "")
            if next_action:
                print(f"Credential guidance: {next_action}", file=sys.stderr)

        probe_path = Path(tmp_dir) / "connectivity_probe.rllm"
        probe_path.write_text(_render_connectivity_probe_app_text(model), encoding="utf-8")
        run_program(
            probe_path,
            {"text": "hello from runllm onboarding"},
            RunOptions(model_override=model, max_retries=1),
            autoload_config=autoload_config,
        )

        user_name = os.environ.get("USER") or os.environ.get("USERNAME") or "runllm user"
        hello_step = run_step(
            "hello_test",
            {"user_name": user_name},
            {"message": "Connectivity verified.", "ok": True},
        )
        hello_message = str(hello_step.get("message") or "")
        if hello_message:
            print(f"Hello check: {hello_message}", file=sys.stderr)

        initial_goal = _prompt(
            "Describe what your app should do (chat style)",
            default=str(session_data.get("initial_goal") or "summarize support messages"),
        )
        persist(initial_goal=initial_goal)

        goal_step = run_step(
            "app_goal_capture",
            {"raw_goal": initial_goal},
            {"app_name_hint": "first_app", "purpose": initial_goal, "acceptance_criteria": []},
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

        task_size = "small"
        if len(input_keys) + len(output_keys) >= 6:
            task_size = "large"
        elif len(input_keys) + len(output_keys) >= 4:
            task_size = "medium"
        context_suggestion = run_step(
            "context_window_picker",
            {
                "task_size": task_size,
                "expected_input_length": f"{max(32, len(purpose) * 8)} characters",
            },
            {"recommended_max_context_window": 8000, "rationale": "fallback"},
        )
        suggested_context = int(context_suggestion.get("recommended_max_context_window") or 8000)
        max_context_window = _prompt_int(
            "max_context_window",
            int(session_data.get("max_context_window") or suggested_context),
        )
        temperature = _prompt_float(
            "temperature",
            float(session_data.get("temperature") or 0.0),
        )
        if temperature < 0:
            raise make_error(
                error_code="RLLM_002",
                error_type="MetadataValidationError",
                message="temperature must be greater than or equal to 0.",
                details={"temperature": temperature},
                recovery_hint="Set temperature to 0 or greater.",
                doc_ref="docs/errors.md#RLLM_002",
            )
        top_p = _prompt_optional_float(
            "top_p (optional, blank to skip)",
            float(session_data["top_p"]) if session_data.get("top_p") is not None else None,
        )
        if top_p is not None and (top_p <= 0 or top_p > 1):
            raise make_error(
                error_code="RLLM_002",
                error_type="MetadataValidationError",
                message="top_p must be within (0, 1] when provided.",
                details={"top_p": top_p},
                recovery_hint="Set top_p to a value greater than 0 and less than or equal to 1.",
                doc_ref="docs/errors.md#RLLM_002",
            )
        response_format = _prompt(
            "llm format (json default; override only if required)",
            default=str(session_data.get("response_format") or "json"),
        ).strip()
        if not response_format:
            response_format = "json"
        response_format = response_format.lower()
        if response_format != "json":
            if not _prompt_yes_no(f"Use non-default format '{response_format}'", default=False):
                response_format = "json"
        default_output_path = str(session_data.get("output_path") or f"{app_name}.rllm")
        output_path = Path(_prompt("Output .rllm path", default=default_output_path)).expanduser().resolve()

        def build_draft_components(
            current_purpose: str,
            current_input_keys: list[str],
            current_output_keys: list[str],
        ) -> dict[str, Any]:
            input_schema_step_inner = run_step(
                "input_schema_builder",
                {"purpose": current_purpose, "required_inputs": current_input_keys},
                {
                    "properties": {k: {"type": "string"} for k in current_input_keys},
                    "required": current_input_keys,
                    "notes": "fallback",
                },
            )
            output_schema_step_inner = run_step(
                "output_schema_builder",
                {"purpose": current_purpose, "required_outputs": current_output_keys},
                {
                    "properties": {k: {"type": "string"} for k in current_output_keys},
                    "required": current_output_keys,
                    "notes": "fallback",
                },
            )
            input_schema_inner = _sanitize_schema_from_builder(input_schema_step_inner, current_input_keys)
            output_schema_inner = _sanitize_schema_from_builder(output_schema_step_inner, current_output_keys)

            fallback_prompt_inner = (
                f"You are a focused micro-app for: {current_purpose}.\n"
                f"Return ONLY JSON object with keys: {', '.join(current_output_keys)}.\n\n"
                "Input values:\n"
                + "\n".join(f"- {k}: {{{{input.{k}}}}}" for k in current_input_keys)
            )
            fallback_recovery_inner = (
                "Previous response failed validation.\n"
                f"Return ONLY JSON object with keys: {', '.join(current_output_keys)}.\n"
                "No markdown, prose, or code blocks."
            )
            prompt_step_inner = run_step(
                "prompt_builder",
                {"purpose": current_purpose, "output_keys": current_output_keys},
                {"prompt": fallback_prompt_inner},
            )
            recovery_step_inner = run_step(
                "recovery_builder",
                {"output_keys": current_output_keys},
                {"recovery_prompt": fallback_recovery_inner},
            )
            draft_prompt = str(prompt_step_inner.get("prompt") or "")
            draft_recovery = str(recovery_step_inner.get("recovery_prompt") or "")
            if not _is_usable_prompt(draft_prompt, current_output_keys):
                draft_prompt = ""
            if not _is_usable_prompt(draft_recovery, current_output_keys):
                draft_recovery = ""
            return {
                "input_schema": input_schema_inner,
                "output_schema": output_schema_inner,
                "fallback_prompt": fallback_prompt_inner,
                "fallback_recovery": fallback_recovery_inner,
                "llm_prompt": draft_prompt,
                "llm_recovery": draft_recovery,
            }

        drafts = build_draft_components(purpose, input_keys, output_keys)
        input_schema = drafts["input_schema"]
        output_schema = drafts["output_schema"]
        fallback_prompt = str(drafts["fallback_prompt"])
        fallback_recovery = str(drafts["fallback_recovery"])
        llm_prompt = str(drafts["llm_prompt"])
        llm_recovery = str(drafts["llm_recovery"])
        if llm_prompt.strip():
            print("Draft prompt generated by onboarding micro-app.", file=sys.stderr)
        if llm_recovery.strip():
            print("Draft recovery prompt generated by onboarding micro-app.", file=sys.stderr)

        preview_prompt = (llm_prompt if llm_prompt else fallback_prompt).replace("\n", " ")[:180]
        preview_recovery = (llm_recovery if llm_recovery else fallback_recovery).replace("\n", " ")[:180]
        print("Draft summary before generation:", file=sys.stderr)
        print(f"- purpose: {purpose}", file=sys.stderr)
        print(f"- input keys: {', '.join(input_keys)}", file=sys.stderr)
        print(f"- output keys: {', '.join(output_keys)}", file=sys.stderr)
        print(f"- prompt preview: {preview_prompt}", file=sys.stderr)
        print(f"- recovery preview: {preview_recovery}", file=sys.stderr)

        refine_choice = _prompt(
            "Approve draft or revise (approve|purpose|input|output|params|prompt)",
            default="approve",
        ).strip().lower()
        if refine_choice and refine_choice != "approve":
            if refine_choice == "purpose":
                purpose = _prompt("Revised purpose", default=purpose).strip() or purpose
            elif refine_choice == "input":
                input_keys = _parse_key_list(
                    _prompt("Revised input keys (comma-separated)", default=",".join(input_keys)),
                    "text",
                )
            elif refine_choice == "output":
                output_keys = _parse_key_list(
                    _prompt("Revised output keys (comma-separated)", default=",".join(output_keys)),
                    "result",
                )
            elif refine_choice == "params":
                max_context_window = _prompt_int("max_context_window", max_context_window)
                temperature = _prompt_float("temperature", temperature)
                if temperature < 0:
                    raise make_error(
                        error_code="RLLM_002",
                        error_type="MetadataValidationError",
                        message="temperature must be greater than or equal to 0.",
                        details={"temperature": temperature},
                        recovery_hint="Set temperature to 0 or greater.",
                        doc_ref="docs/errors.md#RLLM_002",
                    )
                top_p = _prompt_optional_float(
                    "top_p (optional, blank to skip)",
                    top_p,
                )
                if top_p is not None and (top_p <= 0 or top_p > 1):
                    raise make_error(
                        error_code="RLLM_002",
                        error_type="MetadataValidationError",
                        message="top_p must be within (0, 1] when provided.",
                        details={"top_p": top_p},
                        recovery_hint="Set top_p to a value greater than 0 and less than or equal to 1.",
                        doc_ref="docs/errors.md#RLLM_002",
                    )
                revised_format = _prompt(
                    "llm format (json default; override only if required)",
                    default=response_format,
                ).strip().lower()
                if revised_format:
                    if revised_format == "json" or _prompt_yes_no(
                        f"Use non-default format '{revised_format}'", default=False
                    ):
                        response_format = revised_format
            elif refine_choice == "prompt":
                llm_prompt = _prompt(
                    "Revised prompt text",
                    default=llm_prompt if llm_prompt else fallback_prompt,
                )
                llm_recovery = _prompt(
                    "Revised recovery prompt text",
                    default=llm_recovery if llm_recovery else fallback_recovery,
                )

            if refine_choice in {"purpose", "input", "output", "params"}:
                drafts = build_draft_components(purpose, input_keys, output_keys)
                input_schema = drafts["input_schema"]
                output_schema = drafts["output_schema"]
                fallback_prompt = str(drafts["fallback_prompt"])
                fallback_recovery = str(drafts["fallback_recovery"])
                llm_prompt = str(drafts["llm_prompt"])
                llm_recovery = str(drafts["llm_recovery"])

        final_prompt = llm_prompt if llm_prompt.strip() else fallback_prompt
        final_recovery = llm_recovery if llm_recovery.strip() else fallback_recovery
        assembler_notes = ""

        persist(
            purpose=purpose,
            app_name=app_name,
            description=description,
            author=author,
            input_keys=input_keys,
            output_keys=output_keys,
            max_context_window=max_context_window,
            temperature=temperature,
            top_p=top_p,
            response_format=response_format,
            output_path=str(output_path),
        )

        rllm_text = _render_rllm_text(
            app_name=app_name,
            description=description,
            author=author,
            model=model,
            temperature=temperature,
            top_p=top_p,
            response_format=response_format,
            max_context_window=max_context_window,
            input_keys=input_keys,
            output_keys=output_keys,
            purpose=purpose,
            input_schema_override=input_schema,
            output_schema_override=output_schema,
        )
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

        validate_step = run_step(
            "validate_and_test",
            {"app_path": str(output_path), "sample_input": json.dumps(sample_input, ensure_ascii=True)},
            {
                "checklist": [
                    f"runllm validate {shlex.quote(str(output_path))}",
                    f"runllm inspect {shlex.quote(str(output_path))}",
                    f"runllm run {shlex.quote(str(output_path))} --input {shlex.quote(json.dumps(sample_input, ensure_ascii=True))}",
                ],
                "troubleshooting": "Use runllm help recovery for schema failures.",
            },
        )
        onboarding_checklist = validate_step.get("checklist", [])
        troubleshooting = str(validate_step.get("troubleshooting") or "")

        llm_params_payload: dict[str, Any] = {
            "temperature": temperature,
            "format": response_format,
        }
        if top_p is not None:
            llm_params_payload["top_p"] = top_p

        scaffold_profile = {
            "app_name": app_name,
            "purpose": purpose,
            "model": model,
            "llm_params": llm_params_payload,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "prompt": final_prompt,
            "recovery_prompt": final_recovery,
            "suggested_sample_input": sample_input,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        scaffold_file: str | None = None
        if save_scaffold:
            _save_scaffold(scaffold_path, scaffold_profile)
            scaffold_file = str(scaffold_path)
    print("Connectivity check passed.", file=sys.stderr)

    payload = {
        "ok": True,
        "provider": provider_name,
        "model": model,
        "credential_written": credential_written,
        "credential_path": credential_path,
        "provider_recommendation": provider_plan,
        "credential_guidance": credential_guidance,
        "hello": hello_step,
        "generated_file": str(output_path),
        "sample_input": sample_input,
        "sample_output": test_output,
        "session_file": str(session_path),
        "scaffold_file": scaffold_file,
        "assembler_notes": assembler_notes,
        "onboarding_checklist": onboarding_checklist,
        "troubleshooting": troubleshooting,
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
