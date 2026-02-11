#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PUPPETMASTER Cyberpunk Terminal HUD
Dystopian hacker aesthetic for SSH/VPS terminals

Design:
- Two-column layout: LOADOUT (menu) + ACTIVE MISSION (description)
- Status bar with real-time progress indicators
- Arrow key + number key navigation
- Cyberpunk color scheme (no emojis)

Colors:
- Base: dark red, dark blue, dark yellow, blue-grey shades
- Highlights: bright green, bright blue
"""

import sys
import os
import time
import webbrowser
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.layout import Layout
from rich import box

# Try to import Group (not available in older rich versions)
try:
    from rich.console import Group
except ImportError:
    # Fallback: create a simple Group-like class
    class Group:
        def __init__(self, *renderables):
            self.renderables = renderables
        def __rich_console__(self, console, options):
            for r in self.renderables:
                yield r


# =============================================================================
# COLOR SCHEME - Cyberpunk Dystopian
# =============================================================================
class Colors:
    """Cyberpunk color palette"""
    # Base colors (dark/muted)
    BASE_RED = "red"
    BASE_BLUE = "blue"
    BASE_YELLOW = "yellow"
    GREY = "grey50"
    DARK_GREY = "grey30"

    # Highlight colors (bright)
    BRIGHT_GREEN = "bright_green"
    BRIGHT_BLUE = "bright_cyan"
    BRIGHT_CYAN = "bright_cyan"
    BRIGHT_RED = "bright_red"
    BRIGHT_YELLOW = "bright_yellow"
    BRIGHT_MAGENTA = "bright_magenta"

    # UI elements
    BORDER = "bright_cyan"
    TITLE = "bright_magenta"
    SELECTED = "bright_green"
    MUTED = "grey50"
    TEXT = "white"

    # Status colors
    STANDBY = "yellow"
    SCANNING = "bright_cyan"
    ANALYZING = "bright_green"
    ERROR = "bright_red"


# =============================================================================
# MENU ITEMS & DESCRIPTIONS
# =============================================================================
@dataclass
class MenuItem:
    """Menu item with description"""
    key: str
    name: str
    category: str
    title: str
    subtitle: str
    description: List[str]
    next_step: str = ""


MENU_ITEMS = {
    "01": MenuItem(
        key="01",
        name="Scrape domains (keywords)",
        category="DISCOVERY & SCANNING",
        title="KEYWORD SCRAPE",
        subtitle="Search Engine Domain Discovery",
        description=[
            "Scrape Google and DuckDuckGo using industry keywords to discover",
            "competitor domains that might be sock puppets. This is typically",
            "the first step in the workflow.",
            "",
            "- Keywords loaded from config.json",
            "- Results filtered through blacklist",
            "- Output added to pending queue for scanning",
            "- Expected runtime: 2-5 minutes",
        ],
        next_step="Use [3] to scan discovered domains with SpiderFoot",
    ),
    "02": MenuItem(
        key="02",
        name="Load domains (file)",
        category="DISCOVERY & SCANNING",
        title="FILE IMPORT",
        subtitle="Load Domain List from File",
        description=[
            "Import a list of domains from a text file. One domain per line.",
            "Useful when you already have a target list from another source.",
            "",
            "- Supports .txt and .csv files",
            "- Auto-deduplication",
            "- Blacklist filtering applied",
        ],
        next_step="Use [3] to scan imported domains",
    ),
    "03": MenuItem(
        key="03",
        name="SpiderFoot Control Center",
        category="DISCOVERY & SCANNING",
        title="SPIDERFOOT CONTROL CENTER",
        subtitle="Unified Scan Management",
        description=[
            "Unified control center for all SpiderFoot operations:",
            "",
            "- Start batch scans with intensity presets",
            "- Launch Web GUI for interactive scanning",
            "- Reset SpiderFoot database (wipe zombies)",
            "- Kill stuck processes, ETA tracking",
        ],
        next_step="Use [5] to analyze completed scans",
    ),
    "04": MenuItem(
        key="04",
        name="Check scan queue",
        category="DISCOVERY & SCANNING",
        title="QUEUE STATUS",
        subtitle="View Scan Progress",
        description=[
            "Monitor the status of running and queued SpiderFoot scans.",
            "",
            "- View active scans and progress",
            "- Check completed/failed counts",
            "- Manage scan queue",
        ],
        next_step="Wait for scans to complete, then use [5]",
    ),
    "11": MenuItem(
        key="11",
        name="Wildcard DNS Analyzer",
        category="ANALYSIS",
        title="SIGNAL//NOISE",
        subtitle="Wildcard DNS Analyzer",
        description=[
            "Analyze domains with wildcard DNS to filter false positives.",
            "Critical for accurate puppet detection on shared hosting.",
            "",
            "- Detect wildcard DNS responses",
            "- Filter false positive subdomains",
            "- Improve signal-to-noise ratio",
        ],
        next_step="Clean results before running [5]",
    ),
    "05": MenuItem(
        key="05",
        name="Puppet Analysis",
        category="ANALYSIS",
        title="PUPPET ANALYSIS",
        subtitle="Detect Sock Puppet Networks",
        description=[
            "Analyze SpiderFoot scan results to identify sock puppet clusters.",
            "Uses graph analysis to find domains with shared infrastructure.",
            "",
            "- Detects shared Analytics/AdSense IDs",
            "- Identifies common WHOIS, nameservers, SSL certs",
            "- Generates cluster visualization",
        ],
        next_step="Review results in [6]",
    ),
    "06": MenuItem(
        key="06",
        name="View results",
        category="ANALYSIS",
        title="RESULTS VIEWER",
        subtitle="Previous Analysis Results",
        description=[
            "Browse and review previous puppet analysis results.",
            "",
            "- View cluster details",
            "- Export findings",
            "- Compare analysis runs",
        ],
        next_step="Run new analysis with [5]",
    ),
    "12": MenuItem(
        key="12",
        name="Manage domain queue",
        category="DISCOVERY & SCANNING",
        title="QUEUE CONTROL",
        subtitle="Domain Queue Manager",
        description=[
            "Manage loaded domains and scan queue in one place.",
            "",
            "LOADED DOMAINS (scraped/imported):",
            "- Review & remove domains before scanning",
            "- Clear all loaded domains",
            "- Move to scan queue to start scanning",
            "",
            "SCAN QUEUE (JobTracker):",
            "- Review & remove pending jobs",
            "- Retry failed scans",
            "- Clear completed/all jobs",
        ],
        next_step="Clean up domains, then scan with [3]",
    ),
    "K1": MenuItem(
        key="K1",
        name="Enumerate domain",
        category="KALI TOOLS",
        title="DOMAIN ENUMERATION",
        subtitle="Subdomain & Infrastructure Discovery",
        description=[
            "Use Kali Linux tools to enumerate subdomains and infrastructure.",
            "",
            "- Subdomain brute-forcing",
            "- DNS reconnaissance",
            "- Certificate transparency logs",
        ],
        next_step="Add discovered domains to scan queue",
    ),
    "K2": MenuItem(
        key="K2",
        name="Scan mode [STANDARD]",
        category="KALI TOOLS",
        title="SCAN MODE",
        subtitle="Configure Kali Tool Intensity",
        description=[
            "Adjust the aggressiveness of Kali enumeration tools.",
            "",
            "- LIGHT: Quick passive scans",
            "- STANDARD: Balanced approach",
            "- AGGRESSIVE: Full enumeration (slower)",
        ],
        next_step="Select mode and run [K1]",
    ),
    "K3": MenuItem(
        key="K3",
        name="Tool status",
        category="KALI TOOLS",
        title="TOOL STATUS",
        subtitle="Kali Tool Availability",
        description=[
            "Check which Kali tools are installed and available.",
            "",
            "- Shows installed/missing tools",
            "- Installation instructions",
            "- Tool version info",
        ],
        next_step="Install missing tools if needed",
    ),
    "K4": MenuItem(
        key="K4",
        name="Blacklist management",
        category="KALI TOOLS",
        title="BLACKLIST",
        subtitle="Domain Blacklist Management",
        description=[
            "Manage the domain blacklist to filter out known false positives.",
            "",
            "- Add/remove domains",
            "- Import blacklist files",
            "- View current blacklist",
        ],
        next_step="Run [1] with updated blacklist",
    ),
    "K5": MenuItem(
        key="K5",
        name="Infra correlation",
        category="KALI TOOLS",
        title="INFRASTRUCTURE CORRELATION",
        subtitle="Cross-Domain Infrastructure Analysis",
        description=[
            "Advanced analysis of shared infrastructure across domains.",
            "Identifies hidden connections through hosting patterns.",
            "",
            "- IP range and ASN correlation",
            "- Hosting provider fingerprinting",
            "- Network topology mapping",
            "- Standalone analysis tool (external script)",
        ],
        next_step="Review findings in results",
    ),
    "07": MenuItem(
        key="07",
        name="Configuration",
        category="SETTINGS",
        title="CONFIGURATION",
        subtitle="Tool Settings",
        description=[
            "Configure PUPPETMASTER settings and preferences.",
            "",
            "- Output directory settings",
            "- SpiderFoot configuration",
            "- Keyword management",
        ],
        next_step="Save settings and continue",
    ),
    "08": MenuItem(
        key="08",
        name="Help & Documentation",
        category="SETTINGS",
        title="TACTICAL MANUAL",
        subtitle="Help & Documentation",
        description=[
            "Full documentation and usage guide for PUPPETMASTER.",
            "",
            "- Workflow tutorials",
            "- Tool explanations",
            "- Troubleshooting guide",
        ],
        next_step="Read and return to main menu",
    ),
    "09": MenuItem(
        key="09",
        name="Launch in tmux",
        category="SETTINGS",
        title="TMUX SESSION",
        subtitle="Persistent Terminal Session",
        description=[
            "Launch PUPPETMASTER in a tmux session that survives disconnects.",
            "Essential for long-running scans over SSH.",
            "",
            "- Survives SSH disconnection",
            "- Reconnect anytime",
            "- Background operation",
        ],
        next_step="Reconnect with: tmux attach",
    ),
    "10": MenuItem(
        key="10",
        name="System monitor (via Glances)",
        category="SETTINGS",
        title="SYSTEM MONITOR",
        subtitle="Resource Usage via Glances",
        description=[
            "Launch Glances to view detailed system stats.",
            "",
            "- CPU/Memory/Disk usage",
            "- Network activity",
            "- Process list",
        ],
        next_step="Return to main menu",
    ),
    "Q": MenuItem(
        key="Q",
        name="Quit",
        category="",
        title="EXIT",
        subtitle="Terminate Session",
        description=[
            "Exit PUPPETMASTER and return to terminal.",
        ],
        next_step="",
    ),
}


# =============================================================================
# UI STATE
# =============================================================================

@dataclass
class UIState:
    """Current UI state"""
    selected_index: int = 0

    # Live stats
    queue_count: int = 0
    scan_count: int = 0
    cluster_count: int = 0
    blacklist_count: int = 231

    # Status
    status: str = "STANDBY"

    # Progress (0-100)
    discover_progress: int = 0
    scan_progress: int = 0
    analyze_progress: int = 0

    # Feature flags
    show_kali: bool = False
    scan_mode: str = "STANDARD"

    # Input buffer for command line display
    input_buffer: str = ""

    # Animation frame counter
    anim_frame: int = 0

    # Banner rotation (switches every 6 seconds)
    banner_mode: int = 0  # 0 = text art, 1+ = pixel art variants
    banner_switch_time: float = field(default_factory=time.time)

    # Menu keys (built dynamically)
    menu_keys: List[str] = field(default_factory=list)

    def __post_init__(self):
        self._rebuild_menu()

    def _rebuild_menu(self):
        """Build menu key list based on current state"""
        self.menu_keys = ["01", "02", "03", "04", "12", "05", "06", "11"]
        if self.show_kali:
            self.menu_keys.extend(["K1", "K2", "K3", "K4", "K5"])
        self.menu_keys.extend(["07", "08", "09", "10", "Q"])

    @property
    def selected_key(self) -> str:
        if 0 <= self.selected_index < len(self.menu_keys):
            return self.menu_keys[self.selected_index]
        return "01"

    def move_up(self):
        # Loop to bottom when at top
        if self.selected_index <= 0:
            self.selected_index = len(self.menu_keys) - 1
        else:
            self.selected_index -= 1

    def move_down(self):
        # Loop to top when at bottom
        if self.selected_index >= len(self.menu_keys) - 1:
            self.selected_index = 0
        else:
            self.selected_index += 1


# =============================================================================
# KEYBOARD INPUT
# =============================================================================
def get_key() -> str:
    """Get a single keypress using non-canonical mode (like ncurses)"""
    import termios
    import tty
    import select

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        # Set to cbreak mode (like ncurses) - not full raw
        # This properly handles escape sequences
        new_settings = termios.tcgetattr(fd)
        new_settings[3] = new_settings[3] & ~(termios.ICANON | termios.ECHO)
        new_settings[6][termios.VMIN] = 1   # Minimum 1 char
        new_settings[6][termios.VTIME] = 0  # No timeout for first char
        termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)

        ch = sys.stdin.read(1)

        # Handle escape sequences
        if ch == '\x1b':
            # Switch to short timeout mode to read rest of sequence
            new_settings[6][termios.VMIN] = 0   # Don't require chars
            new_settings[6][termios.VTIME] = 1  # 0.1 second timeout
            termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)

            seq = sys.stdin.read(2)  # Read up to 2 more chars

            result = None
            if seq == '[A':
                result = 'UP'
            elif seq == '[B':
                result = 'DOWN'
            elif seq == '[C':
                result = 'RIGHT'
            elif seq == '[D':
                result = 'LEFT'
            elif seq.startswith('['):
                # Some other escape sequence - consume any remaining
                while select.select([sys.stdin], [], [], 0)[0]:
                    extra = sys.stdin.read(1)
                    if not extra:
                        break
                result = 'ESC'
            else:
                result = 'ESC'

            # Drain buffered repeats when arrow key is held down
            # This prevents escape sequence artifacts
            if result in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
                # Drain only immediate repeats with very short timeout
                drained = 0
                max_drain = 10
                while drained < max_drain and select.select([sys.stdin], [], [], 0.001)[0]:
                    peek = sys.stdin.read(1)
                    if peek == '\x1b':
                        # Read and discard the rest of this escape sequence
                        sys.stdin.read(2)
                    drained += 1

            return result

        # Backspace
        if ch in ('\x7f', '\x08'):
            return 'BACKSPACE'

        return ch

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# =============================================================================
# CYBERPUNK HUD
# =============================================================================
class CyberpunkHUD:
    """
    Cyberpunk Terminal HUD for PUPPETMASTER
    Full-featured dashboard with two-column layout
    """

    def __init__(
        self,
        show_kali: bool = False,
        stats_callback: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.console = Console(
            force_terminal=True,
            force_interactive=False,
            highlight=False,
            soft_wrap=False
        )
        self.state = UIState(show_kali=show_kali)
        self.stats_callback = stats_callback
        self._running = False

        # Initialize psutil CPU monitoring - first call returns 0/garbage,
        # but subsequent interval=0 calls will return accurate percentages
        try:
            import psutil
            psutil.cpu_percent(interval=None)  # Initialize CPU tracking
        except Exception:
            pass

    def update_stats(self):
        """Update state from stats callback"""
        if self.stats_callback:
            try:
                stats = self.stats_callback()
                self.state.queue_count = stats.get('queue_count', 0)
                self.state.scan_count = stats.get('scan_count', 0)
                self.state.cluster_count = stats.get('cluster_count', 0)
                self.state.blacklist_count = stats.get('blacklist_count', 231)
                self.state.status = stats.get('status', 'STANDBY')
                self.state.scan_mode = stats.get('scan_mode', 'STANDARD')
                self.state.discover_progress = stats.get('discover_progress', 0)
                self.state.scan_progress = stats.get('scan_progress', 0)
                self.state.analyze_progress = stats.get('analyze_progress', 0)

                new_show_kali = stats.get('show_kali', False)
                if new_show_kali != self.state.show_kali:
                    self.state.show_kali = new_show_kali
                    self.state._rebuild_menu()
            except Exception:
                pass

    def _progress_bar(self, percent: int, width: int = 6) -> str:
        """Create a progress bar string"""
        filled = int(width * percent / 100)
        empty = width - filled
        return "█" * filled + "░" * empty

    def _get_system_vitals(self) -> Dict[str, int]:
        """Get CPU, memory, and disk usage percentages"""
        vitals = {'cpu': 0, 'mem': 0, 'disk': 0, 'has_psutil': False}

        try:
            # Try psutil first (most accurate)
            # Use interval=0.1 for accurate CPU reading (100ms sample)
            import psutil
            vitals['cpu'] = int(psutil.cpu_percent(interval=0.1))
            vitals['mem'] = int(psutil.virtual_memory().percent)
            vitals['disk'] = int(psutil.disk_usage('/').percent)
            vitals['has_psutil'] = True
            return vitals
        except ImportError:
            pass  # psutil not installed
        except Exception:
            pass  # other error

        # Fallback to reading /proc on Linux
        try:
            # CPU - read /proc/stat
            with open('/proc/stat', 'r') as f:
                line = f.readline()
                parts = line.split()
                if parts[0] == 'cpu':
                    idle = int(parts[4])
                    total = sum(int(x) for x in parts[1:])
                    vitals['cpu'] = int(100 * (1 - idle / total)) if total > 0 else 0
        except Exception:
            pass

        try:
            # Memory - read /proc/meminfo
            with open('/proc/meminfo', 'r') as f:
                mem_total = mem_avail = 0
                for line in f:
                    if line.startswith('MemTotal:'):
                        mem_total = int(line.split()[1])
                    elif line.startswith('MemAvailable:'):
                        mem_avail = int(line.split()[1])
                if mem_total > 0:
                    vitals['mem'] = int(100 * (1 - mem_avail / mem_total))
        except Exception:
            pass

        try:
            # Disk - use os.statvfs
            stat = os.statvfs('/')
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            if total > 0:
                vitals['disk'] = int(100 * (1 - free / total))
        except Exception:
            pass

        return vitals

    def render_system_vitals(self) -> Panel:
        """Render the SYSTEM VITALS panel"""
        vitals = self._get_system_vitals()

        text = Text()

        # CPU
        cpu_color = Colors.BRIGHT_GREEN if vitals['cpu'] < 70 else (Colors.BRIGHT_YELLOW if vitals['cpu'] < 90 else Colors.BRIGHT_RED)
        text.append("  CPU  [", style=Colors.GREY)
        text.append(self._progress_bar(vitals['cpu'], 16), style=cpu_color)
        text.append(f"] {vitals['cpu']:3d}%\n", style=Colors.TEXT)

        # Memory
        mem_color = Colors.BRIGHT_GREEN if vitals['mem'] < 70 else (Colors.BRIGHT_YELLOW if vitals['mem'] < 90 else Colors.BRIGHT_RED)
        text.append("  MEM  [", style=Colors.GREY)
        text.append(self._progress_bar(vitals['mem'], 16), style=mem_color)
        text.append(f"] {vitals['mem']:3d}%\n", style=Colors.TEXT)

        # Disk
        disk_color = Colors.BRIGHT_GREEN if vitals['disk'] < 80 else (Colors.BRIGHT_YELLOW if vitals['disk'] < 95 else Colors.BRIGHT_RED)
        text.append("  DISK [", style=Colors.GREY)
        text.append(self._progress_bar(vitals['disk'], 16), style=disk_color)
        text.append(f"] {vitals['disk']:3d}%", style=Colors.TEXT)

        # Show hint if psutil not installed
        if not vitals.get('has_psutil', False):
            text.append("\n  ", style=Colors.DARK_GREY)
            text.append("pip install psutil", style="dim italic")

        return Panel(
            text,
            title="[bold magenta]SYSTEM VITALS[/]",
            title_align="left",
            border_style=Colors.BRIGHT_MAGENTA,
            padding=(0, 0),
            width=62,
        )

    def render_scan_queue(self) -> Panel:
        """Render the SCAN QUEUE panel"""
        text = Text()

        # Get pending domains from stats if available
        pending_domains = []
        status = self.state.status
        if self.stats_callback:
            try:
                stats = self.stats_callback()
                pending_domains = stats.get('pending_domains', [])[:5]  # Show max 5
                status = stats.get('status', status)
            except Exception:
                pass

        queue_count = self.state.queue_count

        if queue_count > 0 or pending_domains:
            count = queue_count if queue_count > 0 else len(pending_domains)
            # Different message based on status
            if status == 'READY':
                text.append(f"  {count} domain{'s' if count != 1 else ''} ready\n", style=Colors.BRIGHT_GREEN)
                text.append(f"  Use [3] to start scanning\n", style=Colors.GREY)
            else:
                text.append(f"  {count} domain{'s' if count != 1 else ''} pending\n", style=Colors.BRIGHT_YELLOW)

            for domain in pending_domains[:4]:
                text.append(f"  > {domain[:35]}\n", style=Colors.GREY)

            if count > 4:
                text.append(f"  ... and {count - 4} more", style=Colors.MUTED)
        else:
            text.append("  Queue empty\n", style=Colors.MUTED)
            text.append("  Use [1] or [2] to add domains", style=Colors.DARK_GREY)

        return Panel(
            text,
            title="[bold yellow]SCAN QUEUE[/]",
            title_align="left",
            border_style=Colors.BRIGHT_YELLOW,
            padding=(0, 0),
            width=62,
        )

    def render_banner(self) -> Panel:
        """Render animated PUPPETMASTER banner - switches based on menu position"""
        frame = self.state.anim_frame

        # Switch banner based on menu position (every 8 menu items)
        self.state.banner_mode = (self.state.selected_index // 8) % 10
        text = Text()

        # Colors for animation
        colors = [
            Colors.BRIGHT_CYAN,
            Colors.BRIGHT_GREEN,
            Colors.BRIGHT_YELLOW,
            Colors.BRIGHT_MAGENTA,
            Colors.BRIGHT_RED,
            Colors.BRIGHT_BLUE,
        ]

        if self.state.banner_mode == 0:
            # Mode 0: PUPPETMASTER text art
            art = [
                "  ██████╗ ██╗   ██╗██████╗ ██████╗ ███████╗████████╗",
                "  ██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔════╝╚══██╔══╝",
                "  ██████╔╝██║   ██║██████╔╝██████╔╝█████╗     ██║   ",
                "  ██╔═══╝ ██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝     ██║   ",
                "  ██║     ╚██████╔╝██║     ██║     ███████╗   ██║   ",
                "  ╚═╝      ╚═════╝ ╚═╝     ╚═╝     ╚══════╝   ╚═╝   ",
                "    ███╗   ███╗ █████╗ ███████╗████████╗███████╗██████╗ ",
                "    ████╗ ████║██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗",
                "    ██╔████╔██║███████║███████╗   ██║   █████╗  ██████╔╝",
                "    ██║╚██╔╝██║██╔══██║╚════██║   ██║   ██╔══╝  ██╔══██╗",
                "    ██║ ╚═╝ ██║██║  ██║███████║   ██║   ███████╗██║  ██║",
                "    ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝",
                "",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        elif self.state.banner_mode == 1:
            # Mode 1: Marionette controller with puppets
            art = [
                "              ╔══════════════════════════════════╗              ",
                "              ║  ┌────────────────────────────┐  ║              ",
                "              ║  │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│  ║              ",
                "              ╚══╪════════════════════════════╪══╝              ",
                "      ┌──────────┼──────────┬─────────────────┼──────────┐      ",
                "      │          │          │                 │          │      ",
                "      │          │          │                 │          │      ",
                "     ╱╲         ╱╲         ╱╲                ╱╲         ╱╲      ",
                "    ╱██╲       ╱██╲       ╱██╲              ╱██╲       ╱██╲     ",
                "    │██│       │██│       │██│              │██│       │██│     ",
                "   ╱╲  ╱╲     ╱╲  ╱╲     ╱╲  ╱╲            ╱╲  ╱╲     ╱╲  ╱╲    ",
                "  ╱  ╲╱  ╲   ╱  ╲╱  ╲   ╱  ╲╱  ╲          ╱  ╲╱  ╲   ╱  ╲╱  ╲   ",
                "",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        elif self.state.banner_mode == 2:
            # Mode 2: Spider in web (SpiderFoot theme)
            art = [
                "          ╲                 │                 ╱          ",
                "            ╲    ╲          │          ╱    ╱            ",
                "              ╲    ╲        │        ╱    ╱              ",
                "        ────────╲────╲──────┼──────╱────╱────────        ",
                "                  ╲   ╲     │     ╱   ╱                  ",
                "        ────────────╲──╲────┼────╱──╱────────────        ",
                "                      ╲ ╲ ╔═╧═╗ ╱ ╱                      ",
                "        ────────────────╲─╢█▓█╟─╱────────────────        ",
                "                        ╱ ╚═╤═╝ ╲                        ",
                "        ────────────╱──╱────┼────╲──╲────────────        ",
                "                  ╱   ╱     │     ╲   ╲                  ",
                "        ────────╱────╱──────┼──────╲────╲────────        ",
                "",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        elif self.state.banner_mode == 3:
            # Mode 3: All-seeing eye / pyramid
            art = [
                "                           ╱╲                           ",
                "                          ╱  ╲                          ",
                "                         ╱ ▄▄ ╲                         ",
                "                        ╱ █▀▀█ ╲                        ",
                "                       ╱  █▄▄█  ╲                       ",
                "                      ╱ ▀▀▀▀▀▀▀▀ ╲                      ",
                "                     ╱            ╲                     ",
                "                    ╱   ░░░░░░░░   ╲                    ",
                "                   ╱  ░░░░░░░░░░░░  ╲                   ",
                "                  ╱ ░░░░░░░░░░░░░░░░ ╲                  ",
                "                 ╱░░░░░░░░░░░░░░░░░░░░╲                 ",
                "                ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀                ",
                "",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        elif self.state.banner_mode == 4:
            # Mode 4: Workflow diagram
            art = [
                "    ┌─────────┐      ┌─────────┐      ┌─────────┐       ",
                "    │ DOMAINS │ ───▶ │  SCAN   │ ───▶ │ ANALYZE │       ",
                "    │  [1][2] │      │   [3]   │      │   [5]   │       ",
                "    └─────────┘      └─────────┘      └────┬────┘       ",
                "         │                                 │            ",
                "         │                                 ▼            ",
                "         │              ┌─────────────────────────┐     ",
                "         │              │    PUPPET CLUSTERS      │     ",
                "         │              │  ┌───┐ ┌───┐ ┌───┐     │     ",
                "         │              │  │ A │ │ B │ │ C │ ... │     ",
                "         │              │  └───┘ └───┘ └───┘     │     ",
                "         └────────────▶ │      VIEW [6]          │     ",
                "                        └─────────────────────────┘     ",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        elif self.state.banner_mode == 5:
            # Mode 5: Sock puppet masks metaphor
            art = [
                "       ╭─────╮    ╭─────╮    ╭─────╮    ╭─────╮         ",
                "      ╱ ◠  ◠ ╲  ╱ ◡  ◡ ╲  ╱ ─  ─ ╲  ╱ ◠  ◠ ╲        ",
                "      │   ◡   │  │   ◠   │  │   ○   │  │   ◡   │        ",
                "      ╰───────╯  ╰───────╯  ╰───────╯  ╰───────╯        ",
                "          │          │          │          │            ",
                "          │          │          │          │            ",
                "          ╰──────────┴──────────┴──────────╯            ",
                "                         │                              ",
                "                    ╔════╧════╗                         ",
                "                    ║ ◉    ◉ ║                         ",
                "                    ║    ▽    ║                         ",
                "                    ║  ╰───╯  ║                         ",
                "                    ╚═════════╝                         ",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        elif self.state.banner_mode == 6:
            # Mode 6: Flipper-style dolphin
            art = [
                "                                                        ",
                "                         ▄▄▄▄▄▄                         ",
                "                      ▄██▀▀▀▀▀▀██▄                      ",
                "                    ▄██▀  ▄▄    ▀██▄▄▄▄                 ",
                "              ▄▄▄▄██▀   ▄████▄     ▀▀▀██▄▄              ",
                "           ▄██▀▀▀▀    ▄██▀▀▀▀██▄        ▀██▄            ",
                "          ██▀       ▄██   ●   ██▄        ▀██            ",
                "         ██       ▄██▀         ▀██▄       ██▄           ",
                "        ██▀▀▀▀▀▀▀██    ╲▂▂▂╱    ██▀▀▀▀▀▀▀▀██           ",
                "        ▀██▄▄▄▄▄██▀             ▀██▄▄▄▄▄▄██▀           ",
                "           ▀▀▀▀▀▀                 ▀▀▀▀▀▀▀              ",
                "                                                        ",
                "",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        elif self.state.banner_mode == 7:
            # Mode 7: Geometric hexagon network
            art = [
                "              ╱╲              ╱╲              ╱╲        ",
                "             ╱  ╲            ╱  ╲            ╱  ╲       ",
                "            ╱    ╲──────────╱    ╲──────────╱    ╲      ",
                "            ╲    ╱          ╲    ╱          ╲    ╱      ",
                "             ╲  ╱            ╲  ╱            ╲  ╱       ",
                "              ╲╱──────────────╲╱──────────────╲╱        ",
                "              ╱╲              ╱╲              ╱╲        ",
                "             ╱  ╲            ╱  ╲            ╱  ╲       ",
                "            ╱    ╲──────────╱ ▓▓ ╲──────────╱    ╲      ",
                "            ╲    ╱          ╲ ▓▓ ╱          ╲    ╱      ",
                "             ╲  ╱            ╲  ╱            ╲  ╱       ",
                "              ╲╱──────────────╲╱──────────────╲╱        ",
                "",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        elif self.state.banner_mode == 8:
            # Mode 8: SIGNAL//NOISE - Wildcard DNS Analyzer
            art = [
                "  ███████╗██╗ ██████╗ ███╗   ██╗ █████╗ ██╗            ",
                "  ██╔════╝██║██╔════╝ ████╗  ██║██╔══██╗██║            ",
                "  ███████╗██║██║  ███╗██╔██╗ ██║███████║██║            ",
                "  ╚════██║██║██║   ██║██║╚██╗██║██╔══██║██║            ",
                "  ███████║██║╚██████╔╝██║ ╚████║██║  ██║███████╗       ",
                "  ╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝       ",
                "        ██╗██╗███╗   ██╗ ██████╗ ██╗███████╗███████╗   ",
                "       ██╔╝██╔╝████╗  ██║██╔═══██╗██║██╔════╝██╔════╝   ",
                "      ██╔╝██╔╝ ██╔██╗ ██║██║   ██║██║███████╗█████╗     ",
                "     ██╔╝██╔╝  ██║╚██╗██║██║   ██║██║╚════██║██╔══╝     ",
                "    ██╔╝██╔╝   ██║ ╚████║╚██████╔╝██║███████║███████╗   ",
                "    ╚═╝ ╚═╝    ╚═╝  ╚═══╝ ╚═════╝ ╚═╝╚══════╝╚══════╝   ",
                "",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        elif self.state.banner_mode == 9:
            # Mode 9: WILDCARD HUNTER
            art = [
                "  ██╗    ██╗██╗██╗     ██████╗  ██████╗ █████╗ ██████╗ ██████╗ ",
                "  ██║    ██║██║██║     ██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔══██╗",
                "  ██║ █╗ ██║██║██║     ██║  ██║██║     ███████║██████╔╝██║  ██║",
                "  ██║███╗██║██║██║     ██║  ██║██║     ██╔══██║██╔══██╗██║  ██║",
                "  ╚███╔███╔╝██║███████╗██████╔╝╚██████╗██║  ██║██║  ██║██████╔╝",
                "   ╚══╝╚══╝ ╚═╝╚══════╝╚═════╝  ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ",
                "         ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗   ",
                "         ██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗  ",
                "         ███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝  ",
                "         ██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗  ",
                "         ██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║  ",
                "         ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝  ",
                "",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        else:
            # Fallback to Mode 0 for any other value
            art = [
                "  ██████╗ ██╗   ██╗██████╗ ██████╗ ███████╗████████╗",
                "  ██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔════╝╚══██╔══╝",
                "  ██████╔╝██║   ██║██████╔╝██████╔╝█████╗     ██║   ",
                "  ██╔═══╝ ██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝     ██║   ",
                "  ██║     ╚██████╔╝██║     ██║     ███████╗   ██║   ",
                "  ╚═╝      ╚═════╝ ╚═╝     ╚═╝     ╚══════╝   ╚═╝   ",
                "    ███╗   ███╗ █████╗ ███████╗████████╗███████╗██████╗ ",
                "    ████╗ ████║██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗",
                "    ██╔████╔██║███████║███████╗   ██║   █████╗  ██████╔╝",
                "    ██║╚██╔╝██║██╔══██║╚════██║   ██║   ██╔══╝  ██╔══██╗",
                "    ██║ ╚═╝ ██║██║  ██║███████║   ██║   ███████╗██║  ██║",
                "    ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝",
                "",
            ]
            for i, line in enumerate(art):
                color_idx = (frame + i) % len(colors)
                text.append(line + "\n", style=colors[color_idx])

        return Panel(
            text,
            border_style=Colors.DARK_GREY,
            padding=(0, 0),
            width=62,
        )

    def render_status_bar(self) -> Panel:
        """Render the status bar with mission stats"""
        status_color = {
            "STANDBY": Colors.STANDBY,
            "READY": Colors.BRIGHT_GREEN,  # Domains loaded, ready to scan
            "SCANNING": Colors.SCANNING,
            "ANALYZING": Colors.ANALYZING,
        }.get(self.state.status, Colors.TEXT)

        text = Text()
        # Mission stats
        text.append("MISSION STATUS  ", style=Colors.MUTED)
        text.append(f"Q:{self.state.queue_count}", style=Colors.TEXT)
        text.append(f" {self._progress_bar(min(100, self.state.queue_count * 10))}  ", style=Colors.BRIGHT_BLUE)
        text.append(f"S:{self.state.scan_count}", style=Colors.TEXT)
        text.append(f" {self._progress_bar(min(100, self.state.scan_count * 2))}  ", style=Colors.BRIGHT_GREEN)
        text.append(f"C:{self.state.cluster_count}", style=Colors.TEXT)
        text.append(f" {self._progress_bar(min(100, self.state.cluster_count * 15))}  ", style=Colors.BRIGHT_YELLOW)
        text.append(f"BL:{self.state.blacklist_count}", style=Colors.TEXT)
        text.append("  ", style=Colors.MUTED)
        text.append(f"[{self.state.status}]", style=status_color)

        # Progress section
        text.append("    PROGRESS  ", style=Colors.MUTED)
        text.append("DISC", style=Colors.TEXT)
        text.append(self._progress_bar(self.state.discover_progress), style=Colors.BRIGHT_BLUE)
        text.append(" SCAN", style=Colors.TEXT)
        text.append(self._progress_bar(self.state.scan_progress), style=Colors.BRIGHT_GREEN)
        text.append(" ANLZ", style=Colors.TEXT)
        text.append(self._progress_bar(self.state.analyze_progress), style=Colors.BRIGHT_YELLOW)

        return Panel(text, border_style=Colors.BORDER, padding=(0, 1), width=108)

    def render_loadout(self) -> Panel:
        """Render the LOADOUT menu panel"""
        text = Text()

        categories = [
            ("DISCOVERY & SCANNING", ["01", "02", "03", "04", "12"]),
            ("ANALYSIS", ["05", "06", "11"]),
        ]
        if self.state.show_kali:
            categories.append(("KALI TOOLS", ["K1", "K2", "K3", "K4", "K5"]))
        categories.append(("SETTINGS", ["07", "08", "09", "10"]))

        for cat_name, keys in categories:
            text.append(f"\n  {cat_name}\n", style=Colors.BRIGHT_BLUE)
            text.append(f"  {'─' * len(cat_name)}\n", style=Colors.DARK_GREY)

            for key in keys:
                item = MENU_ITEMS.get(key)
                if not item:
                    continue

                is_selected = key == self.state.selected_key

                # Build display name
                display = item.name
                if key == "K2":
                    display = f"Scan mode [{self.state.scan_mode}]"
                elif key == "K4":
                    display = f"Blacklist ({self.state.blacklist_count})"

                if is_selected:
                    text.append(f"  >[{key}] ", style=f"bold {Colors.SELECTED}")
                    text.append(f"{display}\n", style=f"bold {Colors.SELECTED}")
                else:
                    text.append(f"   [{key}] ", style=Colors.BRIGHT_YELLOW)
                    text.append(f"{display}\n", style=Colors.TEXT)

        # Quit option
        text.append("\n")
        if self.state.selected_key == "Q":
            text.append(f"  >[Q] ", style=f"bold {Colors.SELECTED}")
            text.append(f"Quit\n", style=f"bold {Colors.SELECTED}")
        else:
            text.append(f"   [Q] ", style=Colors.BRIGHT_YELLOW)
            text.append(f"Quit\n", style=Colors.TEXT)

        return Panel(
            text,
            title="[bold green]LOADOUT[/]",
            title_align="left",
            border_style=Colors.BRIGHT_GREEN,
            width=44,
            padding=(0, 0),
        )

    def render_description(self) -> Panel:
        """Render the PuppetMaster description panel below LOADOUT"""
        text = Text()
        text.append("PUPPETMASTER", style=f"bold {Colors.BRIGHT_CYAN}")
        text.append(" is an end-to-end tool\n", style=Colors.TEXT)
        text.append("to discover ", style=Colors.TEXT)
        text.append("Sock Puppet Domains", style=f"bold {Colors.BRIGHT_YELLOW}")
        text.append(".\n\n", style=Colors.TEXT)
        text.append("Build domain lists, scan them with\n", style=Colors.GREY)
        text.append("SpiderFoot, and analyze with ", style=Colors.GREY)
        text.append("[5]", style=Colors.BRIGHT_GREEN)
        text.append(" to\n", style=Colors.GREY)
        text.append("uncover possible puppet clusters.", style=Colors.GREY)

        return Panel(
            text,
            border_style=Colors.DARK_GREY,
            width=44,
            padding=(0, 1),
        )

    def render_mission(self) -> Panel:
        """Render the ACTIVE MISSION description panel - fixed height"""
        FIXED_HEIGHT = 14  # Fixed number of content lines

        item = MENU_ITEMS.get(self.state.selected_key)
        if not item:
            text = Text()
            text.append("\n  Select an option to view details\n", style=Colors.MUTED)
            # Pad to fixed height
            for _ in range(FIXED_HEIGHT - 2):
                text.append("\n")
            return Panel(text, title="[bold cyan]ACTIVE MISSION[/]", border_style=Colors.BORDER)

        lines = []
        lines.append("")  # Top padding
        lines.append(f"  [{item.key}] {item.title}")
        lines.append(f"  {item.subtitle}")
        lines.append("")

        for line in item.description:
            lines.append(f"  {line}")

        if item.next_step:
            lines.append("")
            lines.append(f"  {'─' * 50}")
            lines.append(f"  NEXT: {item.next_step}")

        # Pad to fixed height
        while len(lines) < FIXED_HEIGHT:
            lines.append("")

        # Build styled text
        text = Text()
        for i, line in enumerate(lines[:FIXED_HEIGHT]):
            if i == 1:  # Title line
                text.append(line + "\n", style=f"bold {Colors.BRIGHT_GREEN}")
            elif i == 2:  # Subtitle
                text.append(line + "\n", style=Colors.BRIGHT_CYAN)
            elif line.strip().startswith("-"):
                # Bullet points - colorful
                text.append(line + "\n", style=Colors.BRIGHT_YELLOW)
            elif line.strip().startswith("NEXT:"):
                text.append(line + "\n", style=f"bold {Colors.BRIGHT_MAGENTA}")
            elif "─" in line:
                text.append(line + "\n", style=Colors.DARK_GREY)
            else:
                text.append(line + "\n", style=Colors.TEXT)

        return Panel(
            text,
            title="[bold cyan]ACTIVE MISSION[/]",
            title_align="left",
            border_style=Colors.BRIGHT_CYAN,
            padding=(0, 0),
            width=62,
        )

    def render_tips(self) -> Panel:
        """Render tips panel"""
        text = Text()
        text.append("TIP: ", style=f"bold {Colors.BRIGHT_CYAN}")
        text.append("New here? Press ", style=Colors.GREY)
        text.append("[8]", style=Colors.BRIGHT_YELLOW)
        text.append(" for full tactical manual.\n", style=Colors.GREY)
        text.append("TIP: ", style=f"bold {Colors.BRIGHT_CYAN}")
        text.append("Long scans? Press ", style=Colors.GREY)
        text.append("[9]", style=Colors.BRIGHT_YELLOW)
        text.append(" for tmux (survives disconnects)", style=Colors.GREY)

        return Panel(text, border_style=Colors.DARK_GREY, padding=(0, 1), width=108)

    def render_controls(self) -> Panel:
        """Render keyboard controls panel"""
        text = Text()
        text.append("DEPLOY ", style=Colors.BRIGHT_GREEN)
        text.append("[ENTER]    ", style=Colors.TEXT)
        text.append("SELECT ", style=Colors.BRIGHT_BLUE)
        text.append("[UP/DOWN]    ", style=Colors.TEXT)
        text.append("DIRECT ", style=Colors.BRIGHT_YELLOW)
        text.append("[1-9/K1-K5]    ", style=Colors.TEXT)
        text.append("EXIT ", style=Colors.BRIGHT_RED)
        text.append("[Q]    ", style=Colors.TEXT)
        text.append("[R]", style=Colors.DARK_GREY)

        return Panel(text, border_style=Colors.DARK_GREY, padding=(0, 1), width=108)

    def render_input_line(self) -> Panel:
        """Render the command input line at the bottom"""
        text = Text()
        text.append("CMD> ", style=f"bold {Colors.BRIGHT_GREEN}")
        if self.state.input_buffer:
            text.append(self.state.input_buffer, style=f"bold {Colors.BRIGHT_YELLOW}")
        text.append("_", style=f"bold blink {Colors.BRIGHT_GREEN}")

        return Panel(text, border_style=Colors.BRIGHT_GREEN, padding=(0, 1), width=108)

    def render(self):
        """Render the full HUD using Layout for proper grid"""
        # Setup alternate screen buffer on first render
        if not hasattr(self, '_rendered_once'):
            # Enter alternate screen buffer (like tmux/vim)
            sys.stdout.write('\033[?1049h')
            # Hide cursor
            sys.stdout.write('\033[?25l')
            sys.stdout.flush()
            self._rendered_once = True
            self._last_state = None

        # Increment animation frame (for color cycling)
        self.state.anim_frame = (self.state.anim_frame + 1) % 100

        # Check if state changed - only redraw if needed
        # Note: anim_frame NOT included since we use menu-position-based banners
        current_state = (
            self.state.selected_index,
            self.state.input_buffer,
            self.state.status,
            self.state.queue_count,
            self.state.scan_count,
        )

        if current_state == self._last_state:
            return  # Nothing changed, don't redraw

        self._last_state = current_state

        # Move cursor to home without clearing (alternate buffer is already clean)
        sys.stdout.write('\033[H')
        sys.stdout.flush()

        # Fixed layout width (left 46 + right 62 = 108)
        # Right column needs 62 to fit PUPPETMASTER banner (~58 chars + borders)
        LAYOUT_WIDTH = 108

        # Status bar (fixed width)
        self.console.print(self.render_status_bar())

        # Build the main layout using Rich Layout
        layout = Layout(size=LAYOUT_WIDTH)

        # Main content area with left/right split
        layout.split_row(
            Layout(name="left", size=46),  # Fixed width for loadout
            Layout(name="right", size=62),  # Fixed width for right column (banner needs ~58)
        )

        # Left column: LOADOUT + DESCRIPTION stacked
        layout["left"].split_column(
            Layout(name="loadout", ratio=3),
            Layout(name="desc", ratio=1),
        )
        layout["left"]["loadout"].update(self.render_loadout())
        layout["left"]["desc"].update(self.render_description())

        # Right column: MISSION + VITALS + QUEUE + BANNER stacked
        layout["right"].split_column(
            Layout(name="mission", size=16),
            Layout(name="vitals", size=5),
            Layout(name="queue", size=5),
            Layout(name="banner", size=15),
        )
        layout["right"]["mission"].update(self.render_mission())
        layout["right"]["vitals"].update(self.render_system_vitals())
        layout["right"]["queue"].update(self.render_scan_queue())
        layout["right"]["banner"].update(self.render_banner())

        # Print the layout with fixed width
        self.console.print(layout, height=42, width=LAYOUT_WIDTH)

        # Bottom panels (fixed width)
        self.console.print(self.render_tips())
        self.console.print(self.render_controls())
        self.console.print(self.render_input_line())

        # Ensure any remaining lines are cleared
        sys.stdout.write('\033[J')
        sys.stdout.flush()

    def handle_key(self, key: str) -> Optional[str]:
        """Handle keypress, return tool key if selected"""
        # Arrow keys for navigation (immediate)
        if key == 'UP':
            self.state.move_up()
            self.state.input_buffer = ""  # Clear buffer on nav
            return None
        elif key == 'DOWN':
            self.state.move_down()
            self.state.input_buffer = ""  # Clear buffer on nav
            return None
        elif key in ('LEFT', 'RIGHT'):
            # Ignore left/right arrows - not used for menu nav
            return None

        # Backspace - clear input buffer
        elif key == 'BACKSPACE':
            if self.state.input_buffer:
                self.state.input_buffer = self.state.input_buffer[:-1]
            return None

        # Enter/Space - execute current selection or buffer
        elif key in ('\r', '\n', ' '):
            if self.state.input_buffer:
                # Try to match buffer to a menu key
                buf = self.state.input_buffer.upper()
                self.state.input_buffer = ""

                # Direct match (e.g., "01", "K1", "Q")
                if buf in self.state.menu_keys:
                    return buf

                # Single digit match (e.g., "1" -> "01")
                if len(buf) == 1 and buf.isdigit():
                    target = f"0{buf}"
                    if target in self.state.menu_keys:
                        return target
                    # Also check for 10
                    if buf == "0" and "10" in self.state.menu_keys:
                        return "10"

                # Invalid input - just clear and continue
                return None
            else:
                # No buffer - execute current selection
                return self.state.selected_key

        # Escape - clear buffer
        elif key == 'ESC':
            self.state.input_buffer = ""
            return None

        # Ctrl+C - quit
        elif key == '\x03':
            return 'Q'

        # R for rickroll easter egg (check before other alphanumeric handling)
        elif key in ('r', 'R'):
            if not self.state.input_buffer:
                self._rickroll()
            return None

        # Q for quit (immediate, no buffer)
        elif key.upper() == 'Q' and not self.state.input_buffer:
            return 'Q'

        # Alphanumeric - add to buffer (max 10 chars to prevent memory issues)
        elif key.isalnum():
            if len(self.state.input_buffer) < 10:
                self.state.input_buffer += key.upper()

            # Auto-navigation: if buffer matches a menu key exactly, highlight it
            buf = self.state.input_buffer.upper()
            if buf in self.state.menu_keys:
                try:
                    idx = self.state.menu_keys.index(buf)
                    self.state.selected_index = idx
                except ValueError:
                    pass
            # Also handle single digits (1-9 -> 01-09)
            elif len(buf) == 1 and buf.isdigit() and buf != "0":
                target = f"0{buf}"
                if target in self.state.menu_keys:
                    try:
                        idx = self.state.menu_keys.index(target)
                        self.state.selected_index = idx
                    except ValueError:
                        pass

            return None

        return None

    def _rickroll(self):
        """Never gonna give you up, never gonna let you down"""
        rick_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ&start_radio=1'

        # Try to open browser (works on local machines with display)
        browser_opened = False
        try:
            # Check if we have a display (Linux/Mac GUI) or are on Windows
            has_display = os.name == 'nt' or os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')
            if has_display:
                browser_opened = webbrowser.open(rick_url)
        except Exception:
            pass

        # Always show ASCII art (works over SSH, and confirms rickroll on local)
        os.system('clear' if os.name != 'nt' else 'cls')
        rick = """
\033[93m
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣤⣤⣤⣤⣤⣶⣦⣤⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⡿⠛⠉⠙⠛⠛⠛⠛⠻⢿⣿⣷⣤⡀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⠋⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⠈⢻⣿⣿⡄⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⣸⣿⡏⠀⠀⠀⣠⣶⣾⣿⣿⣿⠿⠿⠿⢿⣿⣿⣿⣄⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⣿⣿⠁⠀⠀⢰⣿⣿⣯⠁⠀⠀⠀⠀⠀⠀⠀⠈⠙⢿⣷⡄⠀
    ⠀⠀⣀⣤⣴⣶⣶⣿⡟⠀⠀⠀⢸⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣷⠀
    ⠀⢰⣿⡟⠋⠉⣹⣿⡇⠀⠀⠀⠘⣿⣿⣿⣿⣷⣦⣤⣤⣤⣶⣶⣶⣶⣿⣿⣿⠀
    ⠀⢸⣿⡇⠀⠀⣿⣿⡇⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠃⠀
    ⠀⣸⣿⡇⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠉⠻⠿⣿⣿⣿⣿⡿⠿⠿⠛⢻⣿⡇⠀⠀
    ⠀⣿⣿⠁⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣧⠀⠀
    ⠀⣿⣿⠀⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⠀⠀
    ⠀⣿⣿⠀⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⠀⠀
    ⠀⢿⣿⡆⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⡇⠀⠀
    ⠀⠸⣿⣧⡀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⠃⠀⠀
    ⠀⠀⠛⢿⣿⣿⣿⣿⣇⠀⠀⠀⠀⠀⣰⣿⣿⣷⣶⣶⣶⣶⠶⠀⢠⣿⣿⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⣿⣿⠀⠀⠀⠀⠀⣿⣿⡇⠀⣽⣿⡏⠁⠀⠀⢸⣿⡇⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⣿⣿⠀⠀⠀⠀⠀⣿⣿⡇⠀⢹⣿⡆⠀⠀⠀⣸⣿⠇⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⢿⣿⣦⣄⣀⣠⣴⣿⣿⠁⠀⠈⠻⣿⣿⣿⣿⡿⠏⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠈⠛⠻⠿⠿⠿⠿⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀

\033[96m
    ███╗   ██╗███████╗██╗   ██╗███████╗██████╗      ██████╗  ██████╗ ███╗   ██╗███╗   ██╗ █████╗
    ████╗  ██║██╔════╝██║   ██║██╔════╝██╔══██╗    ██╔════╝ ██╔═══██╗████╗  ██║████╗  ██║██╔══██╗
    ██╔██╗ ██║█████╗  ██║   ██║█████╗  ██████╔╝    ██║  ███╗██║   ██║██╔██╗ ██║██╔██╗ ██║███████║
    ██║╚██╗██║██╔══╝  ╚██╗ ██╔╝██╔══╝  ██╔══██╗    ██║   ██║██║   ██║██║╚██╗██║██║╚██╗██║██╔══██║
    ██║ ╚████║███████╗ ╚████╔╝ ███████╗██║  ██║    ╚██████╔╝╚██████╔╝██║ ╚████║██║ ╚████║██║  ██║
    ╚═╝  ╚═══╝╚══════╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═══╝╚═╝  ╚═╝

\033[95m
     ██████╗ ██╗██╗   ██╗███████╗    ██╗   ██╗ ██████╗ ██╗   ██╗    ██╗   ██╗██████╗ ██╗
    ██╔════╝ ██║██║   ██║██╔════╝    ╚██╗ ██╔╝██╔═══██╗██║   ██║    ██║   ██║██╔══██╗██║
    ██║  ███╗██║██║   ██║█████╗       ╚████╔╝ ██║   ██║██║   ██║    ██║   ██║██████╔╝██║
    ██║   ██║██║╚██╗ ██╔╝██╔══╝        ╚██╔╝  ██║   ██║██║   ██║    ██║   ██║██╔═══╝ ╚═╝
    ╚██████╔╝██║ ╚████╔╝ ███████╗       ██║   ╚██████╔╝╚██████╔╝    ╚██████╔╝██║     ██╗
     ╚═════╝ ╚═╝  ╚═══╝  ╚══════╝       ╚═╝    ╚═════╝  ╚═════╝      ╚═════╝ ╚═╝     ╚═╝
\033[0m
\033[93m                    https://www.youtube.com/watch?v=dQw4w9WgXcQ\033[0m
"""
        if browser_opened:
            rick += "\n\033[92m                              Browser opened! Enjoy :)\033[0m\n"
        rick += "\n\033[90m                         Press any key to return...\033[0m\n"

        print(rick)
        get_key()  # Wait for any key

    def _cleanup(self):
        """Restore terminal state on exit"""
        # Show cursor again
        sys.stdout.write('\033[?25h')
        # Exit alternate screen buffer (restore previous screen)
        sys.stdout.write('\033[?1049l')
        sys.stdout.flush()

    def run(self) -> str:
        """Run the HUD loop, return selected tool key"""
        self._running = True
        self.update_stats()

        try:
            while self._running:
                self.render()
                key = get_key()
                result = self.handle_key(key)

                if result is not None:
                    self._cleanup()
                    return result

                self.update_stats()

        except KeyboardInterrupt:
            self._cleanup()
            return 'Q'
        except Exception as e:
            # Don't silently fail - re-raise so caller can see the error
            self._cleanup()
            raise RuntimeError(f"HUD crashed: {e}") from e

        self._cleanup()
        return 'Q'


# =============================================================================
# DEMO
# =============================================================================
def demo():
    """Demo the Cyberpunk HUD"""
    def get_stats():
        return {
            'queue_count': 47,
            'scan_count': 128,
            'cluster_count': 7,
            'blacklist_count': 231,
            'status': 'STANDBY',
            'show_kali': True,
            'scan_mode': 'STANDARD',
            'discover_progress': 60,
            'scan_progress': 100,
            'analyze_progress': 30,
        }

    hud = CyberpunkHUD(show_kali=True, stats_callback=get_stats)
    selected = hud.run()
    print(f"\nSelected: {selected}")


if __name__ == "__main__":
    demo()
