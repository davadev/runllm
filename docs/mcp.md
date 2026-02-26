# MCP Integration

`runllm` can expose `.rllm` apps over a minimal MCP surface.

Related docs:

- CLI command reference: `cli.md`
- `.rllm` file contract and schemas: `rllm-spec.md`
- Error payload catalog: `errors.md`

Design goals for v0.2:

- project-scoped discovery to avoid cross-project context bloat
- minimal tool surface for better agent reliability
- compact program cards that include contract hints

## Library layout

Projects are inferred by directory, not metadata.

- `userlib/<project_name>/**/*.rllm` -> project = `<project_name>`
- `rllmlib/**/*.rllm` -> project = `rllmlib`

Notes:

- Files directly under `userlib/` are ignored.
- `examples/` is not part of MCP discovery.

## Start server

Use stdio MCP server mode and scope one project per server instance.

```bash
runllm mcp serve --project runllm
```

Common scope examples:

```bash
runllm mcp serve --project billing
runllm mcp serve --project rllmlib
```

Registry behavior:

- program registry is indexed once at server startup
- use `list_programs` with `refresh: true` to reload newly added or edited `.rllm` files
- `invoke_program` auto-retries once with an internal refresh when id is initially missing

## MCP tools (minimal)

- `list_programs`
  - optional inputs: `query`, `limit`, `cursor`, `refresh`
  - returns compact cards with:
    - `name`, `description`
    - `input_required` and `input_optional` with type hints
    - `returns` with type hints
    - `invocation_template` for minimum valid input
- `invoke_program`
  - required inputs: `id`, `input`
  - runs one scoped app with JSON input

## Agent-friendly flow

1. Call `list_programs` with optional `query`.
2. Pick one id from returned cards.
3. Call `invoke_program` with the card's `invocation_template` adapted to task data.

This keeps discovery flat and usually completes in 2 MCP calls.

Refresh behavior:

- `list_programs` uses startup index by default.
- pass `refresh: true` to rebuild registry before listing.
- `invoke_program` automatically performs one registry refresh retry when id is not found.

## Failure handling

- Unknown/out-of-scope ids return structured error payloads.
- Non-object invocation input returns structured input-schema error payload.
- Runtime app failures are returned as structured `runllm` error payloads.
- MCP tool error responses are marked with protocol `isError=true`.
