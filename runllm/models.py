from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class UseSpec:
    name: str
    path: Path
    with_map: dict[str, Any] = field(default_factory=dict)


@dataclass
class RLLMProgram:
    path: Path
    name: str
    description: str
    version: str
    author: str
    max_context_window: int
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    llm: dict[str, Any]
    llm_params: dict[str, Any]
    prompt: str
    recovery_prompt: str
    metadata: dict[str, Any] = field(default_factory=dict)
    recommended_models: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    uses: list[UseSpec] = field(default_factory=list)
    python_pre: str | None = None
    python_post: str | None = None


@dataclass
class RunOptions:
    model_override: str | None = None
    max_retries: int = 2
    verbose: bool = False
    ollama_auto_pull: bool = False
    trusted_python: bool = False
    python_memory_limit_mb: int = 256
    debug_prompt_file: str | None = None
    debug_prompt_stdout: bool = False
    debug_prompt_wrap: int = 100


@dataclass
class UsageMetrics:
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
