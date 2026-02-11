#!/usr/bin/env python3
"""
INFRA - Infrastructure Correlation Analyzer

Analyzes infrastructure patterns across multiple domains to detect
hidden connections indicating common ownership/operation.

Supports both CLI arguments and interactive mode.
"""

import argparse
import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# =============================================================================
# CYBERPUNK COLOR SCHEME
# =============================================================================

class C:
    """Dark cyberpunk color palette"""
    # Core colors
    BLACK = '\033[30m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

    # Neon accents
    NEON_PINK = '\033[38;5;198m'
    NEON_CYAN = '\033[38;5;51m'
    NEON_GREEN = '\033[38;5;46m'
    NEON_ORANGE = '\033[38;5;208m'
    NEON_PURPLE = '\033[38;5;129m'
    NEON_RED = '\033[38;5;196m'

    # Dark tones
    DARK_GRAY = '\033[38;5;238m'
    MED_GRAY = '\033[38;5;244m'
    LIGHT_GRAY = '\033[38;5;250m'

    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    RESET = '\033[0m'

    # Background
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_DARK = '\033[48;5;234m'


# =============================================================================
# ASCII ART & VISUALS
# =============================================================================

BANNER_MAIN = f"""
{C.NEON_CYAN}
    ██╗███╗   ██╗███████╗██████╗  █████╗
    ██║████╗  ██║██╔════╝██╔══██╗██╔══██╗
    ██║██╔██╗ ██║█████╗  ██████╔╝███████║
    ██║██║╚██╗██║██╔══╝  ██╔══██╗██╔══██║
    ██║██║ ╚████║██║     ██║  ██║██║  ██║
    ╚═╝╚═╝  ╚═══╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝{C.RESET}
{C.NEON_PINK}    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀{C.RESET}
{C.DIM}{C.WHITE}    INFRASTRUCTURE CORRELATION ANALYZER{C.RESET}
{C.DARK_GRAY}    [ Supplementary Sock Puppet Detection ]{C.RESET}
"""

BANNER_MINI = f"""
{C.NEON_CYAN}╔══════════════════════════════════════════╗
║{C.RESET} {C.BOLD}INFRA{C.RESET} {C.DIM}// Infrastructure Analyzer{C.RESET}        {C.NEON_CYAN}║
╚══════════════════════════════════════════╝{C.RESET}
"""

SKULL = f"""{C.NEON_RED}
      ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
      ░░░░░░▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄░░░░░░
      ░░░░░█░░░░░░░░░░░░░░░░░█░░░░░
      ░░░░░█░░░░░░░░░░░░░░░░░█░░░░░
      ░░░░░█░░░░░░░░░░░░░░░░░█░░░░░
      ░░░░░░▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀░░░░░░
{C.RESET}"""

SCAN_FRAMES = [
    f"{C.NEON_CYAN}[■□□□□□□□□□]{C.RESET}",
    f"{C.NEON_CYAN}[■■□□□□□□□□]{C.RESET}",
    f"{C.NEON_CYAN}[■■■□□□□□□□]{C.RESET}",
    f"{C.NEON_CYAN}[■■■■□□□□□□]{C.RESET}",
    f"{C.NEON_CYAN}[■■■■■□□□□□]{C.RESET}",
    f"{C.NEON_CYAN}[■■■■■■□□□□]{C.RESET}",
    f"{C.NEON_CYAN}[■■■■■■■□□□]{C.RESET}",
    f"{C.NEON_CYAN}[■■■■■■■■□□]{C.RESET}",
    f"{C.NEON_CYAN}[■■■■■■■■■□]{C.RESET}",
    f"{C.NEON_CYAN}[■■■■■■■■■■]{C.RESET}",
]


def box(title: str, content: list, width: int = 60, accent: str = C.NEON_CYAN) -> str:
    """Create a styled box with title and content"""
    lines = []
    lines.append(f"{accent}╔{'═' * (width-2)}╗{C.RESET}")

    # Title bar
    title_padded = f" {title} ".center(width-2)
    lines.append(f"{accent}║{C.RESET}{C.BOLD}{title_padded}{C.RESET}{accent}║{C.RESET}")
    lines.append(f"{accent}╠{'═' * (width-2)}╣{C.RESET}")

    # Content
    for line in content:
        # Strip ANSI for length calculation
        import re
        clean = re.sub(r'\033\[[0-9;]*m', '', line)
        padding = width - 4 - len(clean)
        lines.append(f"{accent}║{C.RESET}  {line}{' ' * max(0, padding)}{accent}║{C.RESET}")

    lines.append(f"{accent}╚{'═' * (width-2)}╝{C.RESET}")
    return '\n'.join(lines)


def hline(char: str = '─', width: int = 60, color: str = C.DARK_GRAY) -> str:
    """Horizontal line"""
    return f"{color}{char * width}{C.RESET}"


def menu_option(key: str, label: str, desc: str = "") -> str:
    """Format a menu option"""
    if desc:
        return f"  {C.NEON_CYAN}[{key}]{C.RESET} {C.WHITE}{label}{C.RESET} {C.DARK_GRAY}// {desc}{C.RESET}"
    return f"  {C.NEON_CYAN}[{key}]{C.RESET} {C.WHITE}{label}{C.RESET}"


def prompt(text: str) -> str:
    """Styled input prompt"""
    return f"{C.NEON_PINK}>{C.RESET} {C.WHITE}{text}{C.RESET} "


def status(stype: str, msg: str) -> str:
    """Formatted status message"""
    icons = {
        'info': f"{C.NEON_CYAN}[i]{C.RESET}",
        'ok': f"{C.NEON_GREEN}[✓]{C.RESET}",
        'warn': f"{C.NEON_ORANGE}[!]{C.RESET}",
        'error': f"{C.NEON_RED}[✗]{C.RESET}",
        'scan': f"{C.NEON_PURPLE}[~]{C.RESET}",
        'data': f"{C.NEON_CYAN}[◆]{C.RESET}",
    }
    icon = icons.get(stype, f"{C.WHITE}[*]{C.RESET}")
    return f"  {icon} {msg}"


def clear_screen():
    """Clear terminal"""
    os.system('cls' if os.name == 'nt' else 'clear')


def typing_effect(text: str, delay: float = 0.02):
    """Typewriter effect for dramatic text"""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


# =============================================================================
# INTERACTIVE MODE
# =============================================================================

def interactive_mode():
    """Full interactive menu system"""
    from kali.modes import ScanMode
    from kali.infra_analyzer import InfrastructureAnalyzer, run_infra_analysis

    clear_screen()
    print(BANNER_MAIN)
    time.sleep(0.5)

    # Welcome message
    print(f"\n{C.DIM}  Initializing infrastructure analysis protocols...{C.RESET}")
    time.sleep(0.3)
    print(status('ok', f"{C.GREEN}System ready{C.RESET}"))
    print()

    while True:
        # Main menu
        print(hline('═', 55, C.NEON_CYAN))
        print(f"  {C.BOLD}{C.WHITE}MAIN MENU{C.RESET}")
        print(hline('─', 55, C.DARK_GRAY))
        print()
        print(menu_option('1', 'Analyze Domains', 'Run infrastructure correlation'))
        print(menu_option('2', 'Quick Scan', 'Single domain deep scan'))
        print(menu_option('3', 'Scan Mode', 'Configure scan intensity'))
        print(menu_option('4', 'About', 'What does this tool do?'))
        print(menu_option('q', 'Exit', 'Terminate session'))
        print()
        print(hline('═', 55, C.NEON_CYAN))

        choice = input(prompt("Select")).strip().lower()

        if choice == 'q' or choice == 'exit':
            print(f"\n{C.NEON_RED}  [SESSION TERMINATED]{C.RESET}\n")
            break

        elif choice == '1':
            run_analysis_menu()

        elif choice == '2':
            run_quick_scan()

        elif choice == '3':
            configure_mode()

        elif choice == '4':
            show_about()

        else:
            print(status('warn', f"Unknown command: {choice}"))
            time.sleep(0.5)

        print()


def run_analysis_menu():
    """Domain analysis submenu"""
    from kali.modes import ScanMode
    from kali.infra_analyzer import run_infra_analysis

    clear_screen()
    print(BANNER_MINI)

    content = [
        f"{C.WHITE}Select domain input method:{C.RESET}",
        "",
        f"{C.NEON_CYAN}[1]{C.RESET} Load from file",
        f"{C.NEON_CYAN}[2]{C.RESET} Enter manually",
        f"{C.NEON_CYAN}[3]{C.RESET} Paste list",
        f"{C.NEON_CYAN}[b]{C.RESET} Back",
    ]
    print(box("INPUT SOURCE", content, accent=C.NEON_PURPLE))
    print()

    choice = input(prompt("Method")).strip().lower()

    domains = []

    if choice == 'b':
        return

    elif choice == '1':
        # File input
        print()
        print(status('info', "Enter path to domains file"))
        print(f"  {C.DARK_GRAY}Format: one domain per line, # for comments{C.RESET}")
        print()
        filepath = input(prompt("Path")).strip()

        if not filepath or not os.path.exists(filepath):
            print(status('error', f"File not found: {filepath}"))
            input(f"\n  {C.DIM}Press Enter...{C.RESET}")
            return

        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip().lower()
                    if line and not line.startswith('#'):
                        domains.append(line)
            print(status('ok', f"Loaded {len(domains)} domains"))
        except Exception as e:
            print(status('error', f"Read error: {e}"))
            input(f"\n  {C.DIM}Press Enter...{C.RESET}")
            return

    elif choice == '2':
        # Manual entry
        print()
        print(status('info', "Enter domains (one per line, empty line when done)"))
        print()
        while True:
            d = input(f"  {C.NEON_CYAN}>{C.RESET} ").strip().lower()
            if not d:
                if domains:
                    break
                print(f"  {C.DARK_GRAY}Enter at least one domain{C.RESET}")
                continue
            domains.append(d)

    elif choice == '3':
        # Paste list
        print()
        print(status('info', "Paste domains (comma or newline separated)"))
        print(f"  {C.DARK_GRAY}End with empty line{C.RESET}")
        print()
        buffer = []
        while True:
            line = input(f"  {C.NEON_CYAN}|{C.RESET} ").strip()
            if not line:
                break
            buffer.append(line)

        # Parse
        text = ' '.join(buffer)
        for sep in [',', '\n', ' ', ';']:
            text = text.replace(sep, ',')
        for d in text.split(','):
            d = d.strip().lower()
            if d:
                domains.append(d)

    if not domains:
        print(status('error', "No domains specified"))
        input(f"\n  {C.DIM}Press Enter...{C.RESET}")
        return

    # Deduplicate
    domains = list(dict.fromkeys(domains))

    # Show domains
    print()
    print(hline('─', 55))
    print(f"  {C.BOLD}TARGETS: {len(domains)} domains{C.RESET}")
    print(hline('─', 55))
    for i, d in enumerate(domains[:8]):
        print(f"  {C.NEON_CYAN}│{C.RESET} {d}")
    if len(domains) > 8:
        print(f"  {C.DARK_GRAY}│ ... +{len(domains)-8} more{C.RESET}")
    print()

    # Mode selection
    print(status('info', "Select scan mode:"))
    print()
    print(f"  {C.NEON_CYAN}[1]{C.RESET} Ghost    {C.DARK_GRAY}// Passive only, zero contact{C.RESET}")
    print(f"  {C.NEON_CYAN}[2]{C.RESET} Stealth  {C.DARK_GRAY}// Minimal requests{C.RESET}")
    print(f"  {C.NEON_CYAN}[3]{C.RESET} Standard {C.DARK_GRAY}// Balanced (default){C.RESET}")
    print(f"  {C.NEON_CYAN}[4]{C.RESET} Deep     {C.DARK_GRAY}// Maximum coverage{C.RESET}")
    print()

    mode_choice = input(prompt("Mode [3]")).strip() or "3"
    mode_map = {'1': ScanMode.GHOST, '2': ScanMode.STEALTH, '3': ScanMode.STANDARD, '4': ScanMode.DEEP}
    mode = mode_map.get(mode_choice, ScanMode.STANDARD)

    # Output directory
    print()
    output_dir = input(prompt("Output dir [./infra_output]")).strip() or "./infra_output"

    # Confirm
    print()
    print(hline('═', 55, C.NEON_ORANGE))
    print(f"  {C.BOLD}{C.NEON_ORANGE}CONFIRM SCAN{C.RESET}")
    print(hline('─', 55, C.DARK_GRAY))
    print(f"  Targets:  {C.WHITE}{len(domains)} domains{C.RESET}")
    print(f"  Mode:     {C.WHITE}{mode.value}{C.RESET}")
    print(f"  Output:   {C.WHITE}{output_dir}{C.RESET}")
    print(f"  Est Time: {C.DARK_GRAY}~{len(domains) * 30}-{len(domains) * 60}s{C.RESET}")
    print(hline('═', 55, C.NEON_ORANGE))
    print()

    confirm = input(prompt("Execute? [Y/n]")).strip().lower()
    if confirm == 'n':
        print(status('warn', "Scan cancelled"))
        return

    # RUN SCAN
    print()
    print(f"{C.NEON_CYAN}╔{'═'*55}╗{C.RESET}")
    print(f"{C.NEON_CYAN}║{C.RESET} {C.BOLD}EXECUTING INFRASTRUCTURE SCAN{C.RESET}                       {C.NEON_CYAN}║{C.RESET}")
    print(f"{C.NEON_CYAN}╚{'═'*55}╝{C.RESET}")
    print()

    def progress_cb(domain, pstatus, message):
        colors = {
            'starting': C.NEON_PURPLE,
            'scanning': C.NEON_CYAN,
            'complete': C.NEON_GREEN,
            'correlating': C.NEON_PINK,
            'error': C.NEON_RED,
        }
        c = colors.get(pstatus, C.WHITE)
        icon = '◆' if pstatus == 'complete' else '○' if pstatus == 'scanning' else '●'
        print(f"  {c}{icon}{C.RESET} {C.DIM}[{pstatus:11}]{C.RESET} {domain}: {message}")

    try:
        result = run_infra_analysis(
            domains=domains,
            mode=mode,
            output_dir=output_dir,
            progress_callback=progress_cb
        )
    except KeyboardInterrupt:
        print(f"\n{C.NEON_RED}  [SCAN INTERRUPTED]{C.RESET}")
        return
    except Exception as e:
        print(status('error', f"Scan failed: {e}"))
        input(f"\n  {C.DIM}Press Enter...{C.RESET}")
        return

    # RESULTS
    print()
    print(f"{C.NEON_GREEN}╔{'═'*55}╗{C.RESET}")
    print(f"{C.NEON_GREEN}║{C.RESET} {C.BOLD}SCAN COMPLETE{C.RESET}                                       {C.NEON_GREEN}║{C.RESET}")
    print(f"{C.NEON_GREEN}╚{'═'*55}╝{C.RESET}")
    print()

    print(f"  {C.NEON_CYAN}Statistics:{C.RESET}")
    print(f"    Domains scanned:    {result.domains_scanned}")
    print(f"    Domains failed:     {result.domains_failed}")
    print(f"    Correlations found: {C.BOLD}{C.NEON_GREEN}{result.total_correlations}{C.RESET}")

    # Clusters
    clusters = result.get_domain_clusters(min_score=0.5)
    if clusters:
        print()
        print(f"  {C.NEON_ORANGE}Domain Clusters:{C.RESET}")
        for i, cluster in enumerate(clusters[:5], 1):
            print(f"    {C.NEON_CYAN}[{i}]{C.RESET} {', '.join(sorted(cluster))}")

    # Correlations
    if result.correlations:
        print()
        print(f"  {C.NEON_PURPLE}Correlations by type:{C.RESET}")
        from collections import Counter
        counts = Counter(c.signal_type for c in result.correlations)
        for sig, count in counts.most_common(5):
            bar = '█' * min(count, 20)
            print(f"    {sig:25} {C.NEON_CYAN}{bar}{C.RESET} {count}")

    print()
    print(status('ok', f"Reports saved to: {output_dir}/"))

    input(f"\n  {C.DIM}Press Enter to continue...{C.RESET}")


def run_quick_scan():
    """Quick single-domain deep scan"""
    from kali.modes import ScanMode
    from kali.infra_analyzer import InfrastructureAnalyzer

    clear_screen()
    print(BANNER_MINI)

    print()
    print(status('info', "Quick infrastructure scan for a single domain"))
    print()
    domain = input(prompt("Target domain")).strip().lower()

    if not domain:
        return

    print()
    print(f"  {C.NEON_CYAN}Scanning {domain}...{C.RESET}")
    print()

    def progress_cb(d, s, m):
        c = C.NEON_GREEN if s == 'complete' else C.NEON_CYAN
        print(f"  {c}○{C.RESET} {m}")

    analyzer = InfrastructureAnalyzer(mode=ScanMode.STANDARD, progress_callback=progress_cb)

    try:
        result = analyzer.analyze([domain])

        print()
        print(hline('─', 55, C.NEON_GREEN))
        infra = result.domain_infra.get(domain)
        if infra:
            print(f"  {C.BOLD}IPs:{C.RESET}          {', '.join(infra.ips) or 'None'}")
            print(f"  {C.BOLD}Nameservers:{C.RESET}  {', '.join(list(infra.nameservers)[:3]) or 'None'}")
            print(f"  {C.BOLD}MX Servers:{C.RESET}   {', '.join(list(infra.mx_servers)[:3]) or 'None'}")
            print(f"  {C.BOLD}Emails:{C.RESET}       {', '.join(list(infra.emails)[:3]) or 'None'}")
            print(f"  {C.BOLD}Technologies:{C.RESET} {', '.join(list(infra.technologies)[:5]) or 'None'}")
            if infra.ssl_org:
                print(f"  {C.BOLD}SSL Org:{C.RESET}      {infra.ssl_org}")
        print(hline('─', 55, C.NEON_GREEN))
    except Exception as e:
        print(status('error', str(e)))

    input(f"\n  {C.DIM}Press Enter...{C.RESET}")


def configure_mode():
    """Mode configuration"""
    clear_screen()
    print(BANNER_MINI)

    content = [
        f"{C.NEON_CYAN}GHOST{C.RESET}    - Passive only. No target contact.",
        f"           APIs and cached data only.",
        "",
        f"{C.NEON_GREEN}STEALTH{C.RESET}  - Light touch. 1-2 requests/domain.",
        f"           Minimal detection risk.",
        "",
        f"{C.NEON_ORANGE}STANDARD{C.RESET} - Balanced recon. Multiple tools.",
        f"           Good coverage, moderate noise.",
        "",
        f"{C.NEON_RED}DEEP{C.RESET}     - Maximum coverage. All tools.",
        f"           High noise, high data yield.",
    ]
    print(box("SCAN MODES", content, width=55, accent=C.NEON_PURPLE))

    input(f"\n  {C.DIM}Press Enter...{C.RESET}")


def show_about():
    """About information"""
    clear_screen()
    print(BANNER_MAIN)

    content = [
        f"{C.WHITE}INFRA finds hidden infrastructure connections{C.RESET}",
        f"{C.WHITE}between domains that may indicate common{C.RESET}",
        f"{C.WHITE}ownership or operation.{C.RESET}",
        "",
        f"{C.NEON_CYAN}Signals Detected:{C.RESET}",
        f"  {C.DIM}•{C.RESET} Shared IP addresses / ASNs",
        f"  {C.DIM}•{C.RESET} Shared nameservers / mail servers",
        f"  {C.DIM}•{C.RESET} Shared SSL certificates",
        f"  {C.DIM}•{C.RESET} Shared technology stacks",
        f"  {C.DIM}•{C.RESET} Shared emails / document authors",
        "",
        f"{C.NEON_ORANGE}Difference from Puppet Analysis:{C.RESET}",
        f"  {C.DIM}[5] finds identifier sharing (GA/AdSense){C.RESET}",
        f"  {C.DIM}[k5] finds infrastructure sharing{C.RESET}",
    ]
    print(box("ABOUT INFRA", content, width=55, accent=C.NEON_CYAN))

    input(f"\n  {C.DIM}Press Enter...{C.RESET}")


# =============================================================================
# CLI MODE
# =============================================================================

def cli_mode(args):
    """Non-interactive CLI mode"""
    from kali.modes import ScanMode
    from kali.infra_analyzer import run_infra_analysis

    # Load domains
    domains = []
    if args.domains:
        domains = [d.strip().lower() for d in args.domains.split(',')]
    elif args.file:
        try:
            with open(args.file, 'r') as f:
                for line in f:
                    line = line.strip().lower()
                    if line and not line.startswith('#'):
                        domains.append(line)
        except Exception as e:
            print(f"{C.NEON_RED}[ERROR]{C.RESET} Failed to read file: {e}")
            sys.exit(1)

    if not domains:
        print(f"{C.NEON_RED}[ERROR]{C.RESET} No domains specified")
        sys.exit(1)

    # Deduplicate
    domains = list(dict.fromkeys(domains))

    # Parse mode
    mode_map = {'ghost': ScanMode.GHOST, 'stealth': ScanMode.STEALTH,
                'standard': ScanMode.STANDARD, 'deep': ScanMode.DEEP}
    mode = mode_map.get(args.mode, ScanMode.STANDARD)

    # Banner
    if not args.quiet:
        print(BANNER_MINI)
        print(f"  Domains: {len(domains)} | Mode: {mode.value} | Output: {args.output}")
        print()

    # Progress callback
    def progress_cb(domain, pstatus, message):
        if args.quiet:
            return
        c = C.NEON_GREEN if pstatus == 'complete' else C.NEON_CYAN if pstatus == 'scanning' else C.WHITE
        print(f"  {c}○{C.RESET} [{pstatus:11}] {domain}: {message}")

    # Run
    try:
        result = run_infra_analysis(
            domains=domains,
            mode=mode,
            output_dir=args.output,
            progress_callback=progress_cb
        )
    except KeyboardInterrupt:
        print(f"\n{C.NEON_RED}[INTERRUPTED]{C.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{C.NEON_RED}[ERROR]{C.RESET} {e}")
        sys.exit(1)

    # Summary
    if not args.quiet:
        print()
        print(f"{C.NEON_GREEN}[COMPLETE]{C.RESET} {result.total_correlations} correlations found")
        print(f"  Reports saved to: {args.output}/")

    # JSON output if requested
    if args.json:
        import json
        data = {
            'domains': result.domains_analyzed,
            'correlations': result.total_correlations,
            'clusters': [list(c) for c in result.get_domain_clusters()],
        }
        print(json.dumps(data))


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='INFRA - Infrastructure Correlation Analyzer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{C.NEON_CYAN}Examples:{C.RESET}
  %(prog)s                                  # Interactive mode
  %(prog)s -d domain1.com,domain2.com       # CLI mode
  %(prog)s -f domains.txt -m deep           # From file, deep scan
  %(prog)s -f domains.txt -o ./results -q   # Quiet mode
        """
    )

    parser.add_argument('-d', '--domains', help='Comma-separated domains')
    parser.add_argument('-f', '--file', help='File with domains (one per line)')
    parser.add_argument('-o', '--output', default='./infra_output', help='Output directory')
    parser.add_argument('-m', '--mode', choices=['ghost', 'stealth', 'standard', 'deep'],
                        default='standard', help='Scan mode')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    parser.add_argument('--json', action='store_true', help='JSON output summary')
    parser.add_argument('-i', '--interactive', action='store_true', help='Force interactive mode')

    args = parser.parse_args()

    # Decide mode
    if args.interactive or (not args.domains and not args.file):
        interactive_mode()
    else:
        cli_mode(args)


if __name__ == '__main__':
    main()
