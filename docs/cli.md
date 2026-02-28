# CLI Reference

`runllm` provides a unified CLI for running, validating, and managing `.rllm` apps.

## Commands

### `runllm run`

Execute a `.rllm` program with typed input and output.

```bash
runllm run <file.rllm> [--input '{"key": "value"}'] [--input-file path.json] [--model name] [--max-retries N] [--verbose]
```

### `runllm validate`

Check `.rllm` file syntax, required metadata, and schema validity.

```bash
runllm validate <file.rllm>
```

### `runllm inspect`

Print parsed contract details (metadata, schemas, model params, dependencies).

```bash
runllm inspect <file.rllm>
```

### `runllm stats`

Show observed runtime metrics (latency, token usage, success rate) stored in local SQLite database.

```bash
runllm stats <file.rllm> [--model name]
```

### `runllm exectime`

Estimate total execution time based on observed averages for the app and its dependencies.

```bash
runllm exectime <file.rllm> [--model name]
```

### `runllm onboard`

Interactive flow to guide provider setup and create your first app.

```bash
runllm onboard [--model name] [--resume]
```

### `runllm bundle`

Bundle a project into a standalone CLI shim for easy execution without MCP overhead.

```bash
runllm bundle <project_name> [--repo-root path] [--bin-dir path]
```

Example:
```bash
runllm bundle jw_deep_research
./.bin/jw_deep_research --query "How can we overcome fear of death?"
```

### `runllm help`

Show LLM-oriented authoring help topics.

```bash
runllm help <topic> [--format json|text]
```

Topics: `rllm`, `schema`, `recovery`, `composition`, `examples`, `credentials`, `config`.

## MCP Commands

### `runllm mcp serve`

Start an MCP stdio server scoped to one project or the `runllm` library.

```bash
runllm mcp serve --project <name> [--repo-root path] [--trusted-workflows]
```

### `runllm mcp install-opencode`

Install the `runllm` documentation MCP and builder agent into OpenCode.

```bash
runllm mcp install-opencode [--runllm-bin path] [--repo-root path] [--agent-file filename] [--force]
```

Behavior:
- upserts `mcp.runllm` documentation entry in `opencode.json`
- creates `runllm-rllm-builder.md` agent file
- the agent is instructed to use documentation tools and the `bundle` workflow for project execution

## Exit codes

- `0`: Success
- `1`: Failure (with structured JSON error payload)
