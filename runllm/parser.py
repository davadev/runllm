from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from runllm.errors import make_error
from runllm.litellm_params import validate_litellm_params
from runllm.models import RLLMProgram, UseSpec


REQUIRED_FIELDS = {
    "name",
    "description",
    "version",
    "author",
    "max_context_window",
    "input_schema",
    "output_schema",
    "llm",
    "llm_params",
}


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise make_error(
            error_code="RLLM_001",
            error_type="ParseError",
            message=".rllm file must start with YAML frontmatter delimited by '---'.",
            details={},
            recovery_hint="Start file with '---', include metadata, close with '---', then prompt body.",
            doc_ref="docs/errors.md#RLLM_001",
        )
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        raise make_error(
            error_code="RLLM_001",
            error_type="ParseError",
            message="Could not find closing YAML frontmatter delimiter.",
            details={},
            recovery_hint="Ensure a closing '---' line exists after metadata.",
            doc_ref="docs/errors.md#RLLM_001",
        )
    header_text = parts[0][4:]
    body = parts[1]
    try:
        metadata = yaml.safe_load(header_text) or {}
    except yaml.YAMLError as exc:
        raise make_error(
            error_code="RLLM_001",
            error_type="ParseError",
            message="Invalid YAML frontmatter.",
            details={"yaml_error": str(exc)},
            recovery_hint="Fix YAML syntax in frontmatter.",
            doc_ref="docs/errors.md#RLLM_001",
        )
    if not isinstance(metadata, dict):
        raise make_error(
            error_code="RLLM_001",
            error_type="ParseError",
            message="YAML frontmatter must be a mapping/object.",
            details={"actual_type": type(metadata).__name__},
            recovery_hint="Use key-value pairs in frontmatter.",
            doc_ref="docs/errors.md#RLLM_001",
        )
    return metadata, body


def _extract_python_block(body: str, block_name: str) -> tuple[str, str | None]:
    start = f"```rllm-python {block_name}"
    marker = body.find(start)
    if marker == -1:
        return body, None
    code_start = body.find("\n", marker)
    if code_start == -1:
        return body, None
    code_end = body.find("\n```", code_start)
    if code_end == -1:
        return body, None
    code = body[code_start + 1 : code_end]
    cleaned = body[:marker] + body[code_end + 4 :]
    return cleaned.strip(), code.strip()


def _extract_recovery_prompt(body: str) -> tuple[str, str]:
    token = "\n<<<RECOVERY>>>\n"
    if token in body:
        prompt, recovery = body.split(token, 1)
        return prompt.strip(), recovery.strip()
    return body.strip(), ""


def _validate_metadata(meta: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_FIELDS - set(meta.keys()))
    if missing:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="Missing required metadata fields.",
            details={"missing_fields": missing},
            recovery_hint="Add all required metadata keys to frontmatter.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    if not isinstance(meta["max_context_window"], int) or meta["max_context_window"] <= 0:
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="max_context_window must be a positive integer.",
            details={"value": meta["max_context_window"]},
            recovery_hint="Set max_context_window to a positive integer.",
            doc_ref="docs/errors.md#RLLM_002",
        )
    for key in ("input_schema", "output_schema", "llm", "llm_params"):
        if not isinstance(meta[key], dict):
            raise make_error(
                error_code="RLLM_002",
                error_type="MetadataValidationError",
                message=f"{key} must be a mapping/object.",
                details={"actual_type": type(meta[key]).__name__},
                recovery_hint=f"Provide {key} as a JSON/YAML object.",
                doc_ref="docs/errors.md#RLLM_002",
            )

    llm_model = meta["llm"].get("model")
    if not isinstance(llm_model, str) or not llm_model.strip():
        raise make_error(
            error_code="RLLM_002",
            error_type="MetadataValidationError",
            message="llm.model is required and must be a non-empty string.",
            details={"llm": meta["llm"]},
            recovery_hint="Set llm.model in .rllm frontmatter.",
            doc_ref="docs/errors.md#RLLM_002",
        )

    validate_litellm_params(meta["llm_params"])


def _parse_uses(path: Path, raw_uses: Any) -> list[UseSpec]:
    if raw_uses is None:
        return []
    if not isinstance(raw_uses, list):
        raise make_error(
            error_code="RLLM_008",
            error_type="DependencyResolutionError",
            message="uses must be a list.",
            details={"actual_type": type(raw_uses).__name__},
            recovery_hint="Define uses as a list of objects with name/path.",
            doc_ref="docs/errors.md#RLLM_008",
        )
    parsed: list[UseSpec] = []
    for item in raw_uses:
        if not isinstance(item, dict):
            raise make_error(
                error_code="RLLM_008",
                error_type="DependencyResolutionError",
                message="Each uses entry must be an object.",
                details={"entry": item},
                recovery_hint="Provide uses entries with keys: name, path, with.",
                doc_ref="docs/errors.md#RLLM_008",
            )
        if "name" not in item or "path" not in item:
            raise make_error(
                error_code="RLLM_008",
                error_type="DependencyResolutionError",
                message="Each uses entry must include name and path.",
                details={"entry": item},
                recovery_hint="Add both name and path fields to uses entry.",
                doc_ref="docs/errors.md#RLLM_008",
            )
        with_map = item.get("with", {})
        if not isinstance(with_map, dict):
            raise make_error(
                error_code="RLLM_008",
                error_type="DependencyResolutionError",
                message="uses.with must be an object when provided.",
                details={"entry": item, "actual_type": type(with_map).__name__},
                recovery_hint="Define uses.with as a mapping of child input keys to literals/templates.",
                doc_ref="docs/errors.md#RLLM_008",
            )
        dep_path = (path.parent / str(item["path"])).resolve()
        parsed.append(
            UseSpec(
                name=str(item["name"]),
                path=dep_path,
                with_map=with_map,
            )
        )
    return parsed


def parse_rllm_file(path: str | Path) -> RLLMProgram:
    p = Path(path).resolve()
    if not p.exists():
        raise make_error(
            error_code="RLLM_001",
            error_type="ParseError",
            message=".rllm file does not exist.",
            details={"path": str(p)},
            recovery_hint="Pass an existing .rllm file path.",
            doc_ref="docs/errors.md#RLLM_001",
        )
    content = p.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(content)
    _validate_metadata(metadata)
    body, python_pre = _extract_python_block(body, "pre")
    body, python_post = _extract_python_block(body, "post")
    prompt, recovery_prompt = _extract_recovery_prompt(body)
    if not prompt:
        raise make_error(
            error_code="RLLM_001",
            error_type="ParseError",
            message="Prompt body is empty.",
            details={"path": str(p)},
            recovery_hint="Add prompt text after frontmatter.",
            doc_ref="docs/errors.md#RLLM_001",
        )

    uses = _parse_uses(p, metadata.get("uses"))
    return RLLMProgram(
        path=p,
        name=str(metadata["name"]),
        description=str(metadata["description"]),
        version=str(metadata["version"]),
        author=str(metadata["author"]),
        max_context_window=int(metadata["max_context_window"]),
        input_schema=metadata["input_schema"],
        output_schema=metadata["output_schema"],
        llm=metadata["llm"],
        llm_params=metadata["llm_params"],
        prompt=prompt,
        recovery_prompt=recovery_prompt or str(metadata.get("recovery_prompt", "")).strip(),
        metadata=metadata.get("metadata", {}) if isinstance(metadata.get("metadata", {}), dict) else {},
        recommended_models=metadata.get("recommended_models", [])
        if isinstance(metadata.get("recommended_models", []), list)
        else [],
        tags=metadata.get("tags", []) if isinstance(metadata.get("tags", []), list) else [],
        uses=uses,
        python_pre=python_pre,
        python_post=python_post,
    )
