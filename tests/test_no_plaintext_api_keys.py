from __future__ import annotations

import re
import subprocess
from pathlib import Path


KEY_PATTERNS = {
    "openai": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "anthropic": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "google": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "github": re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
}


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def _git_list_files(repo_root: Path) -> list[Path]:
    tracked = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
        cwd=repo_root,
    ).stdout.splitlines()
    untracked_not_ignored = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
        cwd=repo_root,
    ).stdout.splitlines()
    rel_paths = sorted(set(tracked + untracked_not_ignored))
    return [repo_root / rel for rel in rel_paths]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""
    except OSError:
        return ""


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def test_no_plaintext_api_keys_in_non_ignored_files() -> None:
    repo_root = _repo_root()
    offenders: list[str] = []

    for file_path in _git_list_files(repo_root):
        if not file_path.is_file():
            continue
        if file_path.parts and ".git" in file_path.parts:
            continue

        text = _read_text(file_path)
        if not text:
            continue

        rel_path = file_path.relative_to(repo_root)
        for provider, pattern in KEY_PATTERNS.items():
            for match in pattern.finditer(text):
                offenders.append(f"{rel_path} [{provider}] {_mask_secret(match.group(0))}")

    assert not offenders, "Potential plaintext API keys found:\n" + "\n".join(offenders)
