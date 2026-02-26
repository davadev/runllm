from pathlib import Path

import pytest

from runllm.parser import parse_rllm_file


NEW_EXAMPLES = [
    "intent_router.rllm",
    "support_reply_drafter.rllm",
    "support_pipeline.rllm",
    "meeting_extractor.rllm",
    "policy_guard.rllm",
    "schema_repair_proxy.rllm",
    "code_patch_planner.rllm",
    "test_case_generator.rllm",
    "ocr_postprocessor.rllm",
    "risk_score_aggregator.rllm",
]


@pytest.mark.parametrize("filename", NEW_EXAMPLES)
def test_new_examples_parse(filename: str) -> None:
    path = Path("examples") / filename
    program = parse_rllm_file(path)
    assert program.name
    assert isinstance(program.input_schema, dict)
    assert isinstance(program.output_schema, dict)
