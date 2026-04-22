"""Output rendering: terminal (Rich), markdown, JSON."""

from __future__ import annotations

from enum import Enum

from rich.console import Console

from ometa_diff.models import CatalogChangelog, ChangeSeverity, ChangeType, EntityDiff

_console = Console()


class OutputFormat(str, Enum):
    """Supported output formats."""

    TERMINAL = "terminal"
    MARKDOWN = "markdown"
    JSON = "json"


_SEVERITY_LABEL = {
    ChangeSeverity.MAJOR: "[bold red]* MAJOR[/bold red]",
    ChangeSeverity.MINOR: "[bold yellow]* MINOR[/bold yellow]",
    ChangeSeverity.PATCH: "[bold green]* PATCH[/bold green]",
}

_SEVERITY_MD = {
    ChangeSeverity.MAJOR: "[MAJOR]",
    ChangeSeverity.MINOR: "[MINOR]",
    ChangeSeverity.PATCH: "[PATCH]",
}


def _truncate(value: object, limit: int = 80) -> str:
    """Truncate a value to a safe display length."""
    s = str(value)
    return s[:limit] + "..." if len(s) > limit else s


# ---------------------------------------------------------------------------
# Diff formatting
# ---------------------------------------------------------------------------


def _format_diff_terminal(diff: EntityDiff) -> str:
    """Render an EntityDiff as Rich markup text."""
    lines: list[str] = []

    # Header
    lines.append(f"[bold cyan]{diff.entity_fqn}[/bold cyan] [dim]({diff.entity_type})[/dim]")
    lines.append(
        f"[bold]v{diff.from_version}[/bold] -> [bold]v{diff.to_version}[/bold]"
        f"  [dim]|[/dim]  Changed by: [cyan]{diff.updated_by}[/cyan]"
        f"  [dim]|  {diff.updated_at.strftime('%Y-%m-%d %H:%M')} UTC[/dim]"
    )
    lines.append(f"[italic]{diff.summary}[/italic]")

    if diff.changes:
        lines.append("")
        for change in diff.changes:
            label = _SEVERITY_LABEL[change.severity]
            ct = change.change_type.value.upper()
            lines.append(f"  {label}  [bold]{change.field_path}[/bold] - {ct}")
            if change.change_type == ChangeType.MODIFIED:
                if change.old_value is not None:
                    lines.append(f"             [red]- {_truncate(change.old_value)}[/red]")
                if change.new_value is not None:
                    lines.append(f"             [green]+ {_truncate(change.new_value)}[/green]")
    else:
        lines.append("[dim]  (no changes)[/dim]")

    return "\n".join(lines)


def _format_diff_markdown(diff: EntityDiff) -> str:
    """Render an EntityDiff as GitHub-flavored Markdown."""
    lines: list[str] = []

    lines.append(f"## `{diff.entity_fqn}` ({diff.entity_type})")
    lines.append("")
    lines.append(
        f"**v{diff.from_version} -> v{diff.to_version}**"
        f" | Changed by: `{diff.updated_by}`"
        f" | {diff.updated_at.strftime('%Y-%m-%d %H:%M')} UTC"
    )
    lines.append("")
    lines.append(f"_{diff.summary}_")

    if diff.changes:
        lines.append("")
        lines.append("| Severity | Field | Change | Old | New |")
        lines.append("|----------|-------|--------|-----|-----|")
        for change in diff.changes:
            sev = _SEVERITY_MD[change.severity]
            ct = change.change_type.value.upper()
            old = _truncate(change.old_value) if change.old_value is not None else ""
            new = _truncate(change.new_value) if change.new_value is not None else ""
            lines.append(f"| {sev} | `{change.field_path}` | {ct} | {old} | {new} |")

    return "\n".join(lines)


def _format_diff_json(diff: EntityDiff) -> str:
    """Render an EntityDiff as compact JSON."""
    return diff.model_dump_json(indent=2)


def format_diff(diff: EntityDiff, fmt: OutputFormat = OutputFormat.TERMINAL) -> str:
    """Render an EntityDiff in the requested format.

    Args:
        diff: The diff to render.
        fmt: Output format (terminal, markdown, json).

    Returns:
        Formatted string ready to print or write.
    """
    if fmt == OutputFormat.TERMINAL:
        return _format_diff_terminal(diff)
    if fmt == OutputFormat.MARKDOWN:
        return _format_diff_markdown(diff)
    return _format_diff_json(diff)


# ---------------------------------------------------------------------------
# Changelog formatting
# ---------------------------------------------------------------------------


def _format_changelog_terminal(log: CatalogChangelog) -> str:
    """Render a CatalogChangelog as Rich markup text."""
    lines: list[str] = []

    from_str = log.from_date.strftime("%Y-%m-%d")
    to_str = log.to_date.strftime("%Y-%m-%d")
    lines.append(f"[bold cyan]Catalog Changelog:[/bold cyan] [bold]{log.scope}[/bold]")
    lines.append(f"[dim]{from_str} -> {to_str}[/dim]")
    lines.append("")

    major = log.major_changes
    minor = log.minor_changes
    patch = log.total_changes - major - minor
    lines.append(
        f"[bold]{log.total_entities_changed}[/bold] entities changed"
        f"  [dim]|[/dim]  [bold]{log.total_changes}[/bold] changes"
        f"  [dim]|[/dim]  [bold red]{major}[/bold red] major"
        f"  [bold yellow]{minor}[/bold yellow] minor"
        f"  [bold green]{patch}[/bold green] patch"
    )

    if log.top_changers:
        changer_str = ", ".join(
            f"[cyan]{c['user']}[/cyan] ({c['change_count']})" for c in log.top_changers[:5]
        )
        lines.append(f"Top changers: {changer_str}")

    if log.entries:
        lines.append("")
        lines.append("[dim]--- Entities -------------------------------------------[/dim]")
        for entry in log.entries:
            sev_flag = "[red]*[/red]" if entry.is_major else "[yellow]*[/yellow]"
            n = len(entry.changes)
            v_range = f"v{entry.from_version}->v{entry.to_version}"
            noun = "change" if n == 1 else "changes"
            lines.append(
                f"  {sev_flag} [bold]{entry.entity_fqn}[/bold]  [dim]{n} {noun} ({v_range})[/dim]"
            )
    else:
        lines.append("[dim]  No changes in this period.[/dim]")

    return "\n".join(lines)


def _format_changelog_markdown(log: CatalogChangelog) -> str:
    """Render a CatalogChangelog as GitHub-flavored Markdown."""
    lines: list[str] = []
    from_str = log.from_date.strftime("%Y-%m-%d")
    to_str = log.to_date.strftime("%Y-%m-%d")

    lines.append(f"# Catalog Changelog: {log.scope}")
    lines.append("")
    lines.append(f"**Period:** {from_str} -> {to_str}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"| Metric | Value |"
        "\n|--------|-------|"
        f"\n| Entities changed | {log.total_entities_changed} |"
        f"\n| Total changes | {log.total_changes} |"
        f"\n| Major changes | {log.major_changes} |"
        f"\n| Minor changes | {log.minor_changes} |"
    )

    if log.top_changers:
        lines.append("")
        lines.append("## Top Changers")
        lines.append("")
        lines.append("| User | Changes |")
        lines.append("|------|---------|")
        for c in log.top_changers[:10]:
            lines.append(f"| `{c['user']}` | {c['change_count']} |")

    if log.entries:
        lines.append("")
        lines.append("## Changed Entities")
        lines.append("")
        for entry in log.entries:
            sev = "[MAJOR]" if entry.is_major else "[MINOR]"
            n = len(entry.changes)
            lines.append(
                f"- {sev} **{entry.entity_fqn}** ({entry.entity_type})"
                f" - {n} change{'s' if n != 1 else ''}"
                f" (v{entry.from_version}->v{entry.to_version}, by `{entry.updated_by}`)"
            )

    return "\n".join(lines)


def _format_changelog_json(log: CatalogChangelog) -> str:
    """Render a CatalogChangelog as compact JSON."""
    return log.model_dump_json(indent=2)


def format_changelog(log: CatalogChangelog, fmt: OutputFormat = OutputFormat.TERMINAL) -> str:
    """Render a CatalogChangelog in the requested format.

    Args:
        log: The changelog to render.
        fmt: Output format (terminal, markdown, json).

    Returns:
        Formatted string ready to print or write.
    """
    if fmt == OutputFormat.TERMINAL:
        return _format_changelog_terminal(log)
    if fmt == OutputFormat.MARKDOWN:
        return _format_changelog_markdown(log)
    return _format_changelog_json(log)


# ---------------------------------------------------------------------------
# Rich print helpers
# ---------------------------------------------------------------------------


def print_diff(diff: EntityDiff) -> None:
    """Print an EntityDiff to the terminal using Rich.

    Args:
        diff: The diff to display.
    """
    _console.rule(f"[cyan]{diff.entity_fqn}[/cyan]", style="blue")
    _console.print(format_diff(diff, OutputFormat.TERMINAL))
    _console.rule(style="blue dim")


def print_changelog(log: CatalogChangelog) -> None:
    """Print a CatalogChangelog to the terminal using Rich.

    Args:
        log: The changelog to display.
    """
    _console.print(format_changelog(log, OutputFormat.TERMINAL))
