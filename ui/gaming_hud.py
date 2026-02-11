"""
PUPPETMASTER Gaming HUD
SSH/VPS compatible terminal UI using rich library
Designed for 80x24 minimum terminal size
"""

import sys
import os
import shutil
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .colors import COLORS
from .descriptions import TOOL_DESCRIPTIONS


# Minimum terminal size
MIN_WIDTH = 80
MIN_HEIGHT = 24


@dataclass
class UIState:
    """Current state of the UI"""
    selected_index: int = 0

    # Live stats
    queue_count: int = 0
    scan_count: int = 0
    cluster_count: int = 0
    blacklist_count: int = 231

    # Status
    status: str = "STANDBY"

    # Feature flags
    show_kali: bool = False
    scan_mode: str = "STANDARD"

    # Menu keys (built dynamically)
    menu_keys: list = None

    def __post_init__(self):
        if self.menu_keys is None:
            self.menu_keys = self._build_menu_keys()

    def _build_menu_keys(self) -> list:
        keys = ["01", "02", "03", "04", "11", "05", "06", "12"]
        if self.show_kali:
            keys.extend(["K1", "K2", "K3", "K4", "K5"])
        keys.extend(["07", "08", "09", "10", "Q"])
        return keys

    @property
    def selected_key(self) -> str:
        if 0 <= self.selected_index < len(self.menu_keys):
            return self.menu_keys[self.selected_index]
        return "01"


def get_terminal_size():
    """Get terminal size, with fallback"""
    try:
        size = shutil.get_terminal_size()
        return max(size.columns, MIN_WIDTH), max(size.lines, MIN_HEIGHT)
    except Exception:
        return MIN_WIDTH, MIN_HEIGHT


def clear_screen():
    """Clear the terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')


def get_key_simple() -> str:
    """Get a single keypress - simple version for SSH compatibility"""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        # Handle escape sequences (arrow keys)
        if ch == '\x1b':
            # Read potential escape sequence
            import select
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        ch3 = sys.stdin.read(1)
                        if ch3 == 'A': return 'UP'
                        elif ch3 == 'B': return 'DOWN'
            return 'ESC'

        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class GamingHUD:
    """
    SSH-compatible Gaming HUD for PUPPETMASTER
    Works on 80x24 minimum terminals
    """

    def __init__(
        self,
        show_kali: bool = False,
        stats_callback: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.console = Console()
        self.state = UIState(show_kali=show_kali)
        self.stats_callback = stats_callback
        self._running = False
        self._rebuild_menu()

    def _rebuild_menu(self):
        """Rebuild menu keys based on current state"""
        self.state.menu_keys = self.state._build_menu_keys()

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

                new_show_kali = stats.get('show_kali', False)
                if new_show_kali != self.state.show_kali:
                    self.state.show_kali = new_show_kali
                    self._rebuild_menu()
            except Exception:
                pass

    def render_banner(self) -> Panel:
        """Render compact banner"""
        banner = Text()
        banner.append("PUPPETMASTER", style="bold bright_magenta")
        banner.append(" v2.0 | ", style="dim")
        banner.append("SpiderFoot Sock Puppet Detector", style="bright_cyan")

        return Panel(
            banner,
            border_style="bright_cyan",
            padding=(0, 1),
        )

    def render_status_bar(self) -> Panel:
        """Render status bar with stats"""
        status_color = {
            "STANDBY": "yellow",
            "SCANNING": "bright_cyan",
            "ANALYZING": "bright_green",
        }.get(self.state.status, "white")

        text = Text()
        text.append("Q:", style="dim")
        text.append(f"{self.state.queue_count}", style="bright_white")
        text.append("  S:", style="dim")
        text.append(f"{self.state.scan_count}", style="bright_white")
        text.append("  C:", style="dim")
        text.append(f"{self.state.cluster_count}", style="bright_white")
        text.append("  BL:", style="dim")
        text.append(f"{self.state.blacklist_count}", style="bright_white")
        text.append("  ", style="dim")
        text.append(f"[{self.state.status}]", style=status_color)

        return Panel(text, border_style="cyan", padding=(0, 1))

    def render_menu(self) -> Panel:
        """Render the menu with selection highlight"""
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("Key", style="bright_yellow", width=5)
        table.add_column("Option", style="white")

        categories = [
            ("DISCOVERY & SCANNING", ["01", "02", "03", "04", "11"]),
            ("ANALYSIS", ["05", "06", "12"]),
        ]
        if self.state.show_kali:
            categories.append(("KALI TOOLS", ["K1", "K2", "K3", "K4", "K5"]))
        categories.append(("SETTINGS", ["07", "08", "09", "10"]))

        current_idx = 0
        for cat_name, keys in categories:
            table.add_row("", f"[bold bright_cyan]{cat_name}[/]")

            for key in keys:
                tool = TOOL_DESCRIPTIONS.get(key)
                if not tool:
                    continue

                is_selected = current_idx == self.state.selected_index

                # Build display name
                display = tool.short_name
                if key == "K2":
                    display = f"Scan mode [{self.state.scan_mode}]"
                elif key == "K4":
                    display = f"Blacklist ({self.state.blacklist_count})"

                if is_selected:
                    table.add_row(
                        f"[bold white on blue]>{key}[/]",
                        f"[bold white on blue]{tool.emoji} {display}[/]"
                    )
                else:
                    table.add_row(f"[{key}]", f"{tool.emoji} {display}")

                current_idx += 1

            table.add_row("", "")  # Spacing

        # Quit option
        is_quit_selected = current_idx == self.state.selected_index
        if is_quit_selected:
            table.add_row("[bold white on blue]>Q[/]", "[bold white on blue]👋 Quit[/]")
        else:
            table.add_row("[Q]", "👋 Quit")

        return Panel(
            table,
            title="[bold bright_magenta]◢◣ LOADOUT ◢◣[/]",
            border_style="bright_cyan",
            padding=(0, 0),
        )

    def render_description(self) -> Panel:
        """Render description for selected tool"""
        tool = TOOL_DESCRIPTIONS.get(self.state.selected_key)
        if not tool:
            return Panel("Select an option", border_style="cyan")

        text = Text()
        text.append(f"{tool.title}\n", style="bold bright_magenta")
        text.append(f"{tool.subtitle}\n\n", style="bright_cyan")

        for line in tool.description:
            text.append(f"{line}\n", style="white")

        if tool.objectives:
            text.append("\n")
            for obj in tool.objectives:
                text.append(f"• {obj}\n", style="dim white")

        if tool.next_step:
            text.append(f"\n→ {tool.next_step}", style="bright_yellow")

        return Panel(
            text,
            title="[bold bright_magenta]◢◣ MISSION ◢◣[/]",
            border_style="bright_cyan",
            padding=(0, 1),
        )

    def render_help_bar(self) -> Text:
        """Render bottom help bar"""
        text = Text()
        text.append(" [↑↓]", style="bright_yellow")
        text.append(" Navigate  ", style="dim")
        text.append("[ENTER]", style="bright_yellow")
        text.append(" Select  ", style="dim")
        text.append("[1-9]", style="bright_yellow")
        text.append(" Quick  ", style="dim")
        text.append("[Q]", style="bright_yellow")
        text.append(" Quit", style="dim")
        return text

    def render(self):
        """Render the full UI"""
        clear_screen()

        width, height = get_terminal_size()

        # Banner
        self.console.print(self.render_banner())

        # Status bar
        self.console.print(self.render_status_bar())

        # Main content - side by side if wide enough, stacked if narrow
        if width >= 100:
            # Wide terminal - side by side layout
            from rich.columns import Columns
            menu = self.render_menu()
            desc = self.render_description()
            self.console.print(Columns([menu, desc], expand=True))
        else:
            # Narrow terminal - stacked layout
            self.console.print(self.render_menu())
            self.console.print(self.render_description())

        # Help bar
        self.console.print(self.render_help_bar())

    def handle_key(self, key: str) -> Optional[str]:
        """Handle keypress, return tool key if selected"""
        key_lower = key.lower() if len(key) == 1 else key

        if key in ('UP', 'k'):
            self.state.selected_index = max(0, self.state.selected_index - 1)
        elif key in ('DOWN', 'j'):
            self.state.selected_index = min(len(self.state.menu_keys) - 1, self.state.selected_index + 1)
        elif key in ('\r', '\n'):
            return self.state.selected_key
        elif key_lower == 'q':
            return 'Q'
        elif key in '123456789':
            target = f"0{key}"
            if target in self.state.menu_keys:
                return target
        elif key == '0':
            if "10" in self.state.menu_keys:
                return "10"
        elif key == '?':
            return "08"
        elif key == '\x03':  # Ctrl+C
            return 'Q'

        return None

    def run(self) -> str:
        """Run the UI loop, return selected tool key"""
        self._running = True
        self.update_stats()

        while self._running:
            try:
                self.render()
                key = get_key_simple()
                result = self.handle_key(key)

                if result is not None:
                    return result

                self.update_stats()

            except KeyboardInterrupt:
                return 'Q'
            except Exception as e:
                # On any error, return Q to fall back to classic menu
                return 'Q'

        return 'Q'


def demo():
    """Demo the HUD"""
    def get_stats():
        return {
            'queue_count': 47,
            'scan_count': 128,
            'cluster_count': 7,
            'blacklist_count': 231,
            'status': 'STANDBY',
            'show_kali': True,
            'scan_mode': 'STANDARD',
        }

    hud = GamingHUD(show_kali=True, stats_callback=get_stats)
    selected = hud.run()
    print(f"\nSelected: {selected}")


if __name__ == "__main__":
    demo()
