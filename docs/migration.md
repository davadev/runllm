# Versioning and Migration

Current `.rllm` spec version: `0.1`.

Compatibility rules:
- Runtime should remain backward compatible with `0.1.x` files.
- Any breaking file-format changes require `0.2`+ and migration notes.

Stats DB:
- `schema_version` is tracked in `meta` table.
- Future upgrades should include migration scripts before runtime writes.
