"""
pm_ui_helpers.py - UI Display Helpers

Terminal output utilities: banner, menus, prompts, colors, animations.
"""

import os
import sys
import time
import subprocess
from typing import Optional

try:
    from utils.colors import C
except ImportError:
    class C:
        RESET = '\033[0m'
        BOLD = '\033[1m'
        DIM = '\033[2m'
        UNDERLINE = '\033[4m'
        BLINK = '\033[5m'
        WHITE = '\033[37m'
        BRIGHT_RED = '\033[91m'
        BRIGHT_GREEN = '\033[92m'
        BRIGHT_YELLOW = '\033[93m'
        BRIGHT_BLUE = '\033[94m'
        BRIGHT_MAGENTA = '\033[95m'
        BRIGHT_CYAN = '\033[96m'
        BRIGHT_WHITE = '\033[97m'


def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def is_running_in_tmux() -> bool:
    """Check if we're running inside a tmux session."""
    return 'TMUX' in os.environ


def get_tmux_session_name() -> Optional[str]:
    """Get the current tmux session name if running in tmux."""
    if not is_running_in_tmux():
        return None
    try:
        result = subprocess.run(
            ['tmux', 'display-message', '-p', '#S'],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None


def auto_launch_in_tmux(session_name: str = "puppetmaster", start_menu: str = None) -> bool:
    """
    Re-launch the current script inside a new tmux session.

    This function will:
    1. Check if tmux is installed
    2. Create a new tmux session with the given name
    3. Start puppetmaster inside that session
    4. Attach to the session (so user sees the UI)

    Args:
        session_name: Name for the tmux session
        start_menu: Optional menu to start in ("c2" for distributed scanning menu)

    Returns True if successful, False if tmux not available.
    """
    # Check if tmux is available
    try:
        result = subprocess.run(['which', 'tmux'], capture_output=True, text=True)
        if result.returncode != 0:
            return False
    except Exception:
        return False

    # Get the current script path
    script_path = os.path.abspath(sys.argv[0])

    # Kill any existing session with this name
    subprocess.run(['tmux', 'kill-session', '-t', session_name],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Create new tmux session running puppetmaster
    # Use the same Python interpreter and working directory
    python_path = sys.executable
    cwd = os.getcwd()

    # Build the command to run inside tmux
    # Add --start-menu argument if specified to resume where user left off
    if start_menu:
        cmd = f'cd {cwd} && {python_path} {script_path} --start-menu {start_menu}'
    else:
        cmd = f'cd {cwd} && {python_path} {script_path}'

    # Create and attach to the tmux session
    try:
        # Create session and attach to it
        os.execvp('tmux', ['tmux', 'new-session', '-s', session_name, cmd])
    except Exception as e:
        print(f"Failed to start tmux: {e}")
        return False

    # This line is never reached if execvp succeeds (it replaces the process)
    return True


def print_banner():
    """Print the glorious PUPPETMASTER banner"""
    # Build each line with exact spacing (79 chars inner width)
    W = 79  # inner width

    def pad(text, width=W):
        """Pad text to exact width"""
        return text + " " * (width - len(text))

    # ASCII art lines (raw text without colors for length calculation)
    puppet_art = [
        "\u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2557   \u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557",
        "\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d",
        "\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2588\u2588\u2588\u2557     \u2588\u2588\u2551   ",
        "\u2588\u2588\u2554\u2550\u2550\u2550\u255d \u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2550\u255d \u2588\u2588\u2554\u2550\u2550\u2550\u255d \u2588\u2588\u2554\u2550\u2550\u255d     \u2588\u2588\u2551   ",
        "\u2588\u2588\u2551     \u255a\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2551     \u2588\u2588\u2551     \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557   \u2588\u2588\u2551   ",
        "\u255a\u2550\u255d      \u255a\u2550\u2550\u2550\u2550\u2550\u255d \u255a\u2550\u255d     \u255a\u2550\u255d     \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d   \u255a\u2550\u255d   ",
    ]

    master_art = [
        "\u2588\u2588\u2588\u2557   \u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2557 ",
        "\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557",
        "\u2588\u2588\u2554\u2588\u2588\u2588\u2588\u2554\u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557   \u2588\u2588\u2551   \u2588\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d",
        "\u2588\u2588\u2551\u255a\u2588\u2588\u2554\u255d\u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551\u255a\u2550\u2550\u2550\u2550\u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2554\u2550\u2550\u255d  \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557",
        "\u2588\u2588\u2551 \u255a\u2550\u255d \u2588\u2588\u2551\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2551  \u2588\u2588\u2551",
        "\u255a\u2550\u255d     \u255a\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d   \u255a\u2550\u255d   \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u255d",
    ]

    print(f"{C.BRIGHT_CYAN}\u2554{'═' * W}\u2557")
    print(f"\u2551{' ' * W}\u2551")

    # PUPPET in magenta
    for line in puppet_art:
        content = f"   {C.BRIGHT_MAGENTA}{line}{C.BRIGHT_CYAN}"
        visual_len = 3 + len(line)  # 3 spaces + art
        padding = W - visual_len
        print(f"\u2551{content}{' ' * padding}\u2551")

    print(f"\u2551{' ' * W}\u2551")

    # MASTER in yellow
    for line in master_art:
        content = f"   {C.BRIGHT_YELLOW}{line}{C.BRIGHT_CYAN}"
        visual_len = 3 + len(line)
        padding = W - visual_len
        print(f"\u2551{content}{' ' * padding}\u2551")

    print(f"\u2551{' ' * W}\u2551")

    # Info lines - (text with color codes, visual length without colors)
    info_lines = [
        (f"{C.WHITE}SpiderFoot Sock Puppet Detector v2.0{C.BRIGHT_CYAN}", 36),
        (f"{C.DIM}Vibe coded with Claude | Prompted by deliciousnoodles{C.RESET}{C.BRIGHT_CYAN}", 53),
        (f"{C.WHITE}{C.DIM}\"good morning coffee with bacon egg and cheese\"{C.RESET}{C.BRIGHT_CYAN}", 47),
    ]

    for text, visual_len in info_lines:
        padding = W - 3 - visual_len  # 3 for leading spaces
        print(f"\u2551   {text}{' ' * padding}\u2551")

    print(f"\u2551{' ' * W}\u2551")
    print(f"\u255a{'═' * W}\u255d{C.RESET}")
    print()


def print_section(title, color=None):
    """Print a section header"""
    if color is None:
        color = C.BRIGHT_CYAN
    width = 70
    print(f"\n{color}{'━' * width}")
    print(f"  {C.BOLD}{title}{C.RESET}")
    print(f"{color}{'━' * width}{C.RESET}\n")


def print_menu_item(key, description, icon=""):
    """Print a menu item"""
    print(f"  {C.BRIGHT_YELLOW}[{key}]{C.RESET} {icon} {description}")


def print_success(message):
    """Print a success message"""
    print(f"{C.BRIGHT_GREEN}\u2713 {message}{C.RESET}")


def print_error(message):
    """Print an error message"""
    print(f"{C.BRIGHT_RED}\u2717 {message}{C.RESET}")


def print_warning(message):
    """Print a warning message"""
    print(f"{C.BRIGHT_YELLOW}\u26a0 {message}{C.RESET}")


def print_info(message):
    """Print an info message"""
    print(f"{C.BRIGHT_CYAN}\u2139 {message}{C.RESET}")


def get_input(prompt, default=None, max_length=10000, allow_multiline=False):
    """
    Get user input with a styled prompt.
    Returns None on Ctrl+C/Ctrl+D to signal cancellation.
    Callers should check for None and handle as "user wants to cancel".

    Args:
        allow_multiline: If True, preserve multi-line paste instead of truncating.
                        Used for hostname collection where bulk paste is expected.
    """
    if default:
        prompt_text = f"{C.BRIGHT_MAGENTA}\u25ba {prompt} {C.DIM}[{default}]{C.RESET}: "
    else:
        prompt_text = f"{C.BRIGHT_MAGENTA}\u25ba {prompt}{C.RESET}: "

    try:
        response = input(prompt_text).strip()
        # Protect against paste bombs
        if len(response) > max_length:
            print(f"\n{C.BRIGHT_YELLOW}\u26a0 Input too long ({len(response)} chars). Truncated to {max_length}.{C.RESET}")
            response = response[:max_length]
        # Handle multi-line paste
        if '\n' in response or len(response) > 500:
            line_count = response.count('\n') + 1
            if line_count > 5:
                if allow_multiline:
                    print(f"\n{C.BRIGHT_GREEN}\u2713 Received {line_count} lines.{C.RESET}")
                else:
                    print(f"\n{C.BRIGHT_YELLOW}\u26a0 Detected multi-line paste ({line_count} lines). Using first line only.{C.RESET}")
                    response = response.split('\n')[0].strip()
        return response if response else (default or "")
    except (EOFError, KeyboardInterrupt):
        print()  # Newline after ^C or ^D
        return None  # Signal cancellation


def confirm(prompt, default=True):
    """Ask for yes/no confirmation. Returns False on Ctrl+C."""
    default_str = "Y/n" if default else "y/N"
    response = get_input(f"{prompt} [{default_str}]", "y" if default else "n")
    if response is None:
        return False  # Ctrl+C = cancel = no
    response = response.lower().strip()
    if response == '':
        return default  # Empty = use default
    return response in ('y', 'yes')


def animated_print(message, delay=0.03):
    """Print message with typing animation"""
    for char in message:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def progress_bar(current, total, prefix="Progress", length=40):
    """Display a progress bar"""
    if total <= 0:
        percent = 0
    else:
        percent = current / total
    filled = int(length * percent)
    bar = "\u2588" * filled + "\u2591" * (length - filled)
    print(f"\r{C.BRIGHT_CYAN}{prefix}: [{bar}] {percent*100:.1f}%{C.RESET}", end="", flush=True)
    if current == total and total > 0:
        print()  # New line when complete
