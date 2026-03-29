"""
CLI interface for Memora using Click and Rich.
Run with: python -m memora.cli
"""

import json
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from memora.memory import MemoraMemory

load_dotenv(Path(__file__).parent / ".env")

# Auto-load saved cloud config (~/.memora/config.json) into env
_config_path = Path.home() / ".memora" / "config.json"
if _config_path.exists():
    try:
        _cfg = json.loads(_config_path.read_text(encoding="utf-8"))
        for _k in ("MEMORA_API_URL", "MEMORA_API_KEY"):
            if _k in _cfg and not os.getenv(_k):
                os.environ[_k] = _cfg[_k]
    except Exception:
        pass

console = Console()


def get_memory() -> MemoraMemory:
    return MemoraMemory(
        db_path=os.getenv("MEMORA_DB_PATH"),
        api_key=os.getenv("GROQ_API_KEY"),
    )


@click.group()
@click.version_option(version="0.1.0", prog_name="memora")
def cli():
    """Memora — decision memory layer for AI agent builders."""
    pass


@cli.command()
@click.argument("summary")
@click.option("--reasoning", "-r", required=True, help="Why this decision was made")
@click.option("--type", "-T", "dtype", default="DECISION", type=click.Choice(["DECISION", "REJECTED", "NEXT", "BUG_FIXED", "CONTEXT", "ASSUMPTION", "TRADEOFF", "CONSTRAINT", "DEPENDENCY", "RISK"], case_sensitive=False), help="Memory type")
@click.option("--alternatives", "-a", multiple=True, help="Alternatives considered")
@click.option("--tags", "-t", multiple=True, help="Topic tags")
@click.option("--project", "-p", default="", help="Project name")
@click.option("--agent", default="", help="Agent identifier")
@click.option("--context", "-c", default="", help="Where this was decided")
def record(summary: str, reasoning: str, dtype: str, alternatives: tuple, tags: tuple, project: str, agent: str, context: str):
    """Record a new decision."""
    mem = get_memory()
    result = mem.record(
        summary=summary,
        reasoning=reasoning,
        alternatives=list(alternatives),
        tags=list(tags),
        context=context,
        project=project,
        agent=agent,
        source="cli",
        type=dtype.upper(),
    )
    _print_decision(result)
    console.print(f"\n[green]Decision recorded:[/green] {result['id']}")


@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=10, help="Max results")
def search(query: str, limit: int):
    """Search past decisions."""
    mem = get_memory()
    results = mem.recall(query, limit=limit)
    if not results:
        console.print("[yellow]No decisions found.[/yellow]")
        return
    _print_decision_table(results)


@cli.command("list")
@click.option("--project", "-p", default="", help="Filter by project")
@click.option("--agent", default="", help="Filter by agent")
@click.option("--tag", "-t", default="", help="Filter by tag")
@click.option("--type", "-T", "dtype", default="", help="Filter by type (DECISION, REJECTED, NEXT, BUG_FIXED, CONTEXT, ASSUMPTION, TRADEOFF, CONSTRAINT, DEPENDENCY, RISK)")
@click.option("--limit", "-l", default=20, help="Max results")
@click.option("--json-output", "--json", is_flag=True, help="Output as JSON")
def list_cmd(project: str, agent: str, tag: str, dtype: str, limit: int, json_output: bool):
    """List recorded decisions."""
    mem = get_memory()
    results = mem.list_all(project=project, agent=agent, tag=tag, type=dtype, limit=limit)
    if json_output:
        click.echo(json.dumps(results, indent=2))
        return
    if not results:
        console.print("[yellow]No decisions found.[/yellow]")
        return
    _print_decision_table(results)


@cli.command()
@click.argument("decision_id")
def show(decision_id: str):
    """Show details of a specific decision."""
    mem = get_memory()
    result = mem.get_decision(decision_id)
    if result is None:
        console.print(f"[red]Decision {decision_id} not found.[/red]")
        sys.exit(1)
    _print_decision(result)
    related = mem.get_related(decision_id)
    if related:
        console.print(f"\n[bold]Related decisions ({len(related)}):[/bold]")
        for r in related:
            console.print(f"  [{r.get('_relation', 'related')}] {r['id']}: {r['summary']}")


@cli.command()
@click.argument("decision_id")
@click.confirmation_option(prompt="Are you sure you want to delete this decision?")
def delete(decision_id: str):
    """Delete a decision."""
    mem = get_memory()
    if mem.delete_decision(decision_id):
        console.print(f"[green]Deleted {decision_id}[/green]")
    else:
        console.print(f"[red]Decision {decision_id} not found.[/red]")
        sys.exit(1)


@cli.command()
@click.argument("from_id")
@click.argument("to_id")
@click.option("--relation", "-r", default="related", help="Relationship type")
def link(from_id: str, to_id: str, relation: str):
    """Link two decisions together."""
    mem = get_memory()
    result = mem.link_decisions(from_id, to_id, relation)
    console.print(f"[green]Linked {from_id} --[{result['relation']}]--> {to_id}[/green]")


@cli.command()
@click.option("--file", "-f", "filepath", type=click.Path(exists=True), help="Read text from file")
@click.option("--project", "-p", default="", help="Project name")
@click.option("--agent", default="", help="Agent identifier")
@click.option("--context", "-c", default="", help="Source context")
def extract(filepath, project: str, agent: str, context: str):
    """Extract decisions from text using AI. Reads from stdin if no file given."""
    if filepath:
        with open(filepath) as f:
            text = f.read()
    else:
        console.print("[dim]Reading from stdin (Ctrl+D to finish)...[/dim]")
        text = sys.stdin.read()

    if not text.strip():
        console.print("[yellow]No text provided.[/yellow]")
        return

    mem = get_memory()
    console.print("[dim]Extracting decisions...[/dim]")
    results = mem.extract_and_store(text=text, context=context, project=project, agent=agent, source="cli-extract")
    if not results:
        console.print("[yellow]No decisions found in text.[/yellow]")
        return
    console.print(f"\n[green]Extracted {len(results)} decision(s):[/green]")
    _print_decision_table(results)


@cli.command()
@click.option("--project", "-p", default="", help="Scope to project")
def stats(project: str):
    """Show decision statistics."""
    mem = get_memory()
    s = mem.stats(project=project)
    console.print(Panel(f"[bold]Total decisions:[/bold] {s['total']}", title="Memora Stats"))

    if s.get("types"):
        table = Table(title="By Type")
        table.add_column("Type", style="green")
        table.add_column("Count", justify="right")
        for t, count in sorted(s["types"].items(), key=lambda x: -x[1]):
            table.add_row(t, str(count))
        console.print(table)

    if s["sources"]:
        table = Table(title="By Source")
        table.add_column("Source", style="cyan")
        table.add_column("Count", justify="right")
        for source, count in sorted(s["sources"].items(), key=lambda x: -x[1]):
            table.add_row(source, str(count))
        console.print(table)

    if s["tags"]:
        table = Table(title="Top Tags")
        table.add_column("Tag", style="magenta")
        table.add_column("Count", justify="right")
        for tag, count in sorted(s["tags"].items(), key=lambda x: -x[1])[:15]:
            table.add_row(tag, str(count))
        console.print(table)


@cli.command()
def serve():
    """Start the MCP server."""
    from memora.server import main as server_main
    server_main()


@cli.command()
def web():
    """Start the web dashboard."""
    from memora.app import main as app_main
    app_main()


@cli.command()
@click.option("--port", "-p", default=8377, help="Port number")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
def dashboard(port: int, no_browser: bool):
    """Launch the Memora dashboard in your browser."""
    import webbrowser
    import threading
    from memora.app import app

    url = f"http://127.0.0.1:{port}/dashboard"
    if not no_browser:
        threading.Timer(1.0, webbrowser.open, args=[url]).start()
    console.print(f"[green]Memora dashboard starting at {url}[/green]")
    app.run(host="127.0.0.1", port=port)


@cli.command()
def login():
    """Configure Memora cloud mode (saves API URL and key to ~/.memora/config.json)."""
    api_url = click.prompt("Memora API URL", default=os.getenv("MEMORA_API_URL", ""))
    api_key = click.prompt("Memora API Key", default="", hide_input=True)

    config = {}
    config_path = Path.home() / ".memora" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Preserve existing config keys
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    if api_url:
        config["MEMORA_API_URL"] = api_url.rstrip("/")
    if api_key:
        config["MEMORA_API_KEY"] = api_key

    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    console.print(f"[green]Config saved to {config_path}[/green]")

    # Show which mode is now active
    if config.get("MEMORA_API_URL"):
        console.print(f"[cyan]Cloud mode:[/cyan] {config['MEMORA_API_URL']}")
    else:
        console.print("[cyan]Local mode:[/cyan] SQLite (default)")


@cli.command()
def logout():
    """Remove saved cloud config and revert to local mode."""
    config_path = Path.home() / ".memora" / "config.json"
    if config_path.exists():
        config_path.unlink()
        # Clear env vars for this session
        os.environ.pop("MEMORA_API_URL", None)
        os.environ.pop("MEMORA_API_KEY", None)
        console.print("[green]Logged out. Memora is now in local mode.[/green]")
    else:
        console.print("[yellow]No cloud config found — already in local mode.[/yellow]")


@cli.command()
def mode():
    """Show current Memora backend mode and workspace."""
    from memora.memory_backend import get_store

    api_url = os.getenv("MEMORA_API_URL")
    cloud_mode = os.getenv("MEMORA_CLOUD_MODE", "").lower() in ("true", "1", "yes")

    lines = Text()
    if api_url:
        lines.append("Backend:   ", style="dim")
        lines.append("CLOUD (RemoteStore)\n", style="bold cyan")
        lines.append("Endpoint:  ", style="dim")
        lines.append(f"{api_url}\n", style="cyan")
        lines.append("Workspace: ", style="dim")
        lines.append("remote\n", style="cyan")
        auth = "configured" if os.getenv("MEMORA_API_KEY") else "none"
        lines.append("Auth:      ", style="dim")
        lines.append(f"{auth}\n", style="green" if auth == "configured" else "yellow")
    elif cloud_mode:
        lines.append("Backend:   ", style="dim")
        lines.append("CLOUD (TursoStore)\n", style="bold cyan")
        turso_url = os.getenv("TURSO_DATABASE_URL", "not set")
        lines.append("Database:  ", style="dim")
        lines.append(f"{turso_url}\n", style="cyan")
        lines.append("Workspace: ", style="dim")
        lines.append("cloud\n", style="cyan")
    else:
        db_path = os.getenv("MEMORA_DB_PATH", str(Path.home() / ".memora" / "decisions.db"))
        lines.append("Backend:   ", style="dim")
        lines.append("LOCAL (SQLite)\n", style="bold green")
        lines.append("Database:  ", style="dim")
        lines.append(f"{db_path}\n", style="green")
        lines.append("Workspace: ", style="dim")
        lines.append("local\n", style="green")

    # Show decision count
    try:
        store = get_store()
        s = store.stats()
        lines.append("Decisions: ", style="dim")
        lines.append(str(s.get("total", 0)), style="bold")
    except Exception:
        pass

    console.print(Panel(lines, title="Memora Status", border_style="blue"))


@cli.command()
def doctor():
    """Run diagnostics on the Memora installation."""
    from memora.memory_backend import get_store

    console.print(Panel("[bold]Memora Doctor Report[/bold]", border_style="blue"))
    checks = []

    # 1. Backend
    api_url = os.getenv("MEMORA_API_URL")
    cloud_mode = os.getenv("MEMORA_CLOUD_MODE", "").lower() in ("true", "1", "yes")
    if api_url:
        backend_name = "RemoteStore"
    elif cloud_mode:
        backend_name = "TursoStore"
    else:
        backend_name = "LocalStore"
    checks.append(("Backend", backend_name, "green"))

    # 2. Store reachability
    try:
        store = get_store()
        store.stats()
        if api_url:
            checks.append(("API", "reachable", "green"))
        else:
            checks.append(("Database", "accessible", "green"))
    except Exception as e:
        label = "API" if api_url else "Database"
        checks.append((label, f"error: {e}", "red"))

    # 3. Workspace
    try:
        s = store.stats()
        total = s.get("total", 0)
        checks.append(("Workspace", f"active ({total} decisions)", "green"))
    except Exception:
        checks.append(("Workspace", "unknown", "yellow"))

    # 4. Extractor (Groq API key)
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        checks.append(("Extractor", "configured (Groq)", "green"))
    else:
        checks.append(("Extractor", "not configured (set GROQ_API_KEY)", "yellow"))

    # 5. Dashboard
    try:
        dashboard_dir = Path(__file__).parent / "dashboard" / "index.html"
        if dashboard_dir.exists():
            checks.append(("Dashboard", "available", "green"))
        else:
            checks.append(("Dashboard", "missing files", "red"))
    except Exception:
        checks.append(("Dashboard", "error", "red"))

    # 6. MCP tools
    try:
        import importlib
        importlib.import_module("fastmcp")
        checks.append(("MCP tools", "available", "green"))
    except ImportError:
        checks.append(("MCP tools", "not installed (pip install memora[mcp])", "yellow"))

    # 7. Config file
    config_path = Path.home() / ".memora" / "config.json"
    if config_path.exists():
        checks.append(("Config", str(config_path), "green"))
    else:
        checks.append(("Config", "none (using defaults)", "dim"))

    # Render
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Component", style="bold", width=14)
    table.add_column("Status")
    for name, status, style in checks:
        table.add_row(name, Text(status, style=style))
    console.print(table)

    # Summary
    errors = sum(1 for _, _, s in checks if s == "red")
    warns = sum(1 for _, _, s in checks if s == "yellow")
    if errors:
        console.print(f"\n[red]{errors} error(s) found. Fix them to use Memora fully.[/red]")
    elif warns:
        console.print(f"\n[green]Memora is operational.[/green] [yellow]{warns} optional component(s) not configured.[/yellow]")
    else:
        console.print("\n[green]All systems operational.[/green]")


@cli.command()
@click.option("--cleanup", is_flag=True, help="Remove demo data after display")
def demo(cleanup: bool):
    """Run an interactive Memora demo with sample decisions."""
    import time

    console.print(Panel("[bold]Memora Interactive Demo[/bold]\nDecision memory layer for AI agent builders", border_style="green"))
    console.print()

    mem = get_memory()
    demo_ids = []

    # --- Phase 1: Record sample decisions ---
    console.print("[bold cyan]Phase 1:[/bold cyan] Recording decisions...\n")
    time.sleep(0.3)

    samples = [
        {
            "summary": "Use PostgreSQL instead of MongoDB",
            "reasoning": "Need JSONB support for flexible schema with SQL query power. MongoDB lacks transactional guarantees we need for billing.",
            "alternatives": ["MongoDB", "DynamoDB", "CockroachDB"],
            "tags": ["database", "infrastructure"],
            "project": "memora-demo",
            "agent": "backend-architect",
            "type": "DECISION",
        },
        {
            "summary": "Rejected GraphQL in favor of REST",
            "reasoning": "Team has deep REST expertise. GraphQL adds complexity without clear benefit for our simple CRUD API surface.",
            "alternatives": ["GraphQL", "gRPC"],
            "tags": ["api", "architecture"],
            "project": "memora-demo",
            "agent": "tech-lead",
            "type": "REJECTED",
        },
        {
            "summary": "Switch from JWT to session tokens",
            "reasoning": "JWT revocation is complex and error-prone. Session tokens with Redis give us instant logout and better security posture.",
            "alternatives": ["JWT with blacklist", "JWT with short expiry"],
            "tags": ["auth", "security"],
            "project": "memora-demo",
            "agent": "security-engineer",
            "type": "DECISION",
        },
        {
            "summary": "Fixed N+1 query in dashboard endpoint",
            "reasoning": "Dashboard load time was 4.2s due to N+1 queries on user.projects. Added eager loading, reduced to 180ms.",
            "alternatives": ["Caching layer", "Denormalized table"],
            "tags": ["performance", "bugfix"],
            "project": "memora-demo",
            "agent": "backend-dev",
            "type": "BUG_FIXED",
        },
        {
            "summary": "Migrate to Turso for edge-compatible SQLite",
            "reasoning": "Vercel serverless functions lose SQLite data between invocations. Turso provides persistent, edge-replicated libSQL.",
            "alternatives": ["PlanetScale", "Neon Postgres", "Supabase"],
            "tags": ["database", "deployment", "edge"],
            "project": "memora-demo",
            "agent": "platform-engineer",
            "type": "NEXT",
        },
        {
            "summary": "Rate limiting assumes single-region deployment",
            "reasoning": "Current token bucket is in-process memory. Will break under multi-region. Acceptable for MVP, must fix before scaling.",
            "alternatives": [],
            "tags": ["scaling", "risk"],
            "project": "memora-demo",
            "agent": "tech-lead",
            "type": "ASSUMPTION",
        },
        {
            "summary": "Chose speed over durability for event queue",
            "reasoning": "Redis Streams chosen over Kafka. Simpler ops, lower latency, but risk of data loss on crash. Acceptable for non-critical events.",
            "alternatives": ["Kafka", "RabbitMQ", "SQS"],
            "tags": ["messaging", "tradeoff"],
            "project": "memora-demo",
            "agent": "backend-architect",
            "type": "TRADEOFF",
        },
    ]

    for sample in samples:
        result = mem.record(
            summary=sample["summary"],
            reasoning=sample["reasoning"],
            alternatives=sample["alternatives"],
            tags=sample["tags"],
            project=sample["project"],
            agent=sample["agent"],
            source="demo",
            type=sample["type"],
        )
        demo_ids.append(result["id"])
        style = _TYPE_STYLES.get(sample["type"], "white")
        console.print(f"  [{style}]{sample['type']:12s}[/{style}]  {sample['summary']}")
        time.sleep(0.15)

    console.print(f"\n  [green]Recorded {len(samples)} decisions.[/green]\n")

    # --- Phase 2: Link related decisions ---
    console.print("[bold cyan]Phase 2:[/bold cyan] Linking related decisions...\n")
    time.sleep(0.3)

    if len(demo_ids) >= 5:
        mem.link_decisions(demo_ids[0], demo_ids[4], "leads_to")
        console.print(f"  {demo_ids[0]} --[leads_to]--> {demo_ids[4]}")
        console.print(f"  PostgreSQL decision leads to Turso migration plan\n")

    # --- Phase 3: Search / recall ---
    console.print("[bold cyan]Phase 3:[/bold cyan] Querying decision memory...\n")
    time.sleep(0.3)

    for query in ["database infrastructure", "security auth"]:
        results = mem.recall(query, limit=3)
        console.print(f'  [bold]Search:[/bold] "{query}"')
        if results:
            for r in results:
                style = _TYPE_STYLES.get(r.get("type", "DECISION"), "white")
                console.print(f"    [{style}]{r.get('type', '?'):12s}[/{style}] {r['summary'][:55]}")
        else:
            console.print("    [dim]No results[/dim]")
        console.print()

    # --- Phase 4: Stats ---
    console.print("[bold cyan]Phase 4:[/bold cyan] Decision statistics\n")
    time.sleep(0.3)

    s = mem.stats(project="memora-demo")
    table = Table(title="memora-demo stats", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Total decisions", str(s["total"]))
    if s.get("types"):
        for t, c in sorted(s["types"].items()):
            table.add_row(f"  {t}", str(c))
    console.print(table)
    console.print()

    # --- Phase 5: Dashboard prompt ---
    console.print("[bold cyan]Phase 5:[/bold cyan] Dashboard\n")
    console.print("  Run [bold]memora dashboard[/bold] to visualize these decisions in your browser.")
    console.print("  Run [bold]memora doctor[/bold] to check your installation health.")
    console.print()

    # --- Cleanup ---
    if cleanup:
        console.print("[dim]Cleaning up demo data...[/dim]")
        for did in demo_ids:
            mem.delete_decision(did)
        console.print(f"[dim]Removed {len(demo_ids)} demo decisions.[/dim]\n")
    else:
        console.print("[dim]Demo data kept. Run [bold]memora demo --cleanup[/bold] or delete project 'memora-demo' manually.[/dim]\n")

    console.print(Panel("[bold green]Demo complete![/bold green] Memora captures the WHY behind every decision.", border_style="green"))


_TYPE_STYLES = {
    "DECISION": "green",
    "REJECTED": "red",
    "NEXT": "yellow",
    "BUG_FIXED": "blue",
    "CONTEXT": "cyan",
    "ASSUMPTION": "bright_yellow",
    "TRADEOFF": "magenta",
    "CONSTRAINT": "bright_red",
    "DEPENDENCY": "bright_blue",
    "RISK": "bright_red",
}


def _print_decision(d: dict):
    dtype = d.get("type", "DECISION")
    type_style = _TYPE_STYLES.get(dtype, "white")
    tags_str = ", ".join(d.get("tags", []))
    alts_str = "\n".join(f"  - {a}" for a in d.get("alternatives", []))

    content = Text()
    content.append(f"ID: {d['id']}\n", style="dim")
    content.append(f"Type: {dtype}\n", style=type_style)
    content.append(f"Summary: {d['summary']}\n", style="bold")
    content.append(f"Reasoning: {d['reasoning']}\n")
    if alts_str:
        content.append(f"Alternatives:\n{alts_str}\n")
    if tags_str:
        content.append(f"Tags: {tags_str}\n", style="magenta")
    if d.get("project"):
        content.append(f"Project: {d['project']}\n", style="cyan")
    if d.get("agent"):
        content.append(f"Agent: {d['agent']}\n", style="cyan")
    content.append(f"Source: {d.get('source', '?')}  ", style="dim")
    content.append(f"Confidence: {d.get('confidence', '?')}  ", style="dim")
    content.append(f"Created: {d.get('created_at', '?')}", style="dim")

    console.print(Panel(content, title=f"{dtype} Memory", border_style=type_style))


def _print_decision_table(decisions: list[dict]):
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=14)
    table.add_column("Type", width=12)
    table.add_column("Summary", min_width=30)
    table.add_column("Tags", style="magenta", width=20)
    table.add_column("Project", style="cyan", width=15)
    table.add_column("Source", style="dim", width=12)
    table.add_column("Date", style="dim", width=12)
    for d in decisions:
        dtype = d.get("type", "DECISION")
        type_style = _TYPE_STYLES.get(dtype, "white")
        tags = ", ".join(d.get("tags", [])[:3])
        date = d.get("created_at", "")[:10]
        type_text = Text(dtype, style=type_style)
        table.add_row(d["id"], type_text, d["summary"][:60], tags, d.get("project", ""), d.get("source", ""), date)
    console.print(table)


def main():
    cli()


if __name__ == "__main__":
    main()
