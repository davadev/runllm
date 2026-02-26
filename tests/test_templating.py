from __future__ import annotations

from runllm.templating import render_template


def test_render_template_nested_value() -> None:
    out = render_template("Hello {{input.user.name}}", {"input": {"user": {"name": "Ana"}}})
    assert out == "Hello Ana"


def test_render_template_missing_value_becomes_empty_string() -> None:
    out = render_template("v={{input.missing.key}}", {"input": {}})
    assert out == "v="


def test_render_template_structured_values_are_json() -> None:
    out = render_template(
        "payload={{input.data}}",
        {"input": {"data": {"k": 1, "list": [1, 2]}}},
    )
    assert out == 'payload={"k": 1, "list": [1, 2]}'


def test_render_template_none_becomes_empty_string() -> None:
    out = render_template("x={{input.optional}}", {"input": {"optional": None}})
    assert out == "x="
