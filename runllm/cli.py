from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any

import yaml

from runllm.config import get_runtime_config, load_runtime_config
from runllm.errors import RunLLMError, make_error
from runllm.executor import estimate_execution_time_ms, run_program
from runllm.models import RunOptions
from runllm.onboarding import cmd_onboard
from runllm.parser import parse_rllm_file
from runllm.stats import StatsStore


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


def _help_topics_text() -> dict[str, str]:
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


def _help_topics_json() -> dict[str, Any]:
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


def cmd_help(args: argparse.Namespace) -> int:
    topic = args.topic
    if args.format == "json":
        payload = {
            "topic": topic,
            "content": _help_topics_json()[topic],
        }
        _print_json(payload)
        return 0

    print(_help_topics_text()[topic])
    return 0


def _load_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.input_file:
        p = Path(args.input_file)
        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Input file must contain a JSON/YAML object.")
        return data
    if args.input:
        parsed = json.loads(args.input)
        if not isinstance(parsed, dict):
            raise ValueError("--input must be a JSON object.")
        return parsed
    return {}


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def cmd_run(args: argparse.Namespace) -> int:
    input_payload = _load_input(args)
    cfg = get_runtime_config()
    retries = args.max_retries if args.max_retries is not None else cfg.default_max_retries
    if retries < 0:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="max_retries must be a non-negative integer.",
            details={"max_retries": retries},
            recovery_hint="Set --max-retries to 0 or greater.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    model = args.model or cfg.default_model
    if args.ollama_auto_pull is None:
        ollama_auto_pull = cfg.default_ollama_auto_pull
    else:
        ollama_auto_pull = args.ollama_auto_pull
    options = RunOptions(
        model_override=model,
        max_retries=retries,
        verbose=args.verbose,
        ollama_auto_pull=ollama_auto_pull,
        trusted_python=args.trusted_python,
    )
    output = run_program(
        args.file,
        input_payload,
        options,
        autoload_config=getattr(args, "_autoload_config", None),
    )
    _print_json(output)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    program = parse_rllm_file(args.file)
    result = {
        "ok": True,
        "path": str(program.path),
        "name": program.name,
        "version": program.version,
    }
    _print_json(result)
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    program = parse_rllm_file(args.file)
    result = {
        "path": str(program.path),
        "name": program.name,
        "description": program.description,
        "version": program.version,
        "author": program.author,
        "max_context_window": program.max_context_window,
        "input_schema": program.input_schema,
        "output_schema": program.output_schema,
        "llm": program.llm,
        "llm_params": program.llm_params,
        "uses": [{"name": u.name, "path": str(u.path), "with": u.with_map} for u in program.uses],
        "recommended_models": program.recommended_models,
        "metadata": program.metadata,
    }
    _print_json(result)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    p = str(Path(args.file).resolve())
    result = StatsStore().aggregate(app_path=p, model=args.model)
    _print_json(result)
    return 0


def cmd_exectime(args: argparse.Namespace) -> int:
    result = estimate_execution_time_ms(args.file, model=args.model)
    _print_json(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runllm",
        description="Run and compose .rllm apps with typed contracts.",
        formatter_class=_HelpFormatter,
        epilog=textwrap.dedent(
            """
            Quick start:
              runllm validate examples/summary.rllm
              runllm run examples/summary.rllm --input '{"text":"hello"}'

            LLM authoring help:
              runllm help rllm
              runllm help schema
              runllm help recovery
            """
        ),
    )
    parser.add_argument(
        "--no-config-autoload",
        action="store_true",
        help="Disable automatic loading of .env/config files.",
    )
    sub = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="{run,validate,inspect,stats,exectime,onboard,help}",
    )

    run_p = sub.add_parser(
        "run",
        help="Execute a .rllm program",
        description="Execute a .rllm app with optional model and retry overrides.",
        formatter_class=_HelpFormatter,
    )
    run_p.add_argument("file", metavar="FILE", help="Path to .rllm file")
    run_p.add_argument("--input", metavar="JSON", help="Inline JSON input object")
    run_p.add_argument("--input-file", metavar="PATH", help="JSON/YAML input file")
    run_p.add_argument("--model", metavar="MODEL", help="Override model (e.g. ollama/llama3.1:8b)")
    run_p.add_argument("--max-retries", metavar="N", type=int, help="Override retry count for schema recovery")
    run_p.add_argument("--verbose", action="store_true", help="Enable verbose mode for diagnostics")
    run_p.add_argument(
        "--ollama-auto-pull",
        action="store_true",
        default=None,
        help="Automatically pull missing Ollama models when needed",
    )
    run_p.add_argument(
        "--trusted-python",
        action="store_true",
        help="Run python blocks with unrestricted builtins (unsafe)",
    )
    run_p.set_defaults(func=cmd_run)

    v_p = sub.add_parser(
        "validate",
        help="Validate .rllm syntax and metadata",
        description="Validate .rllm file shape, required metadata, and parameter support.",
        formatter_class=_HelpFormatter,
    )
    v_p.add_argument("file", metavar="FILE", help="Path to .rllm file")
    v_p.set_defaults(func=cmd_validate)

    i_p = sub.add_parser(
        "inspect",
        help="Inspect parsed app contract",
        description="Print parsed metadata, schemas, model params, and uses dependencies.",
        formatter_class=_HelpFormatter,
    )
    i_p.add_argument("file", metavar="FILE", help="Path to .rllm file")
    i_p.set_defaults(func=cmd_inspect)

    s_p = sub.add_parser(
        "stats",
        help="Show observed runtime metrics",
        description="Show stored stats such as schema compliance, latency, and token usage.",
        formatter_class=_HelpFormatter,
    )
    s_p.add_argument("file", metavar="FILE", help="Path to .rllm file")
    s_p.add_argument("--model", metavar="MODEL", help="Filter stats by model")
    s_p.set_defaults(func=cmd_stats)

    e_p = sub.add_parser(
        "exectime",
        help="Estimate runtime from observed data",
        description="Estimate execution time from observed parent + dependency averages.",
        formatter_class=_HelpFormatter,
    )
    e_p.add_argument("file", metavar="FILE", help="Path to .rllm file")
    e_p.add_argument("--model", metavar="MODEL", help="Estimate for one model only")
    e_p.set_defaults(func=cmd_exectime)

    o_p = sub.add_parser(
        "onboard",
        help="Interactive first-app onboarding flow",
        description="Guide setup, connectivity test, and first .rllm app creation.",
        formatter_class=_HelpFormatter,
    )
    o_p.add_argument("--model", metavar="MODEL", help="Preselect model for onboarding flow")
    o_p.add_argument(
        "--resume",
        action="store_true",
        help="Resume defaults from saved onboarding session file",
    )
    o_p.add_argument(
        "--session-file",
        metavar="PATH",
        help="Custom onboarding session state path",
    )
    o_p.add_argument(
        "--scaffold-file",
        metavar="PATH",
        help="Custom onboarding scaffold profile output path",
    )
    o_p.add_argument(
        "--no-save-scaffold",
        action="store_true",
        help="Skip writing reusable scaffold profile file",
    )
    o_p.set_defaults(func=cmd_onboard)

    h_p = sub.add_parser(
        "help",
        help="Show LLM-oriented authoring help topics",
        description="Show detailed help for building .rllm apps.",
        formatter_class=_HelpFormatter,
    )
    h_p.add_argument(
        "topic",
        choices=["rllm", "schema", "recovery", "examples", "credentials", "config"],
        metavar="TOPIC",
        help="Help topic to print",
    )
    h_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="json",
        help="Output format for help topic",
    )
    h_p.set_defaults(func=cmd_help)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "help":
            return int(args.func(args))
        autoload = not args.no_config_autoload and os.environ.get("RUNLLM_NO_CONFIG_AUTOLOAD") != "1"
        load_runtime_config(autoload=autoload)
        setattr(args, "_autoload_config", autoload)
        return int(args.func(args))
    except RunLLMError as exc:
        _print_json(exc.payload.to_dict())
        return 1
    except Exception as exc:
        payload = {
            "error_code": "RLLM_999",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "details": {},
            "expected_schema": None,
            "received_payload": None,
            "recovery_hint": "Inspect stack trace with --verbose or validate input format.",
            "doc_ref": "docs/errors.md#RLLM_999",
        }
        _print_json(payload)
        return 1


if __name__ == "__main__":
    sys.exit(main())
