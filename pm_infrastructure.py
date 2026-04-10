"""pm_infrastructure.py - System Infrastructure Tools (tmux, glances)"""

import os
import sys
import subprocess
import shutil
import time

from pm_ui_helpers import (
    C, clear_screen, print_banner, print_section,
    print_success, print_error, print_warning, print_info,
    get_input, confirm,
)
from pm_environment import get_existing_venv_python

try:
    from ui.cyberpunk_ui import (
        cyber_header, cyber_info, cyber_success, cyber_warning,
        cyber_error, cyber_confirm, get_console,
    )
    CYBER_UI_AVAILABLE = True
except ImportError:
    CYBER_UI_AVAILABLE = False


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

        print_info("Detecting OS and installing glances...yaaaaa boiiiii")

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
