from __future__ import annotations

import subprocess

from runllm.errors import make_error


def _run_ollama(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def ollama_has_model(model: str) -> bool:
    proc = _run_ollama(["ollama", "list"])
    if proc.returncode != 0:
        return False
    return any(line.split()[0] == model for line in proc.stdout.splitlines() if line.strip())


def ensure_ollama_model(model: str, auto_pull: bool) -> None:
    if ollama_has_model(model):
        return
    if not auto_pull:
        raise make_error(
            error_code="RLLM_010",
            error_type="OllamaModelMissingError",
            message="Required Ollama model is not available locally.",
            details={"model": model},
            recovery_hint="Run with --ollama-auto-pull or execute: ollama pull <model>",
            doc_ref="docs/errors.md#RLLM_010",
        )

    proc = _run_ollama(["ollama", "pull", model])
    if proc.returncode != 0:
        raise make_error(
            error_code="RLLM_010",
            error_type="OllamaModelMissingError",
            message="Failed to pull Ollama model.",
            details={"model": model, "stderr": proc.stderr.strip()},
            recovery_hint="Verify model name and local resources, then retry.",
            doc_ref="docs/errors.md#RLLM_010",
        )
