from __future__ import annotations

import signal
from contextlib import contextmanager
from typing import Any

from runllm.errors import make_error


SAFE_BUILTINS = {
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "enumerate": enumerate,
    "range": range,
    "zip": zip,
}


@contextmanager
def _timeout(seconds: int):
    def handler(signum: int, frame: Any) -> None:
        raise TimeoutError("Python block timed out")

    original = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original)


def execute_python_block(
    code: str,
    context: dict[str, Any],
    *,
    block_name: str,
    trusted: bool,
    timeout_seconds: int = 2,
) -> dict[str, Any]:
    global_ns: dict[str, Any]
    if trusted:
        global_ns = {"__builtins__": __builtins__}
    else:
        global_ns = {"__builtins__": SAFE_BUILTINS}
    local_ns: dict[str, Any] = {"context": dict(context), "result": {}}

    try:
        with _timeout(timeout_seconds):
            exec(code, global_ns, local_ns)
    except Exception as exc:
        raise make_error(
            error_code="RLLM_009",
            error_type="PythonBlockExecutionError",
            message=f"Python block '{block_name}' failed.",
            details={"exception": type(exc).__name__, "reason": str(exc)},
            received_payload={"context": context},
            recovery_hint="Fix python block code or run with --trusted-python if intentionally using broader features.",
            doc_ref="docs/errors.md#RLLM_009",
        )

    result = local_ns.get("result")
    if result is None:
        return {}
    if not isinstance(result, dict):
        raise make_error(
            error_code="RLLM_009",
            error_type="PythonBlockExecutionError",
            message="Python block result must be a dict.",
            details={"actual_type": type(result).__name__},
            received_payload=result,
            recovery_hint="Set result = {...} inside python block.",
            doc_ref="docs/errors.md#RLLM_009",
        )
    return result
