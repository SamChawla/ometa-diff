"""Typer CLI for ometa-diff."""

from __future__ import annotations

from enum import Enum

import typer
from rich.console import Console

app = typer.Typer(
    name="ometa-diff",
    help="Metadata version-diff intelligence for OpenMetadata.",
    no_args_is_help=True,
)

_console = Console()
_err = Console(stderr=True)


class FormatOption(str, Enum):
    """CLI output format choices."""

    terminal = "terminal"
    markdown = "markdown"
    json = "json"


@app.command()
def diff(
    entity_type: str = typer.Argument(..., help="Entity type: table, dashboard, pipeline, …"),
    fqn: str = typer.Argument(..., help="Fully qualified name, e.g. service.db.schema.table"),
    from_version: str | None = typer.Option(
        None, "--from", help="Earlier version (default: previous)"
    ),  # noqa: E501
    to_version: str | None = typer.Option(None, "--to", help="Later version (default: latest)"),
    since: str | None = typer.Option(None, "--since", help="Time window, e.g. 7d"),
    fmt: FormatOption = typer.Option(FormatOption.terminal, "--format", "-f", help="Output format"),
) -> None:
    """Show what changed between two versions of a metadata entity."""
    raise NotImplementedError


@app.command()
def changelog(
    service: str | None = typer.Option(None, "--service", help="Filter by service name"),
    user: str | None = typer.Option(None, "--user", help="Filter by username"),
    entity_type: str | None = typer.Option(None, "--type", help="Filter by entity type"),
    since: str = typer.Option("7d", "--since", help="Time window, e.g. 7d, 30d"),
    fmt: FormatOption = typer.Option(FormatOption.terminal, "--format", "-f", help="Output format"),
) -> None:
    """Show recent metadata changes across your data catalog."""
    raise NotImplementedError


@app.command()
def serve() -> None:
    """Start the MCP server over STDIO transport."""
    from ometa_diff.mcp_server import run

    run()


@app.command()
def config() -> None:
    """Show current configuration (host, auth status)."""
    import os

    host = os.environ.get("OPENMETADATA_HOST", "(not set — defaults to http://localhost:8585/api)")
    token = os.environ.get("OPENMETADATA_JWT_TOKEN", "")
    token_display = f"{token[:8]}…" if len(token) > 8 else ("(not set)" if not token else token)
    _console.print(f"[bold]OPENMETADATA_HOST[/bold]      {host}")
    _console.print(f"[bold]OPENMETADATA_JWT_TOKEN[/bold] {token_display}")
