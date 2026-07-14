"""AAiOS CLI — Typer-based command-line interface.

Commands:
  aaios version          Print the version
  aaios doctor           Run health checks
  aaios run <goal>       Submit a task
  aaios tasks            List tasks
  aaios agents           List registered agents
  aaios plugins          Manage plugins
  aaios memory           Memory operations (recall, remember)
  aaios providers        List LLM providers
  aaios models           List available models
  aaios costs            Show cost summary
  aaios config           Show configuration
  aaios audit            Query audit log
  aaios dev              Start dev stack
"""

from __future__ import annotations

import platform
from importlib import metadata
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
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
    """Return the installed AAiOS version."""
    try:
        return metadata.version("aaios")
    except metadata.PackageNotFoundError:
        return "0.1.0.dev0 (dev)"


def _api_get(path: str) -> dict[str, Any]:
    """Make a GET request to the local API server."""
    import httpx

    try:
        resp = httpx.get(f"http://127.0.0.1:8000{path}", timeout=5.0)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data
    except Exception as e:
        return {"error": str(e)}


def _api_post(path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make a POST request to the local API server."""
    import httpx

    try:
        resp = httpx.post(f"http://127.0.0.1:8000{path}", json=body or {}, timeout=10.0)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the AAiOS version."""
    console.print(f"AAiOS v{_version()}")


@app.command()
def doctor() -> None:
    """Run health checks against the local AAiOS installation."""
    table = Table(title="AAiOS Doctor", show_header=True)
    table.add_column("Check", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status", style="yellow")

    table.add_row("Version", _version(), "info")
    table.add_row("Python", platform.python_version(), "ok")
    table.add_row("Platform", platform.platform(), "ok")

    # Check API server
    health = _api_get("/healthz")
    if "error" in health:
        table.add_row("API Server", "not running", "error")
    else:
        table.add_row("API Server", health.get("status", "unknown"), "ok")

    # Check agents
    agents = _api_get("/api/v1/agents")
    if "error" not in agents:
        count = len(agents.get("agents", []))
        table.add_row("Agents", f"{count} registered", "ok" if count > 0 else "warning")
    else:
        table.add_row("Agents", "unavailable", "warning")

    # Check providers
    providers = _api_get("/api/v1/providers")
    if "error" not in providers:
        count = len(providers.get("providers", []))
        table.add_row("Providers", f"{count} configured", "ok" if count > 0 else "warning")
    else:
        table.add_row("Providers", "unavailable", "warning")

    console.print(table)


@app.command()
def run(
    goal: str = typer.Argument(help="The goal to accomplish"),
    priority: str = typer.Option(
        "normal", "--priority", "-p", help="critical|high|normal|low|background"
    ),
) -> None:
    """Submit a task (goal) for execution."""
    result = _api_post("/api/v1/tasks", {"goal": goal, "priority": priority})
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)
    console.print(f"[green]Task submitted:[/green] {result.get('task_id', '?')}")
    console.print(f"  Status: {result.get('status', '?')}")


@app.command()
def tasks() -> None:
    """List all active tasks."""
    result = _api_get("/api/v1/tasks")
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)

    tasks_list = result.get("tasks", [])
    if not tasks_list:
        console.print("[dim]No active tasks.[/dim]")
        return

    table = Table(title="Active Tasks", show_header=True)
    table.add_column("Task ID", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Steps", style="green")
    table.add_column("Priority", style="blue")
    for t in tasks_list:
        table.add_row(
            t.get("task_id", "?")[:12] + "...",
            t.get("status", "?"),
            str(t.get("step_count", 0)),
            t.get("priority", "?"),
        )
    console.print(table)


@app.command()
def agents() -> None:
    """List all registered agents."""
    result = _api_get("/api/v1/agents")
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)

    agents_list = result.get("agents", [])
    if not agents_list:
        console.print("[dim]No agents registered.[/dim]")
        return

    table = Table(title="Registered Agents", show_header=True)
    table.add_column("Agent ID", style="cyan")
    table.add_column("Type", style="blue")
    table.add_column("Implementation", style="green")
    table.add_column("Version", style="yellow")
    table.add_column("Health", style="magenta")
    table.add_column("Capabilities", style="white")

    for a in agents_list:
        health = a.get("health", "?")
        health_style = (
            "green" if health == "healthy" else "red" if health == "unhealthy" else "yellow"
        )
        caps = ", ".join(a.get("capabilities", [])[:5])
        if len(a.get("capabilities", [])) > 5:
            caps += "..."
        table.add_row(
            a.get("agent_id", "?"),
            a.get("agent_type", "?"),
            a.get("implementation_name", "?"),
            a.get("version", "?"),
            f"[{health_style}]{health}[/{health_style}]",
            caps,
        )
    console.print(table)


@app.command()
def capabilities() -> None:
    """List all capability namespaces."""
    result = _api_get("/api/v1/capabilities")
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)

    caps = result.get("capabilities", [])
    if not caps:
        console.print("[dim]No capabilities indexed.[/dim]")
        return

    console.print(Panel("\n".join(f"  • {c}" for c in caps), title=f"Capabilities ({len(caps)})"))


@app.command()
def providers() -> None:
    """List LLM providers."""
    result = _api_get("/api/v1/providers")
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)

    providers_list = result.get("providers", [])
    if not providers_list:
        console.print("[dim]No providers configured.[/dim]")
        return

    table = Table(title="LLM Providers", show_header=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Success Rate", style="green")
    table.add_column("Avg Latency", style="blue")
    table.add_column("Failures", style="red")

    for p in providers_list:
        status = p.get("status", "?")
        status_style = (
            "green" if status == "healthy" else "red" if status == "unhealthy" else "yellow"
        )
        table.add_row(
            p.get("provider", "?"),
            f"[{status_style}]{status}[/{status_style}]",
            f"{p.get('success_rate', 0):.1%}",
            f"{p.get('avg_latency_s', 0):.2f}s",
            str(p.get("consecutive_failures", 0)),
        )
    console.print(table)


@app.command()
def models(
    provider: str | None = typer.Option(None, "--provider", "-p", help="Filter by provider"),
) -> None:
    """List available models."""
    path = "/api/v1/models" + (f"?provider={provider}" if provider else "")
    result = _api_get(path)
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)

    models_list = result.get("models", [])
    if not models_list:
        console.print("[dim]No models available.[/dim]")
        return

    table = Table(title="Available Models", show_header=True)
    table.add_column("Model", style="cyan")
    table.add_column("Provider", style="blue")
    table.add_column("Context", style="green")
    table.add_column("Input $/1M", style="yellow")
    table.add_column("Output $/1M", style="yellow")
    table.add_column("Features", style="magenta")

    for m in models_list:
        features: list[str] = []
        if m.get("supports_vision"):
            features.append("vision")
        if m.get("supports_tools"):
            features.append("tools")
        if m.get("supports_reasoning"):
            features.append("reasoning")
        table.add_row(
            m.get("name", "?"),
            m.get("provider", "?"),
            f"{m.get('context_window', 0):,}",
            f"${m.get('cost_per_1m_input_usd', 0):.2f}",
            f"${m.get('cost_per_1m_output_usd', 0):.2f}",
            ", ".join(features) or "-",
        )
    console.print(table)


@app.command()
def costs() -> None:
    """Show cost summary."""
    result = _api_get("/api/v1/costs")
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)

    total = result.get("total_cost_usd", 0.0)
    by_provider = result.get("by_provider", {})

    console.print(f"[green]Total cost:[/green] ${total:.4f}")
    if by_provider:
        table = Table(title="Cost by Provider", show_header=True)
        table.add_column("Provider", style="cyan")
        table.add_column("Cost (USD)", style="yellow")
        for p, c in sorted(by_provider.items(), key=lambda x: x[1], reverse=True):
            table.add_row(p, f"${c:.4f}")
        console.print(table)


@app.command()
def memory_recall(
    query: str = typer.Argument(help="The query to search for"),
    scope: str = typer.Option("long_term", "--scope", "-s", help="Memory scope type"),
    k: int = typer.Option(10, "--count", "-k", help="Max results"),
) -> None:
    """Recall items from memory."""
    result = _api_post(
        "/api/v1/memory/recall",
        {
            "scope_type": scope,
            "query": query,
            "k": k,
        },
    )
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)

    items = result.get("items", [])
    if not items:
        console.print("[dim]No results found.[/dim]")
        return

    console.print(
        f"[green]Found {result.get('total_found', 0)} items in {result.get('elapsed_s', 0):.3f}s[/green]\n"
    )
    for i, item in enumerate(items, 1):
        score = item.get("score", 0)
        source = item.get("source", "?")
        content = item.get("content", "")[:200]
        console.print(
            f"[cyan]{i}.[/cyan] [yellow]score={score:.3f}[/yellow] [blue]({source})[/blue]"
        )
        console.print(f"   {content}...")
        console.print()


@app.command()
def memory_remember(
    content: str = typer.Argument(help="The content to remember"),
    scope: str = typer.Option("long_term", "--scope", "-s", help="Memory scope type"),
) -> None:
    """Store an item in memory."""
    result = _api_post(
        "/api/v1/memory/remember",
        {
            "scope_type": scope,
            "content": content,
        },
    )
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)
    console.print(f"[green]Remembered:[/green] {result.get('item_id', '?')}")


@app.command()
def audit(
    actor: str | None = typer.Option(None, "--actor", "-a", help="Filter by actor ID"),
    action: str | None = typer.Option(None, "--action", help="Filter by action"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max entries"),
) -> None:
    """Query the audit log."""
    params = []
    if actor:
        params.append(f"actor_id={actor}")
    if action:
        params.append(f"action={action}")
    params.append(f"limit={limit}")
    path = "/api/v1/audit?" + "&".join(params)

    result = _api_get(path)
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)

    entries = result.get("entries", [])
    if not entries:
        console.print("[dim]No audit entries found.[/dim]")
        return

    table = Table(title="Audit Log", show_header=True)
    table.add_column("Timestamp", style="dim")
    table.add_column("Actor", style="cyan")
    table.add_column("Action", style="yellow")
    table.add_column("Target", style="green")
    table.add_column("Success", style="magenta")
    table.add_column("Hash", style="dim")

    for e in entries:
        success = "✓" if e.get("success") else "✗"
        table.add_row(
            e.get("timestamp", "?")[:19],
            e.get("actor", "?"),
            e.get("action", "?"),
            e.get("target", "?")[:40],
            success,
            e.get("hash", "?"),
        )
    console.print(table)


@app.command()
def dev() -> None:
    """Start the development stack (API + Web)."""
    console.print("[yellow]AAiOS dev mode[/yellow]")
    console.print("  Starting API server on http://127.0.0.1:8000 ...")
    console.print("  Starting Web UI on http://127.0.0.1:3000 ...")
    console.print("\n[dim]Run: tasks dev[/dim]")


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
