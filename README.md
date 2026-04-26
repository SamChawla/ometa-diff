# ometa-diff

**Metadata version-diff intelligence for OpenMetadata.**

Answer "what changed in my data catalog?" — via MCP tools for AI agents or a CLI for engineers.

OpenMetadata stores full version history for every entity. `ometa-diff` reads those snapshots, computes field-by-field diffs, and surfaces them as structured output — something OM's built-in MCP server has never offered.

---

## Install

```bash
pip install ometa-diff          # CLI only
pip install "ometa-diff[mcp]"   # CLI + MCP server
```

## Running OpenMetadata locally

If you don't have an OpenMetadata instance yet, spin one up with the included Docker Compose file.

**Prerequisites:** Docker Desktop installed and running.

```bash
# 1. Start the stack (first run takes ~5 min to pull images)
docker compose -f docker-compose-om.yml up -d

# 2. Wait until the server is healthy
docker compose -f docker-compose-om.yml ps
# openmetadata_server should show "healthy"
```

OpenMetadata is ready when `http://localhost:8585` loads in your browser.

**Default login:** username `admin` / password `admin`

### Getting the JWT token

1. Log in at `http://localhost:8585`
2. Go to **Settings** (gear icon, bottom-left)
3. Under **Integrations**, click **Bots**
4. Click **ingestion-bot**
5. Click **Copy Token** — this is your `OPENMETADATA_JWT_TOKEN`

> The token does not expire by default on a fresh local install.

### Stopping the stack

```bash
docker compose -f docker-compose-om.yml down        # stop but keep data
docker compose -f docker-compose-om.yml down -v     # stop and delete all data
```

---

## Quick Start

### Set environment variables

**macOS / Linux (bash/zsh):**
```bash
export OPENMETADATA_HOST=http://localhost:8585/api
export OPENMETADATA_JWT_TOKEN=eyJhbG...
```

**Windows (PowerShell):**
```powershell
$env:OPENMETADATA_HOST = "http://localhost:8585/api"
$env:OPENMETADATA_JWT_TOKEN = "eyJhbG..."
```

**Windows (Command Prompt):**
```cmd
set OPENMETADATA_HOST=http://localhost:8585/api
set OPENMETADATA_JWT_TOKEN=eyJhbG...
```

The JWT token comes from: OM UI → Settings → Bots → Ingestion Bot → Copy Token.

### Diff a specific entity

```bash
ometa-diff diff table my_service.prod_db.public.payments
ometa-diff diff table my_service.prod_db.public.payments --from 0.2 --to 0.4
ometa-diff diff table my_service.prod_db.public.payments --since 7d
```

### View a changelog

```bash
ometa-diff changelog --service my_service --since 30d
ometa-diff changelog --user admin --since 7d
ometa-diff changelog --type table --since 14d
```

---

## MCP Server

`ometa-diff serve` starts an MCP server over **STDIO transport** — the standard used by all MCP-compatible clients. It works with Claude Desktop, Cursor, VS Code (GitHub Copilot), Windsurf, Zed, and any other client that supports the MCP spec.

### Generic config (any MCP client)

Most clients accept a JSON config block like this:

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

Or if `ometa-diff` is already installed globally:

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

### Client-specific config paths

| Client | Config file location |
|--------|---------------------|
| **Claude Desktop** (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Claude Desktop** (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Cursor** | Settings → MCP → Add server |
| **VS Code + GitHub Copilot** | `.vscode/mcp.json` in your workspace |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` |
| **Zed** | `~/.config/zed/settings.json` under `"context_servers"` |
| **Any STDIO-compatible client** | Point `command` at `ometa-diff serve` |

### MCP Tools

| Tool | Description | Example prompt |
|------|-------------|----------------|
| `metadata_diff` | Field-by-field diff between two entity versions | "What changed in the payments table?" |
| `metadata_changelog` | Aggregated changes across a service, type, or user | "Show all metadata changes in my service this week" |
| `metadata_change_summary` | High-level stats: counts, major/minor split, top changers | "Give me a summary of catalog activity this month" |

---

## CLI Reference

```
ometa-diff diff <entity_type> <fqn> [--from VERSION] [--to VERSION] [--since Nd] [--format terminal|markdown|json]
ometa-diff changelog [--service NAME] [--user NAME] [--type TYPE] [--since Nd] [--format ...]
ometa-diff serve          # Start MCP server over STDIO
ometa-diff config         # Show current host and auth status
```

**Output formats:**

```bash
ometa-diff diff table payments --format json | jq '.changes[].field_path'
ometa-diff diff table payments --format markdown > diff.md
```

---

## Architecture

```
src/ometa_diff/
├── models.py       # Pydantic models: FieldChange, EntityDiff, CatalogChangelog
├── client.py       # HTTP client wrapping OM's version REST APIs
├── differ.py       # Core diff engine: compares two JSON version snapshots
├── changelog.py    # Multi-entity changelog aggregation over time windows
├── formatter.py    # Output rendering: terminal (Rich), markdown, JSON
├── mcp_server.py   # MCP server with 3 tools
└── cli.py          # Typer CLI entry point
```

No dependency on `openmetadata-ingestion` — uses `httpx` directly, same approach as OM's AI SDK.

---

## Platform Support

Tested on Python 3.10, 3.11, 3.12 on Ubuntu, macOS, and Windows via CI.

Terminal output uses ASCII-safe characters to avoid encoding issues on Windows consoles.

---

## Change Severity

| Severity | Examples |
|----------|---------|
| **MAJOR** | Column removed, column `dataType` changed, owner removed |
| **MINOR** | Description edited, tag added/removed, column added, owner changed |
| **PATCH** | Display name changed, other cosmetic updates |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENMETADATA_HOST` | `http://localhost:8585/api` | OM API base URL |
| `OPENMETADATA_JWT_TOKEN` | *(required)* | JWT bearer token from OM Bots settings |

Run `ometa-diff config` to verify the current values.

---

## Development

```bash
git clone https://github.com/SamChawla/ometa-diff
cd ometa-diff
pip install -e ".[dev,mcp]"

pytest tests/ -v              # Unit tests (no OM instance needed)
ruff check src/ tests/        # Lint
ruff format src/ tests/       # Format
```

### Integration tests (requires live OM)

Start OpenMetadata (see above), then:

```bash
# macOS / Linux
export OPENMETADATA_HOST=http://localhost:8585/api
export OPENMETADATA_JWT_TOKEN=eyJhbG...
pytest tests/test_integration.py -v -m integration

# Windows PowerShell
$env:OPENMETADATA_HOST = "http://localhost:8585/api"
$env:OPENMETADATA_JWT_TOKEN = "eyJhbG..."
pytest tests/test_integration.py -v -m integration
```

Integration tests are skipped automatically in CI (env vars not set). They verify connectivity, `resolve_fqn`, `list_versions`, `get_version`, diff correctness on real entities, noise-field filtering, and changelog aggregation.

### Remaining test coverage gaps

These require scenarios not easily automated:

| Gap | Reason |
|-----|--------|
| `ChangelogBuilder.for_service` with a real multi-table service | Needs seeded service data |
| `ChangelogBuilder.for_user` filtering | Needs multiple users with edit history |
| MCP tool invocation via an actual MCP client | Needs MCP client harness / E2E test |
| CLI output rendering (Rich terminal format) | TTY-dependent, hard to assert in CI |

---

## License

Apache 2.0 — same as OpenMetadata.
