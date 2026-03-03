import argparse
import sys
from datetime import date
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from digest.analyzer import Analyzer
from digest.collectors import (
    AntigravityCollector,
    ClaudeCodeCollector,
    CodexCollector,
    GeminiCliCollector,
    OpenCodeCollector,
)
from digest.config import load_config
from digest.models import NormalizedSession

console = Console()

def gather_sessions(target_date: date) -> List[NormalizedSession]:
    collectors = [
        ClaudeCodeCollector(),
        CodexCollector(),
        AntigravityCollector(),
        OpenCodeCollector(),
        GeminiCliCollector(),
    ]

    all_sessions = []
    with console.status("[bold green]Harvesting data from local directories...") as status:
        for collector in collectors:
            status.update(f"[bold green]Harvesting from {collector.source_name}...")
            try:
                sessions = collector.collect(target_date)
                if sessions:
                    all_sessions.extend(sessions)
                    console.print(f"[green]✓[/] {collector.source_name}: found {len(sessions)} sessions")
                else:
                    console.print(f"[dim]~[/] {collector.source_name}: no sessions found")
            except Exception as e:
                console.print(f"[red]✗[/] {collector.source_name}: error parsing ({e})")
    
    all_sessions.sort(key=lambda s: s.start_time)
    return all_sessions

def cmd_collect(args):
    try:
        target_date = date.fromisoformat(args.date)
    except ValueError:
        console.print("[red]Invalid date format. Use YYYY-MM-DD[/]")
        sys.exit(1)

    console.print(Panel(f"[bold blue]Digesting AI Agent Activities for {target_date.isoformat()}[/]"))
    
    sessions = gather_sessions(target_date)

    if not sessions:
        console.print(f"\n[yellow]No activities found for {target_date.isoformat()}[/]")
        sys.exit(0)

    console.print("\n[bold]Activity Timeline[/]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Time")
    table.add_column("Source")
    table.add_column("Project")
    table.add_column("Title / First Prompt", overflow="fold")
    table.add_column("Msgs", justify="right")

    source_colors = {
        "Claude Code": "cyan",
        "Codex": "blue",
        "Antigravity": "magenta",
        "OpenCode": "green",
        "Gemini CLI": "yellow",
    }

    for s in sessions:
        time_str = s.start_time.strftime("%H:%M")
        color = source_colors.get(s.source, "white")
        title = s.title_or_prompt.replace("\n", " ").strip()
        if len(title) > 80:
            title = title[:77] + "..."
            
        table.add_row(
            time_str,
            f"[{color}]{s.source}[/]",
            s.project_path or "-",
            title,
            str(s.message_count)
        )

    console.print(table)
    console.print(f"\n[bold]Total Sessions:[/] {len(sessions)}")

def cmd_analyze(args):
    try:
        target_date = date.fromisoformat(args.date)
    except ValueError:
        console.print("[red]Invalid date format. Use YYYY-MM-DD[/]")
        sys.exit(1)

    try:
        config = load_config()
    except Exception as e:
        console.print(f"[red]Configuration Error: {e}[/]")
        sys.exit(1)

    console.print(Panel(f"[bold blue]Analyzing AI Agent Activities for {target_date.isoformat()}[/]"))
    
    sessions = gather_sessions(target_date)
    if not sessions:
        console.print(f"\n[yellow]No activities found for {target_date.isoformat()}, nothing to analyze.[/]")
        sys.exit(0)

    console.print("\n[bold cyan]Engaging LLM Analyzer...[/]")
    analyzer = Analyzer(config)
    
    with console.status(f"[bold cyan]Sending {len(sessions)} records to {config.ai.provider}/{config.ai.model}..."):
        try:
            summary = analyzer.analyze(target_date, sessions)
        except Exception as e:
            console.print(f"[red]Error during LLM Analysis: {e}[/]")
            sys.exit(1)

    if not summary:
        console.print("[red]Failed to generate summary.[/]")
        sys.exit(1)

    # Output JSON representation nicely
    console.print("\n[bold magenta]🚀 Daily Summary Report[/]")
    console.print(Panel("\n".join(f"• {h}" for h in summary.highlights), title="Highlights", border_style="yellow"))
    
    for act in summary.activities:
        act_table = Table(show_header=False, show_edge=False, box=None)
        act_table.add_column("Field", style="dim", width=10)
        act_table.add_column("Value")
        
        act_table.add_row("Time", act.time_range)
        act_table.add_row("Project", f"[bold]{act.project}[/]")
        act_table.add_row("Category", f"[cyan]{act.category}[/]")
        act_table.add_row("Summary", act.summary)
        
        details_str = "\n".join(f"  - {d}" for d in act.details)
        act_table.add_row("Details", details_str)
        
        console.print(Panel(act_table, title=f"Activity", expand=False))


def main():
    parser = argparse.ArgumentParser(description="AI Agent Daily Data Collector & Analyzer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Collect Command
    parser_collect = subparsers.add_parser("collect", help="Harvest local logs and display table")
    parser_collect.add_argument(
        "--date", 
        type=str, 
        help="Target date (YYYY-MM-DD). Defaults to today.", 
        default=date.today().isoformat()
    )
    
    # Analyze Command
    parser_analyze = subparsers.add_parser("analyze", help="Harvest logs and generate LLM summary")
    parser_analyze.add_argument(
        "--date", 
        type=str, 
        help="Target date (YYYY-MM-DD). Defaults to today.", 
        default=date.today().isoformat()
    )

    args = parser.parse_args()

    if args.command == "collect":
        cmd_collect(args)
    elif args.command == "analyze":
        cmd_analyze(args)

if __name__ == "__main__":
    main()
