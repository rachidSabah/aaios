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

import os
import platform
import time
from importlib import metadata
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from services.doctor.manager import DoctorManager
from services.doctor.models import ScanType
from services.self_healing.engine import SelfHealingEngine
from services.self_healing.models import HealingStatus
from services.backup.manager import BackupManager
from services.backup.models import BackupType, ExportFormat
from services.backup.recovery import RecoveryManager
from services.update.manager import UpdateManager
from services.update.models import ReleaseChannel, UpdateInfo, UpdateStatus
from services.validator.manager import ReleaseValidator
from services.monitoring.monitor import ContinuousHealthMonitor
from services.monitoring.models import AlertChannel

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


def _api_get(path: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
    """Make a GET request to the local API server."""
    import httpx

    try:
        url = f"http://127.0.0.1:8000{path}"
        resp = httpx.get(url, params=params, timeout=5.0)
        resp.raise_for_status()
        data: dict[str, Any] = dict(resp.json())
        return data
    except httpx.HTTPError as exc:
        return {"error": str(exc)}


def _api_post(path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make a POST request to the local API server."""
    import httpx

    try:
        resp = httpx.post(f"http://127.0.0.1:8000{path}", json=body or {}, timeout=10.0)
        resp.raise_for_status()
        data: dict[str, Any] = dict(resp.json())
        return data
    except httpx.HTTPError as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the AAiOS version."""
    console.print(f"AAiOS v{_version()}")


@app.command()
def doctor(
    scan: str = typer.Option("quick", "--scan", "-s", help="quick|full|offline|online|security|dependency|performance|memory|storage|provider|agent|plugin|mcp|database|dashboard|api|cli|mission|workflow|graph|vector|config|audit|network|windows"),
    heal: bool = typer.Option(False, "--heal", "-h", help="Attempt auto-repair of detected failures"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve repairs"),
) -> None:
    """Run health checks and optional self-healing."""
    try:
        scan_type = ScanType(scan.lower())
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid scan type: {scan}. Choose from: {[s.value for s in ScanType]}")
        raise typer.Exit(1)  # noqa: B904

    manager = DoctorManager()
    with console.status("[bold green]Running diagnostic scan...[/bold green]"):
        report = manager.run_scan(scan_type)

    table = Table(title=f"AAiOS Doctor Diagnostic Report ({scan_type.value})", show_header=True)
    table.add_column("Score Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Health Score", f"{report.health_score}/100")
    table.add_row("Production Score", f"{report.production_score}/100")
    table.add_row("Risk Score", f"{report.risk_score}/100")
    table.add_row("Dependency Score", f"{report.dependency_score}/100")
    table.add_row("Security Score", f"{report.security_score}/100")
    table.add_row("Performance Score", f"{report.performance_score}/100")
    table.add_row("Availability Score", f"{report.availability_score}/100")

    console.print(table)
    console.print()

    if report.issues:
        issues_table = Table(title="Detected Issues", show_header=True)
        issues_table.add_column("ID", style="red")
        issues_table.add_column("Severity", style="magenta")
        issues_table.add_column("Description", style="white")
        issues_table.add_column("Recommended Fix", style="green")
        issues_table.add_column("Auto-Repair", style="blue")

        for issue in report.issues:
            issues_table.add_row(
                issue.id,
                issue.severity.value,
                issue.description,
                issue.recommended_fix,
                "Yes" if issue.repair_available else "No"
            )
        console.print(issues_table)
    else:
        console.print("[green]No issues found! System is healthy.[/green]")

    if heal:
        console.print("\n[yellow]Starting self-healing engine...[/yellow]")
        healing_engine = SelfHealingEngine(doctor_mgr=manager)
        import asyncio
        records = asyncio.run(healing_engine.run_healing(auto_approve=yes))
        if records:
            rep_table = Table(title="Self-Healing Executions", show_header=True)
            rep_table.add_column("Trigger", style="cyan")
            rep_table.add_column("Action", style="yellow")
            rep_table.add_column("Status", style="green")
            rep_table.add_column("Details", style="white")

            for r in records:
                rep_table.add_row(r.trigger.value, r.action_type.value, r.status.value, r.details)
            console.print(rep_table)
        else:
            console.print("[green]No healing actions were required.[/green]")


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
        raise typer.Exit(1)  # noqa: B904
    console.print(f"[green]Task submitted:[/green] {result.get('task_id', '?')}")
    console.print(f"  Status: {result.get('status', '?')}")


@app.command()
def tasks() -> None:
    """List all active tasks."""
    result = _api_get("/api/v1/tasks")
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)  # noqa: B904

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
        raise typer.Exit(1)  # noqa: B904

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
        raise typer.Exit(1)  # noqa: B904

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
        raise typer.Exit(1)  # noqa: B904

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
        raise typer.Exit(1)  # noqa: B904

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
        raise typer.Exit(1)  # noqa: B904

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
        raise typer.Exit(1)  # noqa: B904

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
        raise typer.Exit(1)  # noqa: B904
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
        raise typer.Exit(1)  # noqa: B904

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


@app.command()
def start(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
) -> None:
    """Start AAiOS in LIVE mode — boots everything and serves immediately.

    No mock mode. No demo features. Fully live.

    Boots: kernel, security, model router, memory, agent registry,
    orchestrator, supervisor, and the FastAPI API server.
    """
    console.print("[green]Starting AAiOS in LIVE mode...[/green]")
    import subprocess
    import sys

    cmd = [sys.executable, "scripts/start.py", "--host", host, "--port", str(port)]
    env = dict(os.environ)

    try:
        subprocess.run(cmd, env=env, check=True)  # noqa: S603
    except KeyboardInterrupt:
        console.print("\n[yellow]AAiOS shutting down...[/yellow]")
    except FileNotFoundError:
        console.print("[red]Error:[/red] Could not find scripts/start.py")
        console.print("Make sure you are in the AAiOS repository root.")
        raise typer.Exit(1)  # noqa: B904


@app.command()
def update(
    channel: str = typer.Option("stable", "--channel", help="Release channel: stable|lts|beta|nightly|enterprise"),
    check_only: bool = typer.Option(False, "--check", "-c", help="Only check for updates"),
    pin: str | None = typer.Option(None, "--pin", help="Pin system version"),
    offline: str | None = typer.Option(None, "--offline", help="Path to offline update zip package"),
) -> None:
    """Manage AAiOS system updates and migrations."""
    manager = UpdateManager()

    if pin:
        manager.pin_version(pin)
        console.print(f"[green]Pinned system version to {pin}[/green]")
        return

    try:
        chan_enum = ReleaseChannel(channel.lower())
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid channel: {channel}. Choose from: {[c.value for c in ReleaseChannel]}")
        raise typer.Exit(1)  # noqa: B904

    if offline:
        offline_path = Path(offline)
        if not offline_path.exists():
            console.print(f"[red]Error:[/red] Offline package not found: {offline}")
            raise typer.Exit(1)  # noqa: B904
        info = UpdateInfo(
            version="offline-package",
            channel=chan_enum,
            release_notes="Offline delta package update",
            package_url=offline_path.as_uri(),
            size_bytes=offline_path.stat().st_size,
            checksum="",
        )
        console.print("[yellow]Installing offline update package...[/yellow]")
        import asyncio
        report = asyncio.run(manager.install_update(info, offline_path))
        if report.status == UpdateStatus.SUCCESS:
            console.print("[green]Offline update installed successfully![/green]")
        else:
            console.print(f"[red]Offline update failed: {report.error}[/red]")
        return

    info = manager.check_for_updates(chan_enum)
    if not info:
        console.print("[green]Already up to date.[/green]")
        return

    console.print(f"[yellow]New update available: v{info.version} on channel '{info.channel.value}'[/yellow]")
    console.print(f"Notes: {info.release_notes}")

    if check_only:
        return

    with console.status("[bold green]Downloading update...[/bold green]"):
        package_path = manager.download_update(info)

    console.print("[yellow]Installing update and running migrations...[/yellow]")
    import asyncio
    report = asyncio.run(manager.install_update(info, package_path))
    if report.status == UpdateStatus.SUCCESS:
        console.print(f"[green]Successfully upgraded to v{info.version}![/green]")
    else:
        console.print(f"[red]Upgrade failed: {report.error}[/red]")
        if report.rollback_done:
            console.print("[yellow]System successfully rolled back to pre-upgrade state.[/yellow]")


@app.command()
def validate() -> None:
    """Run static, dependency, and performance validations."""
    validator = ReleaseValidator()
    with console.status("[bold green]Running release validation...[/bold green]"):
        val_report = validator.run_validation()
        cert_report = validator.generate_certification_report(val_report)
        readiness_report = validator.generate_readiness_report(val_report)

    val_table = Table(title="Enterprise Validation Report", show_header=True)
    val_table.add_column("Stage / Validation Check", style="cyan")
    val_table.add_column("Status", style="green")

    val_table.add_row("Static Analysis", "Passed" if val_report.static_analysis_ok else "Failed")
    val_table.add_row("Runtime Validation", "Passed" if val_report.runtime_ok else "Failed")
    val_table.add_row("Dependency Validation", "Passed" if val_report.dependencies_ok else "Failed")
    val_table.add_row("Provider Validation", "Passed" if val_report.providers_ok else "Failed")
    val_table.add_row("Plugin & MCP Validation", "Passed" if (val_report.plugins_ok and val_report.mcp_ok) else "Failed")
    val_table.add_row("Database Validation", "Passed" if val_report.database_ok else "Failed")
    val_table.add_row("Performance Validation", "Passed" if val_report.performance_ok else "Failed")
    val_table.add_row("Security Validation", "Passed" if val_report.security_ok else "Failed")

    console.print(val_table)
    console.print()

    cert_panel = Panel.fit(
        f"[cyan]Certification ID:[/cyan]  {cert_report.certification_id}\n"
        f"[cyan]Compliance Level:[/cyan]  {cert_report.compliance_level}\n"
        f"[cyan]Checked Controls:[/cyan]  {cert_report.checked_controls}\n"
        f"[cyan]Passed Controls:[/cyan]   {cert_report.passed_controls}\n"
        f"[cyan]Status:[/cyan]            {cert_report.status.upper()}\n"
        f"[cyan]Notes:[/cyan]             {cert_report.notes}",
        title="Enterprise Certification Report",
    )
    console.print(cert_panel)
    console.print()

    color = "green" if readiness_report.is_ready else "red"
    readiness_panel = Panel.fit(
        f"[cyan]Readiness Score:[/cyan]  {readiness_report.readiness_score}/100\n"
        f"[cyan]Ready for Prod:[/cyan]   [{color}]{readiness_report.is_ready}[/{color}]\n"
        f"[cyan]Blockers:[/cyan]         {', '.join(readiness_report.blockers) or 'None'}\n"
        f"[cyan]Recommendations:[/cyan]  {', '.join(readiness_report.recommendations) or 'None'}",
        title="Deployment Readiness Report",
    )
    console.print(readiness_panel)


@app.command()
def monitor(
    interval: int = typer.Option(5, "--interval", "-i", help="Monitoring interval in seconds"),
    slack: str | None = typer.Option(None, "--slack", help="Slack webhook URL"),
    discord: str | None = typer.Option(None, "--discord", help="Discord webhook URL"),
) -> None:
    """Start continuous health monitoring loop."""
    monitor_svc = ContinuousHealthMonitor()
    if slack:
        monitor_svc.configure_channel(AlertChannel.SLACK, slack)
    if discord:
        monitor_svc.configure_channel(AlertChannel.DISCORD, discord)

    console.print("[green]Continuous Health Monitor started. Press Ctrl+C to exit.[/green]")
    try:
        while True:
            metrics = monitor_svc.collect_metrics()
            statuses = monitor_svc.check_components()
            alerts = monitor_svc.evaluate_rules(metrics, statuses)
            if alerts:
                monitor_svc.dispatch_alerts(alerts)
            else:
                console.print(f"[dim]{datetime.now(UTC).isoformat()[:19]} - System healthy. CPU: {metrics.cpu_percent:.1f}% | RAM: {metrics.ram_used_gb:.1f}GB[/dim]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring loop stopped.[/yellow]")


backup_app = typer.Typer(help="Manage enterprise backups and snapshots.")
app.add_typer(backup_app, name="backup")


@backup_app.command("create")
def backup_create(
    backup_type: str = typer.Option("full", "--type", help="full|incremental|differential"),
    format_type: str = typer.Option("zip", "--format", help="zip|tar|json|yaml"),
    encrypt: bool = typer.Option(False, "--encrypt", "-e", help="Encrypt the backup archive"),
    tag: list[str] = typer.Option([], "--tag", help="Tags to apply to the backup"),
) -> None:
    """Create a new backup."""
    try:
        b_type = BackupType(backup_type.lower())
        f_type = ExportFormat(format_type.lower())
    except ValueError:
        console.print("[red]Error:[/red] Invalid type or format options")
        raise typer.Exit(1)  # noqa: B904

    manager = BackupManager()
    with console.status("[bold green]Creating backup...[/bold green]"):
        meta = manager.create_backup(b_type, f_type, encrypt=encrypt, tags=tag)
    console.print(f"[green]Backup created successfully: {meta.id}[/green]")
    console.print(f"Size: {meta.size_bytes} bytes")


@backup_app.command("list")
def backup_list() -> None:
    """List all available backups."""
    manager = BackupManager()
    backups = manager.list_backups()
    if not backups:
        console.print("[yellow]No backups found.[/yellow]")
        return
    table = Table(title="Available Backups", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Timestamp", style="white")
    table.add_column("Type", style="magenta")
    table.add_column("Format", style="yellow")
    table.add_column("Size (Bytes)", style="green")
    table.add_column("Encrypted", style="blue")

    for b in backups:
        table.add_row(b.id, b.timestamp.isoformat()[:19], b.backup_type.value, b.format.value, str(b.size_bytes), "Yes" if b.encrypted else "No")
    console.print(table)


@backup_app.command("delete")
def backup_delete(backup_id: str = typer.Argument(..., help="Backup ID to delete")) -> None:
    """Delete a backup."""
    manager = BackupManager()
    if manager.delete_backup(backup_id):
        console.print(f"[green]Deleted backup {backup_id}[/green]")
    else:
        console.print(f"[red]Failed to delete backup {backup_id}[/red]")


@backup_app.command("restore")
def backup_restore(
    backup_id: str = typer.Argument(..., help="Backup ID to restore"),
    components: str | None = typer.Option(None, "--components", help="Comma-separated list of components to selectively restore"),
) -> None:
    """Restore a backup with automatic rollback validation."""
    manager = BackupManager()
    recovery = RecoveryManager(backup_mgr=manager)
    comp_list = components.split(",") if components else None

    console.print(f"[yellow]Restoring backup {backup_id}...[/yellow]")
    import asyncio
    report = asyncio.run(recovery.restore_backup(backup_id, selective_components=comp_list))
    if report.success:
        console.print("[green]Backup restored successfully![/green]")
    else:
        console.print(f"[red]Restore failed: {', '.join(report.errors)}[/red]")
        if report.rolled_back:
            console.print("[yellow]Automatically rolled back to pre-restore state.[/yellow]")


@backup_app.command("snapshot-create")
def snapshot_create(
    tag: list[str] = typer.Option([], "--tag", help="Tags to apply to the snapshot"),
) -> None:
    """Create an immutable snapshot."""
    manager = BackupManager()
    with console.status("[bold green]Creating snapshot...[/bold green]"):
        meta = manager.create_backup(BackupType.FULL, ExportFormat.ZIP, encrypt=False, tags=tag, is_snapshot=True)
    console.print(f"[green]Snapshot created successfully: {meta.id}[/green]")
    console.print(f"Git Commit: {meta.git_commit or 'N/A'}")


@backup_app.command("snapshot-list")
def snapshot_list() -> None:
    """List all available snapshots."""
    manager = BackupManager()
    snapshots = manager.list_backups(is_snapshot=True)
    if not snapshots:
        console.print("[yellow]No snapshots found.[/yellow]")
        return
    table = Table(title="Available Snapshots", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Timestamp", style="white")
    table.add_column("Git Commit", style="magenta")
    table.add_column("Tags", style="yellow")
    table.add_column("Size (Bytes)", style="green")

    for s in snapshots:
        table.add_row(s.id, s.timestamp.isoformat()[:19], s.git_commit or "N/A", ", ".join(s.tags), str(s.size_bytes))
    console.print(table)


@backup_app.command("snapshot-compare")
def snapshot_compare(
    snap_a: str = typer.Argument(..., help="First snapshot ID"),
    snap_b: str = typer.Argument(..., help="Second snapshot ID"),
) -> None:
    """Compare two snapshots."""
    manager = BackupManager()
    diff = manager.compare_snapshots(snap_a, snap_b)
    console.print(f"[cyan]Comparing Snapshot A ({snap_a}) vs Snapshot B ({snap_b})[/cyan]\n")
    console.print(f"[green]Added files:[/green] {len(diff['added'])}")
    for f in diff['added'][:10]:
        console.print(f"  + {f}")
    console.print(f"\n[red]Deleted files:[/red] {len(diff['deleted'])}")
    for f in diff['deleted'][:10]:
        console.print(f"  - {f}")
    console.print(f"\n[yellow]Modified files:[/yellow] {len(diff['modified'])}")
    for f in diff['modified'][:10]:
        console.print(f"  * {f}")


@app.command()
def uninstall(
    remove_data: bool = typer.Option(
        False, "--remove-data", help="Also remove config, data, and logs"
    ),
    remove_agents: bool = typer.Option(False, "--remove-agents", help="Also remove agent CLIs"),
) -> None:
    """Uninstall AAiOS completely.

    Removes: venv, node_modules, config, data, logs, and the repository.
    Does NOT remove system dependencies (Python, Node.js, git).

    Examples:
      aaios uninstall                        # basic uninstall
      aaios uninstall --remove-data          # also delete config/data/logs
      aaios uninstall --remove-data --remove-agents  # nuke everything
    """
    import platform
    import subprocess

    console.print("[red]Uninstalling AAiOS...[/red]")

    if platform.system() == "Windows":
        script = "deploy/windows/uninstall.ps1"
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", script]
        if remove_data:
            cmd.append("-RemoveData")
        if remove_agents:
            cmd.append("-RemoveAgents")
    else:
        script = "deploy/wsl/uninstall.sh"
        cmd = ["bash", script]
        if remove_data:
            cmd.append("--remove-data")
        if remove_agents:
            cmd.append("--remove-agents")

    try:
        subprocess.run(cmd, check=True)  # noqa: S603
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Could not find {script}")
        console.print("Run from the AAiOS repository root, or use the one-liner:")
        if platform.system() == "Windows":
            console.print(
                "  irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/uninstall.ps1 | iex"
            )
        else:
            console.print(
                "  curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/wsl/uninstall.sh | bash"
            )
        raise typer.Exit(1)  # noqa: B904


def main() -> None:
    """CLI entry point."""
    app()


# --- Experience & Learning commands (v2.1) ---


experience_app = typer.Typer(help="Experience & Learning Engine — query past executions.")
learning_app = typer.Typer(help="Learning analytics and recommendations.")
app.add_typer(experience_app, name="experience")
app.add_typer(learning_app, name="learning")


@experience_app.command("list")
def experience_list(
    agent_id: str = typer.Option(None, "--agent", help="Filter by agent ID"),
    provider: str = typer.Option(None, "--provider", help="Filter by provider"),
    capability: str = typer.Option(None, "--capability", help="Filter by capability"),
    outcome: str = typer.Option(None, "--outcome", help="Filter by outcome (success/failure)"),
    limit: int = typer.Option(20, "--limit", help="Max results"),
) -> None:
    """List recent experiences."""
    params: dict[str, Any] = {"limit": limit}
    if agent_id:
        params["agent_id"] = agent_id
    if provider:
        params["provider"] = provider
    if capability:
        params["capability"] = capability
    if outcome:
        params["outcome"] = outcome
    try:
        data = _api_get("/api/v1/experience", params=params)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    experiences = data.get("experiences", [])
    if not experiences:
        console.print("[yellow]No experiences found.[/yellow]")
        return
    table = Table(title=f"Experiences ({data.get('count', 0)} shown, {data.get('total', 0)} total)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Timestamp", style="white")
    table.add_column("Agent", style="magenta")
    table.add_column("Goal", style="white")
    table.add_column("Outcome", style="green")
    table.add_column("Quality", style="yellow")
    for exp in experiences:
        outcome_str = exp.get("outcome", "?")
        color = "green" if outcome_str == "success" else "red"
        table.add_row(
            str(exp.get("experience_id", ""))[:8],
            exp.get("timestamp", "")[:19],
            str(exp.get("agent_id", "")),
            str(exp.get("goal", ""))[:40],
            f"[{color}]{outcome_str}[/{color}]",
            f"{exp.get('reflection_score', 0):.2f}",
        )
    console.print(table)


@experience_app.command("show")
def experience_show(
    experience_id: str = typer.Argument(..., help="Experience ID (UUID)"),
) -> None:
    """Show details of a single experience."""
    try:
        exp = _api_get(f"/api/v1/experience/{experience_id}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(Panel.fit(
        f"[cyan]Experience:[/cyan] {exp.get('experience_id')}\n"
        f"[cyan]Task:[/cyan]        {exp.get('task_id')}\n"
        f"[cyan]Agent:[/cyan]       {exp.get('agent_id')} ({exp.get('agent_type')})\n"
        f"[cyan]Provider:[/cyan]    {exp.get('provider', '—')} / {exp.get('model', '—')}\n"
        f"[cyan]Goal:[/cyan]        {exp.get('goal', '')}\n"
        f"[cyan]Input:[/cyan]       {exp.get('input_summary', '')[:100]}\n"
        f"[cyan]Output:[/cyan]      {exp.get('output_summary', '')[:100]}\n"
        f"[cyan]Outcome:[/cyan]     {exp.get('outcome')} (success={exp.get('success')})\n"
        f"[cyan]Time:[/cyan]        {exp.get('execution_time_s', 0):.3f}s\n"
        f"[cyan]Cost:[/cyan]        ${exp.get('cost_usd', 0):.4f}\n"
        f"[cyan]Quality:[/cyan]     reflection={exp.get('reflection_score', 0):.2f} qa={exp.get('qa_score', 0):.2f}\n"
        f"[cyan]Retries:[/cyan]     {exp.get('retries', 0)}\n"
        f"[cyan]Failure:[/cyan]     {exp.get('failure_reason', '—')}\n"
        f"[cyan]Recovery:[/cyan]    {exp.get('recovery_action', '—')}",
        title="Experience Detail",
    ))


@experience_app.command("search")
def experience_search(
    query: str = typer.Argument(..., help="Search query"),
    search_type: str = typer.Option(None, "--type", help="Search type (similar_successes, similar_failures, best_agent_for_capability, fastest_provider, cheapest_provider, highest_quality)"),
    limit: int = typer.Option(10, "--limit"),
) -> None:
    """Search experiences semantically."""
    try:
        data = _api_post("/api/v1/experience/search", body={
            "query": query, "search_type": search_type, "limit": limit,
        })
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    results = data.get("results", [])
    if not results:
        console.print("[yellow]No matching experiences found.[/yellow]")
        return
    table = Table(title=f"Search Results ({data.get('type', 'semantic')})")
    table.add_column("Score", style="cyan")
    table.add_column("Experience", style="white")
    table.add_column("Agent", style="magenta")
    table.add_column("Goal", style="white")
    table.add_column("Outcome", style="green")
    for r in results:
        table.add_row(
            f"{r.get('score', 0):.4f}",
            str(r.get("experience_id", ""))[:8],
            str(r.get("agent_id", "")),
            str(r.get("goal", ""))[:50],
            str(r.get("outcome", "")),
        )
    console.print(table)


@experience_app.command("replay")
def experience_replay(
    experience_id: str = typer.Argument(..., help="Experience ID to replay"),
    mode: str = typer.Option("dry_run", "--mode", help="dry_run, re_execute, compare"),
    comparison_agent: str = typer.Option(None, "--compare-with", help="Agent ID for compare mode"),
) -> None:
    """Replay an experience."""
    body: dict[str, Any] = {"mode": mode}
    if comparison_agent:
        body["comparison_agent_id"] = comparison_agent
    try:
        data = _api_post(f"/api/v1/experience/{experience_id}/replay", body=body)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(Panel.fit(
        f"[cyan]Original:[/cyan] {data.get('original_experience_id')}\n"
        f"[cyan]Mode:[/cyan]      {data.get('mode')}\n"
        f"[cyan]New ID:[/cyan]    {data.get('new_experience_id', '—')}\n"
        f"[cyan]Outcome:[/cyan]   {data.get('new_outcome', '—')}\n"
        f"[cyan]Time:[/cyan]      {data.get('new_execution_time_s', 0):.3f}s\n"
        f"[cyan]Cost:[/cyan]      ${data.get('new_cost_usd', 0):.4f}\n"
        f"[cyan]Error:[/cyan]     {data.get('error', '—')}",
        title="Replay Result",
    ))
    if data.get("comparison"):
        console.print("\n[cyan]Comparison:[/cyan]")
        for k, v in data["comparison"].items():
            console.print(f"  {k}: {v}")


@experience_app.command("export")
def experience_export(
    format: str = typer.Argument("json", help="Export format: json or csv"),
    agent_id: str = typer.Option(None, "--agent"),
    output: str = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
) -> None:
    """Export experiences to JSON or CSV."""
    params: dict[str, Any] = {}
    if agent_id:
        params["agent_id"] = agent_id
    try:
        data = _api_get(f"/api/v1/experience/export/{format}", params=params)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    content = data.get("content", "")
    if output:
        Path(output).write_text(content, encoding="utf-8")
        console.print(f"[green]Exported {len(content)} bytes to {output}[/green]")
    else:
        console.print(content)


@learning_app.command("stats")
def learning_stats() -> None:
    """Show top-level learning statistics."""
    try:
        stats = _api_get("/api/v1/learning/stats")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(Panel.fit(
        f"[cyan]Total experiences:[/cyan]  {stats.get('total_experiences', 0)}\n"
        f"[cyan]Successes:[/cyan]          {stats.get('total_successes', 0)}\n"
        f"[cyan]Failures:[/cyan]           {stats.get('total_failures', 0)}\n"
        f"[cyan]Success rate:[/cyan]       {stats.get('overall_success_rate', 0):.1%}\n"
        f"[cyan]Avg quality:[/cyan]        {stats.get('overall_avg_quality', 0):.3f}\n"
        f"[cyan]Avg latency:[/cyan]        {stats.get('overall_avg_latency_s', 0):.3f}s\n"
        f"[cyan]Avg cost:[/cyan]           ${stats.get('overall_avg_cost_usd', 0):.4f}\n"
        f"[cyan]Total cost:[/cyan]         ${stats.get('total_cost_usd', 0):.2f}\n"
        f"[cyan]Total tokens:[/cyan]       {stats.get('total_tokens', 0)}\n"
        f"[cyan]Agents tracked:[/cyan]     {stats.get('agent_count', 0)}\n"
        f"[cyan]Providers tracked:[/cyan]  {stats.get('provider_count', 0)}\n"
        f"[cyan]Capabilities:[/cyan]       {stats.get('capability_count', 0)}\n"
        f"[cyan]Workflows:[/cyan]          {stats.get('workflow_count', 0)}\n"
        f"[cyan]Last 24h:[/cyan]           {stats.get('last_24h_count', 0)} experiences\n"
        f"[cyan]Last 7d:[/cyan]            {stats.get('last_7d_count', 0)} experiences",
        title="Learning Statistics",
    ))


@learning_app.command("analyze")
def learning_analyze() -> None:
    """Analyze patterns in experience data."""
    try:
        report = _api_get("/api/v1/learning/patterns")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    successes = report.get("success_patterns", [])
    failures = report.get("failure_patterns", [])
    fixes = report.get("repeated_fixes", [])
    console.print(f"[green]Success patterns:[/green] {len(successes)}")
    for p in successes[:5]:
        console.print(f"  • {p.get('description')} ({p.get('occurrence_count')}x, quality={p.get('avg_quality', 0):.2f})")
    console.print(f"\n[red]Failure patterns:[/red] {len(failures)}")
    for p in failures[:5]:
        console.print(f"  • {p.get('description')} ({p.get('occurrence_count')}x)")
        if p.get("recovery_action"):
            console.print(f"    recovery: {p['recovery_action']} (success rate: {p.get('recovery_success_rate', 0):.0%})")
    console.print(f"\n[cyan]Repeated fixes:[/cyan] {len(fixes)}")
    for p in fixes[:5]:
        console.print(f"  • {p.get('description')} ({p.get('occurrence_count')}x)")


@learning_app.command("agents")
def learning_agents(limit: int = typer.Option(10, "--limit")) -> None:
    """Rank agents by reliability."""
    try:
        data = _api_get("/api/v1/learning/agents", params={"limit": str(limit)})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    agents = data.get("agents", [])
    if not agents:
        console.print("[yellow]No agent data yet.[/yellow]")
        return
    table = Table(title="Agent Reliability Rankings")
    table.add_column("Agent", style="magenta")
    table.add_column("Experiences", style="white")
    table.add_column("Success Rate", style="green")
    table.add_column("Quality", style="yellow")
    table.add_column("Latency", style="cyan")
    table.add_column("Cost", style="white")
    table.add_column("Reliability", style="green")
    table.add_column("Trend", style="blue")
    for a in agents:
        table.add_row(
            a.get("agent_id", ""),
            str(a.get("experience_count", 0)),
            f"{a.get('success_rate', 0):.1%}",
            f"{a.get('avg_quality', 0):.3f}",
            f"{a.get('avg_latency_s', 0):.3f}s",
            f"${a.get('avg_cost_usd', 0):.4f}",
            f"{a.get('reliability_score', 0):.3f}",
            a.get("trend", "?"),
        )
    console.print(table)


@learning_app.command("providers")
def learning_providers(limit: int = typer.Option(10, "--limit")) -> None:
    """Rank providers by reliability."""
    try:
        data = _api_get("/api/v1/learning/providers", params={"limit": str(limit)})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    providers = data.get("providers", [])
    if not providers:
        console.print("[yellow]No provider data yet.[/yellow]")
        return
    table = Table(title="Provider Reliability Rankings")
    table.add_column("Provider", style="magenta")
    table.add_column("Experiences", style="white")
    table.add_column("Success Rate", style="green")
    table.add_column("Latency", style="cyan")
    table.add_column("Cost", style="white")
    table.add_column("Reliability", style="green")
    for p in providers:
        table.add_row(
            p.get("provider", ""),
            str(p.get("experience_count", 0)),
            f"{p.get('success_rate', 0):.1%}",
            f"{p.get('avg_latency_s', 0):.3f}s",
            f"${p.get('avg_cost_usd', 0):.4f}",
            f"{p.get('reliability_score', 0):.3f}",
        )
    console.print(table)


@learning_app.command("recommend")
def learning_recommend(
    capability: str = typer.Argument(..., help="Capability namespace (e.g. code.generate)"),
) -> None:
    """Recommend the best agent for a capability based on history."""
    try:
        rec = _api_get(f"/api/v1/learning/recommendations/{capability}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(Panel.fit(
        f"[cyan]Capability:[/cyan]          {rec.get('capability')}\n"
        f"[green]Recommended agent:[/green] {rec.get('recommended_agent_id')}\n"
        f"[cyan]Score:[/cyan]              {rec.get('score', 0):.3f}\n"
        f"[cyan]Experiences:[/cyan]        {rec.get('experience_count', 0)}\n"
        f"[cyan]Success rate:[/cyan]       {rec.get('success_rate', 0):.1%}\n"
        f"[cyan]Avg quality:[/cyan]        {rec.get('avg_quality', 0):.3f}\n"
        f"[cyan]Avg cost:[/cyan]           ${rec.get('avg_cost_usd', 0):.4f}\n"
        f"[cyan]Reason:[/cyan]             {rec.get('reason', '')}",
        title="Agent Recommendation",
    ))


# --- Mission & Organization commands (v3.0) ---

mission_app = typer.Typer(help="Mission & Organization System — autonomous mission execution.")
app.add_typer(mission_app, name="mission")


@mission_app.command("create")
def mission_create(
    title: str = typer.Option(..., "--title", help="Mission title"),
    description: str = typer.Option("", "--description", help="Mission description"),
    objective: list[str] = typer.Option([], "--objective", help="Mission objective (repeatable)"),
    priority: str = typer.Option("normal", "--priority", help="critical/high/normal/low/background"),
    budget: float = typer.Option(0.0, "--budget", help="Total budget in USD"),
    owner: str = typer.Option(None, "--owner", help="Mission owner"),
    tag: list[str] = typer.Option([], "--tag", help="Mission tag (repeatable)"),
) -> None:
    """Create a new mission."""
    body: dict[str, Any] = {
        "title": title,
        "description": description,
        "objectives": objective,
        "priority": priority,
        "budget_total_usd": budget,
        "tags": tag,
    }
    if owner:
        body["owner"] = owner
    try:
        data = _api_post("/api/v1/missions", body=body)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(Panel.fit(
        f"[green]Mission created:[/green] {data.get('mission_id')}\n"
        f"[cyan]Title:[/cyan]       {data.get('title')}\n"
        f"[cyan]Status:[/cyan]      {data.get('status')}\n"
        f"[cyan]Priority:[/cyan]    {data.get('priority')}\n"
        f"[cyan]WBS nodes:[/cyan]   {len(data.get('wbs_nodes', []))}\n"
        f"[cyan]Budget:[/cyan]      ${data.get('budget', {}).get('total_usd', 0):.2f}",
        title="Mission Created",
    ))


@mission_app.command("start")
def mission_start(mission_id: str = typer.Argument(..., help="Mission ID")) -> None:
    """Start a mission."""
    try:
        data = _api_post(f"/api/v1/missions/{mission_id}/start", body={})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[green]Mission started:[/green] {data.get('status')}")


@mission_app.command("stop")
def mission_stop(
    mission_id: str = typer.Argument(..., help="Mission ID"),
    reason: str = typer.Option("", "--reason", help="Stop reason"),
) -> None:
    """Stop (cancel) a mission."""
    try:
        data = _api_post(f"/api/v1/missions/{mission_id}/cancel?reason={reason}", body={})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[yellow]Mission cancelled:[/yellow] {data.get('status')}")


@mission_app.command("pause")
def mission_pause(
    mission_id: str = typer.Argument(..., help="Mission ID"),
    reason: str = typer.Option("", "--reason", help="Pause reason"),
) -> None:
    """Pause a mission."""
    try:
        data = _api_post(f"/api/v1/missions/{mission_id}/pause?reason={reason}", body={})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[yellow]Mission paused:[/yellow] {data.get('status')}")


@mission_app.command("resume")
def mission_resume(mission_id: str = typer.Argument(..., help="Mission ID")) -> None:
    """Resume a paused mission."""
    try:
        data = _api_post(f"/api/v1/missions/{mission_id}/resume", body={})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[green]Mission resumed:[/green] {data.get('status')}")


@mission_app.command("cancel")
def mission_cancel(
    mission_id: str = typer.Argument(..., help="Mission ID"),
    reason: str = typer.Option("", "--reason", help="Cancellation reason"),
) -> None:
    """Cancel a mission."""
    try:
        data = _api_post(f"/api/v1/missions/{mission_id}/cancel?reason={reason}", body={})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[red]Mission cancelled:[/red] {data.get('status')}")


@mission_app.command("replay")
def mission_replay(mission_id: str = typer.Argument(..., help="Mission ID")) -> None:
    """Replay a mission's history."""
    try:
        data = _api_post(f"/api/v1/missions/{mission_id}/replay", body={})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[cyan]Events replayed:[/cyan] {data.get('events_replayed', 0)}")
    console.print(f"[cyan]Final status:[/cyan] {data.get('final_status', '')}")
    timeline = data.get("timeline", [])
    if timeline:
        console.print(f"\n[cyan]Timeline ({len(timeline)} entries):[/cyan]")
        for entry in timeline[:20]:
            console.print(f"  {entry.get('timestamp', '')[:19]}  {entry.get('event_type', '')}  {entry.get('description', '')}")


@mission_app.command("graph")
def mission_graph(mission_id: str = typer.Argument(..., help="Mission ID")) -> None:
    """Show a mission's WBS dependency graph."""
    try:
        data = _api_get(f"/api/v1/missions/{mission_id}/graph")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[cyan]Graph:[/cyan] {data.get('node_count', 0)} nodes, {data.get('edge_count', 0)} edges")
    nodes = data.get("nodes", [])
    if nodes:
        table = Table(title="WBS Nodes")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("Title", style="white")
        table.add_column("Status", style="green")
        table.add_column("Agent", style="yellow")
        for n in nodes[:30]:
            table.add_row(
                str(n.get("id", ""))[:8],
                n.get("type", ""),
                str(n.get("title", ""))[:40],
                n.get("status", ""),
                n.get("assigned_agent_id", "") or "—",
            )
        console.print(table)


@mission_app.command("timeline")
def mission_timeline(mission_id: str = typer.Argument(..., help="Mission ID")) -> None:
    """Show a mission's timeline."""
    try:
        data = _api_get(f"/api/v1/missions/{mission_id}/timeline")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    timeline = data.get("timeline", [])
    console.print(f"[cyan]Timeline:[/cyan] {len(timeline)} entries")
    for entry in timeline[:30]:
        console.print(f"  {entry.get('timestamp', '')[:19]}  [{entry.get('event_type', '')}]  {entry.get('description', '')}")


@mission_app.command("analytics")
def mission_analytics(mission_id: str = typer.Argument(..., help="Mission ID")) -> None:
    """Show mission analytics."""
    try:
        data = _api_get(f"/api/v1/missions/{mission_id}/analytics")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(Panel.fit(
        f"[cyan]Status:[/cyan]         {data.get('status', '')}\n"
        f"[cyan]Decisions:[/cyan]      {data.get('decisions', 0)}\n"
        f"[cyan]Artifacts:[/cyan]      {data.get('artifacts', 0)}\n"
        f"[cyan]Risks:[/cyan]          {data.get('risks', 0)}\n"
        f"[cyan]Milestones:[/cyan]     {data.get('milestones', 0)}\n"
        f"[cyan]Elapsed:[/cyan]        {data.get('elapsed_s', 0):.1f}s\n"
        f"[cyan]Budget spent:[/cyan]   ${data.get('budget', {}).get('spent_usd', 0):.4f}",
        title="Mission Analytics",
    ))


@mission_app.command("export")
def mission_export(
    format: str = typer.Argument("json", help="Export format: json or csv"),
    output: str = typer.Option(None, "--output", "-o", help="Output file"),
) -> None:
    """Export all missions."""
    try:
        # Use the portfolio metrics endpoint for a summary, or list all
        data = _api_get("/api/v1/missions?limit=1000")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    import json as _json
    content = _json.dumps(data, indent=2) if format == "json" else ""
    if output:
        Path(output).write_text(content, encoding="utf-8")
        console.print(f"[green]Exported to {output}[/green]")
    else:
        console.print(content)


@mission_app.command("list")
def mission_list(
    status: str = typer.Option(None, "--status", help="Filter by status"),
    limit: int = typer.Option(20, "--limit"),
) -> None:
    """List missions."""
    params: dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status
    try:
        data = _api_get("/api/v1/missions", params=params)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    missions = data.get("missions", [])
    if not missions:
        console.print("[yellow]No missions found.[/yellow]")
        return
    table = Table(title=f"Missions ({len(missions)})")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Status", style="green")
    table.add_column("Priority", style="magenta")
    table.add_column("WBS", style="yellow")
    table.add_column("Budget", style="white")
    for m in missions:
        status_color = "green" if m.get("status") == "completed" else "yellow" if m.get("status") == "executing" else "red"
        table.add_row(
            str(m.get("mission_id", ""))[:8],
            str(m.get("title", ""))[:40],
            f"[{status_color}]{m.get('status', '')}[/{status_color}]",
            m.get("priority", ""),
            str(len(m.get("wbs_nodes", []))),
            f"${m.get('budget', {}).get('spent_usd', 0):.2f}/${m.get('budget', {}).get('total_usd', 0):.2f}",
        )
    console.print(table)


# --- Intelligence commands (v3.1) ---

intelligence_app = typer.Typer(help="Enterprise Intelligence — health, forecasts, optimization, risks.")
app.add_typer(intelligence_app, name="intelligence")


@intelligence_app.command("health")
def intelligence_health() -> None:
    """Show enterprise health score."""
    try:
        data = _api_get("/api/v1/intelligence/health")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    grade = data.get("grade", "?")
    score = data.get("overall_score", 0)
    status = data.get("status", "?")
    color = "green" if score >= 0.8 else "yellow" if score >= 0.6 else "red"
    console.print(Panel.fit(
        f"[{color}]Enterprise Health: {grade} ({score:.2f}) — {status}[/{color}]\n\n"
        f"[cyan]Operational:[/cyan]         {data.get('operational', 0):.2f}\n"
        f"[cyan]Mission:[/cyan]             {data.get('mission', 0):.2f}\n"
        f"[cyan]Agent Efficiency:[/cyan]   {data.get('agent_efficiency', 0):.2f}\n"
        f"[cyan]Provider Efficiency:[/cyan]{data.get('provider_efficiency', 0):.2f}\n"
        f"[cyan]Workflow Quality:[/cyan]   {data.get('workflow_quality', 0):.2f}\n"
        f"[cyan]Execution Success:[/cyan]  {data.get('execution_success', 0):.2f}\n"
        f"[cyan]Risk Level:[/cyan]         {data.get('risk_level', 0):.2f}\n"
        f"[cyan]Reliability:[/cyan]        {data.get('reliability', 0):.2f}\n"
        f"[cyan]Cost Efficiency:[/cyan]    {data.get('cost_efficiency', 0):.2f}\n"
        f"[cyan]Learning Velocity:[/cyan]  {data.get('learning_velocity', 0):.2f}\n"
        f"[cyan]Innovation:[/cyan]         {data.get('innovation', 0):.2f}",
        title="Enterprise Health Score",
    ))


@intelligence_app.command("analyze")
def intelligence_analyze() -> None:
    """Show full intelligence analysis."""
    try:
        data = _api_get("/api/v1/intelligence/all")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    health = data.get("health", {})
    console.print(f"[cyan]Health:[/cyan] {health.get('grade', '?')} ({health.get('overall_score', 0):.2f})")
    console.print(f"[cyan]Forecasts:[/cyan] {len(data.get('forecasts', []))}")
    for f in data.get("forecasts", [])[:5]:
        console.print(f"  {f.get('forecast_type', '')}: {f.get('probability', 0):.0%} — {f.get('prediction', '')[:60]}")
    console.print(f"\n[cyan]Recommendations:[/cyan] {len(data.get('recommendations', []))}")
    for r in data.get("recommendations", [])[:5]:
        console.print(f"  [{r.get('priority', '')}] {r.get('title', '')[:60]}")
    console.print(f"\n[cyan]Risks:[/cyan] {len(data.get('risks', []))}")
    for r in data.get("risks", [])[:5]:
        console.print(f"  [{r.get('level', '')}] {r.get('description', '')[:60]}")


@intelligence_app.command("forecast")
def intelligence_forecast() -> None:
    """Show predictive forecasts."""
    try:
        data = _api_get("/api/v1/intelligence/forecast")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    forecasts = data.get("forecasts", [])
    if not forecasts:
        console.print("[yellow]No forecasts available.[/yellow]")
        return
    table = Table(title=f"Forecasts ({len(forecasts)})")
    table.add_column("Type", style="cyan")
    table.add_column("Probability", style="yellow")
    table.add_column("Confidence", style="magenta")
    table.add_column("Prediction", style="white")
    table.add_column("Horizon", style="green")
    for f in forecasts:
        prob = f.get("probability", 0)
        color = "red" if prob > 0.5 else "yellow" if prob > 0.3 else "green"
        table.add_row(
            f.get("forecast_type", ""),
            f"[{color}]{prob:.0%}[/{color}]",
            f.get("confidence", ""),
            str(f.get("prediction", ""))[:50],
            f.get("time_horizon", ""),
        )
    console.print(table)


@intelligence_app.command("optimize")
def intelligence_optimize() -> None:
    """Show optimization recommendations."""
    try:
        data = _api_get("/api/v1/intelligence/optimization")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    recs = data.get("recommendations", [])
    if not recs:
        console.print("[yellow]No optimization recommendations available.[/yellow]")
        return
    table = Table(title=f"Optimization Recommendations ({len(recs)})")
    table.add_column("Priority", style="red")
    table.add_column("Type", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Impact", style="yellow")
    table.add_column("Improvement", style="green")
    for r in recs:
        table.add_row(
            r.get("priority", ""),
            r.get("optimization_type", ""),
            str(r.get("title", ""))[:50],
            f"{r.get('estimated_impact', 0):.0%}",
            str(r.get("expected_improvement", ""))[:30],
        )
    console.print(table)


@intelligence_app.command("risks")
def intelligence_risks() -> None:
    """Show risk assessments + heat map."""
    try:
        data = _api_get("/api/v1/intelligence/risks")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    risks = data.get("risks", [])
    heat_map = data.get("heat_map", {})
    console.print(f"[cyan]Risk Heat Map:[/cyan] {heat_map.get('total_risks', 0)} total risks")
    by_level = heat_map.get("by_level", {})
    for level in ["critical", "high", "medium", "low", "negligible"]:
        count = by_level.get(level, 0)
        if count:
            color = "red" if level in ("critical", "high") else "yellow" if level == "medium" else "green"
            console.print(f"  [{color}]{level}[/{color}]: {count}")
    if risks:
        table = Table(title=f"Risk Details ({len(risks)})")
        table.add_column("Level", style="red")
        table.add_column("Type", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Score", style="yellow")
        table.add_column("Mitigation", style="green")
        for r in risks[:15]:
            table.add_row(
                r.get("level", ""),
                r.get("risk_type", ""),
                str(r.get("description", ""))[:40],
                f"{r.get('risk_score', 0):.2f}",
                str(r.get("mitigation", ""))[:40],
            )
        console.print(table)


@intelligence_app.command("capacity")
def intelligence_capacity() -> None:
    """Show capacity forecasts."""
    try:
        data = _api_get("/api/v1/intelligence/capacity")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    caps = data.get("capacity", [])
    if not caps:
        console.print("[yellow]No capacity data available.[/yellow]")
        return
    table = Table(title=f"Capacity Forecasts ({len(caps)})")
    table.add_column("Resource", style="cyan")
    table.add_column("Usage", style="white")
    table.add_column("Capacity", style="white")
    table.add_column("Util %", style="yellow")
    table.add_column("7d Projection", style="magenta")
    table.add_column("30d Projection", style="red")
    table.add_column("Exhaustion ETA", style="red")
    for c in caps:
        util = c.get("utilization_pct", 0)
        color = "red" if util > 80 else "yellow" if util > 60 else "green"
        table.add_row(
            c.get("resource", ""),
            f"{c.get('current_usage', 0):.1f}",
            f"{c.get('current_capacity', 0):.1f}",
            f"[{color}]{util:.0f}%[/{color}]",
            f"{c.get('projected_usage_7d', 0):.1f}",
            f"{c.get('projected_usage_30d', 0):.1f}",
            c.get("exhaustion_eta", "—")[:19] if c.get("exhaustion_eta") else "—",
        )
    console.print(table)


@intelligence_app.command("report")
def intelligence_report(
    report_type: str = typer.Argument("daily_executive", help="Report type: daily_executive, weekly_operations, monthly_performance, reliability, optimization, risk, mission"),
) -> None:
    """Generate an intelligence report."""
    try:
        data = _api_get(f"/api/v1/intelligence/report/{report_type}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    health = data.get("health_score", {})
    console.print(Panel.fit(
        f"[cyan]Report Type:[/cyan] {data.get('report_type', '')}\n"
        f"[cyan]Generated:[/cyan]  {data.get('generated_at', '')[:19]}\n"
        f"[cyan]Period:[/cyan]     {data.get('period_start', '')[:19]} → {data.get('period_end', '')[:19]}\n"
        f"[cyan]Health:[/cyan]     {health.get('grade', '?')} ({health.get('overall_score', 0):.2f})\n"
        f"\n[cyan]Summary:[/cyan]\n{data.get('summary', '')}\n"
        f"\n[cyan]Key Findings:[/cyan]",
        title="Intelligence Report",
    ))
    for finding in data.get("key_findings", []):
        console.print(f"  • {finding}")
    console.print("\n[cyan]Action Items:[/cyan]")
    for action in data.get("action_items", []):
        console.print(f"  → {action}")


# --- Execution commands (v4.0) ---

exec_app = typer.Typer(help="Autonomous Execution — run real-world operations safely.")
app.add_typer(exec_app, name="exec")


@exec_app.command("run")
def exec_run(
    domain: str = typer.Option("terminal", "--domain", help="Execution domain (terminal, filesystem, git, etc.)"),
    action: str = typer.Option(..., "--action", help="Action to execute"),
    param: list[str] = typer.Option([], "--param", help="key=value parameter (repeatable)"),
    description: str = typer.Option("", "--description"),
    timeout: float = typer.Option(120.0, "--timeout"),
) -> None:
    """Run an execution."""
    params: dict[str, Any] = {}
    for p in param:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k] = v
    body: dict[str, Any] = {
        "domain": domain, "action": action, "parameters": params,
        "description": description, "timeout_s": timeout,
    }
    try:
        data = _api_post("/api/v1/execution", body=body)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    status_color = "green" if data.get("succeeded") else "red"
    console.print(Panel.fit(
        f"[{status_color}]Status:[/{status_color}] {data.get('status', '')}\n"
        f"[cyan]Exit code:[/cyan]  {data.get('exit_code', '—')}\n"
        f"[cyan]Duration:[/cyan]   {data.get('duration_s', 0):.3f}s\n"
        f"[cyan]Error:[/cyan]      {data.get('error', '—')}",
        title=f"Execution {data.get('execution_id', '')[:8]}",
    ))
    if data.get("stdout"):
        console.print(f"\n[cyan]stdout:[/cyan]\n{data['stdout'][:2000]}")
    if data.get("stderr"):
        console.print(f"\n[yellow]stderr:[/yellow]\n{data['stderr'][:2000]}")


@exec_app.command("cancel")
def exec_cancel(
    execution_id: str = typer.Argument(...),
    reason: str = typer.Option("", "--reason"),
) -> None:
    """Cancel an execution."""
    try:
        data = _api_post(f"/api/v1/execution/{execution_id}/cancel?reason={reason}", body={})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[yellow]Cancelled:[/yellow] {data.get('status', '')}")


@exec_app.command("list")
def exec_list(
    domain: str = typer.Option(None, "--domain"),
    status: str = typer.Option(None, "--status"),
    limit: int = typer.Option(20, "--limit"),
) -> None:
    """List executions."""
    params: dict[str, Any] = {"limit": limit}
    if domain:
        params["domain"] = domain
    if status:
        params["status"] = status
    try:
        data = _api_get("/api/v1/execution", params=params)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    execs = data.get("executions", [])
    if not execs:
        console.print("[yellow]No executions found.[/yellow]")
        return
    table = Table(title=f"Executions ({len(execs)})")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Domain", style="magenta")
    table.add_column("Action", style="white")
    table.add_column("Status", style="green")
    table.add_column("Duration", style="yellow")
    table.add_column("Error", style="red")
    for ex in execs:
        st = ex.get("status", "")
        color = "green" if st == "succeeded" else "red" if st in ("failed", "cancelled") else "yellow"
        table.add_row(
            str(ex.get("execution_id", ""))[:8],
            ex.get("domain", ""),
            ex.get("action", ""),
            f"[{color}]{st}[/{color}]",
            f"{ex.get('duration_s', 0):.2f}s",
            str(ex.get("error", ""))[:30],
        )
    console.print(table)


@exec_app.command("logs")
def exec_logs(execution_id: str = typer.Argument(...)) -> None:
    """Show logs for an execution."""
    try:
        data = _api_get(f"/api/v1/execution/{execution_id}/logs")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    logs = data.get("logs", [])
    for log in logs:
        level = log.get("level", "info")
        color = {"error": "red", "warning": "yellow", "info": "white", "debug": "cyan"}.get(level, "white")
        console.print(f"[{color}]{log.get('timestamp', '')[:19]}[/{color}] [{level}] {log.get('message', '')[:200]}")


@exec_app.command("replay")
def exec_replay(execution_id: str = typer.Argument(...)) -> None:
    """Replay an execution."""
    try:
        data = _api_post(f"/api/v1/execution/{execution_id}/replay", body={})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[green]Replayed:[/green] status={data.get('status', '')} id={data.get('execution_id', '')[:8]}")


@exec_app.command("approve")
def exec_approve(
    execution_id: str = typer.Argument(...),
    decided_by: str = typer.Option("operator", "--by"),
    reason: str = typer.Option("Approved via CLI", "--reason"),
) -> None:
    """Approve a pending execution."""
    try:
        data = _api_post(f"/api/v1/execution/{execution_id}/approve?decided_by={decided_by}&reason={reason}", body={})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[green]Approved:[/green] {data.get('status', '')}")


@exec_app.command("history")
def exec_history(
    domain: str = typer.Option(None, "--domain"),
    limit: int = typer.Option(50, "--limit"),
) -> None:
    """Show execution history."""
    params: dict[str, Any] = {"limit": limit}
    if domain:
        params["domain"] = domain
    try:
        data = _api_get("/api/v1/execution/history", params=params)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    history = data.get("history", [])
    if not history:
        console.print("[yellow]No execution history.[/yellow]")
        return
    table = Table(title=f"Execution History ({len(history)})")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Domain", style="magenta")
    table.add_column("Action", style="white")
    table.add_column("Status", style="green")
    table.add_column("Duration", style="yellow")
    for h in history:
        st = h.get("status", "")
        color = "green" if st == "succeeded" else "red" if st in ("failed", "cancelled") else "yellow"
        table.add_row(
            str(h.get("execution_id", ""))[:8],
            h.get("domain", ""),
            h.get("action", ""),
            f"[{color}]{st}[/{color}]",
            f"{h.get('duration_s', 0):.2f}s",
        )
    console.print(table)


@exec_app.command("monitor")
def exec_monitor() -> None:
    """Show execution overview (pending approvals + recent history)."""
    try:
        approvals = _api_get("/api/v1/execution/approvals/pending")
        history = _api_get("/api/v1/execution/history?limit=10")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    pending = approvals.get("approvals", [])
    console.print(f"[cyan]Pending Approvals:[/cyan] {len(pending)}")
    for a in pending:
        console.print(f"  [{a.get('risk_level', '')}] {a.get('domain', '')}/{a.get('action', '')} — {a.get('description', '')[:60]}")
    console.print(f"\n[cyan]Recent Executions:[/cyan] {history.get('count', 0)}")
    for h in history.get("history", [])[:10]:
        st = h.get("status", "")
        color = "green" if st == "succeeded" else "red" if st in ("failed", "cancelled") else "yellow"
        console.print(f"  [{color}]{st}[/{color}] {h.get('domain', '')}/{h.get('action', '')} ({h.get('duration_s', 0):.2f}s)")


# --- Cognitive Intelligence commands (v5.0) ---

cognitive_app = typer.Typer(help="Cognitive Intelligence — learning, prediction, optimization, knowledge graph.")
app.add_typer(cognitive_app, name="cognitive")


@cognitive_app.command("learning")
def cognitive_learning() -> None:
    """Show learning insights."""
    try:
        data = _api_get("/api/v1/cognitive/learning")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    insights = data.get("insights", [])
    console.print(f"[cyan]Learning Insights:[/cyan] {len(insights)}")
    for i in insights[:10]:
        console.print(f"  [{i.get('category', '')}] {i.get('finding', '')[:80]}")
    metrics = data.get("metrics", [])
    if metrics:
        console.print("\n[cyan]Metrics:[/cyan]")
        for m in metrics:
            console.print(f"  {m.get('name', '')}: {m.get('value', 0):.4f} {m.get('unit', '')}")


@cognitive_app.command("predict")
def cognitive_predict(
    goal: str = typer.Option("", "--goal", help="Goal to predict"),
    agent: str = typer.Option("", "--agent", help="Agent to use"),
) -> None:
    """Generate predictions for a context."""
    body: dict[str, Any] = {"goal": goal}
    if agent:
        body["agent"] = agent
    try:
        data = _api_post("/api/v1/cognitive/predict", body=body)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    predictions = data.get("predictions", [])
    console.print(f"[cyan]Predictions:[/cyan] {len(predictions)}")
    for p in predictions:
        console.print(f"  {p.get('prediction_type', '')}: {p.get('predicted_value', 0):.4f} "
                      f"(confidence: {p.get('confidence', 0):.2f})")
        console.print(f"    {p.get('explanation', '')[:100]}")


@cognitive_app.command("optimize")
def cognitive_optimize() -> None:
    """Show optimization recommendations."""
    try:
        data = _api_get("/api/v1/cognitive/recommendations")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    recs = data.get("recommendations", [])
    if not recs:
        console.print("[yellow]No recommendations available.[/yellow]")
        return
    for r in recs:
        console.print(f"\n  [{r.get('priority', '')}] {r.get('title', '')}")
        console.print(f"  {r.get('description', '')[:80]}")
        console.print(f"  Impact: {r.get('estimated_impact', 0):.0%} | Confidence: {r.get('confidence', 0):.0%}")


@cognitive_app.command("experience")
def cognitive_experience() -> None:
    """Show experience statistics."""
    try:
        data = _api_get("/api/v1/cognitive/experience")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(Panel.fit(
        f"[cyan]Total:[/cyan]          {data.get('total', 0)}\n"
        f"[cyan]Successes:[/cyan]      {data.get('successes', 0)}\n"
        f"[cyan]Failures:[/cyan]       {data.get('failures', 0)}\n"
        f"[cyan]Success rate:[/cyan]   {data.get('success_rate', 0):.1%}\n"
        f"[cyan]Avg cost:[/cyan]       ${data.get('avg_cost_usd', 0):.4f}\n"
        f"[cyan]Avg latency:[/cyan]    {data.get('avg_latency_s', 0):.2f}s\n"
        f"[cyan]Avg risk:[/cyan]       {data.get('avg_risk_score', 0):.2f}\n"
        f"[cyan]Avg confidence:[/cyan]{data.get('avg_confidence', 0):.2f}\n"
        f"[cyan]Agents:[/cyan]         {data.get('unique_agents', 0)}\n"
        f"[cyan]Providers:[/cyan]      {data.get('unique_providers', 0)}",
        title="Cognitive Experience Statistics",
    ))


@cognitive_app.command("knowledge")
def cognitive_knowledge() -> None:
    """Show knowledge graph summary."""
    try:
        data = _api_get("/api/v1/cognitive/knowledge-graph")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[cyan]Knowledge Graph:[/cyan] {data.get('node_count', 0)} nodes, {data.get('edge_count', 0)} edges")


@cognitive_app.command("architecture")
def cognitive_architecture() -> None:
    """Show architecture intelligence."""
    try:
        data = _api_get("/api/v1/cognitive/architecture")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    issues = data.get("issues", [])
    console.print(f"[cyan]Architecture Issues:[/cyan] {len(issues)}")
    for issue in issues[:10]:
        console.print(f"  [{issue.get('severity', '')}] {issue.get('issue_type', '')}: "
                      f"{issue.get('description', '')[:60]}")


@cognitive_app.command("report")
def cognitive_report(
    report_type: str = typer.Argument("execution", help="Report type"),
    format: str = typer.Option("json", "--format", help="json, markdown, csv"),
) -> None:
    """Generate a cognitive report."""
    try:
        if format == "json":
            data = _api_get(f"/api/v1/cognitive/reports/{report_type}")
            console.print(Panel.fit(
                f"[cyan]Type:[/cyan]    {data.get('title', '')}\n"
                f"[cyan]Summary:[/cyan] {data.get('summary', '')}",
                title="Cognitive Report",
            ))
            for finding in data.get("key_findings", []):
                console.print(f"  • {finding}")
        else:
            data = _api_get(f"/api/v1/cognitive/reports/{report_type}/export/{format}")
            console.print(data.get("content", ""))
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@cognitive_app.command("health")
def cognitive_health() -> None:
    """Show repository health."""
    try:
        data = _api_get("/api/v1/cognitive/repository-health")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(Panel.fit(
        f"[cyan]Health Score:[/cyan]     {data.get('health_score', 0)}/100\n"
        f"[cyan]Source files:[/cyan]     {data.get('source_files', 0)}\n"
        f"[cyan]Test files:[/cyan]       {data.get('test_files', 0)}\n"
        f"[cyan]Source lines:[/cyan]     {data.get('source_lines', 0)}\n"
        f"[cyan]Test lines:[/cyan]       {data.get('test_lines', 0)}\n"
        f"[cyan]Test/Source ratio:[/cyan] {data.get('test_to_source_ratio', 0)}\n"
        f"[cyan]Doc files:[/cyan]        {data.get('documentation_files', 0)}\n"
        f"[cyan]Has README:[/cyan]       {data.get('has_readme', False)}\n"
        f"[cyan]Has CHANGELOG:[/cyan]    {data.get('has_changelog', False)}\n"
        f"[cyan]Has LICENSE:[/cyan]      {data.get('has_license', False)}",
        title="Repository Health",
    ))


# --- Knowledge Platform commands (v5.1) ---

knowledge_app = typer.Typer(help="Knowledge & Memory Platform — enterprise knowledge management.")
app.add_typer(knowledge_app, name="knowledge")


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit"),
) -> None:
    """Search knowledge entries."""
    try:
        data = _api_post("/api/v1/knowledge/search", body={"query": query, "limit": limit})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    results = data.get("results", [])
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return
    for r in results:
        console.print(f"  [{r.get('match_type', '')}] {r.get('title', '')} (score: {r.get('score', 0):.3f})")
        console.print(f"    {r.get('content_snippet', '')[:100]}")


@knowledge_app.command("rag")
def knowledge_rag(
    query: str = typer.Argument(..., help="RAG query"),
    max_results: int = typer.Option(5, "--max"),
) -> None:
    """RAG retrieval."""
    try:
        data = _api_post("/api/v1/knowledge/rag", body={"query": query, "max_results": max_results})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[cyan]Confidence:[/cyan] {data.get('confidence', 0):.2f}")
    console.print(f"[cyan]Tokens:[/cyan]     {data.get('token_count', 0)}")
    console.print(f"[cyan]Sources:[/cyan]    {len(data.get('sources', []))}")
    console.print(f"\n[cyan]Context:[/cyan]\n{data.get('context', '')[:2000]}")
    if data.get("citations"):
        console.print("\n[cyan]Citations:[/cyan]")
        for c in data["citations"]:
            console.print(f"  {c.get('source', '')}: {c.get('title', '')} (score: {c.get('score', 0):.3f})")


@knowledge_app.command("memory")
def knowledge_memory() -> None:
    """Show memory statistics."""
    try:
        data = _api_get("/api/v1/knowledge/memory")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[cyan]Memory Types:[/cyan] {data.get('memory_types', 0)}")
    console.print(f"[cyan]Total Records:[/cyan] {data.get('total', 0)}")
    for mt, count in data.items():
        if mt not in ("total", "memory_types"):
            console.print(f"  {mt}: {count}")


@knowledge_app.command("graph")
def knowledge_graph() -> None:
    """Show knowledge graph summary."""
    try:
        data = _api_get("/api/v1/knowledge/graph")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[cyan]Graph:[/cyan] {data.get('node_count', 0)} nodes, {data.get('edge_count', 0)} edges")


@knowledge_app.command("stats")
def knowledge_stats() -> None:
    """Show knowledge platform statistics."""
    try:
        data = _api_get("/api/v1/knowledge/statistics")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(Panel.fit(
        f"[cyan]Entries:[/cyan]      {data.get('entries', 0)}\n"
        f"[cyan]Versions:[/cyan]     {data.get('versions', 0)}\n"
        f"[cyan]Collections:[/cyan]  {data.get('collections', 0)}\n"
        f"[cyan]Workspaces:[/cyan]   {data.get('workspaces', 0)}\n"
        f"[cyan]Graph nodes:[/cyan]  {data.get('graph_nodes', 0)}\n"
        f"[cyan]Graph edges:[/cyan]  {data.get('graph_edges', 0)}\n"
        f"[cyan]Memory total:[/cyan] {data.get('memory', {}).get('total', 0)}",
        title="Knowledge Platform Statistics",
    ))


# ---------------------------------------------------------------------------
# Engineering Intelligence — Phase 25 CLI Integration
# ---------------------------------------------------------------------------

engineering_app = typer.Typer(help="Engineering Intelligence — review, metrics, architecture, repository, release, health, documentation, dependencies, planning.")
app.add_typer(engineering_app, name="engineering")

architecture_app = typer.Typer(help="Architecture analysis and recommendations.")
app.add_typer(architecture_app, name="architecture")

review_app = typer.Typer(help="Engineering reviews — 12 review types.")
app.add_typer(review_app, name="review")

metrics_app = typer.Typer(help="Engineering metrics — complexity, debt, coverage.")
app.add_typer(metrics_app, name="metrics")

repository_app = typer.Typer(help="Repository intelligence and evolution.")
app.add_typer(repository_app, name="repository")

release_app = typer.Typer(help="Release readiness and certification.")
app.add_typer(release_app, name="release")

health_app = typer.Typer(help="Repository health center.")
app.add_typer(health_app, name="health")

documentation_app = typer.Typer(help="Documentation intelligence.")
app.add_typer(documentation_app, name="documentation")

dependencies_app = typer.Typer(help="Dependency review.")
app.add_typer(dependencies_app, name="dependencies")

planning_app = typer.Typer(help="Engineering planning — WBS, roadmaps, dependencies.")
app.add_typer(planning_app, name="planning")


def _emit(data: Any, fmt: str) -> None:
    """Render ``data`` in the requested format (json/yaml/markdown/table)."""
    import json as _json
    if fmt == "json":
        console.print_json(_json.dumps(data, default=str))
        return
    if fmt == "yaml":
        try:
            import yaml
            console.print(yaml.safe_dump(data, default_flow_style=False, sort_keys=False))
        except ImportError:
            console.print_json(_json.dumps(data, default=str))
        return
    if fmt == "markdown":
        if isinstance(data, dict):
            for k, v in data.items():
                console.print(f"**{k}:** {v}")
        elif isinstance(data, list):
            for item in data:
                console.print(f"- {item}")
        else:
            console.print(str(data))
        return
    # Default table format
    if isinstance(data, dict):
        for k, v in data.items():
            console.print(f"[cyan]{k}:[/cyan] {v}")
    elif isinstance(data, list):
        for item in data:
            console.print(f"- {item}")
    else:
        console.print(str(data))


@engineering_app.command("overview")
def engineering_overview(
    fmt: str = typer.Option("table", "--format", "-f", help="Output format: table|json|yaml|markdown"),
) -> None:
    """Show engineering overview."""
    try:
        data = _api_get("/api/v1/engineering/overview")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@engineering_app.command("agents")
def engineering_agents(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """List engineering agents."""
    try:
        data = _api_get("/api/v1/engineering/agents")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@architecture_app.command("recommendations")
def architecture_recommendations(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """List architecture recommendations."""
    try:
        data = _api_get("/api/v1/engineering/architecture/recommendations")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@review_app.command("run")
def review_run(
    review_type: str = typer.Argument(..., help="Review type: architecture|code|security|performance|dependency|documentation|testing|api|database|workflow|plugin|mission"),
    target: str = typer.Argument(".", help="Target path or mission id"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Run a single engineering review."""
    try:
        data = _api_post(
            f"/api/v1/engineering/reviews/{review_type}",
            body={"target": target},
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@review_app.command("all")
def review_all(
    target: str = typer.Argument(".", help="Target path"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Run all 12 review types against the target."""
    try:
        data = _api_post("/api/v1/engineering/reviews", body={"target": target})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@metrics_app.command("show")
def metrics_show(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show engineering metrics."""
    try:
        data = _api_get("/api/v1/engineering/metrics")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@repository_app.command("analyze")
def repository_analyze(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Analyze the repository."""
    try:
        data = _api_get("/api/v1/engineering/repository/analysis")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@repository_app.command("evolution")
def repository_evolution(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show repository evolution dashboard."""
    try:
        data = _api_get("/api/v1/engineering/repository/evolution")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@repository_app.command("timeline")
def repository_timeline(
    limit: int = typer.Option(50, "--limit"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show repository timeline."""
    try:
        data = _api_get(f"/api/v1/engineering/repository/timeline?limit={limit}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@release_app.command("readiness")
def release_readiness(
    version: str = typer.Option("", "--version", help="Version string for the release"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Evaluate release readiness."""
    try:
        data = _api_post("/api/v1/engineering/release/readiness", body={"version": version})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@release_app.command("certify")
def release_certify(
    version: str = typer.Option("", "--version"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Generate a certification report."""
    try:
        data = _api_post("/api/v1/engineering/release/certification", body={"version": version})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@health_app.command("show")
def health_show(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show repository health report."""
    try:
        data = _api_get("/api/v1/engineering/health")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@documentation_app.command("analyze")
def documentation_analyze(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Analyze documentation."""
    try:
        data = _api_get("/api/v1/engineering/documentation/analysis")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@documentation_app.command("recommendations")
def documentation_recommendations(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show documentation recommendations."""
    try:
        data = _api_get("/api/v1/engineering/documentation/recommendations")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@dependencies_app.command("review")
def dependencies_review(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Run a dependency review."""
    try:
        data = _api_post("/api/v1/engineering/reviews/dependency", body={"target": "."})
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@planning_app.command("create")
def planning_create(
    title: str = typer.Option("", "--title"),
    description: str = typer.Option("", "--description"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Create an engineering plan."""
    try:
        data = _api_post(
            "/api/v1/engineering/planning/create",
            body={"title": title, "description": description},
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@planning_app.command("impact")
def planning_impact(
    target: str = typer.Argument(..., help="Target file or module to analyze impact for"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Analyze the impact of a change to ``target``."""
    try:
        data = _api_post(
            "/api/v1/engineering/planning/impact",
            body={"target": target},
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@engineering_app.command("test-intelligence")
def engineering_test_intelligence(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show test intelligence analysis."""
    try:
        data = _api_get("/api/v1/engineering/test-intelligence/analysis")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@engineering_app.command("productivity")
def engineering_productivity(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show developer productivity dashboard."""
    try:
        data = _api_get("/api/v1/engineering/productivity/dashboard")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


# ---------------------------------------------------------------------------
# Research Platform — v5.3 CLI Integration
# ---------------------------------------------------------------------------

research_app = typer.Typer(help="Enterprise Research & Reasoning Platform — projects, sessions, agents, reasoning, evidence, verification, synthesis.")
app.add_typer(research_app, name="research")


@research_app.command("overview")
def research_overview(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show research platform overview."""
    try:
        data = _api_get("/api/v1/research/overview")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@research_app.command("projects")
def research_projects(
    status: str = typer.Option("", "--status", help="Filter by status"),
    domain: str = typer.Option("", "--domain", help="Filter by domain"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """List research projects."""
    params = []
    if status:
        params.append(f"status={status}")
    if domain:
        params.append(f"domain={domain}")
    qs = "?" + "&".join(params) if params else ""
    try:
        data = _api_get(f"/api/v1/research/projects{qs}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@research_app.command("create-project")
def research_create_project(
    title: str = typer.Option(..., "--title"),
    description: str = typer.Option("", "--description"),
    domain: str = typer.Option("", "--domain"),
    owner: str = typer.Option("", "--owner"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Create a new research project."""
    try:
        data = _api_post(
            "/api/v1/research/projects",
            body={"title": title, "description": description, "domain": domain, "owner": owner},
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@research_app.command("agents")
def research_agents(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """List the 10 specialized research agents."""
    try:
        data = _api_get("/api/v1/research/agents")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@research_app.command("research")
def research_run(
    agent_type: str = typer.Argument(..., help="Agent type: literature|scientific|legal|business|technology|market|news|financial|policy|open_data"),
    query: str = typer.Argument(..., help="Research query"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Run research with a specific agent."""
    try:
        data = _api_post(
            f"/api/v1/research/agents/{agent_type}/research",
            body={"query": query},
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@research_app.command("reason")
def research_reason(
    question: str = typer.Argument(..., help="Question for multi-model reasoning"),
    models: str = typer.Option("", "--models", help="Comma-separated list of models (placeholder)"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Run multi-model reasoning on a question."""
    try:
        data = _api_post(
            "/api/v1/research/reasoning",
            body={"question": question, "models": models.split(",") if models else []},
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@research_app.command("evidence")
def research_evidence(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show evidence graph statistics."""
    try:
        data = _api_get("/api/v1/research/evidence-graph")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@research_app.command("verify")
def research_verify(
    fact: str = typer.Argument(..., help="Fact to verify"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Verify a fact (no sources = unverifiable)."""
    try:
        data = _api_post(
            "/api/v1/research/verification",
            body={"fact_text": fact, "sources": []},
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@research_app.command("synthesize")
def research_synthesize(
    title: str = typer.Option("Synthesis", "--title"),
    project_id: str = typer.Option("cli", "--project-id"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Synthesize knowledge (empty corpus = low-confidence placeholder)."""
    try:
        data = _api_post(
            "/api/v1/research/synthesis",
            body={"project_id": project_id, "title": title, "documents": []},
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@research_app.command("timeline")
def research_timeline(
    project_id: str = typer.Option("", "--project-id"),
    limit: int = typer.Option(50, "--limit"),
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show research timeline."""
    qs = f"?limit={limit}" + (f"&project_id={project_id}" if project_id else "")
    try:
        data = _api_get(f"/api/v1/research/timeline{qs}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


@research_app.command("stats")
def research_stats(
    fmt: str = typer.Option("table", "--format", "-f"),
) -> None:
    """Show research engine statistics."""
    try:
        data = _api_get("/api/v1/research/stats")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    _emit(data, fmt)


# ---------------------------------------------------------------------------
# Installer — v5.3.2 CLI Integration
# ---------------------------------------------------------------------------

install_app = typer.Typer(help="AAiOS Installer — install, repair, upgrade, validate.")
app.add_typer(install_app, name="install")


def _run_install(mode: str, workspace: str, profile: str, force: bool) -> None:
    """Run the installer in the given mode."""
    import asyncio

    from services.installer import InstallationMode, InstallerOrchestrator
    orchestrator = InstallerOrchestrator(workspace_root=workspace)
    try:
        report = asyncio.run(orchestrator.install(
            mode=InstallationMode(mode),
            workspace_root=workspace,
            profile=profile if profile else None,
            force=force,
        ))
    except Exception as e:
        console.print(f"[red]Installation failed:[/red] {e}")
        raise typer.Exit(1) from e
    # Print summary
    console.print(Panel.fit(
        f"[cyan]Mode:[/cyan]           {report.mode}\n"
        f"[cyan]Status:[/cyan]         {report.overall_status}\n"
        f"[cyan]Workspace:[/cyan]      {report.plan.workspace_root if report.plan else '-'}\n"
        f"[cyan]Restore point:[/cyan]  {report.restore_point_path or '-'}\n"
        f"[cyan]Errors:[/cyan]         {len(report.errors)}\n"
        f"[cyan]Warnings:[/cyan]       {len(report.warnings)}\n"
        f"[cyan]Dependencies:[/cyan]   {len(report.dependencies)} checked\n"
        f"[cyan]Databases:[/cyan]      {len(report.databases)} bootstrapped\n"
        f"[cyan]Providers:[/cyan]      {len(report.providers)} checked\n"
        f"[cyan]Agents registered:[/cyan] {len(report.agents_registered)}\n"
        f"[cyan]Log:[/cyan]            {report.log_path or '-'}",
        title="AAiOS Installation Report",
    ))
    if report.errors:
        console.print("\n[red]Errors:[/red]")
        for err in report.errors:
            console.print(f"  - {err}")
    if report.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in report.warnings:
            console.print(f"  - {w}")
    if report.log_path:
        console.print(f"\n[cyan]Full report:[/cyan] {report.log_path}")
    if report.overall_status != "success":
        raise typer.Exit(1)


@install_app.callback(invoke_without_command=True)
def install(
    ctx: typer.Context,
    mode: str = typer.Option(
        "interactive", "--mode", "-m",
        help="Installation mode: interactive|silent|minimal|developer|enterprise|portable|offline|repair|force|upgrade|validate",
    ),
    workspace: str = typer.Option("", "--workspace", "-w", help="Workspace root path"),
    profile: str = typer.Option("", "--profile", help="Configuration profile"),
    force: bool = typer.Option(False, "--force", help="Force installation past compatibility blockers"),
    interactive: bool = typer.Option(False, "--interactive", help="Shortcut for --mode=interactive"),
    silent: bool = typer.Option(False, "--silent", help="Shortcut for --mode=silent"),
    minimal: bool = typer.Option(False, "--minimal", help="Shortcut for --mode=minimal"),
    developer: bool = typer.Option(False, "--developer", help="Shortcut for --mode=developer"),
    enterprise: bool = typer.Option(False, "--enterprise", help="Shortcut for --mode=enterprise"),
    portable: bool = typer.Option(False, "--portable", help="Shortcut for --mode=portable"),
    offline: bool = typer.Option(False, "--offline", help="Shortcut for --mode=offline"),
    repair: bool = typer.Option(False, "--repair", help="Shortcut for --mode=repair"),
    upgrade: bool = typer.Option(False, "--upgrade", help="Shortcut for --mode=upgrade"),
    validate: bool = typer.Option(False, "--validate", help="Shortcut for --mode=validate"),
) -> None:
    """Install AAiOS. Without a sub-command, runs in the chosen mode."""
    if ctx.invoked_subcommand is not None:
        return
    # Resolve mode from shortcut flags
    selected_mode = mode
    for flag, m in (
        (interactive, "interactive"), (silent, "silent"), (minimal, "minimal"),
        (developer, "developer"), (enterprise, "enterprise"), (portable, "portable"),
        (offline, "offline"), (repair, "repair"), (upgrade, "upgrade"),
        (validate, "validate"),
    ):
        if flag:
            selected_mode = m
            break
    _run_install(selected_mode, workspace, profile, force or repair)


@install_app.command("interactive")
def install_interactive(
    workspace: str = typer.Option("", "--workspace", "-w"),
) -> None:
    """Install AAiOS interactively."""
    _run_install("interactive", workspace, "", False)


@install_app.command("silent")
def install_silent(
    workspace: str = typer.Option("", "--workspace", "-w"),
    profile: str = typer.Option("production", "--profile"),
) -> None:
    """Install AAiOS silently (no prompts)."""
    _run_install("silent", workspace, profile, False)


@install_app.command("minimal")
def install_minimal(
    workspace: str = typer.Option("", "--workspace", "-w"),
) -> None:
    """Install AAiOS with minimal features."""
    _run_install("minimal", workspace, "", False)


@install_app.command("developer")
def install_developer(
    workspace: str = typer.Option("", "--workspace", "-w"),
) -> None:
    """Install AAiOS for development."""
    _run_install("developer", workspace, "", False)


@install_app.command("enterprise")
def install_enterprise(
    workspace: str = typer.Option("", "--workspace", "-w"),
) -> None:
    """Install AAiOS for enterprise production."""
    _run_install("enterprise", workspace, "", False)


@install_app.command("portable")
def install_portable(
    workspace: str = typer.Option("", "--workspace", "-w"),
) -> None:
    """Install AAiOS as a portable application."""
    _run_install("portable", workspace or "./aaios-portable", "", False)


@install_app.command("offline")
def install_offline(
    workspace: str = typer.Option("", "--workspace", "-w"),
) -> None:
    """Install AAiOS in offline mode (no network)."""
    _run_install("offline", workspace, "", False)


@install_app.command("repair")
def install_repair(
    workspace: str = typer.Option("", "--workspace", "-w"),
) -> None:
    """Repair an existing AAiOS installation."""
    _run_install("repair", workspace, "", True)


@install_app.command("force")
def install_force(
    workspace: str = typer.Option("", "--workspace", "-w"),
) -> None:
    """Force installation past compatibility blockers."""
    _run_install("force", workspace, "", True)


@install_app.command("upgrade")
def install_upgrade(
    workspace: str = typer.Option("", "--workspace", "-w"),
) -> None:
    """Upgrade an existing AAiOS installation."""
    _run_install("upgrade", workspace, "", False)


@install_app.command("validate")
def install_validate(
    workspace: str = typer.Option("", "--workspace", "-w"),
) -> None:
    """Validate an existing AAiOS installation."""
    _run_install("validate", workspace, "", False)


if __name__ == "__main__":
    main()
