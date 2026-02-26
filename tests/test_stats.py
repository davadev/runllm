from __future__ import annotations

from runllm.models import UsageMetrics
from runllm.stats import StatsStore


def test_stats_aggregate_empty_returns_total_runs_only(tmp_path) -> None:
    store = StatsStore(db_path=tmp_path / "stats.db")
    out = store.aggregate(app_path="/tmp/app.rllm")

    assert out["app_path"] == "/tmp/app.rllm"
    assert out["total_runs"] == 0


def test_stats_aggregate_counts_and_averages(tmp_path) -> None:
    store = StatsStore(db_path=tmp_path / "stats.db")

    store.record_run(
        app_path="/tmp/app.rllm",
        app_name="app",
        model="openai/gpt-4o-mini",
        success=True,
        output_schema_ok=True,
        input_schema_ok=True,
        usage=UsageMetrics(latency_ms=100.0, prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )
    store.record_run(
        app_path="/tmp/app.rllm",
        app_name="app",
        model="openai/gpt-4o-mini",
        success=False,
        output_schema_ok=False,
        input_schema_ok=True,
        usage=UsageMetrics(latency_ms=200.0, prompt_tokens=20, completion_tokens=10, total_tokens=30),
    )

    out = store.aggregate(app_path="/tmp/app.rllm", model="openai/gpt-4o-mini")

    assert out["total_runs"] == 2
    assert out["success_count"] == 1
    assert out["failure_count"] == 1
    assert out["avg_latency_ms"] == 150.0
    assert out["max_completion_tokens"] == 20


def test_stats_aggregate_model_filter(tmp_path) -> None:
    store = StatsStore(db_path=tmp_path / "stats.db")

    store.record_run(
        app_path="/tmp/app.rllm",
        app_name="app",
        model="openai/gpt-4o-mini",
        success=True,
        output_schema_ok=True,
        input_schema_ok=True,
        usage=UsageMetrics(latency_ms=50.0, prompt_tokens=5, completion_tokens=5, total_tokens=10),
    )
    store.record_run(
        app_path="/tmp/app.rllm",
        app_name="app",
        model="anthropic/claude-3-5-sonnet-20241022",
        success=True,
        output_schema_ok=True,
        input_schema_ok=True,
        usage=UsageMetrics(latency_ms=500.0, prompt_tokens=50, completion_tokens=50, total_tokens=100),
    )

    filtered = store.aggregate(app_path="/tmp/app.rllm", model="openai/gpt-4o-mini")

    assert filtered["total_runs"] == 1
    assert filtered["avg_latency_ms"] == 50.0
