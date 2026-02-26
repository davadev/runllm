from __future__ import annotations

import signal
import threading
from contextlib import ExitStack
from contextlib import contextmanager
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - non-POSIX platforms
    resource = None

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


@contextmanager
def _memory_limit(memory_limit_mb: int):
    if resource is None or memory_limit_mb <= 0 or not hasattr(resource, "RLIMIT_AS"):
        yield
        return
    if threading.active_count() > 1:
        # RLIMIT_AS is process-wide. In multithreaded contexts, applying it here can
        # impact unrelated work running concurrently in other threads.
        yield
        return

    bytes_limit = int(memory_limit_mb) * 1024 * 1024
    try:
        original_soft, original_hard = resource.getrlimit(resource.RLIMIT_AS)
    except Exception:
        # Best effort only; continue without memory limiting if unavailable.
        yield
        return
    infinity_values = {-1}
    rlim_infinity = getattr(resource, "RLIM_INFINITY", None)
    if isinstance(rlim_infinity, int):
        infinity_values.add(rlim_infinity)

    def is_infinite(value: int) -> bool:
        return int(value) in infinity_values

    if is_infinite(original_soft):
        target_soft = bytes_limit
    else:
        target_soft = min(bytes_limit, int(original_soft))
    if not is_infinite(original_hard):
        target_soft = min(target_soft, int(original_hard))
    if target_soft == int(original_soft):
        # No stronger constraint can be applied without raising limits.
        yield
        return

    try:
        resource.setrlimit(resource.RLIMIT_AS, (target_soft, original_hard))
    except Exception:
        # Some systems disallow RLIMIT_AS changes for this process.
        yield
        return

    try:
        yield
    finally:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (original_soft, original_hard))
        except Exception:
            # Best-effort restore; avoid masking original execution errors.
            pass


def execute_python_block(
    code: str,
    context: dict[str, Any],
    *,
    block_name: str,
    trusted: bool,
    timeout_seconds: int = 2,
    memory_limit_mb: int = 256,
) -> dict[str, Any]:
    global_ns: dict[str, Any]
    if trusted:
        global_ns = {"__builtins__": __builtins__}
    else:
        global_ns = {"__builtins__": SAFE_BUILTINS}
    local_ns: dict[str, Any] = {"context": dict(context), "result": {}}

    try:
        with ExitStack() as stack:
            stack.enter_context(_timeout(timeout_seconds))
            if not trusted:
                stack.enter_context(_memory_limit(memory_limit_mb))
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
