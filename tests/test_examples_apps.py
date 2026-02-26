from pathlib import Path

import pytest

from runllm.parser import parse_rllm_file


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"
ALL_EXAMPLES = sorted(EXAMPLES_DIR.rglob("*.rllm"))
assert ALL_EXAMPLES, "No .rllm files found under examples/."


@pytest.mark.parametrize("path", ALL_EXAMPLES)
def test_examples_parse(path: Path) -> None:
    program = parse_rllm_file(path)
    assert program.name
    assert isinstance(program.input_schema, dict)
    assert isinstance(program.output_schema, dict)
