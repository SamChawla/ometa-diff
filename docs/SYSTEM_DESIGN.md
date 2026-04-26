# ometa-diff: System Design Document

## 1. Introduction

**ometa-diff** is a Python-based utility that provides metadata version-diff intelligence for OpenMetadata (OM). While OM natively tracks version history for data catalog entities, it only exposes raw JSON snapshots. `ometa-diff` bridges this gap by fetching these snapshots, computing semantic, field-level differences, and classifying them by severity.

It exposes this functionality through two primary interfaces:
1. **MCP Server**: Allowing AI Agents (like Claude Desktop) to proactively query metadata changes.
2. **CLI Tool**: Allowing human engineers to run commands directly in their terminal or CI/CD pipelines.

## 2. High-Level Architecture

The system is designed as a stateless middleware layer sitting between the user (or AI agent) and the OpenMetadata server. 

```mermaid
graph TD
    User(CLI User / CI-CD) --> CLI[cli.py (Typer)]
    Agent(AI Agent / Claude) --> MCP[mcp_server.py (FastMCP)]
    
    CLI --> Differ[differ.py / changelog.py]
    CLI --> Formatter[formatter.py]
    
    MCP --> Differ
    MCP --> Formatter
    
    Differ --> Client[client.py (httpx)]
    Differ --> Models[(models.py)]
    
    Client -- HTTP GET --> OM_REST(OpenMetadata REST API)
```

## 3. Core Components

The architecture follows a modular, separation-of-concerns pattern to ensure the core business logic (diffing) is entirely decoupled from the presentation layers (CLI/MCP).

### 3.1 Data Layer (`models.py`)
Uses `pydantic` v2 to enforce strict schemas for all data crossing module boundaries.
- **`FieldChange`**: Represents a single mutation (e.g., `columns.payment_id.description` was MODIFIED).
- **`EntityDiff`**: Represents a full version-to-version change for a specific entity.
- **`CatalogChangelog`**: Represents aggregated changes across multiple entities over a time window.

### 3.2 HTTP Interface (`client.py`)
A thin, lightweight `httpx` wrapper strictly focused on reading from OpenMetadata's REST endpoints:
- Resolving FQNs to UUIDs (`/api/v1/{type}/name/{fqn}`).
- Listing versions (`/api/v1/{type}/{id}/versions`).
- Fetching specific snapshots (`/api/v1/{type}/{id}/versions/{v}`).
- Executing ElasticSearch queries for aggregation (`/api/v1/search/query`).

### 3.3 Diff Engine (`differ.py`)
The "brain" of the application. It takes two raw JSON dictionaries (old vs. new) and:
1. Flattens nested JSON structures into dot-notation paths.
2. Smartly handles arrays (e.g., matching columns by `name` rather than array index to prevent false positives when column order changes).
3. Compares paths and identifies `ADDED`, `REMOVED`, or `MODIFIED` keys.
4. Classifies changes into `MAJOR`, `MINOR`, or `PATCH` severity based on predefined logic rules.
5. Filters out system "noise" (e.g., `updatedAt`, `href`, `version`).

### 3.4 Aggregation Layer (`changelog.py`)
Handles multi-entity scopes. It uses `client.search_entities()` to find all assets matching a criteria (e.g., specific service or owner), fetches their versions within a date range, passes them to `differ.py`, and rolls up the results into a `CatalogChangelog`.

### 3.5 Presentation Layer (`formatter.py`)
Translates `pydantic` models into user-friendly outputs:
- **Terminal**: Uses `rich` to print beautiful, color-coded ascii tables and diffs.
- **Markdown**: Formats output for AI agents (MCP) or GitHub PR comments.
- **JSON**: Outputs pure JSON for jq piping.

## 4. Key Data Flows

### The "Diff" Flow
1. User requests diff for `table: payments` via CLI.
2. `cli.py` calls `differ.diff_entity("table", "payments")`.
3. `differ.py` uses `client.py` to resolve the FQN and fetch the 2 most recent snapshots.
4. `differ.py` flattens both snapshots, computes differences, applies severity rules, and returns an `EntityDiff` object.
5. `cli.py` passes the `EntityDiff` to `formatter.py`, which prints a `rich` table to stdout.

## 5. Key Design Decisions

1. **Lightweight HTTP Client vs OM Ingestion SDK**:
   - *Decision:* Build a custom `httpx` client (`client.py`) instead of depending on `openmetadata-ingestion`.
   - *Rationale:* The OM ingestion SDK is massive and carries dozens of heavy dependencies. Since we only need to perform `GET` requests against the REST API, a thin `httpx` client keeps `ometa-diff` lightning-fast, highly portable, and extremely easy to install.
2. **Stateless Execution**:
   - *Decision:* The tool maintains zero local database or state.
   - *Rationale:* Ensures easy containerization and simplifies CI/CD integration. OM serves as the absolute source of truth.
3. **Pydantic Validation boundary**:
   - *Decision:* Raw JSON from OM is heavily unstructured. We keep it as `dict` during the diffing phase, but the *output* of the diff is strictly cast into `Pydantic` models.
   - *Rationale:* Diffing flat dictionaries is mathematically simpler, but returning strictly typed models ensures the CLI, MCP server, and Formatters never encounter unexpected `KeyError`s.
