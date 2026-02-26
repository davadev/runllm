from __future__ import annotations

import json
from typing import Any


def estimate_tokens(text: str) -> int:
    # Conservative heuristic fallback.
    return max(1, int(len(text) / 4))


def estimate_context_tokens(payload: dict[str, Any], prompt: str) -> int:
    data_text = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return estimate_tokens(data_text) + estimate_tokens(prompt)
