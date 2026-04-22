"""Shared pytest fixtures with mock OM API responses.

All snapshots mirror the real shape returned by:
  GET /api/v1/tables/{id}/versions/{ver}
"""

from __future__ import annotations

import pytest

from ometa_diff.client import OMVersionClient

# ---------------------------------------------------------------------------
# Table version snapshots
# ---------------------------------------------------------------------------


@pytest.fixture
def table_version_v1() -> dict:
    """Realistic table entity snapshot at version 0.1 (initial creation)."""
    return {
        "id": "a1b2c3d4-0001-0001-0001-000000000001",
        "name": "payments",
        "fullyQualifiedName": "my_service.prod_db.public.payments",
        "displayName": "Payments",
        "description": "Stores payment records",
        "version": 0.1,
        "updatedAt": 1713000000000,
        "updatedBy": "admin",
        "href": "http://localhost:8585/api/v1/tables/a1b2c3d4-0001-0001-0001-000000000001",
        "tableType": "Regular",
        "service": {"id": "svc-001", "name": "my_service", "type": "databaseService"},
        "database": {"id": "db-001", "name": "prod_db", "type": "database"},
        "databaseSchema": {"id": "schema-001", "name": "public", "type": "databaseSchema"},
        "owner": {"id": "user-001", "name": "data_team", "type": "team"},
        "tags": [],
        "columns": [
            {
                "name": "payment_id",
                "dataType": "BIGINT",
                "description": "Primary key",
                "tags": [],
                "ordinalPosition": 1,
            },
            {
                "name": "amount",
                "dataType": "DECIMAL",
                "description": "Payment amount in USD",
                "tags": [],
                "ordinalPosition": 2,
            },
            {
                "name": "payment_method",
                "dataType": "VARCHAR",
                "description": "Payment method used",
                "tags": [],
                "ordinalPosition": 3,
            },
        ],
    }


@pytest.fixture
def table_version_v2() -> dict:
    """Same table at version 0.2: description changed, column added, tag added."""
    return {
        "id": "a1b2c3d4-0001-0001-0001-000000000001",
        "name": "payments",
        "fullyQualifiedName": "my_service.prod_db.public.payments",
        "displayName": "Payments",
        "description": "Stores payment transaction records",  # MODIFIED
        "version": 0.2,
        "updatedAt": 1713086400000,
        "updatedBy": "alice",
        "href": "http://localhost:8585/api/v1/tables/a1b2c3d4-0001-0001-0001-000000000001",
        "tableType": "Regular",
        "service": {"id": "svc-001", "name": "my_service", "type": "databaseService"},
        "database": {"id": "db-001", "name": "prod_db", "type": "database"},
        "databaseSchema": {"id": "schema-001", "name": "public", "type": "databaseSchema"},
        "owner": {"id": "user-001", "name": "data_team", "type": "team"},
        "tags": [
            {"tagFQN": "PII.Sensitive", "source": "Manual", "labelType": "Manual"},  # ADDED
        ],
        "columns": [
            {
                "name": "payment_id",
                "dataType": "BIGINT",
                "description": "Primary key",
                "tags": [],
                "ordinalPosition": 1,
            },
            {
                "name": "amount",
                "dataType": "DECIMAL",
                "description": "Payment amount in USD",
                "tags": [],
                "ordinalPosition": 2,
            },
            {
                "name": "payment_method",
                "dataType": "VARCHAR",
                "description": "Payment method used",
                "tags": [],
                "ordinalPosition": 3,
            },
            {
                "name": "currency",  # ADDED column
                "dataType": "VARCHAR",
                "description": "ISO currency code",
                "tags": [],
                "ordinalPosition": 4,
            },
        ],
    }


@pytest.fixture
def table_version_v3() -> dict:
    """Same table at version 0.3: column removed (MAJOR), owner changed (MINOR)."""
    return {
        "id": "a1b2c3d4-0001-0001-0001-000000000001",
        "name": "payments",
        "fullyQualifiedName": "my_service.prod_db.public.payments",
        "displayName": "Payments",
        "description": "Stores payment transaction records",
        "version": 0.3,
        "updatedAt": 1713172800000,
        "updatedBy": "bob",
        "href": "http://localhost:8585/api/v1/tables/a1b2c3d4-0001-0001-0001-000000000001",
        "tableType": "Regular",
        "service": {"id": "svc-001", "name": "my_service", "type": "databaseService"},
        "database": {"id": "db-001", "name": "prod_db", "type": "database"},
        "databaseSchema": {"id": "schema-001", "name": "public", "type": "databaseSchema"},
        "owner": {"id": "user-002", "name": "payments_team", "type": "team"},  # MODIFIED
        "tags": [
            {"tagFQN": "PII.Sensitive", "source": "Manual", "labelType": "Manual"},
        ],
        "columns": [
            {
                "name": "payment_id",
                "dataType": "BIGINT",
                "description": "Primary key",
                "tags": [],
                "ordinalPosition": 1,
            },
            {
                "name": "amount",
                "dataType": "DECIMAL",
                "description": "Payment amount in USD",
                "tags": [],
                "ordinalPosition": 2,
            },
            # payment_method column REMOVED (MAJOR)
            {
                "name": "currency",
                "dataType": "VARCHAR",
                "description": "ISO currency code",
                "tags": [],
                "ordinalPosition": 3,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Mock client
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_om_client(monkeypatch) -> OMVersionClient:
    """OMVersionClient with HTTP calls replaced by in-memory data.

    Tests should monkeypatch specific methods as needed rather than hitting
    a real OpenMetadata instance.
    """

    # Build a real client pointed at a non-existent host; tests override methods.
    client = OMVersionClient(host="http://localhost:8585/api", token="test-token")
    return client
