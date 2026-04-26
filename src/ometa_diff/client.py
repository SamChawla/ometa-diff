"""HTTP client for OpenMetadata's version REST APIs."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from ometa_diff.exceptions import OMAPIError, OMAuthError, OMConnectionError, OMNotFoundError

SUPPORTED_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "table",
        "database",
        "databaseSchema",
        "dashboard",
        "chart",
        "pipeline",
        "topic",
        "mlmodel",
        "container",
        "storedProcedure",
        "searchIndex",
        "glossaryTerm",
        "tag",
        "dataProduct",
    }
)

# OM REST API uses plural paths — map singular type names to their URL segments.
_ENTITY_TYPE_TO_PATH: dict[str, str] = {
    "table": "tables",
    "database": "databases",
    "databaseSchema": "databaseSchemas",
    "dashboard": "dashboards",
    "chart": "charts",
    "pipeline": "pipelines",
    "topic": "topics",
    "mlmodel": "mlmodels",
    "container": "containers",
    "storedProcedure": "storedProcedures",
    "searchIndex": "searchIndexes",
    "glossaryTerm": "glossaryTerms",
    "tag": "tags",
    "dataProduct": "dataProducts",
}


def _version_sort_key(v: str) -> tuple[int, ...]:
    """Return a numeric sort key from a version string like '0.1' or '1.10.2'.

    Falls back to (0,) for non-numeric versions so they sort to the front
    rather than raising.
    """
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)


def _entity_path(entity_type: str) -> str:
    """Return the plural REST path segment for an entity type.

    Falls back to appending 's' for unknown types.
    """
    return _ENTITY_TYPE_TO_PATH.get(entity_type, f"{entity_type}s")


def client_from_env() -> OMVersionClient:
    """Create an OMVersionClient from environment variables.

    Reads OPENMETADATA_HOST and OPENMETADATA_JWT_TOKEN.
    """
    host = os.environ.get("OPENMETADATA_HOST", "http://localhost:8585/api")
    token = os.environ.get("OPENMETADATA_JWT_TOKEN", "")
    return OMVersionClient(host=host, token=token)


class OMVersionClient:
    """Reads version history from OpenMetadata's REST API.

    Uses httpx for HTTP — no dependency on openmetadata-ingestion.
    """

    def __init__(self, host: str, token: str) -> None:
        """Initialise the client.

        Args:
            host: Base URL of the OM API, e.g. 'http://localhost:8585/api'.
            token: JWT bearer token from OM Settings → Bots → Ingestion Bot.
        """
        self._host = host.rstrip("/")
        self._http = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request and return parsed JSON.

        Args:
            path: API path starting with '/v1/...'.
            params: Optional query parameters.

        Raises:
            OMConnectionError: Server unreachable or timed out.
            OMAuthError: 401 response.
            OMNotFoundError: 404 response.
            OMAPIError: Any other non-2xx response.
        """
        url = f"{self._host}{path}"
        try:
            response = self._http.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise OMConnectionError(f"Request timed out connecting to {self._host}.") from exc
        except httpx.TransportError as exc:
            raise OMConnectionError(
                f"Cannot connect to OpenMetadata at {self._host}. Is the server running?"
            ) from exc

        if response.status_code == 401:
            raise OMAuthError("Authentication failed. Check OPENMETADATA_JWT_TOKEN.")
        if response.status_code == 404:
            raise OMNotFoundError(f"Not found: {path}")
        if response.status_code >= 500:
            raise OMAPIError(f"OpenMetadata server error: {response.status_code}")
        if not response.is_success:
            raise OMAPIError(
                f"Unexpected API error: {response.status_code} — {response.text[:200]}"
            )

        return response.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_versions(self, entity_type: str, entity_id: str) -> list[str]:
        """List all available version numbers for an entity.

        Args:
            entity_type: OM entity type, e.g. 'table'.
            entity_id: UUID of the entity.

        Returns:
            Sorted list of version strings, e.g. ['0.1', '0.2', '1.2'].

        Note:
            OM returns each version as a full JSON snapshot string; we extract
            just the 'version' field from each and sort numerically.
        """
        data = self._get(f"/v1/{_entity_path(entity_type)}/{entity_id}/versions")
        raw = data.get("versions", [])
        versions: list[str] = []
        for item in raw:
            v: Any = None
            if isinstance(item, str):
                try:
                    snap: dict[str, Any] = json.loads(item)
                    v = snap.get("version")
                except (json.JSONDecodeError, AttributeError):
                    continue
            elif isinstance(item, dict):
                v = item.get("version")
            else:
                v = item
            if v is not None:
                versions.append(str(v))
        return sorted(versions, key=_version_sort_key)

    def get_version(self, entity_type: str, entity_id: str, version: str) -> dict[str, Any]:
        """Fetch a specific version snapshot of an entity.

        Args:
            entity_type: OM entity type, e.g. 'table'.
            entity_id: UUID of the entity.
            version: Version string, e.g. '0.2'.

        Returns:
            Raw entity JSON at that version.
        """
        return self._get(f"/v1/{_entity_path(entity_type)}/{entity_id}/versions/{version}")

    def resolve_fqn(self, entity_type: str, fqn: str) -> dict[str, Any]:
        """Resolve a fully-qualified name to the full entity dict (including id).

        Args:
            entity_type: OM entity type, e.g. 'table'.
            fqn: Fully qualified name, e.g. 'my_service.db.schema.payments'.

        Returns:
            Full entity JSON including 'id', 'version', etc.

        Raises:
            OMNotFoundError: If the FQN does not exist.
        """
        try:
            return self._get(f"/v1/{_entity_path(entity_type)}/name/{fqn}")
        except OMNotFoundError as exc:
            raise OMNotFoundError(
                f"Entity '{fqn}' not found. Check the fully qualified name."
            ) from exc

    def search_entities(
        self,
        query: str,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search for entities using OM's search API.

        Args:
            query: Search query string (supports wildcards).
            entity_type: Optional filter to a specific entity type.
            limit: Maximum results to return.

        Returns:
            List of entity source dicts from the search hits.
        """
        params: dict[str, Any] = {"q": query, "limit": limit}
        if entity_type:
            params["index"] = f"{entity_type}_search_index"
        data = self._get("/v1/search/query", params=params)
        hits = data.get("hits", {}).get("hits", [])
        return [h.get("_source", {}) for h in hits]

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> OMVersionClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
