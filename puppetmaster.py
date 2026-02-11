#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ██████╗ ██╗   ██╗██████╗ ██████╗ ███████╗████████╗                         ║
║   ██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔════╝╚══██╔══╝                         ║
║   ██████╔╝██║   ██║██████╔╝██████╔╝█████╗     ██║                            ║
║   ██╔═══╝ ██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝     ██║                            ║
║   ██║     ╚██████╔╝██║     ██║     ███████╗   ██║                            ║
║   ╚═╝      ╚═════╝ ╚═╝     ╚═╝     ╚══════╝   ╚═╝                            ║
║                                                                               ║
║   ███╗   ███╗ █████╗ ███████╗████████╗███████╗██████╗                        ║
║   ████╗ ████║██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗                       ║
║   ██╔████╔██║███████║███████╗   ██║   █████╗  ██████╔╝                       ║
║   ██║╚██╔╝██║██╔══██║╚════██║   ██║   ██╔══╝  ██╔══██╗                       ║
║   ██║ ╚═╝ ██║██║  ██║███████║   ██║   ███████╗██║  ██║                       ║
║   ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝                       ║
║                                                                               ║
║   SpiderFoot Sock Puppet Detector                                            ║
║   "good morning coffee with bacon egg and cheese"                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

PUPPETMASTER - The orchestrator for SpiderFoot Sock Puppet Detection

This tool analyzes SpiderFoot scan exports to identify coordinated networks
of domains (sock puppets) that are likely controlled by the same entity.

Author: Built with Claude
License: MIT
"""

import os
import sys
import subprocess
import time
import shutil
import json
from datetime import datetime
from pathlib import Path

# Enable readline for arrow key support in input() prompts
try:
    import readline  # noqa: F401 - imported for side effects
except ImportError:
    pass  # readline not available on Windows

# =============================================================================
# KALI LINUX INTEGRATION
# =============================================================================
# Try to import Kali module for enhanced features
try:
    from kali.integration import (
        kali_startup_check,
        is_enhanced_mode,
        print_enhanced_menu,
        handle_enhanced_menu_choice,
        get_kali_status_line,
        should_show_kali_menu,
        kali_expand_domains,
    )
    KALI_MODULE_AVAILABLE = True
except ImportError:
    KALI_MODULE_AVAILABLE = False
    def is_enhanced_mode(): return False
    def should_show_kali_menu(): return False
    def get_kali_status_line(): return ""
    def kali_expand_domains(domains, **kwargs): return domains

# =============================================================================
# CYBERPUNK HUD UI
# =============================================================================
# Try to import the new Cyberpunk HUD
try:
    from ui.integration import run_cyberpunk_hud_menu, map_hud_key_to_choice
    CYBERPUNK_HUD_AVAILABLE = True
    _HUD_IMPORT_ERROR = None
except ImportError as e:
    CYBERPUNK_HUD_AVAILABLE = False
    _HUD_IMPORT_ERROR = str(e)

# Try to import cyberpunk UI components for submenus
try:
    from ui.cyberpunk_ui import (
        cyber_header, cyber_menu, cyber_info, cyber_success,
        cyber_warning, cyber_error, cyber_prompt, cyber_confirm,
        cyber_status, cyber_divider, cyber_table, CyberProgress, cyber_wait,
        get_console,
        # Themed banners for submenus
        cyber_banner_discovery, cyber_banner_import, cyber_banner_spider,
        cyber_banner_queue, cyber_banner_analysis, cyber_banner_wildcard,
        cyber_banner_help, cyber_banner_config, cyber_banner_results,
        cyber_banner_kali, cyber_banner_workflow
    )
    CYBER_UI_AVAILABLE = True
except ImportError:
    CYBER_UI_AVAILABLE = False

# Toggle for Cyberpunk UI
USE_CYBERPUNK_HUD = True

# Backwards compatibility
GAMING_HUD_AVAILABLE = CYBERPUNK_HUD_AVAILABLE
USE_GAMING_HUD = USE_CYBERPUNK_HUD

# =============================================================================
# CONFIG FILE - Remember user's output directories
# =============================================================================
CONFIG_FILE = Path(__file__).parent / ".puppetmaster_config.json"

def load_config():
    """Load saved configuration (output directories, etc.)"""
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except Exception:
        pass
    return {"output_dirs": []}

def save_config(config):
    """Save configuration to disk"""
    try:
        CONFIG_FILE.write_text(json.dumps(config, indent=2))
    except Exception:
        pass  # Silently fail if we can't write config

def remember_output_dir(path):
    """Remember an output directory for later retrieval"""
    config = load_config()
    abs_path = str(Path(path).resolve())

    # Add to front of list (most recent first), avoid duplicates
    if abs_path in config["output_dirs"]:
        config["output_dirs"].remove(abs_path)
    config["output_dirs"].insert(0, abs_path)

    # Keep only last 20 directories
    config["output_dirs"] = config["output_dirs"][:20]
    save_config(config)

def get_remembered_output_dirs():
    """Get list of previously used output directories"""
    config = load_config()
    return config.get("output_dirs", [])

# =============================================================================
# DISPLAY UTILITIES - Colors, animations, and fun terminal features
# =============================================================================
# Try to import from shared utils, fall back to local definitions
try:
    from utils.display import (
        C, FunSpinner, SPINNERS, PROGRESS_STYLES, LOADING_ANIMATIONS,
        fun_progress_bar, animated_loading, print_stage_header,
        print_info, print_success, print_warning, print_error,
        animated_print, random_hunting_message, random_completion_message,
        celebrate, HUNTING_MESSAGES, COMPLETION_MESSAGES
    )
except ImportError:
    # Fallback definitions if utils not available
    class Colors:
        RESET = "\033[0m"
        BOLD = "\033[1m"
        DIM = "\033[2m"
        UNDERLINE = "\033[4m"
        BLINK = "\033[5m"
        BLACK = "\033[30m"
        RED = "\033[31m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        BLUE = "\033[34m"
        MAGENTA = "\033[35m"
        CYAN = "\033[36m"
        WHITE = "\033[37m"
        BRIGHT_RED = "\033[91m"
        BRIGHT_GREEN = "\033[92m"
        BRIGHT_YELLOW = "\033[93m"
        BRIGHT_BLUE = "\033[94m"
        BRIGHT_MAGENTA = "\033[95m"
        BRIGHT_CYAN = "\033[96m"
        BRIGHT_WHITE = "\033[97m"
        BG_RED = "\033[41m"
        BG_GREEN = "\033[42m"
        BG_YELLOW = "\033[43m"
        BG_BLUE = "\033[44m"
        BG_MAGENTA = "\033[45m"
        BG_CYAN = "\033[46m"
    C = Colors

    # Minimal fallbacks - local functions defined below will be used
    HUNTING_MESSAGES = ["🔍 Hunting for sock puppets...", "🕵️ Following the breadcrumbs..."]
    COMPLETION_MESSAGES = ["🎉 Analysis complete!", "✨ Puppet strings revealed!"]
    SPINNERS = {'dots': ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']}
    PROGRESS_STYLES = [{'fill': '█', 'empty': '░', 'left': '│', 'right': '│'}]
    LOADING_ANIMATIONS = {'fish': ['><>', ' ><>', '  ><>', '   ><>']}
    FunSpinner = None  # Will use local implementation
    fun_progress_bar = None
    animated_loading = None
    print_stage_header = None
    celebrate = None
    random_hunting_message = None
    random_completion_message = None

# Ensure random and threading are available regardless of import path
import random
import threading

# =============================================================================
# BACKGROUND SCAN TRACKING
# =============================================================================
# Global state for background scanning
_background_scan_thread = None
_background_scan_stats = {
    'running': False,
    'completed': 0,
    'failed': 0,
    'total': 0,
    'current_domain': None,
    'start_time': None,
    # Module-level progress (new)
    'current_module': None,
    'results_found': 0,
    'file_size_kb': 0.0,
}
_background_scan_lock = threading.Lock()


def is_background_scan_running():
    """Check if a background scan is currently running"""
    with _background_scan_lock:
        return _background_scan_stats['running']


def get_background_scan_stats():
    """Get current background scan statistics"""
    with _background_scan_lock:
        return dict(_background_scan_stats)


def _update_background_stats(**kwargs):
    """Update background scan statistics"""
    with _background_scan_lock:
        _background_scan_stats.update(kwargs)


def _run_background_scans(scanner, tracker):
    """Run scans in background thread"""
    global _background_scan_stats

    def on_start(domain):
        _update_background_stats(
            current_domain=domain,
            current_module=None,
            results_found=0,
            file_size_kb=0.0
        )

    def on_complete(domain, csv_path):
        with _background_scan_lock:
            _background_scan_stats['completed'] += 1

    def on_failed(domain, error):
        with _background_scan_lock:
            _background_scan_stats['failed'] += 1

    def on_progress(completed, failed, total):
        _update_background_stats(completed=completed, failed=failed, total=total)

    def on_module_progress(domain, module, results_count, file_size_kb):
        """Real-time module-level progress from SpiderFoot"""
        _update_background_stats(
            current_module=module,
            results_found=results_count,
            file_size_kb=file_size_kb
        )

    scanner.on_scan_start = on_start
    scanner.on_scan_complete = on_complete
    scanner.on_scan_failed = on_failed
    scanner.on_progress = on_progress
    scanner.on_module_progress = on_module_progress

    try:
        scanner.process_queue(progress_callback=on_progress)
    except Exception as e:
        pass  # Errors logged in tracker
    finally:
        _update_background_stats(running=False, current_domain=None, current_module=None)


def get_elapsed_time_str():
    """Get formatted elapsed time for background scan"""
    stats = get_background_scan_stats()
    start_time = stats.get('start_time')
    if not start_time:
        return "N/A"
    try:
        start = datetime.fromisoformat(start_time)
        elapsed = datetime.now() - start
        total_seconds = int(elapsed.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception:
        return "N/A"


# =============================================================================
# PATH SECURITY HELPERS
# =============================================================================
def is_safe_path(user_path: str, base_dir: str = None) -> bool:
    """
    Check if a path is safe (no path traversal).

    Args:
        user_path: User-provided path to check
        base_dir: Optional base directory the path should stay within

    Returns:
        True if path is safe, False if it contains traversal attempts
    """
    # Expand user path
    expanded = os.path.expanduser(user_path)
    resolved = os.path.realpath(expanded)

    # Check for obvious traversal attempts in the original input
    if '..' in user_path:
        return False

    # If base_dir specified, ensure resolved path is within it
    if base_dir:
        base_resolved = os.path.realpath(os.path.expanduser(base_dir))
        if not resolved.startswith(base_resolved):
            return False

    return True


def sanitize_path(user_path: str, base_dir: str = None) -> str:
    """
    Sanitize a user-provided path, rejecting unsafe paths.

    Args:
        user_path: User-provided path
        base_dir: Optional base directory to enforce

    Returns:
        Sanitized path or raises ValueError if unsafe
    """
    if not is_safe_path(user_path, base_dir):
        raise ValueError(f"Unsafe path detected: {user_path}")
    return os.path.realpath(os.path.expanduser(user_path))


# =============================================================================
# BANNER AND UI HELPERS
# =============================================================================
def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    """Print the glorious PUPPETMASTER banner"""
    # Build each line with exact spacing (79 chars inner width)
    W = 79  # inner width

    def pad(text, width=W):
        """Pad text to exact width"""
        return text + " " * (width - len(text))

    # ASCII art lines (raw text without colors for length calculation)
    puppet_art = [
        "██████╗ ██╗   ██╗██████╗ ██████╗ ███████╗████████╗",
        "██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔════╝╚══██╔══╝",
        "██████╔╝██║   ██║██████╔╝██████╔╝█████╗     ██║   ",
        "██╔═══╝ ██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝     ██║   ",
        "██║     ╚██████╔╝██║     ██║     ███████╗   ██║   ",
        "╚═╝      ╚═════╝ ╚═╝     ╚═╝     ╚══════╝   ╚═╝   ",
    ]

    master_art = [
        "███╗   ███╗ █████╗ ███████╗████████╗███████╗██████╗ ",
        "████╗ ████║██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗",
        "██╔████╔██║███████║███████╗   ██║   █████╗  ██████╔╝",
        "██║╚██╔╝██║██╔══██║╚════██║   ██║   ██╔══╝  ██╔══██╗",
        "██║ ╚═╝ ██║██║  ██║███████║   ██║   ███████╗██║  ██║",
        "╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝",
    ]

    print(f"{C.BRIGHT_CYAN}╔{'═' * W}╗")
    print(f"║{' ' * W}║")

    # PUPPET in magenta
    for line in puppet_art:
        content = f"   {C.BRIGHT_MAGENTA}{line}{C.BRIGHT_CYAN}"
        visual_len = 3 + len(line)  # 3 spaces + art
        padding = W - visual_len
        print(f"║{content}{' ' * padding}║")

    print(f"║{' ' * W}║")

    # MASTER in yellow
    for line in master_art:
        content = f"   {C.BRIGHT_YELLOW}{line}{C.BRIGHT_CYAN}"
        visual_len = 3 + len(line)
        padding = W - visual_len
        print(f"║{content}{' ' * padding}║")

    print(f"║{' ' * W}║")

    # Info lines - (text with color codes, visual length without colors)
    info_lines = [
        (f"{C.WHITE}SpiderFoot Sock Puppet Detector v2.0{C.BRIGHT_CYAN}", 36),
        (f"{C.DIM}Vibe coded with Claude | Prompted by deliciousnoodles{C.RESET}{C.BRIGHT_CYAN}", 53),
        (f"{C.WHITE}{C.DIM}\"good morning coffee with bacon egg and cheese\"{C.RESET}{C.BRIGHT_CYAN}", 47),
    ]

    for text, visual_len in info_lines:
        padding = W - 3 - visual_len  # 3 for leading spaces
        print(f"║   {text}{' ' * padding}║")

    print(f"║{' ' * W}║")
    print(f"╚{'═' * W}╝{C.RESET}")
    print()

def print_section(title, color=C.BRIGHT_CYAN):
    """Print a section header"""
    width = 70
    print(f"\n{color}{'━' * width}")
    print(f"  {C.BOLD}{title}{C.RESET}")
    print(f"{color}{'━' * width}{C.RESET}\n")

def print_menu_item(key, description, icon=""):
    """Print a menu item"""
    print(f"  {C.BRIGHT_YELLOW}[{key}]{C.RESET} {icon} {description}")

def print_success(message):
    """Print a success message"""
    print(f"{C.BRIGHT_GREEN}✓ {message}{C.RESET}")

def print_error(message):
    """Print an error message"""
    print(f"{C.BRIGHT_RED}✗ {message}{C.RESET}")

def print_warning(message):
    """Print a warning message"""
    print(f"{C.BRIGHT_YELLOW}⚠ {message}{C.RESET}")

def print_info(message):
    """Print an info message"""
    print(f"{C.BRIGHT_CYAN}ℹ {message}{C.RESET}")

def get_input(prompt, default=None, max_length=10000):
    """
    Get user input with a styled prompt.
    Returns None on Ctrl+C/Ctrl+D to signal cancellation.
    Callers should check for None and handle as "user wants to cancel".
    """
    if default:
        prompt_text = f"{C.BRIGHT_MAGENTA}► {prompt} {C.DIM}[{default}]{C.RESET}: "
    else:
        prompt_text = f"{C.BRIGHT_MAGENTA}► {prompt}{C.RESET}: "

    try:
        response = input(prompt_text).strip()
        # Protect against paste bombs
        if len(response) > max_length:
            print(f"\n{C.BRIGHT_YELLOW}⚠ Input too long ({len(response)} chars). Truncated to {max_length}.{C.RESET}")
            response = response[:max_length]
        # Warn about suspicious input (likely accidental paste)
        if '\n' in response or len(response) > 500:
            line_count = response.count('\n') + 1
            if line_count > 5:
                print(f"\n{C.BRIGHT_YELLOW}⚠ Detected multi-line paste ({line_count} lines). Using first line only.{C.RESET}")
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
    bar = "█" * filled + "░" * (length - filled)
    print(f"\r{C.BRIGHT_CYAN}{prefix}: [{bar}] {percent*100:.1f}%{C.RESET}", end="", flush=True)
    if current == total and total > 0:
        print()  # New line when complete

# =============================================================================
# DEPENDENCY MANAGEMENT (Cross-platform: Windows, Mac, Linux)
# =============================================================================
REQUIRED_PACKAGES = {
    'pandas': 'pandas',
    'networkx': 'networkx',
    'tqdm': 'tqdm',
    'tldextract': 'tldextract',
    'matplotlib': 'matplotlib',
    'googlesearch': 'googlesearch-python',  # import name != pip name
    'ddgs': 'ddgs',  # DuckDuckGo search (renamed from duckduckgo_search)
    'community': 'python-louvain',  # Louvain clustering (essential for accurate cluster detection)
    'dns': 'dnspython',  # DNS resolution for Wildcard DNS Analyzer
    'simple_term_menu': 'simple-term-menu',  # Interactive domain review UI
    'rich': 'rich',  # Gaming HUD UI
    'psutil': 'psutil',  # System monitoring (CPU/MEM/DISK stats in HUD)
}

# Optional packages (currently none - all essential packages are required)
OPTIONAL_PACKAGES = {
}

def check_python_version():
    """Ensure Python 3.8+ is being used"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error(f"Python 3.8+ required. You have {version.major}.{version.minor}")
        return False
    print_success(f"Python {version.major}.{version.minor}.{version.micro} detected")
    return True

def check_pip_available():
    """Check if pip is available"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def is_debian_based():
    """Check if running on Debian-based system (Debian, Ubuntu, Kali)"""
    try:
        with open('/etc/os-release', 'r') as f:
            content = f.read().lower()
            return any(x in content for x in ['debian', 'ubuntu', 'kali'])
    except Exception:
        return False


def auto_install_pip():
    """Auto-install pip on Debian-based systems"""
    if not is_debian_based():
        return False

    print_info("pip not found. Auto-installing via apt...")

    try:
        # First update apt
        result = subprocess.run(
            ["sudo", "apt", "update"],
            capture_output=True,
            text=True,
            timeout=120
        )

        # Install pip and venv
        result = subprocess.run(
            ["sudo", "apt", "install", "-y", "python3-pip", "python3-venv"],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            print_success("pip installed successfully!")
            return True
        else:
            print_error(f"Failed to install pip: {result.stderr[:200]}")
            return False

    except subprocess.TimeoutExpired:
        print_error("Timeout while installing pip")
        return False
    except Exception as e:
        print_error(f"Error installing pip: {e}")
        return False


def get_pip_install_instructions():
    """Get platform-specific pip installation instructions"""
    import platform
    system = platform.system().lower()

    instructions = f"""
{C.BRIGHT_YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                           PIP NOT FOUND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}

pip (Python package manager) is required but not installed.
"""

    if system == "linux":
        instructions += f"""
{C.BRIGHT_CYAN}For Ubuntu/Debian:{C.RESET}
    sudo apt update && sudo apt install python3-pip python3-venv

{C.BRIGHT_CYAN}For Fedora/RHEL:{C.RESET}
    sudo dnf install python3-pip

{C.BRIGHT_CYAN}For Arch Linux:{C.RESET}
    sudo pacman -S python-pip
"""
    elif system == "darwin":  # macOS
        instructions += f"""
{C.BRIGHT_CYAN}Option 1 - Using Homebrew (recommended):{C.RESET}
    brew install python3

{C.BRIGHT_CYAN}Option 2 - Using the Python installer:{C.RESET}
    Download from https://python.org and reinstall Python
    (pip is included with the official installer)
"""
    elif system == "windows":
        instructions += f"""
{C.BRIGHT_CYAN}Option 1 - Reinstall Python:{C.RESET}
    Download from https://python.org
    Make sure to check "Add Python to PATH" during installation

{C.BRIGHT_CYAN}Option 2 - Use get-pip.py:{C.RESET}
    Download https://bootstrap.pypa.io/get-pip.py
    Run: python get-pip.py
"""

    # Build activate command separately (backslashes not allowed in f-strings)
    activate_cmd = 'venv\\Scripts\\activate' if system == 'windows' else 'source venv/bin/activate'
    instructions += f"""
{C.BRIGHT_CYAN}Alternative - Use a virtual environment:{C.RESET}
    python3 -m venv venv
    {activate_cmd}
    pip install -r requirements.txt
"""
    return instructions

def check_dependencies(silent=False):
    """Check if all required packages are installed

    Args:
        silent: If True, don't print anything (just return results)
    """
    missing = []
    optional_missing = []

    if not silent:
        print_info("Checking dependencies...")

    for package, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(package)
            if not silent:
                print(f"  {C.GREEN}✓{C.RESET} {package}")
        except ImportError:
            if not silent:
                print(f"  {C.RED}✗{C.RESET} {package} {C.DIM}(required){C.RESET}")
            missing.append(pip_name)

    # Check optional packages
    for package, pip_name in OPTIONAL_PACKAGES.items():
        try:
            __import__(package)
            if not silent:
                print(f"  {C.GREEN}✓{C.RESET} {package} {C.DIM}(optional){C.RESET}")
        except ImportError:
            if not silent:
                print(f"  {C.YELLOW}○{C.RESET} {package} {C.DIM}(optional, not installed){C.RESET}")
            optional_missing.append(pip_name)

    return missing, optional_missing

def is_externally_managed_error(stderr):
    """Check if pip error is due to externally-managed-environment (PEP 668)"""
    return "externally-managed-environment" in stderr.lower()


def is_running_in_venv():
    """Check if we're currently running inside a virtual environment"""
    return sys.prefix != sys.base_prefix


def get_existing_venv_python():
    """Check if a venv exists in the project directory and return its python path"""
    script_dir = Path(__file__).parent
    venv_path = script_dir / "venv"

    if not venv_path.exists():
        return None

    # Find the venv python
    if os.name == 'nt':  # Windows
        venv_python = venv_path / "Scripts" / "python.exe"
    else:  # Linux/Mac
        venv_python = venv_path / "bin" / "python3"
        if not venv_python.exists():
            venv_python = venv_path / "bin" / "python"

    if venv_python.exists():
        return str(venv_python)
    return None


def ensure_running_in_venv():
    """If a venv exists but we're not in it, restart using the venv python"""
    if is_running_in_venv():
        # Already in a venv, we're good
        return True

    venv_python = get_existing_venv_python()
    if venv_python:
        # Venv exists but we're not in it - restart
        print_info("Virtual environment detected. Restarting in venv...")
        time.sleep(0.5)
        os.execv(venv_python, [venv_python] + sys.argv)
        # This line never reached - execv replaces the process

    # No venv exists yet, continue normally
    return True


def create_and_use_venv():
    """Create a virtual environment and return path to its python"""
    script_dir = Path(__file__).parent
    venv_path = script_dir / "venv"

    print_section("Creating Virtual Environment", C.BRIGHT_CYAN)
    print_info("Modern Python requires a virtual environment for pip installs.")
    print_info(f"Creating venv at: {venv_path}")

    try:
        # Create venv
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print_error(f"Failed to create venv: {result.stderr}")
            return None

        print_success("Virtual environment created!")

        # Determine path to venv python
        if os.name == 'nt':  # Windows
            venv_python = venv_path / "Scripts" / "python.exe"
        else:  # Linux/Mac
            venv_python = venv_path / "bin" / "python3"

        if not venv_python.exists():
            # Try alternate path
            venv_python = venv_path / "bin" / "python"

        if venv_python.exists():
            print_success(f"Venv Python: {venv_python}")
            return str(venv_python)
        else:
            print_error("Could not find Python in venv")
            return None

    except Exception as e:
        print_error(f"Failed to create venv: {e}")
        return None


def restart_in_venv(venv_python):
    """Restart the script using the venv Python"""
    print_info("Restarting PUPPETMASTER in virtual environment...")
    time.sleep(1)

    # Re-run this script with venv python
    os.execv(venv_python, [venv_python] + sys.argv)


def install_dependencies(packages, optional=False, venv_python=None):
    """Install missing packages using pip"""
    if not packages:
        return True

    label = "Optional Packages" if optional else "Required Packages"
    print_section(f"Installing {label}", C.BRIGHT_YELLOW)

    python_exe = venv_python or sys.executable

    for package in packages:
        print_info(f"Installing {package}...")
        try:
            # Use subprocess with sys.executable for cross-platform compatibility
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", package, "--quiet"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print_success(f"Installed {package}")
            else:
                # Check for externally-managed-environment error
                if is_externally_managed_error(result.stderr):
                    print_warning("System Python is externally managed (PEP 668)")
                    print_info("This is common on Kali, Ubuntu 23+, and other modern distros.")
                    print()

                    if confirm("Create a virtual environment to install packages?"):
                        venv_python = create_and_use_venv()
                        if venv_python:
                            # Install packages in venv
                            print_section("Installing Packages in Venv", C.BRIGHT_GREEN)
                            all_packages = packages  # Install all, not just remaining
                            for pkg in all_packages:
                                print_info(f"Installing {pkg}...")
                                sub_result = subprocess.run(
                                    [venv_python, "-m", "pip", "install", pkg, "--quiet"],
                                    capture_output=True,
                                    text=True
                                )
                                if sub_result.returncode == 0:
                                    print_success(f"Installed {pkg}")
                                else:
                                    print_warning(f"Could not install {pkg}")

                            print()
                            print_success("Packages installed in virtual environment!")
                            print_info("Restarting PUPPETMASTER with venv...")
                            time.sleep(1)
                            restart_in_venv(venv_python)
                            return True  # Won't reach here due to exec
                        else:
                            print_error("Failed to create virtual environment")
                            print_info("Try manually: python3 -m venv venv && source venv/bin/activate")
                            return False
                    else:
                        print_info("You can also run: pip install --break-system-packages -r requirements.txt")
                        return False

                if optional:
                    print_warning(f"Could not install {package} (optional, continuing...)")
                else:
                    print_error(f"Failed to install {package}")
                    print(f"{C.DIM}{result.stderr}{C.RESET}")
                    return False
        except Exception as e:
            if optional:
                print_warning(f"Could not install {package}: {e}")
            else:
                print_error(f"Failed to install {package}: {e}")
                return False

    return True

def setup_environment():
    """Check and setup the environment"""
    print_section("Environment Setup", C.BRIGHT_BLUE)

    # Check Python version
    if not check_python_version():
        return False

    # Quick silent check first - if all required packages are present, skip verbose check
    missing, optional_missing = check_dependencies(silent=True)

    if not missing:
        # All required packages are installed - just show a quick confirmation
        print_success("All dependencies installed!")
        return True

    # Something is missing - do the full verbose check
    print_info("Some packages are missing, checking details...")
    missing, optional_missing = check_dependencies(silent=False)

    # Check if pip is available (only needed if we need to install)
    if not check_pip_available():
        # Try to auto-install pip on Debian-based systems (Kali, Ubuntu, Debian)
        if not auto_install_pip():
            print(get_pip_install_instructions())
            return False

    packages_installed = False

    if missing:
        print()
        print_warning(f"Missing {len(missing)} required package(s): {', '.join(missing)}")

        # Highlight important packages
        if 'python-louvain' in missing:
            print(f"{C.BRIGHT_RED}  ⚠ python-louvain is CRITICAL for accurate cluster detection!{C.RESET}")
            print(f"{C.DIM}  Without it, you may find 2 clusters instead of 6+{C.RESET}")

        if confirm("Would you like to install them now?"):
            if not install_dependencies(missing, optional=False):
                return False
            packages_installed = True
        else:
            print_error("Cannot proceed without required packages.")
            print_info("You can install manually with: pip install -r requirements.txt")
            return False

    # Optional packages (if any are defined in OPTIONAL_PACKAGES)
    if optional_missing:
        print()
        print_warning(f"{len(optional_missing)} optional package(s) not installed: {', '.join(optional_missing)}")
        if confirm("Install optional packages?", default=True):
            install_dependencies(optional_missing, optional=True)
            packages_installed = True

    print()
    print_success("Environment is ready!")

    # If packages were installed, restart script to pick up new imports
    # Must restart regardless of venv status - imports happen at module load time
    if packages_installed:
        print()
        print_info("Restarting to load newly installed packages...")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    return True

# =============================================================================
# PATH HELPERS
# =============================================================================
def get_data_directory():
    """Interactively get the SpiderFoot data directory from user"""
    print_section("Data Input", C.BRIGHT_MAGENTA)

    # Check for existing exports in known locations
    config = load_config()
    default_export_dir = config.get('spiderfoot_output_dir', './spiderfoot_exports')
    default_export_dir = os.path.expanduser(default_export_dir)

    # Also check common locations
    possible_dirs = [
        default_export_dir,
        './spiderfoot_exports',
        os.path.expanduser('~/spiderfoot_exports'),
    ]

    # Find directories with CSV files
    found_dirs = []
    for d in possible_dirs:
        if os.path.isdir(d):
            csv_files = list(Path(d).glob("*.csv"))
            if csv_files:
                if d not in [x[0] for x in found_dirs]:  # Avoid duplicates
                    found_dirs.append((d, csv_files))

    # If we found directories with exports, show selection menu
    if found_dirs:
        print(f"""
{C.WHITE}Found existing SpiderFoot exports:{C.RESET}
""")
        for i, (dir_path, csv_files) in enumerate(found_dirs, 1):
            total_size = sum(f.stat().st_size for f in csv_files)
            size_mb = total_size / (1024 * 1024)
            print(f"  {C.BRIGHT_GREEN}[{i}]{C.RESET} {dir_path}")
            print(f"      {C.DIM}{len(csv_files)} CSV files ({size_mb:.1f} MB){C.RESET}")
            # Show most recent files
            sorted_files = sorted(csv_files, key=lambda f: f.stat().st_mtime, reverse=True)
            for f in sorted_files[:3]:
                print(f"      {C.DIM}• {f.name}{C.RESET}")
            if len(csv_files) > 3:
                print(f"      {C.DIM}  ... and {len(csv_files) - 3} more{C.RESET}")
            print()

        print(f"  {C.BRIGHT_YELLOW}[{len(found_dirs) + 1}]{C.RESET} Enter a different path...")
        print()

        choice = get_input("Select option", "1")
        if choice is None:
            print_info("Cancelled.")
            return None

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(found_dirs):
                selected_dir = found_dirs[choice_num - 1][0]
                print_success(f"Using: {selected_dir}")
                return os.path.abspath(selected_dir)
        except ValueError:
            pass

        # Fall through to manual entry

    # Manual path entry
    print(f"""
{C.WHITE}Enter the directory containing your SpiderFoot CSV exports.{C.RESET}

{C.DIM}────────────────────────────────────────────────────────────────
💡 TIP: Drag and drop your SpiderFoot exports folder directly
   into this terminal window - the path will appear automatically!
────────────────────────────────────────────────────────────────{C.RESET}
""")

    while True:
        path = get_input("Enter the path to your SpiderFoot exports")

        # Ctrl+C = cancel
        if path is None:
            print_info("Cancelled.")
            return None

        if not path:
            print_warning("Path cannot be empty. Please try again.")
            continue

        # Expand user home directory
        path = os.path.expanduser(path)

        # Check if path exists
        if not os.path.exists(path):
            print_error(f"Path does not exist: {path}")
            if confirm("Would you like to try again?"):
                continue
            else:
                return None

        # Check if it's a directory
        if not os.path.isdir(path):
            print_error("That's a file, not a directory. Please provide a directory path.")
            continue

        # Check for CSV files
        csv_files = list(Path(path).glob("*.csv"))
        if not csv_files:
            print_warning(f"No CSV files found in: {path}")
            if confirm("This doesn't look like a SpiderFoot export directory. Continue anyway?"):
                pass
            else:
                continue
        else:
            print_success(f"Found {len(csv_files)} CSV file(s)")

            # Show file sizes
            total_size = sum(f.stat().st_size for f in csv_files)
            size_mb = total_size / (1024 * 1024)
            print_info(f"Total data size: {size_mb:.1f} MB")

            # Preview files
            print(f"\n{C.DIM}Files found:{C.RESET}")
            for f in csv_files[:5]:
                size = f.stat().st_size / (1024 * 1024)
                print(f"  • {f.name} ({size:.1f} MB)")
            if len(csv_files) > 5:
                print(f"  ... and {len(csv_files) - 5} more")

        print()
        if confirm("Use this directory?"):
            return os.path.abspath(path)

def get_output_directory():
    """Get or create output directory"""
    print_section("Output Location", C.BRIGHT_GREEN)

    # Default output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_output = os.path.join(os.getcwd(), f"results_{timestamp}")

    print(f"""
{C.WHITE}Where should we save the results?{C.RESET}

{C.DIM}The output directory will contain:
  • executive_summary.md - The main findings report
  • detailed_connections.csv - All domain connections
  • clusters.csv - Identified sock puppet groups
  • network_visualization.html - Interactive graph
  • And more...{C.RESET}
""")

    path = get_input(f"Output directory", default_output)

    # Ctrl+C = cancel
    if path is None:
        print_info("Cancelled.")
        return None

    path = os.path.expanduser(path)

    # Create directory if it doesn't exist
    if not os.path.exists(path):
        if confirm(f"Directory doesn't exist. Create it?"):
            try:
                os.makedirs(path, exist_ok=True)
                print_success(f"Created: {path}")
            except Exception as e:
                print_error(f"Failed to create directory: {e}")
                return None
        else:
            return None

    # Remember this directory for "View Previous Results"
    abs_path = os.path.abspath(path)
    remember_output_dir(abs_path)
    return abs_path

# =============================================================================
# MAIN MENU
# =============================================================================
def show_main_menu():
    """Display the main menu"""
    clear_screen()
    print_banner()

    # Check if background scan is running
    if is_background_scan_running():
        stats = get_background_scan_stats()
        progress = stats['completed'] + stats['failed']
        current = stats.get('current_domain', 'unknown')
        if len(current) > 30:
            current = current[:27] + "..."
        print(f"""
{C.BRIGHT_YELLOW}╔═══════════════════════════════════════════════════════════════════════════════╗
║  🔄 SPIDERFOOT SCAN IN PROGRESS — {progress}/{stats['total']} complete                             ║
║     Currently scanning: {current:<30}  Use [4] to view details  ║
╚═══════════════════════════════════════════════════════════════════════════════╝{C.RESET}
""")

    # Check if domains are ready for scanning
    config = load_config()
    if config.get('domains_ready_for_scan'):
        domain_count = config.get('domains_ready_count', 0)
        print(f"""
{C.BRIGHT_GREEN}╔═══════════════════════════════════════════════════════════════════════════════╗
║  ✓ {domain_count} DOMAINS LOADED — Proceed to option [3] to start SpiderFoot scans!      ║
╚═══════════════════════════════════════════════════════════════════════════════╝{C.RESET}
""")
        # Clear the flag after showing
        config['domains_ready_for_scan'] = False
        save_config(config)

    # Show Kali mode banner if active
    if KALI_MODULE_AVAILABLE and is_enhanced_mode():
        kali_status = get_kali_status_line()
        print(f"""
{C.BRIGHT_RED}╔═══════════════════════════════════════════════════════════════════════════════╗
║  🐉 KALI LINUX ENHANCED MODE ACTIVE                                                        
║     {kali_status:<69}                                                                       ║
║     Option [1] auto-expands domains with Kali tools after scraping!                         ║
╚═════════════════════════════════════════════════════════════════════════════════════════════╝{C.RESET}
""")

    print(f"""
{C.WHITE}{C.BOLD}Welcome to PUPPETMASTER!{C.RESET}
{C.DIM}End-to-end sock puppet detection pipeline{C.RESET}

{C.WHITE}What does this tool do?{C.RESET}
{C.DIM}━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
Discovers, scans, and analyzes domains to expose "sock puppet" networks —
websites that {C.UNDERLINE}appear{C.RESET}{C.DIM} independent but are secretly controlled by the same operator.

{C.WHITE}The Pipeline:{C.RESET}
{C.DIM}━━━━━━━━━━━━━{C.RESET}
  {C.BRIGHT_CYAN}1. Discover{C.RESET}  Scrape search engines for domains you suspect are sock puppets
  {C.BRIGHT_CYAN}2. Scan{C.RESET}      Run SpiderFoot OSINT scans on scrapd list (batch or interactive GUI)
  {C.BRIGHT_CYAN}3. Analyze{C.RESET}   Analyze spiderfoot scans to detect if there are any sock puppet clusters

{C.WHITE}What We Find:{C.RESET}
{C.DIM}━━━━━━━━━━━━━{C.RESET}
  {C.BRIGHT_RED}•{C.RESET} Same Google Analytics/AdSense IDs {C.DIM}← definitive proof{C.RESET}
  {C.BRIGHT_YELLOW}•{C.RESET} Same WHOIS, nameservers, SSL certs {C.DIM}← strong evidence{C.RESET}

{C.BRIGHT_GREEN}One shared unique identifier = same operator.{C.RESET}

{C.WHITE}New here?{C.RESET} Press {C.BRIGHT_YELLOW}[8]{C.RESET} for the full guide.
{C.BRIGHT_YELLOW}Long scans?{C.RESET} Press {C.WHITE}[9]{C.RESET} to run in {C.WHITE}tmux{C.RESET} (survives SSH disconnects)

""")

    print_section("Main Menu", C.BRIGHT_YELLOW)

    # Discovery & Scanning Section
    print(f"  {C.BRIGHT_CYAN}DISCOVERY & SCANNING{C.RESET}")
    print_menu_item("1", "Scrape domains via keywords", "🔍")
    print_menu_item("2", "Load domains from file", "📂")
    print_menu_item("3", "SpiderFoot Control Center (scans, GUI, DB)", "🕷️")
    print_menu_item("4", "Check scan queue status", "📋")
    print()

    # Analysis Section
    print(f"  {C.BRIGHT_GREEN}ANALYSIS{C.RESET}")
    print_menu_item("5", "Run Puppet Analysis on SpiderFoot scans", "🎭")
    print_menu_item("6", "View previous results", "📊")
    print_menu_item("11", "Signal//Noise Wildcard DNS Analyzer", "📡")
    print()

    # Settings Section
    print(f"  {C.BRIGHT_MAGENTA}SETTINGS{C.RESET}")
    print_menu_item("7", "Configuration", "⚙️")
    print_menu_item("8", "Help & Documentation", "❓")
    print_menu_item("9", "Launch in tmux (for long scans)", "🖥️")
    print_menu_item("10", "System monitor (via Glances)", "📊")
    print()

    # Kali Enhanced Mode Section (only shown when Kali is detected)
    if should_show_kali_menu():
        print_enhanced_menu(print_func=print, colors=C)

    print_menu_item("q", "Quit", "👋")
    print()


def launch_in_tmux():
    """Check for tmux, install if needed, and relaunch puppetmaster in a tmux session"""
    clear_screen()
    print_banner()
    print_section("Launch in tmux", C.BRIGHT_CYAN)

    # Check if already in tmux
    if os.environ.get('TMUX'):
        print_success("You're already running inside tmux!")
        print_info("Your session will persist even if you disconnect.")
        print()
        print(f"{C.DIM}Useful tmux commands:{C.RESET}")
        print(f"  {C.WHITE}Ctrl+b d{C.RESET}     - Detach (leave running in background)")
        print(f"  {C.WHITE}tmux attach{C.RESET}  - Reattach to session later")
        print(f"  {C.WHITE}Ctrl+b [{C.RESET}     - Scroll mode (q to exit)")
        get_input("\nPress Enter to return to main menu...")
        return

    print(f"""
{C.WHITE}tmux keeps your session alive even if you disconnect.{C.RESET}
{C.DIM}Perfect for long-running SpiderFoot scans!{C.RESET}
""")

    # Check if tmux is installed
    print_info("Checking if tmux is installed...")
    try:
        result = subprocess.run(
            ["which", "tmux"],
            capture_output=True,
            text=True
        )
        tmux_installed = result.returncode == 0
    except Exception:
        tmux_installed = False

    if tmux_installed:
        print_success("tmux is installed!")
    else:
        print_warning("tmux is not installed.")

        if not confirm("Install tmux now? (requires sudo)"):
            print_info("Cancelled. You can install manually with: sudo apt install tmux")
            get_input("\nPress Enter to return to main menu...")
            return

        print_info("Installing tmux...")
        try:
            # Try apt first (Debian/Ubuntu/Kali)
            result = subprocess.run(
                ["sudo", "apt", "install", "-y", "tmux"],
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                print_success("tmux installed successfully!")
            else:
                # Try yum (RHEL/CentOS)
                result = subprocess.run(
                    ["sudo", "yum", "install", "-y", "tmux"],
                    text=True,
                    timeout=120
                )
                if result.returncode != 0:
                    print_error("Failed to install tmux.")
                    print_info("Try installing manually: sudo apt install tmux")
                    get_input("\nPress Enter to return to main menu...")
                    return
                print_success("tmux installed successfully!")
        except subprocess.TimeoutExpired:
            print_error("Installation timed out.")
            get_input("\nPress Enter to return to main menu...")
            return
        except Exception as e:
            print_error(f"Installation failed: {e}")
            get_input("\nPress Enter to return to main menu...")
            return

    # Launch puppetmaster in tmux
    print()
    print_info("Launching PUPPETMASTER in a new tmux session...")
    print()
    print(f"{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
    print(f"{C.WHITE}After launching, useful tmux commands:{C.RESET}")
    print(f"  {C.BRIGHT_YELLOW}Ctrl+b d{C.RESET}     - Detach (leave PUPPETMASTER running in background)")
    print(f"  {C.BRIGHT_YELLOW}tmux attach{C.RESET}  - Reattach to this session later")
    print(f"  {C.BRIGHT_YELLOW}Ctrl+b [{C.RESET}     - Scroll mode (press q to exit scroll mode)")
    print(f"{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
    print()

    if not confirm("Launch now?"):
        print_info("Cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Get the path to this script
    script_path = os.path.abspath(__file__)

    # Get the python executable (use venv python if available)
    venv_python = get_existing_venv_python()
    python_exe = venv_python if venv_python else sys.executable

    # Launch tmux with puppetmaster
    # Using exec replaces the current process
    try:
        os.execlp(
            "tmux", "tmux",
            "new-session", "-s", "puppetmaster",
            python_exe, script_path
        )
    except Exception as e:
        print_error(f"Failed to launch tmux: {e}")
        get_input("\nPress Enter to return to main menu...")


def launch_glances():
    """Launch glances system monitor, installing if needed"""
    clear_screen()
    print_banner()
    print_section("System Monitor (Glances)", C.BRIGHT_CYAN)

    print(f"""
{C.WHITE}Glances is a cross-platform system monitoring tool.{C.RESET}
{C.DIM}Great for watching CPU, memory, network, and disk usage during scans!{C.RESET}
""")

    # Check if glances is installed
    print_info("Checking if glances is installed...")
    try:
        result = subprocess.run(
            ["which", "glances"],
            capture_output=True,
            text=True
        )
        glances_installed = result.returncode == 0
    except Exception:
        glances_installed = False

    if glances_installed:
        print_success("glances is installed!")
    else:
        print_warning("glances is not installed.")

        if not confirm("Install glances now?"):
            print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
            return

        print_info("Detecting OS and installing glances...")

        # Detect OS and install accordingly
        install_success = False

        # Check for apt (Debian/Ubuntu/Kali)
        try:
            result = subprocess.run(["which", "apt"], capture_output=True)
            if result.returncode == 0:
                print_info("Detected Debian/Ubuntu/Kali - using apt...")
                result = subprocess.run(
                    ["sudo", "apt", "install", "-y", "glances"],
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    install_success = True
                    print_success("glances installed via apt!")
        except Exception:
            pass

        # Check for yum (RHEL/CentOS/Fedora)
        if not install_success:
            try:
                result = subprocess.run(["which", "yum"], capture_output=True)
                if result.returncode == 0:
                    print_info("Detected RHEL/CentOS - using yum...")
                    result = subprocess.run(
                        ["sudo", "yum", "install", "-y", "glances"],
                        text=True,
                        timeout=120
                    )
                    if result.returncode == 0:
                        install_success = True
                        print_success("glances installed via yum!")
            except Exception:
                pass

        # Check for dnf (Fedora)
        if not install_success:
            try:
                result = subprocess.run(["which", "dnf"], capture_output=True)
                if result.returncode == 0:
                    print_info("Detected Fedora - using dnf...")
                    result = subprocess.run(
                        ["sudo", "dnf", "install", "-y", "glances"],
                        text=True,
                        timeout=120
                    )
                    if result.returncode == 0:
                        install_success = True
                        print_success("glances installed via dnf!")
            except Exception:
                pass

        # Check for pacman (Arch)
        if not install_success:
            try:
                result = subprocess.run(["which", "pacman"], capture_output=True)
                if result.returncode == 0:
                    print_info("Detected Arch Linux - using pacman...")
                    result = subprocess.run(
                        ["sudo", "pacman", "-S", "--noconfirm", "glances"],
                        text=True,
                        timeout=120
                    )
                    if result.returncode == 0:
                        install_success = True
                        print_success("glances installed via pacman!")
            except Exception:
                pass

        # Check for brew (macOS)
        if not install_success:
            try:
                result = subprocess.run(["which", "brew"], capture_output=True)
                if result.returncode == 0:
                    print_info("Detected macOS - using brew...")
                    result = subprocess.run(
                        ["brew", "install", "glances"],
                        text=True,
                        timeout=180
                    )
                    if result.returncode == 0:
                        install_success = True
                        print_success("glances installed via brew!")
            except Exception:
                pass

        # Try pip as fallback
        if not install_success:
            print_info("Trying pip as fallback...")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "glances"],
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    install_success = True
                    print_success("glances installed via pip!")
            except Exception:
                pass

        if not install_success:
            print_error("Failed to install glances.")
            print_info("Try installing manually:")
            print(f"  {C.DIM}pip install glances{C.RESET}")
            print(f"  {C.DIM}sudo apt install glances{C.RESET}")
            get_input("\nPress Enter to return to main menu...")
            return

    # Launch glances
    print()
    print(f"{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
    print(f"{C.WHITE}Glances controls:{C.RESET}")
    print(f"  {C.BRIGHT_YELLOW}q{C.RESET}         - Quit glances")
    print(f"  {C.BRIGHT_YELLOW}h{C.RESET}         - Toggle help")
    print(f"  {C.BRIGHT_YELLOW}1{C.RESET}         - Toggle CPU per-core stats")
    print(f"  {C.BRIGHT_YELLOW}d{C.RESET}         - Toggle disk I/O stats")
    print(f"  {C.BRIGHT_YELLOW}n{C.RESET}         - Toggle network stats")
    print(f"{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
    print()

    if not confirm("Launch glances now?"):
        print_info("Cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return

    print_info("Launching glances... (press 'q' to exit and return to menu)")
    print()

    try:
        # Run glances interactively
        subprocess.run(["glances"])
    except KeyboardInterrupt:
        # User pressed Ctrl+C - that's fine, just return to menu
        print()
        print_info("Glances interrupted.")
    except FileNotFoundError:
        print_error("glances command not found. Try: pip install glances")
    except Exception as e:
        print_error(f"Failed to run glances: {e}")

    get_input("\nPress Enter to return to main menu...")


def launch_spiderfoot_gui():
    """Launch SpiderFoot web GUI with SSH tunnel instructions"""
    clear_screen()
    print_banner()
    print_section("SpiderFoot Web GUI Mode", C.BRIGHT_CYAN)

    print(f"""
{C.WHITE}SpiderFoot Web GUI{C.RESET}
{C.DIM}━━━━━━━━━━━━━━━━━━{C.RESET}
The SpiderFoot web interface lets you run scans interactively with a
graphical UI instead of command-line batch mode.

{C.BRIGHT_YELLOW}Note:{C.RESET} The GUI is useful for:
  • Running one-off scans on specific domains
  • Exploring SpiderFoot's full module configuration
  • Viewing real-time scan progress with detailed logs
  • Exporting results in various formats

For batch scanning multiple domains, use option [3] (CLI mode) instead.
""")

    # Check if SpiderFoot is configured
    config = load_config()
    sf_path = config.get('spiderfoot_path')
    sf_python = config.get('spiderfoot_python')

    # Try to find SpiderFoot if not configured
    if not sf_path or not os.path.exists(sf_path):
        print_info("Checking for SpiderFoot installation...")

        # Check if we have SpiderFoot installed in project directory
        script_dir = Path(__file__).parent
        project_sf_path = script_dir / "spiderfoot" / "sf.py"
        project_sf_python = script_dir / "spiderfoot" / "venv" / "bin" / "python3"

        if project_sf_path.exists() and project_sf_python.exists():
            print_success(f"Found SpiderFoot in project directory!")
            sf_path = str(project_sf_path)
            sf_python = str(project_sf_python)
            config['spiderfoot_path'] = sf_path
            config['spiderfoot_python'] = sf_python
            save_config(config)
        else:
            # Offer to install
            print(f"""
{C.WHITE}SpiderFoot is not installed.{C.RESET}

SpiderFoot is required for the web GUI. Would you like to install it now?

{C.DIM}Source:{C.RESET}  {C.CYAN}https://github.com/smicallef/spiderfoot{C.RESET}
{C.DIM}Install:{C.RESET} Clone repo → Create venv → Install dependencies
{C.DIM}Location:{C.RESET} ./spiderfoot/ (in this project directory)
""")
            if confirm("Install SpiderFoot now?"):
                result = install_spiderfoot_interactive()
                if result:
                    sf_path, sf_python = result
                    config['spiderfoot_path'] = sf_path
                    config['spiderfoot_python'] = sf_python
                    save_config(config)
                    print_success("SpiderFoot installed successfully!")
                else:
                    print_error("SpiderFoot installation failed.")
                    get_input("\nPress Enter to return to main menu...")
                    return
            else:
                print_info("SpiderFoot is required for the web GUI.")
                get_input("\nPress Enter to return to main menu...")
                return

    # Verify sf_path exists after all checks
    if not sf_path or not os.path.exists(sf_path):
        print_error("SpiderFoot path not found!")
        get_input("\nPress Enter to return to main menu...")
        return

    # Get the SpiderFoot directory
    sf_dir = Path(sf_path).parent

    # Detect if running over SSH
    ssh_connection = os.environ.get('SSH_CONNECTION', '')
    ssh_client = os.environ.get('SSH_CLIENT', '')

    if ssh_connection:
        # Parse SSH_CONNECTION: "client_ip client_port server_ip server_port"
        parts = ssh_connection.split()
        host_ip = parts[0] if parts else 'YOUR_HOST_IP'
        server_ip = parts[2] if len(parts) > 2 else 'THIS_SERVER'
        is_remote = True
    else:
        host_ip = None
        server_ip = 'localhost'
        is_remote = False

    # Default port
    default_port = 5001

    # Ask for port
    print(f"\n{C.WHITE}Port Configuration:{C.RESET}")
    port_input = get_input(f"Enter port for SpiderFoot web UI [{default_port}]: ").strip()
    port = int(port_input) if port_input.isdigit() else default_port

    # Check if port is in use
    print_info(f"Checking if port {port} is available...")

    def check_port_in_use(port):
        """Check if a port is in use"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    def find_spiderfoot_processes():
        """Find running SpiderFoot processes"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "sf.py"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                return [p for p in pids if p]
            return []
        except Exception:
            return []

    port_in_use = check_port_in_use(port)
    sf_processes = find_spiderfoot_processes()

    if port_in_use:
        print_warning(f"Port {port} is already in use!")

        if sf_processes:
            print(f"  Found {len(sf_processes)} SpiderFoot process(es): {', '.join(sf_processes)}")

            if confirm("Kill existing SpiderFoot processes and use this port?"):
                for pid in sf_processes:
                    try:
                        subprocess.run(["kill", pid], capture_output=True)
                        print_success(f"Killed process {pid}")
                    except Exception:
                        pass
                time.sleep(1)  # Give processes time to die

                # Check again
                if check_port_in_use(port):
                    print_error(f"Port {port} is still in use. Try a different port.")
                    alt_port = port + 1
                    print_info(f"Suggestion: use port {alt_port}")
                    get_input("\nPress Enter to return to main menu...")
                    return
            else:
                # Offer alternative port
                alt_port = port + 1
                while check_port_in_use(alt_port) and alt_port < port + 10:
                    alt_port += 1

                if not check_port_in_use(alt_port):
                    if confirm(f"Use port {alt_port} instead?"):
                        port = alt_port
                    else:
                        print_info("Cancelled.")
                        get_input("\nPress Enter to return to main menu...")
                        return
                else:
                    print_error("Could not find an available port.")
                    get_input("\nPress Enter to return to main menu...")
                    return
        else:
            print_info("Something else is using this port.")
            alt_port = port + 1
            while check_port_in_use(alt_port) and alt_port < port + 10:
                alt_port += 1

            if not check_port_in_use(alt_port):
                if confirm(f"Use port {alt_port} instead?"):
                    port = alt_port
                else:
                    print_info("Cancelled.")
                    get_input("\nPress Enter to return to main menu...")
                    return
            else:
                print_error("Could not find an available port.")
                get_input("\nPress Enter to return to main menu...")
                return
    else:
        print_success(f"Port {port} is available!")

    # Show SSH tunnel instructions if remote
    if is_remote:
        # Try to get username
        username = os.environ.get('USER', 'user')

        # Try to get the EC2 public IP if available
        public_ip = None
        try:
            # Try to get public IP from EC2 metadata (if on EC2)
            result = subprocess.run(
                ["curl", "-s", "--connect-timeout", "2",
                 "http://169.254.169.254/latest/meta-data/public-ipv4"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                public_ip = result.stdout.strip()
        except Exception:
            pass

        # Use public IP if available, otherwise use server_ip from SSH_CONNECTION
        remote_ip = public_ip or server_ip

        print(f"""
{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
{C.BRIGHT_WHITE}  SSH TUNNEL INSTRUCTIONS{C.RESET}
{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}

{C.WHITE}You're connected via SSH. To access the SpiderFoot GUI:{C.RESET}

{C.BRIGHT_YELLOW}Step 1:{C.RESET} Open a {C.UNDERLINE}NEW{C.RESET} terminal on your {C.BRIGHT_CYAN}local machine{C.RESET}

{C.BRIGHT_YELLOW}Step 2:{C.RESET} Run this SSH tunnel command:

  {C.BRIGHT_WHITE}ssh -L {port}:localhost:{port} {username}@{remote_ip}{C.RESET}

{C.BRIGHT_YELLOW}Step 3:{C.RESET} Open in your browser:

  {C.BRIGHT_WHITE}http://localhost:{port}{C.RESET}

{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}

{C.DIM}Your Host IP (detected): {host_ip}
Remote Server IP: {remote_ip}{C.RESET}
""")
    else:
        print(f"""
{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
{C.WHITE}SpiderFoot will be available at:{C.RESET}

  {C.BRIGHT_WHITE}http://localhost:{port}{C.RESET}
{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
""")

    if not confirm("Start SpiderFoot web server now?"):
        print_info("Cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Check if tmux is installed
    print_info("Checking if tmux is installed...")
    try:
        result = subprocess.run(["which", "tmux"], capture_output=True, text=True)
        tmux_installed = result.returncode == 0
    except Exception:
        tmux_installed = False

    if not tmux_installed:
        print_warning("tmux is not installed. Installing it is recommended for better session management.")
        if confirm("Install tmux now?"):
            try:
                subprocess.run(["sudo", "apt", "install", "-y", "tmux"], timeout=60)
                print_success("tmux installed!")
                tmux_installed = True
            except Exception as e:
                print_error(f"Failed to install tmux: {e}")
                tmux_installed = False

    # Build the command
    python_exe = sf_python if sf_python and os.path.exists(sf_python) else "python3"
    session_name = "spiderfoot-gui"

    if tmux_installed:
        # Check if session already exists
        check_session = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True
        )

        if check_session.returncode == 0:
            print_warning(f"tmux session '{session_name}' already exists!")
            if confirm("Kill existing session and create a new one?"):
                subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
                print_success(f"Killed session '{session_name}'")
            else:
                print_info(f"To attach to the existing session: tmux attach -t {session_name}")
                get_input("\nPress Enter to return to main menu...")
                return

        # Build the SpiderFoot command for tmux
        # Use shlex.quote to prevent command injection via path variables
        sf_cmd = f"{shlex.quote(python_exe)} {shlex.quote(str(sf_path))} -l 127.0.0.1:{port}"

        print()
        print_info(f"Starting SpiderFoot in tmux session '{session_name}'...")
        print()

        if is_remote:
            print(f"{C.BRIGHT_YELLOW}Remember:{C.RESET} Set up the SSH tunnel in another terminal first!")
            print(f"{C.DIM}ssh -L {port}:localhost:{port} {username}@{remote_ip}{C.RESET}")
            print()

        print(f"{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
        print(f"{C.WHITE}tmux session '{session_name}' commands:{C.RESET}")
        print(f"  {C.BRIGHT_YELLOW}tmux attach -t {session_name}{C.RESET}  - View SpiderFoot output")
        print(f"  {C.BRIGHT_YELLOW}Ctrl+b d{C.RESET}                     - Detach (leave running in background)")
        print(f"  {C.BRIGHT_YELLOW}tmux kill-session -t {session_name}{C.RESET} - Stop SpiderFoot")
        print(f"{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
        print()

        # Create tmux session and run SpiderFoot
        try:
            # Create detached session with SpiderFoot command
            subprocess.run([
                "tmux", "new-session", "-d", "-s", session_name,
                "-c", str(sf_dir),  # Set working directory
                sf_cmd
            ], check=True)

            print_success(f"SpiderFoot web server started in tmux session '{session_name}'!")
            print()
            print_info(f"SpiderFoot is now running at: http://localhost:{port}")
            print_info(f"To view output: tmux attach -t {session_name}")
            print_info(f"To stop server: tmux kill-session -t {session_name}")

        except subprocess.CalledProcessError as e:
            print_error(f"Failed to start SpiderFoot in tmux: {e}")

    else:
        # Fallback: run without tmux (blocks current session)
        print_warning("Running SpiderFoot without tmux (will block this session)")
        cmd = [python_exe, sf_path, "-l", f"127.0.0.1:{port}"]

        print()
        print_info(f"Starting SpiderFoot on port {port}...")
        print(f"{C.DIM}Command: {' '.join(cmd)}{C.RESET}")
        print()

        if is_remote:
            print(f"{C.BRIGHT_YELLOW}Remember:{C.RESET} Set up the SSH tunnel in another terminal first!")
            print(f"{C.DIM}ssh -L {port}:localhost:{port} {username}@{remote_ip}{C.RESET}")
            print()

        print(f"{C.BRIGHT_GREEN}Press Ctrl+C to stop the server and return to menu.{C.RESET}")
        print()

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(sf_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in process.stdout:
                if line.strip():
                    print(f"  {line.rstrip()}")

            process.wait()

        except KeyboardInterrupt:
            print()
            print_info("Stopping SpiderFoot web server...")
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            print_success("SpiderFoot stopped.")

        except FileNotFoundError:
            print_error(f"Could not find Python at: {python_exe}")

        except Exception as e:
            print_error(f"Error running SpiderFoot: {e}")

    get_input("\nPress Enter to return to main menu...")


def show_help():
    """Display help information"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_banner_help()
        cyber_header("HELP & DOCUMENTATION")

        console.print("[bold white]What would you like help with?[/]\n")
        console.print("  [bold yellow][1][/] How PUPPETMASTER works")
        console.print("  [bold yellow][2][/] SpiderFoot installation guide")
        console.print("  [bold yellow][3][/] Signal types explained")
        console.print("  [bold yellow][4][/] Output files explained")
        console.print("  [bold yellow][5][/] Back to main menu")
        console.print()
    else:
        print_banner()
        print_section("Help & Documentation", C.BRIGHT_BLUE)

        print(f"""
{C.WHITE}What would you like help with?{C.RESET}

  {C.BRIGHT_YELLOW}[1]{C.RESET} How PUPPETMASTER works
  {C.BRIGHT_YELLOW}[2]{C.RESET} SpiderFoot installation guide
  {C.BRIGHT_YELLOW}[3]{C.RESET} Signal types explained
  {C.BRIGHT_YELLOW}[4]{C.RESET} Output files explained
  {C.BRIGHT_YELLOW}[5]{C.RESET} Back to main menu
""")

    choice = get_input("Choice", "1")
    if choice is None or choice == '5':
        return

    if choice == '1':
        show_help_overview()
    elif choice == '2':
        show_spiderfoot_install_guide()
    elif choice == '3':
        show_help_signals()
    elif choice == '4':
        show_help_outputs()


def show_help_overview():
    """Show general help overview"""
    clear_screen()
    print_banner()
    print_section("How PUPPETMASTER Works", C.BRIGHT_BLUE)

    help_text = f"""
{C.BOLD}WHAT IS THIS TOOL?{C.RESET}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PUPPETMASTER analyzes SpiderFoot OSINT scan data to identify "sock puppet"
networks - groups of websites that appear independent but are actually
controlled by the same entity.

{C.BOLD}COMPLETE WORKFLOW{C.RESET}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{C.BRIGHT_CYAN}Step 1: DISCOVER{C.RESET} - Find domains to investigate
   • Use option [1] to scrape domains from keywords
   • Or use option [2] to load your own domain list

{C.BRIGHT_CYAN}Step 2: SCAN{C.RESET} - Run SpiderFoot on those domains
   • Use option [3] to batch scan all domains
   • Scans run in parallel (configurable)
   • Progress is saved - you can resume if interrupted

{C.BRIGHT_CYAN}Step 3: ANALYZE{C.RESET} - Find connections between domains
   • Use option [5] to analyze the SpiderFoot exports
   • PUPPETMASTER finds shared infrastructure

{C.BRIGHT_CYAN}Step 4: REVIEW{C.RESET} - Examine the findings
   • Start with executive_summary.md
   • Check smoking_guns.csv for definitive proof
   • Use clusters.csv to see domain groupings

{C.BOLD}WORKFLOW TIPS{C.RESET}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Start with domains you {C.UNDERLINE}suspect{C.RESET} are connected
• More domains = better network analysis (but slower)
• Review smoking guns first - these are your strongest evidence
• Hub domains may indicate the "puppet master" controller
"""
    print(help_text)
    get_input("\nPress Enter to return to help menu...")
    show_help()


def install_spiderfoot_interactive():
    """Interactively install SpiderFoot with its own virtual environment"""
    clear_screen()
    print_banner()
    print_section("SpiderFoot Auto-Installer", C.BRIGHT_GREEN)

    # Default to project directory
    script_dir = Path(__file__).parent
    default_install_dir = str(script_dir / "spiderfoot")

    print(f"""
{C.WHITE}This will install SpiderFoot with its own virtual environment.{C.RESET}

{C.WHITE}Source:{C.RESET}  {C.CYAN}https://github.com/smicallef/spiderfoot{C.RESET}
{C.DIM}         (Official SpiderFoot repository by Steve Micallef){C.RESET}

{C.DIM}Steps:
  1. Clone SpiderFoot from GitHub
  2. Install system dependencies (libxml2, etc.)
  3. Create virtual environment for SpiderFoot
  4. Install Python dependencies
  5. Verify installation & save to config{C.RESET}
""")

    install_dir = get_input(f"Install location", default_install_dir)
    if install_dir is None:
        print_info("Cancelled.")
        return None

    install_dir = os.path.expanduser(install_dir)
    sf_path = os.path.join(install_dir, "sf.py")
    sf_venv_path = os.path.join(install_dir, "venv")

    # Determine venv python path
    if os.name == 'nt':  # Windows
        sf_venv_python = os.path.join(sf_venv_path, "Scripts", "python.exe")
    else:  # Linux/Mac
        sf_venv_python = os.path.join(sf_venv_path, "bin", "python3")

    # Check if already installed with working venv
    if os.path.exists(sf_path) and os.path.exists(sf_venv_python):
        print_success(f"SpiderFoot already exists at: {sf_path}")
        print_info("Verifying installation...")
        try:
            result = subprocess.run(
                [sf_venv_python, sf_path, "--help"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                print_success("SpiderFoot is working!")
                # Save to config
                config = load_config()
                config['spiderfoot_path'] = sf_path
                config['spiderfoot_python'] = sf_venv_python
                save_config(config)
                print_success(f"Saved to config!")
                return (sf_path, sf_venv_python)
            else:
                print_warning("SpiderFoot exists but verification failed.")
        except Exception as e:
            print_warning(f"Could not verify: {e}")

        if not confirm("Reinstall SpiderFoot?"):
            return None

    print_section("Installing SpiderFoot", C.BRIGHT_CYAN)

    # Step 1: Clone repository
    print_info("Step 1/4: Cloning SpiderFoot repository...")
    if os.path.exists(install_dir):
        print_info(f"Removing existing directory: {install_dir}")
        try:
            import shutil
            shutil.rmtree(install_dir)
        except Exception as e:
            print_error(f"Could not remove directory: {e}")
            return None

    try:
        result = subprocess.run(
            ["git", "clone", "https://github.com/smicallef/spiderfoot.git", install_dir],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            print_success("Repository cloned!")
        else:
            print_error(f"Git clone failed: {result.stderr}")
            print_info("Make sure git is installed: sudo apt install git")
            return None
    except FileNotFoundError:
        print_error("Git not found. Please install git first:")
        print_info("  sudo apt install git")
        return None
    except subprocess.TimeoutExpired:
        print_error("Clone timed out. Check your internet connection.")
        return None
    except Exception as e:
        print_error(f"Clone failed: {e}")
        return None

    # Step 2: Install system dependencies (needed for lxml, etc.)
    print_info("Step 2/5: Installing system dependencies...")
    print(f"{C.DIM}Some Python packages need system libraries to compile.{C.RESET}")

    try:
        # Install build dependencies AND pre-built Python packages for problematic deps
        # These packages are then skipped in pip install to avoid version conflicts
        print(f"{C.DIM}Running apt install (this may take a minute)...{C.RESET}")
        result = subprocess.run(
            ["sudo", "apt", "install", "-y",
             # Build dependencies
             "libxml2-dev", "libxslt-dev", "libffi-dev",
             "python3-dev", "build-essential", "pkg-config",
             "rustc", "cargo",
             # Pre-built Python packages (avoids compilation issues on Python 3.13)
             "python3-lxml",         # lxml<5 won't compile on Python 3.13
             "python3-cryptography", # cryptography needs Rust
             "python3-openssl",      # pyopenssl - must match cryptography version
             "python3-bs4",          # beautifulsoup4
             "python3-yaml",         # pyyaml
             "python3-requests"],    # requests
            capture_output=True,  # Capture to prevent terminal spam
            text=True,
            timeout=180
        )
        if result.returncode == 0:
            print_success("System dependencies installed!")
        else:
            print_warning("Some system dependencies may not have installed (continuing anyway)")
            if result.stderr:
                print(f"{C.DIM}{result.stderr[:200]}{C.RESET}")
    except subprocess.TimeoutExpired:
        print_warning("System dependency installation timed out (continuing anyway)")
    except Exception as e:
        print_warning(f"Could not install system dependencies: {e}")
        print_info("If pip fails, try manually:")
        print(f"  {C.DIM}sudo apt install python3-lxml python3-bs4 python3-cryptography python3-openssl python3-yaml python3-requests{C.RESET}")

    # Step 3: Create virtual environment for SpiderFoot
    print_info("Step 3/5: Creating virtual environment for SpiderFoot...")
    print(f"{C.DIM}Using --system-site-packages to access pre-built lxml/cryptography{C.RESET}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "venv", "--system-site-packages", sf_venv_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print_success(f"Virtual environment created at: {sf_venv_path}")
        else:
            print_error(f"Failed to create venv: {result.stderr}")
            return None

        # Check the venv python exists
        if not os.path.exists(sf_venv_python):
            # Try alternate path
            alt_python = os.path.join(sf_venv_path, "bin", "python")
            if os.path.exists(alt_python):
                sf_venv_python = alt_python
            else:
                print_error("Could not find Python in the created venv")
                return None

    except Exception as e:
        print_error(f"Failed to create venv: {e}")
        return None

    # Step 4: Install dependencies into SpiderFoot's venv
    print_info("Step 4/5: Installing Python dependencies (this may take a few minutes)...")
    requirements_file = os.path.join(install_dir, "requirements.txt")

    if not os.path.exists(requirements_file):
        print_warning("requirements.txt not found!")
        return None

    # First upgrade pip and install wheel
    print(f"{C.DIM}Upgrading pip and installing wheel...{C.RESET}")
    try:
        subprocess.run(
            [sf_venv_python, "-m", "pip", "install", "--upgrade", "pip", "setuptools<81", "wheel", "--quiet"],
            capture_output=True,
            text=True,
            timeout=120
        )
    except Exception:
        pass  # Continue anyway

    # Packages that we installed via apt (skip these in pip to avoid version conflicts)
    # These correspond to: python3-lxml, python3-bs4, python3-cryptography, python3-openssl, python3-yaml, python3-requests
    skip_packages = {'lxml', 'beautifulsoup4', 'bs4', 'cryptography', 'pyopenssl', 'pyyaml', 'yaml', 'requests'}

    # Read and filter requirements
    print(f"{C.DIM}Filtering requirements to avoid conflicts with system packages...{C.RESET}")
    try:
        with open(requirements_file, 'r') as f:
            requirements = f.readlines()

        # Filter out packages we have from apt
        filtered_reqs = []
        for req in requirements:
            req = req.strip()
            if not req or req.startswith('#'):
                continue
            # Extract package name (before any version specifier)
            pkg_name = req.split('<')[0].split('>')[0].split('=')[0].split('[')[0].lower()
            if pkg_name not in skip_packages:
                filtered_reqs.append(req)
            else:
                print(f"  {C.DIM}Skipping {pkg_name} (using system version){C.RESET}")

        # Write filtered requirements to temp file
        filtered_req_file = os.path.join(install_dir, "requirements_filtered.txt")
        with open(filtered_req_file, 'w') as f:
            f.write('\n'.join(filtered_reqs))

        print(f"{C.DIM}Installing {len(filtered_reqs)} packages...{C.RESET}")

    except Exception as e:
        print_warning(f"Could not filter requirements: {e}")
        filtered_req_file = requirements_file

    # Try installing filtered requirements
    try:
        result = subprocess.run(
            [sf_venv_python, "-m", "pip", "install", "-r", filtered_req_file, "--quiet"],
            capture_output=True,
            text=True,
            timeout=900
        )

        if result.returncode == 0:
            print_success("Dependencies installed!")
        else:
            # Try again and capture the verbose output to show errors
            print_warning("First attempt failed, retrying...")
            result = subprocess.run(
                [sf_venv_python, "-m", "pip", "install", "-r", filtered_req_file],
                capture_output=True,  # Still capture to prevent terminal spam
                text=True,
                timeout=900
            )

            if result.returncode == 0:
                print_success("Dependencies installed!")
            else:
                # Show relevant error lines if any
                if result.stderr:
                    error_lines = [l for l in result.stderr.split('\n') if 'error' in l.lower()][:3]
                    if error_lines:
                        for line in error_lines:
                            print(f"  {C.DIM}{line[:100]}{C.RESET}")

                # Try installing core packages one by one
                print_warning("Some packages failed. Installing core packages individually...")
                core_packages = [
                    "cherrypy", "cherrypy-cors", "mako", "dnspython", "netaddr",
                    "pysocks", "ipwhois", "phonenumbers", "publicsuffixlist",
                    "pyopenssl", "openpyxl", "exifread", "pypdf2", "networkx>=2.6"
                ]
                installed = 0
                for pkg in core_packages:
                    try:
                        res = subprocess.run(
                            [sf_venv_python, "-m", "pip", "install", pkg, "--quiet"],
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                        if res.returncode == 0:
                            installed += 1
                    except Exception:
                        pass

                print_success(f"Installed {installed}/{len(core_packages)} core packages.")
                print_info("SpiderFoot should work for most scanning operations.")

    except subprocess.TimeoutExpired:
        print_error("Dependency installation timed out.")
        return None
    except Exception as e:
        print_error(f"Dependency installation failed: {e}")
        return None

    # Step 5: Verify installation
    print_info("Step 5/5: Verifying installation...")
    if not os.path.exists(sf_path):
        print_error(f"sf.py not found at: {sf_path}")
        return None

    verification_success = False
    try:
        result = subprocess.run(
            [sf_venv_python, sf_path, "--help"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and "SpiderFoot" in result.stdout:
            print_success("SpiderFoot installed and verified!")
            verification_success = True
        else:
            print_error("Verification failed:")
            print(f"{C.DIM}{result.stderr[:300]}{C.RESET}")
    except Exception as e:
        print_error(f"Verification failed: {e}")

    if not verification_success:
        print_error("SpiderFoot installation failed verification.")
        return None

    # Save to config
    config = load_config()
    config['spiderfoot_path'] = sf_path
    config['spiderfoot_python'] = sf_venv_python
    save_config(config)

    print(f"""
{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
{C.GREEN}✓{C.RESET} SpiderFoot installed successfully!

  {C.WHITE}Location:{C.RESET} {sf_path}
  {C.WHITE}Python:{C.RESET}   {sf_venv_python}
  {C.WHITE}Config:{C.RESET}   Saved!

  {C.DIM}You can now use option [3] to run SpiderFoot scans.{C.RESET}
{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
""")

    return (sf_path, sf_venv_python)


def show_spiderfoot_install_guide():
    """Show SpiderFoot installation guide"""
    clear_screen()
    print_banner()
    print_section("SpiderFoot Installation Guide", C.BRIGHT_BLUE)

    print(f"""
{C.WHITE}How would you like to install SpiderFoot?{C.RESET}

  {C.BRIGHT_GREEN}[1]{C.RESET} {C.BOLD}Auto-install (recommended){C.RESET}
      {C.DIM}Let PUPPETMASTER install SpiderFoot for you{C.RESET}

  {C.BRIGHT_YELLOW}[2]{C.RESET} Manual install - Linux (Debian/Ubuntu/Kali)
  {C.BRIGHT_YELLOW}[3]{C.RESET} Manual install - macOS
  {C.BRIGHT_YELLOW}[4]{C.RESET} Manual install - Windows
  {C.BRIGHT_YELLOW}[5]{C.RESET} Back to help menu
""")

    choice = get_input("Choice", "1")
    if choice is None or choice == '5':
        show_help()
        return

    if choice == '1':
        result = install_spiderfoot_interactive()
        get_input("\nPress Enter to return to help menu...")
        show_help()
        return

    clear_screen()
    print_banner()

    if choice == '2':
        print(f"""
{C.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SPIDERFOOT INSTALLATION - Linux (Debian/Ubuntu/Kali)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}

{C.WHITE}Copy and paste these commands:{C.RESET}

{C.BRIGHT_GREEN}# Clone SpiderFoot{C.RESET}
git clone https://github.com/smicallef/spiderfoot.git
cd spiderfoot

{C.BRIGHT_GREEN}# Install dependencies{C.RESET}
pip3 install -r requirements.txt

{C.BRIGHT_GREEN}# Test installation{C.RESET}
python3 sf.py --help

{C.BRIGHT_GREEN}# (Optional) Start web UI{C.RESET}
python3 sf.py -l 127.0.0.1:5001

{C.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
{C.DIM}After installation, note the path to sf.py (e.g., /home/user/spiderfoot/sf.py)
You'll need to provide this path when running SpiderFoot scans.{C.RESET}
{C.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
""")

    elif choice == '3':
        print(f"""
{C.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SPIDERFOOT INSTALLATION - macOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}

{C.WHITE}Copy and paste these commands:{C.RESET}

{C.BRIGHT_GREEN}# Install prerequisites (if needed){C.RESET}
brew install python3 git

{C.BRIGHT_GREEN}# Clone SpiderFoot{C.RESET}
git clone https://github.com/smicallef/spiderfoot.git
cd spiderfoot

{C.BRIGHT_GREEN}# Install dependencies{C.RESET}
pip3 install -r requirements.txt

{C.BRIGHT_GREEN}# Test installation{C.RESET}
python3 sf.py --help

{C.BRIGHT_GREEN}# (Optional) Start web UI{C.RESET}
python3 sf.py -l 127.0.0.1:5001

{C.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
{C.DIM}After installation, note the path to sf.py (e.g., /Users/you/spiderfoot/sf.py)
You'll need to provide this path when running SpiderFoot scans.{C.RESET}
{C.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
""")

    elif choice == '4':
        print(f"""
{C.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SPIDERFOOT INSTALLATION - Windows
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}

{C.WHITE}Step 1: Install Prerequisites{C.RESET}
  • Install Python 3 from https://www.python.org/downloads/
    {C.DIM}(Make sure to check "Add Python to PATH"){C.RESET}
  • Install Git from https://git-scm.com/download/win

{C.WHITE}Step 2: Open Command Prompt or PowerShell and run:{C.RESET}

{C.BRIGHT_GREEN}# Clone SpiderFoot{C.RESET}
git clone https://github.com/smicallef/spiderfoot.git
cd spiderfoot

{C.BRIGHT_GREEN}# Install dependencies{C.RESET}
pip install -r requirements.txt

{C.BRIGHT_GREEN}# Test installation{C.RESET}
python sf.py --help

{C.BRIGHT_GREEN}# (Optional) Start web UI{C.RESET}
python sf.py -l 127.0.0.1:5001

{C.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
{C.DIM}After installation, note the path to sf.py (e.g., C:\\Users\\You\\spiderfoot\\sf.py)
You'll need to provide this path when running SpiderFoot scans.{C.RESET}
{C.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
""")

    get_input("\nPress Enter to return to help menu...")
    show_help()


def show_help_signals():
    """Show signal types explanation"""
    clear_screen()
    print_banner()
    print_section("Signal Types Explained", C.BRIGHT_BLUE)

    print(f"""
{C.BOLD}SIGNAL TYPES{C.RESET}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{C.BRIGHT_RED}🔴 SMOKING GUNS{C.RESET} (Definitive - one match = confirmed connection)
   These are unique identifiers that prove same ownership:

   • {C.WHITE}Google Analytics ID{C.RESET} (UA-XXXXXX or G-XXXXXX)
     Each Analytics account has a unique ID. Same ID = same operator.

   • {C.WHITE}AdSense Publisher ID{C.RESET} (pub-XXXXXXXX)
     AdSense accounts are tied to real identities. Same ID = same person.

   • {C.WHITE}Google Site Verification{C.RESET}
     Unique token proving ownership of Search Console account.

   • {C.WHITE}Unique Email Address{C.RESET}
     Same contact email in WHOIS or on-page = same operator.

   • {C.WHITE}SSL Certificate Fingerprint{C.RESET}
     Custom (non-shared) SSL certs prove same infrastructure.

{C.BRIGHT_YELLOW}🟡 STRONG SIGNALS{C.RESET} (2+ matches = likely connected)
   Strong evidence, but could occasionally be coincidental:

   • {C.WHITE}WHOIS Registrant{C.RESET} - Same name/org in domain registration
   • {C.WHITE}Phone Number{C.RESET} - Same contact phone across sites
   • {C.WHITE}Custom Nameserver{C.RESET} - Unique DNS servers (not ns1.google.com)
   • {C.WHITE}Facebook Pixel ID{C.RESET} - Shared advertising tracking

{C.BRIGHT_GREEN}🟢 WEAK SIGNALS{C.RESET} (Filtered out - too many false positives)
   These are excluded because they're shared infrastructure:

   • Cloudflare IPs - millions of sites use Cloudflare
   • AWS/Azure/GCP hosting - common cloud providers
   • Registrar abuse emails - generic contacts
   • Common nameservers - ns1.google.com, etc.
""")

    get_input("\nPress Enter to return to help menu...")
    show_help()


def show_help_outputs():
    """Show output files explanation"""
    clear_screen()
    print_banner()
    print_section("Output Files Explained", C.BRIGHT_BLUE)

    print(f"""
{C.BOLD}OUTPUT FILES{C.RESET}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{C.BRIGHT_CYAN}executive_summary.md{C.RESET} - {C.WHITE}START HERE!{C.RESET}
   Human-readable overview of all findings. Includes:
   • Key statistics (domains analyzed, connections found)
   • High-confidence cluster summaries
   • Top hub domains (potential controllers)
   • Recommended next steps

{C.BRIGHT_CYAN}smoking_guns.csv{C.RESET}
   All definitive connections with evidence. Columns:
   domain1, domain2, signal_type, signal_value, confidence

{C.BRIGHT_CYAN}clusters.csv{C.RESET}
   Domain groupings by cluster ID. Each cluster represents
   a group of domains that share connections.

{C.BRIGHT_CYAN}hub_analysis.csv{C.RESET}
   Domains with high centrality scores - these connect many
   other domains and may be "command and control" infrastructure.

{C.BRIGHT_CYAN}all_connections.csv{C.RESET}
   Complete list of every connection found, including weak signals.
   Use for deep-dive analysis.

{C.BRIGHT_CYAN}signals.csv{C.RESET}
   Raw signal data extracted from SpiderFoot exports.
   Useful for custom analysis.

{C.BRIGHT_CYAN}network.graphml{C.RESET}
   Graph file for visualization tools (Gephi, Cytoscape, etc.)
   Nodes = domains, Edges = connections.
""")

    get_input("\nPress Enter to return to help menu...")
    show_help()

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

# =============================================================================
# DISCOVERY & SCANNING FUNCTIONS
# =============================================================================

def run_domain_scrape(keywords, use_google, use_duckduckgo, max_results, existing_domains=None):
    """Run the actual domain scraping and return results"""
    from discovery.scraper import DomainScraper

    print_section("Scraping Domains", C.BRIGHT_MAGENTA)
    print(f"{C.DIM}Safe mode enabled - 2-3 second delays between requests{C.RESET}\n")

    scraper = DomainScraper(delay_range=(2, 4))

    # If we have existing domains, add them to the scraper
    if existing_domains:
        scraper.domains = set(existing_domains)

    def progress_callback(keyword, current, total):
        print(f"  {C.CYAN}[{current}/{total}]{C.RESET} Searching: \"{keyword}\"")

    try:
        domains = scraper.search_all(
            keywords=keywords,
            max_results_per_keyword=max_results,
            use_google=use_google,
            use_duckduckgo=use_duckduckgo,
            progress_callback=progress_callback
        )
    except KeyboardInterrupt:
        print_warning("\nScraping interrupted by user.")
        domains = scraper.domains

    # Show errors if any
    if scraper.errors:
        print()
        print_warning("Search errors occurred:")
        for error in scraper.errors[:5]:  # Limit to first 5
            print(f"  {C.DIM}• {error}{C.RESET}")
        if len(scraper.errors) > 5:
            print(f"  {C.DIM}• ... and {len(scraper.errors) - 5} more{C.RESET}")

    return domains


def interactive_domain_removal(domains: set) -> set:
    """
    Interactive UI for reviewing and removing domains.
    Uses simple-term-menu for arrow key navigation with search.
    Loops until user chooses to proceed.

    Args:
        domains: Set of domains to review

    Returns:
        Filtered set of domains (with removals applied)
    """
    if not domains:
        return domains

    # Try to import simple-term-menu
    try:
        from simple_term_menu import TerminalMenu
    except ImportError:
        print_warning("simple-term-menu not installed, skipping interactive review")
        print_info("Install with: pip install simple-term-menu")
        return domains

    # Try to import blacklist for permanent additions
    try:
        from core.blacklist import add_to_blacklist
        blacklist_available = True
    except ImportError:
        blacklist_available = False

    current_domains = set(domains)  # Work with a copy

    # Main review loop
    while True:
        sorted_domains = sorted(current_domains)
        domain_count = len(sorted_domains)

        # Show pre-review menu
        print(f"\n{C.BRIGHT_CYAN}{'━' * 65}{C.RESET}")
        print(f"  {C.BRIGHT_WHITE}DOMAIN REVIEW{C.RESET} {C.DIM}// {domain_count} domains{C.RESET}")
        print(f"{C.BRIGHT_CYAN}{'━' * 65}{C.RESET}")

        # Warn about large lists
        if domain_count > 500:
            print(f"\n  {C.BRIGHT_YELLOW}⚠ Large list ({domain_count} domains) - review may be slow{C.RESET}")

        print(f"\n  {C.BRIGHT_MAGENTA}[r]{C.RESET} Review & remove domains (↑/↓ navigate, TAB select, / search)")
        print(f"  {C.BRIGHT_MAGENTA}[d]{C.RESET} Done - proceed with {domain_count} domains")
        print(f"  {C.BRIGHT_MAGENTA}[q]{C.RESET} Cancel\n")

        choice = get_input("Choice", "d")
        if choice is None or choice.lower() == 'q':
            print_info("Cancelled")
            return current_domains
        elif choice.lower() == 'd':
            print_success(f"Proceeding with {domain_count} domains")
            return current_domains
        elif choice.lower() != 'r':
            print_success(f"Proceeding with {domain_count} domains")
            return current_domains

        # Show interactive picker
        print(f"\n{C.BRIGHT_MAGENTA}{'━' * 65}{C.RESET}")
        print(f"  {C.BRIGHT_WHITE}SELECT DOMAINS TO REMOVE{C.RESET}")
        print(f"{C.BRIGHT_MAGENTA}{'━' * 65}{C.RESET}")
        print(f"  {C.BRIGHT_CYAN}↑/↓{C.RESET} Navigate  {C.BRIGHT_CYAN}TAB{C.RESET} Toggle  {C.BRIGHT_CYAN}/{C.RESET} Search  {C.BRIGHT_CYAN}ESC{C.RESET} Exit search  {C.BRIGHT_CYAN}ENTER{C.RESET} Confirm")
        print(f"{C.DIM}{'─' * 65}{C.RESET}\n")

        try:
            menu = TerminalMenu(
                sorted_domains,
                title=f"  [{domain_count} domains] - TAB to select, ENTER when done",
                multi_select=True,
                show_multi_select_hint=True,
                multi_select_select_on_accept=False,
                multi_select_empty_ok=True,
                # Cyberpunk styling
                menu_cursor="▸ ",
                menu_cursor_style=("fg_purple", "bold"),
                menu_highlight_style=("fg_cyan", "bold"),
                search_key="/",
                search_highlight_style=("fg_yellow", "bold"),
                cycle_cursor=True,
                clear_screen=False,
            )

            selected_indices = menu.show()

        except Exception as e:
            print_warning(f"Interactive menu failed: {e}")
            continue  # Go back to review menu

        # Handle no selection
        if not selected_indices:
            print_info("No domains selected")
            continue  # Loop back to review menu

        # Convert indices to domain names
        to_remove = {sorted_domains[i] for i in selected_indices}

        # Confirmation
        print(f"\n{C.BRIGHT_YELLOW}{'═' * 65}{C.RESET}")
        print(f"  {C.BRIGHT_WHITE}CONFIRM REMOVAL{C.RESET} - {len(to_remove)} domain(s) selected")
        print(f"{C.DIM}{'─' * 65}{C.RESET}")

        for d in sorted(to_remove)[:15]:
            print(f"  {C.BRIGHT_RED}✗{C.RESET} {d}")
        if len(to_remove) > 15:
            print(f"  {C.DIM}... and {len(to_remove) - 15} more{C.RESET}")

        print(f"{C.BRIGHT_YELLOW}{'═' * 65}{C.RESET}")

        print(f"\n  {C.BRIGHT_CYAN}[1]{C.RESET} Remove (this session only)")
        if blacklist_available:
            print(f"  {C.BRIGHT_CYAN}[2]{C.RESET} Remove + add to permanent blacklist")
        print(f"  {C.BRIGHT_CYAN}[3]{C.RESET} Cancel - go back\n")

        confirm_choice = get_input("Choice", "1")

        if confirm_choice == '1':
            current_domains = current_domains - to_remove
            print_success(f"Removed {len(to_remove)} domains ({len(current_domains)} remaining)")
            # Loop continues - user can review more or choose [d] to proceed
        elif confirm_choice == '2' and blacklist_available:
            for d in to_remove:
                add_to_blacklist(d, persistent=True)
            current_domains = current_domains - to_remove
            print_success(f"Removed {len(to_remove)} domains + added to permanent blacklist ({len(current_domains)} remaining)")
            # Loop continues
        else:
            print_info("Cancelled - no changes made")
            # Loop continues


def show_scrape_results_menu(domains, keywords, use_google, use_duckduckgo, max_results):
    """Show post-scrape menu with options to view, re-run, add more, etc."""
    from discovery.scraper import DomainScraper

    while True:
        clear_screen()

        # Use cyberpunk UI if available
        if CYBER_UI_AVAILABLE:
            console = get_console()
            from rich.panel import Panel
            from rich.text import Text

            cyber_banner_discovery()
            cyber_header("SCRAPE RESULTS")

            # Show summary in panel
            summary_text = Text()
            summary_text.append("Current Working Set:\n", style="bold white")
            summary_text.append("  Domains collected:  ", style="dim")
            summary_text.append(f"{len(domains)}\n", style="bold green")
            summary_text.append("  Keywords used:      ", style="dim")
            summary_text.append(f"{len(keywords)}\n\n", style="white")
            keywords_preview = ', '.join(keywords[:3]) + ('...' if len(keywords) > 3 else '')
            summary_text.append(f"Last keywords: {keywords_preview}", style="dim italic")

            console.print(Panel(summary_text, title="[bold green]⟨ RESULTS ⟩[/]", border_style="green"))
            console.print()

            console.print("[bold white]What would you like to do?[/]\n")
            console.print("  [bold yellow]\\[1][/] View domains")
            console.print("  [bold yellow]\\[2][/] Add more keywords (keep current domains)")
            console.print("  [bold green]\\[A][/] Manually add domains")
            console.print("  [bold yellow]\\[3][/] Re-run with same keywords")
            console.print("  [bold yellow]\\[4][/] Start fresh (new keywords)")
            console.print("  [bold yellow]\\[5][/] Save list to file")
            console.print("  [bold magenta]\\[R][/] Review & remove domains")
            if KALI_MODULE_AVAILABLE and is_enhanced_mode():
                console.print("  [bold cyan]\\[K][/] Expand with Kali tools")
            console.print("  [bold yellow]\\[6][/] Load into SpiderFoot scan queue")
            console.print("  [bold yellow]\\[7][/] Back to main menu")
            console.print()
        else:
            print_banner()
            print_section("Scrape Results", C.BRIGHT_GREEN)

            # Show summary
            print(f"""
{C.WHITE}Current Working Set:{C.RESET}
  Domains collected:  {C.BRIGHT_GREEN}{len(domains)}{C.RESET}
  Keywords used:      {len(keywords)}

{C.DIM}Last keywords: {', '.join(keywords[:3])}{'...' if len(keywords) > 3 else ''}{C.RESET}
""")

            print(f"{C.WHITE}What would you like to do?{C.RESET}\n")
            print_menu_item("1", "View domains", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("2", "Add more keywords (keep current domains)", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("a", "Manually add domains", f"{C.BRIGHT_GREEN}◆{C.RESET}")
            print_menu_item("3", "Re-run with same keywords", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("4", "Start fresh (new keywords)", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("5", "Save list to file", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("r", "Review & remove domains", f"{C.BRIGHT_MAGENTA}◆{C.RESET}")
            # Show Kali option if available
            if KALI_MODULE_AVAILABLE and is_enhanced_mode():
                print_menu_item("k", "Expand with Kali tools", f"{C.BRIGHT_CYAN}◆{C.RESET}")
            print_menu_item("6", "Load into SpiderFoot scan queue", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("7", "Back to main menu", f"{C.BRIGHT_RED}◆{C.RESET}")
            print()

        choice = get_input("Choice", "6")
        if choice is None:
            choice = "7"

        if choice == "1":
            # View domains
            clear_screen()
            print_banner()
            print_section(f"Domains Found ({len(domains)})", C.BRIGHT_CYAN)

            sorted_domains = sorted(domains)
            # Paginate if too many
            page_size = 30
            total_pages = (len(sorted_domains) + page_size - 1) // page_size

            page = 0
            while True:
                start = page * page_size
                end = min(start + page_size, len(sorted_domains))

                print(f"\n{C.DIM}Showing {start + 1}-{end} of {len(sorted_domains)}{C.RESET}\n")
                for i, domain in enumerate(sorted_domains[start:end], start + 1):
                    print(f"  {C.DIM}{i:4d}.{C.RESET} {domain}")

                print()
                if total_pages > 1:
                    print(f"{C.DIM}[n] Next page  [p] Previous page  [q] Back{C.RESET}")
                    nav = get_input("", "q")
                    if nav == 'n' and page < total_pages - 1:
                        page += 1
                    elif nav == 'p' and page > 0:
                        page -= 1
                    elif nav == 'q' or nav is None:
                        break
                else:
                    get_input("Press Enter to go back...")
                    break

        elif choice == "2":
            # Add more keywords
            clear_screen()
            print_banner()
            print_section("Add More Keywords", C.BRIGHT_CYAN)

            print(f"""
{C.WHITE}Current domains:{C.RESET} {len(domains)}
{C.DIM}New domains will be added to your existing set.{C.RESET}

{C.WHITE}Enter additional keywords:{C.RESET}
{C.DIM}Separate multiple keywords with commas.{C.RESET}
""")
            new_keywords_input = get_input("Keywords")
            if new_keywords_input and new_keywords_input.strip():
                new_keywords = [k.strip() for k in new_keywords_input.split(',') if k.strip()]
                if new_keywords:
                    print(f"\n{C.GREEN}✓{C.RESET} {len(new_keywords)} new keyword(s)\n")
                    new_domains = run_domain_scrape(
                        new_keywords, use_google, use_duckduckgo, max_results,
                        existing_domains=domains
                    )
                    added = len(new_domains) - len(domains)
                    domains = new_domains
                    keywords = keywords + new_keywords
                    print(f"\n{C.GREEN}✓{C.RESET} Added {added} new unique domains")
                    print(f"  Total domains: {len(domains)}")
                    get_input("\nPress Enter to continue...")

        elif choice == "3":
            # Re-run with same keywords
            print(f"\n{C.CYAN}Re-running with {len(keywords)} keywords...{C.RESET}\n")
            domains = run_domain_scrape(
                keywords, use_google, use_duckduckgo, max_results
            )
            print(f"\n{C.GREEN}✓{C.RESET} Found {len(domains)} unique domains")
            get_input("\nPress Enter to continue...")

        elif choice == "4":
            # Start fresh
            if confirm("Clear current domains and start with new keywords?"):
                return None  # Signal to restart the whole flow

        elif choice.lower() == "a":
            # Manually add domains
            clear_screen()
            print_banner()
            print_section("Manually Add Domains", C.BRIGHT_GREEN)

            print(f"""
{C.WHITE}Enter domains to add to your list.{C.RESET}
{C.DIM}Single domain or comma-separated. URLs auto-cleaned (http:// stripped).{C.RESET}

{C.DIM}Examples:{C.RESET}
  example.com
  example.com, another.com, third.com
  https://example.com/page  {C.DIM}→ becomes: example.com{C.RESET}
""")
            domain_input = get_input("Domains")
            if domain_input and domain_input.strip():
                # Parse comma-separated domains
                new_domains = []
                for d in domain_input.split(','):
                    d = d.strip().lower()
                    # Basic cleanup - remove protocols
                    if d.startswith('http://'):
                        d = d[7:]
                    elif d.startswith('https://'):
                        d = d[8:]
                    d = d.split('/')[0].strip()
                    if d and '.' in d:
                        new_domains.append(d)

                if new_domains:
                    before_count = len(domains)
                    domains = domains | set(new_domains)
                    added = len(domains) - before_count
                    print(f"\n{C.GREEN}✓{C.RESET} Added {added} new domain(s)")
                    print(f"  Total domains: {len(domains)}")
                else:
                    print_warning("No valid domains entered")
            get_input("\nPress Enter to continue...")

        elif choice == "5":
            # Save to file - with domain_lists directory
            from discovery.scraper import DomainScraper
            scraper = DomainScraper()

            # Determine domain_lists directory (relative to puppetmaster)
            puppetmaster_dir = Path(__file__).parent
            domain_lists_dir = puppetmaster_dir / "domain_lists"

            print(f"""
{C.WHITE}Save Domain List{C.RESET}
{C.DIM}Lists are saved to: {domain_lists_dir}{C.RESET}

  {C.BRIGHT_YELLOW}[1]{C.RESET} Auto-name with timestamp
  {C.BRIGHT_YELLOW}[2]{C.RESET} Enter custom name
  {C.BRIGHT_YELLOW}[3]{C.RESET} Save to custom path
""")
            save_choice = get_input("Choice", "1")

            if save_choice == "1":
                # Auto timestamp name
                filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                save_path = domain_lists_dir / filename
            elif save_choice == "2":
                # Custom name
                custom_name = get_input("Enter list name (without .txt)")
                if custom_name and custom_name.strip():
                    # Sanitize filename
                    safe_name = "".join(c for c in custom_name.strip() if c.isalnum() or c in '-_').strip()
                    if safe_name:
                        save_path = domain_lists_dir / f"{safe_name}.txt"
                    else:
                        print_warning("Invalid name, using timestamp")
                        filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        save_path = domain_lists_dir / filename
                else:
                    filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    save_path = domain_lists_dir / filename
            elif save_choice == "3":
                # Custom path
                default_filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                user_path = get_input("File path", default_filename)
                if user_path:
                    save_path = Path(os.path.expanduser(user_path))
                else:
                    save_path = domain_lists_dir / default_filename
            else:
                filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                save_path = domain_lists_dir / filename

            # Ensure directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)

            if scraper.save_to_file(str(save_path), domains):
                print_success(f"Saved {len(domains)} domains to: {save_path}")
            else:
                print_error("Failed to save file.")
            get_input("\nPress Enter to continue...")

        elif choice == "6":
            # Load into SpiderFoot queue
            config = load_config()
            existing_pending = set(config.get('pending_domains', []))
            combined = existing_pending | domains
            config['pending_domains'] = list(combined)
            config['last_scrape_keywords'] = keywords
            config['domains_ready_for_scan'] = True  # Flag to show notification
            config['domains_ready_count'] = len(combined)
            save_config(config)

            added = len(combined) - len(existing_pending)
            print_success(f"Added {added} new domains to scan queue.")
            print_info(f"Total in queue: {len(combined)}")
            print()
            print(f"{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
            print(f"{C.BRIGHT_GREEN}  Returning to main menu. Select option [3] to start scanning!{C.RESET}")
            print(f"{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
            time.sleep(1.5)
            break  # Return to main menu

        elif choice.lower() == "r":
            # Review & remove domains interactively
            domains = interactive_domain_removal(domains)

        elif choice.lower() == "k":
            # Expand with Kali tools
            if KALI_MODULE_AVAILABLE and is_enhanced_mode():
                domains = kali_expand_domains(domains, print_func=print, get_input_func=get_input)
                get_input("\nPress Enter to continue...")
            else:
                print_warning("Kali enhanced mode not available")
                get_input("\nPress Enter to continue...")

        elif choice == "7":
            # Save state before exiting
            config = load_config()
            config['last_scrape_domains'] = list(domains)
            config['last_scrape_keywords'] = keywords
            save_config(config)
            break

    return domains


def scrape_domains_menu():
    """Menu for scraping domains via keywords"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        cyber_banner_discovery()
    else:
        print_banner()
        print_section("Scrape Domains via Keywords", C.BRIGHT_CYAN)

    # Check dependencies
    try:
        from discovery.scraper import DomainScraper
    except ImportError as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Discovery module not available: {e}")
            cyber_info("Make sure you're running from the correct directory.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error(f"Discovery module not available: {e}")
            print_info("Make sure you're running from the correct directory.")
            get_input("\nPress Enter to return to main menu...")
        return

    # Check if search libraries are available
    deps = DomainScraper.check_dependencies()
    if not deps['google'] and not deps['duckduckgo']:
        if CYBER_UI_AVAILABLE:
            cyber_error("No search libraries available!")
            cyber_info("Install with: pip install googlesearch-python duckduckgo_search")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error("No search libraries available!")
            print_info("Install with: pip install googlesearch-python duckduckgo_search")
            get_input("\nPress Enter to return to main menu...")
        return

    # Check for previous session
    config = load_config()
    last_domains = config.get('last_scrape_domains', [])
    last_keywords = config.get('last_scrape_keywords', [])

    if last_domains:
        if CYBER_UI_AVAILABLE:
            console = get_console()
            console.print(f"\n[bright_yellow]Previous session found:[/]")
            console.print(f"  [dim]Domains:[/] [bright_green]{len(last_domains)}[/]")
            console.print(f"  [dim]Keywords:[/] [bright_cyan]{', '.join(last_keywords[:3])}{'...' if len(last_keywords) > 3 else ''}[/]\n")
            console.print("  [bright_yellow][1][/] Continue with previous results")
            console.print("  [bright_yellow][2][/] Add new keywords (merge with existing)")
            console.print("  [bright_red][3][/] Clear all & start fresh\n")
            resume_choice = cyber_prompt("Choice", "1")
        else:
            print(f"""
{C.BRIGHT_YELLOW}Previous session found:{C.RESET}
  Domains: {len(last_domains)}
  Keywords: {', '.join(last_keywords[:3])}{'...' if len(last_keywords) > 3 else ''}
""")
            print_menu_item("1", "Continue with previous results", "▶️")
            print_menu_item("2", "Add new keywords (merge with existing)", "➕")
            print_menu_item("3", "Clear all & start fresh", "🆕")
            print()
            resume_choice = get_input("Choice", "1")

        if resume_choice == "1":
            # Resume previous session
            use_google = deps['google']
            use_duckduckgo = deps['duckduckgo']
            max_results = 50

            result = show_scrape_results_menu(
                set(last_domains), last_keywords,
                use_google, use_duckduckgo, max_results
            )
            if result is None:
                pass
            else:
                return

        elif resume_choice == "2":
            # Add new keywords but merge with existing domains
            use_google = deps['google']
            use_duckduckgo = deps['duckduckgo']
            max_results = 50
            existing_domains = set(last_domains)

            clear_screen()
            if CYBER_UI_AVAILABLE:
                cyber_banner_discovery()
                console = get_console()
                console.print(f"\n[bright_green]Keeping {len(existing_domains)} existing domains[/]")
                console.print("[white]Enter additional keywords to search for more domains.[/]")
                console.print("[dim]Separate multiple keywords with commas.[/]\n")
            else:
                print_banner()
                print_section("Add More Keywords", C.BRIGHT_CYAN)
                print(f"\n{C.GREEN}Keeping {len(existing_domains)} existing domains{C.RESET}")
                print(f"\n{C.WHITE}Enter additional keywords to search for more domains.{C.RESET}")
                print(f"{C.DIM}Separate multiple keywords with commas.{C.RESET}\n")

            if CYBER_UI_AVAILABLE:
                keywords_input = cyber_prompt("Keywords")
            else:
                keywords_input = get_input("Keywords")

            if keywords_input and keywords_input.strip():
                new_keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
                if new_keywords:
                    new_domains = run_domain_scrape(
                        new_keywords, use_google, use_duckduckgo, max_results,
                        existing_domains=existing_domains
                    )
                    # Merge keywords
                    all_keywords = last_keywords + [k for k in new_keywords if k not in last_keywords]
                    added = len(new_domains) - len(existing_domains)
                    print(f"\n{C.GREEN}✓{C.RESET} Added {added} new unique domains")
                    print(f"  Total domains: {len(new_domains)}")
                    get_input("\nPress Enter to continue...")

                    # Go to results menu with merged data
                    result = show_scrape_results_menu(
                        new_domains, all_keywords,
                        use_google, use_duckduckgo, max_results
                    )
                    if result is not None:
                        return
            return

        # resume_choice == "3" or anything else: clear and start fresh
        clear_screen()
        if CYBER_UI_AVAILABLE:
            cyber_banner_discovery()
        else:
            print_banner()
            print_section("Scrape Domains via Keywords", C.BRIGHT_CYAN)

    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print("\n[white]Enter keywords to search for domains.[/]")
        console.print("[dim]Separate multiple keywords with commas.[/]\n")
        console.print("[dim]Examples:[/]")
        console.print("  [bright_cyan]•[/] electrical contractors NYC, electrical services New York")
        console.print("  [bright_cyan]•[/] plastic surgery clinic, cosmetic surgeon")
        console.print("  [bright_cyan]•[/] online tutoring, math help\n")
    else:
        print(f"""
{C.WHITE}Enter keywords to search for domains.{C.RESET}
{C.DIM}Separate multiple keywords with commas.{C.RESET}

{C.DIM}Examples:{C.RESET}
  • electrical contractors NYC, electrical services New York
  • plastic surgery clinic, cosmetic surgeon
  • online tutoring, math help
""")

    # Get keywords
    if CYBER_UI_AVAILABLE:
        keywords_input = cyber_prompt("Keywords")
    else:
        keywords_input = get_input("Keywords")
    if keywords_input is None or not keywords_input.strip():
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
        return

    keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
    if not keywords:
        if CYBER_UI_AVAILABLE:
            cyber_error("No valid keywords provided.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error("No valid keywords provided.")
            get_input("\nPress Enter to return to main menu...")
        return

    if CYBER_UI_AVAILABLE:
        cyber_success(f"{len(keywords)} keyword(s) entered")
        console = get_console()
        console.print("\n[white]Search engine:[/]")
        if deps['google']:
            console.print("  [bright_yellow][1][/] Google [dim](no API key, uses delays)[/]")
        else:
            console.print("  [dim][1] Google (not available)[/]")
        if deps['duckduckgo']:
            console.print("  [bright_yellow][2][/] DuckDuckGo [dim](no API key, reliable)[/]")
        else:
            console.print("  [dim][2] DuckDuckGo (not available)[/]")
        if deps['google'] and deps['duckduckgo']:
            console.print("  [bright_yellow][3][/] Both [dim](recommended)[/]")
        console.print()
    else:
        print(f"\n{C.GREEN}✓{C.RESET} {len(keywords)} keyword(s) entered\n")
        print(f"{C.WHITE}Search engine:{C.RESET}")
        if deps['google']:
            print_menu_item("1", "Google (no API key, uses delays to avoid blocking)", "")
        else:
            print(f"  {C.DIM}[1] Google (not available - install googlesearch-python){C.RESET}")
        if deps['duckduckgo']:
            print_menu_item("2", "DuckDuckGo (no API key, more reliable)", "")
        else:
            print(f"  {C.DIM}[2] DuckDuckGo (not available - install duckduckgo_search){C.RESET}")
        if deps['google'] and deps['duckduckgo']:
            print_menu_item("3", "Both (searches both, combines results)", "")
        print()

    # Default to what's available
    default_engine = "3" if (deps['google'] and deps['duckduckgo']) else ("1" if deps['google'] else "2")
    if CYBER_UI_AVAILABLE:
        engine_choice = cyber_prompt("Choice", default_engine)
    else:
        engine_choice = get_input(f"Choice", default_engine)
    if engine_choice is None:
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
        return

    use_google = engine_choice in ('1', '3') and deps['google']
    use_duckduckgo = engine_choice in ('2', '3') and deps['duckduckgo']

    if not use_google and not use_duckduckgo:
        if CYBER_UI_AVAILABLE:
            cyber_error("No search engine selected.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error("No search engine selected.")
            get_input("\nPress Enter to return to main menu...")
        return

    # Max results per keyword
    if CYBER_UI_AVAILABLE:
        max_results = cyber_prompt("Max results per keyword", "50")
    else:
        max_results = get_input("Max results per keyword", "50")
    if max_results is None:
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
        return
    try:
        max_results = int(max_results)
    except ValueError:
        max_results = 50

    # Run the scraper
    domains = run_domain_scrape(keywords, use_google, use_duckduckgo, max_results)

    # Show results summary
    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print("\n[bright_green]" + "━" * 60 + "[/]")
        cyber_success("Scraping complete!")
        console.print(f"  [dim]Keywords searched:[/]    [bright_cyan]{len(keywords)}[/]")
        console.print(f"  [dim]Unique domains found:[/] [bright_green]{len(domains)}[/]")
        console.print("[bright_green]" + "━" * 60 + "[/]\n")
    else:
        print(f"""
{C.BRIGHT_GREEN}{'━' * 60}{C.RESET}
{C.GREEN}✓{C.RESET} Scraping complete!

  Keywords searched:     {len(keywords)}
  Unique domains found:  {len(domains)}
{C.BRIGHT_GREEN}{'━' * 60}{C.RESET}
""")

    if not domains:
        if CYBER_UI_AVAILABLE:
            cyber_warning("No domains found. Try different keywords.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_warning("No domains found. Try different keywords.")
            get_input("\nPress Enter to return to main menu...")
        return

    # BLACKLIST FILTER: Remove known platform domains
    try:
        from core.blacklist import filter_domains, get_blacklist_stats

        original_count = len(domains)
        clean_domains, blocked_domains = filter_domains(domains)

        if blocked_domains:
            stats = get_blacklist_stats()
            if CYBER_UI_AVAILABLE:
                console = get_console()
                console.print("\n[bright_yellow]" + "━" * 60 + "[/]")
                console.print("[bright_yellow]BLACKLIST FILTER[/]\n")
                console.print(f"  [bright_red]Filtered out:[/] {len(blocked_domains)} platform domains")
                console.print(f"  [bright_green]Remaining:[/]    {len(clean_domains)} target domains\n")
                console.print(f"  [dim]Blacklisted: {', '.join(sorted(blocked_domains)[:5])}{'...' if len(blocked_domains) > 5 else ''}[/]")
                console.print("[bright_yellow]" + "━" * 60 + "[/]\n")
                console.print(f"  [bright_yellow][1][/] Use filtered list ({len(clean_domains)} domains) [dim]- recommended[/]")
                console.print(f"  [bright_yellow][2][/] Keep all domains ({original_count} domains)")
                console.print(f"  [bright_yellow][3][/] View all filtered domains\n")
                filter_choice = cyber_prompt("Choice", "1") or "1"
            else:
                print(f"""
{C.BRIGHT_YELLOW}{'━' * 60}{C.RESET}
{C.YELLOW}BLACKLIST FILTER{C.RESET}

  {C.RED}Filtered out:{C.RESET} {len(blocked_domains)} platform domains
  {C.GREEN}Remaining:{C.RESET}    {len(clean_domains)} target domains

  {C.DIM}Blacklisted: {', '.join(sorted(blocked_domains)[:5])}{'...' if len(blocked_domains) > 5 else ''}{C.RESET}
{C.BRIGHT_YELLOW}{'━' * 60}{C.RESET}
""")
                print(f"  [1] Use filtered list ({len(clean_domains)} domains) - recommended")
                print(f"  [2] Keep all domains ({original_count} domains)")
                print(f"  [3] View all filtered domains")
                print()
                filter_choice = get_input("Choice [1]: ") or "1"

            if filter_choice == "3":
                if CYBER_UI_AVAILABLE:
                    console.print("\n  [dim]Filtered domains:[/]")
                    for d in sorted(blocked_domains):
                        console.print(f"    [bright_red]✗[/] {d}")
                    console.print()
                    filter_choice = cyber_prompt("Use filtered list? [Y/n]") or "y"
                else:
                    print(f"\n  {C.DIM}Filtered domains:{C.RESET}")
                    for d in sorted(blocked_domains):
                        print(f"    {C.RED}✗{C.RESET} {d}")
                    print()
                    filter_choice = get_input("Use filtered list? [Y/n]: ") or "y"
                if filter_choice.lower() != 'n':
                    domains = clean_domains
            elif filter_choice == "2":
                if CYBER_UI_AVAILABLE:
                    cyber_info("Keeping all domains (including platforms)")
                else:
                    print_info("Keeping all domains (including platforms)")
            else:
                domains = clean_domains
                if CYBER_UI_AVAILABLE:
                    cyber_success(f"Using {len(domains)} filtered domains")
                else:
                    print_success(f"Using {len(domains)} filtered domains")

    except ImportError:
        pass  # Blacklist module not available, skip filtering

    # Note: Interactive domain review and Kali expansion are now in the Results Menu
    if CYBER_UI_AVAILABLE:
        cyber_prompt("Press Enter to continue to results menu")
    else:
        get_input("Press Enter to continue to results menu...")

    # Show results menu
    while True:
        result = show_scrape_results_menu(
            domains, keywords, use_google, use_duckduckgo, max_results
        )
        if result is None:
            scrape_domains_menu()
            return
        else:
            break


def load_domains_menu():
    """Menu for loading domains from a file"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        cyber_banner_import()
    else:
        print_banner()
        print_section("Load Domains from File", C.BRIGHT_CYAN)

    try:
        from discovery.scraper import DomainScraper
    except ImportError as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Discovery module not available: {e}")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error(f"Discovery module not available: {e}")
            get_input("\nPress Enter to return to main menu...")
        return

    # Check for saved lists in domain_lists directory
    puppetmaster_dir = Path(__file__).parent
    domain_lists_dir = puppetmaster_dir / "domain_lists"
    available_lists = []

    if domain_lists_dir.exists():
        for txt_file in sorted(domain_lists_dir.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                # Count domains and get file info
                with open(txt_file, 'r') as f:
                    domain_count = sum(1 for line in f if line.strip() and not line.strip().startswith('#'))
                mod_time = datetime.fromtimestamp(txt_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                available_lists.append({
                    'path': txt_file,
                    'name': txt_file.name,
                    'domains': domain_count,
                    'modified': mod_time
                })
            except Exception:
                pass

    # Show available lists if any exist
    if available_lists:
        if CYBER_UI_AVAILABLE:
            console = get_console()
            console.print("\n[bold white]Available Domain Lists:[/]")
            console.print(f"[dim]Saved in: {domain_lists_dir}[/]\n")
            for i, lst in enumerate(available_lists[:10], 1):
                console.print(f"  [bold yellow]\\[{i}][/] {lst['name']}")
                console.print(f"      [dim]{lst['domains']} domains • {lst['modified']}[/]")
            if len(available_lists) > 10:
                console.print(f"  [dim]... and {len(available_lists) - 10} more files[/]")
            console.print(f"\n  [bold cyan]\\[C][/] Enter custom file path")
            console.print()
            list_choice = cyber_prompt("Select list", "1")
        else:
            print(f"\n{C.WHITE}Available Domain Lists:{C.RESET}")
            print(f"{C.DIM}Saved in: {domain_lists_dir}{C.RESET}\n")
            for i, lst in enumerate(available_lists[:10], 1):
                print(f"  {C.BRIGHT_YELLOW}[{i}]{C.RESET} {lst['name']}")
                print(f"      {C.DIM}{lst['domains']} domains • {lst['modified']}{C.RESET}")
            if len(available_lists) > 10:
                print(f"  {C.DIM}... and {len(available_lists) - 10} more files{C.RESET}")
            print(f"\n  {C.BRIGHT_CYAN}[C]{C.RESET} Enter custom file path")
            print()
            list_choice = get_input("Select list", "1")

        # Handle selection
        file_path = None
        if list_choice and list_choice.lower() == 'c':
            # Custom path input
            if CYBER_UI_AVAILABLE:
                console = get_console()
                console.print("\n[white]Enter path to domain file:[/]")
                file_path = cyber_prompt("File path")
            else:
                print(f"\n{C.WHITE}Enter path to domain file:{C.RESET}")
                file_path = get_input("File path")
        elif list_choice and list_choice.isdigit():
            idx = int(list_choice) - 1
            if 0 <= idx < len(available_lists):
                file_path = str(available_lists[idx]['path'])
            else:
                print_warning("Invalid selection")
                get_input("\nPress Enter to return to main menu...")
                return
        else:
            # Default to first list if nothing entered
            if available_lists:
                file_path = str(available_lists[0]['path'])
            else:
                return
    else:
        # No saved lists, show traditional input
        if CYBER_UI_AVAILABLE:
            console = get_console()
            console.print("\n[white]Load a list of domains from a text file.[/]")
            console.print("[dim]File should contain one domain per line.[/]\n")
            console.print("[dim]Example file format:[/]")
            console.print("  [bright_green]example1.com[/]")
            console.print("  [bright_green]example2.com[/]")
            console.print("  [bright_green]www.example3.com[/]")
            console.print("  [bright_cyan]https://example4.com/page[/]  [dim](URLs will be parsed)[/]\n")
            console.print(f"[dim]Tip: Save lists from option [1] to {domain_lists_dir}[/]\n")
            file_path = cyber_prompt("Enter path to file")
        else:
            print(f"""
{C.WHITE}Load a list of domains from a text file.{C.RESET}
{C.DIM}File should contain one domain per line.{C.RESET}

{C.DIM}Example file format:{C.RESET}
  example1.com
  example2.com
  www.example3.com
  https://example4.com/page  {C.DIM}(URLs will be parsed){C.RESET}

{C.DIM}Tip: Save lists from option [1] to {domain_lists_dir}{C.RESET}
""")
            file_path = get_input("Enter path to file")
    if file_path is None or not file_path.strip():
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
        return

    file_path = os.path.expanduser(file_path.strip())

    # Check file exists
    if not os.path.exists(file_path):
        if CYBER_UI_AVAILABLE:
            cyber_error(f"File not found: {file_path}")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error(f"File not found: {file_path}")
            get_input("\nPress Enter to return to main menu...")
        return

    if not os.path.isfile(file_path):
        if CYBER_UI_AVAILABLE:
            cyber_error("That's not a file.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error("That's not a file.")
            get_input("\nPress Enter to return to main menu...")
        return

    # Load and validate
    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print("\n[bright_magenta]" + "━" * 50 + "[/]")
        console.print("[bright_magenta]VALIDATING FILE[/]")
        console.print("[bright_magenta]" + "━" * 50 + "[/]\n")
    else:
        print_section("Validating File", C.BRIGHT_MAGENTA)

    scraper = DomainScraper()
    valid_domains, invalid_lines = scraper.load_from_file(file_path)

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_success(f"File found: {os.path.basename(file_path)}")
        console.print("\n[dim]Parsing domains...[/]")
        console.print(f"  [bright_cyan]•[/] Valid domains:     [bright_green]{len(valid_domains)}[/]")
        console.print(f"  [bright_cyan]•[/] Invalid/skipped:   [bright_yellow]{len(invalid_lines)}[/]\n")
    else:
        print(f"""
{C.GREEN}✓{C.RESET} File found: {os.path.basename(file_path)}

Parsing domains...
  • Valid domains:     {C.GREEN}{len(valid_domains)}{C.RESET}
  • Invalid/skipped:   {C.YELLOW}{len(invalid_lines)}{C.RESET}
""")

    # Show invalid lines (up to 5)
    if invalid_lines:
        if CYBER_UI_AVAILABLE:
            console.print("[dim]Invalid lines:[/]")
            for line_num, line, reason in invalid_lines[:5]:
                console.print(f"  [dim]Line {line_num}: \"{line[:30]}...\" ({reason})[/]")
            if len(invalid_lines) > 5:
                console.print(f"  [dim]... and {len(invalid_lines) - 5} more[/]")
            console.print()
        else:
            print(f"{C.DIM}Invalid lines:{C.RESET}")
            for line_num, line, reason in invalid_lines[:5]:
                print(f"  {C.DIM}Line {line_num}: \"{line[:30]}...\" ({reason}){C.RESET}")
            if len(invalid_lines) > 5:
                print(f"  {C.DIM}... and {len(invalid_lines) - 5} more{C.RESET}")
            print()

    if not valid_domains:
        if CYBER_UI_AVAILABLE:
            cyber_error("No valid domains found in file.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error("No valid domains found in file.")
            get_input("\nPress Enter to return to main menu...")
        return

    if CYBER_UI_AVAILABLE:
        cyber_success(f"Loaded {len(valid_domains)} domains")
    else:
        print_success(f"Loaded {len(valid_domains)} domains")

    # Offer to proceed to SpiderFoot scanning
    if CYBER_UI_AVAILABLE:
        proceed = cyber_confirm("\nAdd to SpiderFoot scan queue?")
    else:
        proceed = confirm("\nAdd to SpiderFoot scan queue?")

    if proceed:
        config = load_config()
        # MERGE with existing queue (don't replace!)
        existing_pending = set(config.get('pending_domains', []))
        combined = existing_pending | valid_domains
        config['pending_domains'] = list(combined)
        save_config(config)

        added = len(combined) - len(existing_pending)
        if CYBER_UI_AVAILABLE:
            if existing_pending:
                cyber_success(f"Added {added} new domains to scan queue.")
                cyber_info(f"Total in queue: {len(combined)}")
            else:
                cyber_success(f"Loaded {len(valid_domains)} domains into scan queue.")
            cyber_info("Use option [3] Run SpiderFoot scans to start scanning.")
        else:
            if existing_pending:
                print_success(f"Added {added} new domains to scan queue.")
                print_info(f"Total in queue: {len(combined)}")
            else:
                print_success(f"Loaded {len(valid_domains)} domains into scan queue.")
            print_info("Use option [3] Run SpiderFoot scans to start scanning.")

    if CYBER_UI_AVAILABLE:
        cyber_prompt("Press Enter to return to main menu")
    else:
        get_input("\nPress Enter to return to main menu...")


# =============================================================================
# SPIDERFOOT CONTROL CENTER (UNIFIED)
# =============================================================================

def spiderfoot_control_center_menu():
    """
    Unified SpiderFoot Control Center menu.

    Consolidates:
    - CLI batch scanning
    - Web GUI
    - Database management
    - Intensity presets
    - ETA tracking
    - Stuck scan detection
    """
    while True:  # Loop to allow returning to submenu
        clear_screen()

        # Use cyberpunk UI if available
        if CYBER_UI_AVAILABLE:
            console = get_console()
            cyber_banner_spider()
            cyber_header("SPIDERFOOT CONTROL CENTER")
        else:
            print_banner()
            print_section("SpiderFoot Control Center", C.BRIGHT_CYAN)

        # Import the control center module
        try:
            from discovery.spiderfoot_control import (
                SpiderFootControlCenter, INTENSITY_PRESETS,
                find_spiderfoot_db, get_db_size, count_db_scans,
                reset_spiderfoot_db, kill_spiderfoot_processes,
                is_in_tmux, estimate_total_time, should_warn_tmux
            )
            from discovery.jobs import JobTracker
        except ImportError as e:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Failed to import control center: {e}")
            else:
                print_error(f"Failed to import control center: {e}")
            get_input("\nPress Enter to return to main menu...")
            return

        # Load configuration
        config = load_config()
        sf_path = config.get('spiderfoot_path')
        sf_python = config.get('spiderfoot_python')
        sf_output = config.get('spiderfoot_output_dir', './spiderfoot_exports')

        # Auto-detect SpiderFoot if not configured
        if not sf_path or not os.path.exists(sf_path):
            script_dir = Path(__file__).parent
            project_sf_path = script_dir / "spiderfoot" / "sf.py"
            project_sf_python = script_dir / "spiderfoot" / "venv" / "bin" / "python3"

            if project_sf_path.exists() and project_sf_python.exists():
                sf_path = str(project_sf_path)
                sf_python = str(project_sf_python)
                config['spiderfoot_path'] = sf_path
                config['spiderfoot_python'] = sf_python
                save_config(config)

        # Get status information
        sf_installed = sf_path and os.path.exists(sf_path)
        db_path = find_spiderfoot_db(sf_path) if sf_installed else None
        db_size = get_db_size(db_path) if db_path else "N/A"
        db_scans = count_db_scans(db_path) if db_path else {}

        # Get queue status
        tracker = JobTracker()
        queue_stats = tracker.get_stats()
        pending_domains = config.get('pending_domains', [])

        # Check if background scan is running
        bg_running = is_background_scan_running()
        bg_stats = get_background_scan_stats() if bg_running else None

        # Display status panel
        if CYBER_UI_AVAILABLE:
            from rich.panel import Panel
            from rich.table import Table
            from rich.text import Text

            # Status table
            status_table = Table(show_header=False, box=None, padding=(0, 2))
            status_table.add_column("Label", style="dim white", width=25)
            status_table.add_column("Value")

            # SpiderFoot status
            if sf_installed:
                status_table.add_row("◈ SpiderFoot", "[green]INSTALLED[/]")
            else:
                status_table.add_row("◈ SpiderFoot", "[red]NOT INSTALLED[/]")

            # Database status
            if db_path:
                status_table.add_row("◈ Database", f"[cyan]{db_size}[/]")
                status_table.add_row("  └─ Scans", f"[white]{db_scans.get('total', 0)} total[/] | "
                                    f"[yellow]{db_scans.get('running', 0)} running[/] | "
                                    f"[green]{db_scans.get('finished', 0)} finished[/]")
            else:
                status_table.add_row("◈ Database", "[dim]Not found[/]")

            # Queue status
            status_table.add_row("◈ Scan Queue",
                f"[white]{queue_stats['total']} total[/] | "
                f"[cyan]{queue_stats['pending']} pending[/] | "
                f"[green]{queue_stats['completed']} done[/]")

            # Pending domains (not yet in queue)
            if pending_domains:
                status_table.add_row("◈ Domains Loaded", f"[yellow]{len(pending_domains)} ready to add[/]")

            # Background scan status
            if bg_running:
                progress = bg_stats['completed'] + bg_stats['failed']
                status_table.add_row("◈ Active Scan", f"[bold yellow]RUNNING[/] - {progress}/{bg_stats['total']}")

            # tmux status
            status_table.add_row("◈ tmux", "[green]Active[/]" if is_in_tmux() else "[dim]Not in tmux[/]")

            console.print(Panel(
                status_table,
                title="[bold magenta]⟨ SYSTEM STATUS ⟩[/]",
                border_style="magenta",
                padding=(1, 2)
            ))
            console.print()

            # Menu options
            menu_text = Text()

            # Show install option prominently if not installed
            if not sf_installed:
                menu_text.append("SETUP REQUIRED\n", style="bold red underline")
                menu_text.append("  [I] ", style="bold yellow")
                menu_text.append("Install SpiderFoot      ", style="bold white")
                menu_text.append("Auto-install SpiderFoot OSINT tool\n\n", style="yellow")

            menu_text.append("SCAN OPERATIONS\n", style="bold white underline")
            menu_text.append("  [1] ", style="bold green")
            menu_text.append("Start Batch Scans       ", style="white")
            menu_text.append("CLI mode with intensity presets\n", style="dim")
            menu_text.append("  [2] ", style="bold cyan")
            menu_text.append("View Scan Status        ", style="white")
            menu_text.append("Progress, ETA, stuck detection\n", style="dim")
            menu_text.append("  [3] ", style="bold yellow")
            menu_text.append("Open Web GUI            ", style="white")
            menu_text.append("Interactive browser interface\n\n", style="dim")

            menu_text.append("DATABASE MANAGEMENT\n", style="bold white underline")
            menu_text.append("  [4] ", style="bold red")
            menu_text.append("Reset SpiderFoot DB     ", style="white")
            menu_text.append("Wipe all scan data (creates backup)\n", style="dim")
            menu_text.append("  [5] ", style="bold magenta")
            menu_text.append("Kill SpiderFoot         ", style="white")
            menu_text.append("Stop all running processes\n\n", style="dim")

            menu_text.append("  [Q] ", style="bold white")
            menu_text.append("Back to Main Menu\n", style="dim")

            console.print(Panel(menu_text, title="[bold cyan]⟨ CONTROL CENTER ⟩[/]", border_style="cyan"))
            console.print()
        else:
            # Classic terminal output
            install_section = ""
            if not sf_installed:
                install_section = f"""
{C.BRIGHT_RED}SETUP REQUIRED{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.BRIGHT_YELLOW}[I]{C.RESET} {C.WHITE}Install SpiderFoot{C.RESET}      Auto-install SpiderFoot OSINT tool
"""
            print(f"""
{C.WHITE}SYSTEM STATUS{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  SpiderFoot:     {C.GREEN + "[INSTALLED]" + C.RESET if sf_installed else C.RED + "[NOT INSTALLED]" + C.RESET}
  Database:       {db_size} ({db_scans.get('total', 0)} scans, {db_scans.get('running', 0)} running)
  Scan Queue:     {queue_stats['total']} total ({queue_stats['pending']} pending, {queue_stats['completed']} done)
  Domains Loaded: {len(pending_domains)}
  Background:     {"[RUNNING]" if bg_running else "[idle]"}
  tmux:           {"[Active]" if is_in_tmux() else "[Not in tmux]"}
{install_section}
{C.WHITE}SCAN OPERATIONS{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.GREEN}[1]{C.RESET} Start Batch Scans       CLI mode with intensity presets
  {C.CYAN}[2]{C.RESET} View Scan Status        Progress, ETA, stuck detection
  {C.YELLOW}[3]{C.RESET} Open Web GUI            Interactive browser interface

{C.WHITE}DATABASE MANAGEMENT{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.RED}[4]{C.RESET} Reset SpiderFoot DB     Wipe all scan data (creates backup)
  {C.BRIGHT_MAGENTA}[5]{C.RESET} Kill SpiderFoot         Stop all running processes

  {C.WHITE}[Q]{C.RESET} Back to Main Menu
""")

        choice = get_input("Select an option")
        if choice is None:
            choice = 'q'
        choice = choice.lower().strip()

        if choice == 'q':
            return

        elif choice == '1':
            # Start batch scans with intensity presets
            _spiderfoot_batch_scan_menu(config, sf_path, sf_python, sf_output)

        elif choice == '2':
            # View scan status
            check_scan_status_menu()

        elif choice == '3':
            # Open Web GUI
            launch_spiderfoot_gui()

        elif choice == '4':
            # Reset SpiderFoot database
            _reset_spiderfoot_menu(sf_path)

        elif choice == '5':
            # Kill SpiderFoot processes
            _kill_spiderfoot_menu()

        elif choice == 'i':
            # Install SpiderFoot
            result = install_spiderfoot_interactive()
            if result:
                sf_path, sf_python = result
                config['spiderfoot_path'] = sf_path
                config['spiderfoot_python'] = sf_python
                save_config(config)
                if CYBER_UI_AVAILABLE:
                    cyber_success("SpiderFoot installed successfully!")
                else:
                    print_success("SpiderFoot installed successfully!")
            get_input("\nPress Enter to continue...")


def _check_port_in_use(port: int) -> bool:
    """Check if a port is in use"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def _start_gui_server_background(sf_path: str, sf_python: str, port: int = 5001) -> bool:
    """
    Start SpiderFoot GUI server in background.

    Returns:
        True if server started or already running, False on failure
    """
    # Check if already running on this port
    if _check_port_in_use(port):
        return True  # Already running, that's fine

    # Get SpiderFoot directory
    sf_dir = Path(sf_path).parent

    # Build command
    python_exe = sf_python if sf_python and os.path.exists(sf_python) else "python3"

    # Check if we're in tmux - if so, create a new window
    if os.environ.get('TMUX'):
        # Already in tmux, create a new window for the GUI
        import shlex
        sf_cmd = f"cd {shlex.quote(str(sf_dir))} && {shlex.quote(python_exe)} sf.py -l 127.0.0.1:{port}"
        try:
            subprocess.run([
                'tmux', 'new-window', '-d', '-n', 'spiderfoot-gui', sf_cmd
            ], check=True, capture_output=True)
            return True
        except Exception:
            pass  # Fall through to direct subprocess

    # Start as background subprocess
    try:
        subprocess.Popen(
            [python_exe, sf_path, "-l", f"127.0.0.1:{port}"],
            cwd=str(sf_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        # Give it a moment to start
        time.sleep(1)
        return True
    except Exception:
        return False


def _open_or_show_gui_url(port: int = 5001):
    """
    Open browser to GUI URL, or show SSH tunnel instructions if remote.
    """
    # Check if remote (SSH connection)
    ssh_connection = os.environ.get('SSH_CONNECTION', '')

    if ssh_connection:
        # Parse SSH_CONNECTION for IPs
        parts = ssh_connection.split()
        server_ip = parts[2] if len(parts) > 2 else 'THIS_SERVER'
        username = os.environ.get('USER', 'user')

        # Try to get EC2 public IP
        public_ip = None
        try:
            result = subprocess.run(
                ["curl", "-s", "--connect-timeout", "2",
                 "http://169.254.169.254/latest/meta-data/public-ipv4"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                public_ip = result.stdout.strip()
        except Exception:
            pass

        remote_ip = public_ip or server_ip

        if CYBER_UI_AVAILABLE:
            console = get_console()
            from rich.panel import Panel
            console.print(Panel(
                f"[bold]SSH Tunnel Required[/]\n\n"
                f"Run this in a [cyan]NEW[/] terminal on your local machine:\n\n"
                f"  [bold white]ssh -L {port}:localhost:{port} {username}@{remote_ip}[/]\n\n"
                f"Then open: [bold white]http://localhost:{port}[/]",
                title="[bold yellow]⟨ REMOTE ACCESS ⟩[/]",
                border_style="yellow"
            ))
        else:
            print(f"""
{C.BRIGHT_YELLOW}SSH Tunnel Required{C.RESET}

Run this in a {C.UNDERLINE}NEW{C.RESET} terminal on your local machine:

  {C.BRIGHT_WHITE}ssh -L {port}:localhost:{port} {username}@{remote_ip}{C.RESET}

Then open: {C.BRIGHT_WHITE}http://localhost:{port}{C.RESET}
""")
    else:
        # Local - try to open browser
        url = f"http://localhost:{port}"
        try:
            import webbrowser
            webbrowser.open(url)
            if CYBER_UI_AVAILABLE:
                cyber_success(f"Opened browser to {url}")
            else:
                print_success(f"Opened browser to {url}")
        except Exception:
            if CYBER_UI_AVAILABLE:
                cyber_info(f"Open in browser: {url}")
            else:
                print_info(f"Open in browser: {url}")


def _spiderfoot_batch_scan_menu(config, sf_path, sf_python, sf_output):
    """Sub-menu for starting batch scans with intensity presets"""
    clear_screen()

    try:
        from discovery.spiderfoot_control import (
            INTENSITY_PRESETS, estimate_total_time, should_warn_tmux, is_in_tmux
        )
        from discovery.jobs import JobTracker
    except ImportError as e:
        print_error(f"Import error: {e}")
        get_input("\nPress Enter to return...")
        return

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_header("BATCH SCAN CONFIGURATION")
    else:
        print_section("Batch Scan Configuration", C.BRIGHT_GREEN)

    # Check SpiderFoot installation
    if not sf_path or not os.path.exists(sf_path):
        if CYBER_UI_AVAILABLE:
            cyber_error("SpiderFoot not installed!")
            cyber_info("Use Help → Install SpiderFoot to set it up")
        else:
            print_error("SpiderFoot not installed!")
            print_info("Use Help → Install SpiderFoot to set it up")
        get_input("\nPress Enter to return...")
        return

    # Get queue info
    tracker = JobTracker()
    pending_domains = config.get('pending_domains', [])
    existing_pending = len(tracker.get_pending())

    total_domains = len(pending_domains) + existing_pending

    if total_domains == 0:
        if CYBER_UI_AVAILABLE:
            cyber_warning("No domains in queue!")
            cyber_info("Use [1] Scrape or [2] Load domains first")
        else:
            print_warning("No domains in queue!")
            print_info("Use [1] Scrape or [2] Load domains first")
        get_input("\nPress Enter to return...")
        return

    # Display intensity presets
    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        console.print(f"\n[bold white]Domains to scan:[/] [cyan]{total_domains}[/]\n")

        preset_table = Table(show_header=True, header_style="bold white", box=None)
        preset_table.add_column("Key", style="bold", width=5)
        preset_table.add_column("Preset", width=12)
        preset_table.add_column("Timeout", width=10)
        preset_table.add_column("Parallel", width=10)
        preset_table.add_column("Est. Time/Domain", width=15)
        preset_table.add_column("Description")

        for key, preset in INTENSITY_PRESETS.items():
            timeout_str = f"{preset.timeout_seconds // 60}m" if preset.timeout_seconds < 3600 else f"{preset.timeout_seconds // 3600}h"
            est_str = f"~{preset.estimated_time_per_domain // 60}m"
            color = preset.color
            preset_table.add_row(
                f"[{color}]{key[0].upper()}[/]",
                f"[{color}]{preset.name}[/]",
                timeout_str,
                str(preset.parallel_scans),
                est_str,
                preset.description[:40]
            )

        console.print(Panel(preset_table, title="[bold green]⟨ INTENSITY PRESETS ⟩[/]", border_style="green"))
        console.print()
    else:
        print(f"\n{C.WHITE}Domains to scan: {C.CYAN}{total_domains}{C.RESET}\n")
        print(f"{C.WHITE}INTENSITY PRESETS{C.RESET}")
        print(f"{C.DIM}{'━' * 70}{C.RESET}")
        for key, preset in INTENSITY_PRESETS.items():
            timeout_str = f"{preset.timeout_seconds // 60}m" if preset.timeout_seconds < 3600 else f"{preset.timeout_seconds // 3600}h"
            print(f"  [{key[0].upper()}] {preset.name:<12} | {timeout_str} timeout | {preset.parallel_scans} parallel | {preset.description[:35]}")
        print()

    # Select preset
    preset_choice = get_input("Select intensity preset [S/M/C/X for custom]", "M")
    if preset_choice is None:
        return

    preset_choice = preset_choice.lower().strip()
    preset_map = {'s': 'safe', 'm': 'moderate', 'c': 'committed', 'x': 'custom'}
    preset_key = preset_map.get(preset_choice, 'moderate')

    if preset_key == 'custom':
        # Custom configuration
        timeout_input = get_input("Timeout per scan (minutes)", "60")
        parallel_input = get_input("Parallel scans", "3")
        try:
            timeout_min = int(timeout_input) if timeout_input else 60
            parallel = int(parallel_input) if parallel_input else 3
            parallel = max(1, min(10, parallel))

            from discovery.spiderfoot_control import IntensityPreset
            preset = IntensityPreset(
                name='Custom',
                description=f'{timeout_min}m timeout, {parallel} parallel',
                timeout_seconds=timeout_min * 60,
                modules=None,
                parallel_scans=parallel,
                estimated_time_per_domain=timeout_min * 30,  # Rough estimate
                color='magenta'
            )
        except ValueError:
            print_warning("Invalid input, using Moderate preset")
            preset = INTENSITY_PRESETS['moderate']
    else:
        preset = INTENSITY_PRESETS[preset_key]

    # Calculate ETA
    total_time = estimate_total_time(total_domains, preset)
    hours = total_time.total_seconds() / 3600

    # tmux warning
    if should_warn_tmux(total_domains, preset):
        if CYBER_UI_AVAILABLE:
            from rich.panel import Panel
            console.print(Panel(
                f"[yellow]This scan batch is estimated to take {hours:.1f} hours.\n"
                f"Consider running in tmux to prevent interruption on disconnect.\n"
                f"Use option [9] from main menu to launch in tmux session.[/]",
                title="[bold yellow]⚠ LONG SCAN WARNING[/]",
                border_style="yellow"
            ))
        else:
            print(f"""
{C.YELLOW}{'━' * 60}
  WARNING: This scan batch is estimated to take {hours:.1f} hours.
  Consider running in tmux to prevent interruption on disconnect.
  Use option [9] from main menu to launch in tmux session.
{'━' * 60}{C.RESET}
""")

    # Confirmation
    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        console.print(Panel(
            f"[bold]Preset:[/] {preset.name}\n"
            f"[bold]Domains:[/] {total_domains}\n"
            f"[bold]Timeout:[/] {preset.timeout_seconds // 60} minutes per scan\n"
            f"[bold]Parallel:[/] {preset.parallel_scans} simultaneous scans\n"
            f"[bold]Est. Total:[/] ~{hours:.1f} hours",
            title="[bold green]⟨ SCAN SUMMARY ⟩[/]",
            border_style="green"
        ))
        console.print()
        do_scan = cyber_confirm("Start scanning?")
    else:
        print(f"""
{C.GREEN}{'━' * 50}{C.RESET}
  Preset:     {preset.name}
  Domains:    {total_domains}
  Timeout:    {preset.timeout_seconds // 60} minutes per scan
  Parallel:   {preset.parallel_scans} simultaneous scans
  Est. Total: ~{hours:.1f} hours
{C.GREEN}{'━' * 50}{C.RESET}
""")
        do_scan = confirm("Start scanning?")

    if not do_scan:
        print_info("Cancelled.")
        get_input("\nPress Enter to return...")
        return

    # Ask about GUI monitoring
    if CYBER_UI_AVAILABLE:
        open_gui = cyber_confirm("Monitor scans in browser?")
    else:
        open_gui = confirm("Monitor scans in browser?")

    if open_gui:
        # Start GUI server in background
        if _start_gui_server_background(sf_path, sf_python, port=5001):
            if CYBER_UI_AVAILABLE:
                cyber_success("SpiderFoot GUI started on port 5001")
            else:
                print_success("SpiderFoot GUI started on port 5001")
            # Open browser or show SSH tunnel instructions
            _open_or_show_gui_url(port=5001)
        else:
            if CYBER_UI_AVAILABLE:
                cyber_warning("Could not start GUI server")
            else:
                print_warning("Could not start GUI server")

    # Add pending domains to tracker
    if pending_domains:
        added = tracker.add_domains(pending_domains)
        config['pending_domains'] = []
        save_config(config)
        if CYBER_UI_AVAILABLE:
            cyber_success(f"Added {added} domains to scan queue")
        else:
            print_success(f"Added {added} domains to scan queue")

    # Create output directory
    if not os.path.exists(sf_output):
        os.makedirs(sf_output, exist_ok=True)

    # Import scanner
    from discovery.scanner import SpiderFootScanner

    scanner = SpiderFootScanner(
        spiderfoot_path=sf_path,
        output_dir=sf_output,
        max_parallel=preset.parallel_scans,
        job_tracker=tracker,
        spiderfoot_python=sf_python,
        timeout_seconds=preset.timeout_seconds,
        modules=preset.modules
    )

    # Ask for run mode
    if CYBER_UI_AVAILABLE:
        console.print("\n[bold white]Run Mode:[/]")
        console.print("  [1] Background (return to menu)")
        console.print("  [2] Foreground (watch progress)")
        console.print()
    else:
        print(f"""
{C.WHITE}Run Mode:{C.RESET}
  [1] Background (return to menu)
  [2] Foreground (watch progress)
""")

    run_mode = get_input("Select run mode", "1")
    if run_mode is None:
        return

    total_pending = len(tracker.get_pending())

    if run_mode == "1":
        # Run in background
        global _background_scan_thread
        _update_background_stats(
            running=True,
            completed=0,
            failed=0,
            total=total_pending,
            current_domain=None,
            start_time=datetime.now().isoformat()
        )

        _background_scan_thread = threading.Thread(
            target=_run_background_scans,
            args=(scanner, tracker),
            daemon=True
        )
        _background_scan_thread.start()

        if CYBER_UI_AVAILABLE:
            cyber_success("Scans started in background!")
            cyber_info("Use [2] View Scan Status to check progress")
        else:
            print_success("Scans started in background!")
            print_info("Use [2] View Scan Status to check progress")
        time.sleep(1.5)
        return
    else:
        # Run in foreground
        if CYBER_UI_AVAILABLE:
            cyber_header("RUNNING SCANS")
            console.print("[dim]Press Ctrl+C to pause. Progress auto-saves.[/]\n")

            def on_start(domain):
                console.print(f"  [cyan]▶[/] Starting: [bold]{domain}[/]")

            def on_complete(domain, csv_path):
                console.print(f"  [green]✓[/] Completed: [bold green]{domain}[/]")

            def on_failed(domain, error):
                console.print(f"  [red]✗[/] Failed: [bold]{domain}[/] - [dim]{error[:50]}[/]")

            def on_progress(completed, failed, total):
                console.print(f"\n  [bold cyan]Progress: {completed + failed}/{total}[/]\n")
        else:
            print_section("Running Scans", C.BRIGHT_MAGENTA)
            print(f"{C.DIM}Press Ctrl+C to pause. Progress auto-saves.{C.RESET}\n")

            def on_start(domain):
                print(f"  {C.CYAN}▶{C.RESET} Starting: {domain}")

            def on_complete(domain, csv_path):
                print(f"  {C.GREEN}✓{C.RESET} Completed: {domain}")

            def on_failed(domain, error):
                print(f"  {C.RED}✗{C.RESET} Failed: {domain} - {error[:50]}")

            def on_progress(completed, failed, total):
                print(f"\n  {C.CYAN}Progress: {completed + failed}/{total}{C.RESET}\n")

        scanner.on_scan_start = on_start
        scanner.on_scan_complete = on_complete
        scanner.on_scan_failed = on_failed
        scanner.on_progress = on_progress

        try:
            results = scanner.process_queue(progress_callback=on_progress)
            if CYBER_UI_AVAILABLE:
                cyber_success(f"Batch complete! {results['completed']} succeeded, {results['failed']} failed")
            else:
                print_success(f"Batch complete! {results['completed']} succeeded, {results['failed']} failed")
        except KeyboardInterrupt:
            scanner.stop()
            if CYBER_UI_AVAILABLE:
                cyber_warning("Scan paused. Progress saved.")
            else:
                print_warning("Scan paused. Progress saved.")
        except Exception as e:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Error: {e}")
            else:
                print_error(f"Error: {e}")

        get_input("\nPress Enter to return...")


def _reset_spiderfoot_menu(sf_path):
    """Sub-menu for resetting SpiderFoot database"""
    clear_screen()

    try:
        from discovery.spiderfoot_control import (
            find_spiderfoot_db, get_db_size, count_db_scans,
            reset_spiderfoot_db, kill_spiderfoot_processes
        )
    except ImportError as e:
        print_error(f"Import error: {e}")
        get_input("\nPress Enter to return...")
        return

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_header("RESET SPIDERFOOT DATABASE")
    else:
        print_section("Reset SpiderFoot Database", C.BRIGHT_RED)

    if not sf_path or not os.path.exists(sf_path):
        if CYBER_UI_AVAILABLE:
            cyber_error("SpiderFoot not found!")
        else:
            print_error("SpiderFoot not found!")
        get_input("\nPress Enter to return...")
        return

    # Find database
    db_path = find_spiderfoot_db(sf_path)
    if not db_path:
        if CYBER_UI_AVAILABLE:
            cyber_warning("SpiderFoot database not found. Nothing to reset.")
        else:
            print_warning("SpiderFoot database not found. Nothing to reset.")
        get_input("\nPress Enter to return...")
        return

    # Show current status
    db_size = get_db_size(db_path)
    db_scans = count_db_scans(db_path)

    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        console.print(Panel(
            f"[bold]Database:[/] {db_path}\n"
            f"[bold]Size:[/] {db_size}\n"
            f"[bold]Total Scans:[/] {db_scans.get('total', 0)}\n"
            f"  └─ Running: {db_scans.get('running', 0)}\n"
            f"  └─ Finished: {db_scans.get('finished', 0)}\n"
            f"  └─ Aborted: {db_scans.get('aborted', 0)}",
            title="[bold red]⟨ DATABASE STATUS ⟩[/]",
            border_style="red"
        ))
        console.print()
        console.print("[yellow]WARNING: This will delete ALL SpiderFoot scan data![/]")
        console.print("[dim]A backup will be created before deletion.[/]\n")
        do_reset = cyber_confirm("Reset SpiderFoot database?")
    else:
        print(f"""
{C.RED}{'━' * 50}{C.RESET}
  Database:     {db_path}
  Size:         {db_size}
  Total Scans:  {db_scans.get('total', 0)}
    └─ Running:   {db_scans.get('running', 0)}
    └─ Finished:  {db_scans.get('finished', 0)}
    └─ Aborted:   {db_scans.get('aborted', 0)}
{C.RED}{'━' * 50}{C.RESET}

{C.YELLOW}WARNING: This will delete ALL SpiderFoot scan data!{C.RESET}
{C.DIM}A backup will be created before deletion.{C.RESET}
""")
        do_reset = confirm("Reset SpiderFoot database?")

    if not do_reset:
        print_info("Cancelled.")
        get_input("\nPress Enter to return...")
        return

    # Kill any running processes first
    if CYBER_UI_AVAILABLE:
        cyber_info("Stopping SpiderFoot processes...")
    else:
        print_info("Stopping SpiderFoot processes...")

    killed = kill_spiderfoot_processes()
    if killed > 0:
        if CYBER_UI_AVAILABLE:
            cyber_success(f"Killed {killed} SpiderFoot process(es)")
        else:
            print_success(f"Killed {killed} SpiderFoot process(es)")
        time.sleep(1)

    # Reset database
    success, msg = reset_spiderfoot_db(sf_path, backup=True)

    if success:
        if CYBER_UI_AVAILABLE:
            cyber_success(msg)
        else:
            print_success(msg)
    else:
        if CYBER_UI_AVAILABLE:
            cyber_error(msg)
        else:
            print_error(msg)

    get_input("\nPress Enter to return...")


def _kill_spiderfoot_menu():
    """Sub-menu for killing SpiderFoot processes"""
    clear_screen()

    try:
        from discovery.spiderfoot_control import kill_spiderfoot_processes
    except ImportError as e:
        print_error(f"Import error: {e}")
        get_input("\nPress Enter to return...")
        return

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_header("KILL SPIDERFOOT PROCESSES")
    else:
        print_section("Kill SpiderFoot Processes", C.BRIGHT_RED)

    # Find running processes
    try:
        result = subprocess.run(
            ["pgrep", "-af", "sf.py"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            processes = result.stdout.strip().split('\n')
            if CYBER_UI_AVAILABLE:
                console.print(f"[yellow]Found {len(processes)} SpiderFoot process(es):[/]\n")
                for proc in processes:
                    console.print(f"  [dim]{proc}[/]")
                console.print()
            else:
                print(f"\n{C.YELLOW}Found {len(processes)} SpiderFoot process(es):{C.RESET}\n")
                for proc in processes:
                    print(f"  {C.DIM}{proc}{C.RESET}")
                print()
        else:
            if CYBER_UI_AVAILABLE:
                cyber_info("No SpiderFoot processes found running.")
            else:
                print_info("No SpiderFoot processes found running.")
            get_input("\nPress Enter to return...")
            return
    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Could not check processes: {e}")
        else:
            print_error(f"Could not check processes: {e}")
        get_input("\nPress Enter to return...")
        return

    # Confirm
    do_kill = cyber_confirm("Kill all SpiderFoot processes?") if CYBER_UI_AVAILABLE else confirm("Kill all SpiderFoot processes?")

    if not do_kill:
        print_info("Cancelled.")
        get_input("\nPress Enter to return...")
        return

    killed = kill_spiderfoot_processes()

    if CYBER_UI_AVAILABLE:
        cyber_success(f"Killed {killed} process(es)")
    else:
        print_success(f"Killed {killed} process(es)")

    get_input("\nPress Enter to return...")


def run_spiderfoot_scans_menu():
    """Menu for running SpiderFoot scans"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_banner_spider()
        cyber_header("SPIDERFOOT SCAN CONTROLLER")
    else:
        print_banner()
        print_section("Run SpiderFoot Scans", C.BRIGHT_CYAN)

    # Check if background scan is already running
    if is_background_scan_running():
        bg_stats = get_background_scan_stats()
        progress = bg_stats['completed'] + bg_stats['failed']

        if CYBER_UI_AVAILABLE:
            from rich.panel import Panel
            from rich.text import Text
            progress_text = Text()
            progress_text.append("⚡ BACKGROUND SCAN IN PROGRESS\n\n", style="bold yellow")
            progress_text.append(f"   Progress: ", style="white")
            progress_text.append(f"{progress}/{bg_stats['total']}", style="bold cyan")
            progress_text.append(f" scans\n", style="white")
            progress_text.append(f"   Completed: ", style="white")
            progress_text.append(f"{bg_stats['completed']}", style="bold green")
            progress_text.append(f"   Failed: ", style="white")
            progress_text.append(f"{bg_stats['failed']}", style="bold red")
            console.print(Panel(progress_text, border_style="yellow", title="[bold yellow]⟐ ACTIVE SCAN ⟐[/]"))
            console.print()
            cyber_info("Use option [4] to view detailed progress")
            cyber_info("Wait for current scans to complete before starting new ones")
        else:
            print(f"""
{C.BRIGHT_YELLOW}╔═══════════════════════════════════════════════════════════════════════════════╗
║  🔄 BACKGROUND SCAN ALREADY IN PROGRESS                                        ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║   Progress: {progress}/{bg_stats['total']} scans ({bg_stats['completed']} completed, {bg_stats['failed']} failed){' ' * 25}║
╚═══════════════════════════════════════════════════════════════════════════════╝{C.RESET}
""")
            print_info("Use option [4] to view detailed progress.")
            print_info("Wait for current scans to complete before starting new ones.")
        get_input("\nPress Enter to return to main menu...")
        return

    try:
        from discovery.scanner import SpiderFootScanner, get_install_guide
        from discovery.jobs import JobTracker
    except ImportError as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Discovery module not available: {e}")
        else:
            print_error(f"Discovery module not available: {e}")
        get_input("\nPress Enter to return to main menu...")
        return

    # Check for pending domains
    config = load_config()
    pending_domains = config.get('pending_domains', [])

    # Also check job tracker for any existing jobs
    tracker = JobTracker()
    existing_pending = len(tracker.get_pending())
    existing_running = len(tracker.get_running())

    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        from rich.text import Text
        from rich.table import Table

        # Create spider web style queue display
        queue_table = Table(show_header=False, box=None, padding=(0, 2))
        queue_table.add_column("Label", style="dim white")
        queue_table.add_column("Value", style="bold")
        queue_table.add_row("◈ Domains loaded (new)", f"[cyan]{len(pending_domains)}[/]")
        queue_table.add_row("◈ Existing pending scans", f"[cyan]{existing_pending}[/]")
        queue_table.add_row("◈ Currently running", f"[yellow]{existing_running}[/]")

        console.print(Panel(
            queue_table,
            title="[bold magenta]⟨ SCAN QUEUE ⟩[/]",
            border_style="magenta",
            padding=(1, 2)
        ))
        console.print()
    else:
        print(f"""
{C.WHITE}SpiderFoot Batch Scanner{C.RESET}
{C.DIM}━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}

{C.WHITE}Current Queue:{C.RESET}
  • Domains loaded (new):     {C.CYAN}{len(pending_domains)}{C.RESET}
  • Existing pending scans:   {C.CYAN}{existing_pending}{C.RESET}
  • Currently running:        {C.YELLOW}{existing_running}{C.RESET}
""")

    # Check if SpiderFoot is configured
    sf_path = config.get('spiderfoot_path')
    sf_output = config.get('spiderfoot_output_dir', './spiderfoot_exports')

    if CYBER_UI_AVAILABLE:
        # Display configuration status
        config_table = Table(show_header=False, box=None, padding=(0, 2))
        config_table.add_column("Label", style="dim white")
        config_table.add_column("Value")
        if sf_path and os.path.exists(sf_path):
            config_table.add_row("◈ SpiderFoot path", f"[green]{sf_path}[/]")
        else:
            config_table.add_row("◈ SpiderFoot path", "[red]Not configured[/]")
            sf_path = None
        config_table.add_row("◈ Output directory", f"[cyan]{sf_output}[/]")
        console.print(config_table)
        console.print()
    else:
        if sf_path and os.path.exists(sf_path):
            print(f"  • SpiderFoot path:          {C.GREEN}{sf_path}{C.RESET}")
        else:
            print(f"  • SpiderFoot path:          {C.RED}Not configured{C.RESET}")
            sf_path = None
        print(f"  • Output directory:         {C.CYAN}{sf_output}{C.RESET}")
        print()

    if not pending_domains and existing_pending == 0:
        if CYBER_UI_AVAILABLE:
            cyber_warning("No domains in queue")
            cyber_info("Use option [1] or [2] to add domains first")
        else:
            print_warning("No domains in queue.")
            print_info("Use option [1] or [2] to add domains first.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Configure SpiderFoot path if not set
    sf_python = config.get('spiderfoot_python')  # The venv python for SpiderFoot

    if not sf_path or not sf_python:
        if CYBER_UI_AVAILABLE:
            cyber_warning("SpiderFoot not configured")
        else:
            print(f"\n{C.YELLOW}SpiderFoot not configured.{C.RESET}")

        # Check if we have SpiderFoot installed in project directory
        script_dir = Path(__file__).parent
        project_sf_path = script_dir / "spiderfoot" / "sf.py"
        project_sf_python = script_dir / "spiderfoot" / "venv" / "bin" / "python3"

        if project_sf_path.exists() and project_sf_python.exists():
            if CYBER_UI_AVAILABLE:
                cyber_success("Found SpiderFoot in project directory!")
            else:
                print_success(f"Found SpiderFoot in project directory!")
            sf_path = str(project_sf_path)
            sf_python = str(project_sf_python)
            config['spiderfoot_path'] = sf_path
            config['spiderfoot_python'] = sf_python
            save_config(config)
        else:
            # Offer to install
            if CYBER_UI_AVAILABLE:
                from rich.panel import Panel
                install_text = Text()
                install_text.append("SpiderFoot is required to scan domains.\n\n", style="white")
                install_text.append("Source:   ", style="dim")
                install_text.append("https://github.com/smicallef/spiderfoot\n", style="cyan")
                install_text.append("Install:  ", style="dim")
                install_text.append("Clone repo → Create venv → Install dependencies\n", style="white")
                install_text.append("Location: ", style="dim")
                install_text.append("./spiderfoot/ (in this project directory)", style="white")
                console.print(Panel(install_text, title="[bold red]⚠ SPIDERFOOT NOT INSTALLED[/]", border_style="red"))
                console.print()
            else:
                print(f"""
{C.WHITE}SpiderFoot is not installed.{C.RESET}

SpiderFoot is required to scan domains. Would you like to install it now?

{C.DIM}Source:{C.RESET}  {C.CYAN}https://github.com/smicallef/spiderfoot{C.RESET}
{C.DIM}Install:{C.RESET} Clone repo → Create venv → Install dependencies
{C.DIM}Location:{C.RESET} ./spiderfoot/ (in this project directory)
""")
            do_install = cyber_confirm("Install SpiderFoot now?") if CYBER_UI_AVAILABLE else confirm("Install SpiderFoot now?")
            if do_install:
                result = install_spiderfoot_interactive()
                if result:
                    # Reload config after install
                    config = load_config()
                    sf_path = config.get('spiderfoot_path')
                    sf_python = config.get('spiderfoot_python')
                    if not sf_path or not sf_python:
                        if CYBER_UI_AVAILABLE:
                            cyber_error("Installation completed but configuration not saved properly")
                        else:
                            print_error("Installation completed but configuration not saved properly.")
                        get_input("\nPress Enter to return to main menu...")
                        return
                else:
                    if CYBER_UI_AVAILABLE:
                        cyber_error("SpiderFoot installation failed or was cancelled")
                    else:
                        print_error("SpiderFoot installation failed or was cancelled.")
                    get_input("\nPress Enter to return to main menu...")
                    return
            else:
                if CYBER_UI_AVAILABLE:
                    cyber_info("SpiderFoot is required to run scans")
                    cyber_info("You can install it anytime via Help [8] → Install SpiderFoot")
                else:
                    print_info("SpiderFoot is required to run scans.")
                    print_info("You can install it anytime via Help [8] → Install SpiderFoot")
                get_input("\nPress Enter to return to main menu...")
                return

    # Verify SpiderFoot works with its venv python
    if CYBER_UI_AVAILABLE:
        cyber_info("Verifying SpiderFoot installation...")
    else:
        print_info("Verifying SpiderFoot installation...")
    try:
        result = subprocess.run(
            [sf_python, sf_path, "--help"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            if CYBER_UI_AVAILABLE:
                cyber_success("SpiderFoot is ready!")
            else:
                print_success("SpiderFoot is ready!")
        else:
            if CYBER_UI_AVAILABLE:
                cyber_error("SpiderFoot verification failed")
                console.print(f"[dim]{result.stderr[:200]}[/]")
                do_reinstall = cyber_confirm("Would you like to reinstall SpiderFoot?")
            else:
                print_error("SpiderFoot verification failed:")
                print(f"{C.DIM}{result.stderr[:200]}{C.RESET}")
                do_reinstall = confirm("Would you like to reinstall SpiderFoot?")
            if do_reinstall:
                install_spiderfoot_interactive()
                config = load_config()
                sf_path = config.get('spiderfoot_path')
                sf_python = config.get('spiderfoot_python')
            else:
                get_input("\nPress Enter to return to main menu...")
                return
    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"SpiderFoot verification failed: {e}")
            do_reinstall = cyber_confirm("Would you like to reinstall SpiderFoot?")
        else:
            print_error(f"SpiderFoot verification failed: {e}")
            do_reinstall = confirm("Would you like to reinstall SpiderFoot?")
        if do_reinstall:
            install_spiderfoot_interactive()
            config = load_config()
            sf_path = config.get('spiderfoot_path')
            sf_python = config.get('spiderfoot_python')
        else:
            get_input("\nPress Enter to return to main menu...")
            return

    # Configure output directory
    if CYBER_UI_AVAILABLE:
        console.print()
        console.print("[bold white]Where should SpiderFoot save CSV exports?[/]")
    else:
        print(f"\n{C.WHITE}Where should SpiderFoot save CSV exports?{C.RESET}")
    sf_output = get_input("Output directory", sf_output)
    if sf_output is None:
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled")
        else:
            print_info("Cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return

    sf_output = os.path.expanduser(sf_output)
    if not os.path.exists(sf_output):
        do_create = cyber_confirm(f"Create directory {sf_output}?") if CYBER_UI_AVAILABLE else confirm(f"Create directory {sf_output}?")
        if do_create:
            os.makedirs(sf_output, exist_ok=True)
        else:
            if CYBER_UI_AVAILABLE:
                cyber_info("Cancelled")
            else:
                print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
            return

    config['spiderfoot_output_dir'] = sf_output
    save_config(config)

    # Add new domains to tracker
    if pending_domains:
        added = tracker.add_domains(pending_domains)
        if CYBER_UI_AVAILABLE:
            cyber_success(f"Added {added} new domains to scan queue")
        else:
            print_success(f"Added {added} new domains to scan queue")
        # Clear pending domains from config
        config['pending_domains'] = []
        save_config(config)

    # Configure parallelism
    max_parallel = get_input("Max parallel scans", "3")
    if max_parallel is None:
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled")
        else:
            print_info("Cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return
    try:
        max_parallel = int(max_parallel)
        max_parallel = max(1, min(10, max_parallel))  # Limit 1-10
    except ValueError:
        max_parallel = 3

    # Confirm and start
    total_pending = len(tracker.get_pending())

    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        from rich.text import Text

        # Spider web style scan summary
        scan_text = Text()
        scan_text.append("◈ Domains to scan:   ", style="dim white")
        scan_text.append(f"{total_pending}\n", style="bold cyan")
        scan_text.append("◈ Parallel scans:    ", style="dim white")
        scan_text.append(f"{max_parallel}\n", style="bold yellow")
        scan_text.append("◈ Output directory:  ", style="dim white")
        scan_text.append(f"{sf_output}\n", style="cyan")
        scan_text.append("◈ SpiderFoot path:   ", style="dim white")
        scan_text.append(f"{sf_path}\n\n", style="dim")
        scan_text.append("Note: Each scan may take 5-30 minutes", style="dim italic")

        console.print(Panel(scan_text, title="[bold green]⟨ READY TO SCAN ⟩[/]", border_style="green"))
        console.print()

        # Run mode menu
        console.print("[bold white]How would you like to run scans?[/]\n")
        console.print("  [bold green][1][/] Run in background (return to menu, check progress with [4])")
        console.print("  [bold yellow][2][/] Run in foreground (watch progress live)")
        console.print("  [bold red][3][/] Cancel")
        console.print()
    else:
        print(f"""
{C.BRIGHT_GREEN}{'━' * 60}{C.RESET}
{C.WHITE}Ready to scan:{C.RESET}

  Domains to scan:     {total_pending}
  Parallel scans:      {max_parallel}
  Output directory:    {sf_output}
  SpiderFoot path:     {sf_path}

{C.DIM}Note: Each scan may take 5-30 minutes depending on the domain.{C.RESET}
{C.BRIGHT_GREEN}{'━' * 60}{C.RESET}

{C.WHITE}How would you like to run scans?{C.RESET}

  {C.BRIGHT_GREEN}[1]{C.RESET} Run in background (return to menu, check progress with [4])
  {C.BRIGHT_YELLOW}[2]{C.RESET} Run in foreground (watch progress live)
  {C.BRIGHT_RED}[3]{C.RESET} Cancel
""")

    choice = get_input("Choice", "1")
    if choice is None or choice == "3":
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled. Domains remain in queue for later")
        else:
            print_info("Cancelled. Domains remain in queue for later.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Create scanner
    scanner = SpiderFootScanner(
        spiderfoot_path=sf_path,
        output_dir=sf_output,
        max_parallel=max_parallel,
        job_tracker=tracker,
        spiderfoot_python=sf_python
    )

    if choice == "1":
        # Run in background
        global _background_scan_thread
        _update_background_stats(
            running=True,
            completed=0,
            failed=0,
            total=total_pending,
            current_domain=None,
            start_time=datetime.now().isoformat()
        )

        _background_scan_thread = threading.Thread(
            target=_run_background_scans,
            args=(scanner, tracker),
            daemon=True
        )
        _background_scan_thread.start()

        if CYBER_UI_AVAILABLE:
            cyber_success("Scans started in background!")
            cyber_info("Returning to main menu. Use option [4] to check progress")
        else:
            print_success("Scans started in background!")
            print_info("Returning to main menu. Use option [4] to check progress.")
        time.sleep(1.5)
        return

    # Run in foreground (choice == "2")
    if CYBER_UI_AVAILABLE:
        cyber_header("RUNNING SPIDERFOOT SCANS")
        console.print("[dim]Press Ctrl+C to pause and return to menu. Progress auto-saves.[/]\n")
    else:
        print_section("Running SpiderFoot Scans", C.BRIGHT_MAGENTA)
        print(f"{C.DIM}Press Ctrl+C to pause and return to menu. Progress auto-saves.{C.RESET}\n")

    try:
        if CYBER_UI_AVAILABLE:
            def on_start(domain):
                console.print(f"  [cyan]▶[/] Starting scan: [bold]{domain}[/]")

            def on_complete(domain, csv_path):
                console.print(f"  [green]✓[/] Completed: [bold green]{domain}[/]")

            def on_failed(domain, error):
                console.print(f"  [red]✗[/] Failed: [bold]{domain}[/] - [dim]{error[:50]}[/]")

            def on_progress(completed, failed, total):
                console.print(f"\n  [bold cyan]Progress: {completed + failed}/{total} "
                      f"({completed} completed, {failed} failed)[/]\n")
        else:
            def on_start(domain):
                print(f"  {C.CYAN}▶{C.RESET} Starting scan: {domain}")

            def on_complete(domain, csv_path):
                print(f"  {C.GREEN}✓{C.RESET} Completed: {domain}")

            def on_failed(domain, error):
                print(f"  {C.RED}✗{C.RESET} Failed: {domain} - {error[:50]}")

            def on_progress(completed, failed, total):
                print(f"\n  {C.BRIGHT_CYAN}Progress: {completed + failed}/{total} "
                      f"({completed} completed, {failed} failed){C.RESET}\n")

        scanner.on_scan_start = on_start
        scanner.on_scan_complete = on_complete
        scanner.on_scan_failed = on_failed
        scanner.on_progress = on_progress

        results = scanner.process_queue(progress_callback=on_progress)

    except KeyboardInterrupt:
        if CYBER_UI_AVAILABLE:
            cyber_warning("\n\nScanning paused. Progress has been saved")
            cyber_info("Use option [3] to resume, or [4] to check queue status")
        else:
            print_warning("\n\nScanning paused. Progress has been saved.")
            print_info("Use option [3] to resume, or [4] to check queue status.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Show results
    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        from rich.text import Text

        result_text = Text()
        result_text.append("✓ ", style="bold green")
        result_text.append("Scanning complete!\n\n", style="bold white")
        result_text.append("  Total scans:     ", style="dim white")
        result_text.append(f"{results['total']}\n", style="bold")
        result_text.append("  Completed:       ", style="dim white")
        result_text.append(f"{results['completed']}\n", style="bold green")
        result_text.append("  Failed:          ", style="dim white")
        result_text.append(f"{results['failed']}\n\n", style="bold red")
        result_text.append("  CSV exports saved to: ", style="dim white")
        result_text.append(f"{sf_output}", style="cyan")

        console.print(Panel(result_text, title="[bold green]⟨ SCAN COMPLETE ⟩[/]", border_style="green"))
        console.print()
    else:
        print(f"""
{C.BRIGHT_GREEN}{'━' * 60}{C.RESET}
{C.GREEN}✓{C.RESET} Scanning complete!

  Total scans:     {results['total']}
  Completed:       {C.GREEN}{results['completed']}{C.RESET}
  Failed:          {C.RED}{results['failed']}{C.RESET}

  CSV exports saved to: {sf_output}
{C.BRIGHT_GREEN}{'━' * 60}{C.RESET}
""")

    if results['failed'] > 0:
        do_retry = cyber_confirm("Retry failed scans?") if CYBER_UI_AVAILABLE else confirm("Retry failed scans?")
        if do_retry:
            tracker.retry_failed()
            if CYBER_UI_AVAILABLE:
                cyber_info("Failed scans reset. Run this option again to retry")
            else:
                print_info("Failed scans reset. Run this option again to retry.")

    do_proceed = cyber_confirm("\nProceed to Puppet Analysis on these exports?") if CYBER_UI_AVAILABLE else confirm("\nProceed to Puppet Analysis on these exports?")
    if do_proceed:
        # Remember the output dir for analysis
        remember_output_dir(sf_output)
        if CYBER_UI_AVAILABLE:
            cyber_info("Use option [5] Run Puppet Analysis and point to this directory")
        else:
            print_info("Use option [5] Run Puppet Analysis and point to this directory.")

    get_input("\nPress Enter to return to main menu...")


def check_scan_status_menu():
    """Show scan queue status"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_banner_queue()
        cyber_header("SCAN QUEUE STATUS")
    else:
        print_banner()
        print_section("Scan Queue Status", C.BRIGHT_CYAN)

    try:
        from discovery.jobs import JobTracker
    except ImportError as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Discovery module not available: {e}")
        else:
            print_error(f"Discovery module not available: {e}")
        get_input("\nPress Enter to return to main menu...")
        return

    tracker = JobTracker()
    stats = tracker.get_stats()

    # Show live background scan status if running
    if is_background_scan_running():
        bg_stats = get_background_scan_stats()
        progress = bg_stats['completed'] + bg_stats['failed']
        current = bg_stats.get('current_domain', 'starting...')
        elapsed = get_elapsed_time_str()
        # Calculate percentage
        pct = int((progress / bg_stats['total'] * 100)) if bg_stats['total'] > 0 else 0
        # Progress bar
        bar_width = 30
        filled = int(bar_width * progress / bg_stats['total']) if bg_stats['total'] > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        # Module-level progress
        results_found = bg_stats.get('results_found', 0)
        file_size_kb = bg_stats.get('file_size_kb', 0.0)

        # Smart status: show "scanning..." if we have data flowing
        current_module = bg_stats.get('current_module')
        if current_module:
            status_str = current_module
        elif file_size_kb > 0 or results_found > 0:
            status_str = "scanning... (collecting data)"
        else:
            status_str = "initializing..."

        if CYBER_UI_AVAILABLE:
            from rich.panel import Panel
            from rich.text import Text
            from rich.progress import BarColumn, Progress, TextColumn, TaskProgressColumn

            # Create progress display
            scan_text = Text()
            scan_text.append("⚡ BACKGROUND SCAN IN PROGRESS\n\n", style="bold yellow")
            scan_text.append(f"  [{bar}] {pct:3d}%\n\n", style="cyan")
            scan_text.append(f"  Queue:    ", style="dim white")
            scan_text.append(f"{progress}/{bg_stats['total']}", style="bold cyan")
            scan_text.append(f" scans  ({bg_stats['completed']} completed, {bg_stats['failed']} failed)\n", style="white")
            scan_text.append(f"  Elapsed:  ", style="dim white")
            scan_text.append(f"{elapsed}\n\n", style="yellow")
            scan_text.append(f"  Domain:   ", style="dim white")
            scan_text.append(f"{current[:50]}\n", style="bold white")
            scan_text.append(f"  Status:   ", style="dim white")
            scan_text.append(f"{status_str[:50]}\n", style="magenta")
            scan_text.append(f"  Results:  ", style="dim white")
            scan_text.append(f"{results_found}", style="green")
            scan_text.append(f"  |  File: ", style="dim white")
            scan_text.append(f"{file_size_kb:,.1f} KB", style="cyan")

            console.print(Panel(scan_text, title="[bold yellow]⟨ ACTIVE SCAN ⟩[/]", border_style="yellow"))
            console.print()
        else:
            print(f"""
{C.BRIGHT_YELLOW}╔═══════════════════════════════════════════════════════════════════════════════╗
║  🔄 BACKGROUND SCAN IN PROGRESS                                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   [{bar}] {pct:3d}%{' ' * 13}║
║                                                                               ║
║   Queue:       {progress}/{bg_stats['total']} scans ({bg_stats['completed']} completed, {bg_stats['failed']} failed){' ' * 20}║
║   Elapsed:     {elapsed:<20}                                          ║
╠───────────────────────────────────────────────────────────────────────────────╣
║   Domain:      {current[:50]:<50} ║
║   Status:      {status_str[:50]:<50} ║
║   Results:     {results_found:<10} | File: {file_size_kb:,.1f} KB{' ' * 24}║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝{C.RESET}
""")

    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        from rich.text import Text
        from rich.table import Table

        # Queue status table
        queue_table = Table(show_header=False, box=None, padding=(0, 2))
        queue_table.add_column("Label", style="dim white")
        queue_table.add_column("Value", style="bold")
        queue_table.add_row("Total jobs", f"{stats['total']}")
        queue_table.add_row("Pending", f"[cyan]{stats['pending']}[/]")
        queue_table.add_row("Running", f"[yellow]{stats['running']}[/]")
        queue_table.add_row("Completed", f"[green]{stats['completed']}[/]")
        queue_table.add_row("Failed", f"[red]{stats['failed']}[/]")

        console.print(Panel(queue_table, title="[bold cyan]⟨ QUEUE STATUS ⟩[/]", border_style="cyan"))
        console.print()
    else:
        print(f"""
{C.WHITE}Queue Status (from tracker):{C.RESET}
{C.DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}

  Total jobs:      {stats['total']}
  Pending:         {C.CYAN}{stats['pending']}{C.RESET}
  Running:         {C.YELLOW}{stats['running']}{C.RESET}
  Completed:       {C.GREEN}{stats['completed']}{C.RESET}
  Failed:          {C.RED}{stats['failed']}{C.RESET}
""")

    if stats['total'] == 0:
        if CYBER_UI_AVAILABLE:
            cyber_info("No jobs in queue. Use option [1] or [2] to add domains")
        else:
            print_info("No jobs in queue. Use option [1] or [2] to add domains.")
    else:
        # Show some details
        if stats['completed'] > 0:
            if CYBER_UI_AVAILABLE:
                console.print("[bold white]Completed Scans:[/]")
                for job in tracker.get_completed()[:5]:
                    console.print(f"  [green]✓[/] {job.domain}")
                if stats['completed'] > 5:
                    console.print(f"  [dim]... and {stats['completed'] - 5} more[/]")
            else:
                print(f"\n{C.WHITE}Completed Scans:{C.RESET}")
                for job in tracker.get_completed()[:5]:
                    print(f"  {C.GREEN}✓{C.RESET} {job.domain}")
                if stats['completed'] > 5:
                    print(f"  {C.DIM}... and {stats['completed'] - 5} more{C.RESET}")

        if stats['failed'] > 0:
            if CYBER_UI_AVAILABLE:
                console.print("\n[bold white]Failed Scans:[/]")
                for job in tracker.get_failed()[:5]:
                    error_msg = job.error[:40] if job.error else 'Unknown error'
                    console.print(f"  [red]✗[/] {job.domain}: [dim]{error_msg}[/]")
                if stats['failed'] > 5:
                    console.print(f"  [dim]... and {stats['failed'] - 5} more[/]")
            else:
                print(f"\n{C.WHITE}Failed Scans:{C.RESET}")
                for job in tracker.get_failed()[:5]:
                    print(f"  {C.RED}✗{C.RESET} {job.domain}: {job.error[:40] if job.error else 'Unknown error'}")
                if stats['failed'] > 5:
                    print(f"  {C.DIM}... and {stats['failed'] - 5} more{C.RESET}")

        if stats['pending'] > 0:
            if CYBER_UI_AVAILABLE:
                console.print("\n[bold white]Pending Scans:[/]")
                for job in tracker.get_pending()[:5]:
                    console.print(f"  [cyan]○[/] {job.domain}")
                if stats['pending'] > 5:
                    console.print(f"  [dim]... and {stats['pending'] - 5} more[/]")
            else:
                print(f"\n{C.WHITE}Pending Scans:{C.RESET}")
                for job in tracker.get_pending()[:5]:
                    print(f"  {C.CYAN}○{C.RESET} {job.domain}")
                if stats['pending'] > 5:
                    print(f"  {C.DIM}... and {stats['pending'] - 5} more{C.RESET}")

    if CYBER_UI_AVAILABLE:
        console.print()
    else:
        print()

    # Build options menu
    while True:
        if CYBER_UI_AVAILABLE:
            console.print("\n[bold white]Options:[/]")
            cyber_divider()
        else:
            print(f"\n{C.WHITE}Options:{C.RESET}")
            print(f"{C.DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")

        options = []
        # Always show refresh if scan is running
        if is_background_scan_running():
            options.append(('refresh', "Refresh status"))
            options.append(('watch', "Watch mode (auto-refresh every 5s)"))
        if stats['failed'] > 0:
            options.append(('retry', f"Retry failed scans ({stats['failed']})"))
        if stats['completed'] > 0:
            options.append(('clear_completed', f"Clear completed jobs ({stats['completed']})"))
        if stats['total'] > 0:
            options.append(('clear_all', "Clear ALL jobs (reset queue)"))
        options.append(('back', "Back to main menu"))

        for i, (key, label) in enumerate(options, 1):
            if CYBER_UI_AVAILABLE:
                if key == 'refresh':
                    console.print(f"  [bold cyan][{i}][/] [cyan]↻[/] {label}")
                elif key == 'watch':
                    console.print(f"  [bold cyan][{i}][/] [cyan]◉[/] {label}")
                elif key == 'retry':
                    console.print(f"  [bold yellow][{i}][/] [yellow]↻[/] {label}")
                elif key == 'clear_completed':
                    console.print(f"  [bold green][{i}][/] [green]✓[/] {label}")
                elif key == 'clear_all':
                    console.print(f"  [bold red][{i}][/] [red]⚠[/] {label}")
                else:
                    console.print(f"  [{i}] {label}")
            else:
                if key == 'refresh':
                    print(f"  [{i}] {C.CYAN}🔄{C.RESET} {label}")
                elif key == 'watch':
                    print(f"  [{i}] {C.CYAN}👁{C.RESET}  {label}")
                elif key == 'retry':
                    print(f"  [{i}] {C.YELLOW}🔄{C.RESET} {label}")
                elif key == 'clear_completed':
                    print(f"  [{i}] {C.GREEN}✓{C.RESET} {label}")
                elif key == 'clear_all':
                    print(f"  [{i}] {C.RED}⚠{C.RESET} {label}")
                else:
                    print(f"  [{i}] {label}")

        choice = get_input(f"\nSelect option [1-{len(options)}]: ").strip()

        if not choice or choice == str(len(options)):
            # Back to main menu (last option or empty)
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                action = options[idx][0]

                if action == 'refresh':
                    # Just re-enter this menu to refresh display
                    check_scan_status_menu()
                    return

                elif action == 'watch':
                    # Watch mode - auto-refresh every 3 seconds for more responsive updates
                    import time
                    if CYBER_UI_AVAILABLE:
                        console.print("\n[cyan]Watch mode active. Refreshing every 3s. Press Ctrl+C to stop.[/]")
                    else:
                        print(f"\n{C.CYAN}Watch mode active. Refreshing every 3s. Press Ctrl+C to stop.{C.RESET}")
                    try:
                        while is_background_scan_running():
                            time.sleep(3)
                            clear_screen()

                            if CYBER_UI_AVAILABLE:
                                cyber_banner_queue()
                                cyber_header("SCAN QUEUE STATUS - LIVE")
                            else:
                                print_banner()
                                print_section("Scan Queue Status - LIVE", C.BRIGHT_CYAN)

                            # Show live stats
                            bg_stats = get_background_scan_stats()
                            progress = bg_stats['completed'] + bg_stats['failed']
                            current = bg_stats.get('current_domain', 'starting...')
                            elapsed = get_elapsed_time_str()
                            pct = int((progress / bg_stats['total'] * 100)) if bg_stats['total'] > 0 else 0
                            bar_width = 30
                            filled = int(bar_width * progress / bg_stats['total']) if bg_stats['total'] > 0 else 0
                            bar = "█" * filled + "░" * (bar_width - filled)

                            # Module-level progress
                            results_found = bg_stats.get('results_found', 0)
                            file_size_kb = bg_stats.get('file_size_kb', 0.0)

                            # Smart status: show "scanning..." if we have data flowing
                            current_module = bg_stats.get('current_module')
                            if current_module:
                                status_str = current_module
                            elif file_size_kb > 0 or results_found > 0:
                                status_str = "scanning... (collecting data)"
                            else:
                                status_str = "initializing..."

                            if CYBER_UI_AVAILABLE:
                                from rich.panel import Panel
                                from rich.text import Text

                                live_text = Text()
                                live_text.append("⚡ LIVE SCAN PROGRESS\n\n", style="bold yellow")
                                live_text.append(f"  [{bar}] {pct:3d}%\n\n", style="cyan")
                                live_text.append(f"  Queue:     ", style="dim white")
                                live_text.append(f"{progress}/{bg_stats['total']}", style="bold cyan")
                                live_text.append(f" scans  ({bg_stats['completed']} completed, {bg_stats['failed']} failed)\n", style="white")
                                live_text.append(f"  Elapsed:   ", style="dim white")
                                live_text.append(f"{elapsed}\n\n", style="yellow")
                                live_text.append(f"  Domain:    ", style="dim white")
                                live_text.append(f"{current[:50]}\n", style="bold white")
                                live_text.append(f"  Status:    ", style="dim white")
                                live_text.append(f"{status_str[:50]}\n", style="magenta")
                                live_text.append(f"  Results:   ", style="dim white")
                                live_text.append(f"{results_found}", style="green")
                                live_text.append(f" rows  |  File: ", style="dim white")
                                live_text.append(f"{file_size_kb:,.1f} KB\n\n", style="cyan")
                                live_text.append("  Press Ctrl+C to stop watching", style="dim italic")

                                console.print(Panel(live_text, title="[bold yellow]⟨ LIVE MONITOR ⟩[/]", border_style="yellow"))
                            else:
                                print(f"""
{C.BRIGHT_YELLOW}╔═══════════════════════════════════════════════════════════════════════════════╗
║  🔄 LIVE SCAN PROGRESS                                                         ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   [{bar}] {pct:3d}%{' ' * 13}║
║                                                                               ║
║   {C.WHITE}Queue:{C.RESET}{C.BRIGHT_YELLOW}       {progress}/{bg_stats['total']} scans ({bg_stats['completed']} completed, {bg_stats['failed']} failed){' ' * 20}║
║   {C.WHITE}Elapsed:{C.RESET}{C.BRIGHT_YELLOW}     {elapsed:<20}                                          ║
║                                                                               ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  {C.WHITE}Current Scan:{C.RESET}{C.BRIGHT_YELLOW}                                                              ║
║   Domain:      {current[:50]:<50} ║
║   Status:      {status_str[:50]:<50} ║
║   Results:     {results_found:<10} rows found                                     ║
║   File Size:   {file_size_kb:,.1f} KB                                                   ║
║                                                                               ║
║   {C.DIM}Press Ctrl+C to stop watching{C.RESET}{C.BRIGHT_YELLOW}                                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝{C.RESET}
""")
                            # Show recent activity from tracker
                            tracker_fresh = JobTracker()
                            completed_jobs = tracker_fresh.get_completed()[-3:]
                            if completed_jobs:
                                if CYBER_UI_AVAILABLE:
                                    console.print("[bold white]Recent completions:[/]")
                                    for job in reversed(completed_jobs):
                                        console.print(f"  [green]✓[/] {job.domain}")
                                else:
                                    print(f"{C.WHITE}Recent completions:{C.RESET}")
                                    for job in reversed(completed_jobs):
                                        print(f"  {C.GREEN}✓{C.RESET} {job.domain}")

                        # Scan finished
                        if CYBER_UI_AVAILABLE:
                            cyber_success("Scan complete!")
                        else:
                            print(f"\n{C.GREEN}Scan complete!{C.RESET}")
                        time.sleep(2)
                        check_scan_status_menu()
                        return

                    except KeyboardInterrupt:
                        if CYBER_UI_AVAILABLE:
                            console.print("\n[dim]Watch mode stopped.[/]")
                        else:
                            print(f"\n{C.DIM}Watch mode stopped.{C.RESET}")
                        time.sleep(1)
                        check_scan_status_menu()
                        return

                elif action == 'retry':
                    count = tracker.retry_failed()
                    if CYBER_UI_AVAILABLE:
                        cyber_success(f"Reset {count} failed jobs for retry")
                    else:
                        print_success(f"Reset {count} failed jobs for retry.")
                    stats = tracker.get_stats()  # Refresh stats

                elif action == 'clear_completed':
                    tracker.clear_completed()
                    if CYBER_UI_AVAILABLE:
                        cyber_success("Cleared completed jobs")
                    else:
                        print_success("Cleared completed jobs.")
                    stats = tracker.get_stats()  # Refresh stats

                elif action == 'clear_all':
                    do_clear = cyber_confirm("Are you sure? This cannot be undone.", default=False) if CYBER_UI_AVAILABLE else confirm("Are you sure? This cannot be undone.", default=False)
                    if do_clear:
                        tracker.clear_all()
                        if CYBER_UI_AVAILABLE:
                            cyber_success("Cleared all jobs")
                        else:
                            print_success("Cleared all jobs.")
                        stats = tracker.get_stats()  # Refresh stats

                elif action == 'back':
                    break
            else:
                if CYBER_UI_AVAILABLE:
                    cyber_error("Invalid option")
                else:
                    print_error("Invalid option")
        except ValueError:
            if choice.lower() in ('q', 'quit', 'back', 'b'):
                break
            if CYBER_UI_AVAILABLE:
                cyber_error("Please enter a number")
            else:
                print_error("Please enter a number")


# =============================================================================
# ANALYSIS RUNNER
# =============================================================================
def run_analysis():
    """Run the full sock puppet detection analysis"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_banner_analysis()
        cyber_header("PUPPET NETWORK ANALYZER")
    else:
        print_banner()

    # Get input directory
    input_dir = get_data_directory()
    if not input_dir:
        if CYBER_UI_AVAILABLE:
            cyber_error("Analysis cancelled - no input directory provided")
        else:
            print_error("Analysis cancelled - no input directory provided.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Get output directory
    output_dir = get_output_directory()
    if not output_dir:
        if CYBER_UI_AVAILABLE:
            cyber_error("Analysis cancelled - no output directory provided")
        else:
            print_error("Analysis cancelled - no output directory provided.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Confirmation
    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        from rich.text import Text

        config_text = Text()
        config_text.append("◈ Input:   ", style="dim white")
        config_text.append(f"{input_dir}\n", style="cyan")
        config_text.append("◈ Output:  ", style="dim white")
        config_text.append(f"{output_dir}", style="cyan")

        console.print(Panel(config_text, title="[bold green]⟨ ANALYSIS CONFIGURATION ⟩[/]", border_style="green"))
        console.print()

        do_start = cyber_confirm("Start the analysis?")
    else:
        print_section("Ready to Analyze", C.BRIGHT_GREEN)
        print(f"""
{C.WHITE}Analysis Configuration:{C.RESET}
  Input:  {C.CYAN}{input_dir}{C.RESET}
  Output: {C.CYAN}{output_dir}{C.RESET}
""")
        do_start = confirm("Start the analysis?")

    if not do_start:
        if CYBER_UI_AVAILABLE:
            cyber_info("Analysis cancelled")
        else:
            print_info("Analysis cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Run the pipeline
    if CYBER_UI_AVAILABLE:
        cyber_header("RUNNING ANALYSIS")
    else:
        print_section("Running Analysis", C.BRIGHT_MAGENTA)

    try:
        # Import and run the pipeline
        from core.pipeline import run_full_pipeline

        import random
        animated_print(f"\n{random.choice(HUNTING_MESSAGES)}\n", delay=0.02)

        success = run_full_pipeline(input_dir, output_dir)

        if success:
            if CYBER_UI_AVAILABLE:
                console.print()
                console.print("[bold green]" + "═" * 70 + "[/]")
                animated_print(f"{random.choice(COMPLETION_MESSAGES)}", delay=0.02)
                console.print("[bold green]" + "═" * 70 + "[/]")
                console.print()
                cyber_info(f"Results saved to: {output_dir}")
                cyber_info(f"Start with: {os.path.join(output_dir, 'executive_summary.md')}")
            else:
                print()
                print(f"{C.BRIGHT_GREEN}{'═' * 70}{C.RESET}")
                animated_print(f"{random.choice(COMPLETION_MESSAGES)}", delay=0.02)
                print(f"{C.BRIGHT_GREEN}{'═' * 70}{C.RESET}")
                print()
                print_info(f"Results saved to: {output_dir}")
                print_info(f"Start with: {os.path.join(output_dir, 'executive_summary.md')}")
        else:
            if CYBER_UI_AVAILABLE:
                cyber_error("Analysis completed with errors. Check the output directory for details")
            else:
                print_error("Analysis completed with errors. Check the output directory for details.")

    except ImportError as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Failed to import pipeline modules: {e}")
            cyber_info("Make sure you're running from the correct directory")
        else:
            print_error(f"Failed to import pipeline modules: {e}")
            print_info("Make sure you're running from the correct directory.")
    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Analysis failed: {e}")
        else:
            print_error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()

    get_input("\nPress Enter to return to main menu...")


# =============================================================================
# WILDCARD DNS ANALYZER
# =============================================================================
def run_wildcard_analyzer():
    """Run the Signal//Noise Wildcard DNS Analyzer"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_banner_wildcard()
        cyber_header("SIGNAL//NOISE WILDCARD DNS ANALYZER")

        from rich.panel import Panel
        from rich.text import Text

        desc_text = Text()
        desc_text.append("This tool investigates whether enumerated subdomains are real or\n", style="white")
        desc_text.append("just wildcard DNS artifacts (false positives).\n\n", style="white")
        desc_text.append("Use this when you see suspicious domains with thousands of subdomains\n", style="dim")
        desc_text.append("that might be inflating your cluster results.", style="dim")

        console.print(Panel(desc_text, border_style="cyan", padding=(0, 2)))
        console.print()

        # Options menu
        console.print("[bold yellow]Options:[/]")
        console.print("  [bold white][1][/] Quick Check - Test a domain for wildcard DNS")
        console.print("  [bold white][2][/] Full Analysis - Deep dive with SpiderFoot data correlation")
        console.print("  [bold white][3][/] Load from Puppet Analysis - Auto-detect suspects from results")
        console.print("  [bold white][4][/] Back to main menu")
        console.print()
    else:
        print_banner()
        print_section("Signal//Noise Wildcard DNS Analyzer", C.BRIGHT_CYAN)

        print(f"""
{C.WHITE}This tool investigates whether enumerated subdomains are real or
just wildcard DNS artifacts (false positives).{C.RESET}

{C.DIM}Use this when you see suspicious domains with thousands of subdomains
that might be inflating your cluster results.{C.RESET}
""")

        print(f"{C.BRIGHT_YELLOW}Options:{C.RESET}")
        print(f"  {C.WHITE}[1]{C.RESET} Quick Check - Test a domain for wildcard DNS")
        print(f"  {C.WHITE}[2]{C.RESET} Full Analysis - Deep dive with SpiderFoot data correlation")
        print(f"  {C.WHITE}[3]{C.RESET} Load from Puppet Analysis - Auto-detect suspects from results")
        print(f"  {C.WHITE}[4]{C.RESET} Back to main menu")
        print()

    choice = get_input("Select an option")
    if choice is None or choice == '4':
        return

    if choice == '1':
        # Quick check
        domain = get_input("Enter domain to check (e.g., example.io)")
        if not domain:
            if CYBER_UI_AVAILABLE:
                cyber_warning("No domain provided")
            else:
                print_warning("No domain provided.")
            get_input("\nPress Enter to return to main menu...")
            return

        if CYBER_UI_AVAILABLE:
            console.print()
            cyber_info(f"Testing {domain} for wildcard DNS...")
        else:
            print()
            print_info(f"Testing {domain} for wildcard DNS...")

        try:
            from wildcardDNS_analyzer import quick_wildcard_check, TerminalUI

            results = quick_wildcard_check([domain])
            result = results.get(domain, {})

            if result.get('is_wildcard'):
                if CYBER_UI_AVAILABLE:
                    console.print()
                    console.print("  [bold yellow][!] WILDCARD DNS DETECTED[/]")
                    console.print(f"      Domain: [bold white]{domain}[/]")
                    console.print(f"      Wildcard IP: [cyan]{result.get('wildcard_ip', 'unknown')}[/]")
                    console.print(f"      Confidence: {result.get('confidence', 'unknown')}")
                    console.print()
                    console.print("  [dim]This domain responds to ANY subdomain query.[/]")
                    console.print("  [dim]Enumerated subdomains are likely false positives.[/]")
                else:
                    print()
                    print(f"  {C.YELLOW}[!] WILDCARD DNS DETECTED{C.RESET}")
                    print(f"      Domain: {C.WHITE}{domain}{C.RESET}")
                    print(f"      Wildcard IP: {C.CYAN}{result.get('wildcard_ip', 'unknown')}{C.RESET}")
                    print(f"      Confidence: {result.get('confidence', 'unknown')}")
                    print()
                    print(f"  {C.DIM}This domain responds to ANY subdomain query.{C.RESET}")
                    print(f"  {C.DIM}Enumerated subdomains are likely false positives.{C.RESET}")
            else:
                if CYBER_UI_AVAILABLE:
                    console.print()
                    console.print("  [bold green][+] NO WILDCARD PATTERN[/]")
                    console.print(f"      Domain: [bold white]{domain}[/]")
                    console.print(f"      Confidence: {result.get('confidence', 'unknown')}")
                    console.print()
                    console.print("  [dim]This domain does NOT have wildcard DNS.[/]")
                    console.print("  [dim]Enumerated subdomains are likely real.[/]")
                else:
                    print()
                    print(f"  {C.GREEN}[+] NO WILDCARD PATTERN{C.RESET}")
                    print(f"      Domain: {C.WHITE}{domain}{C.RESET}")
                    print(f"      Confidence: {result.get('confidence', 'unknown')}")
                    print()
                    print(f"  {C.DIM}This domain does NOT have wildcard DNS.{C.RESET}")
                    print(f"  {C.DIM}Enumerated subdomains are likely real.{C.RESET}")

        except ImportError as e:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Failed to import wildcard analyzer: {e}")
                cyber_info("Make sure dnspython is installed: pip install dnspython")
            else:
                print_error(f"Failed to import wildcard analyzer: {e}")
                print_info("Make sure dnspython is installed: pip install dnspython")
        except Exception as e:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Quick check failed: {e}")
            else:
                print_error(f"Quick check failed: {e}")

    elif choice == '2':
        # Full analysis
        domain = get_input("Enter domain to analyze (e.g., example.io)")
        if not domain:
            if CYBER_UI_AVAILABLE:
                cyber_warning("No domain provided")
            else:
                print_warning("No domain provided.")
            get_input("\nPress Enter to return to main menu...")
            return

        # Get SpiderFoot directory
        if CYBER_UI_AVAILABLE:
            console.print()
            cyber_info("For full analysis, provide the SpiderFoot export directory")
        else:
            print()
            print_info("For full analysis, provide the SpiderFoot export directory.")
        spiderfoot_dir = get_input("SpiderFoot exports directory (or Enter to skip)")

        # Get output directory
        config = load_config()
        default_output = config.get('last_output_dir', './output')
        output_dir = get_input(f"Output directory [{default_output}]") or default_output

        if CYBER_UI_AVAILABLE:
            console.print()
            cyber_info(f"Starting full analysis of {domain}...")
            cyber_info("This may take a few minutes...")
            console.print()
        else:
            print()
            print_info(f"Starting full analysis of {domain}...")
            print_info("This may take a few minutes...")
            print()

        try:
            from wildcardDNS_analyzer import WildcardAnalyzer

            analyzer = WildcardAnalyzer(
                domain=domain,
                spiderfoot_dir=spiderfoot_dir if spiderfoot_dir else None,
                output_dir=output_dir
            )

            results = analyzer.run_full_analysis()

            if CYBER_UI_AVAILABLE:
                console.print()
                cyber_success("Analysis complete!")
                cyber_info(f"Reports saved to: {output_dir}")
            else:
                print()
                print_success("Analysis complete!")
                print_info(f"Reports saved to: {output_dir}")

        except ImportError as e:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Failed to import wildcard analyzer: {e}")
                cyber_info("Make sure dnspython is installed: pip install dnspython")
            else:
                print_error(f"Failed to import wildcard analyzer: {e}")
                print_info("Make sure dnspython is installed: pip install dnspython")
        except Exception as e:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Full analysis failed: {e}")
            else:
                print_error(f"Full analysis failed: {e}")
            import traceback
            traceback.print_exc()

    elif choice == '3':
        # Load from Puppet Analysis
        _wildcard_load_from_puppet()

    get_input("\nPress Enter to return to main menu...")


def _wildcard_load_from_puppet():
    """Load wildcard suspects from Puppet Analysis results"""
    try:
        from wildcardDNS_analyzer import (
            find_results_directories,
            parse_wildcard_suspects_from_summary,
            find_spiderfoot_exports_dir,
            WildcardAnalyzer
        )
    except ImportError as e:
        print_error(f"Failed to import wildcard analyzer: {e}")
        print_info("Make sure dnspython is installed: pip install dnspython")
        return

    print()
    print_section("Load from Puppet Analysis", C.BRIGHT_CYAN)

    # Find results directories
    results_dirs = find_results_directories()

    if not results_dirs:
        print_error("No PUPPETMASTER results directories found.")
        print_info("Run Puppet Analysis [option 5] first to generate results.")
        print()
        # Debug: show where we looked
        saved_dirs = get_remembered_output_dirs()
        if saved_dirs:
            print_info(f"Config has {len(saved_dirs)} saved path(s), but none contain executive_summary.md:")
            for d in saved_dirs[:3]:
                print(f"      {C.DIM}- {d}{C.RESET}")
        else:
            print_info(f"No saved paths in config. Config location: {CONFIG_FILE}")
            if not CONFIG_FILE.exists():
                print(f"      {C.DIM}(Config file does not exist){C.RESET}")
        return

    # Show available directories
    print_info(f"Found {len(results_dirs)} results director{'y' if len(results_dirs) == 1 else 'ies'}:")
    print()

    for i, d in enumerate(results_dirs[:10], 1):
        from datetime import datetime
        mtime = datetime.fromtimestamp(d.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        print(f"  {C.BRIGHT_YELLOW}[{i}]{C.RESET} {d.name} {C.DIM}({mtime}){C.RESET}")

    if len(results_dirs) > 10:
        print(f"  {C.DIM}... and {len(results_dirs) - 10} more{C.RESET}")
    print()

    # Auto-select most recent or let user choose
    choice = get_input("Select results directory", "1")

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(results_dirs):
            selected_dir = results_dirs[idx]
        else:
            print_warning("Invalid selection, using most recent.")
            selected_dir = results_dirs[0]
    except ValueError:
        from pathlib import Path
        if Path(choice).exists():
            selected_dir = Path(choice)
        else:
            print_warning("Invalid selection, using most recent.")
            selected_dir = results_dirs[0]

    print_success(f"Using: {selected_dir}")
    print()

    # Parse wildcard suspects
    suspects = parse_wildcard_suspects_from_summary(selected_dir)

    if not suspects:
        print_warning("No wildcard DNS suspects found in this analysis.")
        print_info("This could mean:")
        print(f"      {C.DIM}- No domains were flagged as potential wildcards{C.RESET}")
        print(f"      {C.DIM}- The analysis didn't run wildcard detection{C.RESET}")
        print()

        if confirm("Would you like to manually enter a domain to analyze?"):
            domain = get_input("Enter domain to analyze")
            if domain:
                _run_wildcard_full_analysis(domain)
        return

    # Display suspects
    print(f"{C.BRIGHT_YELLOW}Found {len(suspects)} wildcard DNS suspect(s):{C.RESET}")
    print()

    for i, s in enumerate(suspects, 1):
        print(f"  {C.BRIGHT_YELLOW}[{i}]{C.RESET} {s['domain']} {C.DIM}(IP: {s['wildcard_ip']}, Confidence: {s['confidence']}){C.RESET}")
    print()

    # Find SpiderFoot exports directory
    sf_dir = find_spiderfoot_exports_dir()
    if sf_dir:
        print_info(f"SpiderFoot exports: {sf_dir}")

    # Let user choose which domain to analyze
    print()
    print(f"{C.WHITE}Which domain would you like to analyze?{C.RESET}")
    print(f"  {C.DIM}Enter number, domain name, or 'all' for batch analysis{C.RESET}")
    print()

    selection = get_input("Selection", "1")

    domains_to_analyze = []

    if selection.lower() == 'all':
        domains_to_analyze = [s['domain'] for s in suspects]
    else:
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(suspects):
                domains_to_analyze = [suspects[idx]['domain']]
        except ValueError:
            for s in suspects:
                if selection.lower() in s['domain'].lower():
                    domains_to_analyze.append(s['domain'])
            if not domains_to_analyze:
                domains_to_analyze = [selection]

    if not domains_to_analyze:
        print_warning("No domain selected.")
        return

    # Confirm SpiderFoot directory
    if sf_dir:
        if not confirm(f"Use SpiderFoot exports from {sf_dir}?"):
            sf_input = get_input("SpiderFoot exports directory (or Enter to skip)")
            from pathlib import Path
            sf_dir = Path(sf_input) if sf_input else None
    else:
        sf_input = get_input("SpiderFoot exports directory (or Enter to skip)")
        from pathlib import Path
        sf_dir = Path(sf_input) if sf_input else None

    # Run analysis for each domain
    # Ensure wildcard_outputs directory exists
    from pathlib import Path
    wildcard_dir = Path("./wildcard_outputs")
    wildcard_dir.mkdir(exist_ok=True)

    for domain in domains_to_analyze:
        print()
        print(f"{C.BRIGHT_CYAN}{'=' * 70}{C.RESET}")
        print_info(f"Analyzing: {domain}")
        print(f"{C.BRIGHT_CYAN}{'=' * 70}{C.RESET}")
        print()

        from datetime import datetime
        output_dir = str(wildcard_dir / f"wildcard_analysis_{domain.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        try:
            analyzer = WildcardAnalyzer(
                domain=domain,
                spiderfoot_dir=str(sf_dir) if sf_dir else None,
                output_dir=output_dir
            )

            results = analyzer.run_full_analysis()

            print()
            print_success(f"Analysis complete. Reports saved to: {output_dir}")

        except Exception as e:
            print_error(f"Analysis failed for {domain}: {e}")

    print()
    print_success("All analyses complete!")


def _run_wildcard_full_analysis(domain: str):
    """Helper to run full wildcard analysis on a single domain"""
    try:
        from wildcardDNS_analyzer import WildcardAnalyzer, find_spiderfoot_exports_dir
    except ImportError as e:
        print_error(f"Failed to import wildcard analyzer: {e}")
        return

    sf_dir = find_spiderfoot_exports_dir()
    if sf_dir:
        print_info(f"Found SpiderFoot exports: {sf_dir}")
        if not confirm(f"Use this directory?"):
            sf_input = get_input("SpiderFoot exports directory (or Enter to skip)")
            from pathlib import Path
            sf_dir = Path(sf_input) if sf_input else None
    else:
        sf_input = get_input("SpiderFoot exports directory (or Enter to skip)")
        from pathlib import Path
        sf_dir = Path(sf_input) if sf_input else None

    from datetime import datetime
    # Save to wildcard_outputs/ subdirectory
    wildcard_dir = Path("./wildcard_outputs")
    wildcard_dir.mkdir(exist_ok=True)
    output_dir = str(wildcard_dir / f"wildcard_analysis_{domain.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    print()
    print_info(f"Starting full analysis of {domain}...")
    print()

    try:
        analyzer = WildcardAnalyzer(
            domain=domain,
            spiderfoot_dir=str(sf_dir) if sf_dir else None,
            output_dir=output_dir
        )

        results = analyzer.run_full_analysis()

        print()
        print_success("Analysis complete!")
        print_info(f"Reports saved to: {output_dir}")

    except Exception as e:
        print_error(f"Analysis failed: {e}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    """Main entry point"""
    # Check if we should be running in an existing venv
    ensure_running_in_venv()

    # Initial setup
    clear_screen()
    print_banner()

    # Check environment
    if not setup_environment():
        print_error("Environment setup failed. Please resolve the issues above and try again.")
        sys.exit(1)

    # Kali Linux detection and bootstrap
    if KALI_MODULE_AVAILABLE:
        print_section("OS Detection", C.BRIGHT_BLUE)
        is_kali, os_info = kali_startup_check(print_func=print)
        if is_kali:
            print_success("Kali Linux enhanced mode enabled!")
            time.sleep(1)
        else:
            print_info(f"Running on {os_info.os_name} - standard mode")
        time.sleep(1)

    time.sleep(1)

    # Report UI mode
    print_section("UI Mode", C.BRIGHT_MAGENTA)
    if USE_CYBERPUNK_HUD and CYBERPUNK_HUD_AVAILABLE:
        if sys.stdin.isatty():
            print_success("Cyberpunk HUD enabled (TTY detected)")
        else:
            print_warning("Cyberpunk HUD disabled (no TTY - using classic menu)")
    else:
        if not CYBERPUNK_HUD_AVAILABLE:
            print_info("Classic menu (Cyberpunk HUD not available - 'rich' not installed?)")
        else:
            print_info("Classic menu (Cyberpunk HUD disabled)")
    time.sleep(1)

    # Clear any buffered input from startup (prevents accidental quit)
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass  # Ignore on Windows or if stdin isn't a terminal

    # Main menu loop
    while True:
        # Use Cyberpunk HUD if available and enabled
        if USE_CYBERPUNK_HUD and CYBERPUNK_HUD_AVAILABLE:
            try:
                # Get scan mode function if Kali is available
                get_scan_mode = None
                if KALI_MODULE_AVAILABLE:
                    try:
                        from kali.integration import get_current_scan_mode
                        get_scan_mode = get_current_scan_mode
                    except ImportError:
                        pass

                hud_key = run_cyberpunk_hud_menu(
                    load_config=load_config,
                    is_background_scan_running=is_background_scan_running,
                    get_background_scan_stats=get_background_scan_stats,
                    should_show_kali_menu=should_show_kali_menu,
                    is_enhanced_mode=is_enhanced_mode if KALI_MODULE_AVAILABLE else None,
                    get_kali_status_line=get_kali_status_line if KALI_MODULE_AVAILABLE else None,
                    get_scan_mode=get_scan_mode,
                )
                choice = map_hud_key_to_choice(hud_key)
            except Exception as e:
                # Fallback to classic menu on error - show WHY it failed
                clear_screen()
                print_banner()
                print()
                print_warning(f"Cyberpunk HUD unavailable: {e}")
                print_info("Falling back to classic menu. Press Enter to continue...")
                try:
                    input()
                except (EOFError, KeyboardInterrupt):
                    pass
                show_main_menu()
                choice = get_input("Select an option")
                if choice is None:
                    choice = 'q'
                else:
                    choice = choice.lower()
        else:
            # Classic menu
            show_main_menu()
            choice = get_input("Select an option")

            # Handle Ctrl+C at main menu = exit gracefully
            if choice is None:
                choice = 'q'
            else:
                choice = choice.lower()

        # Discovery & Scanning
        if choice == '1':
            scrape_domains_menu()
        elif choice == '2':
            load_domains_menu()
        elif choice == '3':
            spiderfoot_control_center_menu()  # Unified SpiderFoot Control Center
        elif choice == '4':
            check_scan_status_menu()
        # Analysis
        elif choice == '5':
            run_analysis()
        elif choice == '6':
            view_previous_results()
        # Settings
        elif choice == '7':
            show_config()
        elif choice == '8':
            show_help()
        elif choice == '9':
            launch_in_tmux()
        elif choice == '10':
            launch_glances()
        elif choice == '11':
            run_wildcard_analyzer()  # Moved from 12
        # Legacy option redirects (for backward compatibility)
        elif choice == '12':
            run_wildcard_analyzer()  # Keep 12 working for old muscle memory
        # Kali Enhanced Mode options
        elif choice.startswith('k') and KALI_MODULE_AVAILABLE:
            handled = handle_enhanced_menu_choice(
                choice,
                print_func=print,
                get_input_func=get_input,
                clear_func=clear_screen,
                colors=C
            )
            if not handled:
                print_warning("Invalid Kali option.")
                time.sleep(1)
        elif choice in ('q', 'quit', 'exit'):
            # Check if background scan is running
            if is_background_scan_running():
                print_warning("Background scan is still running!")
                if not confirm("Quit anyway? (scans will be interrupted)"):
                    continue

            clear_screen()
            print(f"""
{C.BRIGHT_CYAN}
╔═════════════════════════════════════════════════════════════════╗
║                                                                 ║
║              Thank you for using PUPPETMASTER! 🎭               ║
║                                                                 ║
║                  Enjoy your noodles al dente.                   ║
║                                                                 ║
╚═════════════════════════════════════════════════════════════════╝
{C.RESET}
""")
            sys.exit(0)
        else:
            print_warning("Invalid option. Please try again.")
            time.sleep(1)

if __name__ == "__main__":
    main()
