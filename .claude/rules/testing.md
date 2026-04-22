# Testing Conventions

## Structure

```
tests/
├── conftest.py           # Shared fixtures: mock OM responses, sample snapshots
├── test_client.py        # OMVersionClient tests (mock HTTP)
├── test_differ.py        # MetadataDiffer tests (pure logic, no HTTP)
├── test_changelog.py     # ChangelogBuilder tests (mock client)
├── test_formatter.py     # Output formatting tests
├── test_cli.py           # CLI integration tests (Typer test runner)
└── test_mcp_server.py    # MCP tool tests
```

## Fixture Design

All fixtures go in `conftest.py`. Key fixtures needed:

```python
@pytest.fixture
def table_version_v1() -> dict:
    """A realistic table entity snapshot at version 0.1"""

@pytest.fixture
def table_version_v2() -> dict:
    """Same table at version 0.2 with: description changed, column added, tag added"""

@pytest.fixture
def table_version_v3() -> dict:
    """Same table at version 0.3 with: column removed (MAJOR), owner changed"""

@pytest.fixture
def mock_om_client() -> OMVersionClient:
    """Client with mocked HTTP responses — never hits a real server"""
```

Fixtures should use realistic OM entity JSON — match the actual shape returned by
`GET /api/v1/tables/{id}/versions/{ver}`. Include fields like:
`id`, `name`, `fullyQualifiedName`, `version`, `updatedAt`, `updatedBy`,
`columns` (array with name, dataType, description), `tags`, `owner`,
`description`, `service`, `database`, `databaseSchema`

## Test Patterns

- Test the diff engine with PURE LOGIC tests — pass in two dicts, assert the FieldChange list
- Test the client with MOCKED HTTP — use `httpx.MockTransport` or `respx`
- Test the CLI with Typer's `CliRunner`
- Test formatters by asserting output contains expected strings

## What Must Be Tested

The diff engine is the core value — it needs the most coverage:

1. No changes → empty changes list
2. Description modified → MINOR severity
3. Column added → MINOR severity
4. Column removed → MAJOR severity
5. Column dataType changed → MAJOR severity
6. Tag added → MINOR severity
7. Tag removed → MINOR severity
8. Owner changed → MINOR severity
9. Owner removed → MAJOR severity
10. Multiple simultaneous changes → correct count and severities
11. Noise fields (updatedAt, href, version) → filtered out, NOT in changes

## Do NOT

- Do NOT require a running OpenMetadata instance for unit tests
- Do NOT use `unittest.mock.patch` on internal implementation — test via public API
- Do NOT write tests that depend on test execution order
