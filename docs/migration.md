# Versioning and Migration

Current `.rllm` spec version: `0.1`.

Compatibility rules:
- Runtime should remain backward compatible with `0.1.x` files.
- Any breaking file-format changes require `0.2`+ and migration notes.

Stats DB:
- `schema_version` is tracked in `meta` table.
- Future upgrades should include migration scripts before runtime writes.

## Documentation compatibility note

This repository keeps runtime behavior and docs aligned.

When runtime behavior changes (for example retry logic, parsing behavior, or supported params), update:

- `docs/rllm-spec.md`
- `docs/cli.md`
- `docs/errors.md`

in the same PR/commit to preserve agent-scaffold reliability.
