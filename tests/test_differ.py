"""Unit tests for MetadataDiffer.

All tests use pure dict fixtures — no HTTP calls are made.
"""

from __future__ import annotations

import copy

import pytest

from ometa_diff.differ import MetadataDiffer
from ometa_diff.models import ChangeSeverity, ChangeType


@pytest.fixture
def differ(mock_om_client) -> MetadataDiffer:
    return MetadataDiffer(mock_om_client)


# ---------------------------------------------------------------------------
# No changes
# ---------------------------------------------------------------------------


class TestNoChanges:
    def test_identical_versions_returns_no_changes(self, differ, table_version_v1):
        result = differ.diff_versions(table_version_v1, table_version_v1, "table")
        assert result.changes == []
        assert result.is_major is False
        assert result.summary == "No changes"

    def test_only_noise_fields_differ_returns_no_changes(self, differ, table_version_v1):
        old = table_version_v1
        new = copy.deepcopy(table_version_v1)
        new["updatedAt"] = old["updatedAt"] + 1000
        new["version"] = 0.2
        new["updatedBy"] = "someone_else"
        new["href"] = "http://other-host/api/v1/tables/123"
        result = differ.diff_versions(old, new, "table")
        assert result.changes == []


# ---------------------------------------------------------------------------
# Description change (MINOR)
# ---------------------------------------------------------------------------


class TestDescriptionChange:
    def test_description_modified_is_minor(self, differ, table_version_v1, table_version_v2):
        result = differ.diff_versions(table_version_v1, table_version_v2, "table")
        desc_changes = [c for c in result.changes if c.field_path == "description"]
        assert len(desc_changes) == 1
        change = desc_changes[0]
        assert change.change_type == ChangeType.MODIFIED
        assert change.severity == ChangeSeverity.MINOR
        assert change.old_value == "Stores payment records"
        assert change.new_value == "Stores payment transaction records"


# ---------------------------------------------------------------------------
# Column changes
# ---------------------------------------------------------------------------


class TestColumnChanges:
    def test_column_added_is_minor(self, differ, table_version_v1, table_version_v2):
        result = differ.diff_versions(table_version_v1, table_version_v2, "table")
        col_changes = [c for c in result.changes if c.field_path == "columns.currency"]
        assert len(col_changes) == 1
        change = col_changes[0]
        assert change.change_type == ChangeType.ADDED
        assert change.severity == ChangeSeverity.MINOR

    def test_column_removed_is_major(self, differ, table_version_v2, table_version_v3):
        result = differ.diff_versions(table_version_v2, table_version_v3, "table")
        col_changes = [c for c in result.changes if c.field_path == "columns.payment_method"]
        assert len(col_changes) == 1
        change = col_changes[0]
        assert change.change_type == ChangeType.REMOVED
        assert change.severity == ChangeSeverity.MAJOR

    def test_column_removed_makes_diff_is_major(self, differ, table_version_v2, table_version_v3):
        result = differ.diff_versions(table_version_v2, table_version_v3, "table")
        assert result.is_major is True

    def test_column_datatype_changed_is_major(self, differ, table_version_v1):
        old = table_version_v1
        new = copy.deepcopy(old)
        new["columns"][0]["dataType"] = "VARCHAR"  # payment_id: BIGINT → VARCHAR
        result = differ.diff_versions(old, new, "table")
        datatype_changes = [
            c for c in result.changes if c.field_path == "columns.payment_id.dataType"
        ]
        assert len(datatype_changes) == 1
        assert datatype_changes[0].severity == ChangeSeverity.MAJOR
        assert result.is_major is True

    def test_column_description_changed_is_minor(self, differ, table_version_v1):
        old = table_version_v1
        new = copy.deepcopy(old)
        new["columns"][0]["description"] = "Updated primary key description"
        result = differ.diff_versions(old, new, "table")
        col_desc_changes = [
            c for c in result.changes if c.field_path == "columns.payment_id.description"
        ]
        assert len(col_desc_changes) == 1
        assert col_desc_changes[0].severity == ChangeSeverity.MINOR


# ---------------------------------------------------------------------------
# Tag changes (MINOR)
# ---------------------------------------------------------------------------


class TestTagChanges:
    def test_tag_added_is_minor(self, differ, table_version_v1, table_version_v2):
        result = differ.diff_versions(table_version_v1, table_version_v2, "table")
        tag_changes = [c for c in result.changes if c.field_path == "tags.PII.Sensitive"]
        assert len(tag_changes) == 1
        assert tag_changes[0].change_type == ChangeType.ADDED
        assert tag_changes[0].severity == ChangeSeverity.MINOR

    def test_tag_removed_is_minor(self, differ, table_version_v2, table_version_v3):
        # v2 has PII.Sensitive, v3 still has it — create a version without it to test removal
        old = table_version_v2
        new = copy.deepcopy(table_version_v2)
        new["tags"] = []
        result = differ.diff_versions(old, new, "table")
        tag_changes = [c for c in result.changes if "tags" in c.field_path]
        assert len(tag_changes) == 1
        assert tag_changes[0].change_type == ChangeType.REMOVED
        assert tag_changes[0].severity == ChangeSeverity.MINOR


# ---------------------------------------------------------------------------
# Owner changes
# ---------------------------------------------------------------------------


class TestOwnerChanges:
    def test_owner_changed_is_minor(self, differ, table_version_v2, table_version_v3):
        result = differ.diff_versions(table_version_v2, table_version_v3, "table")
        owner_changes = [c for c in result.changes if c.field_path == "owner"]
        assert len(owner_changes) == 1
        assert owner_changes[0].change_type == ChangeType.MODIFIED
        assert owner_changes[0].severity == ChangeSeverity.MINOR

    def test_owner_removed_is_major(self, differ, table_version_v1):
        old = table_version_v1
        new = copy.deepcopy(old)
        del new["owner"]
        result = differ.diff_versions(old, new, "table")
        owner_changes = [c for c in result.changes if c.field_path == "owner"]
        assert len(owner_changes) == 1
        assert owner_changes[0].change_type == ChangeType.REMOVED
        assert owner_changes[0].severity == ChangeSeverity.MAJOR
        assert result.is_major is True


# ---------------------------------------------------------------------------
# Noise field filtering
# ---------------------------------------------------------------------------


class TestNoiseFiltering:
    def test_noise_fields_never_appear_in_changes(self, differ, table_version_v1, table_version_v2):
        result = differ.diff_versions(table_version_v1, table_version_v2, "table")
        noise = {"version", "updatedAt", "updatedBy", "changeDescription", "href"}
        for change in result.changes:
            top_field = change.field_path.split(".")[0]
            assert top_field not in noise, f"Noise field leaked: {change.field_path}"


# ---------------------------------------------------------------------------
# Multiple simultaneous changes
# ---------------------------------------------------------------------------


class TestMultipleChanges:
    def test_v1_to_v2_has_three_changes(self, differ, table_version_v1, table_version_v2):
        """v1→v2: description MODIFIED, columns.currency ADDED, tags.PII.Sensitive ADDED."""
        result = differ.diff_versions(table_version_v1, table_version_v2, "table")
        assert len(result.changes) == 3

    def test_v1_to_v2_not_major(self, differ, table_version_v1, table_version_v2):
        result = differ.diff_versions(table_version_v1, table_version_v2, "table")
        assert result.is_major is False

    def test_v2_to_v3_has_two_changes(self, differ, table_version_v2, table_version_v3):
        """v2→v3: columns.payment_method REMOVED (MAJOR), owner MODIFIED (MINOR)."""
        result = differ.diff_versions(table_version_v2, table_version_v3, "table")
        assert len(result.changes) == 2

    def test_summary_reflects_severity_breakdown(self, differ, table_version_v2, table_version_v3):
        result = differ.diff_versions(table_version_v2, table_version_v3, "table")
        assert "2 changes" in result.summary
        assert "major" in result.summary
        assert "minor" in result.summary

    def test_entity_diff_metadata(self, differ, table_version_v1, table_version_v2):
        result = differ.diff_versions(table_version_v1, table_version_v2, "table")
        assert result.entity_type == "table"
        assert result.entity_fqn == "my_service.prod_db.public.payments"
        assert result.from_version == 0.1
        assert result.to_version == 0.2
        assert result.updated_by == "alice"
