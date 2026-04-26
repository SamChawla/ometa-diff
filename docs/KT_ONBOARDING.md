# Knowledge Transfer (KT) & Onboarding Document

Welcome to **ometa-diff**! 🚀 We are thrilled to have you onboard. 

This document is designed for developers who are completely new to the codebase. It will walk you through the project setup, our architectural patterns, how to navigate the repository, and how to safely contribute your first feature.

---

## 1. What is ometa-diff?

OpenMetadata natively keeps track of version histories for all data assets (tables, dashboards, pipelines), but it doesn't have a way to intelligently compare versions. If a user asks *"What changed in this database?"*, they currently have to look at giant JSON payloads. 

**ometa-diff** solves this. It pulls the raw JSON snapshots from OpenMetadata via its REST API, compares them field-by-field, categorizes the severity of the changes, and presents them cleanly to human engineers (via CLI) or AI agents (via our MCP Server).

---

## 2. Local Setup & Prerequisites

You don't need a huge environment to run this.

### Requirements:
1. Python 3.10 or higher.
2. A local or Sandbox OpenMetadata instance to test against.

### Installation:
```bash
# Clone the repository
git clone https://github.com/SamChawla/ometa-diff
cd ometa-diff

# Install in editable mode with development & MCP dependencies
pip install -e ".[dev,mcp]"
```

### Environment Variables:
The app strictly reads the OM connection details from environment variables.
```bash
export OPENMETADATA_HOST=http://localhost:8585/api
export OPENMETADATA_JWT_TOKEN=your_jwt_token_here
```
*(Tip: In OpenMetadata, you can grab a JWT token by navigating to Settings -> Bots -> Ingestion Bot).*

---

## 3. Navigating the Codebase

Everything important lives in `src/ometa_diff/`. Here is the mental map of how the files relate to each other:

1. **`models.py`**: Start here. This file defines what a `FieldChange`, an `EntityDiff`, and a `CatalogChangelog` look like using `pydantic`. All internal layers communicate using these models.
2. **`client.py`**: This is our HTTP bridge to OpenMetadata. It uses `httpx`. We **do not** use the official `openmetadata-ingestion` python package because it is too heavy. If you need a new OpenMetadata API endpoint, add it here.
3. **`differ.py`**: The core logic engine. It takes two raw JSON `dict`s from `client.py` and figures out what changed. 
4. **`changelog.py`**: Uses `client.py`'s ElasticSearch wrapper to find many entities, then loops over them using `differ.py` to build aggregated histories.
5. **`formatter.py`**: Takes the Pydantic models and makes them pretty (either a Markdown string or a `rich` ASCII terminal table).
6. **`cli.py`**: The Typer application that binds everything together for terminal users.
7. **`mcp_server.py`**: The FastMCP wrapper that exposes the exact same logic to AI agents.

---

## 4. How the Code Works: A Trace

Let's trace what happens when you run `ometa-diff diff table my_db.schema.users`.

1. **CLI Layer (`cli.py`)**: `app()` parses the command. It calls `differ.diff_entity("table", "my_db.schema.users")`.
2. **Fetch (`differ.py` + `client.py`)**: 
   - `client.resolve_fqn` looks up the entity ID.
   - `client.list_versions` gets the history array (e.g., `["0.1", "0.2"]`).
   - `client.get_version` fetches the raw JSON payloads for `"0.1"` and `"0.2"`.
3. **Compare (`differ.py`)**: 
   - `differ.diff_versions()` flattens both JSONs into dictionaries like `{"columns.user_id.dataType": "INT"}`.
   - It compares the keys to find additions, deletions, and modifications.
   - It applies rules to classify severity (e.g., if `dataType` changes, it's marked as `MAJOR`).
4. **Format (`cli.py` + `formatter.py`)**: The resulting `EntityDiff` object is sent to `formatter.py` which prints the colorful table to your console.

---

## 5. Testing Strategy

We take testing seriously to ensure we don't break diff logic.

- **Run tests:** `pytest tests/ -v`
- **Linting:** `ruff check src/ tests/` (You must pass this before your PR is merged!)

**Testing Rules:**
- **No live APIs in tests!** We use `pytest` fixtures in `tests/conftest.py`. If you open that file, you'll see hardcoded mock JSON snapshots mimicking OpenMetadata's output.
- Every module has a matching test file (e.g., `differ.py` -> `test_differ.py`).
- If you add a new feature (like a new way to match JSON fields), write a unit test in `test_differ.py` using the mock snapshots.

---

## 6. How to Contribute Your First Feature

Let's say we want to add a rule: *"If a column's tags change, classify it as a MINOR change instead of PATCH."*

1. **Locate the logic:** Open `src/ometa_diff/differ.py`.
2. **Find the Severity Classifier:** Look for the method (likely named `_classify_severity`) that checks the field path string.
3. **Add the condition:** Add `if "tags" in field_path: return ChangeSeverity.MINOR`.
4. **Write a test:** Open `tests/test_differ.py`, add a test function `test_tag_change_is_minor()` that sends mock JSON with different tags to the differ, and `assert diff.severity == "minor"`.
5. **Lint and Test:** Run `pytest` and `ruff check`.
6. **Submit PR:** Commit to a branch and open a Pull Request! The GitHub Action will automatically run tests across Mac, Linux, and Windows to guarantee cross-platform safety.

---

## 7. FAQ & Gotchas

- **Why didn't my diff show the `updatedAt` field?**
  We actively filter out "noise" fields like `updatedAt`, `version`, and `href` in `differ.py`. Users don't care about these systemic timestamp changes, only metadata mutations.
- **Why aren't we using `DeepDiff`?**
  Libraries like `DeepDiff` are great, but they are very generic and bad at domain-specific logic. For example, OpenMetadata lists columns as an array. If a user deletes column #2, `DeepDiff` will flag columns #3, #4, and #5 as "changed" because their array indices shifted. Our custom differ intelligently matches arrays by identity (`name` for columns, `tagFQN` for tags) to avoid this.
- **I'm getting an `OMAuthError`.**
  Double-check your `OPENMETADATA_JWT_TOKEN` environment variable. If testing against a Sandbox, tokens expire frequently.

Welcome to the team! 🎉
