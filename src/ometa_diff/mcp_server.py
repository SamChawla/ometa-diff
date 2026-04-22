"""MCP server exposing metadata diff tools for OpenMetadata."""

from __future__ import annotations

import importlib.util
from typing import Any

_mcp_available = importlib.util.find_spec("mcp") is not None


def create_server() -> Any:
    """Build and return the MCP server with all three tools registered.

    Returns:
        Configured FastMCP server instance.

    Raises:
        ImportError: If the 'mcp' extra is not installed.
    """
    if not _mcp_available:
        raise ImportError("MCP SDK not installed. Run: pip install 'ometa-diff[mcp]'")

    from mcp.server.fastmcp import FastMCP

    import ometa_diff.client as _om_client
    from ometa_diff.changelog import ChangelogBuilder
    from ometa_diff.differ import MetadataDiffer
    from ometa_diff.exceptions import NoDiffAvailable, OmetaDiffError
    from ometa_diff.formatter import OutputFormat, format_changelog, format_diff

    mcp = FastMCP(
        name="ometa-diff",
        instructions=(
            "Metadata version-diff intelligence for OpenMetadata. "
            "Use these tools when users ask about what changed in their data catalog, "
            "metadata version history, or recent catalog activity."
        ),
    )

    # ------------------------------------------------------------------
    # Tool 1: metadata_diff
    # ------------------------------------------------------------------

    @mcp.tool(  # type: ignore[misc]
        name="metadata_diff",
        description=(
            "Compare two versions of a metadata entity in OpenMetadata and return a "
            "field-by-field diff showing what was added, removed, or modified. "
            "Use this when the user asks: 'What changed in the payments table?', "
            "'Show me the diff for my dashboard', or 'What's different in version 0.3 vs 0.4?'. "
            "Requires OPENMETADATA_HOST and OPENMETADATA_JWT_TOKEN environment variables."
        ),
    )
    def metadata_diff(
        entity_type: str,
        entity_fqn: str,
        from_version: str | None = None,
        to_version: str | None = None,
    ) -> str:
        """Compare two versions of a metadata entity.

        Args:
            entity_type: OM entity type — 'table', 'dashboard', 'pipeline', 'topic', etc.
            entity_fqn: Fully qualified name, e.g. 'my_service.db.schema.payments'.
            from_version: Earlier version string (defaults to previous version).
            to_version: Later version string (defaults to latest version).

        Returns:
            Formatted diff report as markdown text.
        """
        try:
            client = _om_client.client_from_env()
            differ = MetadataDiffer(client)
            result = differ.diff_entity(
                entity_type, entity_fqn, from_version=from_version, to_version=to_version
            )
            return format_diff(result, OutputFormat.MARKDOWN)
        except NoDiffAvailable as exc:
            return f"No diff available: {exc}"
        except OmetaDiffError as exc:
            return f"Error: {exc}"
        except Exception as exc:  # noqa: BLE001
            return f"Unexpected error: {exc}"

    # ------------------------------------------------------------------
    # Tool 2: metadata_changelog
    # ------------------------------------------------------------------

    @mcp.tool(  # type: ignore[misc]
        name="metadata_changelog",
        description=(
            "Show recent metadata changes across your OpenMetadata data catalog. "
            "Use this when the user asks: 'Show me all metadata changes in my service this week', "
            "'What did admin change recently?', or 'What tables changed in the last 30 days?'. "
            "Scope by service name, entity type, or username. "
            "Requires OPENMETADATA_HOST and OPENMETADATA_JWT_TOKEN environment variables."
        ),
    )
    def metadata_changelog(
        scope: str,
        since_days: int = 7,
    ) -> str:
        """Aggregate metadata changes across multiple entities over a time window.

        Args:
            scope: Filter scope — 'service:my_service', 'type:table', or 'user:admin'.
            since_days: How many days back to scan (default 7).

        Returns:
            Aggregated changelog as markdown text.
        """
        try:
            client = _om_client.client_from_env()
            builder = ChangelogBuilder(client)

            if scope.startswith("service:"):
                service_name = scope[len("service:") :]
                log = builder.for_service(service_name, since_days=since_days)
            elif scope.startswith("type:"):
                entity_type = scope[len("type:") :]
                log = builder.for_entity_type(entity_type, since_days=since_days)
            elif scope.startswith("user:"):
                username = scope[len("user:") :]
                log = builder.for_user(username, since_days=since_days)
            else:
                return "Invalid scope format. Use 'service:name', 'type:table', or 'user:admin'."

            return format_changelog(log, OutputFormat.MARKDOWN)
        except OmetaDiffError as exc:
            return f"Error: {exc}"
        except Exception as exc:  # noqa: BLE001
            return f"Unexpected error: {exc}"

    # ------------------------------------------------------------------
    # Tool 3: metadata_change_summary
    # ------------------------------------------------------------------

    @mcp.tool(  # type: ignore[misc]
        name="metadata_change_summary",
        description=(
            "Get high-level statistics about metadata activity in your OpenMetadata catalog. "
            "Use this when the user asks: 'Give me a summary of catalog activity this month', "
            "'Who is changing the most metadata?', "
            "or 'How many major changes happened this week?'. "
            "Returns total change counts, major/minor breakdown, and top changers. "
            "Requires OPENMETADATA_HOST and OPENMETADATA_JWT_TOKEN environment variables."
        ),
    )
    def metadata_change_summary(
        since_days: int = 7,
    ) -> str:
        """Return a high-level summary of catalog-wide metadata activity.

        Args:
            since_days: How many days back to scan (default 7).

        Returns:
            Summary statistics as markdown text.
        """
        try:
            client = _om_client.client_from_env()
            builder = ChangelogBuilder(client)
            log = builder.for_entity_type("table", since_days=since_days)

            lines = [
                f"## Metadata Activity Summary — Last {since_days} Days",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Entities changed | {log.total_entities_changed} |",
                f"| Total field changes | {log.total_changes} |",
                f"| Major changes | {log.major_changes} |",
                f"| Minor changes | {log.minor_changes} |",
                f"| Patch changes | {log.total_changes - log.major_changes - log.minor_changes} |",
                "",
            ]

            if log.top_changers:
                lines += [
                    "### Top Changers",
                    "",
                    "| User | Changes |",
                    "|------|---------|",
                ]
                for entry in log.top_changers[:5]:
                    lines.append(f"| {entry['user']} | {entry['change_count']} |")

            return "\n".join(lines)
        except OmetaDiffError as exc:
            return f"Error: {exc}"
        except Exception as exc:  # noqa: BLE001
            return f"Unexpected error: {exc}"

    return mcp


def run() -> None:
    """Entry point: start the MCP server over STDIO transport."""
    server = create_server()
    server.run("stdio")
