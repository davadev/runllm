from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

USERLIB_DIR = "userlib"
RLLMLIB_DIR = "rllmlib"
MAX_ARRAY_TEMPLATE_ITEMS = 3
LOGGER = logging.getLogger(__name__)


def infer_project(path: Path, repo_root: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if not parts:
        return None

    if parts[0] == USERLIB_DIR:
        if len(parts) < 3:
            return None
        return parts[1]
    if parts[0] == RLLMLIB_DIR:
        return RLLMLIB_DIR
    if parts[0] == "examples" and len(parts) >= 2 and parts[1] == "onboarding":
        return "runllm"
    return None


def matches_query(card: dict[str, Any], query: str | None) -> bool:
    if query is None:
        return True
    q = query.strip().lower()
    if not q:
        return True
    haystack = " ".join(
        [
            str(card.get("name", "")),
            str(card.get("description", "")),
            str(card.get("project", "")),
        ]
    ).lower()
    return q in haystack


def placeholder_for_schema(schema: dict[str, Any]) -> Any:
    if "const" in schema:
        return schema.get("const")
    if "enum" in schema:
        enum_values = schema.get("enum")
        if isinstance(enum_values, list) and enum_values:
            return enum_values[0]
        return None

    raw_type = schema.get("type")
    chosen: str | None = None
    if isinstance(raw_type, str):
        chosen = raw_type
    elif isinstance(raw_type, list):
        for candidate in raw_type:
            if candidate != "null":
                chosen = str(candidate)
                break
        if chosen is None and raw_type:
            chosen = str(raw_type[0])

    if chosen == "string":
        return "<string>"
    if chosen == "integer":
        return 0
    if chosen == "number":
        return 0.0
    if chosen == "boolean":
        return False
    if chosen == "array":
        items = schema.get("items")
        item_schema = items if isinstance(items, dict) else {}
        min_items_raw = schema.get("minItems", 0)
        min_items = min_items_raw if isinstance(min_items_raw, int) and min_items_raw > 0 else 0
        if min_items == 0:
            return []
        render_count = min(min_items, MAX_ARRAY_TEMPLATE_ITEMS)
        return [placeholder_for_schema(item_schema) for _ in range(render_count)]
    if chosen == "object":
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        required = schema.get("required", [])
        required_keys = required if isinstance(required, list) else []
        out: dict[str, Any] = {}
        for key in required_keys:
            key_name = str(key)
            subschema = properties.get(key_name)
            if not isinstance(subschema, dict):
                subschema = {}
            out[key_name] = placeholder_for_schema(subschema)
        return out
    return None
