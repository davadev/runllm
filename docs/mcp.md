# MCP Integration

`runllm` exposes a minimal MCP surface for documentation and program discovery.

## Documentation MCP

The core `mcp.runllm` server provides:
- `help_topic`: Retrieve authoring guidance.
- `list_programs`: Discover apps in the library. Response includes `tags`, `suggestions`, and type hints for inputs/outputs.
- `invoke_program`: Run documentation-related helpers.
- `list_workflows`: Discover workflows in the library. Response includes `tags`, `suggestions`, and type hints for inputs/outputs.
- `invoke_workflow`: Run orchestration workflows (requires trusted mode).


## Project Discovery

Apps are discovered and assigned to projects based on their location in the repository:

- `userlib/<project>/**/*.rllm` -> project `<project>`
- `rllmlib/**/*.rllm` -> project `rllmlib`
- `examples/onboarding/*.rllm` -> project `runllm`

## Installation in OpenCode

Use `install-opencode` to set up the documentation MCP and builder agent:

```bash
runllm mcp install-opencode
```

This command:
- updates `opencode.json` with the `runllm` entry.
- creates `agent/runllm-rllm-builder.md` with documentation rules.

## Project Execution (Bundling)

For project-specific execution (like `jw_deep_research`), we recommend using the **bundle** approach instead of separate MCP servers to avoid request timeouts on long-running tasks.

1. **Bundle the project:**
   ```bash
   runllm bundle jw_deep_research
   ```
2. **Run directly:**
   ```bash
   ./.bin/jw_deep_research --query "How can we overcome fear of death?"
   ```

## Start server (Manual)

To manually start a project-scoped server:

```bash
runllm mcp serve --project <name> [--repo-root path]
```
