from __future__ import annotations

import pytest

from runllm.errors import RunLLMError
from runllm.litellm_params import validate_litellm_params


def test_validate_litellm_params_accepts_supported_keys() -> None:
    validate_litellm_params({"temperature": 0, "format": "json", "top_p": 1})


def test_validate_litellm_params_rejects_unsupported_keys() -> None:
    with pytest.raises(RunLLMError) as exc:
        validate_litellm_params({"temperature": 0, "bad_key": True})

    assert exc.value.payload.error_code == "RLLM_003"
    assert "bad_key" in exc.value.payload.details["unsupported_keys"]
