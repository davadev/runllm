from __future__ import annotations

import json
import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

from runllm.config import get_runtime_config, load_runtime_config, required_provider_key
from runllm.errors import RunLLMError, make_error
from runllm.models import RLLMProgram, RunOptions, UsageMetrics
from runllm.ollama import ensure_ollama_model
from runllm.parser import parse_rllm_file
from runllm.pyblocks import execute_python_block
from runllm.stats import StatsStore
from runllm.templating import render_template
from runllm.utils import estimate_context_tokens, estimate_tokens
from runllm.validation import (
    extract_json_object_candidates,
    parse_model_json_payload,
    validate_json_schema_instance,
)


def _extract_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except Exception as exc:
        raise make_error(
            error_code="RLLM_011",
            error_type="ExecutionError",
            message="Unexpected LiteLLM response shape.",
            details={"reason": str(exc)},
            received_payload=str(response),
            recovery_hint="Verify provider/model response compatibility.",
            doc_ref="docs/errors.md#RLLM_011",
        )
    if not isinstance(content, str):
        raise make_error(
            error_code="RLLM_011",
            error_type="ExecutionError",
            message="Unexpected LiteLLM response content type.",
            details={"actual_type": type(content).__name__},
            received_payload=content,
            recovery_hint="Use a provider/model combination that returns string message content.",
            doc_ref="docs/errors.md#RLLM_011",
        )
    return content


def _extract_usage(response: Any, prompt: str, content: str, elapsed_ms: float) -> UsageMetrics:
    usage = getattr(response, "usage", None)
    if usage is None:
        prompt_tokens = estimate_tokens(prompt)
        completion_tokens = estimate_tokens(content)
        total_tokens = prompt_tokens + completion_tokens
    else:
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
    return UsageMetrics(
        latency_ms=elapsed_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _prepare_model(program: RLLMProgram, options: RunOptions) -> str:
    model = options.model_override or str(program.llm.get("model", "")).strip()
    if not model:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="llm.model is required.",
            details={"llm": program.llm},
            recovery_hint="Set llm.model in .rllm frontmatter or pass --model.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    return model


def _ensure_provider_credentials(model: str) -> None:
    required = required_provider_key(model)
    if required is None:
        return
    provider, key_name = required
    if os.environ.get(key_name):
        return
    cfg = get_runtime_config()
    raise make_error(
        error_code="RLLM_014",
        error_type="MissingProviderCredentialError",
        message="Provider credential is missing for selected model.",
        details={
            "provider": provider,
            "missing_env_var": key_name,
            "model": model,
            "checked_sources": cfg.loaded_sources or [],
        },
        recovery_hint=f"Set {key_name} in environment or .env, then retry.",
        doc_ref="docs/errors.md#RLLM_014",
    )


def _validate_context(program: RLLMProgram, payload: dict[str, Any], prompt: str) -> None:
    estimated = estimate_context_tokens(payload, prompt)
    if estimated > program.max_context_window:
        raise make_error(
            error_code="RLLM_012",
            error_type="ContextWindowExceededError",
            message="Input exceeds app max_context_window.",
            details={
                "estimated_tokens": estimated,
                "max_context_window": program.max_context_window,
                "app": program.name,
            },
            recovery_hint="Send smaller input or increase max_context_window in app metadata.",
            doc_ref="docs/errors.md#RLLM_012",
        )


def _schema_example(schema: dict[str, Any], depth: int = 0) -> Any:
    if depth > 4:
        return None
    if not isinstance(schema, dict):
        return None

    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null = [item for item in schema_type if item != "null"]
        schema_type = non_null[0] if non_null else schema_type[0]

    if schema_type == "object":
        props = schema.get("properties")
        required = schema.get("required")
        if not isinstance(props, dict):
            return {}
        if not isinstance(required, list):
            required = list(props.keys())
        out: dict[str, Any] = {}
        for key in required:
            if not isinstance(key, str):
                continue
            child_schema = props.get(key, {})
            out[key] = _schema_example(child_schema, depth + 1)
        return out

    if schema_type == "array":
        items = schema.get("items", {})
        return [_schema_example(items, depth + 1)]

    if schema_type == "string":
        return "example"
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0.0
    if schema_type == "boolean":
        return False
    if schema_type == "null":
        return None

    return None


def _build_output_contract(output_schema: dict[str, Any]) -> str:
    schema_json = json.dumps(output_schema, indent=2, ensure_ascii=True)
    example_json = json.dumps(_schema_example(output_schema), indent=2, ensure_ascii=True)
    return (
        "Output contract:\n"
        "- Return ONLY one valid JSON object.\n"
        "- No markdown, no prose, no extra wrappers.\n\n"
        "Output schema (JSON):\n"
        f"{schema_json}\n\n"
        "Example output (JSON):\n"
        f"{example_json}"
    )


def _build_attempt_prompt(
    *,
    rendered_prompt: str,
    output_schema: dict[str, Any],
    recovery_prompt: str,
    attempt: int,
) -> str:
    contract = _build_output_contract(output_schema)
    prompt = f"{rendered_prompt}\n\n{contract}"
    if attempt == 0:
        return prompt
    if recovery_prompt:
        return f"{prompt}\n\nRecovery instruction:\n{recovery_prompt}"
    return (
        f"{prompt}\n\nRecovery instruction:\n"
        "Last attempt did not satisfy output_schema. Respond with only a valid JSON object that satisfies output_schema."
    )


def _format_prompt_preview(prompt: str, width: int) -> str:
    lines = prompt.splitlines()
    wrapped_lines: list[str] = []
    safe_width = width
    for line in lines:
        if not line.strip():
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(textwrap.wrap(line, width=safe_width, break_long_words=False, break_on_hyphens=False) or [""])
    return "\n".join(wrapped_lines)


def _emit_prompt_debug(
    *,
    options: RunOptions,
    attempt: int,
    max_attempts: int,
    model: str,
    prompt: str,
) -> None:
    if not options.debug_prompt_file and not options.debug_prompt_stdout:
        return
    header = (
        f"===== Attempt {attempt + 1}/{max_attempts} =====\n"
        f"Model: {model}\n"
        "----- Prompt (wrapped) -----\n"
    )
    wrapped = _format_prompt_preview(prompt, options.debug_prompt_wrap)
    raw = f"\n----- Prompt (raw) -----\n{prompt}\n"
    block = f"{header}{wrapped}{raw}"
    if options.debug_prompt_stdout:
        print(block, file=sys.stderr)
    if options.debug_prompt_file:
        out_path = Path(options.debug_prompt_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("a", encoding="utf-8") as handle:
            handle.write(block)


def _execute_uses(
    program: RLLMProgram,
    input_payload: dict[str, Any],
    options: RunOptions,
    *,
    completion_fn: Any,
    stack: tuple[str, ...],
    stats_store: StatsStore,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for dep in program.uses:
        dep_path = str(dep.path)
        if dep_path in stack:
            raise make_error(
                error_code="RLLM_008",
                error_type="DependencyResolutionError",
                message="Circular dependency detected in uses chain.",
                details={"cycle": list(stack) + [dep_path]},
                recovery_hint="Remove circular references in uses entries.",
                doc_ref="docs/errors.md#RLLM_008",
            )
        child_input: dict[str, Any] = {}
        for out_key, in_expr in dep.with_map.items():
            if isinstance(in_expr, str):
                child_input[out_key] = render_template(in_expr, {"input": input_payload, "uses": outputs})
            else:
                child_input[out_key] = in_expr
        child_output = _run_program_path(
            dep.path,
            child_input,
            options,
            stack=stack + (str(program.path),),
            stats_store=stats_store,
            completion_fn=completion_fn,
        )
        outputs[dep.name] = child_output
    return outputs


def _litellm_completion_call(
    *, model: str, prompt: str, llm_params: dict[str, Any], completion_fn: Any
) -> tuple[str, UsageMetrics]:
    started = time.perf_counter()
    response = completion_fn(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **llm_params,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    content = _extract_content(response)
    usage = _extract_usage(response, prompt, content, elapsed_ms)
    return content, usage


def _run_single(
    program: RLLMProgram,
    input_payload: dict[str, Any],
    options: RunOptions,
    *,
    completion_fn: Any,
    stack: tuple[str, ...],
    stats_store: StatsStore,
) -> dict[str, Any]:
    if options.max_retries < 0:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="max_retries must be a non-negative integer.",
            details={"max_retries": options.max_retries},
            recovery_hint="Set max_retries to 0 or greater.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    if options.debug_prompt_wrap <= 0:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="debug_prompt_wrap must be a positive integer.",
            details={"debug_prompt_wrap": options.debug_prompt_wrap},
            recovery_hint="Set debug_prompt_wrap to 1 or greater.",
            doc_ref="docs/errors.md#RLLM_002",
        )

    validate_json_schema_instance(instance=input_payload, schema=program.input_schema, phase="input")

    dep_outputs = _execute_uses(
        program,
        input_payload,
        options,
        completion_fn=completion_fn,
        stack=stack,
        stats_store=stats_store,
    )
    context = {"input": input_payload, "uses": dep_outputs}

    if program.python_pre:
        pre = execute_python_block(
            program.python_pre,
            context,
            block_name="pre",
            trusted=options.trusted_python,
            memory_limit_mb=options.python_memory_limit_mb,
        )
        context.update(pre)

    rendered_prompt = render_template(program.prompt, context)

    model = _prepare_model(program, options)
    _ensure_provider_credentials(model)
    if model.startswith("ollama/"):
        short_model = model.split("/", 1)[1]
        ensure_ollama_model(short_model, auto_pull=options.ollama_auto_pull)

    last_err: RunLLMError | None = None
    usage = UsageMetrics(latency_ms=0.0, prompt_tokens=0, completion_tokens=0, total_tokens=0)
    max_attempts = options.max_retries + 1

    for attempt in range(max_attempts):
        attempt_prompt = _build_attempt_prompt(
            rendered_prompt=rendered_prompt,
            output_schema=program.output_schema,
            recovery_prompt=program.recovery_prompt,
            attempt=attempt,
        )
        _validate_context(program, input_payload, attempt_prompt)
        _emit_prompt_debug(
            options=options,
            attempt=attempt,
            max_attempts=max_attempts,
            model=model,
            prompt=attempt_prompt,
        )
        content, usage = _litellm_completion_call(
            model=model,
            prompt=attempt_prompt,
            llm_params=program.llm_params,
            completion_fn=completion_fn,
        )
        try:
            out: dict[str, Any] | None = None
            candidates = extract_json_object_candidates(content)
            if not candidates:
                out = parse_model_json_payload(content)
                validate_json_schema_instance(instance=out, schema=program.output_schema, phase="output")
            else:
                for candidate in candidates:
                    try:
                        validate_json_schema_instance(
                            instance=candidate, schema=program.output_schema, phase="output"
                        )
                        out = candidate
                        break
                    except RunLLMError:
                        continue
                if out is None:
                    # Preserve best diagnostics from the direct parser path.
                    out = parse_model_json_payload(content)
                    validate_json_schema_instance(instance=out, schema=program.output_schema, phase="output")

            assert out is not None
            if program.python_post:
                post = execute_python_block(
                    program.python_post,
                    {"input": input_payload, "output": out, "uses": dep_outputs},
                    block_name="post",
                    trusted=options.trusted_python,
                    memory_limit_mb=options.python_memory_limit_mb,
                )
                if post:
                    out.update(post)
            stats_store.record_run(
                app_path=str(program.path),
                app_name=program.name,
                model=model,
                success=True,
                output_schema_ok=True,
                input_schema_ok=True,
                usage=usage,
            )
            return out
        except RunLLMError as exc:
            if exc.payload.error_code in {"RLLM_005", "RLLM_006", "RLLM_007"}:
                last_err = exc
                continue
            stats_store.record_run(
                app_path=str(program.path),
                app_name=program.name,
                model=model,
                success=False,
                output_schema_ok=False,
                input_schema_ok=True,
                usage=usage,
            )
            raise

    assert last_err is not None
    stats_store.record_run(
        app_path=str(program.path),
        app_name=program.name,
        model=model,
        success=False,
        output_schema_ok=False,
        input_schema_ok=True,
        usage=usage,
    )
    raise make_error(
        error_code="RLLM_013",
        error_type="RetryExhaustedError",
        message="Model did not satisfy output schema after retries.",
        details={"retries": options.max_retries},
        expected_schema=program.output_schema,
        received_payload=last_err.payload.received_payload,
        recovery_hint="Use a more schema-compliant model or tighten prompt instructions.",
        doc_ref="docs/errors.md#RLLM_013",
    )


def _run_program_path(
    program_path: str | Path,
    input_payload: dict[str, Any],
    options: RunOptions,
    *,
    stack: tuple[str, ...],
    stats_store: StatsStore,
    completion_fn: Any | None = None,
) -> dict[str, Any]:
    completion_impl = completion_fn
    if completion_impl is None:
        from litellm import completion as completion_impl  # lazy import

    program = parse_rllm_file(program_path)
    return _run_single(
        program,
        input_payload,
        options,
        completion_fn=completion_impl,
        stack=stack,
        stats_store=stats_store,
    )


def run_program(
    program_path: str | Path,
    input_payload: dict[str, Any],
    options: RunOptions | None = None,
    *,
    completion_fn: Any | None = None,
    autoload_config: bool | None = None,
) -> dict[str, Any]:
    if autoload_config is None:
        autoload = os.environ.get("RUNLLM_NO_CONFIG_AUTOLOAD") != "1"
    else:
        autoload = autoload_config
    load_runtime_config(autoload=autoload)
    if options is None:
        cfg = get_runtime_config()
        opts = RunOptions(
            model_override=cfg.default_model,
            max_retries=cfg.default_max_retries,
            ollama_auto_pull=cfg.default_ollama_auto_pull,
        )
    else:
        opts = options
    store = StatsStore()
    return _run_program_path(
        program_path,
        input_payload,
        opts,
        stack=(),
        stats_store=store,
        completion_fn=completion_fn,
    )


def estimate_execution_time_ms(program_path: str | Path, model: str | None = None) -> dict[str, Any]:
    p = str(Path(program_path).resolve())
    store = StatsStore()
    root_stats = store.aggregate(app_path=p, model=model)

    program = parse_rllm_file(program_path)
    deps = [str(dep.path) for dep in program.uses]
    children = [store.aggregate(app_path=dp, model=model) for dp in deps]

    root_est = float(root_stats.get("avg_latency_ms", 0.0) or 0.0)
    dep_est = sum(float(item.get("avg_latency_ms", 0.0) or 0.0) for item in children)
    return {
        "app_path": p,
        "model": model,
        "estimated_ms": root_est + dep_est,
        "root_avg_latency_ms": root_est,
        "deps_avg_latency_ms": dep_est,
        "dependency_count": len(deps),
    }
