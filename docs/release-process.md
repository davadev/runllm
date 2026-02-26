# Release Process

This document defines the minimum steps to publish a release.

Related docs:

- Release scope and milestones: `../ROADMAP.md`
- Version compatibility notes: `migration.md`
- Main project docs and install paths: `../README.md`
- Changelog source: `../CHANGELOG.md`

## 1) Prepare release branch

- Ensure release scope is merged into `release/<major>.<minor>`.
- Confirm docs are synchronized for behavior changes.
- Ensure `CHANGELOG.md` includes the target version section.

## 2) Validate

Run required checks:

- `python3 -m pytest -q`
- `RUNLLM_OLLAMA_TESTS=1 python3 -m pytest -q tests/test_examples_ollama_live.py`
- `RUNLLM_OLLAMA_TESTS=1 python3 -m pytest -q tests/test_onboarding_ollama_live.py`

If live tests are not available in CI, run them manually before tagging.

## 3) Cut release

- Merge `release/*` into `main`.
- Tag on `main`:
  - `git tag v<major>.<minor>.<patch>`
  - `git push origin v<major>.<minor>.<patch>`

## 4) Publish GitHub release

- Create release from pushed tag.
- Use `.github/release_template.md` as starting notes.
- Include:
  - key additions/fixes
  - migration notes (if any)
  - test status and known limitations

## 5) Post-release

- Move next work to appropriate `feature/*` and `bugfix/*` branches from active release branch.
- Keep `CHANGELOG.md` updates in each follow-up PR.
