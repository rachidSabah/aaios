"""AAiOS CLI entry point.

Run with: ``aaios`` (after install) or ``python -m surfaces.cli``.
"""

from __future__ import annotations

import platform
import sys
from importlib import metadata

import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(
    name="aaios",
    help="Agentic AI Operating System — orchestrate generic AI agents.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


def _version() -> str:
    """Return the installed AAiOS version, or a dev marker."""
    try:
        return metadata.version("aaios")
    except metadata.PackageNotFoundError:  # not installed (dev mode)
        return "0.1.0.dev0 (dev)"


@app.command()
def version() -> None:
    """Print the AAiOS version."""
    console.print(f"AAiOS v{_version()}")


@app.command()
def doctor() -> None:
    """Run health checks against the local AAiOS installation.

    Phase 2 stub: reports version, platform, and Python only.
    The full doctor (services, ACLs, master key, providers) lands in Phase 12.
    """
    table = Table(title="AAiOS Doctor — Phase 2 Stub", show_header=True)
    table.add_column("Check", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status", style="yellow")

    table.add_row("Version", _version(), "info")
    table.add_row("Python", platform.python_version(), "ok")
    table.add_row("Platform", platform.platform(), "ok")
    table.add_row("Implementation", platform.python_implementation(), "ok")
    table.add_row("Services", "not yet implemented", "pending")
    table.add_row("Database", "not yet implemented", "pending")
    table.add_row("Qdrant", "not yet implemented", "pending")
    table.add_row("Providers", "not yet implemented", "pending")
    table.add_row("Master key", "not yet implemented", "pending")

    console.print(table)
    console.print(
        "\n[dim]Full doctor implementation lands in Phase 12. "
        "See docs/architecture/09-roadmap.md.[/dim]",
    )


@app.command()
def dev() -> None:
    """Start the development stack (Phase 2 stub).

    The real ``aaios dev`` will start the API server and the Next.js dev server
    in the foreground. For now it prints what would happen.
    """
    console.print("[yellow]AAiOS dev mode (Phase 2 stub)[/yellow]")
    console.print("  • API server would start on http://127.0.0.1:8000")
    console.print("  • Web UI would start on http://127.0.0.1:3000")
    console.print("  • Runtime supervisor would start in-process")
    console.print("\n[dim]Use 'tasks dev' from the repo root for the real workflow.[/dim]")


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
    sys.exit(0)
