# ometa-diff

An MCP server that adds metadata version-diff intelligence to OpenMetadata. Lets AI agents and engineers answer "what changed in my data catalog?"

## Project Context

See @ometa-diff-final-plan.md for full project plan, architecture, and module designs.

## Stack

- Python 3.10+, Pydantic v2, httpx for HTTP
- Typer for CLI, Rich for terminal output
- Official `mcp` Python SDK for MCP server
- Hatchling build system, ruff for linting, pytest for tests
- Published to PyPI as `ometa-diff`

## Architecture

```
src/ometa_diff/
├── models.py       # Pydantic models: FieldChange, EntityDiff, CatalogChangelog
├── client.py       # HTTP client wrapping OM's version REST APIs (no openmetadata-ingestion dependency)
├── differ.py       # Core diff engine: compares two JSON version snapshots
├── changelog.py    # Multi-entity changelog aggregation over time windows
├── formatter.py    # Output rendering: terminal (Rich), markdown, JSON
├── mcp_server.py   # MCP server exposing 3 tools: metadata_diff, metadata_changelog, metadata_change_summary
└── cli.py          # Typer CLI: ometa-diff diff, changelog, serve, config
```

## Commands

- Lint: `ruff check src/ tests/`
- Format: `ruff format src/ tests/`
- Test: `pytest tests/ -v`
- Test single: `pytest tests/test_differ.py -v`
- Install local: `pip install -e ".[dev,mcp]"`
- Build: `python -m build`
- Type check: `pyright src/` (if installed)

## OpenMetadata Conventions (IMPORTANT)

This project follows OM ecosystem conventions:
- Env vars: `OPENMETADATA_HOST`, `OPENMETADATA_JWT_TOKEN` (same as OM SDK — do NOT invent custom names)
- Entity types: lowercase strings exactly as OM uses: `table`, `dashboard`, `pipeline`, `topic`, `mlmodel`, `glossaryTerm`, `dataProduct`
- FQN format: `service.database.schema.table_name`
- No dependency on `openmetadata-ingestion` — use httpx directly (same approach as OM's AI SDK `data-ai-sdk`)
- License: Apache 2.0

## Code Rules

- Type hints on ALL public functions and method signatures
- Pydantic v2 models for all data structures — no raw dicts crossing module boundaries
- Docstrings on all public classes and methods (one-line or Google style)
- No bare `except:` — always catch specific exceptions
- HTTP errors: raise typed exceptions (OMConnectionError, OMAuthError, OMNotFoundError, OMAPIError)
- Never print() — use Rich console for CLI output, return structured data from library functions
- Imports: stdlib first, then third-party, then local — ruff handles ordering

## Testing Rules

- Every module gets a corresponding test file: `differ.py` → `test_differ.py`
- Use mock OM API responses in fixtures — tests must NOT require a running OM instance
- Test the diff engine with at least these scenarios:
  1. Field added
  2. Field removed
  3. Field modified
  4. Column added to table
  5. Column removed from table
  6. Column dataType changed (MAJOR severity)
  7. Description changed (MINOR severity)
  8. Tag added/removed
  9. Owner changed
  10. No changes (identical versions)
- Keep fixtures in `tests/conftest.py` — sample version snapshots as dicts

## Git Conventions

- Commit format: `type(scope): description`
- Types: feat, fix, refactor, test, docs, chore
- Branch: `main` only (hackathon pace)

## What NOT to Do

- Do NOT depend on `openmetadata-ingestion` — it's too heavy
- Do NOT create new API endpoints — we read from OM's existing version APIs
- Do NOT use `deepdiff` library — roll our own diff logic for control over severity classification and noise filtering
- Do NOT hardcode OM host or token anywhere — always from env vars or configure()
- Do NOT add async complexity unless specifically needed — keep it sync-first for simplicity
