"""pm_help.py - Help & Documentation Screens"""

import os
import sys
import subprocess
import shlex
import time
from pathlib import Path

from pm_ui_helpers import (
    C, clear_screen, print_banner, print_section, print_menu_item,
    print_success, print_error, print_warning, print_info,
    get_input, confirm,
)

from pm_config import load_config, save_config

try:
    from ui.cyberpunk_ui import (
        cyber_header, cyber_info, cyber_success, cyber_warning,
        cyber_error, get_console, cyber_banner_help,
    )
    CYBER_UI_AVAILABLE = True
except ImportError:
    CYBER_UI_AVAILABLE = False


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
• Use the InfraAnalysis tool to see supportive clues, however these signals have more false positives
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
