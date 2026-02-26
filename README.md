# runllm
<img width="1536" height="1024" alt="C89B7899-69B6-4872-88CE-AE36AE6269D1" src="https://github.com/user-attachments/assets/636fd58f-1f44-4bd3-9815-b9f52457201f" />


Most LLM systems fail for predictable reasons:

- Too many tools available at once, so the model chooses poorly.
- Too many instructions in one prompt, so key constraints are forgotten.
- Output schema drift, especially in longer workflows.
- "Agentic" setups that require tool-calling models only, which often means bigger models and stronger hardware.

`runllm` is built to solve this by changing the unit of work.

Instead of one giant, fragile agent, you write small atomic `.rllm` programs.
Each program does one thing, has strict typed input/output, and can be stacked with other programs.

That gives you a practical production path:

- More deterministic behavior.
- Better schema compliance.
- Better observability (success rate, latency, token usage).
- Better model flexibility (use small local models where they fit, stronger models where needed).

In short: fewer "smart but flaky" systems, more reliable workflows.

## What runllm gives you

- Single-iteration `.rllm` apps with explicit contracts.
- Input and output validation using JSON Schema subset.
- Retry with recovery prompts when output schema fails.
- Composition (`uses`) so apps can call other apps like functions.
- Per-app/per-model stats in SQLite.
- Execution-time estimation (`exectime`) when stacking apps.
- Ollama support without requiring tool-calling-only models.

## Why this approach works

LLMs perform best on focused tasks.

When one call has to route, reason, extract, transform, and format all at once, reliability drops.
When each call is atomic and schema-bounded, reliability rises.

`runllm` makes this pattern first-class:

1. Define tiny apps with strict I/O.
2. Measure each app's compliance and runtime.
3. Compose apps into larger workflows.
4. Predict cost/latency and identify weak links.

This makes local and small-model workflows viable for many users, not only teams with large GPU setups.

## Install

Recommended (global CLI, works from any directory):

```bash
pipx install runllm
```

For local development in this repository:

```bash
pip install -e .
```

If you used `pip install --user`, make sure your user scripts path is on `PATH`.
See `docs/global-install.md`.

For provider API keys (OpenAI and others), see `docs/provider-credentials.md`.
Autoload and precedence details are in `docs/configuration.md`.

## Quickstart

Validate an app:

```bash
runllm validate examples/summary.rllm
```

Run an app:

```bash
runllm run examples/summary.rllm --input '{"text":"Large language models are useful."}'
```

Inspect metadata and schemas:

```bash
runllm inspect examples/summary.rllm
```

View stats and execution estimate:

```bash
runllm stats examples/summary.rllm
runllm exectime examples/compose_summary_keywords.rllm
```

## Live local testing with Ollama

By default, tests that call real local models are skipped.

Run standard tests:

```bash
python3 -m pytest -q
```

Run live Ollama integration tests:

```bash
RUNLLM_OLLAMA_TESTS=1 python3 -m pytest -q tests/test_examples_ollama_live.py
```

These live tests validate schema compliance and structural correctness rather than exact text, because LLM text is non-deterministic.

## Example apps

The repository includes diverse examples such as:

- Intent routing
- Support reply drafting
- Multi-step support pipeline (composition)
- Meeting extraction
- Policy compliance guard
- Schema repair proxy
- Code patch planner
- Test case generator
- OCR post-processing
- Risk score aggregation (composition + python post block)

See `examples/`.

## Core commands

- `runllm run <file.rllm> ...`
- `runllm validate <file.rllm>`
- `runllm inspect <file.rllm>`
- `runllm stats <file.rllm> [--model ...]`
- `runllm exectime <file.rllm> [--model ...]`

## Project docs

- Project roadmap: `ROADMAP.md`
- Docs index: `docs/README.md`
- `.rllm` format spec: `docs/rllm-spec.md`
- Authoring guide: `docs/authoring-guide.md`
- Agent scaffold guide: `docs/agent-scaffold-guide.md`
- Schema cookbook: `docs/schema-cookbook.md`
- Recovery playbook: `docs/recovery-playbook.md`
- CLI reference: `docs/cli.md`
- Error reference: `docs/errors.md`
- Composition guide: `docs/composition.md`
- Ollama guide: `docs/ollama.md`
- Global install: `docs/global-install.md`
- Provider credentials: `docs/provider-credentials.md`
- Configuration and autoload: `docs/configuration.md`
- Migration notes: `docs/migration.md`

## For coding agents

If you are building apps automatically, start in this order:

1. `docs/agent-scaffold-guide.md`
2. `docs/rllm-spec.md`
3. `docs/schema-cookbook.md`
4. `docs/recovery-playbook.md`

## Practical notes

- Output contract defaults to JSON object for strict parsing reliability.
- Schemas use a JSON Schema subset for both input and output.
- Stats are stored in `~/.config/runllm/stats.db`.
- Ollama auto-pull is opt-in (`--ollama-auto-pull`).
- You can choose model per app, so workflows can mix small fast models and larger reasoning models.
