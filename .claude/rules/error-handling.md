# Error Handling

## Custom Exception Hierarchy

Define in `src/ometa_diff/exceptions.py`:

```python
class OmetaDiffError(Exception):
    """Base exception for ometa-diff."""

class OMConnectionError(OmetaDiffError):
    """Cannot reach the OpenMetadata server."""

class OMAuthError(OmetaDiffError):
    """JWT token is invalid or missing."""

class OMNotFoundError(OmetaDiffError):
    """Entity not found (404 from OM API)."""

class OMAPIError(OmetaDiffError):
    """Unexpected error from OM API."""

class NoDiffAvailable(OmetaDiffError):
    """Entity has only one version — nothing to diff."""
```

## HTTP Error Mapping

| OM API Status | Our Exception | CLI Behavior |
|--------------|---------------|-------------|
| Connection refused | OMConnectionError | "Cannot connect to OpenMetadata at {host}. Is the server running?" |
| 401 | OMAuthError | "Authentication failed. Check OPENMETADATA_JWT_TOKEN." |
| 404 | OMNotFoundError | "Entity '{fqn}' not found. Check the fully qualified name." |
| 5xx | OMAPIError | "OpenMetadata server error: {status_code}" |

## Rules

- CLI must NEVER show raw tracebacks to users — catch exceptions and show friendly messages via Rich
- Library API should raise typed exceptions — let callers handle them
- MCP server must catch all exceptions and return error text — never crash the server process
- Always include actionable guidance in error messages ("Check OPENMETADATA_JWT_TOKEN" not just "Auth failed")
