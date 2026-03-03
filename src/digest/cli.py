import argparse
import sys
from datetime import date
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from digest.collectors import (
    ClaudeCodeCollector,
    CodexCollector,
    AntigravityCollector,
    OpenCodeCollector,
    GeminiCliCollector,
)

console = Console()

def main():
    parser = argparse.ArgumentParser(description="AI Agent Daily Data Collector")
    parser.add_argument(
        "--date", 
        type=str, 
        help="Target date (YYYY-MM-DD). Defaults to today.", 
        default=date.today().isoformat()
    )
    args = parser.parse_args()

    try:
        target_date = date.fromisoformat(args.date)
    except ValueError:
        console.print("[red]Invalid date format. Use YYYY-MM-DD[/]")
        sys.exit(1)

    console.print(Panel(f"[bold blue]Digesting AI Agent Activities for {target_date.isoformat()}[/]"))

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

    if not all_sessions:
        console.print(f"\n[yellow]No activities found for {target_date.isoformat()}[/]")
        sys.exit(0)

    # Sort all sessions chronologically
    all_sessions.sort(key=lambda s: s.start_time)

    # Output tabular results
    console.print("\n[bold]Activity Timeline[/]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Time")
    table.add_column("Source")
    table.add_column("Project")
    table.add_column("Title / First Prompt", overflow="fold")
    table.add_column("Msgs", justify="right")

    # Mapping sources to colors
    source_colors = {
        "Claude Code": "cyan",
        "Codex": "blue",
        "Antigravity": "magenta",
        "OpenCode": "green",
        "Gemini CLI": "yellow",
    }

    for s in all_sessions:
        time_str = s.start_time.strftime("%H:%M")
        color = source_colors.get(s.source, "white")
        
        # Clean up title
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
    console.print(f"\n[bold]Total Sessions:[/] {len(all_sessions)}")

if __name__ == "__main__":
    main()
