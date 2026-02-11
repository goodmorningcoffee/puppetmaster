#!/usr/bin/env python3
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
        (f"{C.WHITE}SpiderFoot Sock Puppet Detector v1.0{C.BRIGHT_CYAN}", 36),
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

def get_input(prompt, default=None):
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
    return response.lower() in ('y', 'yes', '')

def animated_print(message, delay=0.03):
    """Print message with typing animation"""
    for char in message:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def progress_bar(current, total, prefix="Progress", length=40):
    """Display a progress bar"""
    percent = current / total
    filled = int(length * percent)
    bar = "█" * filled + "░" * (length - filled)
    print(f"\r{C.BRIGHT_CYAN}{prefix}: [{bar}] {percent*100:.1f}%{C.RESET}", end="", flush=True)
    if current == total:
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
        print(get_pip_install_instructions())
        return False

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

    print()
    print_success("Environment is ready!")
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
                os.makedirs(path)
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

    print(f"""
{C.WHITE}{C.BOLD}Welcome to PUPPETMASTER!{C.RESET}
{C.DIM}End-to-end sock puppet detection pipeline{C.RESET}

{C.WHITE}What does this tool do?{C.RESET}
{C.DIM}━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
Discovers, scans, and analyzes domains to expose "sock puppet" networks —
websites that {C.UNDERLINE}appear{C.RESET}{C.DIM} independent but are secretly controlled by the same operator.

{C.WHITE}The Pipeline:{C.RESET}
{C.DIM}━━━━━━━━━━━━━{C.RESET}
  {C.BRIGHT_CYAN}1. Discover{C.RESET}  Scrape search engines for competitor/suspicious domains
  {C.BRIGHT_CYAN}2. Scan{C.RESET}     Run SpiderFoot OSINT scans (batch or interactive GUI)
  {C.BRIGHT_CYAN}3. Analyze{C.RESET}  Detect shared infrastructure that proves common ownership

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
    print_menu_item("3", "Run SpiderFoot scans (CLI batch mode)", "🕷️")
    print_menu_item("4", "Check scan queue status", "📋")
    print_menu_item("11", "SpiderFoot Web GUI (interactive mode)", "🌐")
    print()

    # Analysis Section
    print(f"  {C.BRIGHT_GREEN}ANALYSIS{C.RESET}")
    print_menu_item("5", "Run Puppet Analysis on SpiderFoot scans", "🎭")
    print_menu_item("6", "View previous results", "📊")
    print()

    # Settings Section
    print(f"  {C.BRIGHT_MAGENTA}SETTINGS{C.RESET}")
    print_menu_item("7", "Configuration", "⚙️")
    print_menu_item("8", "Help & Documentation", "❓")
    print_menu_item("9", "Launch in tmux (for long scans)", "🖥️")
    print_menu_item("10", "System monitor (glances)", "📊")
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
        sf_cmd = f"{python_exe} {sf_path} -l 127.0.0.1:{port}"

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
                return sf_path
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

    return sf_path


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
    print_banner()
    print_section("Previous Results", C.BRIGHT_GREEN)

    # Find all results directories
    results_dirs = find_results_directories()

    if not results_dirs:
        print_warning("No previous results found.")
        print_info("Results are identified by containing an 'executive_summary.md' file.")
        print_info("Run a new analysis first, or check your output directory.")
        print()
        print(f"{C.DIM}Searched in:{C.RESET}")
        print(f"  • Current directory: {Path('.').resolve()}")
        print(f"  • Output directory:  {Path('output').resolve()}")
    else:
        print(f"Found {len(results_dirs)} previous analysis result(s):\n")
        for i, d in enumerate(results_dirs[:10], 1):
            # Get modification time and try to read scan info
            mtime = datetime.fromtimestamp(d.stat().st_mtime)
            # Show relative path if in current dir, otherwise full path
            try:
                display_path = d.relative_to(Path.cwd())
            except ValueError:
                display_path = d

            print_menu_item(str(i), f"{display_path} ({mtime.strftime('%Y-%m-%d %H:%M')})", "📁")

        print()
        choice = get_input("Enter number to view, or press Enter to go back")

        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(results_dirs):
                summary_path = results_dirs[idx] / "executive_summary.md"
                if summary_path.exists():
                    print(f"\n{C.CYAN}{'─' * 70}{C.RESET}")
                    print(summary_path.read_text())
                    print(f"{C.CYAN}{'─' * 70}{C.RESET}\n")
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


def show_scrape_results_menu(domains, keywords, use_google, use_duckduckgo, max_results):
    """Show post-scrape menu with options to view, re-run, add more, etc."""
    from discovery.scraper import DomainScraper

    while True:
        clear_screen()
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
        print_menu_item("3", "Re-run with same keywords", f"{C.BRIGHT_RED}◆{C.RESET}")
        print_menu_item("4", "Start fresh (new keywords)", f"{C.BRIGHT_RED}◆{C.RESET}")
        print_menu_item("5", "Save to file", f"{C.BRIGHT_RED}◆{C.RESET}")
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

        elif choice == "5":
            # Save to file
            from discovery.scraper import DomainScraper
            scraper = DomainScraper()

            default_filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            print(f"\n{C.WHITE}Save location:{C.RESET}")
            save_path = get_input("File path", default_filename)

            if save_path:
                save_path = os.path.expanduser(save_path)
                save_dir = os.path.dirname(save_path)
                if save_dir and not os.path.exists(save_dir):
                    os.makedirs(save_dir)

                if scraper.save_to_file(save_path, domains):
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
    print_banner()
    print_section("Scrape Domains via Keywords", C.BRIGHT_CYAN)

    # Check dependencies
    try:
        from discovery.scraper import DomainScraper
    except ImportError as e:
        print_error(f"Discovery module not available: {e}")
        print_info("Make sure you're running from the correct directory.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Check if search libraries are available
    deps = DomainScraper.check_dependencies()
    if not deps['google'] and not deps['duckduckgo']:
        print_error("No search libraries available!")
        print_info("Install with: pip install googlesearch-python duckduckgo_search")
        get_input("\nPress Enter to return to main menu...")
        return

    # Check for previous session
    config = load_config()
    last_domains = config.get('last_scrape_domains', [])
    last_keywords = config.get('last_scrape_keywords', [])

    if last_domains:
        print(f"""
{C.BRIGHT_YELLOW}Previous session found:{C.RESET}
  Domains: {len(last_domains)}
  Keywords: {', '.join(last_keywords[:3])}{'...' if len(last_keywords) > 3 else ''}
""")
        print_menu_item("1", "Continue with previous results", "▶️")
        print_menu_item("2", "Start fresh", "🆕")
        print()

        resume_choice = get_input("Choice", "1")
        if resume_choice == "1":
            # Resume previous session
            # Need to get search engine settings
            use_google = deps['google']
            use_duckduckgo = deps['duckduckgo']
            max_results = 50

            result = show_scrape_results_menu(
                set(last_domains), last_keywords,
                use_google, use_duckduckgo, max_results
            )
            if result is None:
                # User chose to start fresh, continue below
                pass
            else:
                return

        clear_screen()
        print_banner()
        print_section("Scrape Domains via Keywords", C.BRIGHT_CYAN)

    print(f"""
{C.WHITE}Enter keywords to search for domains.{C.RESET}
{C.DIM}Separate multiple keywords with commas.{C.RESET}

{C.DIM}Examples:{C.RESET}
  • electrical contractors NYC, electrical services New York
  • plastic surgery clinic, cosmetic surgeon
  • online tutoring, math help
""")

    # Get keywords
    keywords_input = get_input("Keywords")
    if keywords_input is None or not keywords_input.strip():
        print_info("Cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return

    keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
    if not keywords:
        print_error("No valid keywords provided.")
        get_input("\nPress Enter to return to main menu...")
        return

    print(f"\n{C.GREEN}✓{C.RESET} {len(keywords)} keyword(s) entered\n")

    # Choose search engine
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
    engine_choice = get_input(f"Choice", default_engine)
    if engine_choice is None:
        print_info("Cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return

    use_google = engine_choice in ('1', '3') and deps['google']
    use_duckduckgo = engine_choice in ('2', '3') and deps['duckduckgo']

    if not use_google and not use_duckduckgo:
        print_error("No search engine selected.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Max results per keyword
    max_results = get_input("Max results per keyword", "50")
    if max_results is None:
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
    print(f"""
{C.BRIGHT_GREEN}{'━' * 60}{C.RESET}
{C.GREEN}✓{C.RESET} Scraping complete!

  Keywords searched:     {len(keywords)}
  Unique domains found:  {len(domains)}
{C.BRIGHT_GREEN}{'━' * 60}{C.RESET}
""")

    if not domains:
        print_warning("No domains found. Try different keywords.")
        get_input("\nPress Enter to return to main menu...")
        return

    get_input("Press Enter to continue to results menu...")

    # Show results menu
    while True:
        result = show_scrape_results_menu(
            domains, keywords, use_google, use_duckduckgo, max_results
        )
        if result is None:
            # User chose to start fresh, restart the whole flow
            scrape_domains_menu()
            return
        else:
            break


def load_domains_menu():
    """Menu for loading domains from a file"""
    clear_screen()
    print_banner()
    print_section("Load Domains from File", C.BRIGHT_CYAN)

    try:
        from discovery.scraper import DomainScraper
    except ImportError as e:
        print_error(f"Discovery module not available: {e}")
        get_input("\nPress Enter to return to main menu...")
        return

    print(f"""
{C.WHITE}Load a list of domains from a text file.{C.RESET}
{C.DIM}File should contain one domain per line.{C.RESET}

{C.DIM}Example file format:{C.RESET}
  example1.com
  example2.com
  www.example3.com
  https://example4.com/page  {C.DIM}(URLs will be parsed){C.RESET}
""")

    # Get file path
    file_path = get_input("Enter path to file")
    if file_path is None or not file_path.strip():
        print_info("Cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return

    file_path = os.path.expanduser(file_path.strip())

    # Check file exists
    if not os.path.exists(file_path):
        print_error(f"File not found: {file_path}")
        get_input("\nPress Enter to return to main menu...")
        return

    if not os.path.isfile(file_path):
        print_error("That's not a file.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Load and validate
    print_section("Validating File", C.BRIGHT_MAGENTA)

    scraper = DomainScraper()
    valid_domains, invalid_lines = scraper.load_from_file(file_path)

    print(f"""
{C.GREEN}✓{C.RESET} File found: {os.path.basename(file_path)}

Parsing domains...
  • Valid domains:     {C.GREEN}{len(valid_domains)}{C.RESET}
  • Invalid/skipped:   {C.YELLOW}{len(invalid_lines)}{C.RESET}
""")

    # Show invalid lines (up to 5)
    if invalid_lines:
        print(f"{C.DIM}Invalid lines:{C.RESET}")
        for line_num, line, reason in invalid_lines[:5]:
            print(f"  {C.DIM}Line {line_num}: \"{line[:30]}...\" ({reason}){C.RESET}")
        if len(invalid_lines) > 5:
            print(f"  {C.DIM}... and {len(invalid_lines) - 5} more{C.RESET}")
        print()

    if not valid_domains:
        print_error("No valid domains found in file.")
        get_input("\nPress Enter to return to main menu...")
        return

    print_success(f"Loaded {len(valid_domains)} domains")

    # Offer to proceed to SpiderFoot scanning
    if confirm("\nProceed to SpiderFoot scanning?"):
        config = load_config()
        config['pending_domains'] = list(valid_domains)
        save_config(config)
        print_success(f"Loaded {len(valid_domains)} domains into scan queue.")
        print_info("Use option [3] Run SpiderFoot scans to start scanning.")

    get_input("\nPress Enter to return to main menu...")


def run_spiderfoot_scans_menu():
    """Menu for running SpiderFoot scans"""
    clear_screen()
    print_banner()
    print_section("Run SpiderFoot Scans", C.BRIGHT_CYAN)

    # Check if background scan is already running
    if is_background_scan_running():
        bg_stats = get_background_scan_stats()
        progress = bg_stats['completed'] + bg_stats['failed']
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
    if sf_path and os.path.exists(sf_path):
        print(f"  • SpiderFoot path:          {C.GREEN}{sf_path}{C.RESET}")
    else:
        print(f"  • SpiderFoot path:          {C.RED}Not configured{C.RESET}")
        sf_path = None

    # Check output directory
    sf_output = config.get('spiderfoot_output_dir', './spiderfoot_exports')
    print(f"  • Output directory:         {C.CYAN}{sf_output}{C.RESET}")
    print()

    if not pending_domains and existing_pending == 0:
        print_warning("No domains in queue.")
        print_info("Use option [1] or [2] to add domains first.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Configure SpiderFoot path if not set
    sf_python = config.get('spiderfoot_python')  # The venv python for SpiderFoot

    if not sf_path or not sf_python:
        print(f"\n{C.YELLOW}SpiderFoot not configured.{C.RESET}")

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

SpiderFoot is required to scan domains. Would you like to install it now?

{C.DIM}Source:{C.RESET}  {C.CYAN}https://github.com/smicallef/spiderfoot{C.RESET}
{C.DIM}Install:{C.RESET} Clone repo → Create venv → Install dependencies
{C.DIM}Location:{C.RESET} ./spiderfoot/ (in this project directory)
""")
            if confirm("Install SpiderFoot now?"):
                result = install_spiderfoot_interactive()
                if result:
                    # Reload config after install
                    config = load_config()
                    sf_path = config.get('spiderfoot_path')
                    sf_python = config.get('spiderfoot_python')
                    if not sf_path or not sf_python:
                        print_error("Installation completed but configuration not saved properly.")
                        get_input("\nPress Enter to return to main menu...")
                        return
                else:
                    print_error("SpiderFoot installation failed or was cancelled.")
                    get_input("\nPress Enter to return to main menu...")
                    return
            else:
                print_info("SpiderFoot is required to run scans.")
                print_info("You can install it anytime via Help [8] → Install SpiderFoot")
                get_input("\nPress Enter to return to main menu...")
                return

    # Verify SpiderFoot works with its venv python
    print_info("Verifying SpiderFoot installation...")
    try:
        result = subprocess.run(
            [sf_python, sf_path, "--help"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print_success("SpiderFoot is ready!")
        else:
            print_error("SpiderFoot verification failed:")
            print(f"{C.DIM}{result.stderr[:200]}{C.RESET}")
            if confirm("Would you like to reinstall SpiderFoot?"):
                install_spiderfoot_interactive()
                config = load_config()
                sf_path = config.get('spiderfoot_path')
                sf_python = config.get('spiderfoot_python')
            else:
                get_input("\nPress Enter to return to main menu...")
                return
    except Exception as e:
        print_error(f"SpiderFoot verification failed: {e}")
        if confirm("Would you like to reinstall SpiderFoot?"):
            install_spiderfoot_interactive()
            config = load_config()
            sf_path = config.get('spiderfoot_path')
            sf_python = config.get('spiderfoot_python')
        else:
            get_input("\nPress Enter to return to main menu...")
            return

    # Configure output directory
    print(f"\n{C.WHITE}Where should SpiderFoot save CSV exports?{C.RESET}")
    sf_output = get_input("Output directory", sf_output)
    if sf_output is None:
        print_info("Cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return

    sf_output = os.path.expanduser(sf_output)
    if not os.path.exists(sf_output):
        if confirm(f"Create directory {sf_output}?"):
            os.makedirs(sf_output)
        else:
            print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
            return

    config['spiderfoot_output_dir'] = sf_output
    save_config(config)

    # Add new domains to tracker
    if pending_domains:
        added = tracker.add_domains(pending_domains)
        print_success(f"Added {added} new domains to scan queue")
        # Clear pending domains from config
        config['pending_domains'] = []
        save_config(config)

    # Configure parallelism
    max_parallel = get_input("Max parallel scans", "3")
    if max_parallel is None:
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

        print_success("Scans started in background!")
        print_info("Returning to main menu. Use option [4] to check progress.")
        time.sleep(1.5)
        return

    # Run in foreground (choice == "2")
    print_section("Running SpiderFoot Scans", C.BRIGHT_MAGENTA)
    print(f"{C.DIM}Press Ctrl+C to pause and return to menu. Progress auto-saves.{C.RESET}\n")

    try:
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
        print_warning("\n\nScanning paused. Progress has been saved.")
        print_info("Use option [3] to resume, or [4] to check queue status.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Show results
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
        if confirm("Retry failed scans?"):
            tracker.retry_failed()
            print_info("Failed scans reset. Run this option again to retry.")

    if confirm("\nProceed to Puppet Analysis on these exports?"):
        # Remember the output dir for analysis
        remember_output_dir(sf_output)
        print_info("Use option [5] Run Puppet Analysis and point to this directory.")

    get_input("\nPress Enter to return to main menu...")


def check_scan_status_menu():
    """Show scan queue status"""
    clear_screen()
    print_banner()
    print_section("Scan Queue Status", C.BRIGHT_CYAN)

    try:
        from discovery.jobs import JobTracker
    except ImportError as e:
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
        print_info("No jobs in queue. Use option [1] or [2] to add domains.")
    else:
        # Show some details
        if stats['completed'] > 0:
            print(f"\n{C.WHITE}Completed Scans:{C.RESET}")
            for job in tracker.get_completed()[:5]:
                print(f"  {C.GREEN}✓{C.RESET} {job.domain}")
            if stats['completed'] > 5:
                print(f"  {C.DIM}... and {stats['completed'] - 5} more{C.RESET}")

        if stats['failed'] > 0:
            print(f"\n{C.WHITE}Failed Scans:{C.RESET}")
            for job in tracker.get_failed()[:5]:
                print(f"  {C.RED}✗{C.RESET} {job.domain}: {job.error[:40] if job.error else 'Unknown error'}")
            if stats['failed'] > 5:
                print(f"  {C.DIM}... and {stats['failed'] - 5} more{C.RESET}")

        if stats['pending'] > 0:
            print(f"\n{C.WHITE}Pending Scans:{C.RESET}")
            for job in tracker.get_pending()[:5]:
                print(f"  {C.CYAN}○{C.RESET} {job.domain}")
            if stats['pending'] > 5:
                print(f"  {C.DIM}... and {stats['pending'] - 5} more{C.RESET}")

    print()

    # Build options menu
    while True:
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
                    print(f"\n{C.CYAN}Watch mode active. Refreshing every 3s. Press Ctrl+C to stop.{C.RESET}")
                    try:
                        while is_background_scan_running():
                            time.sleep(3)
                            clear_screen()
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
                                print(f"{C.WHITE}Recent completions:{C.RESET}")
                                for job in reversed(completed_jobs):
                                    print(f"  {C.GREEN}✓{C.RESET} {job.domain}")

                        # Scan finished
                        print(f"\n{C.GREEN}Scan complete!{C.RESET}")
                        time.sleep(2)
                        check_scan_status_menu()
                        return

                    except KeyboardInterrupt:
                        print(f"\n{C.DIM}Watch mode stopped.{C.RESET}")
                        time.sleep(1)
                        check_scan_status_menu()
                        return

                elif action == 'retry':
                    count = tracker.retry_failed()
                    print_success(f"Reset {count} failed jobs for retry.")
                    stats = tracker.get_stats()  # Refresh stats

                elif action == 'clear_completed':
                    tracker.clear_completed()
                    print_success("Cleared completed jobs.")
                    stats = tracker.get_stats()  # Refresh stats

                elif action == 'clear_all':
                    if confirm("Are you sure? This cannot be undone.", default=False):
                        tracker.clear_all()
                        print_success("Cleared all jobs.")
                        stats = tracker.get_stats()  # Refresh stats

                elif action == 'back':
                    break
            else:
                print_error("Invalid option")
        except ValueError:
            if choice.lower() in ('q', 'quit', 'back', 'b'):
                break
            print_error("Please enter a number")


# =============================================================================
# ANALYSIS RUNNER
# =============================================================================
def run_analysis():
    """Run the full sock puppet detection analysis"""
    clear_screen()
    print_banner()

    # Get input directory
    input_dir = get_data_directory()
    if not input_dir:
        print_error("Analysis cancelled - no input directory provided.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Get output directory
    output_dir = get_output_directory()
    if not output_dir:
        print_error("Analysis cancelled - no output directory provided.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Confirmation
    print_section("Ready to Analyze", C.BRIGHT_GREEN)
    print(f"""
{C.WHITE}Analysis Configuration:{C.RESET}
  📂 Input:  {C.CYAN}{input_dir}{C.RESET}
  📁 Output: {C.CYAN}{output_dir}{C.RESET}
""")

    if not confirm("Start the analysis?"):
        print_info("Analysis cancelled.")
        get_input("\nPress Enter to return to main menu...")
        return

    # Run the pipeline
    print_section("Running Analysis", C.BRIGHT_MAGENTA)

    try:
        # Import and run the pipeline
        from core.pipeline import run_full_pipeline

        import random
        animated_print(f"\n{random.choice(HUNTING_MESSAGES)}\n", delay=0.02)

        success = run_full_pipeline(input_dir, output_dir)

        if success:
            print()
            print(f"{C.BRIGHT_GREEN}{'═' * 70}{C.RESET}")
            animated_print(f"{random.choice(COMPLETION_MESSAGES)}", delay=0.02)
            print(f"{C.BRIGHT_GREEN}{'═' * 70}{C.RESET}")
            print()
            print_info(f"Results saved to: {output_dir}")
            print_info(f"Start with: {os.path.join(output_dir, 'executive_summary.md')}")
        else:
            print_error("Analysis completed with errors. Check the output directory for details.")

    except ImportError as e:
        print_error(f"Failed to import pipeline modules: {e}")
        print_info("Make sure you're running from the correct directory.")
    except Exception as e:
        print_error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()

    get_input("\nPress Enter to return to main menu...")

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

    time.sleep(1)

    # Main menu loop
    while True:
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
            run_spiderfoot_scans_menu()
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
            launch_spiderfoot_gui()
        elif choice in ('q', 'quit', 'exit', ''):
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
