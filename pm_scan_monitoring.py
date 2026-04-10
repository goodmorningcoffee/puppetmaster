"""pm_scan_monitoring.py - Scan Execution & Status Monitoring Menus"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

from pm_config import load_config, save_config, remember_output_dir
from pm_paths import get_output_directory
from pm_ui_helpers import (
    C, clear_screen, print_banner, print_section, print_menu_item,
    print_success, print_error, print_warning, print_info,
    get_input, confirm,
)
from pm_background import (
    is_background_scan_running, get_background_scan_stats,
    _update_background_stats, _run_background_scans,
    get_elapsed_time_str, start_background_thread,
)
from pm_domain_discovery import interactive_domain_removal
from pm_help import install_spiderfoot_interactive

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


# NOTE: This function is currently unused (dead code preserved during refactor)
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

        # Check if scan is already running (prevent duplicate threads)
        if is_background_scan_running():
            if CYBER_UI_AVAILABLE:
                cyber_warning("A background scan is already running!")
                cyber_info("Use View Scan Status to check progress, or wait for it to complete.")
            else:
                print_warning("A background scan is already running!")
                print_info("Use View Scan Status to check progress, or wait for it to complete.")
            get_input("\nPress Enter to continue...")
            return

        _update_background_stats(
            running=True,
            completed=0,
            failed=0,
            total=total_pending,
            current_domain=None,
            start_time=datetime.now().isoformat()
        )

        start_background_thread(target=_run_background_scans, args=(scanner, tracker))

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
        if stats['pending'] > 0:
            options.append(('review', f"Review & remove pending domains ({stats['pending']})"))
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
                elif key == 'review':
                    console.print(f"  [bold magenta][{i}][/] [magenta]✎[/] {label}")
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
                elif key == 'review':
                    print(f"  [{i}] {C.BRIGHT_MAGENTA}✎{C.RESET}  {label}")
                elif key == 'retry':
                    print(f"  [{i}] {C.YELLOW}🔄{C.RESET} {label}")
                elif key == 'clear_completed':
                    print(f"  [{i}] {C.GREEN}✓{C.RESET} {label}")
                elif key == 'clear_all':
                    print(f"  [{i}] {C.RED}⚠{C.RESET} {label}")
                else:
                    print(f"  [{i}] {label}")

        choice = get_input(f"\nSelect option [1-{len(options)}]: ", str(len(options)))

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
║   Results:     {results_found:<10} rows found                                 ║
║   File Size:   {file_size_kb:,.1f} KB                                         ║
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

                elif action == 'review':
                    # Get pending domains from tracker
                    pending_jobs = tracker.get_pending()
                    pending_domains = {job.domain for job in pending_jobs}

                    if not pending_domains:
                        if CYBER_UI_AVAILABLE:
                            cyber_warning("No pending domains to review")
                        else:
                            print_warning("No pending domains to review")
                    else:
                        # Use interactive removal
                        original_count = len(pending_domains)
                        remaining_domains = interactive_domain_removal(pending_domains)
                        removed_domains = pending_domains - remaining_domains

                        if removed_domains:
                            # Remove from tracker
                            removed_count = tracker.remove_pending_domains(removed_domains)
                            if CYBER_UI_AVAILABLE:
                                cyber_success(f"Removed {removed_count} domains from queue ({len(remaining_domains)} remaining)")
                            else:
                                print_success(f"Removed {removed_count} domains from queue ({len(remaining_domains)} remaining)")
                        else:
                            if CYBER_UI_AVAILABLE:
                                cyber_info("No domains removed")
                            else:
                                print_info("No domains removed")

                    stats = tracker.get_stats()  # Refresh stats

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
# DOMAIN QUEUE MANAGER
# =============================================================================
def manage_domain_queue_menu():
    """
    Unified menu to manage both loaded domains and scan queue.

    Shows:
    - Loaded domains (config['pending_domains']) - scraped/loaded but not yet in scan queue
    - Scan queue (JobTracker) - actual scan jobs with status tracking
    """
    while True:
        clear_screen()

        # Load current state
        config = load_config()
        loaded_domains = config.get('pending_domains', [])

        try:
            from discovery.jobs import JobTracker
            tracker = JobTracker()
            queue_stats = tracker.get_stats()
        except ImportError:
            tracker = None
            queue_stats = {'total': 0, 'pending': 0, 'running': 0, 'completed': 0, 'failed': 0}

        # Use cyberpunk UI if available
        if CYBER_UI_AVAILABLE:
            console = get_console()
            from rich.panel import Panel
            from rich.text import Text
            from rich.table import Table

            cyber_banner_config()
            cyber_header("DOMAIN QUEUE MANAGER")

            # Loaded domains section
            loaded_text = Text()
            loaded_text.append("LOADED DOMAINS ", style="bold white")
            loaded_text.append("(scraped/imported, not yet in scan queue)\n\n", style="dim")
            loaded_text.append(f"  {len(loaded_domains)} domains loaded\n\n", style="bold cyan")

            if loaded_domains:
                loaded_text.append("  [1] ", style="bold magenta")
                loaded_text.append("Review & remove loaded domains\n", style="white")
                loaded_text.append("  [2] ", style="bold red")
                loaded_text.append("Clear all loaded domains\n", style="white")
                loaded_text.append("  [3] ", style="bold green")
                loaded_text.append("Move to scan queue (add to JobTracker)\n", style="white")
            else:
                loaded_text.append("  [dim]No domains loaded. Use [1] Scrape or [2] Load from file.[/dim]", style="dim")

            console.print(Panel(loaded_text, title="[bold cyan]⟨ LOADED ⟩[/]", border_style="cyan"))
            console.print()

            # Scan queue section
            queue_text = Text()
            queue_text.append("SCAN QUEUE ", style="bold white")
            queue_text.append("(JobTracker - actual scan jobs)\n\n", style="dim")
            queue_text.append(f"  Pending: {queue_stats['pending']}  ", style="cyan")
            queue_text.append(f"Running: {queue_stats['running']}  ", style="yellow")
            queue_text.append(f"Completed: {queue_stats['completed']}  ", style="green")
            queue_text.append(f"Failed: {queue_stats['failed']}\n\n", style="red")

            if queue_stats['total'] > 0:
                if queue_stats['pending'] > 0:
                    queue_text.append("  [4] ", style="bold magenta")
                    queue_text.append(f"Review & remove pending jobs ({queue_stats['pending']})\n", style="white")
                if queue_stats['failed'] > 0:
                    queue_text.append("  [5] ", style="bold yellow")
                    queue_text.append(f"Retry failed jobs ({queue_stats['failed']})\n", style="white")
                if queue_stats['completed'] > 0:
                    queue_text.append("  [6] ", style="bold green")
                    queue_text.append(f"Clear completed jobs ({queue_stats['completed']})\n", style="white")
                queue_text.append("  [7] ", style="bold red")
                queue_text.append("Clear ENTIRE scan queue\n", style="white")
            else:
                queue_text.append("  [dim]Scan queue empty.[/dim]", style="dim")

            console.print(Panel(queue_text, title="[bold yellow]⟨ SCAN QUEUE ⟩[/]", border_style="yellow"))
            console.print()

            console.print("  [bold white][B][/] Back to main menu\n")

        else:
            # Classic UI
            print_banner()
            print_section("Domain Queue Manager", C.BRIGHT_CYAN)

            print(f"""
{C.BRIGHT_CYAN}╔═══════════════════════════════════════════════════════════════════╗
║  LOADED DOMAINS (scraped/imported, not yet in scan queue)         ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║    {len(loaded_domains):>5} domains loaded                                       ║
║                                                                   ║""")

            if loaded_domains:
                print(f"""║    [1] Review & remove loaded domains                             ║
║    [2] Clear all loaded domains                                   ║
║    [3] Move to scan queue (add to JobTracker)                     ║""")
            else:
                print(f"""║    {C.DIM}No domains loaded. Use [1] Scrape or [2] Load from file.{C.RESET}     ║""")

            print(f"""║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝{C.RESET}

{C.BRIGHT_YELLOW}╔═══════════════════════════════════════════════════════════════════╗
║  SCAN QUEUE (JobTracker - actual scan jobs)                       ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║    Pending: {queue_stats['pending']:>4}  Running: {queue_stats['running']:>4}  Completed: {queue_stats['completed']:>4}  Failed: {queue_stats['failed']:>4}  ║
║                                                                   ║""")

            if queue_stats['total'] > 0:
                if queue_stats['pending'] > 0:
                    print(f"║    [4] Review & remove pending jobs ({queue_stats['pending']})                        ║")
                if queue_stats['failed'] > 0:
                    print(f"║    [5] Retry failed jobs ({queue_stats['failed']})                                   ║")
                if queue_stats['completed'] > 0:
                    print(f"║    [6] Clear completed jobs ({queue_stats['completed']})                             ║")
                print(f"║    [7] Clear ENTIRE scan queue                                    ║")
            else:
                print(f"║    {C.DIM}Scan queue empty.{C.RESET}                                              ║")

            print(f"""║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝{C.RESET}

  [B] Back to main menu
""")

        choice = get_input("Select option", "b")
        if choice is None:
            choice = 'b'
        choice = choice.lower()

        if choice in ('b', 'back', 'q', 'quit'):
            break

        elif choice == '1' and loaded_domains:
            # Review & remove loaded domains
            domains_set = set(loaded_domains)
            remaining = interactive_domain_removal(domains_set)
            if len(remaining) < len(domains_set):
                config['pending_domains'] = list(remaining)
                save_config(config)
                if CYBER_UI_AVAILABLE:
                    cyber_success(f"Removed {len(domains_set) - len(remaining)} domains ({len(remaining)} remaining)")
                else:
                    print_success(f"Removed {len(domains_set) - len(remaining)} domains ({len(remaining)} remaining)")
            get_input("\nPress Enter to continue...")

        elif choice == '2' and loaded_domains:
            # Clear all loaded domains
            do_clear = cyber_confirm(f"Clear all {len(loaded_domains)} loaded domains?", default=False) if CYBER_UI_AVAILABLE else confirm(f"Clear all {len(loaded_domains)} loaded domains?", default=False)
            if do_clear:
                config['pending_domains'] = []
                save_config(config)
                if CYBER_UI_AVAILABLE:
                    cyber_success("Cleared all loaded domains")
                else:
                    print_success("Cleared all loaded domains")
            get_input("\nPress Enter to continue...")

        elif choice == '3' and loaded_domains:
            # Move loaded domains to scan queue
            if tracker:
                added = tracker.add_domains(loaded_domains)
                config['pending_domains'] = []
                save_config(config)
                if CYBER_UI_AVAILABLE:
                    cyber_success(f"Added {added} domains to scan queue (duplicates skipped)")
                else:
                    print_success(f"Added {added} domains to scan queue (duplicates skipped)")
            else:
                if CYBER_UI_AVAILABLE:
                    cyber_error("JobTracker not available")
                else:
                    print_error("JobTracker not available")
            get_input("\nPress Enter to continue...")

        elif choice == '4' and queue_stats['pending'] > 0:
            # Review & remove pending jobs
            if tracker:
                pending_jobs = tracker.get_pending()
                pending_domains = {job.domain for job in pending_jobs}
                if pending_domains:
                    remaining = interactive_domain_removal(pending_domains)
                    removed = pending_domains - remaining
                    if removed:
                        removed_count = tracker.remove_pending_domains(removed)
                        if CYBER_UI_AVAILABLE:
                            cyber_success(f"Removed {removed_count} domains from scan queue")
                        else:
                            print_success(f"Removed {removed_count} domains from scan queue")
            get_input("\nPress Enter to continue...")

        elif choice == '5' and queue_stats['failed'] > 0:
            # Retry failed jobs
            if tracker:
                count = tracker.retry_failed()
                if CYBER_UI_AVAILABLE:
                    cyber_success(f"Reset {count} failed jobs for retry")
                else:
                    print_success(f"Reset {count} failed jobs for retry")
            get_input("\nPress Enter to continue...")

        elif choice == '6' and queue_stats['completed'] > 0:
            # Clear completed jobs
            if tracker:
                tracker.clear_completed()
                if CYBER_UI_AVAILABLE:
                    cyber_success("Cleared completed jobs")
                else:
                    print_success("Cleared completed jobs")
            get_input("\nPress Enter to continue...")

        elif choice == '7' and queue_stats['total'] > 0:
            # Clear entire scan queue
            do_clear = cyber_confirm("Clear ENTIRE scan queue? This cannot be undone.", default=False) if CYBER_UI_AVAILABLE else confirm("Clear ENTIRE scan queue? This cannot be undone.", default=False)
            if do_clear and tracker:
                tracker.clear_all()
                if CYBER_UI_AVAILABLE:
                    cyber_success("Cleared entire scan queue")
                else:
                    print_success("Cleared entire scan queue")
            get_input("\nPress Enter to continue...")

        else:
            if CYBER_UI_AVAILABLE:
                cyber_warning("Invalid option or action not available")
            else:
                print_warning("Invalid option or action not available")
            time.sleep(1)
