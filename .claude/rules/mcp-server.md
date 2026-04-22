# MCP Server Rules

## Convention

- Use the official `mcp` Python SDK (same as OpenMetadata's AI SDK)
- STDIO transport for CLI-based MCP server
- Tool names: `snake_case` — `metadata_diff`, `metadata_changelog`, `metadata_change_summary`
- Tool descriptions: written for LLM consumption — clear, specific, with examples of what users might ask

## Tool Design

Each MCP tool must:

1. Have a clear, descriptive `name` and `description`
2. Define input schema with Pydantic or JSON Schema
3. Return formatted text (not raw JSON) — the LLM needs human-readable output
4. Handle errors gracefully — return error messages, never crash the server
5. Include usage hints in the description: "Use this when the user asks about metadata changes"

## Entry Point

The MCP server starts via the same CLI entry point:
```bash
ometa-diff serve          # STDIO mode (for Claude Desktop, Cursor)
```

## Claude Desktop Config

Must work with this config pattern:
```json
{
  "mcpServers": {
    "ometa-diff": {
      "command": "uvx",
      "args": ["--from", "ometa-diff[mcp]", "ometa-diff", "serve"],
      "env": {
        "OPENMETADATA_HOST": "http://localhost:8585/api",
        "OPENMETADATA_JWT_TOKEN": "your-jwt-token"
      }
    }
  }
}
```

Also support direct invocation:
```json
{
  "mcpServers": {
    "ometa-diff": {
      "command": "ometa-diff",
      "args": ["serve"],
      "env": {
        "OPENMETADATA_HOST": "http://localhost:8585/api",
        "OPENMETADATA_JWT_TOKEN": "your-jwt-token"
      }
    }
  }
}
```

## The MCP server is the PRIMARY deliverable — not an afterthought

Build it with the same care as the CLI. The diff engine and changelog logic must work identically whether accessed via CLI or MCP.
