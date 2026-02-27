# RLLM App Authoring Tips

This file captures reusable best practices for building reliable `.rllm` workflows with local and hosted models.

## 1) Keep Contracts Small and Strict

- Prefer minimal JSON schemas with shallow nesting.
- Use explicit `required` fields and `additionalProperties: false`.
- Keep output fields narrow and purpose-specific for each stage.
- Split large tasks into multiple small apps instead of one broad app.

## 2) Make Every Stage Verifiable

- Require outputs that can be checked against retrieved source text.
- For quote extraction, require exact contiguous substrings from source content.
- Add deterministic post-validation in glue code and drop unverifiable items.
- Treat unverifiable claims as missing evidence, not model mistakes to hide.

## 3) Design for Local Model Stability

- Use `temperature: 0` for deterministic extraction and filtering stages.
- Keep prompts direct and avoid overloaded instruction blocks.
- Raise timeouts for large-context synthesis/filter stages.
- Reduce fan-out early (for example, cap question count), not evidence late.

## 4) Enforce JSON Output Deterministically

- In prompts, repeat "Return ONLY JSON" with exact key names.
- Keep recovery instructions short and schema-specific.
- Use runtime-level output contracts (schema + example + strict JSON-only rule).

## 5) Use Progressive Retrieval Instead of Single-Shot Retrieval

- Start with broad discovery, then focused follow-up questions.
- Prefer diverse high-information questions over naive keyword expansion.
- Add one small gap-check loop instead of many retry loops.
- Deduplicate aggressively to avoid repeated retrieval work.

## 6) Control Runtime by Capping Discovery Inputs

- Cap planned question/lead count to a fixed budget.
- Keep downstream evidence unconstrained once verified.
- Track stage timing to identify dominant latency contributors.
- Use predictable budgets so end-to-end runtime can be estimated.

## 7) Parallelize Independent Work

- Run independent retrieval calls in parallel when backend capacity allows.
- Run independent analysis stages in parallel only when they do not share mutable state.
- Merge outputs with deterministic ordering and dedupe rules.
- Keep per-call retries local to each parallel branch.

## 8) Stage and Pin Workflow Development

- For each new stage: real run once, validate shape, save pin, then add mock test.
- Keep pins as reproducible snapshots of real behavior.
- Use focused tests per stage rather than only end-to-end tests.
- Evolve one stage at a time to isolate regressions.

## 9) Prompt Guidance That Generalizes

- Ask models to generate intent-diverse questions, not entity-specific templates.
- Avoid query-specific hardcoding in stage prompts.
- Prefer constraints based on evidence usefulness and answerability.
- Require explicit uncertainty statements when evidence is thin.

## 10) Final Synthesis Rules

- Build final answers only from verified evidence artifacts.
- Keep citation format uniform and machine-checkable.
- Distinguish conclusions from supporting evidence sections.
- Include explicit limits/uncertainty section in final markdown output.

## 11) Stage Contract Checklist

- Define one clear stage purpose and one primary output payload shape.
- Keep schemas version-tolerant and evolve by additive fields when possible.
- Explicitly document stage failure semantics and retry strategy.
- Include pin naming conventions so outputs are discoverable and resumable.

## 12) Composition Interface Rules

- Make stage boundaries explicit: every downstream field must come from a named upstream artifact.
- Reuse stable key names across stages to avoid brittle mapping code.
- Avoid hidden coupling (for example, parsing meaning from free-form prose fields).
- Prefer normalized intermediate contracts over ad hoc per-branch shapes.

## 13) Evidence Lifecycle and Quality Gates

- Model the lifecycle explicitly: retrieved -> filtered -> verified -> synthesized.
- Preserve provenance fields end-to-end (path, uid, optional chunk identifiers).
- Add pre-synthesis quality gates: duplicate reduction, minimum citation count, coverage checks.
- Run a consistency/contradiction pass when multiple sources support the same claim.

## 14) Branching and Universality

- Use classifier-driven branch routing for broad query types.
- Keep a shared core pipeline and add small branch-specific enrichment stages.
- Converge branches into one normalized final evidence bundle before synthesis.
- Ensure branch prompts stay domain-neutral and avoid hardcoded entity assumptions.
