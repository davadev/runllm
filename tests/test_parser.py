from pathlib import Path

from runllm.parser import parse_rllm_file


def test_parse_summary_example() -> None:
    p = Path("examples/summary.rllm").resolve()
    program = parse_rllm_file(p)
    assert program.name == "summary"
    assert "text" in program.input_schema["properties"]
    assert "summary" in program.output_schema["properties"]
