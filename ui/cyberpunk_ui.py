#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PUPPETMASTER Cyberpunk UI Components
Reusable styled components for submenus and displays
"""

from typing import Optional, List, Tuple, Callable, Any
import sys
import os

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# =============================================================================
# COLOR SCHEME
# =============================================================================
class CyberColors:
    """Cyberpunk color constants for rich"""
    # Primary
    CYAN = "bright_cyan"
    GREEN = "bright_green"
    YELLOW = "bright_yellow"
    RED = "bright_red"
    MAGENTA = "bright_magenta"
    BLUE = "bright_blue"

    # Secondary
    DARK_CYAN = "cyan"
    DARK_GREEN = "green"
    DARK_YELLOW = "yellow"
    DARK_RED = "red"

    # Neutral
    WHITE = "white"
    GREY = "grey70"
    DARK_GREY = "grey35"
    DIM = "grey50"

    # Borders
    BORDER = "bright_cyan"
    BORDER_DIM = "grey50"


# =============================================================================
# CONSOLE SINGLETON
# =============================================================================
_console: Optional[Console] = None

def get_console() -> Console:
    """Get or create the shared console instance"""
    global _console
    if _console is None:
        _console = Console()
    return _console


# =============================================================================
# CYBERPUNK HEADER
# =============================================================================
def cyber_header(title: str, subtitle: str = "") -> None:
    """
    Display a cyberpunk-styled header for a submenu

    Args:
        title: Main header title
        subtitle: Optional subtitle/description
    """
    if not RICH_AVAILABLE:
        print(f"\n{'='*60}\n  {title}\n{'='*60}")
        if subtitle:
            print(f"  {subtitle}")
        return

    console = get_console()

    text = Text()
    text.append(f"  {title}", style=f"bold {CyberColors.GREEN}")
    if subtitle:
        text.append(f"\n  {subtitle}", style=CyberColors.CYAN)

    console.print(Panel(
        text,
        border_style=CyberColors.BORDER,
        padding=(0, 1),
    ))


# =============================================================================
# CYBERPUNK MENU
# =============================================================================
def cyber_menu(
    options: List[Tuple[str, str, str]],
    title: str = "OPTIONS",
    selected: Optional[str] = None,
) -> None:
    """
    Display a cyberpunk-styled menu

    Args:
        options: List of (key, label, description) tuples
        title: Menu title
        selected: Currently selected key (for highlighting)
    """
    if not RICH_AVAILABLE:
        print(f"\n{title}:")
        for key, label, desc in options:
            marker = ">" if key == selected else " "
            print(f"  {marker}[{key}] {label}")
            if desc:
                print(f"        {desc}")
        return

    console = get_console()

    text = Text()
    for key, label, desc in options:
        is_selected = key == selected
        if is_selected:
            text.append(f"  >[{key}] ", style=f"bold {CyberColors.GREEN}")
            text.append(f"{label}\n", style=f"bold {CyberColors.GREEN}")
        else:
            text.append(f"   [{key}] ", style=CyberColors.YELLOW)
            text.append(f"{label}\n", style=CyberColors.WHITE)

        if desc:
            text.append(f"        {desc}\n", style=CyberColors.DIM)

    console.print(Panel(
        text,
        title=f"[bold]{title}[/]",
        title_align="left",
        border_style=CyberColors.BORDER,
        padding=(0, 0),
    ))


# =============================================================================
# CYBERPUNK INFO BOXES
# =============================================================================
def cyber_info(message: str) -> None:
    """Display an info message"""
    if not RICH_AVAILABLE:
        print(f"[INFO] {message}")
        return

    console = get_console()
    text = Text()
    text.append("[i] ", style=f"bold {CyberColors.CYAN}")
    text.append(message, style=CyberColors.GREY)
    console.print(text)


def cyber_success(message: str) -> None:
    """Display a success message"""
    if not RICH_AVAILABLE:
        print(f"[OK] {message}")
        return

    console = get_console()
    text = Text()
    text.append("[+] ", style=f"bold {CyberColors.GREEN}")
    text.append(message, style=CyberColors.WHITE)
    console.print(text)


def cyber_warning(message: str) -> None:
    """Display a warning message"""
    if not RICH_AVAILABLE:
        print(f"[WARN] {message}")
        return

    console = get_console()
    text = Text()
    text.append("[!] ", style=f"bold {CyberColors.YELLOW}")
    text.append(message, style=CyberColors.WHITE)
    console.print(text)


def cyber_error(message: str) -> None:
    """Display an error message"""
    if not RICH_AVAILABLE:
        print(f"[ERROR] {message}")
        return

    console = get_console()
    text = Text()
    text.append("[X] ", style=f"bold {CyberColors.RED}")
    text.append(message, style=CyberColors.WHITE)
    console.print(text)


# =============================================================================
# CYBERPUNK PROMPT
# =============================================================================
def cyber_prompt(prompt: str, default: Optional[str] = None) -> Optional[str]:
    """
    Display a cyberpunk-styled input prompt

    Args:
        prompt: The prompt text
        default: Default value (shown in prompt)

    Returns:
        User input or None if cancelled (Ctrl+C)
    """
    if not RICH_AVAILABLE:
        try:
            if default:
                return input(f"{prompt} [{default}]: ") or default
            return input(f"{prompt}: ")
        except (KeyboardInterrupt, EOFError):
            return None

    console = get_console()

    # Build prompt text
    text = Text()
    text.append("CMD> ", style=f"bold {CyberColors.GREEN}")
    text.append(prompt, style=CyberColors.CYAN)
    if default:
        text.append(f" [{default}]", style=CyberColors.DIM)
    text.append(": ", style=CyberColors.GREEN)

    console.print(text, end="")

    try:
        result = input()
        if not result and default:
            return default
        return result
    except (KeyboardInterrupt, EOFError):
        console.print()
        return None


def cyber_confirm(prompt: str, default: bool = True) -> bool:
    """
    Display a cyberpunk-styled confirmation prompt

    Args:
        prompt: The prompt text
        default: Default value

    Returns:
        True for yes, False for no
    """
    default_str = "Y/n" if default else "y/N"
    result = cyber_prompt(f"{prompt} [{default_str}]")

    if result is None:
        return False

    if not result:
        return default

    return result.lower().startswith('y')


# =============================================================================
# CYBERPUNK STATUS DISPLAY
# =============================================================================
def cyber_status(
    status: str,
    value: str,
    color: Optional[str] = None,
) -> None:
    """Display a status line"""
    if not RICH_AVAILABLE:
        print(f"  {status}: {value}")
        return

    console = get_console()
    text = Text()
    text.append(f"  {status}: ", style=CyberColors.GREY)
    text.append(value, style=color or CyberColors.WHITE)
    console.print(text)


def cyber_divider(char: str = "-", width: int = 50) -> None:
    """Display a divider line"""
    if not RICH_AVAILABLE:
        print(char * width)
        return

    console = get_console()
    console.print(char * width, style=CyberColors.DARK_GREY)


# =============================================================================
# CYBERPUNK TABLE
# =============================================================================
def cyber_table(
    headers: List[str],
    rows: List[List[str]],
    title: Optional[str] = None,
) -> None:
    """
    Display a cyberpunk-styled table

    Args:
        headers: Column headers
        rows: List of row data (each row is a list of strings)
        title: Optional table title
    """
    if not RICH_AVAILABLE:
        # Simple fallback
        if title:
            print(f"\n{title}")
        header_line = " | ".join(headers)
        print(header_line)
        print("-" * len(header_line))
        for row in rows:
            print(" | ".join(str(cell) for cell in row))
        return

    console = get_console()

    table = Table(
        title=title,
        box=box.ROUNDED,
        border_style=CyberColors.BORDER_DIM,
        header_style=f"bold {CyberColors.CYAN}",
        title_style=f"bold {CyberColors.GREEN}",
    )

    for header in headers:
        table.add_column(header)

    for row in rows:
        table.add_row(*[str(cell) for cell in row])

    console.print(table)


# =============================================================================
# CYBERPUNK PROGRESS
# =============================================================================
class CyberProgress:
    """Context manager for cyberpunk-styled progress display"""

    def __init__(self, description: str = "Processing..."):
        self.description = description
        self._progress = None

    def __enter__(self):
        if not RICH_AVAILABLE:
            print(f"{self.description}")
            return self

        self._progress = Progress(
            SpinnerColumn(style=CyberColors.CYAN),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(
                complete_style=CyberColors.GREEN,
                finished_style=CyberColors.GREEN,
            ),
            console=get_console(),
        )
        self._progress.start()
        self._task = self._progress.add_task(self.description, total=100)
        return self

    def __exit__(self, *args):
        if self._progress:
            self._progress.stop()

    def update(self, progress: int, description: Optional[str] = None):
        """Update progress (0-100)"""
        if not RICH_AVAILABLE:
            if description:
                print(f"  {description} ({progress}%)")
            return

        if self._progress:
            self._progress.update(
                self._task,
                completed=progress,
                description=description or self.description,
            )


# =============================================================================
# CYBERPUNK SUBMENU WRAPPER
# =============================================================================
def cyber_submenu(
    title: str,
    subtitle: str = "",
    show_back: bool = True,
) -> Callable:
    """
    Decorator to wrap a submenu function with cyberpunk styling

    Args:
        title: Menu title
        subtitle: Menu subtitle
        show_back: Whether to show "back to main menu" hint
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Clear screen
            os.system('clear' if os.name != 'nt' else 'cls')

            # Show header
            cyber_header(title, subtitle)

            if show_back:
                cyber_info("Press Ctrl+C or enter 'q' to return to main menu")

            print()  # Spacing

            # Run the actual function
            try:
                return func(*args, **kwargs)
            except KeyboardInterrupt:
                print()
                cyber_info("Returning to main menu...")
                return None

        return wrapper
    return decorator


# =============================================================================
# WAIT FOR KEY
# =============================================================================
def cyber_wait(message: str = "Press Enter to continue...") -> None:
    """Wait for user to press Enter"""
    cyber_prompt(message, default="")


# =============================================================================
# THEMED SUBMENU HEADERS - Unique ASCII art for each module
# =============================================================================
#
# DESIGN NOTES:
# - All banners use 80-char wide boxes for consistent alignment
# - No leading whitespace - boxes start at column 0
# - Descriptions explain what the tool DOES, not filler text
# - Colors: bright_cyan borders, bright_green titles, content varies
#
# TO EDIT: Change the text inside the art strings below.
# Keep the box structure intact - just modify text between │ and │
# =============================================================================

def cyber_banner_discovery() -> None:
    """Domain Discovery - Search engines for competitor domains"""
    if not RICH_AVAILABLE:
        print("\n=== DOMAIN DISCOVERY ===\n")
        return
    console = get_console()
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_green]  ◢◤ DOMAIN DISCOVERY                                                       [/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]    [bright_yellow]◎[/][dim])))))[/]     [white]Search Google & DuckDuckGo for domains in your industry[/]    [bright_cyan]│
│[/]   [bright_yellow]◎[/][dim])))))[/]      [dim]Enter keywords like "construction estimating" or "HVAC NYC"[/]   [bright_cyan]│
│[/]    [bright_yellow]◎[/][dim])))))[/]     [dim]Found domains are filtered and added to your scan queue[/]      [bright_cyan]│
│[/]                                                                              [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


def cyber_banner_import() -> None:
    """File Import - Load domains from a text file"""
    if not RICH_AVAILABLE:
        print("\n=== FILE IMPORT ===\n")
        return
    console = get_console()
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_green]  ◢◤ DOMAIN IMPORT                                                          [/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]      [bright_yellow]┌─────────────────────┐[/]                                             [bright_cyan]│
│[/]      [bright_yellow]│[/] [dim]domains.txt[/]         [bright_yellow]│[/]   [white]Load a list of domains from any text file[/]   [bright_cyan]│
│[/]      [bright_yellow]│[/] [bright_green]example.com[/]         [bright_yellow]│[/]   [dim]One domain per line, URLs are parsed[/]       [bright_cyan]│
│[/]      [bright_yellow]│[/] [bright_green]competitor.io[/]       [bright_yellow]│[/]   [dim]Duplicates removed automatically[/]           [bright_cyan]│
│[/]      [bright_yellow]│[/] [bright_green]target-site.net[/]     [bright_yellow]│[/]                                             [bright_cyan]│
│[/]      [bright_yellow]└─────────────────────┘[/]                                             [bright_cyan]│
│[/]                                                                              [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


def cyber_banner_spider() -> None:
    """SpiderFoot Scanner - OSINT batch scanning"""
    if not RICH_AVAILABLE:
        print("\n=== SPIDERFOOT SCANNER ===\n")
        return
    console = get_console()
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_green]  ◢◤ SPIDERFOOT SCANNER                                                     [/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]          [dim]╲       │       ╱[/]                                               [bright_cyan]│
│[/]           [dim]╲  ╲   │   ╱  ╱[/]      [white]Runs SpiderFoot OSINT scans on your domains[/]   [bright_cyan]│
│[/]        [dim]────[bright_yellow]╲──╲──┼──╱──╱[/][dim]────[/]   [dim]Collects: WHOIS, DNS, SSL certs, analytics[/]   [bright_cyan]│
│[/]              [bright_yellow]╲ ╲ █ ╱ ╱[/]        [dim]Results saved as CSV for analysis[/]           [bright_cyan]│
│[/]        [dim]────[bright_yellow]╱──╱──┼──╲──╲[/][dim]────[/]   [dim]Can run multiple domains in batch[/]           [bright_cyan]│
│[/]           [dim]╱  ╱   │   ╲  ╲[/]                                               [bright_cyan]│
│[/]          [dim]╱       │       ╲[/]                                               [bright_cyan]│
│[/]                                                                              [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


def cyber_banner_queue() -> None:
    """Queue Status - Monitor running and pending scans"""
    if not RICH_AVAILABLE:
        print("\n=== SCAN QUEUE ===\n")
        return
    console = get_console()
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_green]  ◢◤ SCAN QUEUE STATUS                                                      [/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]    [bright_cyan]PENDING[/]   [dim]░░░░░░░░░░░░░░░░░░░░[/]   [white]Domains waiting to be scanned[/]         [bright_cyan]│
│[/]    [bright_green]RUNNING[/]   [bright_green]████████[/][dim]░░░░░░░░░░░░[/]   [dim]Currently scanning with SpiderFoot[/]     [bright_cyan]│
│[/]    [bright_yellow]COMPLETE[/]  [bright_yellow]██████████████████░░[/]   [dim]Finished scans ready for analysis[/]     [bright_cyan]│
│[/]                                                                              [bright_cyan]│
│[/]    [dim]View progress, cancel scans, or restart failed jobs from here[/]            [bright_cyan]│
│[/]                                                                              [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


def cyber_banner_analysis() -> None:
    """Puppet Analysis - The main event: find connected domains"""
    if not RICH_AVAILABLE:
        print("\n=== PUPPET ANALYSIS ===\n")
        return
    console = get_console()
    # LCARS Compact style inspired design - the core module
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_magenta]▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓[/][bright_cyan]│
│[/][bold bright_magenta]▓▓[/]  [bold bright_white]PUPPET CLUSTER ANALYSIS[/]                        [bold bright_yellow]// CORE MODULE[/]  [bold bright_magenta]▓▓[/][bright_cyan]│
│[/][bold bright_magenta]▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓[/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]   [bright_yellow]●[/]━━━━━━[bright_yellow]●[/]        [bold white]Finds domains owned by the SAME person/company[/]         [bright_cyan]│
│[/]   [dim]┃[/]      [dim]┃[/]                                                                [bright_cyan]│
│[/]   [bright_yellow]●[/]━━[bright_red]●[/]━━━[bright_yellow]●[/]        [dim]Analyzes: Google Analytics IDs, AdSense, Facebook[/]       [bright_cyan]│
│[/]   [dim]┃[/]  [dim]┃[/]   [dim]┃[/]        [dim]Pixel, WHOIS data, SSL certs, nameservers, IPs[/]          [bright_cyan]│
│[/]   [bright_yellow]●[/]━━[bright_yellow]●[/]━━━[bright_yellow]●[/]                                                                [bright_cyan]│
│[/]                  [bright_green]OUTPUT:[/] Cluster report showing connected domains          [bright_cyan]│
│[/]                                                                              [bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]  [dim]REQUIRES:[/] SpiderFoot CSV exports    [dim]TIME:[/] ~1 min per 100 domains           [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


def cyber_banner_wildcard() -> None:
    """Wildcard DNS - Filter out false positive subdomains"""
    if not RICH_AVAILABLE:
        print("\n=== WILDCARD DNS ANALYZER ===\n")
        return
    console = get_console()
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_green]  ◢◤ WILDCARD DNS ANALYZER                                                  [/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]    [bright_green]SIGNAL[/]  [bright_green]▁▂▃▄▅▆▇█▇▆▅▄▃▂▁[/]   [white]Real subdomains with actual content[/]      [bright_cyan]│
│[/]    [bright_red]NOISE[/]   [dim]░░░░░░░░░░░░░░░░░░[/]   [dim]Wildcard DNS = fake subdomains[/]           [bright_cyan]│
│[/]                                                                              [bright_cyan]│
│[/]    [dim]Some domains respond to ANY subdomain (*.example.com). This tool[/]          [bright_cyan]│
│[/]    [dim]detects wildcards so you don't analyze thousands of fake results.[/]         [bright_cyan]│
│[/]                                                                              [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


def cyber_banner_help() -> None:
    """Help & Documentation - Learn how to use PUPPETMASTER"""
    if not RICH_AVAILABLE:
        print("\n=== HELP & DOCUMENTATION ===\n")
        return
    console = get_console()
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_green]  ◢◤ TACTICAL MANUAL                                                        [/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]    [bright_yellow]┌──────────────────────────────────────────────────────────────────┐[/]    [bright_cyan]│
│[/]    [bright_yellow]│[/]                                                                  [bright_yellow]│[/]    [bright_cyan]│
│[/]    [bright_yellow]│[/]    [bright_white]1. DISCOVER[/]  ─────▶  Find competitor domains              [bright_yellow]│[/]    [bright_cyan]│
│[/]    [bright_yellow]│[/]    [bright_white]2. SCAN[/]      ─────▶  Collect OSINT with SpiderFoot        [bright_yellow]│[/]    [bright_cyan]│
│[/]    [bright_yellow]│[/]    [bright_white]3. ANALYZE[/]   ─────▶  Find shared ownership signals        [bright_yellow]│[/]    [bright_cyan]│
│[/]    [bright_yellow]│[/]    [bright_white]4. RESULTS[/]   ─────▶  View clusters & export reports       [bright_yellow]│[/]    [bright_cyan]│
│[/]    [bright_yellow]│[/]                                                                  [bright_yellow]│[/]    [bright_cyan]│
│[/]    [bright_yellow]└──────────────────────────────────────────────────────────────────┘[/]    [bright_cyan]│
│[/]                                                                              [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


def cyber_banner_config() -> None:
    """Configuration - Set paths, API keys, and options"""
    if not RICH_AVAILABLE:
        print("\n=== CONFIGURATION ===\n")
        return
    console = get_console()
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_green]  ◢◤ SYSTEM CONFIGURATION                                                   [/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]    [bright_yellow]╔══════════════╗[/]  [bright_magenta]╔══════════════╗[/]  [bright_blue]╔══════════════╗[/]          [bright_cyan]│
│[/]    [bright_yellow]║[/]    [white]PATHS[/]     [bright_yellow]║[/]  [bright_magenta]║[/]   [white]API KEYS[/]   [bright_magenta]║[/]  [bright_blue]║[/]   [white]OPTIONS[/]    [bright_blue]║[/]          [bright_cyan]│
│[/]    [bright_yellow]║[/] [dim]SpiderFoot[/]   [bright_yellow]║[/]  [bright_magenta]║[/] [dim]Google CSE[/]   [bright_magenta]║[/]  [bright_blue]║[/] [dim]Thresholds[/]  [bright_blue]║[/]          [bright_cyan]│
│[/]    [bright_yellow]║[/] [dim]Output dir[/]   [bright_yellow]║[/]  [bright_magenta]║[/] [dim]Shodan[/]       [bright_magenta]║[/]  [bright_blue]║[/] [dim]Scan modes[/]  [bright_blue]║[/]          [bright_cyan]│
│[/]    [bright_yellow]╚══════════════╝[/]  [bright_magenta]╚══════════════╝[/]  [bright_blue]╚══════════════╝[/]          [bright_cyan]│
│[/]                                                                              [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


def cyber_banner_results() -> None:
    """Results Browser - View previous analysis runs"""
    if not RICH_AVAILABLE:
        print("\n=== RESULTS BROWSER ===\n")
        return
    console = get_console()
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_green]  ◢◤ RESULTS BROWSER                                                        [/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]    [dim]┌──────────┐[/]  [dim]┌──────────┐[/]  [dim]┌──────────┐[/]  [dim]┌──────────┐[/]        [bright_cyan]│
│[/]    [dim]│[/] [bright_green]2024-12-30[/][dim]│[/]  [dim]│[/] [bright_yellow]2024-12-28[/][dim]│[/]  [dim]│[/] [bright_magenta]2024-12-25[/][dim]│[/]  [dim]│[/] [bright_blue]2024-12-20[/][dim]│[/]        [bright_cyan]│
│[/]    [dim]│[/]  [white]7 clusters[/][dim]│[/]  [dim]│[/]  [white]3 clusters[/][dim]│[/]  [dim]│[/] [white]12 clusters[/][dim]│[/]  [dim]│[/]  [white]5 clusters[/][dim]│[/]        [bright_cyan]│
│[/]    [dim]│[/] [dim]128 domains[/][dim]│[/]  [dim]│[/]  [dim]45 domains[/][dim]│[/]  [dim]│[/] [dim]312 domains[/][dim]│[/]  [dim]│[/]  [dim]89 domains[/][dim]│[/]        [bright_cyan]│
│[/]    [dim]└──────────┘[/]  [dim]└──────────┘[/]  [dim]└──────────┘[/]  [dim]└──────────┘[/]        [bright_cyan]│
│[/]                                                                              [bright_cyan]│
│[/]    [dim]Select a previous run to view clusters, export reports, or compare[/]        [bright_cyan]│
│[/]                                                                              [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


def cyber_banner_kali() -> None:
    """Kali Linux Arsenal - Advanced recon tools"""
    if not RICH_AVAILABLE:
        print("\n=== KALI TOOLS ===\n")
        return
    console = get_console()
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_red]▓▓[/][bold bright_white] KALI LINUX ARSENAL [/][bold bright_red]▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓[/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]    [bright_red]██[/][dim]▀▀▀[/][bright_red]██[/]                                                              [bright_cyan]│
│[/]    [bright_red]██[/]   [bright_red]██[/]   [bright_blue]root@kali[/][dim]:~#[/] [bright_green]_[/]                                        [bright_cyan]│
│[/]    [bright_red]██▄▄▄██[/]                                                              [bright_cyan]│
│[/]                                                                              [bright_cyan]│
│[/]    [white]Extended tools:[/] [dim]amass, subfinder, dnsx, httpx, nuclei, nmap[/]           [bright_cyan]│
│[/]    [dim]Requires Kali Linux or tools installed manually[/]                           [bright_cyan]│
│[/]                                                                              [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


def cyber_banner_workflow() -> None:
    """Workflow diagram - The 4-step process"""
    if not RICH_AVAILABLE:
        print("\n=== WORKFLOW ===\n")
        return
    console = get_console()
    art = """[bright_cyan]╭──────────────────────────────────────────────────────────────────────────────╮
│[/][bold bright_green]  ◢◤ PUPPETMASTER WORKFLOW                                                  [/][bright_cyan]│
├──────────────────────────────────────────────────────────────────────────────┤
│[/]                                                                              [bright_cyan]│
│[/]  [bright_cyan]┌───────────┐[/]     [bright_yellow]┌───────────┐[/]     [bright_magenta]┌───────────┐[/]     [bright_green]┌───────────┐[/]  [bright_cyan]│
│[/]  [bright_cyan]│[/] [bold]DISCOVER[/] [bright_cyan]│[/]────▶[bright_yellow]│[/]   [bold]SCAN[/]   [bright_yellow]│[/]────▶[bright_magenta]│[/]  [bold]ANALYZE[/] [bright_magenta]│[/]────▶[bright_green]│[/]  [bold]REPORT[/]  [bright_green]│[/]  [bright_cyan]│
│[/]  [bright_cyan]│[/] [dim]Option 1,2[/][bright_cyan]│[/]     [bright_yellow]│[/] [dim]Option 3[/]  [bright_yellow]│[/]     [bright_magenta]│[/] [dim]Option 5[/]  [bright_magenta]│[/]     [bright_green]│[/] [dim]Option 6[/]  [bright_green]│[/]  [bright_cyan]│
│[/]  [bright_cyan]└───────────┘[/]     [bright_yellow]└───────────┘[/]     [bright_magenta]└───────────┘[/]     [bright_green]└───────────┘[/]  [bright_cyan]│
│[/]                                                                              [bright_cyan]│
│[/]  [dim]Find domains[/]     [dim]Collect OSINT[/]     [dim]Find clusters[/]    [dim]Export results[/]       [bright_cyan]│
│[/]                                                                              [bright_cyan]│
╰──────────────────────────────────────────────────────────────────────────────╯[/]"""
    console.print(art)


# =============================================================================
# EXPORTS
# =============================================================================
__all__ = [
    'RICH_AVAILABLE',
    'CyberColors',
    'get_console',
    'cyber_header',
    'cyber_menu',
    'cyber_info',
    'cyber_success',
    'cyber_warning',
    'cyber_error',
    'cyber_prompt',
    'cyber_confirm',
    'cyber_status',
    'cyber_divider',
    'cyber_table',
    'CyberProgress',
    'cyber_submenu',
    'cyber_wait',
    # Themed banners
    'cyber_banner_discovery',
    'cyber_banner_import',
    'cyber_banner_spider',
    'cyber_banner_queue',
    'cyber_banner_analysis',
    'cyber_banner_wildcard',
    'cyber_banner_help',
    'cyber_banner_config',
    'cyber_banner_results',
    'cyber_banner_kali',
    'cyber_banner_workflow',
]
