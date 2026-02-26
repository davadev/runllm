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


def test_execute_python_block_applies_memory_limit_when_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, tuple[int, int]]] = []

    class DummyResource:
        RLIMIT_AS = 9
        RLIM_INFINITY = -1

        @staticmethod
        def getrlimit(limit: int) -> tuple[int, int]:
            assert limit == DummyResource.RLIMIT_AS
            return (DummyResource.RLIM_INFINITY, DummyResource.RLIM_INFINITY)

        @staticmethod
        def setrlimit(limit: int, values: tuple[int, int]) -> None:
            calls.append((limit, values))

    monkeypatch.setattr("runllm.pyblocks.resource", DummyResource)
    monkeypatch.setattr("runllm.pyblocks.threading.active_count", lambda: 1)

    out = execute_python_block(
        "result = {'ok': True}",
        {},
        block_name="pre",
        trusted=False,
        memory_limit_mb=32,
    )

    assert out == {"ok": True}
    assert len(calls) == 2
    assert calls[0][0] == DummyResource.RLIMIT_AS
    assert calls[0][1][0] == 32 * 1024 * 1024


def test_execute_python_block_continues_if_memory_limit_not_settable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyResource:
        RLIMIT_AS = 9
        RLIM_INFINITY = -1

        @staticmethod
        def getrlimit(limit: int) -> tuple[int, int]:
            assert limit == DummyResource.RLIMIT_AS
            return (DummyResource.RLIM_INFINITY, DummyResource.RLIM_INFINITY)

        @staticmethod
        def setrlimit(limit: int, values: tuple[int, int]) -> None:
            raise OSError("not allowed")

    monkeypatch.setattr("runllm.pyblocks.resource", DummyResource)
    monkeypatch.setattr("runllm.pyblocks.threading.active_count", lambda: 1)

    out = execute_python_block(
        "result = {'ok': True}",
        {},
        block_name="pre",
        trusted=False,
        memory_limit_mb=32,
    )

    assert out == {"ok": True}


def test_execute_python_block_never_raises_existing_soft_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, tuple[int, int]]] = []

    class DummyResource:
        RLIMIT_AS = 9
        RLIM_INFINITY = -1

        @staticmethod
        def getrlimit(limit: int) -> tuple[int, int]:
            assert limit == DummyResource.RLIMIT_AS
            return (128 * 1024 * 1024, DummyResource.RLIM_INFINITY)

        @staticmethod
        def setrlimit(limit: int, values: tuple[int, int]) -> None:
            calls.append((limit, values))

    monkeypatch.setattr("runllm.pyblocks.resource", DummyResource)

    out = execute_python_block(
        "result = {'ok': True}",
        {},
        block_name="pre",
        trusted=False,
        memory_limit_mb=256,
    )

    assert out == {"ok": True}
    assert calls == []


def test_execute_python_block_trusted_skips_memory_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, tuple[int, int]]] = []

    class DummyResource:
        RLIMIT_AS = 9
        RLIM_INFINITY = -1

        @staticmethod
        def getrlimit(limit: int) -> tuple[int, int]:
            assert limit == DummyResource.RLIMIT_AS
            return (DummyResource.RLIM_INFINITY, DummyResource.RLIM_INFINITY)

        @staticmethod
        def setrlimit(limit: int, values: tuple[int, int]) -> None:
            calls.append((limit, values))

    monkeypatch.setattr("runllm.pyblocks.resource", DummyResource)

    out = execute_python_block(
        "result = {'ok': True}",
        {},
        block_name="pre",
        trusted=True,
        memory_limit_mb=32,
    )

    assert out == {"ok": True}
    assert calls == []


def test_execute_python_block_skips_memory_limit_in_multithreaded_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, tuple[int, int]]] = []

    class DummyResource:
        RLIMIT_AS = 9
        RLIM_INFINITY = -1

        @staticmethod
        def getrlimit(limit: int) -> tuple[int, int]:
            assert limit == DummyResource.RLIMIT_AS
            return (DummyResource.RLIM_INFINITY, DummyResource.RLIM_INFINITY)

        @staticmethod
        def setrlimit(limit: int, values: tuple[int, int]) -> None:
            calls.append((limit, values))

    monkeypatch.setattr("runllm.pyblocks.resource", DummyResource)
    monkeypatch.setattr("runllm.pyblocks.threading.active_count", lambda: 2)

    out = execute_python_block(
        "result = {'ok': True}",
        {},
        block_name="pre",
        trusted=False,
        memory_limit_mb=32,
    )

    assert out == {"ok": True}
    assert calls == []


def test_execute_python_block_continues_if_getrlimit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyResource:
        RLIMIT_AS = 9
        RLIM_INFINITY = -1

        @staticmethod
        def getrlimit(limit: int) -> tuple[int, int]:
            assert limit == DummyResource.RLIMIT_AS
            raise OSError("not supported")

        @staticmethod
        def setrlimit(limit: int, values: tuple[int, int]) -> None:
            raise AssertionError("setrlimit should not be called")

    monkeypatch.setattr("runllm.pyblocks.resource", DummyResource)
    monkeypatch.setattr("runllm.pyblocks.threading.active_count", lambda: 1)

    out = execute_python_block(
        "result = {'ok': True}",
        {},
        block_name="pre",
        trusted=False,
        memory_limit_mb=32,
    )

    assert out == {"ok": True}
