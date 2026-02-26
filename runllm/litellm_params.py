from __future__ import annotations

from typing import Any

from runllm.errors import make_error


ALLOWED_LLM_PARAMS = {
    "temperature",
    "top_p",
    "max_tokens",
    "frequency_penalty",
    "presence_penalty",
    "stop",
    "n",
    "stream",
    "response_format",
    "seed",
    "timeout",
    "logit_bias",
    "user",
    "tools",
    "tool_choice",
    "parallel_tool_calls",
    "format",
}


def validate_litellm_params(params: dict[str, Any]) -> None:
    bad = sorted(k for k in params.keys() if k not in ALLOWED_LLM_PARAMS)
    if bad:
        raise make_error(
            error_code="RLLM_003",
            error_type="LLMParamValidationError",
            message="Unsupported llm_params keys were provided.",
            details={"unsupported_keys": bad, "allowed_keys": sorted(ALLOWED_LLM_PARAMS)},
            recovery_hint="Remove unsupported keys or move custom metadata to metadata.",
            doc_ref="docs/errors.md#RLLM_003",
        )
