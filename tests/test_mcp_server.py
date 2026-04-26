"""MCP server tool registration and tool-call tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("mcp", reason="mcp extra not installed; skipping MCP server tests")

from ometa_diff.models import CatalogChangelog, ChangeSeverity, ChangeType, EntityDiff, FieldChange


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
                old_value="Old",
                new_value="New",
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


class TestCreateServer:
    def test_returns_fastmcp_instance(self):
        from mcp.server.fastmcp import FastMCP

        from ometa_diff.mcp_server import create_server

        server = create_server()
        assert isinstance(server, FastMCP)

    def test_server_has_three_tools(self):
        from ometa_diff.mcp_server import create_server

        server = create_server()
        tool_names = [t.name for t in server._tool_manager.list_tools()]
        assert "metadata_diff" in tool_names
        assert "metadata_changelog" in tool_names
        assert "metadata_change_summary" in tool_names

    def test_tool_descriptions_present(self):
        from ometa_diff.mcp_server import create_server

        server = create_server()
        tools = {t.name: t for t in server._tool_manager.list_tools()}
        assert tools["metadata_diff"].description
        assert tools["metadata_changelog"].description
        assert tools["metadata_change_summary"].description


class TestMetadataDiffTool:
    def test_returns_markdown_output(self, sample_diff):
        from ometa_diff.mcp_server import create_server

        server = create_server()
        with (
            patch("ometa_diff.client.client_from_env") as mock_client,
            patch("ometa_diff.differ.MetadataDiffer.diff_entity", return_value=sample_diff),
        ):
            mock_client.return_value = MagicMock()
            tools = {t.name: t for t in server._tool_manager.list_tools()}
            tool_fn = tools["metadata_diff"].fn
            result = tool_fn(
                entity_type="table",
                entity_fqn="my_service.prod_db.public.payments",
            )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_handles_no_diff_available(self):
        from ometa_diff.exceptions import NoDiffAvailable
        from ometa_diff.mcp_server import create_server

        server = create_server()
        with (
            patch("ometa_diff.client.client_from_env") as mock_client,
            patch(
                "ometa_diff.differ.MetadataDiffer.diff_entity",
                side_effect=NoDiffAvailable("Only one version"),
            ),
        ):
            mock_client.return_value = MagicMock()
            tools = {t.name: t for t in server._tool_manager.list_tools()}
            result = tools["metadata_diff"].fn(entity_type="table", entity_fqn="svc.db.schema.tbl")
        assert "No diff available" in result

    def test_handles_om_errors(self):
        from ometa_diff.exceptions import OMConnectionError
        from ometa_diff.mcp_server import create_server

        server = create_server()
        with patch(
            "ometa_diff.client.client_from_env",
            side_effect=OMConnectionError("refused"),
        ):
            tools = {t.name: t for t in server._tool_manager.list_tools()}
            result = tools["metadata_diff"].fn(entity_type="table", entity_fqn="svc.db.schema.tbl")
        assert "Error" in result


class TestMetadataChangelogTool:
    def test_service_scope(self, sample_changelog):
        from ometa_diff.mcp_server import create_server

        server = create_server()
        with (
            patch("ometa_diff.client.client_from_env") as mock_client,
            patch(
                "ometa_diff.changelog.ChangelogBuilder.for_service",
                return_value=sample_changelog,
            ),
        ):
            mock_client.return_value = MagicMock()
            tools = {t.name: t for t in server._tool_manager.list_tools()}
            result = tools["metadata_changelog"].fn(scope="service:my_service", since_days=7)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_user_scope(self, sample_changelog):
        from ometa_diff.mcp_server import create_server

        server = create_server()
        with (
            patch("ometa_diff.client.client_from_env") as mock_client,
            patch("ometa_diff.changelog.ChangelogBuilder.for_user", return_value=sample_changelog),
        ):
            mock_client.return_value = MagicMock()
            tools = {t.name: t for t in server._tool_manager.list_tools()}
            result = tools["metadata_changelog"].fn(scope="user:alice", since_days=7)
        assert isinstance(result, str)

    def test_type_scope(self, sample_changelog):
        from ometa_diff.mcp_server import create_server

        server = create_server()
        with (
            patch("ometa_diff.client.client_from_env") as mock_client,
            patch(
                "ometa_diff.changelog.ChangelogBuilder.for_catalog",
                return_value=sample_changelog,
            ),
        ):
            mock_client.return_value = MagicMock()
            tools = {t.name: t for t in server._tool_manager.list_tools()}
            result = tools["metadata_changelog"].fn(scope="type:table", since_days=7)
        assert isinstance(result, str)

    def test_invalid_scope_returns_error_string(self):
        from ometa_diff.mcp_server import create_server

        server = create_server()
        with patch("ometa_diff.client.client_from_env") as mock_client:
            mock_client.return_value = MagicMock()
            tools = {t.name: t for t in server._tool_manager.list_tools()}
            result = tools["metadata_changelog"].fn(scope="badscope", since_days=7)
        assert "Invalid scope" in result


class TestMetadataChangeSummaryTool:
    def test_returns_markdown_table(self, sample_changelog):
        from ometa_diff.mcp_server import create_server

        server = create_server()
        with (
            patch("ometa_diff.client.client_from_env") as mock_client,
            patch(
                "ometa_diff.changelog.ChangelogBuilder.for_catalog",
                return_value=sample_changelog,
            ),
        ):
            mock_client.return_value = MagicMock()
            tools = {t.name: t for t in server._tool_manager.list_tools()}
            result = tools["metadata_change_summary"].fn(since_days=7)
        assert "## Metadata Activity Summary" in result
        assert "| Metric" in result

    def test_includes_top_changers(self, sample_changelog):
        from ometa_diff.mcp_server import create_server

        server = create_server()
        with (
            patch("ometa_diff.client.client_from_env") as mock_client,
            patch(
                "ometa_diff.changelog.ChangelogBuilder.for_catalog",
                return_value=sample_changelog,
            ),
        ):
            mock_client.return_value = MagicMock()
            tools = {t.name: t for t in server._tool_manager.list_tools()}
            result = tools["metadata_change_summary"].fn(since_days=7)
        assert "alice" in result
