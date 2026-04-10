"""
pm_environment.py - Dependency management and environment setup for PUPPETMASTER.

Handles Python version checks, pip availability, virtual environment creation,
package installation, and overall environment bootstrapping.

Extracted from puppetmaster.py for modularity.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

from pm_ui_helpers import (
    C, print_success, print_error, print_warning, print_info,
    confirm, print_section,
)

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
    try:
        os.execv(venv_python, [venv_python] + sys.argv)
    except OSError as e:
        print_error(f"Failed to restart in venv: {e}")
        print_info("Try manually: source venv/bin/activate && python puppetmaster.py")
        sys.exit(1)


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
