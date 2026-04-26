"""CLI integration tests using Typer's test runner."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ometa_diff.cli import app
from ometa_diff.exceptions import NoDiffAvailable, OMConnectionError, OMNotFoundError
from ometa_diff.models import CatalogChangelog, ChangeSeverity, ChangeType, EntityDiff, FieldChange
from tests.conftest import strip_ansi

runner = CliRunner()


@pytest.fixture
def sample_diff() -> EntityDiff:
    return EntityDiff(
        entity_type="table",
        entity_fqn="my_service.prod_db.public.payments",
        entity_id="abc-123",
        from_version="0.1",
        to_version="0.2",
        updated_by="alice",
        updated_at=datetime(2026, 4, 18, 14, 30, tzinfo=timezone.utc),
        changes=[
            FieldChange(
                field_path="description",
                change_type=ChangeType.MODIFIED,
                severity=ChangeSeverity.MINOR,
                old_value="Old desc",
                new_value="New desc",
            )
        ],
        is_major=False,
        summary="1 change: 1 minor",
    )


@pytest.fixture
def sample_changelog(sample_diff) -> CatalogChangelog:
    return CatalogChangelog(
        scope="service:my_service",
        from_date=datetime(2026, 4, 11, tzinfo=timezone.utc),
        to_date=datetime(2026, 4, 18, tzinfo=timezone.utc),
        total_entities_changed=1,
        total_changes=1,
        major_changes=0,
        minor_changes=1,
        entries=[sample_diff],
        top_changers=[{"user": "alice", "change_count": 1}],
    )


class TestHelpCommands:
    def test_app_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "ometa-diff" in result.output

    def test_diff_help(self):
        result = runner.invoke(app, ["diff", "--help"])
        assert result.exit_code == 0
        assert "entity_type" in result.output or "ENTITY_TYPE" in result.output

    def test_changelog_help(self):
        result = runner.invoke(app, ["changelog", "--help"])
        assert result.exit_code == 0
        assert "--service" in strip_ansi(result.output)

    def test_config_command(self):
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert "OPENMETADATA_HOST" in result.output


class TestDiffCommand:
    def test_diff_outputs_result(self, sample_diff):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch("ometa_diff.differ.MetadataDiffer.diff_entity", return_value=sample_diff),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(app, ["diff", "table", "my_service.prod_db.public.payments"])
        assert result.exit_code == 0
        assert "payments" in result.output

    def test_diff_since_outputs_multiple(self, sample_diff):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch(
                "ometa_diff.differ.MetadataDiffer.diff_entity_since",
                return_value=[sample_diff, sample_diff],
            ),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(
                app, ["diff", "table", "my_service.prod_db.public.payments", "--since", "7d"]
            )
        assert result.exit_code == 0

    def test_diff_since_no_changes(self):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch("ometa_diff.differ.MetadataDiffer.diff_entity_since", return_value=[]),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(
                app, ["diff", "table", "my_service.prod_db.public.payments", "--since", "7d"]
            )
        assert result.exit_code == 0
        assert "No changes found" in result.output

    def test_diff_no_diff_available(self):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch(
                "ometa_diff.differ.MetadataDiffer.diff_entity",
                side_effect=NoDiffAvailable("Only one version"),
            ),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(app, ["diff", "table", "my_service.prod_db.public.payments"])
        assert result.exit_code == 1

    def test_diff_not_found_error(self):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch(
                "ometa_diff.differ.MetadataDiffer.diff_entity",
                side_effect=OMNotFoundError("Not found"),
            ),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(app, ["diff", "table", "my_service.prod_db.public.payments"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_diff_connection_error(self):
        with patch("ometa_diff.cli._build_client", side_effect=OMConnectionError("refused")):
            result = runner.invoke(app, ["diff", "table", "my_service.prod_db.public.payments"])
        assert result.exit_code == 1

    def test_diff_invalid_since(self):
        with patch("ometa_diff.cli._build_client") as mock_client:
            mock_client.return_value = MagicMock()
            result = runner.invoke(
                app, ["diff", "table", "my_service.prod_db.public.payments", "--since", "invalid"]
            )
        assert result.exit_code == 1
        assert "Invalid" in result.output

    def test_diff_format_json(self, sample_diff):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch("ometa_diff.differ.MetadataDiffer.diff_entity", return_value=sample_diff),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(
                app,
                ["diff", "table", "my_service.prod_db.public.payments", "--format", "json"],
            )
        assert result.exit_code == 0
        assert "{" in result.output  # JSON output

    def test_diff_format_markdown(self, sample_diff):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch("ometa_diff.differ.MetadataDiffer.diff_entity", return_value=sample_diff),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(
                app,
                ["diff", "table", "my_service.prod_db.public.payments", "--format", "markdown"],
            )
        assert result.exit_code == 0
        assert "#" in result.output  # markdown heading


class TestChangelogCommand:
    def test_changelog_requires_scope(self):
        result = runner.invoke(app, ["changelog"])
        assert result.exit_code == 1
        assert "scope" in result.output.lower() or "service" in result.output.lower()

    def test_changelog_by_service(self, sample_changelog):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch(
                "ometa_diff.changelog.ChangelogBuilder.for_service",
                return_value=sample_changelog,
            ),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(app, ["changelog", "--service", "my_service"])
        assert result.exit_code == 0
        assert "my_service" in result.output

    def test_changelog_by_user(self, sample_changelog):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch("ometa_diff.changelog.ChangelogBuilder.for_user", return_value=sample_changelog),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(app, ["changelog", "--user", "alice"])
        assert result.exit_code == 0

    def test_changelog_by_type(self, sample_changelog):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch(
                "ometa_diff.changelog.ChangelogBuilder.for_entity_type",
                return_value=sample_changelog,
            ),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(app, ["changelog", "--type", "table"])
        assert result.exit_code == 0

    def test_changelog_invalid_since(self):
        result = runner.invoke(app, ["changelog", "--service", "my_service", "--since", "1week"])
        assert result.exit_code == 1

    def test_changelog_format_json(self, sample_changelog):
        with (
            patch("ometa_diff.cli._build_client") as mock_client,
            patch(
                "ometa_diff.changelog.ChangelogBuilder.for_service",
                return_value=sample_changelog,
            ),
        ):
            mock_client.return_value = MagicMock()
            result = runner.invoke(
                app, ["changelog", "--service", "my_service", "--format", "json"]
            )
        assert result.exit_code == 0
        assert "{" in result.output
