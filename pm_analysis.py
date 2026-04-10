"""pm_analysis.py - Analysis Pipeline & Wildcard DNS Analyzer"""
import os
import sys
import subprocess
import time
from pathlib import Path

from pm_config import load_config, save_config, remember_output_dir, get_remembered_output_dirs, CONFIG_FILE
from pm_paths import get_data_directory, get_output_directory
from pm_results import find_results_directories
from pm_ui_helpers import (
    C, clear_screen, print_banner, print_section, print_menu_item,
    print_success, print_error, print_warning, print_info,
    get_input, confirm, animated_print,
)

# Try to import cyberpunk UI components
try:
    from ui.cyberpunk_ui import (
        cyber_header, cyber_info, cyber_success,
        cyber_warning, cyber_error, cyber_confirm,
        get_console,
        cyber_banner_analysis, cyber_banner_wildcard,
    )
    CYBER_UI_AVAILABLE = True
except ImportError:
    CYBER_UI_AVAILABLE = False

# Hunting/completion messages for animated output
try:
    from utils.display import HUNTING_MESSAGES, COMPLETION_MESSAGES
except ImportError:
    HUNTING_MESSAGES = ["🔍 Hunting for sock puppets...", "🕵️ Following the breadcrumbs..."]
    COMPLETION_MESSAGES = ["🎉 Analysis complete!", "✨ Puppet strings revealed!"]


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
