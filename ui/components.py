"""
PUPPETMASTER UI Components
Reusable components for the Gaming HUD using rich library
"""

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.padding import Padding
from rich.style import Style
from typing import List, Optional, Tuple

from .colors import COLORS, STYLES
from .ascii_art import (
    BANNER_PUPPET, BANNER_MASTER, VERSION, TAGLINE, CREDITS, QUOTE,
    CHEVRONS, BULLET, CHECK, CROSS, ARROW_RIGHT
)
from .descriptions import ToolDescription, TOOL_DESCRIPTIONS, get_categories


def render_banner(console_width: int = 120) -> Panel:
    """Render the PUPPETMASTER banner"""
    lines = []

    # Empty line
    lines.append("")

    # PUPPET in magenta
    for line in BANNER_PUPPET:
        lines.append(f"[bright_magenta]   {line}[/]")

    lines.append("")

    # MASTER in yellow
    for line in BANNER_MASTER:
        lines.append(f"[bright_yellow]   {line}[/]")

    lines.append("")

    # Info line
    info_line = f"[white]{TAGLINE} {VERSION}[/]  |  [dim]{CREDITS}[/]  |  [dim italic]{QUOTE}[/]"
    lines.append(f"   {info_line}")
    lines.append("")

    content = "\n".join(lines)

    return Panel(
        content,
        border_style="bright_cyan",
        padding=(0, 0),
    )


def render_status_bar(
    queue_count: int = 0,
    scan_count: int = 0,
    cluster_count: int = 0,
    blacklist_count: int = 0,
    status: str = "STANDBY",
    discover_pct: int = 0,
    scan_pct: int = 0,
    analyze_pct: int = 0,
) -> Panel:
    """Render the mission status bar with stats and progress"""

    def progress_bar(pct: int, width: int = 4) -> str:
        """Generate a mini progress bar"""
        filled = int(pct / 100 * width)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        if pct == 100:
            return f"[bright_green]{bar}[/]"
        elif pct > 0:
            return f"[yellow]{bar}[/]"
        else:
            return f"[dim]{bar}[/]"

    def stat(label: str, value: int, bar_width: int = 3) -> str:
        """Format a stat with mini bar"""
        pct = min(100, value * 10)  # Assume max ~10 for visualization
        bar = progress_bar(pct, bar_width)
        return f"[dim]{label}:[/][bright_white]{value}[/] {bar}"

    # Status color
    status_colors = {
        "STANDBY": "bright_yellow",
        "SCANNING": "bright_cyan",
        "ANALYZING": "bright_green",
        "ERROR": "bright_red",
    }
    status_color = status_colors.get(status, "white")

    # Build status line
    left_side = (
        f"  {CHEVRONS} [bold bright_cyan]MISSION STATUS[/] {CHEVRONS}  "
        f"{stat('Q', queue_count)}  {stat('S', scan_count)}  "
        f"{stat('C', cluster_count)}  {stat('BL', blacklist_count)}  "
        f"[{status_color}]{status}[/]"
    )

    right_side = (
        f"{CHEVRONS} [bold bright_cyan]PROGRESS[/] {CHEVRONS}  "
        f"[dim]DISC[/]{progress_bar(discover_pct)} "
        f"[dim]SCAN[/]{progress_bar(scan_pct)} "
        f"[dim]ANLZ[/]{progress_bar(analyze_pct)}  "
    )

    # Combine
    content = f"{left_side}  {right_side}"

    return Panel(
        content,
        border_style="bright_cyan",
        padding=(0, 0),
    )


def render_loadout_menu(
    selected_index: int = 0,
    show_kali: bool = True,
    scan_mode: str = "STANDARD",
    blacklist_count: int = 231,
) -> Panel:
    """Render the left-side loadout menu"""

    lines = []

    # Categories with their tools
    categories = [
        ("DISCOVERY & SCANNING", ["01", "02", "03", "04", "11"]),
        ("ANALYSIS", ["05", "06", "12"]),
    ]

    if show_kali:
        categories.append(("ADVANCED TOOLS", ["K1", "K2", "K3", "K4", "K5"]))

    categories.append(("SETTINGS", ["07", "08", "09", "10"]))

    # Build flat list for index mapping
    all_keys = []
    for _, keys in categories:
        all_keys.extend(keys)
    all_keys.append("Q")  # Add quit

    current_idx = 0

    for cat_name, keys in categories:
        # Category header
        lines.append(f"  [bold bright_cyan]{cat_name}[/]")
        lines.append(f"  [dim cyan]{'─' * (len(cat_name) + 2)}[/]")

        for key in keys:
            tool = TOOL_DESCRIPTIONS.get(key)
            if not tool:
                continue

            # Check if selected
            is_selected = current_idx == selected_index

            # Build display name (with dynamic values for some)
            display_name = tool.short_name
            if key == "K2":
                display_name = f"Scan mode [{scan_mode}]"
            elif key == "K4":
                display_name = f"Blacklist ({blacklist_count})"

            # Format line
            if is_selected:
                prefix = f"[bold bright_white on blue] >{ARROW_RIGHT}[/]"
                key_style = "[bold bright_yellow on blue]"
                text_style = "[bold bright_white on blue]"
                suffix = "[/]"
                # Pad to consistent width
                line = f"  {prefix}{key_style}[{key}]{suffix} {text_style}{tool.emoji} {display_name}{suffix}"
            else:
                prefix = "   "
                key_style = "[bright_yellow]"
                text_style = "[white]"
                suffix = "[/]"
                line = f"  {prefix}{key_style}[{key}]{suffix} {text_style}{tool.emoji} {display_name}{suffix}"

            lines.append(line)
            current_idx += 1

        lines.append("")  # Spacing between categories

    # Add quit
    is_quit_selected = current_idx == selected_index
    if is_quit_selected:
        lines.append(f"  [bold bright_white on blue] >{ARROW_RIGHT}[bold bright_yellow on blue][Q][/] [bold bright_white on blue]👋 Quit[/]")
    else:
        lines.append(f"   [bright_yellow][Q][/] [white]👋 Quit[/]")

    lines.append("")

    content = "\n".join(lines)

    return Panel(
        content,
        title=f"[bold bright_magenta]{CHEVRONS} LOADOUT {CHEVRONS}[/]",
        border_style="bright_cyan",
        padding=(0, 0),
    )


def render_mission_panel(
    selected_key: str = "01",
    dynamic_stats: Optional[dict] = None,
) -> Panel:
    """Render the right-side mission description panel"""

    tool = TOOL_DESCRIPTIONS.get(selected_key)
    if not tool:
        return Panel("No tool selected", border_style="bright_cyan")

    lines = []

    # Title
    lines.append(f"  [bold bright_magenta][{tool.key}] {tool.title}[/]")
    lines.append(f"  [bright_cyan]{tool.subtitle}[/]")
    lines.append("")

    # Description paragraphs
    for para in tool.description:
        lines.append(f"  [white]{para}[/]")
    lines.append("")

    # Objectives
    if tool.objectives:
        for obj in tool.objectives:
            lines.append(f"  [bright_green]{BULLET}[/] [white]{obj}[/]")
        lines.append("")

    # Next step hint
    if tool.next_step:
        lines.append(f"  [dim]{'─' * 60}[/]")
        lines.append(f"  [bright_yellow]{tool.next_step}[/]")

    lines.append("")

    content = "\n".join(lines)

    return Panel(
        content,
        title=f"[bold bright_magenta]{CHEVRONS} ACTIVE MISSION {CHEVRONS}[/]",
        border_style="bright_cyan",
        padding=(0, 0),
    )


def render_tip_box() -> Panel:
    """Render the tip/hint box"""
    content = (
        f"[bright_yellow]💡[/] [white]New here? Press [bright_yellow][8][/] for full tactical manual.[/]    "
        f"[bright_cyan]⏱️[/] [white]Long scans? Press [bright_yellow][9][/] for tmux (survives disconnects)[/]"
    )

    return Panel(
        content,
        border_style="bright_cyan",
        padding=(0, 1),
    )


def render_command_bar() -> Panel:
    """Render the bottom command hints"""
    content = (
        f"[bold bright_magenta]◢ DEPLOY [ENTER] ◣[/]  "
        f"[bold bright_cyan]◢ SELECT [↑↓/jk] ◣[/]  "
        f"[bold bright_yellow]◢ HELP [?] ◣[/]  "
        f"[bold bright_red]◢ QUIT [Q] ◣[/]"
    )

    return Panel(
        Align.center(content),
        border_style="bright_cyan",
        padding=(0, 0),
    )


def render_notification(
    message: str,
    style: str = "info",  # info, success, warning, error
) -> Panel:
    """Render a notification banner"""

    styles = {
        "info": ("bright_cyan", "ℹ️"),
        "success": ("bright_green", "✅"),
        "warning": ("bright_yellow", "⚠️"),
        "error": ("bright_red", "❌"),
    }

    color, emoji = styles.get(style, styles["info"])

    return Panel(
        f"  {emoji} [bold {color}]{message}[/]",
        border_style=color,
        padding=(0, 0),
    )


def render_scan_progress_banner(
    current_domain: str,
    completed: int,
    total: int,
) -> Panel:
    """Render the background scan progress banner"""

    # Truncate domain if too long
    if len(current_domain) > 30:
        current_domain = current_domain[:27] + "..."

    content = (
        f"  [bright_yellow]🔄[/] [bold bright_yellow]SPIDERFOOT SCAN IN PROGRESS[/] — "
        f"[bright_white]{completed}/{total}[/] complete\n"
        f"     Currently scanning: [bright_cyan]{current_domain}[/]  "
        f"Use [bright_yellow][4][/] to view details"
    )

    return Panel(
        content,
        border_style="bright_yellow",
        padding=(0, 0),
    )


def render_kali_mode_banner(status_line: str = "") -> Panel:
    """Render the Kali enhanced mode banner"""

    content = (
        f"  [bright_red]🐉[/] [bold bright_red]KALI LINUX ENHANCED MODE ACTIVE[/]\n"
        f"     {status_line}\n"
        f"     Option [bright_yellow][1][/] auto-expands domains with Kali tools after scraping!"
    )

    return Panel(
        content,
        border_style="bright_red",
        padding=(0, 0),
    )


def render_domains_ready_banner(domain_count: int) -> Panel:
    """Render the domains ready for scan banner"""

    content = (
        f"  [bright_green]✓[/] [bold bright_green]{domain_count} DOMAINS LOADED[/] — "
        f"Proceed to option [bright_yellow][3][/] to start SpiderFoot scans!"
    )

    return Panel(
        content,
        border_style="bright_green",
        padding=(0, 0),
    )
