from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from runllm.config import get_runtime_config, load_runtime_config
from runllm.errors import RunLLMError, make_error
from runllm.executor import estimate_execution_time_ms, run_program
from runllm.help_content import HELP_TOPICS, help_topics_json, help_topics_text
from runllm.models import RunOptions
from runllm.onboarding import cmd_onboard
from runllm.opencode import bundle_project, install_opencode_integration
from runllm.parser import parse_rllm_file
from runllm.stats import StatsStore


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


def cmd_help(args: argparse.Namespace) -> int:
    topic = args.topic
    if args.format == "json":
        payload = {
            "topic": topic,
            "content": help_topics_json()[topic],
        }
        _print_json(payload)
        return 0

    print(help_topics_text()[topic])
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
    python_memory_limit_mb = args.python_memory_limit_mb
    if python_memory_limit_mb < 0:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="python_memory_limit_mb must be a non-negative integer.",
            details={"python_memory_limit_mb": python_memory_limit_mb},
            recovery_hint="Set --python-memory-limit-mb to 0 or greater.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    if args.debug_prompt_wrap <= 0:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="debug_prompt_wrap must be a positive integer.",
            details={"debug_prompt_wrap": args.debug_prompt_wrap},
            recovery_hint="Set --debug-prompt-wrap to 1 or greater.",
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
        python_memory_limit_mb=python_memory_limit_mb,
        debug_prompt_file=args.debug_prompt_file,
        debug_prompt_stdout=args.debug_prompt_stdout,
        debug_prompt_wrap=args.debug_prompt_wrap,
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


def cmd_mcp_serve(args: argparse.Namespace) -> int:
    project = str(args.project).strip()
    if not project:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="project must be a non-empty string.",
            details={"project": args.project},
            recovery_hint="Pass --project with a non-empty value.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    from runllm.mcp_server import run_mcp_server

    repo_root_arg = getattr(args, "repo_root", None)
    repo_root: Path | None = None
    if repo_root_arg is not None:
        repo_root_text = str(repo_root_arg).strip()
        if not repo_root_text:
            raise make_error(
                error_code="RLLM_002",
                error_type="MetadataValidationError",
                message="repo_root must be a non-empty string when provided.",
                details={"repo_root": repo_root_arg},
                recovery_hint="Pass --repo-root with a valid directory path or omit it.",
                doc_ref="docs/errors.md#RLLM_002",
            )
        repo_root = Path(repo_root_text).resolve()

    run_mcp_server(
        project=project,
        repo_root=repo_root,
        autoload_config=getattr(args, "_autoload_config", None),
        trusted_workflows=bool(getattr(args, "trusted_workflows", False)),
    )
    return 0


def cmd_mcp_install_opencode(args: argparse.Namespace) -> int:
    payload = install_opencode_integration(
        repo_root=getattr(args, "repo_root", None),
        runllm_bin=args.runllm_bin,
        agent_file=args.agent_file,
        force=args.force,
    )
    _print_json(payload)
    return 0


def cmd_bundle(args: argparse.Namespace) -> int:
    payload = bundle_project(
        project_name=args.project,
        repo_root=args.repo_root,
        bin_dir=args.bin_dir,
    )
    _print_json(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runllm",
        description="Run and compose .rllm apps with typed contracts.",
        formatter_class=_HelpFormatter,
        epilog=(
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
        metavar="{run,validate,inspect,stats,exectime,onboard,bundle,help,mcp}",
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
    run_p.add_argument(
        "--python-memory-limit-mb",
        metavar="MB",
        type=int,
        default=256,
        help="Memory cap for untrusted python blocks; set 0 to disable",
    )
    run_p.add_argument(
        "--debug-prompt-file",
        metavar="PATH",
        help="Write exact prompts sent to model to a formatted debug file",
    )
    run_p.add_argument(
        "--debug-prompt-stdout",
        action="store_true",
        help="Print exact prompts sent to model to stderr (keeps JSON stdout clean)",
    )
    run_p.add_argument(
        "--debug-prompt-wrap",
        metavar="N",
        type=int,
        default=100,
        help="Line wrap width used for prompt debug output",
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

    b_p = sub.add_parser(
        "bundle",
        help="Bundle a project into a standalone CLI shim",
        description="Create a wrapper script for a project staging script.",
        formatter_class=_HelpFormatter,
    )
    b_p.add_argument("project", metavar="NAME", help="Project name under userlib/")
    b_p.add_argument(
        "--repo-root",
        metavar="PATH",
        default=None,
        help="Repository root (defaults to current working directory).",
    )
    b_p.add_argument(
        "--bin-dir",
        metavar="PATH",
        default=None,
        help="Target directory for the shim script (defaults to .bin/ in repo root).",
    )
    b_p.set_defaults(func=cmd_bundle)

    h_p = sub.add_parser(
        "help",
        help="Show LLM-oriented authoring help topics",
        description="Show detailed help for building .rllm apps.",
        formatter_class=_HelpFormatter,
    )
    h_p.add_argument(
        "topic",
        choices=list(HELP_TOPICS),
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

    m_p = sub.add_parser(
        "mcp",
        help="Run minimal MCP server",
        description="MCP utilities for serving and OpenCode integration.",
        formatter_class=_HelpFormatter,
    )
    m_sub = m_p.add_subparsers(dest="mcp_command", required=True, metavar="{serve,install-opencode}")
    m_serve = m_sub.add_parser(
        "serve",
        help="Serve MCP tools for one project",
        description=(
            "Start MCP stdio server exposing list/invoke tools for programs and workflows "
            "for one project scope."
        ),
        formatter_class=_HelpFormatter,
    )
    m_serve.add_argument(
        "--project",
        metavar="NAME",
        required=True,
        help="Project scope name (userlib/<project> or rllmlib).",
    )
    m_serve.add_argument(
        "--trusted-workflows",
        action="store_true",
        help="Enable invoke_workflow execution of Python workflow entrypoints (trusted repos only).",
    )
    m_serve.add_argument(
        "--repo-root",
        metavar="PATH",
        default=None,
        help="Repository root used for MCP discovery (defaults to current working directory).",
    )
    m_serve.set_defaults(func=cmd_mcp_serve)

    m_install = m_sub.add_parser(
        "install-opencode",
        help="Install runllm MCP into OpenCode config",
        description=(
            "Upsert OpenCode opencode.json MCP entry and create a runllm builder agent prompt file."
        ),
        formatter_class=_HelpFormatter,
    )
    m_install.add_argument(
        "--runllm-bin",
        metavar="PATH_OR_CMD",
        default="runllm",
        help="Executable or path used in MCP command array.",
    )
    m_install.add_argument(
        "--repo-root",
        metavar="PATH",
        default=None,
        help="Repository root pinned into generated MCP command arrays.",
    )
    m_install.add_argument(
        "--agent-file",
        metavar="FILENAME",
        default="runllm-rllm-builder.md",
        help="Builder agent filename created under OpenCode agent directory.",
    )
    m_install.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing builder MCP entry and agent file.",
    )
    m_install.set_defaults(func=cmd_mcp_install_opencode)

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
