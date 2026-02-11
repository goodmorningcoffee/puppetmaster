"""
Kali Integration Module

Provides integration points for puppetmaster.py:
- Startup detection and bootstrap
- Enhanced menu options
- Mode selection UI
"""

import os
import sys
import re
from typing import Optional, Tuple, Callable


def validate_file_path(filepath: str, must_exist: bool = False, allow_write: bool = False) -> Optional[str]:
    """
    Validate a file path to prevent path traversal and other security issues.

    Args:
        filepath: The file path to validate
        must_exist: If True, file must exist
        allow_write: If True, allows paths in writable locations

    Returns:
        Validated absolute path, or None if invalid
    """
    if not filepath:
        return None

    filepath = filepath.strip()

    # Expand user home directory
    filepath = os.path.expanduser(filepath)

    # Get absolute normalized path
    filepath = os.path.abspath(os.path.normpath(filepath))

    # Check for path traversal attempts
    if '..' in filepath:
        return None

    # Don't allow absolute paths to sensitive locations
    sensitive_paths = ['/etc/', '/usr/', '/bin/', '/sbin/', '/root/', '/var/']
    for sensitive in sensitive_paths:
        if filepath.startswith(sensitive):
            return None

    # Check existence if required
    if must_exist and not os.path.exists(filepath):
        return None

    return filepath


def get_optimal_parallelism() -> Tuple[int, dict]:
    """
    Auto-detect system resources and calculate optimal parallelism.

    Returns:
        Tuple of (recommended_parallelism, stats_dict)
    """
    stats = {
        'cpu_cores': 1,
        'ram_total_gb': 4,
        'ram_available_gb': 2,
        'ram_percent_free': 50,
    }

    try:
        # Try psutil first (more accurate)
        import psutil
        stats['cpu_cores'] = psutil.cpu_count(logical=True) or 1
        mem = psutil.virtual_memory()
        stats['ram_total_gb'] = round(mem.total / (1024**3), 1)
        stats['ram_available_gb'] = round(mem.available / (1024**3), 1)
        stats['ram_percent_free'] = round(100 - mem.percent, 1)
    except ImportError:
        # Fallback to os module
        try:
            stats['cpu_cores'] = os.cpu_count() or 1
            # Try reading /proc/meminfo on Linux
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                for line in meminfo.split('\n'):
                    parts = line.split()
                    if len(parts) >= 2:
                        if line.startswith('MemTotal:'):
                            stats['ram_total_gb'] = round(int(parts[1]) / (1024**2), 1)
                        elif line.startswith('MemAvailable:'):
                            stats['ram_available_gb'] = round(int(parts[1]) / (1024**2), 1)
                if stats['ram_total_gb'] > 0:
                    stats['ram_percent_free'] = round(
                        (stats['ram_available_gb'] / stats['ram_total_gb']) * 100, 1
                    )
        except Exception:
            pass  # Use defaults if /proc/meminfo unavailable

    # Calculate optimal parallelism
    # Rule: ~1.5-2GB RAM per parallel domain (amass is hungry)
    # But cap based on practical network/rate-limit constraints

    ram_based = int(stats['ram_available_gb'] / 1.5)  # Conservative RAM estimate
    cpu_based = stats['cpu_cores'] * 4  # CPU rarely the bottleneck

    # Take the lower of RAM-based and CPU-based
    calculated = min(ram_based, cpu_based)

    # Apply practical bounds
    # Min: 3 (always have some parallelism)
    # Max: 50 (beyond this, rate limiting becomes severe)
    optimal = max(3, min(calculated, 50))

    stats['calculated'] = optimal
    stats['ram_based_max'] = ram_based
    stats['cpu_based_max'] = cpu_based

    return optimal, stats

from .detect import detect_os, get_os_info, print_os_banner, OSInfo
from .bootstrap import bootstrap_kali_tools, check_kali_tools, print_tool_status
from .registry import get_registry, ToolRegistry
from .modes import ScanMode, get_mode_config, select_scan_mode, print_mode_details, get_mode_coverage
from .aggregator import DiscoveryAggregator, run_discovery, AggregatedResult

# Import blacklist module
try:
    from core.blacklist import (
        filter_domains, is_blacklisted, get_full_blacklist,
        add_to_blacklist, remove_from_blacklist, get_blacklist_stats,
        format_blacklist_summary, export_blacklist, import_blacklist,
        reset_user_blacklist
    )
    _blacklist_available = True
except ImportError:
    _blacklist_available = False


# Global state
_kali_mode_enabled = False
_current_scan_mode = ScanMode.STANDARD


def is_enhanced_mode() -> bool:
    """Check if enhanced Kali mode is enabled"""
    return _kali_mode_enabled


def get_current_mode() -> ScanMode:
    """Get current scan mode"""
    return _current_scan_mode


def set_current_mode(mode: ScanMode):
    """Set current scan mode"""
    global _current_scan_mode
    _current_scan_mode = mode


def kali_startup_check(print_func: Callable = print) -> Tuple[bool, OSInfo]:
    """
    Run Kali detection and bootstrap at startup.

    Args:
        print_func: Function to use for printing (for integration with display utils)

    Returns:
        Tuple of (is_kali, os_info)
    """
    global _kali_mode_enabled

    os_info = detect_os()

    # Print OS detection banner
    banner = print_os_banner(os_info)
    print_func(banner)

    if os_info.is_kali:
        # Auto-install Kali tools
        print_func("\n  Checking Kali tools...")

        installed, missing = check_kali_tools()

        if missing:
            print_func(f"\n  {len(missing)} tools need to be installed.")
            print_func("  Installing automatically...\n")

            success = bootstrap_kali_tools(verbose=True)

            if success:
                print_func("\n\033[92m  All Kali tools ready!\033[0m")
                _kali_mode_enabled = True
            else:
                print_func("\n\033[93m  Some tools failed to install. Enhanced mode may be limited.\033[0m")
                _kali_mode_enabled = True  # Still enable, just with fewer tools
        else:
            print_func(f"\n\033[92m  All {len(installed)} Kali tools already installed!\033[0m")
            _kali_mode_enabled = True

        # Show tool status
        print_func(print_tool_status())

    else:
        # Not Kali - proceed with standard mode
        _kali_mode_enabled = False

    return os_info.is_kali, os_info


def get_enhanced_menu_items() -> list:
    """
    Get additional menu items for enhanced Kali mode.

    Returns list of tuples: (key, label, icon)
    """
    if not _kali_mode_enabled:
        return []

    mode = get_current_mode()
    coverage = get_mode_coverage(mode)

    items = [
        ('k1', f'Enhanced Discovery ({mode.value} mode)', '🔬'),
        ('k2', f'Change Scan Mode (current: {mode.value})', '⚙️'),
        ('k3', 'View Kali Tool Status', '🛠️'),
    ]

    # k4 available even without full Kali mode (blacklist is OS-agnostic)
    if _blacklist_available:
        stats = get_blacklist_stats()
        items.append(('k4', f'Manage Blacklist ({stats["total_count"]} domains)', '🚫'))

    # k5 Infrastructure Analysis
    items.append(('k5', 'Infrastructure Correlation Analysis', '🔗'))

    return items


def print_enhanced_menu(print_func: Callable = print, colors=None):
    """
    Print the enhanced Kali menu section.

    Args:
        print_func: Print function
        colors: Color class (C from puppetmaster)
    """
    if not _kali_mode_enabled:
        return

    if colors is None:
        # Fallback colors
        class C:
            BRIGHT_RED = "\033[91m"
            BRIGHT_GREEN = "\033[92m"
            BRIGHT_YELLOW = "\033[93m"
            BRIGHT_CYAN = "\033[96m"
            WHITE = "\033[97m"
            DIM = "\033[2m"
            RESET = "\033[0m"
        colors = C

    mode = get_current_mode()
    config = get_mode_config(mode)
    coverage = get_mode_coverage(mode)

    print_func(f"\n  {colors.BRIGHT_RED}KALI ENHANCED MODE{colors.RESET}")
    print_func(f"  {colors.DIM}Mode: {config.name} | Tools: {coverage['available_tools']}/{coverage['total_tools']}{colors.RESET}")
    print_func(f"  {colors.DIM}Note: Option [1] now auto-expands with Kali tools!{colors.RESET}")
    print_func(f"  {colors.BRIGHT_CYAN}[k1]{colors.RESET} Enumerate single domain (subdomains/infra)")
    print_func(f"  {colors.BRIGHT_CYAN}[k2]{colors.RESET} Change Scan Mode")
    print_func(f"  {colors.BRIGHT_CYAN}[k3]{colors.RESET} View Kali Tool Status")
    if _blacklist_available:
        stats = get_blacklist_stats()
        print_func(f"  {colors.BRIGHT_CYAN}[k4]{colors.RESET} Manage Domain Blacklist ({stats['total_count']} domains)")
    print_func(f"  {colors.BRIGHT_CYAN}[k5]{colors.RESET} Infrastructure Correlation Analysis")
    print_func("")


def handle_enhanced_menu_choice(choice: str, print_func: Callable = print,
                                 get_input_func: Callable = input,
                                 clear_func: Callable = None,
                                 colors=None) -> bool:
    """
    Handle enhanced menu choices.

    Args:
        choice: Menu choice (k1, k2, k3)
        print_func: Print function
        get_input_func: Input function
        clear_func: Clear screen function
        colors: Color class

    Returns:
        True if choice was handled, False otherwise
    """
    if not _kali_mode_enabled:
        return False

    if colors is None:
        class C:
            BRIGHT_GREEN = "\033[92m"
            BRIGHT_YELLOW = "\033[93m"
            RESET = "\033[0m"
        colors = C

    if choice == 'k1':
        # Enhanced discovery
        run_enhanced_discovery_menu(print_func, get_input_func, clear_func, colors)
        return True

    elif choice == 'k2':
        # Change scan mode
        run_mode_selection_menu(print_func, get_input_func, clear_func, colors)
        return True

    elif choice == 'k3':
        # View tool status
        if clear_func:
            clear_func()
        print_func(print_tool_status())
        get_input_func("\nPress Enter to continue...")
        return True

    elif choice == 'k4':
        # Blacklist management
        if _blacklist_available:
            run_blacklist_management_menu(print_func, get_input_func, clear_func, colors)
            return True
        else:
            print_func("\n  Blacklist module not available.")
            return True

    elif choice == 'k5':
        # Infrastructure correlation analysis
        run_infra_analysis_menu(print_func, get_input_func, clear_func, colors)
        return True

    return False


def run_mode_selection_menu(print_func: Callable = print,
                            get_input_func: Callable = input,
                            clear_func: Callable = None,
                            colors=None):
    """Run the scan mode selection menu"""
    global _current_scan_mode

    if clear_func:
        clear_func()

    print_func(select_scan_mode(_current_scan_mode))

    print_func("\n  [1] Ghost - Passive only, zero target contact")
    print_func("  [2] Stealth - Light touch, 1-2 requests per domain")
    print_func("  [3] Standard - Balanced reconnaissance (default)")
    print_func("  [4] Deep - Maximum coverage, high noise")
    print_func("  [q] Cancel\n")

    choice = get_input_func("Select mode: ")

    mode_map = {
        '1': ScanMode.GHOST,
        '2': ScanMode.STEALTH,
        '3': ScanMode.STANDARD,
        '4': ScanMode.DEEP,
    }

    if choice in mode_map:
        _current_scan_mode = mode_map[choice]
        print_func(f"\n\033[92m  Mode set to: {_current_scan_mode.value.upper()}\033[0m")
        print_func(print_mode_details(_current_scan_mode))

    get_input_func("\nPress Enter to continue...")


def run_blacklist_management_menu(print_func: Callable = print,
                                   get_input_func: Callable = input,
                                   clear_func: Callable = None,
                                   colors=None):
    """Run the blacklist management menu"""
    if not _blacklist_available:
        print_func("\n  Blacklist module not available.")
        return

    while True:
        if clear_func:
            clear_func()

        stats = get_blacklist_stats()

        print_func(f"""
\033[93m{'━' * 60}\033[0m
\033[1m  DOMAIN BLACKLIST MANAGEMENT\033[0m
\033[93m{'━' * 60}\033[0m

  \033[36mBuilt-in domains:\033[0m  {stats['builtin_count']}
  \033[36mCustom additions:\033[0m  {stats['user_count']}
  \033[36mTotal blacklisted:\033[0m {stats['total_count']}

  \033[90mBlacklisted domains are automatically skipped during Kali
  expansion to reduce noise from platform/hosting domains.\033[0m

  [1] View all blacklisted domains
  [2] Add domain to blacklist
  [3] Remove domain from blacklist (custom only)
  [4] View custom additions
  [5] Export blacklist to file
  [6] Import blacklist from file
  [7] Reset custom blacklist
  [q] Back to main menu
""")

        _flush_stdin()
        choice = get_input_func("Choice: ")

        if choice == 'q' or choice == '':
            break

        elif choice == '1':
            # View all blacklisted
            blacklist = get_full_blacklist()
            print_func(f"\n  \033[36mAll blacklisted domains ({len(blacklist)}):\033[0m\n")

            # Group by category for display
            sorted_domains = sorted(blacklist)
            for i, domain in enumerate(sorted_domains):
                if i > 0 and i % 20 == 0:
                    _flush_stdin()
                    cont = get_input_func("\n  Press Enter for more (q to stop): ")
                    if cont.lower() == 'q':
                        break
                print_func(f"    {domain}")

            _flush_stdin()
            get_input_func("\n  Press Enter to continue...")

        elif choice == '2':
            # Add domain
            print_func("\n  Enter domain to add (e.g., example.com):")
            _flush_stdin()
            domain = get_input_func("  Domain: ").strip().lower()

            if domain:
                if is_blacklisted(domain):
                    print_func(f"\n  \033[93m'{domain}' is already blacklisted.\033[0m")
                else:
                    if add_to_blacklist(domain, persistent=True):
                        print_func(f"\n  \033[92m✓ Added '{domain}' to blacklist.\033[0m")
                    else:
                        print_func(f"\n  \033[91mFailed to add '{domain}'.\033[0m")

            _flush_stdin()
            get_input_func("\n  Press Enter to continue...")

        elif choice == '3':
            # Remove domain
            print_func("\n  Enter domain to remove (custom only):")
            print_func("  \033[90mNote: Cannot remove built-in domains.\033[0m\n")
            _flush_stdin()
            domain = get_input_func("  Domain: ").strip().lower()

            if domain:
                if remove_from_blacklist(domain):
                    print_func(f"\n  \033[92m✓ Removed '{domain}' from blacklist.\033[0m")
                else:
                    print_func(f"\n  \033[91mCannot remove '{domain}' (not found or is built-in).\033[0m")

            _flush_stdin()
            get_input_func("\n  Press Enter to continue...")

        elif choice == '4':
            # View custom additions
            stats = get_blacklist_stats()
            user_domains = stats.get('user_domains', [])

            if user_domains:
                print_func(f"\n  \033[36mCustom blacklist additions ({len(user_domains)}):\033[0m\n")
                for domain in user_domains:
                    print_func(f"    {domain}")
            else:
                print_func("\n  \033[90mNo custom additions.\033[0m")

            _flush_stdin()
            get_input_func("\n  Press Enter to continue...")

        elif choice == '5':
            # Export
            print_func("\n  Enter export file path:")
            _flush_stdin()
            raw_filepath = get_input_func("  Path [./blacklist_export.txt]: ") or "./blacklist_export.txt"

            # Validate file path to prevent path traversal
            filepath = validate_file_path(raw_filepath, must_exist=False)
            if not filepath:
                print_func(f"\n  \033[91mInvalid file path: {raw_filepath}\033[0m")
            elif export_blacklist(filepath):
                print_func(f"\n  \033[92m✓ Exported blacklist to {filepath}\033[0m")
            else:
                print_func(f"\n  \033[91mFailed to export blacklist.\033[0m")

            _flush_stdin()
            get_input_func("\n  Press Enter to continue...")

        elif choice == '6':
            # Import
            print_func("\n  Enter file path to import:")
            _flush_stdin()
            raw_filepath = get_input_func("  Path: ").strip()

            # Validate file path to prevent path traversal
            filepath = validate_file_path(raw_filepath, must_exist=True)
            if not filepath:
                print_func(f"\n  \033[91mInvalid or non-existent file: {raw_filepath}\033[0m")
            else:
                added, skipped = import_blacklist(filepath)
                print_func(f"\n  \033[92m✓ Imported: {added} new, {skipped} already existed.\033[0m")

            _flush_stdin()
            get_input_func("\n  Press Enter to continue...")

        elif choice == '7':
            # Reset
            print_func("\n  \033[91mThis will remove ALL custom blacklist additions.\033[0m")
            print_func("  Built-in domains will remain.")
            _flush_stdin()
            confirm = get_input_func("\n  Type 'RESET' to confirm: ")

            if confirm == 'RESET':
                if reset_user_blacklist():
                    print_func("\n  \033[92m✓ Custom blacklist reset.\033[0m")
                else:
                    print_func("\n  \033[91mFailed to reset blacklist.\033[0m")
            else:
                print_func("\n  Cancelled.")

            _flush_stdin()
            get_input_func("\n  Press Enter to continue...")


def run_infra_analysis_menu(print_func: Callable = print,
                            get_input_func: Callable = input,
                            clear_func: Callable = None,
                            colors=None):
    """Run the infrastructure correlation analysis menu"""
    from .infra_analyzer import InfrastructureAnalyzer, run_infra_analysis

    # Import cyberpunk visuals
    try:
        from core.visuals import C, box, hline, menu_option, prompt, status, result_banner
        has_visuals = True
    except ImportError:
        has_visuals = False
        class C:
            NEON_CYAN = '\033[96m'
            NEON_PINK = '\033[95m'
            NEON_GREEN = '\033[92m'
            NEON_ORANGE = '\033[93m'
            NEON_RED = '\033[91m'
            NEON_PURPLE = '\033[35m'
            WHITE = '\033[97m'
            DARK_GRAY = '\033[90m'
            DIM = '\033[2m'
            BOLD = '\033[1m'
            RESET = '\033[0m'

    if clear_func:
        clear_func()

    mode = get_current_mode()
    cfg = get_mode_config(mode)

    # Cyberpunk banner
    print_func(f"""
{C.NEON_CYAN}╔══════════════════════════════════════════════════════════╗
║{C.RESET} {C.BOLD}INFRA{C.RESET} {C.DIM}// Infrastructure Correlation Analysis{C.RESET}        {C.NEON_CYAN}║
╚══════════════════════════════════════════════════════════╝{C.RESET}

  {C.NEON_CYAN}What this does:{C.RESET}
  {C.WHITE}Analyzes infrastructure patterns across multiple domains{C.RESET}
  {C.WHITE}to find hidden connections indicating common ownership.{C.RESET}

  {C.NEON_PURPLE}Signals Detected:{C.RESET}
  {C.DIM}•{C.RESET} Shared IPs / ASNs / subnets
  {C.DIM}•{C.RESET} Shared nameservers / mail servers
  {C.DIM}•{C.RESET} Shared SSL certificates / organizations
  {C.DIM}•{C.RESET} Shared technology stacks
  {C.DIM}•{C.RESET} Shared emails / document authors

  {C.DARK_GRAY}Note: Different from [5] Puppet Analysis.{C.RESET}
  {C.DARK_GRAY}[5] = identifier sharing (GA/AdSense){C.RESET}
  {C.DARK_GRAY}[k5] = infrastructure sharing (IPs/NS/SSL){C.RESET}

{C.NEON_CYAN}{'═' * 60}{C.RESET}
  {C.BOLD}Current Mode: {cfg.name}{C.RESET}
{C.DARK_GRAY}{'─' * 60}{C.RESET}

  {C.NEON_CYAN}[1]{C.RESET} {C.WHITE}Analyze domains from file{C.RESET}
  {C.NEON_CYAN}[2]{C.RESET} {C.WHITE}Enter domains manually{C.RESET}
  {C.NEON_CYAN}[3]{C.RESET} {C.WHITE}Use domains from config/last analysis{C.RESET}
  {C.NEON_CYAN}[q]{C.RESET} {C.WHITE}Cancel{C.RESET}
""")

    _flush_stdin()
    choice = get_input_func(f"{C.NEON_PINK}>{C.RESET} Choice [1]: ") or "1"

    if choice == 'q':
        return

    domains = []

    if choice == '1':
        # From file
        print_func(f"\n  {C.NEON_CYAN}[i]{C.RESET} Enter path to domains file")
        print_func(f"  {C.DARK_GRAY}Format: one domain per line, # for comments{C.RESET}")
        _flush_stdin()
        raw_filepath = get_input_func(f"\n  {C.NEON_PINK}>{C.RESET} Path: ").strip()

        # Validate file path to prevent path traversal
        filepath = validate_file_path(raw_filepath, must_exist=True)
        if not filepath:
            print_func(f"\n  {C.NEON_RED}[✗]{C.RESET} Invalid or non-existent file: {raw_filepath}")
            get_input_func(f"\n  {C.DIM}Press Enter...{C.RESET}")
            return

        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip().lower()
                    if line and not line.startswith('#'):
                        domains.append(line)
            print_func(f"  {C.NEON_GREEN}[✓]{C.RESET} Loaded {len(domains)} domains")
        except Exception as e:
            print_func(f"\n  {C.NEON_RED}[✗]{C.RESET} Error reading file: {e}")
            get_input_func(f"\n  {C.DIM}Press Enter...{C.RESET}")
            return

    elif choice == '2':
        # Manual entry
        print_func(f"\n  {C.NEON_CYAN}[i]{C.RESET} Enter domains (one per line, empty line when done)")
        print_func("")
        while True:
            _flush_stdin()
            line = get_input_func(f"  {C.NEON_CYAN}>{C.RESET} ").strip().lower()
            if line == '' or line == 'done':
                if domains:
                    break
                print_func(f"  {C.DARK_GRAY}Enter at least one domain{C.RESET}")
                continue
            if line == 'q':
                return

            # Handle comma-separated
            for d in line.split(','):
                d = d.strip()
                if d:
                    domains.append(d)

    elif choice == '3':
        # Use domains from config
        config_file = ".puppetmaster_config.json"
        if os.path.exists(config_file):
            try:
                import json
                with open(config_file, 'r') as f:
                    cfg_data = json.load(f)
                domains = cfg_data.get('pending_domains', [])
                if not domains:
                    domains = cfg_data.get('last_analyzed_domains', [])
            except Exception:
                pass

        if not domains:
            print_func(f"\n  {C.NEON_ORANGE}[!]{C.RESET} No domains found in config. Use option [1] or [2].")
            get_input_func(f"\n  {C.DIM}Press Enter...{C.RESET}")
            return

    # Deduplicate
    domains = list(dict.fromkeys(domains))

    if not domains:
        print_func(f"\n  {C.NEON_RED}[✗]{C.RESET} No domains to analyze.")
        get_input_func(f"\n  {C.DIM}Press Enter...{C.RESET}")
        return

    # Show targets
    print_func(f"\n{C.DARK_GRAY}{'─' * 55}{C.RESET}")
    print_func(f"  {C.BOLD}TARGETS: {len(domains)} domains{C.RESET}")
    print_func(f"{C.DARK_GRAY}{'─' * 55}{C.RESET}")
    for d in domains[:8]:
        print_func(f"  {C.NEON_CYAN}│{C.RESET} {d}")
    if len(domains) > 8:
        print_func(f"  {C.DARK_GRAY}│ ... +{len(domains) - 8} more{C.RESET}")

    print_func(f"\n  Mode: {C.WHITE}{mode.value}{C.RESET}")
    print_func(f"  {C.DARK_GRAY}Estimated time: ~{len(domains) * 30}-{len(domains) * 60}s{C.RESET}")

    # Get output directory first
    print_func("")
    _flush_stdin()
    output_dir = get_input_func(f"  {C.NEON_PINK}>{C.RESET} Output dir [./infra_analysis]: ") or "./infra_analysis"

    # Confirm box
    print_func(f"""
{C.NEON_ORANGE}{'═' * 55}{C.RESET}
  {C.BOLD}{C.NEON_ORANGE}CONFIRM SCAN{C.RESET}
{C.DARK_GRAY}{'─' * 55}{C.RESET}
  Targets:  {C.WHITE}{len(domains)} domains{C.RESET}
  Mode:     {C.WHITE}{mode.value}{C.RESET}
  Output:   {C.WHITE}{output_dir}{C.RESET}
{C.NEON_ORANGE}{'═' * 55}{C.RESET}
""")

    _flush_stdin()
    confirm = get_input_func(f"  {C.NEON_PINK}>{C.RESET} Execute? [Y/n]: ") or "y"
    if confirm.lower() == 'n':
        print_func(f"  {C.NEON_ORANGE}[!]{C.RESET} Scan cancelled")
        return

    # Run analysis header
    print_func(f"""
{C.NEON_CYAN}╔{'═'*55}╗{C.RESET}
{C.NEON_CYAN}║{C.RESET} {C.BOLD}EXECUTING INFRASTRUCTURE SCAN{C.RESET}                       {C.NEON_CYAN}║{C.RESET}
{C.NEON_CYAN}╚{'═'*55}╝{C.RESET}
""")

    def progress_callback(domain, pstatus, message):
        status_colors = {
            'starting': C.NEON_PURPLE,
            'scanning': C.NEON_CYAN,
            'complete': C.NEON_GREEN,
            'correlating': C.NEON_PINK,
            'error': C.NEON_RED,
        }
        color = status_colors.get(pstatus, C.WHITE)
        icon = '◆' if pstatus == 'complete' else '○' if pstatus == 'scanning' else '●'
        print_func(f"  {color}{icon}{C.RESET} {C.DIM}[{pstatus:11}]{C.RESET} {domain}: {message}")

    try:
        result = run_infra_analysis(
            domains=domains,
            mode=mode,
            output_dir=output_dir,
            progress_callback=progress_callback
        )
    except Exception as e:
        print_func(f"\n  {C.NEON_RED}[✗]{C.RESET} Error during analysis: {e}")
        get_input_func(f"\n  {C.DIM}Press Enter...{C.RESET}")
        return

    # Results banner
    print_func(f"""
{C.NEON_GREEN}╔{'═'*55}╗{C.RESET}
{C.NEON_GREEN}║{C.RESET} {C.BOLD}SCAN COMPLETE{C.RESET}                                       {C.NEON_GREEN}║{C.RESET}
{C.NEON_GREEN}╚{'═'*55}╝{C.RESET}
""")

    print_func(f"  {C.NEON_CYAN}Statistics:{C.RESET}")
    print_func(f"    Domains scanned:    {result.domains_scanned}")
    print_func(f"    Domains failed:     {result.domains_failed}")
    print_func(f"    Correlations found: {C.BOLD}{C.NEON_GREEN}{result.total_correlations}{C.RESET}")

    # Show clusters
    clusters = result.get_domain_clusters(min_score=0.5)
    if clusters:
        print_func(f"\n  {C.NEON_ORANGE}Domain Clusters:{C.RESET}")
        for i, cluster in enumerate(clusters[:5], 1):
            print_func(f"    {C.NEON_CYAN}[{i}]{C.RESET} {', '.join(sorted(cluster))}")
        if len(clusters) > 5:
            print_func(f"    {C.DARK_GRAY}... and {len(clusters) - 5} more clusters{C.RESET}")

    # Correlation breakdown
    if result.correlations:
        print_func(f"\n  {C.NEON_PURPLE}Correlations by type:{C.RESET}")
        from collections import Counter
        type_counts = Counter(c.signal_type for c in result.correlations)
        for sig_type, count in type_counts.most_common(5):
            bar = '█' * min(count, 20)
            print_func(f"    {sig_type:25} {C.NEON_CYAN}{bar}{C.RESET} {count}")

    print_func(f"\n  {C.NEON_GREEN}[✓]{C.RESET} Reports saved to: {output_dir}/")

    if result.errors:
        print_func(f"\n  {C.NEON_ORANGE}Warnings:{C.RESET}")
        for error in result.errors[:3]:
            print_func(f"    {C.DIM}•{C.RESET} {error}")

    get_input_func(f"\n  {C.DIM}Press Enter to continue...{C.RESET}")


def run_enhanced_discovery_menu(print_func: Callable = print,
                                 get_input_func: Callable = input,
                                 clear_func: Callable = None,
                                 colors=None) -> Optional[AggregatedResult]:
    """
    Run the enhanced discovery menu.

    Returns:
        AggregatedResult or None if cancelled
    """
    if clear_func:
        clear_func()

    mode = get_current_mode()
    config = get_mode_config(mode)

    print_func(f"""
\033[1m  KALI DOMAIN ENUMERATION - {config.name}\033[0m
  {config.description}
  Target Contact: {config.target_contact} | Detection Risk: {config.detection_risk}

  \033[36mWhat this does:\033[0m
  Enumerates subdomains and related infrastructure for a domain
  using Kali tools (amass, sublist3r, theHarvester, etc.)

  \033[93mFor keyword-based discovery:\033[0m Use Option [1] from main menu.
  It now auto-expands with Kali tools after Google/DDG scraping.

  \033[36mThis option is for:\033[0m
  • Expanding a single known domain
  • Deep enumeration of a specific target
""")

    # Get target domain
    target = get_input_func("Enter target domain (e.g., example.com) or 'q' to cancel: ")
    if not target or target.lower() == 'q':
        print_func("  Cancelled.")
        return None

    target = target.strip().lower()

    # Confirm mode
    print_func(f"\n  Target: {target}")
    print_func(f"  Mode: {mode.value}")
    coverage = get_mode_coverage(mode)
    print_func(f"  Tools: {coverage['available_list']}\n")

    confirm = get_input_func("Proceed? [Y/n]: ")
    if confirm.lower() == 'n':
        print_func("  Cancelled.")
        return None

    # Run discovery
    print_func("\n  Starting enhanced discovery...\n")

    def progress_callback(tool, status, message):
        status_colors = {
            'running': '\033[93m',
            'success': '\033[92m',
            'error': '\033[91m',
            'complete': '\033[96m',
        }
        color = status_colors.get(status, '')
        print_func(f"  {color}[{status.upper():8}]\033[0m {tool}: {message}")

    result = run_discovery(
        target=target,
        mode=mode,
        progress_callback=progress_callback
    )

    # Show results
    print_func(f"\n\033[92m  {'━' * 50}\033[0m")
    print_func(f"  \033[92mDiscovery Complete!\033[0m")
    print_func(f"  {'━' * 50}")
    print_func(f"  Domains found: {len(result.domains)}")
    print_func(f"  Subdomains found: {len(result.subdomains)}")
    print_func(f"  Emails found: {len(result.emails)}")
    print_func(f"  IPs found: {len(result.ips)}")
    print_func(f"  Tools succeeded: {result.tools_succeeded}/{result.tools_run}")

    if result.errors:
        print_func(f"\n  Errors:")
        for error in result.errors[:5]:
            print_func(f"    - {error}")

    # Save options
    print_func("\n  Save options:")
    print_func("  [1] Add to SpiderFoot scan queue (recommended)")
    print_func("  [2] Save to file only")
    print_func("  [3] Both (queue + file)")
    print_func("  [q] Skip saving\n")

    save_choice = get_input_func("Choice [1]: ") or "1"

    if save_choice in ('1', '2', '3'):
        aggregator = DiscoveryAggregator(mode=mode)

        # Option 1 or 3: Add to SpiderFoot pending_domains queue
        if save_choice in ('1', '3'):
            added_to_queue = _add_to_pending_domains(result, print_func)
            if added_to_queue > 0:
                print_func(f"\n  \033[92m✓\033[0m Added {added_to_queue} domains to SpiderFoot scan queue")
                print_func(f"    \033[90mRun option [3] from main menu to start SpiderFoot scans.\033[0m")
            else:
                print_func(f"\n  \033[93m⚠\033[0m No new domains added to queue (may already exist)")

        # Option 2 or 3: Save to file
        if save_choice in ('2', '3'):
            output_dir = get_input_func("Output directory [./kali_discovery]: ") or "./kali_discovery"
            import os
            os.makedirs(output_dir, exist_ok=True)
            domains_file = os.path.join(output_dir, 'domains.txt')
            count = aggregator.save_domains(result, domains_file)
            print_func(f"\n  \033[92m✓\033[0m Saved {count} domains to {domains_file}")

            # Also save full report
            _flush_stdin()
            save_report = get_input_func("  Save full report too? [y/N]: ") or "n"
            if save_report.lower() == 'y':
                files = aggregator.save_full_report(result, output_dir)
                print_func(f"  \033[92m✓\033[0m Saved full report:")
                for name, path in files.items():
                    print_func(f"      - {name}: {path}")

    get_input_func("\nPress Enter to continue...")
    return result


# Convenience functions for puppetmaster.py integration
def should_show_kali_menu() -> bool:
    """Check if Kali menu should be displayed"""
    return _kali_mode_enabled


def get_kali_status_line() -> str:
    """Get status line for Kali mode"""
    if not _kali_mode_enabled:
        return ""

    mode = get_current_mode()
    coverage = get_mode_coverage(mode)

    return f"KALI MODE: {mode.value.upper()} ({coverage['available_tools']} tools)"


def _flush_stdin():
    """Flush any buffered stdin to prevent auto-accepting prompts"""
    try:
        import sys
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass  # Not a TTY or termios not available


# Config file path for puppetmaster
CONFIG_FILE = ".puppetmaster_config.json"


def _add_to_pending_domains(result: AggregatedResult, print_func: Callable = print) -> int:
    """
    Add discovered domains to the pending_domains queue in config.

    Args:
        result: AggregatedResult from discovery
        print_func: Print function

    Returns:
        Number of new domains added
    """
    import json

    # Collect all domains from result
    new_domains = set()
    new_domains.update(result.domains)
    new_domains.update(result.subdomains)

    if not new_domains:
        return 0

    # Load existing config
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except Exception:
            pass

    # Get existing pending domains
    existing_pending = set(config.get('pending_domains', []))
    original_count = len(existing_pending)

    # Add new domains (deduplicated)
    combined = existing_pending | new_domains

    # Filter out blacklisted domains if available
    if _blacklist_available:
        clean, blocked = filter_domains(combined)
        if blocked:
            print_func(f"    \033[90mFiltered {len(blocked)} blacklisted domains\033[0m")
        combined = clean

    # Update config
    config['pending_domains'] = list(combined)

    # Save config
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print_func(f"    \033[91mError saving config: {e}\033[0m")
        return 0

    return len(combined) - original_count


def kali_expand_domains(seed_domains: set, print_func: Callable = print,
                         get_input_func: Callable = input,
                         max_domains: int = 20) -> set:
    """
    Expand seed domains using Kali tools.

    This is called after Google/DDG scraping to enumerate subdomains
    and related infrastructure for each discovered domain.

    Args:
        seed_domains: Set of domains from keyword scraping
        print_func: Print function
        get_input_func: Input function
        max_domains: Max domains to expand (to avoid long waits)

    Returns:
        Expanded set of domains (original + discovered)
    """
    if not _kali_mode_enabled:
        return seed_domains

    # Flush any buffered input from scraping phase
    _flush_stdin()

    mode = get_current_mode()
    config = get_mode_config(mode)
    coverage = get_mode_coverage(mode)

    # =========================================================================
    # PRE-EXPANSION BLACKLIST REVIEW
    # =========================================================================
    clean_domains = seed_domains
    blacklisted_domains = set()

    if _blacklist_available:
        clean_domains, blacklisted_domains = filter_domains(seed_domains)

    total_seeds = len(seed_domains)
    clean_count = len(clean_domains)
    blacklisted_count = len(blacklisted_domains)

    print_func(f"""
\033[93m{'━' * 60}\033[0m
\033[1m  SEED DOMAIN REVIEW\033[0m
\033[93m{'━' * 60}\033[0m
""")

    if blacklisted_count > 0 and _blacklist_available:
        print_func(f"  \033[91m⛔ BLACKLISTED:\033[0m {blacklisted_count} domains (will skip)")
        # Show up to 5 blacklisted domains
        blacklisted_list = sorted(blacklisted_domains)
        for d in blacklisted_list[:5]:
            print_func(f"     \033[90m• {d}\033[0m")
        if blacklisted_count > 5:
            print_func(f"     \033[90m... and {blacklisted_count - 5} more\033[0m")
        print_func("")

    print_func(f"  \033[92m✓  READY TO PROCESS:\033[0m {clean_count} domains")
    print_func("")

    if blacklisted_count > 0:
        print_func("  \033[36mOptions:\033[0m")
        print_func("  [1] Proceed with clean domains only (recommended)")
        print_func("  [2] View all blacklisted domains")
        print_func("  [3] Include all domains (ignore blacklist)")
        print_func("  [4] Skip Kali expansion entirely")
        print_func("")

        _flush_stdin()
        review_choice = get_input_func("Choice [1]: ") or "1"

        if review_choice == "2":
            # View all blacklisted
            print_func(f"\n  \033[91mBlacklisted domains ({blacklisted_count}):\033[0m")
            for d in sorted(blacklisted_domains):
                print_func(f"    • {d}")
            print_func("")

            _flush_stdin()
            review_choice = get_input_func("Proceed with clean domains? [Y/n/all]: ") or "y"
            if review_choice.lower() == "n":
                print_func("  Skipping Kali expansion.")
                return seed_domains
            elif review_choice.lower() == "all":
                clean_domains = seed_domains
                blacklisted_domains = set()
                print_func("  Using ALL domains (blacklist overridden)")

        elif review_choice == "3":
            clean_domains = seed_domains
            blacklisted_domains = set()
            print_func("  Using ALL domains (blacklist overridden)")

        elif review_choice == "4":
            print_func("  Skipping Kali expansion.")
            return seed_domains

    print_func(f"""
\033[93m{'━' * 60}\033[0m
\033[1m  KALI ENHANCED DISCOVERY\033[0m
\033[93m{'━' * 60}\033[0m

  Processing {len(clean_domains)} domains for expansion.

  \033[36mCurrent Mode:\033[0m {config.name}
  \033[36mTools Available:\033[0m {coverage['available_tools']}/{coverage['total_tools']}
  \033[36mTools:\033[0m {', '.join(coverage['available_list'][:5])}{'...' if len(coverage['available_list']) > 5 else ''}

  Kali tools can enumerate subdomains and related infrastructure
  for each domain, potentially finding 10x more targets.
""")

    print_func("  [1] Expand domains with Kali tools (recommended)")
    print_func("  [2] Change scan mode first")
    print_func("  [3] Skip - use original domains only")
    print_func("")

    _flush_stdin()  # Clear any buffered input
    choice = get_input_func("Choice [1]: ") or "1"

    if choice == "3":
        print_func("  Skipping Kali expansion.")
        return seed_domains  # Return original including blacklisted

    if choice == "2":
        run_mode_selection_menu(print_func, get_input_func, None, None)
        # Recursive call with updated mode
        return kali_expand_domains(seed_domains, print_func, get_input_func, max_domains)

    # Ask how many domains to expand
    print_func(f"\n  \033[36mHow many domains to expand?\033[0m")
    print_func(f"  Total available: {clean_count}")
    print_func(f"  Enter a number or 'all' for all domains")
    print_func("")

    _flush_stdin()  # Clear any buffered input
    count_input = get_input_func(f"Domains to expand [{clean_count}]: ") or str(clean_count)

    if count_input.lower() == 'all':
        expand_count = clean_count
    else:
        try:
            expand_count = int(count_input)
            expand_count = min(expand_count, clean_count)  # Cap at total
        except ValueError:
            expand_count = clean_count  # Default to all on invalid input

    # Expand domains (using clean list, not blacklisted)
    domains_to_expand = list(clean_domains)[:expand_count]

    # Auto-detect optimal parallelism
    optimal, sys_stats = get_optimal_parallelism()

    print_func(f"\n  \033[36mSystem Resources Detected:\033[0m")
    print_func(f"  CPU Cores: {sys_stats['cpu_cores']}")
    print_func(f"  RAM: {sys_stats['ram_available_gb']}GB free / {sys_stats['ram_total_gb']}GB total ({sys_stats['ram_percent_free']}% free)")
    print_func(f"")
    print_func(f"  \033[92mRecommended parallelism: {optimal}\033[0m")
    print_func(f"  (Based on {sys_stats['ram_available_gb']}GB available RAM @ ~1.5GB per domain)")
    print_func(f"")

    _flush_stdin()  # Clear any buffered input
    parallel_input = get_input_func(f"Parallel domains [{optimal}]: ") or str(optimal)
    try:
        parallel_domains = max(1, int(parallel_input))
    except ValueError:
        parallel_domains = optimal

    # Threshold settings based on mode (domains exceeding this are likely platforms)
    # Lowered thresholds: legitimate companies rarely have >35 subdomains
    THRESHOLD_BY_MODE = {
        ScanMode.GHOST: 20,
        ScanMode.STEALTH: 25,
        ScanMode.STANDARD: 30,
        ScanMode.DEEP: 35,
    }
    threshold = THRESHOLD_BY_MODE.get(mode, 30)

    print_func(f"\n  Expanding {len(domains_to_expand)} domains with Kali tools...")
    print_func(f"  Processing {parallel_domains} domains in parallel")
    print_func(f"  Threshold: {threshold} subdomains (auto-skip if exceeded)\n")

    all_domains = set(clean_domains)  # Start with clean domains (excluding blacklisted)
    completed = [0]  # Use list for mutable counter in closure
    total = len(domains_to_expand)
    threshold_skipped = []  # Track domains that exceeded threshold

    # Thread-safe lock for updating shared state
    import threading
    lock = threading.Lock()

    # Run aggregator on each domain
    from .aggregator import DiscoveryAggregator
    import concurrent.futures

    def expand_single_domain(domain_info):
        """Expand a single domain - runs in thread pool"""
        idx, domain = domain_info

        # Create aggregator for this thread (no progress callback to avoid garbled output)
        aggregator = DiscoveryAggregator(
            mode=get_current_mode(),
            parallel=True,
            max_workers=3,
            progress_callback=None  # Disable per-tool progress for cleaner output
        )

        try:
            result = aggregator.run(domain)
            new_count = len(result.domains) + len(result.subdomains)

            with lock:
                completed[0] += 1

                # Check if exceeds threshold (likely a platform)
                if new_count > threshold:
                    threshold_skipped.append((domain, new_count))
                    print_func(f"  \033[93m[{completed[0]}/{total}]\033[0m {domain} \033[93m+{new_count} domains (SKIPPED - threshold exceeded)\033[0m")
                else:
                    all_domains.update(result.domains)
                    all_domains.update(result.subdomains)
                    print_func(f"  \033[92m[{completed[0]}/{total}]\033[0m {domain} \033[92m+{new_count} domains\033[0m")

            return (domain, new_count, None)

        except Exception as e:
            with lock:
                completed[0] += 1
                print_func(f"  \033[91m[{completed[0]}/{total}]\033[0m {domain} \033[91mError: {e}\033[0m")
            return (domain, 0, str(e))

    # Process domains in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_domains) as executor:
        domain_infos = list(enumerate(domains_to_expand, 1))
        # Force execution and wait for completion
        results = list(executor.map(expand_single_domain, domain_infos))

    # Summary
    original_count = len(clean_domains)  # Clean domains (after blacklist)
    final_count = len(all_domains)
    new_found = final_count - original_count

    print_func(f"""
\033[92m{'━' * 60}\033[0m
\033[92m  Expansion Complete!\033[0m
\033[92m{'━' * 60}\033[0m

  Input domains:     {original_count}""")
    if blacklisted_count > 0:
        print_func(f"  Blacklisted:       {blacklisted_count} (skipped)")
    print_func(f"""  New discoveries:   {new_found}
  Total domains:     {final_count}
""")

    # Report threshold-skipped domains
    if threshold_skipped:
        print_func(f"\033[93m  Threshold Skipped: {len(threshold_skipped)} domains\033[0m")
        print_func(f"  \033[90m(Exceeded {threshold} subdomains - likely platforms)\033[0m\n")

        for domain, count in sorted(threshold_skipped, key=lambda x: -x[1])[:5]:
            print_func(f"    \033[93m•\033[0m {domain}: {count} subdomains")

        if len(threshold_skipped) > 5:
            print_func(f"    \033[90m... and {len(threshold_skipped) - 5} more\033[0m")

        print_func("")

        # Offer to include skipped domains
        _flush_stdin()
        include_skipped = get_input_func("Include skipped domains anyway? [y/N]: ") or "n"

        if include_skipped.lower() == 'y':
            # Re-add the skipped domains' subdomains
            print_func("  \033[93mNote: Subdomains from skipped domains were not saved.\033[0m")
            print_func("  \033[93mYou'll need to re-run expansion to include them.\033[0m")

    return all_domains
