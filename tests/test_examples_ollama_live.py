from __future__ import annotations

import os
from pathlib import Path

import pytest

from runllm.executor import run_program
from runllm.models import RunOptions


pytestmark = pytest.mark.skipif(
    os.environ.get("RUNLLM_OLLAMA_TESTS") != "1",
    reason="Set RUNLLM_OLLAMA_TESTS=1 to run live Ollama integration tests.",
)


def _opts(model: str) -> RunOptions:
    return RunOptions(model_override=f"ollama/{model}", max_retries=5)


def test_live_intent_router() -> None:
    out = run_program(
        Path("examples/intent_router.rllm"),
        {"text": "I was charged twice and need a refund"},
        _opts("llama3.1:8b"),
    )
    assert out["intent"] in {"billing", "refund", "other", "technical", "sales"}
    assert 0 <= float(out["confidence"]) <= 1


def test_live_support_pipeline() -> None:
    out = run_program(
        Path("examples/support_pipeline.rllm"),
        {
            "ticket_text": "My subscription renewed unexpectedly; please cancel and refund.",
            "customer_tone": "upset",
        },
        _opts("llama3.1:8b"),
    )
    assert isinstance(out["reply"], str) and len(out["reply"]) > 10
    assert out["urgency"] in {"low", "medium", "high"}


def test_live_meeting_extractor() -> None:
    out = run_program(
        Path("examples/meeting_extractor.rllm"),
        {
            "transcript": (
                "Ana: We launch beta Tuesday. "
                "Mark: I own rollback plan by Monday. "
                "Risk remains vendor API latency."
            )
        },
        _opts("llama3.1:8b"),
    )
    assert isinstance(out["summary"], str)
    assert isinstance(out["action_items"], list)


def test_live_policy_guard() -> None:
    out = run_program(
        Path("examples/policy_guard.rllm"),
        {
            "draft_text": "Guaranteed returns in 24h, zero risk for everyone.",
            "prohibited_claims": ["guaranteed return", "zero risk"],
            "required_disclaimers": ["This is not financial advice."],
        },
        _opts("llama3.1:8b"),
    )
    assert isinstance(out["is_compliant"], bool)
    assert isinstance(out["violations"], list)


def test_live_schema_repair_proxy() -> None:
    out = run_program(
        Path("examples/schema_repair_proxy.rllm"),
        {
            "raw_model_output": "name=Chris age=33 country=SK",
            "target_schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name", "age"],
            },
            "task_context": "normalize contact card",
        },
        _opts("llama3.1:8b"),
    )
    assert isinstance(out["fixed_json"], dict)


def test_live_code_patch_planner_and_tests() -> None:
    plan = run_program(
        Path("examples/code_patch_planner.rllm"),
        {
            "issue": "Add --dry-run flag to CLI run command",
            "repo_context": "Python argparse based CLI",
            "constraints": ["No breaking changes", "Keep output JSON"],
        },
        _opts("qwen2.5-coder:7b"),
    )
    assert len(plan["plan_steps"]) > 0

    tests = run_program(
        Path("examples/test_case_generator.rllm"),
        {
            "function_contract": {
                "name": "safe_divide",
                "input": {"a": "number", "b": "number"},
                "output": "number",
                "errors": ["division by zero"],
            },
            "edge_conditions": ["a=0", "b=0", "very large numbers"],
        },
        _opts("qwen2.5-coder:7b"),
    )
    assert len(tests["unit_tests"]) > 0


def test_live_ocr_postprocessor() -> None:
    out = run_program(
        Path("examples/ocr_postprocessor.rllm"),
        {
            "ocr_text": "INVOICE #7781 DATE 2026-02-20 TOTAL 249.90 EUR",
            "doc_type": "invoice",
        },
        _opts("gemma3n:latest"),
    )
    assert isinstance(out["fields"], dict)


def test_live_risk_score_aggregator() -> None:
    out = run_program(
        Path("examples/risk_score_aggregator.rllm"),
        {
            "content_bundle": {
                "ticket_text": "Customer is upset, asks refund after bad experience.",
                "draft_text": "Guaranteed return, no risk.",
                "transcript": "Team discussed vendor latency and rollback plan gaps.",
            }
        },
        _opts("llama3.1:8b"),
    )
    assert isinstance(out["risk_score"], int)
    assert 0 <= out["risk_score"] <= 100
