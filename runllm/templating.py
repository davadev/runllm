from __future__ import annotations

import re
from typing import Any


_TOKEN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_\.]*)\s*\}\}")


def _resolve_path(data: dict[str, Any], dotted: str) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""
    return current


def render_template(template: str, data: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        value = _resolve_path(data, key)
        if isinstance(value, (dict, list)):
            return str(value)
        return "" if value is None else str(value)

    return _TOKEN.sub(repl, template)
