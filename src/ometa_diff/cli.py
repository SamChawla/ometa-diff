"""Typer CLI for ometa-diff."""

from __future__ import annotations

import re
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


def _parse_since_days(since: str) -> int:
    """Convert a '7d' / '30d' string to an integer number of days."""
    match = re.fullmatch(r"(\d+)d", since.strip())
    if not match:
        _err.print(f"[red]Invalid --since value '{since}'. Use format like '7d' or '30d'.[/red]")
        raise typer.Exit(1)
    return int(match.group(1))


def _build_client():  # type: ignore[return]
    """Create an OMVersionClient from env vars, exiting on missing token."""
    from ometa_diff.client import client_from_env
    from ometa_diff.exceptions import OMAuthError, OMConnectionError

    try:
        return client_from_env()
    except (OMConnectionError, OMAuthError) as exc:
        _err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


def _fmt_to_output_format(fmt: FormatOption):  # type: ignore[return]
    """Map CLI FormatOption to formatter's OutputFormat enum."""
    from ometa_diff.formatter import OutputFormat

    return OutputFormat(fmt.value)


def _print_output(text: str, fmt: FormatOption) -> None:
    """Print output, routing markdown/JSON through plain print to avoid Rich encoding issues."""
    if fmt == FormatOption.terminal:
        _console.print(text)
    else:
        print(text)


@app.command()
def diff(
    entity_type: str = typer.Argument(..., help="Entity type: table, dashboard, pipeline, …"),
    fqn: str = typer.Argument(..., help="Fully qualified name, e.g. service.db.schema.table"),
    from_version: str | None = typer.Option(
        None, "--from", help="Earlier version (default: previous)"
    ),
    to_version: str | None = typer.Option(None, "--to", help="Later version (default: latest)"),
    since: str | None = typer.Option(None, "--since", help="Time window, e.g. 7d"),
    fmt: FormatOption = typer.Option(FormatOption.terminal, "--format", "-f", help="Output format"),
) -> None:
    """Show what changed between two versions of a metadata entity."""
    from ometa_diff.differ import MetadataDiffer
    from ometa_diff.exceptions import (
        NoDiffAvailable,
        OMAPIError,
        OMAuthError,
        OMConnectionError,
        OMNotFoundError,
    )
    from ometa_diff.formatter import format_diff

    client = _build_client()
    differ = MetadataDiffer(client)
    output_fmt = _fmt_to_output_format(fmt)

    try:
        if since is not None:
            since_days = _parse_since_days(since)
            diffs = differ.diff_entity_since(entity_type, fqn, since_days=since_days)
            if not diffs:
                _console.print(f"No changes found for [bold]{fqn}[/bold] in the last {since}.")
                return
            for d in diffs:
                _print_output(format_diff(d, output_fmt), fmt)
        else:
            result = differ.diff_entity(
                entity_type, fqn, from_version=from_version, to_version=to_version
            )
            _print_output(format_diff(result, output_fmt), fmt)
    except NoDiffAvailable as exc:
        _err.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)
    except OMNotFoundError as exc:
        _err.print(f"[red]Entity not found: {exc}[/red]")
        raise typer.Exit(1)
    except OMAuthError as exc:
        _err.print(f"[red]Authentication failed: {exc}[/red]")
        raise typer.Exit(1)
    except OMConnectionError as exc:
        _err.print(f"[red]Cannot connect to OpenMetadata: {exc}[/red]")
        raise typer.Exit(1)
    except OMAPIError as exc:
        _err.print(f"[red]OpenMetadata API error: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def changelog(
    service: str | None = typer.Option(None, "--service", help="Filter by service name"),
    user: str | None = typer.Option(None, "--user", help="Filter by username"),
    entity_type: str | None = typer.Option(None, "--type", help="Filter by entity type"),
    since: str = typer.Option("7d", "--since", help="Time window, e.g. 7d, 30d"),
    fmt: FormatOption = typer.Option(FormatOption.terminal, "--format", "-f", help="Output format"),
) -> None:
    """Show recent metadata changes across your data catalog."""
    from ometa_diff.changelog import ChangelogBuilder
    from ometa_diff.exceptions import OMAPIError, OMAuthError, OMConnectionError
    from ometa_diff.formatter import format_changelog

    if not any([service, user, entity_type]):
        _err.print("[red]Provide at least one scope: --service, --user, or --type.[/red]")
        raise typer.Exit(1)

    since_days = _parse_since_days(since)
    client = _build_client()
    builder = ChangelogBuilder(client)
    output_fmt = _fmt_to_output_format(fmt)

    try:
        if service:
            log = builder.for_service(service, since_days=since_days)
        elif user:
            log = builder.for_user(user, since_days=since_days)
        else:
            assert entity_type is not None
            log = builder.for_entity_type(entity_type, since_days=since_days)
    except OMAuthError as exc:
        _err.print(f"[red]Authentication failed: {exc}[/red]")
        raise typer.Exit(1)
    except OMConnectionError as exc:
        _err.print(f"[red]Cannot connect to OpenMetadata: {exc}[/red]")
        raise typer.Exit(1)
    except OMAPIError as exc:
        _err.print(f"[red]OpenMetadata API error: {exc}[/red]")
        raise typer.Exit(1)

    _print_output(format_changelog(log, output_fmt), fmt)


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
