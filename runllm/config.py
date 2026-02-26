from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RuntimeConfig:
    default_model: str | None = None
    default_max_retries: int = 2
    default_ollama_auto_pull: bool = False
    loaded_sources: list[str] = field(default_factory=list)


_RUNTIME_CONFIG: RuntimeConfig | None = None
_RUNTIME_CONFIG_KEY: tuple[Any, ...] | None = None
_AUTOLOADED_ENV_VALUES: dict[str, str] = {}


def _file_signature(path: Path) -> tuple[int, str] | None:
    if not path.exists() or not path.is_file():
        return None
    data = path.read_bytes()
    digest = hashlib.sha1(data).hexdigest()
    return (len(data), digest)


def _cache_key(*, autoload: bool) -> tuple[Any, ...]:
    cfg_home = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    cwd = Path.cwd()
    if not autoload:
        return (autoload, str(cwd), cfg_home)
    root = Path(cfg_home) / "runllm"
    user_env_path = root / ".env"
    cwd_env_path = cwd / ".env"
    yaml_path = root / "config.yaml"
    return (
        autoload,
        str(cwd),
        cfg_home,
        _file_signature(yaml_path),
        _file_signature(user_env_path),
        _file_signature(cwd_env_path),
    )


def _config_root() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "runllm"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        k = key.strip()
        v = value.strip().strip('"').strip("'")
        if not k:
            continue
        data[k] = v
    return data


def _parse_config_yaml(path: Path) -> tuple[RuntimeConfig, dict[str, str]]:
    if not path.exists():
        return RuntimeConfig(), {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return RuntimeConfig(), {}

    runtime = raw.get("runtime", {})
    provider = raw.get("provider", {})
    cfg = RuntimeConfig()

    if isinstance(runtime, dict):
        model = runtime.get("default_model")
        retries = runtime.get("default_max_retries")
        auto_pull = runtime.get("default_ollama_auto_pull")
        if isinstance(model, str) and model.strip():
            cfg.default_model = model.strip()
        if isinstance(retries, int) and retries >= 0:
            cfg.default_max_retries = retries
        if isinstance(auto_pull, bool):
            cfg.default_ollama_auto_pull = auto_pull

    env_from_yaml: dict[str, str] = {}
    if isinstance(provider, dict):
        ollama_api_base = provider.get("ollama_api_base")
        if isinstance(ollama_api_base, str) and ollama_api_base.strip():
            env_from_yaml["OLLAMA_API_BASE"] = ollama_api_base.strip()

    return cfg, env_from_yaml


def load_runtime_config(*, autoload: bool = True) -> RuntimeConfig:
    global _RUNTIME_CONFIG, _RUNTIME_CONFIG_KEY, _AUTOLOADED_ENV_VALUES
    cache_key = _cache_key(autoload=autoload)
    if not autoload and _RUNTIME_CONFIG is not None and _RUNTIME_CONFIG_KEY == cache_key:
        return _RUNTIME_CONFIG

    cfg = RuntimeConfig()
    if not autoload:
        for key, injected_value in list(_AUTOLOADED_ENV_VALUES.items()):
            if os.environ.get(key) == injected_value:
                del os.environ[key]
        _AUTOLOADED_ENV_VALUES = {}
        _RUNTIME_CONFIG = cfg
        _RUNTIME_CONFIG_KEY = cache_key
        return cfg

    root = _config_root()
    user_env_path = root / ".env"
    cwd_env_path = Path.cwd() / ".env"
    yaml_path = root / "config.yaml"

    yaml_cfg, yaml_env = _parse_config_yaml(yaml_path)
    merged_env: dict[str, str] = {}
    merged_env.update(yaml_env)
    merged_env.update(_parse_env_file(user_env_path))
    merged_env.update(_parse_env_file(cwd_env_path))

    protected_existing: dict[str, str] = {}
    for key, value in os.environ.items():
        if key not in _AUTOLOADED_ENV_VALUES:
            protected_existing[key] = value
            continue
        if _AUTOLOADED_ENV_VALUES.get(key) != value:
            # Key was changed externally after autoload injection.
            protected_existing[key] = value

    for key, injected_value in list(_AUTOLOADED_ENV_VALUES.items()):
        if os.environ.get(key) == injected_value and key not in protected_existing:
            del os.environ[key]

    injected_now: dict[str, str] = {}
    for key, value in merged_env.items():
        if key in protected_existing:
            continue
        os.environ[key] = value
        injected_now[key] = value

    cfg.default_model = yaml_cfg.default_model
    cfg.default_max_retries = yaml_cfg.default_max_retries
    cfg.default_ollama_auto_pull = yaml_cfg.default_ollama_auto_pull

    if yaml_path.exists():
        cfg.loaded_sources.append(str(yaml_path))
    if user_env_path.exists():
        cfg.loaded_sources.append(str(user_env_path))
    if cwd_env_path.exists():
        cfg.loaded_sources.append(str(cwd_env_path))

    _AUTOLOADED_ENV_VALUES = injected_now
    _RUNTIME_CONFIG = cfg
    _RUNTIME_CONFIG_KEY = cache_key
    return cfg


def get_runtime_config() -> RuntimeConfig:
    if _RUNTIME_CONFIG is None:
        return RuntimeConfig()
    return _RUNTIME_CONFIG


def _provider_required_key(model: str) -> tuple[str, str] | None:
    lowered = model.lower()
    if lowered.startswith("openai/"):
        return "openai", "OPENAI_API_KEY"
    if lowered.startswith("anthropic/"):
        return "anthropic", "ANTHROPIC_API_KEY"
    if lowered.startswith("google/") or lowered.startswith("gemini/"):
        return "google", "GOOGLE_API_KEY"
    if lowered.startswith("mistral/"):
        return "mistral", "MISTRAL_API_KEY"
    if lowered.startswith("cohere/"):
        return "cohere", "COHERE_API_KEY"
    return None


def required_provider_key(model: str) -> tuple[str, str] | None:
    return _provider_required_key(model)


def reset_runtime_config_for_tests() -> None:
    global _RUNTIME_CONFIG, _RUNTIME_CONFIG_KEY, _AUTOLOADED_ENV_VALUES
    _RUNTIME_CONFIG = None
    _RUNTIME_CONFIG_KEY = None
    _AUTOLOADED_ENV_VALUES = {}
