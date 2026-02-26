from __future__ import annotations

import pytest

from runllm.errors import RunLLMError
from runllm.pyblocks import execute_python_block


def test_execute_python_block_untrusted_disallows_import() -> None:
    with pytest.raises(RunLLMError) as exc:
        execute_python_block(
            "import os\nresult = {'x': 1}",
            {},
            block_name="pre",
            trusted=False,
        )

    assert exc.value.payload.error_code == "RLLM_009"


def test_execute_python_block_trusted_allows_import() -> None:
    out = execute_python_block(
        "import os\nresult = {'sep': os.sep}",
        {},
        block_name="pre",
        trusted=True,
    )
    assert "sep" in out


def test_execute_python_block_result_none_returns_empty_dict() -> None:
    out = execute_python_block(
        "result = None",
        {},
        block_name="post",
        trusted=False,
    )
    assert out == {}


def test_execute_python_block_non_dict_result_raises() -> None:
    with pytest.raises(RunLLMError) as exc:
        execute_python_block(
            "result = 42",
            {},
            block_name="post",
            trusted=False,
        )

    assert exc.value.payload.error_code == "RLLM_009"


def test_execute_python_block_timeout_raises() -> None:
    with pytest.raises(RunLLMError) as exc:
        execute_python_block(
            "while True:\n    pass",
            {},
            block_name="pre",
            trusted=False,
            timeout_seconds=1,
        )

    assert exc.value.payload.error_code == "RLLM_009"
