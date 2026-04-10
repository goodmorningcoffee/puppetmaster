"""pm_results.py - Results Viewing & Configuration Display"""

import os
from pathlib import Path
from datetime import datetime

from pm_config import load_config, get_remembered_output_dirs
from pm_ui_helpers import (
    C, clear_screen, print_banner, print_section, print_menu_item,
    print_success, print_error, print_warning, print_info, get_input, confirm,
)

try:
    from ui.cyberpunk_ui import (
        cyber_header, cyber_info, cyber_success, cyber_warning, cyber_error,
        get_console,
        cyber_banner_config, cyber_banner_results,
    )
    CYBER_UI_AVAILABLE = True
except ImportError:
    CYBER_UI_AVAILABLE = False


def show_config():
    """Show configuration options"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_banner_config()
        cyber_header("CONFIGURATION")

        from rich.panel import Panel
        from rich.text import Text

        config_text = Text()
        config_text.append("Configuration options coming soon...\n\n", style="dim italic")
        config_text.append("Current settings:\n", style="bold white")
        config_text.append("  ◈ Signal classification: ", style="dim")
        config_text.append("Binary (Smoking Gun / Strong / Weak)\n", style="cyan")
        config_text.append("  ◈ Community detection: ", style="dim")
        config_text.append("Louvain + Label Propagation\n", style="cyan")
        config_text.append("  ◈ Minimum cluster size: ", style="dim")
        config_text.append("2 domains\n", style="cyan")
        config_text.append("  ◈ Output format: ", style="dim")
        config_text.append("Markdown + CSV + HTML", style="cyan")

        console.print(Panel(config_text, title="[bold yellow]⟨ SYSTEM CONFIGURATION ⟩[/]", border_style="yellow"))
    else:
        print_banner()
        print_section("Configuration", C.BRIGHT_YELLOW)

        print(f"""
{C.DIM}Configuration options coming soon...

Current settings:
  • Signal classification: Binary (Smoking Gun / Strong / Weak)
  • Community detection: Louvain + Label Propagation
  • Minimum cluster size: 2 domains
  • Output format: Markdown + CSV + HTML{C.RESET}
""")

    get_input("\nPress Enter to return to main menu...")

def find_results_directories():
    """
    Find all directories containing analysis results (executive_summary.md).
    Searches in multiple locations:
    - Previously used output directories (from config)
    - Current directory (results_*)
    - output/ subdirectory
    - User's desktop
    """
    results = []
    seen_paths = set()

    # First, check remembered output directories (most likely to have results)
    for saved_path in get_remembered_output_dirs():
        d = Path(saved_path)
        if d.exists() and d.is_dir() and d.resolve() not in seen_paths:
            summary = d / "executive_summary.md"
            if summary.exists():
                results.append(d)
                seen_paths.add(d.resolve())

    # Also check parent directories of remembered paths for other results
    search_locations = [
        Path("."),                          # Current directory
        Path("output"),                     # Default output directory
    ]

    # Add parent directories of remembered paths
    for saved_path in get_remembered_output_dirs()[:5]:  # Check parents of recent 5
        parent = Path(saved_path).parent
        if parent.exists() and parent not in search_locations:
            search_locations.append(parent)

    for location in search_locations:
        if not location.exists():
            continue

        # Look for results_* directories
        for d in location.glob("results_*"):
            if d.is_dir() and d.resolve() not in seen_paths:
                summary = d / "executive_summary.md"
                if summary.exists():
                    results.append(d)
                    seen_paths.add(d.resolve())

        # Also look for any directory with executive_summary.md (one level deep)
        for summary in location.glob("*/executive_summary.md"):
            d = summary.parent
            if d.resolve() not in seen_paths:
                results.append(d)
                seen_paths.add(d.resolve())

    # Sort by modification time (newest first)
    results.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return results


def view_previous_results():
    """View previous analysis results"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_banner_results()
        cyber_header("PREVIOUS RESULTS")
    else:
        print_banner()
        print_section("Previous Results", C.BRIGHT_GREEN)

    # Find all results directories
    results_dirs = find_results_directories()

    if not results_dirs:
        if CYBER_UI_AVAILABLE:
            cyber_warning("No previous results found")
            cyber_info("Results are identified by containing an 'executive_summary.md' file")
            cyber_info("Run a new analysis first, or check your output directory")
            console.print()
            console.print("[dim]Searched in:[/]")
            console.print(f"  ◈ Current directory: {Path('.').resolve()}")
            console.print(f"  ◈ Output directory:  {Path('output').resolve()}")
        else:
            print_warning("No previous results found.")
            print_info("Results are identified by containing an 'executive_summary.md' file.")
            print_info("Run a new analysis first, or check your output directory.")
            print()
            print(f"{C.DIM}Searched in:{C.RESET}")
            print(f"  • Current directory: {Path('.').resolve()}")
            print(f"  • Output directory:  {Path('output').resolve()}")
    else:
        if CYBER_UI_AVAILABLE:
            console.print(f"Found [bold cyan]{len(results_dirs)}[/] previous analysis result(s):\n")
            for i, d in enumerate(results_dirs[:10], 1):
                mtime = datetime.fromtimestamp(d.stat().st_mtime)
                try:
                    display_path = d.relative_to(Path.cwd())
                except ValueError:
                    display_path = d
                console.print(f"  [bold green][{i}][/] [cyan]{display_path}[/] [dim]({mtime.strftime('%Y-%m-%d %H:%M')})[/]")
        else:
            print(f"Found {len(results_dirs)} previous analysis result(s):\n")
            for i, d in enumerate(results_dirs[:10], 1):
                mtime = datetime.fromtimestamp(d.stat().st_mtime)
                try:
                    display_path = d.relative_to(Path.cwd())
                except ValueError:
                    display_path = d
                print_menu_item(str(i), f"{display_path} ({mtime.strftime('%Y-%m-%d %H:%M')})", "")

        print()
        choice = get_input("Enter number to view, or press Enter to go back")

        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(results_dirs):
                summary_path = results_dirs[idx] / "executive_summary.md"
                if summary_path.exists():
                    if CYBER_UI_AVAILABLE:
                        console.print(f"\n[cyan]{'─' * 70}[/]")
                        console.print(summary_path.read_text())
                        console.print(f"[cyan]{'─' * 70}[/]\n")
                    else:
                        print(f"\n{C.CYAN}{'─' * 70}{C.RESET}")
                        print(summary_path.read_text())
                        print(f"{C.CYAN}{'─' * 70}{C.RESET}\n")
                else:
                    if CYBER_UI_AVAILABLE:
                        cyber_warning("No executive summary found in that directory")
                    else:
                        print_warning("No executive summary found in that directory.")

    get_input("\nPress Enter to return to main menu...")
