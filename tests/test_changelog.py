"""Unit tests for ChangelogBuilder."""

from __future__ import annotations

import pytest

from ometa_diff.changelog import ChangelogBuilder
from ometa_diff.differ import MetadataDiffer


@pytest.fixture
def diff_v1_v2(mock_om_client, table_version_v1, table_version_v2):
    """Pre-computed EntityDiff for v1→v2 (3 minor changes)."""
    return MetadataDiffer(mock_om_client).diff_versions(table_version_v1, table_version_v2, "table")


@pytest.fixture
def diff_v2_v3(mock_om_client, table_version_v2, table_version_v3):
    """Pre-computed EntityDiff for v2→v3 (1 major + 1 minor change)."""
    return MetadataDiffer(mock_om_client).diff_versions(table_version_v2, table_version_v3, "table")


@pytest.fixture
def mock_search_result() -> list[dict]:
    """Minimal entity dicts as returned by search_entities."""
    return [
        {
            "entityType": "table",
            "fullyQualifiedName": "my_service.prod_db.public.payments",
            "id": "a1b2c3d4-0001-0001-0001-000000000001",
        }
    ]


# ---------------------------------------------------------------------------
# for_service
# ---------------------------------------------------------------------------


class TestChangelogForService:
    def test_returns_catalog_changelog_with_correct_scope(
        self, mock_om_client, mock_search_result, diff_v1_v2, monkeypatch
    ):
        monkeypatch.setattr(mock_om_client, "search_entities", lambda **kw: mock_search_result)
        monkeypatch.setattr(
            MetadataDiffer,
            "diff_entity_since",
            lambda self, et, fqn, since_days: [diff_v1_v2],
        )
        builder = ChangelogBuilder(mock_om_client)
        result = builder.for_service("my_service", since_days=7)

        assert result.scope == "service:my_service"
        assert result.total_entities_changed == 1
        assert result.total_changes == 3
        assert result.major_changes == 0
        assert result.minor_changes == 3

    def test_aggregates_top_changers(
        self, mock_om_client, mock_search_result, diff_v1_v2, monkeypatch
    ):
        monkeypatch.setattr(mock_om_client, "search_entities", lambda **kw: mock_search_result)
        monkeypatch.setattr(
            MetadataDiffer,
            "diff_entity_since",
            lambda self, et, fqn, since_days: [diff_v1_v2],
        )
        builder = ChangelogBuilder(mock_om_client)
        result = builder.for_service("my_service", since_days=7)

        assert len(result.top_changers) == 1
        assert result.top_changers[0]["user"] == "alice"
        assert result.top_changers[0]["change_count"] == 1

    def test_empty_when_no_entities_found(self, mock_om_client, monkeypatch):
        monkeypatch.setattr(mock_om_client, "search_entities", lambda **kw: [])
        builder = ChangelogBuilder(mock_om_client)
        result = builder.for_service("empty_service", since_days=7)

        assert result.scope == "service:empty_service"
        assert result.total_entities_changed == 0
        assert result.total_changes == 0
        assert result.entries == []

    def test_major_changes_counted(
        self, mock_om_client, mock_search_result, diff_v2_v3, monkeypatch
    ):
        monkeypatch.setattr(mock_om_client, "search_entities", lambda **kw: mock_search_result)
        monkeypatch.setattr(
            MetadataDiffer,
            "diff_entity_since",
            lambda self, et, fqn, since_days: [diff_v2_v3],
        )
        builder = ChangelogBuilder(mock_om_client)
        result = builder.for_service("my_service", since_days=7)

        assert result.major_changes == 1
        assert result.minor_changes == 1


# ---------------------------------------------------------------------------
# for_user
# ---------------------------------------------------------------------------


class TestChangelogForUser:
    def test_filters_diffs_by_username(
        self, mock_om_client, mock_search_result, diff_v1_v2, diff_v2_v3, monkeypatch
    ):
        # diff_v1_v2.updated_by == "alice", diff_v2_v3.updated_by == "bob"
        monkeypatch.setattr(mock_om_client, "search_entities", lambda **kw: mock_search_result)
        monkeypatch.setattr(
            MetadataDiffer,
            "diff_entity_since",
            lambda self, et, fqn, since_days: [diff_v1_v2, diff_v2_v3],
        )
        builder = ChangelogBuilder(mock_om_client)
        result = builder.for_user("alice", since_days=7)

        assert result.scope == "user:alice"
        assert result.total_entities_changed == 1
        assert all(e.updated_by == "alice" for e in result.entries)

    def test_user_scope_is_correct(self, mock_om_client, monkeypatch):
        monkeypatch.setattr(mock_om_client, "search_entities", lambda **kw: [])
        builder = ChangelogBuilder(mock_om_client)
        result = builder.for_user("bob")
        assert result.scope == "user:bob"


# ---------------------------------------------------------------------------
# for_entity_type
# ---------------------------------------------------------------------------


class TestChangelogForEntityType:
    def test_scope_uses_type_prefix(self, mock_om_client, monkeypatch):
        monkeypatch.setattr(mock_om_client, "search_entities", lambda **kw: [])
        builder = ChangelogBuilder(mock_om_client)
        result = builder.for_entity_type("dashboard")
        assert result.scope == "type:dashboard"

    def test_returns_diffs_for_entity_type(
        self, mock_om_client, mock_search_result, diff_v1_v2, monkeypatch
    ):
        monkeypatch.setattr(mock_om_client, "search_entities", lambda **kw: mock_search_result)
        monkeypatch.setattr(
            MetadataDiffer,
            "diff_entity_since",
            lambda self, et, fqn, since_days: [diff_v1_v2],
        )
        builder = ChangelogBuilder(mock_om_client)
        result = builder.for_entity_type("table", since_days=7)

        assert result.total_entities_changed == 1
        assert len(result.entries) == 1
