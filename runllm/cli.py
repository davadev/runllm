from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from runllm.errors import RunLLMError
from runllm.executor import estimate_execution_time_ms, run_program
from runllm.models import RunOptions
from runllm.parser import parse_rllm_file
from runllm.stats import StatsStore


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
    options = RunOptions(
        model_override=args.model,
        max_retries=args.max_retries,
        verbose=args.verbose,
        ollama_auto_pull=args.ollama_auto_pull,
        trusted_python=args.trusted_python,
    )
    output = run_program(args.file, input_payload, options)
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
    parser = argparse.ArgumentParser(prog="runllm", description="Run .rllm apps")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Execute .rllm file")
    run_p.add_argument("file", help="Path to .rllm file")
    run_p.add_argument("--input", help="Inline JSON input object")
    run_p.add_argument("--input-file", help="JSON/YAML input file")
    run_p.add_argument("--model", help="Override model")
    run_p.add_argument("--max-retries", type=int, default=2)
    run_p.add_argument("--verbose", action="store_true")
    run_p.add_argument("--ollama-auto-pull", action="store_true")
    run_p.add_argument("--trusted-python", action="store_true")
    run_p.set_defaults(func=cmd_run)

    v_p = sub.add_parser("validate", help="Validate .rllm file")
    v_p.add_argument("file")
    v_p.set_defaults(func=cmd_validate)

    i_p = sub.add_parser("inspect", help="Inspect app metadata")
    i_p.add_argument("file")
    i_p.set_defaults(func=cmd_inspect)

    s_p = sub.add_parser("stats", help="Show app stats")
    s_p.add_argument("file")
    s_p.add_argument("--model")
    s_p.set_defaults(func=cmd_stats)

    e_p = sub.add_parser("exectime", help="Estimate app runtime")
    e_p.add_argument("file")
    e_p.add_argument("--model")
    e_p.set_defaults(func=cmd_exectime)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
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
