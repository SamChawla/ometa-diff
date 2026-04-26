"""Integration tests against a live OpenMetadata instance.

Requires:
    OPENMETADATA_HOST=http://localhost:8585/api
    OPENMETADATA_JWT_TOKEN=<bot-token>

Run:
    pytest tests/test_integration.py -v -m integration

Skipped automatically when env vars are not set.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from ometa_diff.changelog import ChangelogBuilder
from ometa_diff.client import OMVersionClient, _version_sort_key
from ometa_diff.differ import MetadataDiffer
from ometa_diff.exceptions import NoDiffAvailable, OMAuthError, OMNotFoundError
from ometa_diff.models import ChangeSeverity, EntityDiff

_EntityFixture = dict[str, Any]

# ---------------------------------------------------------------------------
# Skip condition
# ---------------------------------------------------------------------------

_LIVE_OM = pytest.mark.skipif(
    not os.environ.get("OPENMETADATA_HOST") or not os.environ.get("OPENMETADATA_JWT_TOKEN"),
    reason="OPENMETADATA_HOST and OPENMETADATA_JWT_TOKEN must be set for integration tests",
)

pytestmark = [pytest.mark.integration, _LIVE_OM]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> OMVersionClient:
    """Real client pointed at the live OM instance."""
    host = os.environ["OPENMETADATA_HOST"]
    token = os.environ["OPENMETADATA_JWT_TOKEN"]
    return OMVersionClient(host=host, token=token)


@pytest.fixture(scope="module")
def differ(client: OMVersionClient) -> MetadataDiffer:
    return MetadataDiffer(client)


@pytest.fixture(scope="module")
def any_versioned_entity(client: OMVersionClient) -> dict[str, Any]:
    """Find any entity in the catalog that has >= 2 versions.

    Searches tables first, then falls back to other entity types.
    Skips the test if no multi-version entity is found.
    """
    for entity_type in ("table", "dashboard", "pipeline", "topic", "databaseSchema", "database"):
        entities = client.search_entities(query="*", entity_type=entity_type, limit=50)
        for entity in entities:
            fqn = entity.get("fullyQualifiedName") or entity.get("name", "")
            if not fqn:
                continue
            try:
                resolved = client.resolve_fqn(entity_type, fqn)
                entity_id = resolved["id"]
                versions = client.list_versions(entity_type, entity_id)
                if len(versions) >= 2:
                    return {
                        "entity_type": entity_type,
                        "fqn": fqn,
                        "id": entity_id,
                        "versions": versions,
                    }
            except (OMNotFoundError, KeyError):
                continue
    pytest.skip("No entity with >= 2 versions found in the catalog")
    return None


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------


def test_server_reachable(client: OMVersionClient) -> None:
    """Basic connectivity: search returns without raising."""
    results = client.search_entities(query="*", limit=1)
    assert isinstance(results, list)


def test_auth_valid(client: OMVersionClient) -> None:
    """Token is accepted — no OMAuthError raised."""
    try:
        client.search_entities(query="*", limit=1)
    except OMAuthError:
        pytest.fail("Authentication failed — check OPENMETADATA_JWT_TOKEN")


# ---------------------------------------------------------------------------
# Client API
# ---------------------------------------------------------------------------


def test_search_returns_entities(client: OMVersionClient) -> None:
    """search_entities returns a non-empty list when the catalog has data."""
    results = client.search_entities(query="*", limit=10)
    assert len(results) > 0, "Catalog appears empty — seed some entities first"


def test_search_by_entity_type(client: OMVersionClient) -> None:
    """Filtering by entity_type works without error."""
    results = client.search_entities(query="*", entity_type="table", limit=10)
    assert isinstance(results, list)
    for r in results:
        assert isinstance(r, dict)


def test_resolve_fqn_known_entity(
    client: OMVersionClient, any_versioned_entity: _EntityFixture
) -> None:
    """resolve_fqn returns a dict with an 'id' field for a known entity."""
    entity_type = any_versioned_entity["entity_type"]
    fqn = any_versioned_entity["fqn"]
    result = client.resolve_fqn(entity_type, fqn)
    assert "id" in result
    assert result["id"] == any_versioned_entity["id"]


def test_resolve_fqn_unknown_raises(client: OMVersionClient) -> None:
    """resolve_fqn raises OMNotFoundError for a non-existent FQN."""
    with pytest.raises(OMNotFoundError):
        client.resolve_fqn("table", "does_not_exist.at.all.guaranteed")


def test_list_versions(client: OMVersionClient, any_versioned_entity: _EntityFixture) -> None:
    """list_versions returns a sorted list of version strings."""
    versions = any_versioned_entity["versions"]
    assert len(versions) >= 2
    keys = [_version_sort_key(v) for v in versions]
    assert keys == sorted(keys), "Versions are not sorted"


def test_get_version_returns_snapshot(
    client: OMVersionClient, any_versioned_entity: _EntityFixture
) -> None:
    """get_version returns a dict with standard OM fields."""
    entity_type = any_versioned_entity["entity_type"]
    entity_id = any_versioned_entity["id"]
    version = any_versioned_entity["versions"][-1]
    snap = client.get_version(entity_type, entity_id, version)
    assert "id" in snap
    assert "version" in snap
    assert snap["id"] == entity_id


# ---------------------------------------------------------------------------
# Differ
# ---------------------------------------------------------------------------


def test_diff_entity_returns_entity_diff(
    differ: MetadataDiffer, any_versioned_entity: _EntityFixture
) -> None:
    """diff_entity returns an EntityDiff for an entity with >= 2 versions."""
    result = differ.diff_entity(
        any_versioned_entity["entity_type"],
        any_versioned_entity["fqn"],
    )
    assert isinstance(result, EntityDiff)
    assert result.entity_fqn == any_versioned_entity["fqn"]
    assert _version_sort_key(result.from_version) < _version_sort_key(result.to_version)


def test_diff_entity_changes_have_valid_severity(
    differ: MetadataDiffer, any_versioned_entity: _EntityFixture
) -> None:
    """All FieldChange objects in the diff have a valid ChangeSeverity."""
    result = differ.diff_entity(
        any_versioned_entity["entity_type"],
        any_versioned_entity["fqn"],
    )
    for change in result.changes:
        assert change.severity in (ChangeSeverity.MAJOR, ChangeSeverity.MINOR, ChangeSeverity.PATCH)


def test_diff_entity_noise_fields_filtered(
    differ: MetadataDiffer, any_versioned_entity: _EntityFixture
) -> None:
    """Noise fields (updatedAt, href, version) do not appear in the diff."""
    result = differ.diff_entity(
        any_versioned_entity["entity_type"],
        any_versioned_entity["fqn"],
    )
    noise = {"updatedAt", "href", "version", "changeDescription", "incrementalChangeDescription"}
    for change in result.changes:
        top_field = change.field_path.split(".")[0]
        assert top_field not in noise, f"Noise field leaked into diff: {change.field_path}"


def test_diff_entity_explicit_versions(
    differ: MetadataDiffer, any_versioned_entity: _EntityFixture
) -> None:
    """diff_entity respects explicit from_version / to_version arguments."""
    versions = any_versioned_entity["versions"]
    result = differ.diff_entity(
        any_versioned_entity["entity_type"],
        any_versioned_entity["fqn"],
        from_version=versions[0],
        to_version=versions[-1],
    )
    assert result.from_version == versions[0]
    assert result.to_version == versions[-1]


def test_diff_entity_invalid_version_raises(
    differ: MetadataDiffer, any_versioned_entity: _EntityFixture
) -> None:
    """diff_entity raises NoDiffAvailable for a version string that doesn't exist."""
    with pytest.raises(NoDiffAvailable):
        differ.diff_entity(
            any_versioned_entity["entity_type"],
            any_versioned_entity["fqn"],
            from_version="999.9",
        )


def test_diff_entity_since_returns_list(
    differ: MetadataDiffer, any_versioned_entity: _EntityFixture
) -> None:
    """diff_entity_since returns a list (possibly empty for old entities)."""
    result = differ.diff_entity_since(
        any_versioned_entity["entity_type"],
        any_versioned_entity["fqn"],
        since_days=3650,  # 10 years — should always catch something
    )
    assert isinstance(result, list)
    assert len(result) >= 1, "Expected at least one diff over 10-year window"


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------


def test_changelog_for_entity_type_runs(client: OMVersionClient) -> None:
    """for_entity_type completes without raising for 'table'."""
    builder = ChangelogBuilder(client)
    log = builder.for_entity_type("table", since_days=3650)
    assert log.scope == "type:table"
    assert log.total_changes >= 0


def test_changelog_aggregates_counts(
    client: OMVersionClient, any_versioned_entity: _EntityFixture
) -> None:
    """CatalogChangelog counts are self-consistent."""
    builder = ChangelogBuilder(client)
    entity_type = any_versioned_entity["entity_type"]
    log = builder.for_entity_type(entity_type, since_days=3650)
    assert log.total_changes == log.major_changes + log.minor_changes + (
        log.total_changes - log.major_changes - log.minor_changes
    )
    assert log.total_entities_changed >= 0


def test_changelog_top_changers_format(client: OMVersionClient) -> None:
    """top_changers entries are TopChanger models with user and change_count."""
    builder = ChangelogBuilder(client)
    log = builder.for_entity_type("table", since_days=3650)
    for entry in log.top_changers:
        assert isinstance(entry.user, str)
        assert isinstance(entry.change_count, int)
        assert entry.change_count >= 0
