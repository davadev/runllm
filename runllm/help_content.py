from __future__ import annotations

import textwrap
from typing import Any


HELP_TOPICS: tuple[str, ...] = (
    "rllm",
    "schema",
    "recovery",
    "composition",
    "examples",
    "credentials",
    "config",
)


def help_topics_text() -> dict[str, str]:
    return {
        "rllm": textwrap.dedent(
            """
            .rllm app authoring reference

            Required frontmatter keys:
            - name (string)
            - description (string)
            - version (string)
            - author (string)
            - max_context_window (positive integer)
            - input_schema (JSON Schema object)
            - output_schema (JSON Schema object)
            - llm (object, must include model)
            - llm_params (object)

            Optional frontmatter keys:
            - runllm_compat (object with min and optional max_exclusive)

            Body structure:
            - main prompt text
            - optional <<<RECOVERY>>> block
            - optional ```rllm-python pre/post blocks

            Minimal template:
            ---
            name: my_app
            description: One sentence purpose.
            version: 0.1.0
            author: your_name
            max_context_window: 8000
            input_schema:
              type: object
              properties:
                text: { type: string }
              required: [text]
              additionalProperties: false
            output_schema:
              type: object
              properties:
                result: { type: string }
              required: [result]
              additionalProperties: false
            llm:
              model: ollama/llama3.1:8b
            llm_params:
              temperature: 0
              format: json
            ---
            Return only JSON: {"result":"..."}
            Input: {{input.text}}
            """
        ).strip(),
        "schema": textwrap.dedent(
            """
            JSON Schema guidance

            Good defaults:
            - type: object
            - required: [...] for mandatory fields
            - additionalProperties: false for strict contracts

            Common patterns:
            - classification: enum + confidence in [0,1]
            - extraction: arrays of strings/objects
            - nullable optional field: type: [string, "null"]

            Avoid:
            - missing required list
            - very deep nested objects for small models
            - loose free-form output where enums work
            """
        ).strip(),
        "recovery": textwrap.dedent(
            """
            Recovery prompt playbook

            Use <<<RECOVERY>>> for retry instructions.
            Keep it short and schema-focused.

            Recommended pattern:
            Previous response failed validation.
            Return ONLY JSON object with exact keys: <k1>, <k2>...
            Do not include markdown, prose, or schema definitions.
            """
        ).strip(),
        "composition": textwrap.dedent(
            """
            Composed app playbook

            Stage contract checklist:
            - One stage = one responsibility.
            - Keep input/output schemas minimal and strict.
            - Keep downstream-required keys stable.
            - Define retryable vs non-retryable failures.
            - Prefer deterministic verification for extracted evidence.

            Composition interface rules:
            - Preserve stable key names across stage boundaries.
            - Prefer additive schema evolution over key renames.
            - Keep provenance fields in intermediate artifacts when relevant.
            - Avoid hidden coupling to free-form prose formats.

            Evidence lifecycle pattern:
            - retrieved -> filtered -> verified -> synthesized
            - final synthesis should consume verified evidence only

            Runtime budgeting and parallelism:
            - Cap early discovery fan-out (planned questions/leads).
            - Avoid late-stage truncation of already verified evidence.
            - Parallelize independent retrieval branches.
            - Merge with deterministic ordering + dedupe keys.
            - Add sequential fallback for transient parallel failures.

            Suggested docs:
            - docs/composition.md
            - docs/multistep-apps.md
            - docs/authoring-guide.md
            - docs/schema-cookbook.md
            """
        ).strip(),
        "examples": textwrap.dedent(
            """
            Example command flow

            1) Validate app file
               runllm validate app.rllm

            2) Inspect contract
               runllm inspect app.rllm

            3) Run app
               runllm run app.rllm --input '{"text":"hello"}'

            4) Check quality and latency
               runllm stats app.rllm
               runllm exectime app.rllm
            """
        ).strip(),
        "credentials": textwrap.dedent(
            """
            Provider credential setup

            OpenAI example:
            export OPENAI_API_KEY="sk-..."

            Autoload precedence (highest -> lowest):
            1. process environment
            2. CWD .env
            3. ~/.config/runllm/.env
            4. ~/.config/runllm/config.yaml (non-secret defaults)

            Disable autoload:
            - CLI: --no-config-autoload
            - ENV: RUNLLM_NO_CONFIG_AUTOLOAD=1
            """
        ).strip(),
        "config": textwrap.dedent(
            """
            Runtime config defaults

            File: ~/.config/runllm/config.yaml

            Supported keys:
            runtime.default_model
            runtime.default_max_retries
            runtime.default_ollama_auto_pull
            provider.ollama_api_base
            """
        ).strip(),
    }


def help_topics_json() -> dict[str, Any]:
    return {
        "rllm": {
            "required_fields": [
                "name",
                "description",
                "version",
                "author",
                "max_context_window",
                "input_schema",
                "output_schema",
                "llm",
                "llm_params",
            ],
            "optional_fields": ["runllm_compat", "metadata", "recommended_models", "tags", "uses", "recovery_prompt"],
            "templating": ["{{input.<path>}}", "{{uses.<dep>.<path>}}"],
            "optional_sections": ["<<<RECOVERY>>>", "```rllm-python pre/post"],
            "docs": [
                "docs/rllm-spec.md",
                "docs/schema-cookbook.md",
                "docs/recovery-playbook.md",
            ],
        },
        "schema": {
            "recommendations": [
                "Use type: object",
                "Use required for mandatory keys",
                "Use additionalProperties: false for strict outputs",
                "Prefer enums over free text where possible",
            ]
        },
        "recovery": {
            "pattern": [
                "State previous response failed validation",
                "Require only JSON object",
                "List exact expected keys",
                "Forbid prose/markdown/schema definitions",
            ]
        },
        "composition": {
            "stage_contract_checklist": [
                "One stage has one primary responsibility",
                "Input/output schemas are minimal and strict",
                "Downstream-required keys are stable",
                "Failure behavior is explicit",
                "Deterministic verification is preferred when possible",
            ],
            "interface_rules": [
                "Keep intermediate key names stable across stages",
                "Prefer additive schema evolution",
                "Preserve provenance fields in evidence artifacts",
                "Avoid hidden coupling to prose conventions",
            ],
            "evidence_lifecycle": [
                "retrieved",
                "filtered",
                "verified",
                "synthesized",
            ],
            "runtime_guidance": [
                "Cap discovery fan-out early",
                "Avoid truncating verified evidence late",
                "Parallelize independent retrieval",
                "Merge deterministically with dedupe",
                "Fallback to sequential on transient parallel failures",
            ],
            "docs": [
                "docs/composition.md",
                "docs/multistep-apps.md",
                "docs/authoring-guide.md",
                "docs/schema-cookbook.md",
            ],
        },
        "examples": {
            "commands": [
                "runllm validate app.rllm",
                "runllm inspect app.rllm",
                "runllm run app.rllm --input '{\"text\":\"hello\"}'",
                "runllm stats app.rllm",
                "runllm exectime app.rllm",
            ]
        },
        "credentials": {
            "autoload_precedence": [
                "process_env",
                "cwd_dotenv",
                "user_dotenv",
                "user_config_yaml",
            ],
            "common_env_vars": [
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
                "GOOGLE_API_KEY",
                "MISTRAL_API_KEY",
                "COHERE_API_KEY",
            ],
        },
        "config": {
            "path": "~/.config/runllm/config.yaml",
            "runtime_keys": [
                "runtime.default_model",
                "runtime.default_max_retries",
                "runtime.default_ollama_auto_pull",
            ],
            "provider_keys": ["provider.ollama_api_base"],
        },
    }
