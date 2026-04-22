"""Unit tests for output formatters."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from ometa_diff.differ import MetadataDiffer
from ometa_diff.formatter import OutputFormat, format_changelog, format_diff
from ometa_diff.models import CatalogChangelog


@pytest.fixture
def diff_v1_v2(mock_om_client, table_version_v1, table_version_v2):
    return MetadataDiffer(mock_om_client).diff_versions(table_version_v1, table_version_v2, "table")


@pytest.fixture
def diff_v2_v3(mock_om_client, table_version_v2, table_version_v3):
    return MetadataDiffer(mock_om_client).diff_versions(table_version_v2, table_version_v3, "table")


@pytest.fixture
def empty_changelog():
    now = datetime(2026, 4, 22, tzinfo=timezone.utc)
    return CatalogChangelog(
        scope="service:my_service",
        from_date=datetime(2026, 4, 15, tzinfo=timezone.utc),
        to_date=now,
        total_entities_changed=0,
        total_changes=0,
        major_changes=0,
        minor_changes=0,
    )


@pytest.fixture
def populated_changelog(diff_v1_v2, diff_v2_v3):
    now = datetime(2026, 4, 22, tzinfo=timezone.utc)
    return CatalogChangelog(
        scope="service:my_service",
        from_date=datetime(2026, 4, 15, tzinfo=timezone.utc),
        to_date=now,
        total_entities_changed=2,
        total_changes=5,
        major_changes=1,
        minor_changes=4,
        entries=[diff_v1_v2, diff_v2_v3],
        top_changers=[{"user": "alice", "change_count": 3}, {"user": "bob", "change_count": 2}],
    )


# ---------------------------------------------------------------------------
# format_diff
# ---------------------------------------------------------------------------


class TestFormatDiff:
    def test_terminal_contains_fqn(self, diff_v1_v2):
        output = format_diff(diff_v1_v2, OutputFormat.TERMINAL)
        assert "my_service.prod_db.public.payments" in output

    def test_terminal_contains_version_range(self, diff_v1_v2):
        output = format_diff(diff_v1_v2, OutputFormat.TERMINAL)
        assert "0.1" in output
        assert "0.2" in output

    def test_terminal_contains_updater(self, diff_v1_v2):
        output = format_diff(diff_v1_v2, OutputFormat.TERMINAL)
        assert "alice" in output

    def test_terminal_contains_severity_labels(self, diff_v1_v2):
        output = format_diff(diff_v1_v2, OutputFormat.TERMINAL)
        assert "MINOR" in output

    def test_terminal_major_shows_for_major_diff(self, diff_v2_v3):
        output = format_diff(diff_v2_v3, OutputFormat.TERMINAL)
        assert "MAJOR" in output

    def test_markdown_has_heading(self, diff_v1_v2):
        output = format_diff(diff_v1_v2, OutputFormat.MARKDOWN)
        assert output.startswith("##")

    def test_markdown_contains_table(self, diff_v1_v2):
        output = format_diff(diff_v1_v2, OutputFormat.MARKDOWN)
        assert "| Severity |" in output

    def test_markdown_shows_field_paths(self, diff_v1_v2):
        output = format_diff(diff_v1_v2, OutputFormat.MARKDOWN)
        assert "description" in output
        assert "columns.currency" in output

    def test_json_is_valid(self, diff_v1_v2):
        output = format_diff(diff_v1_v2, OutputFormat.JSON)
        parsed = json.loads(output)
        assert parsed["entity_fqn"] == "my_service.prod_db.public.payments"
        assert parsed["from_version"] == 0.1
        assert parsed["to_version"] == 0.2

    def test_json_changes_list(self, diff_v1_v2):
        output = format_diff(diff_v1_v2, OutputFormat.JSON)
        parsed = json.loads(output)
        assert len(parsed["changes"]) == 3

    def test_no_changes_shows_placeholder(self, mock_om_client, table_version_v1):
        diff = MetadataDiffer(mock_om_client).diff_versions(
            table_version_v1, table_version_v1, "table"
        )
        output = format_diff(diff, OutputFormat.TERMINAL)
        assert "no changes" in output.lower()


# ---------------------------------------------------------------------------
# format_changelog
# ---------------------------------------------------------------------------


class TestFormatChangelog:
    def test_terminal_contains_scope(self, populated_changelog):
        output = format_changelog(populated_changelog, OutputFormat.TERMINAL)
        assert "service:my_service" in output

    def test_terminal_contains_entity_count(self, populated_changelog):
        output = format_changelog(populated_changelog, OutputFormat.TERMINAL)
        assert "2" in output

    def test_terminal_shows_top_changers(self, populated_changelog):
        output = format_changelog(populated_changelog, OutputFormat.TERMINAL)
        assert "alice" in output
        assert "bob" in output

    def test_terminal_empty_changelog(self, empty_changelog):
        output = format_changelog(empty_changelog, OutputFormat.TERMINAL)
        assert "service:my_service" in output
        assert "No changes" in output

    def test_markdown_starts_with_h1(self, populated_changelog):
        output = format_changelog(populated_changelog, OutputFormat.MARKDOWN)
        assert output.startswith("# Catalog Changelog")

    def test_markdown_has_summary_table(self, populated_changelog):
        output = format_changelog(populated_changelog, OutputFormat.MARKDOWN)
        assert "| Metric |" in output

    def test_markdown_has_top_changers_table(self, populated_changelog):
        output = format_changelog(populated_changelog, OutputFormat.MARKDOWN)
        assert "| User |" in output
        assert "alice" in output

    def test_json_is_valid(self, populated_changelog):
        output = format_changelog(populated_changelog, OutputFormat.JSON)
        parsed = json.loads(output)
        assert parsed["scope"] == "service:my_service"
        assert parsed["total_changes"] == 5
        assert len(parsed["entries"]) == 2

    def test_json_includes_top_changers(self, populated_changelog):
        output = format_changelog(populated_changelog, OutputFormat.JSON)
        parsed = json.loads(output)
        assert parsed["top_changers"][0]["user"] == "alice"
