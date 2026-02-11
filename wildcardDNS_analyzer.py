#!/usr/bin/env python3
"""
wildcardDNS_analyzer.py - Signal//Noise Wildcard DNS Deep Dive Analyzer

Part of the PUPPETMASTER sock puppet detection toolkit.

PURPOSE:
When SpiderFoot scans enumerate thousands of subdomains that resolve to a single IP,
it could indicate wildcard DNS configuration (legitimate SaaS/cloud patterns) rather
than actual infrastructure. This module separates SIGNAL from NOISE by:

1. Quick Check: Fast wildcard detection for flagging potential false positives
2. Deep Dive: Comprehensive multi-zone analysis with certificate transparency,
   HTTP fingerprinting, and infrastructure correlation

USAGE:
    Standalone:
        python3 wildcardDNS_analyzer.py --domain example.com
        python3 wildcardDNS_analyzer.py --domain example.com --full
        python3 wildcardDNS_analyzer.py --keywords "keyword1,keyword2" --spiderfoot-dir ./exports

    As module (from pipeline):
        from wildcardDNS_analyzer import quick_wildcard_check, WildcardAnalyzer

        # Quick check for pipeline integration
        suspects = quick_wildcard_check(["example.com", "other.com"])

        # Full analysis
        analyzer = WildcardAnalyzer(domain="example.com", spiderfoot_dir="./exports")
        results = analyzer.run_full_analysis()

Author: PUPPETMASTER Team
Version: 1.0.0
"""

from __future__ import annotations  # Defer type annotation evaluation (fixes dnspython optional import)

import os
import sys
import re
import json
import time
import random
import string
import hashlib
import argparse
import socket
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# DNS resolution
try:
    import dns.resolver
    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False

# HTTP requests
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# =============================================================================
# TERMINAL UI - CYBERPUNK AESTHETIC
# =============================================================================

class C:
    """ANSI color codes for cyberpunk terminal aesthetic"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # Primary colors
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

    # Bright variants
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'


BANNER = f"""
{C.CYAN}+{'=' * 78}+
|{' ' * 78}|
|  {C.MAGENTA}███████╗██╗ ██████╗ ███╗   ██╗ █████╗ ██╗     {C.CYAN}                              |
|  {C.MAGENTA}██╔════╝██║██╔════╝ ████╗  ██║██╔══██╗██║     {C.CYAN}                              |
|  {C.MAGENTA}███████╗██║██║  ███╗██╔██╗ ██║███████║██║     {C.CYAN}                              |
|  {C.MAGENTA}╚════██║██║██║   ██║██║╚██╗██║██╔══██║██║     {C.CYAN}                              |
|  {C.MAGENTA}███████║██║╚██████╔╝██║ ╚████║██║  ██║███████╗{C.CYAN}                              |
|  {C.MAGENTA}╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝{C.CYAN}                              |
|        {C.YELLOW}██╗██╗███╗   ██╗ ██████╗ ██╗███████╗███████╗{C.CYAN}                          |
|       {C.YELLOW}██╔╝██╔╝████╗  ██║██╔═══██╗██║██╔════╝██╔════╝{C.CYAN}                          |
|      {C.YELLOW}██╔╝██╔╝ ██╔██╗ ██║██║   ██║██║███████╗█████╗  {C.CYAN}                          |
|     {C.YELLOW}██╔╝██╔╝  ██║╚██╗██║██║   ██║██║╚════██║██╔══╝  {C.CYAN}                          |
|    {C.YELLOW}██╔╝██╔╝   ██║ ╚████║╚██████╔╝██║███████║███████╗{C.CYAN}                          |
|    {C.YELLOW}╚═╝ ╚═╝    ╚═╝  ╚═══╝ ╚═════╝ ╚═╝╚══════╝╚══════╝{C.CYAN}                          |
|{' ' * 78}|
|  {C.WHITE}[ WILDCARD DNS ANALYZER v1.0 ]{C.CYAN}                                            |
|  {C.DIM}Separating signal from noise in enumerated subdomains{C.RESET}{C.CYAN}                    |
|  {C.DIM}"In infinite subdomains, truth hides in the anomalies"{C.RESET}{C.CYAN}                   |
|{' ' * 78}|
+{'=' * 78}+{C.RESET}
"""

MINI_BANNER = f"""
{C.CYAN}+{'-' * 50}+
|  {C.MAGENTA}SIGNAL//NOISE{C.CYAN} - Wildcard DNS Analyzer        |
+{'-' * 50}+{C.RESET}
"""


class TerminalUI:
    """Cyberpunk-style terminal interface"""

    @staticmethod
    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def print_banner(mini: bool = False):
        print(MINI_BANNER if mini else BANNER)

    @staticmethod
    def print_phase(phase_num: int, title: str, total: int = 6):
        print(f"\n{C.CYAN}+{'=' * 78}+")
        print(f"|  {C.YELLOW}{C.BOLD}PHASE {phase_num}/{total}: {title.upper()}{C.RESET}{C.CYAN}{' ' * (78 - 14 - len(title))}|")
        print(f"+{'=' * 78}+{C.RESET}\n")

    @staticmethod
    def print_section(title: str):
        print(f"\n{C.MAGENTA}+-- {title} {'-' * (60 - len(title))}+{C.RESET}")

    @staticmethod
    def print_info(msg: str):
        print(f"  {C.CYAN}[i]{C.RESET} {msg}")

    @staticmethod
    def print_success(msg: str):
        print(f"  {C.GREEN}[+]{C.RESET} {msg}")

    @staticmethod
    def print_warning(msg: str):
        print(f"  {C.YELLOW}[!]{C.RESET} {msg}")

    @staticmethod
    def print_error(msg: str):
        print(f"  {C.RED}[-]{C.RESET} {msg}")

    @staticmethod
    def print_critical(msg: str):
        print(f"  {C.RED}{C.BOLD}[CRITICAL]{C.RESET} {C.RED}{msg}{C.RESET}")

    @staticmethod
    def print_anomaly(msg: str):
        print(f"  {C.RED}{C.BOLD}[ANOMALY]{C.RESET} {C.YELLOW}{msg}{C.RESET}")

    @staticmethod
    def progress_bar(current: int, total: int, prefix: str = "", width: int = 40):
        """Animated progress bar"""
        pct = current / total if total > 0 else 0
        filled = int(width * pct)
        bar = '+' * filled + '-' * (width - filled)
        sys.stdout.write(f"\r  {C.CYAN}{prefix}: [{bar}] {pct*100:.1f}% ({current}/{total}){C.RESET}")
        sys.stdout.flush()
        if current >= total:
            print()

    @staticmethod
    def print_table(headers: List[str], rows: List[List[str]], col_widths: Optional[List[int]] = None):
        """Print formatted table"""
        if not col_widths:
            col_widths = [max(len(str(row[i])) for row in [headers] + rows) + 2 for i in range(len(headers))]

        # Header
        header_line = f"  {C.CYAN}|"
        for i, h in enumerate(headers):
            header_line += f" {C.BOLD}{h.ljust(col_widths[i])}{C.RESET}{C.CYAN}|"
        print(f"  {C.CYAN}+{'+'.join(['-' * (w + 2) for w in col_widths])}+{C.RESET}")
        print(header_line)
        print(f"  {C.CYAN}+{'+'.join(['=' * (w + 2) for w in col_widths])}+{C.RESET}")

        # Rows
        for row in rows:
            row_line = f"  {C.CYAN}|"
            for i, cell in enumerate(row):
                row_line += f" {str(cell).ljust(col_widths[i])}{C.CYAN}|"
            print(row_line)
        print(f"  {C.CYAN}+{'+'.join(['-' * (w + 2) for w in col_widths])}+{C.RESET}")


# Initialize UI
ui = TerminalUI()


# =============================================================================
# INTERACTIVE MENU HELPERS
# =============================================================================

def get_input(prompt: str, default: str = "") -> str:
    """Get input with optional default value"""
    if default:
        display = f"{C.WHITE}{prompt} [{C.DIM}{default}{C.RESET}{C.WHITE}]: {C.RESET}"
    else:
        display = f"{C.WHITE}{prompt}: {C.RESET}"

    try:
        result = input(display).strip()
        return result if result else default
    except (KeyboardInterrupt, EOFError):
        print()
        return ""


def confirm(prompt: str, default: bool = True) -> bool:
    """Ask for Y/N confirmation"""
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        response = input(f"{C.WHITE}{prompt} {suffix}: {C.RESET}").strip().lower()
        if not response:
            return default
        return response in ('y', 'yes')
    except (KeyboardInterrupt, EOFError):
        print()
        return False


def find_puppetmaster_config() -> Dict:
    """Load puppetmaster config to find saved paths"""
    config_paths = [
        Path(__file__).parent / ".puppetmaster_config.json",
        Path.cwd() / ".puppetmaster_config.json",
    ]

    for config_path in config_paths:
        try:
            if config_path.exists():
                return json.loads(config_path.read_text())
        except Exception:
            pass
    return {}


def find_results_directories() -> List[Path]:
    """
    Find PUPPETMASTER results directories.

    Priority order:
    1. Saved output_dirs from puppetmaster config (exact paths from module 5)
    2. Search for results_* patterns in common locations

    Returns directories sorted by modification time (newest first).
    """
    results_dirs = []
    seen = set()

    # PRIORITY 1: Check saved output directories from puppetmaster config
    # These are the EXACT paths where module 5 saved results
    config = find_puppetmaster_config()
    for saved_dir in config.get('output_dirs', []):
        p = Path(saved_dir)
        if p.exists() and p.is_dir() and p not in seen:
            # Verify it looks like a results directory (has executive_summary.md)
            if (p / "executive_summary.md").exists():
                results_dirs.append(p)
                seen.add(p)

    # PRIORITY 2: Search for results_* patterns in common locations
    search_paths = [
        Path(__file__).parent,  # puppetmaster directory
        Path.cwd(),  # Current working directory
    ]

    # Also search parent directories of saved paths
    for saved_dir in config.get('output_dirs', []):
        parent = Path(saved_dir).parent
        if parent.exists() and parent not in search_paths:
            search_paths.append(parent)

    for search_path in search_paths:
        try:
            for d in search_path.iterdir():
                if d.is_dir() and d.name.startswith('results_') and d not in seen:
                    # Verify it has executive_summary.md
                    if (d / "executive_summary.md").exists():
                        results_dirs.append(d)
                        seen.add(d)
        except Exception:
            pass

    # Sort by modification time (newest first)
    results_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return results_dirs


def parse_wildcard_suspects_from_summary(results_dir: Path) -> List[Dict]:
    """
    Parse executive_summary.md to extract wildcard DNS suspects.

    Returns list of dicts: [{"domain": str, "wildcard_ip": str, "confidence": str}]
    """
    suspects = []
    summary_path = results_dir / "executive_summary.md"

    if not summary_path.exists():
        return suspects

    try:
        content = summary_path.read_text()

        # Look for the wildcard DNS section
        # Format: | domain | wildcard_ip | confidence |
        in_wildcard_section = False

        for line in content.split('\n'):
            if 'Wildcard DNS' in line or 'wildcard DNS' in line:
                in_wildcard_section = True
                continue

            if in_wildcard_section:
                # Stop at next section
                if line.startswith('##') or line.startswith('---'):
                    break

                # Parse table rows: | domain | ip | confidence |
                if line.startswith('|') and not line.startswith('|--') and not line.startswith('| Domain'):
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 4:  # Empty, domain, ip, confidence, empty
                        domain = parts[1].strip()
                        wildcard_ip = parts[2].strip() if len(parts) > 2 else 'unknown'
                        confidence = parts[3].strip() if len(parts) > 3 else 'unknown'

                        if domain and domain not in ('Domain', '---'):
                            suspects.append({
                                'domain': domain,
                                'wildcard_ip': wildcard_ip,
                                'confidence': confidence
                            })
    except Exception as e:
        ui.print_warning(f"Could not parse executive summary: {e}")

    return suspects


def find_spiderfoot_exports_dir() -> Optional[Path]:
    """Find the SpiderFoot exports directory from config or common locations"""
    config = find_puppetmaster_config()

    # Check config first
    if 'spiderfoot_output_dir' in config:
        p = Path(config['spiderfoot_output_dir'])
        if p.exists():
            return p

    # Check common locations
    common_paths = [
        Path(__file__).parent / "spiderfoot_exports",
        Path(__file__).parent.parent / "spiderfoot_export",
        Path.cwd() / "spiderfoot_exports",
        Path.cwd() / "spiderfoot_export",
        Path.home() / "spiderfoot_exports",
    ]

    for p in common_paths:
        if p.exists() and p.is_dir():
            # Check if it contains CSV files
            csv_files = list(p.glob("*.csv"))
            if csv_files:
                return p

    return None


def interactive_menu():
    """Run the interactive menu for standalone use"""
    ui.clear_screen()
    ui.print_banner()

    while True:
        print(f"\n{C.CYAN}+{'-' * 60}+{C.RESET}")
        print(f"{C.CYAN}|  {C.WHITE}MAIN MENU{C.CYAN}{' ' * 50}|{C.RESET}")
        print(f"{C.CYAN}+{'-' * 60}+{C.RESET}\n")

        print(f"  {C.MAGENTA}[1]{C.RESET} {C.WHITE}Quick Wildcard Check{C.RESET}")
        print(f"      {C.DIM}Test a single domain for wildcard DNS{C.RESET}")
        print()
        print(f"  {C.MAGENTA}[2]{C.RESET} {C.WHITE}Full Analysis{C.RESET}")
        print(f"      {C.DIM}Deep dive with multi-zone DNS, CT logs, HTTP fingerprinting{C.RESET}")
        print()
        print(f"  {C.MAGENTA}[3]{C.RESET} {C.WHITE}Load from Puppet Analysis{C.RESET}")
        print(f"      {C.DIM}Auto-detect suspects from PUPPETMASTER results{C.RESET}")
        print()
        print(f"  {C.MAGENTA}[4]{C.RESET} {C.WHITE}Batch Check from File{C.RESET}")
        print(f"      {C.DIM}Check multiple domains from a text file{C.RESET}")
        print()
        print(f"  {C.RED}[Q]{C.RESET} {C.WHITE}Quit{C.RESET}")
        print()

        choice = get_input("Select option", "1").lower()

        if choice == 'q' or choice == 'quit' or choice == 'exit':
            print(f"\n{C.CYAN}[i]{C.RESET} {C.DIM}Exiting SIGNAL//NOISE analyzer...{C.RESET}\n")
            break

        elif choice == '1':
            interactive_quick_check()

        elif choice == '2':
            interactive_full_analysis()

        elif choice == '3':
            interactive_load_from_puppet()

        elif choice == '4':
            interactive_batch_check()

        else:
            ui.print_warning("Invalid option. Please select 1-4 or Q.")


def interactive_quick_check():
    """Interactive quick wildcard check"""
    print(f"\n{C.CYAN}+{'-' * 60}+{C.RESET}")
    print(f"{C.CYAN}|  {C.WHITE}QUICK WILDCARD CHECK{C.CYAN}{' ' * 39}|{C.RESET}")
    print(f"{C.CYAN}+{'-' * 60}+{C.RESET}\n")

    domain = get_input("Enter domain to check (e.g., example.io)")
    if not domain:
        ui.print_warning("No domain provided.")
        return

    ui.print_info(f"Testing {domain} for wildcard DNS...")
    print()

    results = quick_wildcard_check([domain], timeout=3.0)

    if domain in results:
        result = results[domain]
        if result.get('is_wildcard'):
            print(f"\n  {C.YELLOW}{C.BOLD}[!] WILDCARD DNS DETECTED{C.RESET}")
            print(f"      {C.WHITE}Domain:{C.RESET}       {domain}")
            print(f"      {C.WHITE}Wildcard IP:{C.RESET}  {result.get('wildcard_ip', 'unknown')}")
            print(f"      {C.WHITE}Confidence:{C.RESET}   {result.get('confidence', 'unknown')}")
            print()
            ui.print_warning("This domain may be a false positive in sock puppet analysis.")
            ui.print_info("Run Full Analysis for deeper investigation.")
        else:
            print(f"\n  {C.GREEN}[+] NO WILDCARD DNS{C.RESET}")
            print(f"      {C.WHITE}Domain:{C.RESET}     {domain}")
            print(f"      {C.WHITE}Confidence:{C.RESET} {result.get('confidence', 'HIGH')}")
            print()
            ui.print_success("This domain does NOT appear to use wildcard DNS.")

    get_input("\nPress Enter to continue...")


def interactive_full_analysis():
    """Interactive full analysis"""
    print(f"\n{C.CYAN}+{'-' * 60}+{C.RESET}")
    print(f"{C.CYAN}|  {C.WHITE}FULL WILDCARD ANALYSIS{C.CYAN}{' ' * 37}|{C.RESET}")
    print(f"{C.CYAN}+{'-' * 60}+{C.RESET}\n")

    domain = get_input("Enter domain to analyze (e.g., example.io)")
    if not domain:
        ui.print_warning("No domain provided.")
        return

    # SpiderFoot directory
    sf_dir = find_spiderfoot_exports_dir()
    if sf_dir:
        ui.print_info(f"Found SpiderFoot exports: {sf_dir}")
        if not confirm(f"Use this directory?"):
            sf_dir_input = get_input("SpiderFoot exports directory (or Enter to skip)")
            sf_dir = Path(sf_dir_input) if sf_dir_input else None
    else:
        sf_dir_input = get_input("SpiderFoot exports directory (or Enter to skip)")
        sf_dir = Path(sf_dir_input) if sf_dir_input else None

    # Output directory
    # Save to wildcard_outputs/ subdirectory to keep things organized
    wildcard_dir = Path("./wildcard_outputs")
    wildcard_dir.mkdir(exist_ok=True)
    default_output = str(wildcard_dir / f"wildcard_analysis_{domain.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    output_dir = get_input("Output directory", default_output)

    # Create and run analyzer
    analyzer = WildcardAnalyzer(
        domain=domain,
        spiderfoot_dir=str(sf_dir) if sf_dir else None,
        output_dir=output_dir
    )

    print()
    results = analyzer.run_full_analysis()

    print(f"\n{C.CYAN}+{'-' * 60}+{C.RESET}")
    print(f"{C.CYAN}|  {C.GREEN}Analysis Complete{C.CYAN}{' ' * 42}|{C.RESET}")
    print(f"{C.CYAN}+{'-' * 60}+{C.RESET}")

    if output_dir:
        ui.print_info(f"Reports saved to: {output_dir}")

    get_input("\nPress Enter to continue...")


def interactive_load_from_puppet():
    """Load suspects from PUPPETMASTER analysis results"""
    print(f"\n{C.CYAN}+{'-' * 60}+{C.RESET}")
    print(f"{C.CYAN}|  {C.WHITE}LOAD FROM PUPPET ANALYSIS{C.CYAN}{' ' * 34}|{C.RESET}")
    print(f"{C.CYAN}+{'-' * 60}+{C.RESET}\n")

    # Find results directories
    results_dirs = find_results_directories()

    if not results_dirs:
        ui.print_error("No PUPPETMASTER results directories found.")
        ui.print_info("Run PUPPETMASTER analysis [option 5] first to generate results.")
        print()
        # Debug: show where we looked
        config = find_puppetmaster_config()
        saved_dirs = config.get('output_dirs', [])
        if saved_dirs:
            ui.print_info(f"Config has {len(saved_dirs)} saved path(s), but none contain executive_summary.md:")
            for d in saved_dirs[:3]:
                print(f"      {C.DIM}- {d}{C.RESET}")
        else:
            config_path = Path(__file__).parent / ".puppetmaster_config.json"
            ui.print_info(f"No saved paths in config. Config location: {config_path}")
            if not config_path.exists():
                print(f"      {C.DIM}(Config file does not exist){C.RESET}")
        get_input("\nPress Enter to continue...")
        return

    # Show available directories
    ui.print_info(f"Found {len(results_dirs)} results director{'y' if len(results_dirs) == 1 else 'ies'}:")
    print()

    for i, d in enumerate(results_dirs[:10], 1):
        # Get timestamp from directory name
        timestamp = d.name.replace('results_', '')
        mtime = datetime.fromtimestamp(d.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        print(f"  {C.MAGENTA}[{i}]{C.RESET} {d.name} {C.DIM}({mtime}){C.RESET}")

    if len(results_dirs) > 10:
        print(f"  {C.DIM}... and {len(results_dirs) - 10} more{C.RESET}")
    print()

    # Auto-select most recent or let user choose
    default_choice = "1"
    choice = get_input(f"Select results directory", default_choice)

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(results_dirs):
            selected_dir = results_dirs[idx]
        else:
            ui.print_warning("Invalid selection, using most recent.")
            selected_dir = results_dirs[0]
    except ValueError:
        # Maybe they typed a path
        if Path(choice).exists():
            selected_dir = Path(choice)
        else:
            ui.print_warning("Invalid selection, using most recent.")
            selected_dir = results_dirs[0]

    ui.print_success(f"Using: {selected_dir}")
    print()

    # Parse wildcard suspects
    suspects = parse_wildcard_suspects_from_summary(selected_dir)

    if not suspects:
        ui.print_warning("No wildcard DNS suspects found in this analysis.")
        ui.print_info("This could mean:")
        print(f"      {C.DIM}- No domains flagged as potential wildcards{C.RESET}")
        print(f"      {C.DIM}- The analysis didn't run wildcard detection{C.RESET}")
        print()

        # Offer to manually enter a domain
        if confirm("Would you like to manually enter a domain to analyze?"):
            interactive_full_analysis()
        else:
            get_input("\nPress Enter to continue...")
        return

    # Display suspects
    print(f"{C.YELLOW}Found {len(suspects)} wildcard DNS suspect(s):{C.RESET}\n")

    headers = ["#", "Domain", "Wildcard IP", "Confidence"]
    rows = []
    for i, s in enumerate(suspects, 1):
        rows.append([str(i), s['domain'], s['wildcard_ip'], s['confidence']])

    ui.print_table(headers, rows)
    print()

    # Find SpiderFoot exports directory
    sf_dir = find_spiderfoot_exports_dir()
    if sf_dir:
        ui.print_info(f"SpiderFoot exports: {sf_dir}")

    # Let user choose which domain to analyze
    print(f"\n{C.WHITE}Which domain would you like to analyze?{C.RESET}")
    print(f"  {C.DIM}Enter number, domain name, or 'all' for batch analysis{C.RESET}\n")

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
            # Maybe they typed a domain name
            for s in suspects:
                if selection.lower() in s['domain'].lower():
                    domains_to_analyze.append(s['domain'])
            if not domains_to_analyze:
                domains_to_analyze = [selection]

    if not domains_to_analyze:
        ui.print_warning("No domain selected.")
        get_input("\nPress Enter to continue...")
        return

    # Confirm SpiderFoot directory
    if sf_dir:
        if not confirm(f"Use SpiderFoot exports from {sf_dir}?"):
            sf_input = get_input("SpiderFoot exports directory (or Enter to skip)")
            sf_dir = Path(sf_input) if sf_input else None
    else:
        sf_input = get_input("SpiderFoot exports directory (or Enter to skip)")
        sf_dir = Path(sf_input) if sf_input else None

    # Run analysis
    # Ensure wildcard_outputs directory exists
    wildcard_dir = Path("./wildcard_outputs")
    wildcard_dir.mkdir(exist_ok=True)

    for domain in domains_to_analyze:
        print(f"\n{C.CYAN}{'=' * 70}{C.RESET}")
        ui.print_info(f"Analyzing: {domain}")
        print(f"{C.CYAN}{'=' * 70}{C.RESET}\n")

        output_dir = str(wildcard_dir / f"wildcard_analysis_{domain.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        analyzer = WildcardAnalyzer(
            domain=domain,
            spiderfoot_dir=str(sf_dir) if sf_dir else None,
            output_dir=output_dir
        )

        results = analyzer.run_full_analysis()

        ui.print_success(f"Analysis complete. Reports saved to: {output_dir}")

    print(f"\n{C.CYAN}+{'-' * 60}+{C.RESET}")
    print(f"{C.CYAN}|  {C.GREEN}All Analyses Complete{C.CYAN}{' ' * 38}|{C.RESET}")
    print(f"{C.CYAN}+{'-' * 60}+{C.RESET}")

    get_input("\nPress Enter to continue...")


def interactive_batch_check():
    """Batch check multiple domains from a file"""
    print(f"\n{C.CYAN}+{'-' * 60}+{C.RESET}")
    print(f"{C.CYAN}|  {C.WHITE}BATCH WILDCARD CHECK{C.CYAN}{' ' * 39}|{C.RESET}")
    print(f"{C.CYAN}+{'-' * 60}+{C.RESET}\n")

    file_path = get_input("Enter path to file with domains (one per line)")
    if not file_path:
        ui.print_warning("No file provided.")
        get_input("\nPress Enter to continue...")
        return

    file_path = Path(file_path).expanduser()
    if not file_path.exists():
        ui.print_error(f"File not found: {file_path}")
        get_input("\nPress Enter to continue...")
        return

    try:
        domains = [line.strip() for line in file_path.read_text().split('\n') if line.strip()]
    except Exception as e:
        ui.print_error(f"Failed to read file: {e}")
        get_input("\nPress Enter to continue...")
        return

    if not domains:
        ui.print_warning("No domains found in file.")
        get_input("\nPress Enter to continue...")
        return

    ui.print_info(f"Found {len(domains)} domain(s) to check")
    print()

    # Run batch check
    results = quick_wildcard_check(domains, timeout=3.0)

    # Separate wildcards and non-wildcards
    wildcards = []
    non_wildcards = []

    for domain, result in results.items():
        if result.get('is_wildcard'):
            wildcards.append((domain, result))
        else:
            non_wildcards.append((domain, result))

    # Display results
    print(f"\n{C.CYAN}+{'-' * 60}+{C.RESET}")
    print(f"{C.CYAN}|  {C.WHITE}BATCH RESULTS{C.CYAN}{' ' * 46}|{C.RESET}")
    print(f"{C.CYAN}+{'-' * 60}+{C.RESET}\n")

    print(f"  {C.WHITE}Total Checked:{C.RESET}    {len(domains)}")
    print(f"  {C.YELLOW}Wildcards Found:{C.RESET}  {len(wildcards)}")
    print(f"  {C.GREEN}Non-Wildcards:{C.RESET}    {len(non_wildcards)}")
    print()

    if wildcards:
        print(f"\n{C.YELLOW}{C.BOLD}WILDCARD DNS DETECTED:{C.RESET}\n")
        headers = ["Domain", "Wildcard IP", "Confidence"]
        rows = [[d, r.get('wildcard_ip', 'unknown'), r.get('confidence', 'unknown')] for d, r in wildcards]
        ui.print_table(headers, rows)

    # Save results
    if confirm("\nSave results to file?"):
        output_file = get_input("Output file", "wildcard_batch_results.txt")
        try:
            with open(output_file, 'w') as f:
                f.write("# Wildcard DNS Batch Check Results\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")

                f.write("## Wildcard DNS Detected:\n")
                for d, r in wildcards:
                    f.write(f"{d}\t{r.get('wildcard_ip', 'unknown')}\t{r.get('confidence', 'unknown')}\n")

                f.write("\n## Non-Wildcard Domains:\n")
                for d, r in non_wildcards:
                    f.write(f"{d}\n")

            ui.print_success(f"Results saved to: {output_file}")
        except Exception as e:
            ui.print_error(f"Failed to save results: {e}")

    get_input("\nPress Enter to continue...")


# =============================================================================
# QUICK WILDCARD CHECK - For Pipeline Integration
# =============================================================================

def quick_wildcard_check(domains: List[str], timeout: float = 2.0) -> Dict[str, Dict]:
    """
    Quick wildcard DNS detection for pipeline integration.

    Tests each domain for wildcard DNS by querying random non-existent subdomains.
    If multiple random queries return the same IP, it's likely a wildcard.

    Args:
        domains: List of base domains to check (e.g., ["example.com", "other.io"])
        timeout: DNS query timeout in seconds

    Returns:
        Dict mapping domain -> {"is_wildcard": bool, "wildcard_ip": str|None, "confidence": str}
    """
    results = {}

    if not HAS_DNSPYTHON:
        # Fallback to socket-based resolution
        for domain in domains:
            results[domain] = _quick_check_socket(domain, timeout)
    else:
        resolver = dns.resolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout

        for domain in domains:
            results[domain] = _quick_check_dns(domain, resolver)

    return results


def _quick_check_dns(domain: str, resolver: dns.resolver.Resolver) -> Dict:
    """Quick wildcard check using dnspython (checks both IPv4 and IPv6)"""
    test_responses = []

    # Test 3 random non-existent subdomains
    for _ in range(3):
        random_sub = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        test_domain = f"{random_sub}.{domain}"

        ips = []
        got_response = False

        # Try A records (IPv4)
        try:
            answers = resolver.resolve(test_domain, 'A')
            ips.extend(sorted([str(rdata) for rdata in answers]))
            got_response = True
        except dns.resolver.NXDOMAIN:
            test_responses.append(('NXDOMAIN',))
            continue  # Domain doesn't exist at all
        except dns.resolver.NoAnswer:
            pass  # No A record, try AAAA
        except Exception:
            pass

        # Try AAAA records (IPv6) if no A record
        if not got_response:
            try:
                answers = resolver.resolve(test_domain, 'AAAA')
                ips.extend(sorted([str(rdata) for rdata in answers]))
                got_response = True
            except dns.resolver.NXDOMAIN:
                test_responses.append(('NXDOMAIN',))
                continue
            except dns.resolver.NoAnswer:
                test_responses.append(('NOANSWER',))
                continue
            except Exception:
                test_responses.append(('ERROR',))
                continue

        if got_response and ips:
            test_responses.append(tuple(ips))
        elif not got_response:
            test_responses.append(('ERROR',))

    # If all 3 random subdomains return the same response, it's a wildcard
    if len(set(test_responses)) == 1 and test_responses[0] not in [('NXDOMAIN',), ('NOANSWER',), ('ERROR',)]:
        return {
            "is_wildcard": True,
            "wildcard_ip": test_responses[0][0] if test_responses[0] else None,
            "confidence": "HIGH",
            "test_responses": [list(r) for r in test_responses]
        }
    elif len(set(test_responses)) == 1 and test_responses[0] == ('NXDOMAIN',):
        return {
            "is_wildcard": False,
            "wildcard_ip": None,
            "confidence": "HIGH",
            "note": "Non-existent subdomains correctly return NXDOMAIN"
        }
    else:
        return {
            "is_wildcard": False,
            "wildcard_ip": None,
            "confidence": "MEDIUM",
            "note": "Mixed responses - no clear wildcard pattern"
        }


def _quick_check_socket(domain: str, timeout: float) -> Dict:
    """Quick wildcard check using socket (fallback)"""
    socket.setdefaulttimeout(timeout)
    test_responses = []

    for _ in range(3):
        random_sub = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        test_domain = f"{random_sub}.{domain}"

        try:
            ip = socket.gethostbyname(test_domain)
            test_responses.append(ip)
        except socket.gaierror:
            test_responses.append('NXDOMAIN')
        except Exception:
            test_responses.append('ERROR')

    if len(set(test_responses)) == 1 and test_responses[0] not in ['NXDOMAIN', 'ERROR']:
        return {
            "is_wildcard": True,
            "wildcard_ip": test_responses[0],
            "confidence": "HIGH"
        }
    else:
        return {
            "is_wildcard": False,
            "wildcard_ip": None,
            "confidence": "MEDIUM" if 'ERROR' in test_responses else "HIGH"
        }


def extract_base_domains_from_clusters(clusters_path: str) -> Set[str]:
    """
    Extract unique base domains from clusters.csv that might be wildcard candidates.

    Looks for patterns like:
    - Multiple subdomains from same base domain
    - Known cloud/SaaS patterns (*.cust.*, *.dev.*, etc.)
    """
    base_domains = set()
    subdomain_counts = Counter()

    try:
        with open(clusters_path, 'r') as f:
            for line in f:
                if 'Domains' in line or not line.strip():
                    continue

                # Extract domains from cluster row
                parts = line.split(',')
                if len(parts) >= 6:
                    domains_str = ','.join(parts[5:])  # Everything after the 5th field

                    # Find all domain-like strings
                    domain_pattern = r'([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}'
                    matches = re.findall(domain_pattern, domains_str)

                    for match in matches:
                        # Extract potential base domains
                        # Look for patterns like x.cust.y.example.io -> example.io
                        parts_dom = match.rstrip('.').split('.')
                        if len(parts_dom) >= 2:
                            base = '.'.join(parts_dom[-2:])
                            subdomain_counts[base] += 1

                            # Also check for multi-level bases like example.io
                            if len(parts_dom) >= 3:
                                base3 = '.'.join(parts_dom[-3:])
                                subdomain_counts[base3] += 1
    except Exception as e:
        ui.print_error(f"Failed to parse clusters.csv: {e}")

    # Return domains with high subdomain counts (potential wildcards)
    for domain, count in subdomain_counts.most_common(50):
        if count >= 5:  # At least 5 subdomains enumerated
            base_domains.add(domain)

    return base_domains


# =============================================================================
# SPIDERFOOT DATA EXTRACTOR
# =============================================================================

class SpiderFootExtractor:
    """Extract subdomains from SpiderFoot CSV exports"""

    def __init__(self, spiderfoot_dir: str):
        self.spiderfoot_dir = Path(spiderfoot_dir)
        self.subdomains: Set[str] = set()
        self.by_zone: Dict[str, Set[str]] = defaultdict(set)

    def extract_for_domain(self, target_domain: str, keywords: Optional[List[str]] = None) -> Dict:
        """
        Extract subdomains related to a target domain from SpiderFoot exports.

        Args:
            target_domain: The base domain to search for (e.g., "example.io")
            keywords: Optional additional keywords to search for

        Returns:
            Dict with subdomains organized by zone/pattern
        """
        search_patterns = [target_domain.lower()]
        if keywords:
            search_patterns.extend([k.lower() for k in keywords])

        csv_files = list(self.spiderfoot_dir.glob("SpiderFoot*.csv"))
        if not csv_files:
            csv_files = list(self.spiderfoot_dir.glob("*.csv"))

        ui.print_info(f"Found {len(csv_files)} SpiderFoot export files")

        for idx, csv_file in enumerate(csv_files):
            ui.progress_bar(idx + 1, len(csv_files), "Scanning")

            try:
                with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line_lower = line.lower()

                        # Check if line contains any of our patterns
                        for pattern in search_patterns:
                            if pattern in line_lower:
                                # Extract potential subdomains
                                self._extract_subdomains_from_line(line, target_domain)
                                break
            except Exception as e:
                ui.print_warning(f"Error reading {csv_file.name}: {e}")

        # Categorize by zone patterns
        self._categorize_zones(target_domain)

        return {
            "total": len(self.subdomains),
            "subdomains": self.subdomains,
            "by_zone": dict(self.by_zone)
        }

    def _extract_subdomains_from_line(self, line: str, target_domain: str):
        """Extract subdomain patterns from a CSV line"""
        # Match subdomains of target domain
        pattern = rf'([a-zA-Z0-9][-a-zA-Z0-9.]*\.{re.escape(target_domain)})'
        matches = re.findall(pattern, line, re.IGNORECASE)

        for match in matches:
            subdomain = match.lower().strip('.')
            if subdomain and len(subdomain) < 200:  # Sanity check
                self.subdomains.add(subdomain)

    def _categorize_zones(self, target_domain: str):
        """Categorize subdomains by zone patterns (dev, prod, etc.)"""
        zone_patterns = ['dev', 'prod', 'staging', 'test', 'disrec', 'cust', 'demo']

        for subdomain in self.subdomains:
            categorized = False
            for zone in zone_patterns:
                if f'.{zone}.' in subdomain or subdomain.startswith(f'{zone}.'):
                    self.by_zone[zone].add(subdomain)
                    categorized = True
                    break

            if not categorized:
                self.by_zone['other'].add(subdomain)


# =============================================================================
# MULTI-ZONE DNS ANALYZER
# =============================================================================

class MultiZoneDNSAnalyzer:
    """
    Analyzes DNS patterns across multiple zones to detect true anomalies.

    Many cloud/SaaS providers use wildcard DNS with different configs per zone:
    - *.cust.dev.example.io -> one wildcard IP
    - *.cust.prod.example.io -> different wildcard IP

    This analyzer establishes baselines per zone and identifies TRUE anomalies.
    """

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
        self.zone_baselines: Dict[str, Dict] = {}
        self.resolver = None

        if HAS_DNSPYTHON:
            self.resolver = dns.resolver.Resolver()
            self.resolver.timeout = timeout
            self.resolver.lifetime = timeout

    def establish_zone_baselines(self, zones: List[str], base_pattern: str) -> Dict[str, Dict]:
        """
        Establish wildcard baselines for each zone.

        Args:
            zones: List of zone names (e.g., ['dev', 'prod', 'disrec'])
            base_pattern: Base pattern like "cust.{zone}.example.io"

        Returns:
            Dict mapping zone -> {"ipv4": str|None, "ipv6": str|None, "is_wildcard": bool}
        """
        ui.print_section("Establishing Multi-Zone Wildcard Baselines")

        for zone in zones:
            ui.print_info(f"Testing zone: *.{base_pattern.format(zone=zone)}")

            ipv4_responses = []
            ipv6_responses = []

            # Test 5 random subdomains per zone
            for _ in range(5):
                random_prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
                test_domain = f"{random_prefix}.{base_pattern.format(zone=zone)}"

                result = self._resolve_domain(test_domain)
                if result['ipv4']:
                    ipv4_responses.extend(result['ipv4'])
                if result['ipv6']:
                    ipv6_responses.extend(result['ipv6'])

            # Find most common response for each type
            ipv4_counter = Counter(ipv4_responses)
            ipv6_counter = Counter(ipv6_responses)

            baseline = {
                'ipv4': ipv4_counter.most_common(1)[0][0] if ipv4_counter else None,
                'ipv6': ipv6_counter.most_common(1)[0][0] if ipv6_counter else None,
                'is_wildcard': bool(ipv4_counter or ipv6_counter),
                'test_count': 5
            }

            self.zone_baselines[zone] = baseline
            ui.print_success(f"  {zone}: IPv4={baseline['ipv4']}, IPv6={baseline['ipv6']}")

        return self.zone_baselines

    def analyze_subdomains(self, subdomains: List[str], zones: List[str], base_pattern: str) -> Dict:
        """
        Analyze subdomains against zone baselines to find TRUE anomalies.

        Args:
            subdomains: List of subdomains to analyze
            zones: Known zone names
            base_pattern: Base pattern for zone detection

        Returns:
            Dict with analysis results
        """
        results = {
            "zone_matches": defaultdict(list),
            "true_anomalies": [],
            "unreachable": [],
            "analyzed": 0
        }

        # Sample if too many subdomains
        sample_size = min(len(subdomains), 300)
        sample = random.sample(list(subdomains), sample_size) if len(subdomains) > sample_size else list(subdomains)

        ui.print_section(f"Analyzing {len(sample)} Subdomains (Multi-Zone)")

        for idx, subdomain in enumerate(sample):
            ui.progress_bar(idx + 1, len(sample), "DNS Probing")

            # Determine which zone this subdomain belongs to
            detected_zone = None
            for zone in zones:
                if f'.{zone}.' in subdomain:
                    detected_zone = zone
                    break

            if not detected_zone:
                detected_zone = 'unknown'

            # Resolve the subdomain
            resolution = self._resolve_domain(subdomain)
            results["analyzed"] += 1

            if resolution['error']:
                results["unreachable"].append(subdomain)
                continue

            # Check against zone baseline
            baseline = self.zone_baselines.get(detected_zone, {})

            is_anomaly = False
            if resolution['ipv4']:
                for ip in resolution['ipv4']:
                    if ip != baseline.get('ipv4'):
                        is_anomaly = True
            if resolution['ipv6']:
                for ip in resolution['ipv6']:
                    if ip != baseline.get('ipv6'):
                        is_anomaly = True

            if is_anomaly and baseline.get('is_wildcard'):
                results["true_anomalies"].append({
                    "subdomain": subdomain,
                    "zone": detected_zone,
                    "resolved": resolution,
                    "expected_baseline": baseline
                })
            else:
                results["zone_matches"][detected_zone].append(subdomain)

        return results

    def _resolve_domain(self, domain: str) -> Dict:
        """Resolve a domain and return IPv4/IPv6 addresses"""
        result = {"ipv4": [], "ipv6": [], "error": None}

        if self.resolver:
            # Use dnspython
            try:
                answers = self.resolver.resolve(domain, 'A')
                result['ipv4'] = sorted([str(rdata) for rdata in answers])
            except Exception:
                pass

            try:
                answers = self.resolver.resolve(domain, 'AAAA')
                result['ipv6'] = sorted([str(rdata) for rdata in answers])
            except Exception:
                pass

            if not result['ipv4'] and not result['ipv6']:
                result['error'] = 'No resolution'
        else:
            # Fallback to socket
            try:
                ip = socket.gethostbyname(domain)
                result['ipv4'] = [ip]
            except Exception as e:
                result['error'] = str(e)

        return result


# =============================================================================
# CERTIFICATE TRANSPARENCY ANALYZER
# =============================================================================

class CertificateAnalyzer:
    """Query Certificate Transparency logs for SSL certificate evidence"""

    def __init__(self):
        self.crt_sh_url = "https://crt.sh/?q={domain}&output=json"
        self.session = requests.Session() if HAS_REQUESTS else None

    def query_ct_logs(self, domain: str, retries: int = 3) -> Dict:
        """
        Query crt.sh for certificate transparency data.

        Args:
            domain: Domain to query (e.g., "example.io")
            retries: Number of retry attempts

        Returns:
            Dict with certificate data
        """
        if not self.session:
            return {"error": "requests library not available", "certificates": []}

        ui.print_section(f"Querying Certificate Transparency for {domain}")

        for attempt in range(retries):
            ui.print_info(f"Attempt {attempt + 1}/{retries}...")

            try:
                url = self.crt_sh_url.format(domain=f"%.{domain}")
                response = self.session.get(url, timeout=30)

                if response.status_code == 200:
                    try:
                        certs = response.json()
                        ui.print_success(f"Found {len(certs)} certificate entries")
                        return self._process_certificates(certs, domain)
                    except json.JSONDecodeError:
                        ui.print_warning("Invalid JSON response, retrying...")
                else:
                    ui.print_warning(f"HTTP {response.status_code}, retrying...")

            except Exception as e:
                ui.print_warning(f"Request failed: {e}")

            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff

        ui.print_error("Certificate Transparency query failed after all retries")
        return {"error": "All retries failed", "certificates": []}

    def _process_certificates(self, certs: List[Dict], domain: str) -> Dict:
        """Process certificate data to extract useful information"""
        subdomains = set()
        issuers = Counter()

        for cert in certs:
            name = cert.get('name_value', '')
            issuer = cert.get('issuer_name', '')

            # Extract subdomains from certificate names
            for name_part in name.split('\n'):
                name_part = name_part.strip().lower()
                if domain.lower() in name_part:
                    subdomains.add(name_part)

            if issuer:
                issuers[issuer] += 1

        return {
            "total_certs": len(certs),
            "unique_subdomains": len(subdomains),
            "subdomains": list(subdomains)[:100],  # Limit output
            "top_issuers": issuers.most_common(5),
            "error": None
        }


# =============================================================================
# HTTP FINGERPRINTER
# =============================================================================

class HTTPFingerprinter:
    """Probe HTTP endpoints to identify unique vs wildcard responses"""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.session = requests.Session() if HAS_REQUESTS else None
        if self.session:
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (compatible; SecurityResearch/1.0)'
            })

    def fingerprint_endpoints(self, subdomains: List[str], sample_size: int = 30) -> Dict:
        """
        Generate HTTP response fingerprints for a sample of subdomains.

        Args:
            subdomains: List of subdomains to probe
            sample_size: Maximum number to probe

        Returns:
            Dict with fingerprint analysis
        """
        if not self.session:
            return {"error": "requests library not available", "fingerprints": {}}

        sample = random.sample(list(subdomains), min(len(subdomains), sample_size))

        ui.print_section(f"HTTP Fingerprinting ({len(sample)} endpoints)")

        fingerprints = {}
        response_hashes = Counter()

        for idx, subdomain in enumerate(sample):
            ui.progress_bar(idx + 1, len(sample), "Probing")

            fp = self._probe_endpoint(subdomain)
            fingerprints[subdomain] = fp

            if fp.get('hash'):
                response_hashes[fp['hash']] += 1

        # Identify unique responses (potential real services)
        unique_responses = [sub for sub, fp in fingerprints.items()
                          if fp.get('hash') and response_hashes[fp['hash']] == 1]

        return {
            "probed": len(sample),
            "reachable": sum(1 for fp in fingerprints.values() if fp.get('status_code')),
            "unique_responses": unique_responses,
            "fingerprints": fingerprints,
            "response_distribution": response_hashes.most_common(10)
        }

    def _probe_endpoint(self, subdomain: str) -> Dict:
        """Probe a single endpoint and generate fingerprint"""
        result = {"status_code": None, "hash": None, "headers": {}, "error": None}

        for protocol in ['https', 'http']:
            try:
                url = f"{protocol}://{subdomain}/"
                # Note: verify=True is the secure default. Set to False only if you need
                # to probe domains with self-signed certificates and accept the MITM risk.
                response = self.session.get(url, timeout=self.timeout,
                                           allow_redirects=False, verify=True)

                result['status_code'] = response.status_code
                result['headers'] = dict(response.headers)

                # Generate content hash
                content_hash = hashlib.md5(response.content[:4096]).hexdigest()[:16]
                result['hash'] = f"{response.status_code}:{content_hash}"

                return result

            except Exception as e:
                result['error'] = str(e)

        return result


# =============================================================================
# INFRASTRUCTURE CORRELATOR
# =============================================================================

class InfrastructureCorrelator:
    """Correlate target domain infrastructure with sock puppet domains"""

    def __init__(self):
        self.target_ips: Set[str] = set()
        self.shared_hosting_providers = {
            '198.185.159.': 'Squarespace',
            '198.49.23.': 'Squarespace',
            '104.16.': 'Cloudflare',
            '104.17.': 'Cloudflare',
            '104.18.': 'Cloudflare',
            '104.19.': 'Cloudflare',
            '104.20.': 'Cloudflare',
            '13.': 'AWS',
            '52.': 'AWS',
            '54.': 'AWS',
            '104.40.': 'Azure',
            '40.': 'Azure',
            '35.': 'Google Cloud'
        }

    def map_target_infrastructure(self, target_domains: List[str]) -> Set[str]:
        """Map all IPs used by target domains"""
        ui.print_section("Mapping Target Infrastructure")

        for domain in target_domains:
            try:
                ips = socket.gethostbyname_ex(domain)[2]
                for ip in ips:
                    self.target_ips.add(ip)
                    ui.print_info(f"{domain} -> {ips}")
            except Exception as e:
                ui.print_warning(f"{domain} -> DNS lookup failed")

        ui.print_success(f"Total unique target IPs: {len(self.target_ips)}")
        return self.target_ips

    def check_sock_puppet_overlap(self, sock_puppets: List[str]) -> Dict:
        """
        Check if sock puppet domains share IPs with target infrastructure.

        Returns overlapping domains with shared hosting context.
        """
        ui.print_section(f"Checking {len(sock_puppets)} Sock Puppet Domains")

        overlaps = []

        def check_domain(domain: str) -> Optional[Dict]:
            try:
                ips = socket.gethostbyname_ex(domain)[2]
                shared = [ip for ip in ips if ip in self.target_ips]

                if shared:
                    # Check if shared hosting
                    is_shared_hosting = False
                    provider = None
                    for ip in shared:
                        for prefix, prov in self.shared_hosting_providers.items():
                            if ip.startswith(prefix):
                                is_shared_hosting = True
                                provider = prov
                                break

                    return {
                        "domain": domain,
                        "shared_ips": shared,
                        "is_shared_hosting": is_shared_hosting,
                        "hosting_provider": provider
                    }
            except Exception:
                pass
            return None

        # Parallel checking
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(check_domain, d): d for d in sock_puppets}

            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 50 == 0 or completed == len(sock_puppets):
                    ui.progress_bar(completed, len(sock_puppets), "Checking")

                result = future.result()
                if result:
                    overlaps.append(result)

        # Categorize results
        meaningful_overlaps = [o for o in overlaps if not o['is_shared_hosting']]
        shared_hosting_overlaps = [o for o in overlaps if o['is_shared_hosting']]

        if meaningful_overlaps:
            ui.print_critical(f"Found {len(meaningful_overlaps)} domains sharing DEDICATED IPs with target!")
            for o in meaningful_overlaps[:10]:
                ui.print_anomaly(f"{o['domain']} shares: {o['shared_ips']}")

        if shared_hosting_overlaps:
            ui.print_warning(f"{len(shared_hosting_overlaps)} domains share IPs via shared hosting (likely false positive)")

        return {
            "total_checked": len(sock_puppets),
            "meaningful_overlaps": meaningful_overlaps,
            "shared_hosting_overlaps": shared_hosting_overlaps,
            "total_overlaps": len(overlaps)
        }


# =============================================================================
# MAIN ANALYZER CLASS
# =============================================================================

class WildcardAnalyzer:
    """
    Main orchestrator for wildcard DNS analysis.

    Combines all analysis modules for comprehensive investigation.
    """

    def __init__(self,
                 domain: str,
                 spiderfoot_dir: Optional[str] = None,
                 keywords: Optional[List[str]] = None,
                 sock_puppets: Optional[List[str]] = None,
                 output_dir: Optional[str] = None):
        """
        Initialize the analyzer.

        Args:
            domain: Target domain to analyze (e.g., "example.io")
            spiderfoot_dir: Directory containing SpiderFoot CSV exports
            keywords: Additional keywords to search for in exports
            sock_puppets: List of sock puppet domains for correlation
            output_dir: Directory to save reports
        """
        self.domain = domain
        self.spiderfoot_dir = spiderfoot_dir
        self.keywords = keywords or []
        self.sock_puppets = sock_puppets or []
        self.output_dir = Path(output_dir) if output_dir else Path("./output")

        # Analysis results
        self.results: Dict[str, Any] = {
            "target_domain": domain,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }

        # Initialize analyzers
        self.dns_analyzer = MultiZoneDNSAnalyzer()
        self.cert_analyzer = CertificateAnalyzer()
        self.http_fingerprinter = HTTPFingerprinter()
        self.infra_correlator = InfrastructureCorrelator()

    def run_quick_check(self) -> Dict:
        """Run quick wildcard check only"""
        ui.print_phase(1, "Quick Wildcard Check", total=1)

        result = quick_wildcard_check([self.domain])
        self.results["quick_check"] = result

        if result[self.domain]["is_wildcard"]:
            ui.print_warning(f"{self.domain} has wildcard DNS (IP: {result[self.domain]['wildcard_ip']})")
        else:
            ui.print_success(f"{self.domain} does NOT have wildcard DNS")

        return result

    def run_full_analysis(self) -> Dict:
        """Run comprehensive wildcard DNS analysis"""
        ui.clear_screen()
        ui.print_banner()

        total_phases = 6

        # Phase 1: Quick Check
        ui.print_phase(1, "Quick Wildcard Detection", total=total_phases)
        quick_result = quick_wildcard_check([self.domain])
        self.results["quick_check"] = quick_result

        if quick_result[self.domain]["is_wildcard"]:
            ui.print_warning(f"Wildcard DNS detected: {quick_result[self.domain]['wildcard_ip']}")
        else:
            ui.print_success("No simple wildcard detected - checking multi-zone patterns...")

        # Phase 2: Extract Subdomains from SpiderFoot
        ui.print_phase(2, "SpiderFoot Data Extraction", total=total_phases)

        subdomains = set()
        zones = []

        if self.spiderfoot_dir:
            extractor = SpiderFootExtractor(self.spiderfoot_dir)
            sf_data = extractor.extract_for_domain(self.domain, self.keywords)
            subdomains = sf_data["subdomains"]
            zones = list(sf_data["by_zone"].keys())

            ui.print_success(f"Extracted {len(subdomains)} subdomains")
            for zone, subs in sf_data["by_zone"].items():
                ui.print_info(f"  Zone '{zone}': {len(subs)} subdomains")

            self.results["spiderfoot_extraction"] = {
                "total_subdomains": len(subdomains),
                "zones": {z: len(s) for z, s in sf_data["by_zone"].items()}
            }
        else:
            ui.print_warning("No SpiderFoot directory provided - skipping extraction")

        # Phase 3: Multi-Zone DNS Analysis
        ui.print_phase(3, "Multi-Zone DNS Analysis", total=total_phases)

        if zones and subdomains:
            # Detect zone pattern
            base_pattern = self._detect_zone_pattern(subdomains)

            if base_pattern:
                self.dns_analyzer.establish_zone_baselines(zones, base_pattern)
                dns_results = self.dns_analyzer.analyze_subdomains(list(subdomains), zones, base_pattern)

                self.results["dns_analysis"] = {
                    "zone_baselines": self.dns_analyzer.zone_baselines,
                    "true_anomalies": len(dns_results["true_anomalies"]),
                    "zone_matches": {z: len(s) for z, s in dns_results["zone_matches"].items()}
                }

                if dns_results["true_anomalies"]:
                    ui.print_critical(f"Found {len(dns_results['true_anomalies'])} TRUE anomalies!")
                    for anomaly in dns_results["true_anomalies"][:5]:
                        ui.print_anomaly(f"{anomaly['subdomain']}")
                else:
                    ui.print_success("No true anomalies - all responses match zone wildcards")
            else:
                ui.print_warning("Could not detect zone pattern")
        else:
            ui.print_warning("Insufficient data for multi-zone analysis")

        # Phase 4: Certificate Transparency
        ui.print_phase(4, "Certificate Transparency", total=total_phases)

        ct_results = self.cert_analyzer.query_ct_logs(self.domain)
        self.results["certificate_transparency"] = ct_results

        if not ct_results.get("error"):
            # Check for construction-related keywords in certs
            construction_keywords = ["estimat", "takeoff", "construct", "bid", "quantity"]
            construction_certs = []

            for sub in ct_results.get("subdomains", []):
                for kw in construction_keywords:
                    if kw in sub.lower():
                        construction_certs.append(sub)
                        break

            if construction_certs:
                ui.print_warning(f"Found {len(construction_certs)} construction-related SSL certs!")
            else:
                ui.print_success("No construction-related subdomains have explicit SSL certs")

        # Phase 5: HTTP Fingerprinting
        ui.print_phase(5, "HTTP Fingerprinting", total=total_phases)

        if subdomains:
            http_results = self.http_fingerprinter.fingerprint_endpoints(list(subdomains))
            self.results["http_fingerprinting"] = {
                "probed": http_results["probed"],
                "reachable": http_results["reachable"],
                "unique_responses": len(http_results["unique_responses"])
            }

            if http_results["unique_responses"]:
                ui.print_warning(f"Found {len(http_results['unique_responses'])} unique HTTP responses!")
            else:
                ui.print_success("No unique HTTP responses - consistent wildcard behavior")
        else:
            ui.print_warning("No subdomains to fingerprint")

        # Phase 6: Infrastructure Correlation
        ui.print_phase(6, "Infrastructure Correlation", total=total_phases)

        if self.sock_puppets:
            # Map target infrastructure
            target_domains = [
                self.domain,
                f"www.{self.domain}",
                self.domain.replace('.io', '.com'),
                self.domain.replace('.io', '.ch'),
            ]
            self.infra_correlator.map_target_infrastructure(target_domains)

            # Check sock puppet overlap
            overlap_results = self.infra_correlator.check_sock_puppet_overlap(self.sock_puppets)
            self.results["infrastructure_correlation"] = overlap_results
        else:
            ui.print_warning("No sock puppet domains provided for correlation")

        # Generate final assessment
        self._generate_assessment()

        # Save reports
        self._save_reports()

        return self.results

    def _detect_zone_pattern(self, subdomains: Set[str]) -> Optional[str]:
        """Detect the zone pattern from subdomains (e.g., cust.{zone}.domain.io)"""
        # Look for common patterns
        zone_patterns = ['dev', 'prod', 'staging', 'test', 'disrec']

        for sub in list(subdomains)[:100]:
            for zone in zone_patterns:
                pattern = rf'\.cust\.{zone}\.{re.escape(self.domain)}'
                if re.search(pattern, sub):
                    return f"cust.{{zone}}.{self.domain}"

                pattern = rf'\.{zone}\.{re.escape(self.domain)}'
                if re.search(pattern, sub):
                    return f"{{zone}}.{self.domain}"

        return None

    def _generate_assessment(self):
        """Generate final threat assessment"""
        ui.print_section("Final Assessment")

        score = 0
        indicators = []

        # Check quick wildcard result
        quick = self.results.get("quick_check", {}).get(self.domain, {})
        if quick.get("is_wildcard"):
            score -= 20
            indicators.append("- Wildcard DNS confirmed (expected for SaaS)")

        # Check for true anomalies
        dns = self.results.get("dns_analysis", {})
        if dns.get("true_anomalies", 0) > 0:
            score += 30
            indicators.append(f"+ {dns['true_anomalies']} TRUE DNS anomalies detected")
        else:
            score -= 10
            indicators.append("- No DNS anomalies (all match wildcards)")

        # Check certificate transparency
        ct = self.results.get("certificate_transparency", {})
        if ct.get("error"):
            indicators.append("? Certificate transparency unavailable")

        # Check infrastructure overlap
        infra = self.results.get("infrastructure_correlation", {})
        meaningful = len(infra.get("meaningful_overlaps", []))
        if meaningful > 0:
            score += 40
            indicators.append(f"+ CRITICAL: {meaningful} sock puppets share DEDICATED IPs")

        shared = len(infra.get("shared_hosting_overlaps", []))
        if shared > 0 and meaningful == 0:
            indicators.append(f"- {shared} overlaps are shared hosting (false positive)")

        # Normalize score
        score = max(0, min(100, 50 + score))

        self.results["assessment"] = {
            "suspicion_score": score,
            "indicators": indicators,
            "recommendation": self._get_recommendation(score)
        }

        # Display
        if score >= 70:
            threat_level = f"{C.RED}HIGH THREAT{C.RESET}"
        elif score >= 40:
            threat_level = f"{C.YELLOW}MEDIUM THREAT{C.RESET}"
        else:
            threat_level = f"{C.GREEN}LOW THREAT{C.RESET}"

        print(f"\n  {C.BOLD}SUSPICION SCORE: {threat_level} ({score}/100){C.RESET}\n")

        for indicator in indicators:
            if indicator.startswith('+'):
                print(f"  {C.RED}{indicator}{C.RESET}")
            elif indicator.startswith('-'):
                print(f"  {C.GREEN}{indicator}{C.RESET}")
            else:
                print(f"  {C.YELLOW}{indicator}{C.RESET}")

    def _get_recommendation(self, score: int) -> str:
        if score >= 70:
            return "HIGH PRIORITY: Investigate immediately. Evidence suggests real infrastructure hiding behind wildcard."
        elif score >= 40:
            return "MEDIUM: Monitor and gather more data. Some suspicious indicators but inconclusive."
        else:
            return "LOW: Likely legitimate wildcard DNS. Safe to exclude from sock puppet analysis."

    def _save_reports(self):
        """Save analysis reports"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON data
        json_path = self.output_dir / f"wildcard_analysis_{self.domain}_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        ui.print_success(f"Report saved: {json_path}")

        # Markdown report
        md_path = self.output_dir / f"wildcard_analysis_{self.domain}_{timestamp}.md"
        self._write_markdown_report(md_path)

        ui.print_success(f"Markdown saved: {md_path}")

    def _write_markdown_report(self, path: Path):
        """Generate markdown report"""
        assessment = self.results.get("assessment", {})

        report = f"""# SIGNAL//NOISE Wildcard DNS Analysis Report

## Target: {self.domain}
## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Executive Summary

**Suspicion Score: {assessment.get('suspicion_score', 'N/A')}/100**

{assessment.get('recommendation', '')}

### Key Indicators

"""
        for indicator in assessment.get('indicators', []):
            report += f"- {indicator}\n"

        report += f"""

---

## Quick Wildcard Check

"""
        quick = self.results.get("quick_check", {}).get(self.domain, {})
        report += f"- **Is Wildcard:** {quick.get('is_wildcard', 'Unknown')}\n"
        report += f"- **Wildcard IP:** {quick.get('wildcard_ip', 'N/A')}\n"
        report += f"- **Confidence:** {quick.get('confidence', 'Unknown')}\n"

        report += """

---

## Recommendations

"""
        if assessment.get('suspicion_score', 0) < 40:
            report += "This domain can be safely excluded from sock puppet analysis.\n"
            report += "The wildcard DNS pattern is consistent with legitimate SaaS infrastructure.\n"
        else:
            report += "Further investigation recommended.\n"

        report += """

---

*Report generated by SIGNAL//NOISE Wildcard DNS Analyzer v1.0*
*Part of the PUPPETMASTER sock puppet detection toolkit*
"""

        with open(path, 'w') as f:
            f.write(report)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """
    Main entry point.

    - Called with no arguments: Show interactive menu
    - Called with --domain: Run in CLI mode
    """
    # Check if any arguments provided (besides script name)
    if len(sys.argv) == 1:
        # No arguments - show interactive menu
        try:
            interactive_menu()
        except KeyboardInterrupt:
            print(f"\n\n{C.CYAN}[i]{C.RESET} {C.DIM}Interrupted. Exiting...{C.RESET}\n")
        return

    # Arguments provided - run in CLI mode
    parser = argparse.ArgumentParser(
        description='SIGNAL//NOISE - Wildcard DNS Analyzer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Interactive mode (no arguments):
    python3 wildcardDNS_analyzer.py

  Quick check a domain:
    python3 wildcardDNS_analyzer.py --domain example.io

  Full analysis with SpiderFoot data:
    python3 wildcardDNS_analyzer.py --domain example.io --spiderfoot-dir ./exports --full

  With sock puppet correlation:
    python3 wildcardDNS_analyzer.py --domain example.io --sock-puppets domains.txt --full
        """
    )

    parser.add_argument('--domain', '-d', required=True,
                        help='Target domain to analyze (required for CLI mode)')
    parser.add_argument('--spiderfoot-dir', '-s',
                        help='Directory containing SpiderFoot CSV exports')
    parser.add_argument('--keywords', '-k',
                        help='Comma-separated keywords to search for')
    parser.add_argument('--sock-puppets', '-p',
                        help='File containing sock puppet domains (one per line)')
    parser.add_argument('--output-dir', '-o', default='./output',
                        help='Output directory for reports')
    parser.add_argument('--full', '-f', action='store_true',
                        help='Run full analysis (not just quick check)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Minimal output')

    args = parser.parse_args()

    # Parse keywords
    keywords = args.keywords.split(',') if args.keywords else None

    # Load sock puppets
    sock_puppets = []
    if args.sock_puppets:
        try:
            with open(args.sock_puppets, 'r') as f:
                sock_puppets = [line.strip() for line in f if line.strip()]
        except Exception as e:
            ui.print_error(f"Failed to load sock puppets: {e}")

    # Create analyzer
    analyzer = WildcardAnalyzer(
        domain=args.domain,
        spiderfoot_dir=args.spiderfoot_dir,
        keywords=keywords,
        sock_puppets=sock_puppets,
        output_dir=args.output_dir
    )

    # Run analysis
    if args.full:
        results = analyzer.run_full_analysis()
    else:
        if not args.quiet:
            ui.print_banner(mini=True)
        results = analyzer.run_quick_check()

    # Print final status
    if not args.quiet:
        print(f"\n{C.CYAN}+{'-' * 50}+{C.RESET}")
        print(f"{C.CYAN}|  Analysis Complete{' ' * 31}|{C.RESET}")
        print(f"{C.CYAN}+{'-' * 50}+{C.RESET}\n")


if __name__ == "__main__":
    main()
