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

Workflow entrypoint discovery:

- `workflow.yaml` files under a project scope are indexed as MCP workflows.
- A workflow spec must include:
  - `name` (string)
  - `description` (string)
  - `entrypoint` (`relative/path.py:function_name`)
  - `input_schema` (JSON Schema object)
  - `output_schema` (JSON Schema object)

## Start server

Use stdio MCP server mode and scope one project per server instance.

```bash
runllm mcp serve --project runllm
```

Enable trusted workflow execution (`invoke_workflow`) only for repositories you trust:

```bash
runllm mcp serve --project runllm --trusted-workflows
```

Common scope examples:

```bash
runllm mcp serve --project project_a
runllm mcp serve --project rllmlib
```

## OpenCode auto-install

To auto-add `runllm` MCP into OpenCode config and create a dedicated builder agent:

```bash
runllm mcp install-opencode --project runllm
```

This command:

- writes/updates `opencode.json` in `$XDG_CONFIG_HOME/opencode` or `~/.config/opencode`
- upserts builder entry `mcp.runllm` with command:
  - `runllm mcp serve --project runllm`
- upserts project entry `mcp.<mcp-name>` (default `runllm-project`) with command:
  - `runllm mcp serve --project <project>`
- creates `agent/runllm-rllm-builder.md` (or `--agent-file`) with instructions to use only `mcp.runllm` for `.rllm` authoring and runllm docs guidance
- creates `agent/<project>-agent.md` (or `--project-agent-file`) with instructions to prefer `mcp.<mcp-name>` for project tasks while allowing local file tools (`read`, `write`, `edit`, `glob`, `grep`)

Safety behavior:

- preserves existing `mcp.runllm` and `mcp.<mcp-name>` values unless fields are missing
- does not overwrite existing agent file content by default (builder and project agent files)
- pass `--force` to overwrite both
- project agent uses explicit MCP default-deny (`mcp.*: deny`) with allow only for scoped `mcp.<mcp-name>`

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
- `list_workflows`
  - optional inputs: `query`, `limit`, `cursor`, `refresh`
  - returns project-scoped workflow entrypoints (one-call orchestration interfaces)
- `invoke_workflow`
  - required inputs: `id`, `input`
  - validates input against workflow schema, runs workflow entrypoint, validates output schema
  - requires server startup flag `--trusted-workflows`
- `help_topic`
  - required input: `topic`
  - optional input: `format` (`json` default, or `text`)
  - returns canonical runllm authoring guidance for topic:
    - `rllm`, `schema`, `recovery`, `composition`, `examples`, `credentials`, `config`

## Agent-friendly flow

1. Call `help_topic` for `rllm`, `schema`, `recovery`, and `composition`.
2. Call `list_programs` with optional `query`.
3. For single-call project orchestration, call `list_workflows` and pick one id.
4. Call `invoke_workflow` with the workflow `invocation_template` adapted to task data.
5. For direct app calls, use `list_programs` + `invoke_program`.

This keeps discovery flat and usually completes in 3-5 MCP calls depending on whether workflow invocation is needed.

Refresh behavior:

- `list_programs` uses startup index by default.
- pass `refresh: true` to rebuild registry before listing.
- `invoke_program` automatically performs one registry refresh retry when id is not found.

## Failure handling

- Unknown/out-of-scope ids return structured error payloads.
- Non-object invocation input returns structured input-schema error payload.
- Runtime app failures are returned as structured `runllm` error payloads.
- MCP tool error responses are marked with protocol `isError=true`.
