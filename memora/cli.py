"""
CLI interface for Memora using Click and Rich.
Run with: python -m memora.cli
"""

import json
import os
import sys

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from memora.memory import MemoraMemory

load_dotenv()
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
@click.option("--type", "-T", "dtype", default="DECISION", type=click.Choice(["DECISION", "REJECTED", "NEXT", "BUG_FIXED", "CONTEXT"], case_sensitive=False), help="Memory type")
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
@click.option("--type", "-T", "dtype", default="", help="Filter by type (DECISION, REJECTED, NEXT, BUG_FIXED, CONTEXT)")
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


_TYPE_STYLES = {
    "DECISION": "green",
    "REJECTED": "red",
    "NEXT": "yellow",
    "BUG_FIXED": "blue",
    "CONTEXT": "cyan",
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
