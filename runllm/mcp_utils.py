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
    
    parts = [
        str(card.get("name", "")),
        str(card.get("description", "")),
        str(card.get("project", "")),
    ]
    # Search in tags and suggestions if present
    for key in ("tags", "suggestions"):
        vals = card.get(key)
        if isinstance(vals, list):
            parts.extend(str(v) for v in vals)
            
    haystack = " ".join(parts).lower()
    return q in haystack


def placeholder_for_schema(schema: dict[str, Any]) -> Any:
    if not isinstance(schema, dict):
        return None
    if "const" in schema:
        return schema["const"]
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null = [item for item in schema_type if item != "null"]
        schema_type = non_null[0] if non_null else schema_type[0]

    if schema_type == "object":
        props = schema.get("properties")
        if not isinstance(props, dict):
            return {}
        required = schema.get("required")
        if not isinstance(required, list):
            required = []
        out: dict[str, Any] = {}
        for key in required:
            if not isinstance(key, str):
                continue
            child_schema = props.get(key, {})
            if isinstance(child_schema, dict):
                out[key] = placeholder_for_schema(child_schema)
        return out

    if schema_type == "array":
        items = schema.get("items", {})
        if not isinstance(items, dict):
            items = {}
        render_count = max(1, min(int(schema.get("minItems", 1)), MAX_ARRAY_TEMPLATE_ITEMS))
        return [placeholder_for_schema(items) for _ in range(render_count)]

    if schema_type == "string":
        return "<string>"
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0.0
    if schema_type == "boolean":
        return False
    return None


def render_schema_type(schema: dict[str, Any]) -> str:
    raw_type = schema.get("type")
    if isinstance(raw_type, str):
        if raw_type == "array":
            items = schema.get("items")
            if isinstance(items, dict):
                return f"array<{render_schema_type(items)}>"
            return "array<unknown>"
        return raw_type
    if isinstance(raw_type, list):
        return "|".join(str(t) for t in raw_type)
    if "enum" in schema:
        return "enum"
    return "unknown"


def get_schema_fields(schema: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(schema, dict):
        return [], [], {}
    if schema.get("type") != "object":
        field = {
            "name": "value",
            "type": render_schema_type(schema),
            "required": True,
        }
        return [field], [], {}

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    required = set(schema.get("required", [])) if isinstance(schema.get("required", []), list) else set()

    required_fields: list[dict[str, Any]] = []
    optional_fields: list[dict[str, Any]] = []
    invocation_template: dict[str, Any] = {}

    for key in sorted(properties.keys()):
        subschema = properties.get(key)
        if not isinstance(subschema, dict):
            subschema = {}
        row = {
            "name": key,
            "type": render_schema_type(subschema),
            "required": key in required,
        }
        if key in required:
            required_fields.append(row)
            invocation_template[key] = placeholder_for_schema(subschema)
        else:
            optional_fields.append(row)

    return required_fields, optional_fields, invocation_template


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
