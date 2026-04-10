"""pm_c2.py - Distributed Multi-EC2 SpiderFoot Scanning (C2 Controller)"""
import os
import sys
import time
import subprocess
import shlex
from pathlib import Path
from datetime import datetime

from pm_config import load_config, save_config
from pm_ui_helpers import (
    C, clear_screen, print_banner, print_section, print_menu_item,
    print_success, print_error, print_warning, print_info,
    get_input, confirm,
    is_running_in_tmux, get_tmux_session_name, auto_launch_in_tmux,
)
from pm_paths import sanitize_path

# Try to import cyberpunk UI components
try:
    from ui.cyberpunk_ui import (
        cyber_header, cyber_info, cyber_success,
        cyber_warning, cyber_error, cyber_confirm,
        get_console,
    )
    CYBER_UI_AVAILABLE = True
except ImportError:
    CYBER_UI_AVAILABLE = False


# =============================================================================
# DISTRIBUTED MULTI-EC2 SCANNING (C2 CONTROLLER)
# =============================================================================

def distributed_scanning_menu():
    """
    C2-style distributed scanning controller menu.

    Manages multiple EC2 workers for parallel SpiderFoot scanning.
    """
    from datetime import datetime

    # Import distributed modules
    try:
        from discovery.worker_config import DistributedConfigManager
        from discovery.distributed import (
            DistributedScanController,
            SSHExecutor,
            INTENSITY_PRESETS,
            check_local_security,
            run_preflight_security_check,
            check_ssh_agent_symlink_setup,
            setup_ssh_agent_symlink,
            fix_ssh_auth_sock,
        )
    except ImportError as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Failed to import distributed modules: {e}")
        else:
            print_error(f"Failed to import distributed modules: {e}")
        get_input("\nPress Enter to return...")
        return

    # Initialize config manager
    config_manager = DistributedConfigManager()

    # One-time SSH agent symlink setup check (for tmux compatibility)
    # This ensures SSH agent forwarding works reliably in tmux sessions
    if config_manager.config.use_ssh_agent:
        symlink_configured, _ = check_ssh_agent_symlink_setup()
        if not symlink_configured:
            # Check if we're likely in a tmux-using environment
            # Only show prompt if agent is available (user is using SSH agent forwarding)
            agent_ok, _ = SSHExecutor.check_agent_status(auto_fix=True)
            if agent_ok:
                clear_screen()
                if CYBER_UI_AVAILABLE:
                    console = get_console()
                    from rich.panel import Panel

                    console.print(Panel(
                        "[yellow]SSH Agent tmux Compatibility Setup[/]\n\n"
                        "To ensure distributed scans work reliably when you disconnect\n"
                        "and reconnect SSH sessions, puppetmaster can configure a stable\n"
                        "SSH agent socket path.\n\n"
                        "[dim]This adds a few lines to your ~/.zshrc that create a symlink\n"
                        "so tmux sessions can always find your SSH agent.[/]",
                        title="[bold cyan]One-Time Setup[/]",
                        border_style="cyan",
                        width=70
                    ))
                    console.print()
                    choice = get_input("Set up SSH agent tmux compatibility? [Y/n]: ").strip().lower()
                else:
                    print("\n" + "=" * 60)
                    print("SSH Agent tmux Compatibility Setup")
                    print("=" * 60)
                    print("\nTo ensure distributed scans work reliably when you disconnect")
                    print("and reconnect SSH sessions, puppetmaster can configure a stable")
                    print("SSH agent socket path.")
                    print("\nThis adds a few lines to your ~/.zshrc that create a symlink")
                    print("so tmux sessions can always find your SSH agent.")
                    print()
                    choice = get_input("Set up SSH agent tmux compatibility? [Y/n]: ").strip().lower()

                if choice != 'n':
                    # Detect shell
                    shell = os.environ.get('SHELL', '/bin/bash')
                    if 'zsh' in shell:
                        rc_file = "~/.zshrc"
                    else:
                        rc_file = "~/.bashrc"

                    success, message = setup_ssh_agent_symlink(rc_file)
                    if success:
                        if CYBER_UI_AVAILABLE:
                            console.print(f"[green]✓[/] {message}")
                            console.print("[dim]This will take effect on your next login, but we've also")
                            console.print("set it up for this session.[/dim]")
                        else:
                            print(f"✓ {message}")
                            print("This will take effect on your next login, but we've also")
                            print("set it up for this session.")
                    else:
                        if CYBER_UI_AVAILABLE:
                            console.print(f"[red]✗[/] {message}")
                        else:
                            print(f"✗ {message}")
                    get_input("\nPress Enter to continue...")

    while True:
        clear_screen()

        if CYBER_UI_AVAILABLE:
            console = get_console()
            from rich.panel import Panel
            from rich.table import Table
            from rich.text import Text

            # C2 banner
            c2_banner = """
[bold #ff6b6b]
    ╔═══════════════════════════════════════════════════════╗
    ║  ██████╗██████╗     ███████╗ ██████╗ █████╗ ███╗   ██╗ ║
    ║ ██╔════╝╚════██╗    ██╔════╝██╔════╝██╔══██╗████╗  ██║ ║
    ║ ██║      █████╔╝    ███████╗██║     ███████║██╔██╗ ██║ ║
    ║ ██║     ██╔═══╝     ╚════██║██║     ██╔══██║██║╚██╗██║ ║
    ║ ╚██████╗███████╗    ███████║╚██████╗██║  ██║██║ ╚████║ ║
    ║  ╚═════╝╚══════╝    ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝ ║
    ╚═══════════════════════════════════════════════════════╝
[/]
[dim]    DISTRIBUTED EC2 COMMAND & CONTROL[/]
"""
            console.print(c2_banner)
        else:
            print(f"""
{C.BRIGHT_RED}
╔═══════════════════════════════════════════════════════╗
║  C2 SCAN - DISTRIBUTED EC2 CONTROLLER                  ║
╚═══════════════════════════════════════════════════════╝
{C.RESET}""")

        # Get status info
        config = config_manager.config
        workers = config_manager.get_enabled_workers()
        has_key = config_manager.has_ssh_key()

        # Worker status counts
        ready_count = sum(1 for w in workers if w.status == "ready")
        scanning_count = sum(1 for w in workers if w.status == "scanning")
        error_count = sum(1 for w in workers if w.status == "error")

        # Total domains across workers (cap completed to assigned per-worker to avoid stale data issues)
        total_assigned = sum(w.assigned_domains for w in workers)
        total_completed = sum(min(w.completed_domains, w.assigned_domains) for w in workers)

        # Aborted domains
        aborted_count = len(config.aborted_domains)

        # Display status panel
        if CYBER_UI_AVAILABLE:
            status_table = Table(show_header=False, box=None, padding=(0, 2))
            status_table.add_column("Label", style="dim white", width=22)
            status_table.add_column("Value")

            # SSH Authentication
            if config.use_ssh_agent:
                if has_key:
                    status_table.add_row("◈ SSH Auth", "[green]Agent Mode[/] [dim](secure)[/]")
                else:
                    status_table.add_row("◈ SSH Auth", "[red]Agent Mode - NO KEYS LOADED[/]")
            elif has_key:
                key_display = config.ssh_key_path.split('/')[-1]
                status_table.add_row("◈ SSH Auth", f"[yellow]Key File:[/] [cyan]{key_display}[/]")
            else:
                status_table.add_row("◈ SSH Auth", "[red]NOT CONFIGURED[/]")

            # Workers
            if workers:
                worker_status = f"[white]{len(workers)} total[/] | [green]{ready_count} ready[/] | [yellow]{scanning_count} scanning[/]"
                if error_count:
                    worker_status += f" | [red]{error_count} error[/]"
                status_table.add_row("◈ Workers", worker_status)
            else:
                status_table.add_row("◈ Workers", "[dim]None configured[/]")

            # Scan mode
            scan_mode = getattr(config, 'scan_mode', 'cli')
            if scan_mode == "webapi":
                status_table.add_row("◈ Scan Mode", "[green]WebAPI[/] [dim](high parallelism)[/]")
            else:
                status_table.add_row("◈ Scan Mode", "[cyan]CLI[/] [dim](bash scripts)[/]")

            # Domain queue (check both sources)
            main_config = load_config()
            loaded_domains = main_config.get('pending_domains', [])
            tracker_domains = 0
            try:
                from discovery.jobs import JobTracker
                tracker = JobTracker()
                tracker_domains = tracker.get_stats().get('pending', 0)
            except Exception:
                pass
            total_queue = len(loaded_domains) + tracker_domains
            if total_queue > 0:
                queue_parts = []
                if loaded_domains:
                    queue_parts.append(f"{len(loaded_domains)} loaded")
                if tracker_domains:
                    queue_parts.append(f"{tracker_domains} in queue")
                status_table.add_row("◈ Domains Ready", f"[cyan]{total_queue}[/] [dim]({', '.join(queue_parts)})[/]")
            else:
                status_table.add_row("◈ Domains Ready", "[dim]0 - load via main menu[/]")

            # Progress
            if total_assigned > 0:
                pct = (total_completed / total_assigned) * 100
                status_table.add_row("◈ Progress", f"[cyan]{total_completed}[/]/[white]{total_assigned}[/] domains [dim]({pct:.1f}%)[/]")

            # Aborted
            if aborted_count > 0:
                status_table.add_row("◈ Aborted", f"[red]{aborted_count} domains[/]")

            # Active session
            if config.current_session_id:
                status_table.add_row("◈ Session", f"[cyan]{config.current_session_id}[/]")

            console.print(Panel(
                status_table,
                title="[bold #ff6b6b]⟨ C2 STATUS ⟩[/]",
                border_style="#ff6b6b",
                padding=(1, 2),
                width=80
            ))
            console.print()

            # Menu options
            menu_text = Text()

            menu_text.append("WORKER MANAGEMENT\n", style="bold white underline")
            menu_text.append("  [1] ", style="bold green")
            menu_text.append("View Worker Status      ", style="white")
            menu_text.append("Detailed status of all workers\n", style="#888888")
            menu_text.append("  [2] ", style="bold cyan")
            menu_text.append("Add Worker              ", style="white")
            menu_text.append("Add EC2 worker hostname\n", style="#888888")
            menu_text.append("  [3] ", style="bold yellow")
            menu_text.append("Remove Worker           ", style="white")
            menu_text.append("Remove a worker from pool\n", style="#888888")
            menu_text.append("  [4] ", style="bold magenta")
            menu_text.append("Configure SSH Key       ", style="white")
            menu_text.append("Set .pem key path\n", style="#888888")
            menu_text.append("  [5] ", style="bold blue")
            menu_text.append("Setup Workers           ", style="white")
            menu_text.append("Install SpiderFoot on all workers\n", style="#888888")
            menu_text.append("  [6] ", style="bold #00d4aa")
            menu_text.append("EC2 Setup & Cost Guide  ", style="white")
            menu_text.append("Instance recommendations & launch commands\n", style="#888888")
            menu_text.append("  [7] ", style="bold #ffa502")
            menu_text.append("Replace Worker Addresses", style="white")
            menu_text.append("  Update hostnames when EC2 instances restart\n\n", style="#888888")

            menu_text.append("SCAN OPERATIONS\n", style="bold white underline")
            menu_text.append("  [S] ", style="bold #ff6b6b")
            menu_text.append("Start Distributed Scan  ", style="white")
            menu_text.append("Launch scans across all workers\n", style="#888888")
            menu_text.append("  [P] ", style="bold #4ecdc4")
            menu_text.append("Check Progress          ", style="white")
            menu_text.append("View real-time scan progress\n", style="#888888")
            menu_text.append("  [A] ", style="bold red")
            menu_text.append("Stop All Scans          ", style="white")
            menu_text.append("Stop scans, restart GUIs for results\n", style="#888888")
            menu_text.append("  [B] ", style="bold #ff4444")
            menu_text.append("Abort All Scans         ", style="white")
            menu_text.append("Kill everything immediately (no restart)\n", style="#888888")
            menu_text.append("  [V] ", style="bold #ffe66d")
            menu_text.append("View Aborted Domains    ", style="white")
            menu_text.append("Domains that timed out or failed\n", style="#888888")
            menu_text.append("  [F] ", style="bold #ffe66d")
            menu_text.append("Recover Failed Worker   ", style="white")
            menu_text.append("Salvage results, redistribute domains\n", style="#888888")
            menu_text.append("  [U] ", style="bold #95e1d3")
            menu_text.append("Resume All Workers      ", style="white")
            menu_text.append("Restart rolling queues for unsubmitted domains\n", style="#888888")
            menu_text.append("  [C] ", style="bold #95e1d3")
            menu_text.append("Collect Results         ", style="white")
            menu_text.append("Download CSVs from all workers\n", style="#888888")
            menu_text.append("  [G] ", style="bold #f38181")
            menu_text.append("GUI Access              ", style="white")
            menu_text.append("SSH tunnel commands for GUIs\n", style="#888888")
            menu_text.append("  [D] ", style="bold yellow")
            menu_text.append("Debug Worker Logs       ", style="white")
            menu_text.append("View worker scan logs for troubleshooting\n\n", style="#888888")

            menu_text.append("DATABASE MANAGEMENT\n", style="bold white underline")
            menu_text.append("  [R] ", style="bold #ff9f43")
            menu_text.append("Reset Worker Databases  ", style="white")
            menu_text.append("Wipe SpiderFoot DB on all workers\n", style="#888888")
            menu_text.append("  [W] ", style="bold cyan")
            menu_text.append("Verify Workers Clean    ", style="white")
            menu_text.append("Check workers have no running scans\n\n", style="#888888")

            menu_text.append("SECURITY\n", style="bold white underline")
            menu_text.append("  [X] ", style="bold #ff4444")
            menu_text.append("Security Audit          ", style="white")
            menu_text.append("Scan for keys/creds on master & workers\n\n", style="#888888")

            menu_text.append("SETTINGS\n", style="bold white underline")
            # Show scan mode toggle prominently
            if scan_mode == "cli":
                menu_text.append("  [M] ", style="bold #00ff00")
                menu_text.append("Switch to WebAPI Mode   ", style="white")
                menu_text.append("RECOMMENDED - 5x more parallel scans!\n", style="#00ff00")
            else:
                menu_text.append("  [M] ", style="bold #aa96da")
                menu_text.append("Scan Mode               ", style="white")
                menu_text.append("Currently: WebAPI (toggle to CLI)\n", style="#888888")
            menu_text.append("  [T] ", style="bold #aa96da")
            menu_text.append("Scan Settings           ", style="white")
            menu_text.append("Parallelism, timeouts, etc.\n\n", style="#888888")

            menu_text.append("  [Q] ", style="bold white")
            menu_text.append("Back to Control Center\n", style="dim")

            console.print(Panel(menu_text, title="[bold #ff6b6b]⟨ C2 OPERATIONS ⟩[/]", border_style="#ff6b6b", width=80))
            console.print()
        else:
            # Classic terminal output
            scan_mode = getattr(config, 'scan_mode', 'cli')
            mode_display = f"{C.GREEN}WebAPI{C.RESET} (high parallelism)" if scan_mode == "webapi" else f"{C.CYAN}CLI{C.RESET} (bash scripts)"
            print(f"""
{C.WHITE}C2 STATUS{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  SSH Auth:   {C.GREEN + "Agent Mode (secure)" + C.RESET if config.use_ssh_agent and has_key else C.RED + "Agent Mode - NO KEYS" + C.RESET if config.use_ssh_agent else C.YELLOW + "Key: " + config.ssh_key_path.split('/')[-1] + C.RESET if has_key else C.RED + "[NOT CONFIGURED]" + C.RESET}
  Workers:    {len(workers)} total ({ready_count} ready, {scanning_count} scanning)
  Scan Mode:  {mode_display}
  Progress:   {total_completed}/{total_assigned} domains
  Aborted:    {aborted_count} domains

{C.WHITE}WORKER MANAGEMENT{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.GREEN}[1]{C.RESET} View Worker Status      Detailed status of all workers
  {C.CYAN}[2]{C.RESET} Add Worker              Add EC2 worker hostname
  {C.YELLOW}[3]{C.RESET} Remove Worker           Remove a worker from pool
  {C.BRIGHT_MAGENTA}[4]{C.RESET} Configure SSH Key       Set .pem key path
  {C.BRIGHT_BLUE}[5]{C.RESET} Setup Workers           Install SpiderFoot on all workers
  {C.BRIGHT_CYAN}[6]{C.RESET} EC2 Setup & Cost Guide  Instance recommendations & launch commands
  {C.BRIGHT_YELLOW}[7]{C.RESET} Replace Worker Addresses  Update hostnames when EC2 instances restart

{C.WHITE}SCAN OPERATIONS{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.BRIGHT_RED}[S]{C.RESET} Start Distributed Scan  Launch scans across all workers
  {C.BRIGHT_CYAN}[P]{C.RESET} Check Progress          View real-time scan progress
  {C.RED}[A]{C.RESET} Stop All Scans          Stop scans, restart GUIs for results
  {C.BRIGHT_RED}[B]{C.RESET} Abort All Scans         Kill everything immediately (no restart)
  {C.BRIGHT_YELLOW}[V]{C.RESET} View Aborted Domains    Domains that timed out or failed
  {C.BRIGHT_YELLOW}[F]{C.RESET} Recover Failed Worker   Salvage results, redistribute domains
  {C.BRIGHT_GREEN}[U]{C.RESET} Resume All Workers      Restart rolling queues for unsubmitted domains
  {C.BRIGHT_GREEN}[C]{C.RESET} Collect Results         Download CSVs from all workers
  {C.BRIGHT_RED}[G]{C.RESET} GUI Access              SSH tunnel commands for GUIs
  {C.YELLOW}[D]{C.RESET} Debug Worker Logs       View worker scan logs for troubleshooting

{C.WHITE}DATABASE MANAGEMENT{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.BRIGHT_YELLOW}[R]{C.RESET} Reset Worker Databases  Wipe SpiderFoot DB on all workers
  {C.BRIGHT_CYAN}[W]{C.RESET} Verify Workers Clean    Check workers have no running scans

{C.WHITE}SECURITY{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.RED}[X]{C.RESET} Security Audit          Scan for keys/creds on master & workers

{C.WHITE}SETTINGS{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.GREEN if scan_mode == 'cli' else C.BRIGHT_MAGENTA}[M]{C.RESET} {"Switch to WebAPI Mode   " + C.GREEN + "RECOMMENDED - 5x more parallel!" + C.RESET if scan_mode == 'cli' else "Scan Mode               Currently: WebAPI"}
  {C.BRIGHT_MAGENTA}[T]{C.RESET} Scan Settings           Parallelism, timeouts, etc.

  {C.WHITE}[Q]{C.RESET} Back to Control Center
""")

        choice = get_input("Select an option")
        if choice is None:
            choice = 'q'
        choice = choice.lower().strip()

        if choice == 'q':
            return

        elif choice == '1':
            _c2_view_worker_status(config_manager)

        elif choice == '2':
            _c2_add_worker(config_manager)

        elif choice == '3':
            _c2_remove_worker(config_manager)

        elif choice == '4':
            _c2_configure_ssh_key(config_manager)

        elif choice == '5':
            _c2_setup_workers(config_manager)

        elif choice == '6':
            _c2_ec2_cost_guide(config_manager)

        elif choice == '7':
            _c2_replace_worker_addresses(config_manager)

        elif choice == 's':
            _c2_start_distributed_scan(config_manager)

        elif choice == 'p':
            _c2_check_progress(config_manager)

        elif choice == 'a':
            _c2_stop_all_scans(config_manager)

        elif choice == 'b':
            _c2_abort_all_scans(config_manager)

        elif choice == 'v':
            _c2_view_aborted_domains(config_manager)

        elif choice == 'f':
            _c2_recover_worker(config_manager)

        elif choice == 'u':
            _c2_resume_all_workers(config_manager)

        elif choice == 'c':
            _c2_collect_results(config_manager)

        elif choice == 'g':
            _c2_gui_access(config_manager)

        elif choice == 'd':
            _c2_debug_worker_logs(config_manager)

        elif choice == 'r':
            _c2_reset_worker_databases(config_manager)

        elif choice == 'w':
            _c2_verify_workers_clean(config_manager)

        elif choice == 't':
            _c2_modify_timeouts(config_manager)

        elif choice == 'm':
            _c2_toggle_scan_mode(config_manager)

        elif choice == 'x':
            _c2_security_audit(config_manager)


# -----------------------------------------------------------------------------
# C2 Sub-menu Functions
# -----------------------------------------------------------------------------

def _c2_view_worker_status(config_manager):
    """Display detailed status of all workers."""
    clear_screen()

    workers = config_manager.config.workers

    if CYBER_UI_AVAILABLE:
        console = get_console()
        from rich.panel import Panel
        from rich.table import Table

        cyber_header("WORKER STATUS")

        if not workers:
            console.print("[yellow]No workers configured. Use option [2] to add workers.[/]")
        else:
            # Check if we should actively verify SpiderFoot installation
            if config_manager.has_ssh_key():
                worker_count = len(workers)
                console.print(f"[yellow]Checking SpiderFoot installation status on {worker_count} worker{'s' if worker_count != 1 else ''}...[/]")
                console.print(f"[dim]This can take a few minutes depending on how many workers you have.[/]")
                try:
                    from discovery.distributed import DistributedScanController
                    controller = DistributedScanController(config_manager)

                    # Check each worker for SpiderFoot
                    for w in workers:
                        installed, version = controller.installer.check_spiderfoot_installed(
                            w.hostname,
                            w.username,
                            config_manager.config.spiderfoot_install_dir
                        )
                        config_manager.update_worker(w.hostname, spiderfoot_installed=installed)

                    # Refresh workers list after updates
                    workers = config_manager.config.workers
                    console.print("[green]✓ Status refreshed[/]\n")
                except Exception as e:
                    console.print(f"[yellow]⚠ Could not verify SpiderFoot status: {e}[/]\n")

            # Fetch live scan progress when SpiderFoot is installed on any worker
            if any(w.spiderfoot_installed for w in workers):
                try:
                    from discovery.distributed import DistributedScanController
                    controller = DistributedScanController(config_manager)
                    console.print("[yellow]Fetching live scan progress...[/]")
                    controller.get_all_progress()
                    # Re-read workers to get updated progress values
                    workers = config_manager.config.workers
                    console.print("[green]✓ Live progress updated[/]\n")
                except Exception as e:
                    console.print(f"[yellow]⚠ Could not fetch live progress: {e}[/]\n")

            table = Table(title="EC2 Workers", border_style="cyan")
            table.add_column("Nickname", style="cyan")
            table.add_column("Hostname", style="white")
            table.add_column("Status", style="green")
            table.add_column("Resources", style="magenta")
            table.add_column("Progress", style="yellow")
            table.add_column("SpiderFoot", style="blue")

            for w in workers:
                status_color = {
                    "ready": "green",
                    "scanning": "yellow",
                    "completed": "cyan",
                    "error": "red",
                    "unknown": "dim",
                    "idle": "dim",
                }.get(w.status, "white")

                resources = f"{w.ram_gb}GB/{w.cpu_cores}cores" if w.ram_gb else "unknown"
                if w.assigned_domains:
                    progress = f"{w.completed_domains}/{w.assigned_domains}"
                    if w.failed_domains:
                        progress += f" ({w.failed_domains}F)"
                else:
                    progress = "-"
                sf_status = "[green]Yes[/]" if w.spiderfoot_installed else "[red]No[/]"

                table.add_row(
                    w.nickname or "-",
                    w.hostname[:40],
                    f"[{status_color}]{w.status}[/]",
                    resources,
                    progress,
                    sf_status
                )

            console.print(table)
    else:
        print_section("Worker Status", C.BRIGHT_CYAN)

        if not workers:
            print_info("No workers configured. Use option [2] to add workers.")
        else:
            # Check if we should actively verify SpiderFoot installation
            if config_manager.has_ssh_key():
                worker_count = len(workers)
                print(f"Checking SpiderFoot installation status on {worker_count} worker{'s' if worker_count != 1 else ''}...")
                print(f"{C.DIM}This can take a few minutes depending on how many workers you have.{C.RESET}")
                try:
                    from discovery.distributed import DistributedScanController
                    controller = DistributedScanController(config_manager)

                    # Check each worker for SpiderFoot
                    for w in workers:
                        installed, version = controller.installer.check_spiderfoot_installed(
                            w.hostname,
                            w.username,
                            config_manager.config.spiderfoot_install_dir
                        )
                        config_manager.update_worker(w.hostname, spiderfoot_installed=installed)

                    # Refresh workers list after updates
                    workers = config_manager.config.workers
                    print(f"{C.GREEN}✓ Status refreshed{C.RESET}\n")
                except Exception as e:
                    print(f"{C.YELLOW}⚠ Could not verify SpiderFoot status: {e}{C.RESET}\n")

            # Fetch live scan progress when SpiderFoot is installed on any worker
            if any(w.spiderfoot_installed for w in workers):
                try:
                    from discovery.distributed import DistributedScanController
                    controller = DistributedScanController(config_manager)
                    print("Fetching live scan progress...")
                    controller.get_all_progress()
                    # Re-read workers to get updated progress values
                    workers = config_manager.config.workers
                    print(f"{C.GREEN}✓ Live progress updated{C.RESET}\n")
                except Exception as e:
                    print(f"{C.YELLOW}⚠ Could not fetch live progress: {e}{C.RESET}\n")

            for w in workers:
                print(f"\n  {C.CYAN}{w.nickname or w.hostname}{C.RESET}")
                print(f"    Host: {w.hostname}")
                print(f"    Status: {w.status}")
                print(f"    Resources: {w.ram_gb}GB / {w.cpu_cores} cores" if w.ram_gb else "    Resources: unknown")
                print(f"    SpiderFoot: {'Installed' if w.spiderfoot_installed else 'Not installed'}")
                if w.assigned_domains:
                    prog_str = f"{w.completed_domains}/{w.assigned_domains}"
                    if w.failed_domains:
                        prog_str += f" ({w.failed_domains}F)"
                    print(f"    Progress: {prog_str}")
                else:
                    print("    Progress: -")

    get_input("\nPress Enter to continue...")


def _parse_aws_worker_input(raw_lines):
    """
    Parse worker input that may be either:
    - Tag-paired format: 'worker_3\\tec2-1-2-3-4.compute-1.amazonaws.com' (from updated AWS command)
    - Plain hostnames: 'ec2-1-2-3-4.compute-1.amazonaws.com' (legacy format)

    Returns:
        List of (tag_name_or_None, hostname) tuples, sorted by tag name (natural sort)
    """
    import re

    results = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue

        # Split input by whitespace/commas — but preserve tab-separated pairs
        # AWS --output text uses tabs between columns within a row, spaces/tabs between rows
        # A paired entry looks like: "worker_1\tec2-..." or with spaces: "worker_1 ec2-..."
        # We detect pairs by checking if a token looks like "worker_N" followed by an ec2 hostname

        # First, split by multiple whitespace/commas (handles both space and tab separated rows)
        tokens = re.split(r'[,\s]+', line)

        i = 0
        while i < len(tokens):
            token = tokens[i].strip()
            if not token:
                i += 1
                continue

            # Check if this token is a tag name (worker_N pattern) followed by a hostname
            if re.match(r'^worker_\d+$', token, re.IGNORECASE) and i + 1 < len(tokens):
                next_token = tokens[i + 1].strip()
                if next_token and '.' in next_token and not re.match(r'^worker_\d+$', next_token, re.IGNORECASE):
                    # This is a tag + hostname pair
                    results.append((token, next_token))
                    i += 2
                    continue

            # Plain hostname (no tag)
            if '.' in token:
                results.append((None, token))
            i += 1

    # Sort by tag name using natural sort if we have tags
    has_tags = any(tag is not None for tag, _ in results)
    if has_tags:
        def natural_key(pair):
            tag = pair[0] or ""
            return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', tag)]
        results.sort(key=natural_key)

    return results


def _get_aws_paired_command(region):
    """Get the AWS CLI command that returns tag_name + hostname pairs."""
    return (
        f'aws ec2 describe-instances '
        f'--filters "Name=tag:Name,Values=worker_*" "Name=instance-state-name,Values=running" '
        f'--region {region} '
        f"--query 'Reservations[].Instances[].[Tags[?Key==`Name`].Value | [0], PublicDnsName]' "
        f'--output text'
    )


def _c2_add_worker(config_manager):
    """Add one or more workers."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        cyber_header("ADD WORKERS")
        console = get_console()
        console.print("[dim]Add multiple EC2 workers at once.[/]")
        console.print("[dim]Nicknames will match your AWS tag names (worker_1, worker_2, etc.)[/]\n")
        region = config_manager.config.aws_region
        aws_cmd = _get_aws_paired_command(region)
        console.print("[bold cyan]TIP:[/] [dim]Run in AWS CloudShell to get hostnames, then paste the output below:[/]")
        console.print(f"[cyan]{aws_cmd}[/]")
        console.print(f"[dim]Or for a simple hostname list sorted by worker number:[/]")
        console.print(f"[cyan]{aws_cmd} | sort -V | cut -f2[/]")
        console.print(f"[dim]Adjust [bold]Values=worker_*[/dim][dim] if your instances use different tags.[/]")
        console.print(f"[dim](Change [bold]--region {region}[/dim][dim] if your workers are in a different region)[/]\n")
    else:
        print_section("Add Workers", C.BRIGHT_GREEN)
        print("Add multiple EC2 workers at once.")
        print("Nicknames will match your AWS tag names (worker_1, worker_2, etc.)\n")
        region = config_manager.config.aws_region
        aws_cmd = _get_aws_paired_command(region)
        print(f"{C.CYAN}TIP:{C.RESET} Run in AWS CloudShell to get hostnames, then paste the output below:")
        print(f"{C.CYAN}{aws_cmd}{C.RESET}")
        print(f"{C.DIM}Or for a simple hostname list sorted by worker number:")
        print(f"{C.CYAN}{aws_cmd} | sort -V | cut -f2{C.RESET}")
        print(f"{C.DIM}Adjust Values=worker_* if your instances use different tags.")
        print(f"(Change --region {region} if your workers are in a different region){C.RESET}\n")

    # Get username first (applies to all)
    username = get_input("Username for all workers (default: kali)")
    username = username.strip() if username else "kali"

    if CYBER_UI_AVAILABLE:
        console.print(f"\n[dim]Paste the AWS output below (all lines at once, or one per line).[/]")
        console.print("[dim]Press Enter on an empty line when done.[/]\n")
    else:
        print(f"\nPaste the AWS output below (all lines at once, or one per line).")
        print("Press Enter on an empty line when done.\n")

    # Collect hostnames (supports multi-line paste)
    raw_lines = []
    while True:
        line = get_input("Hostname", allow_multiline=True)
        if line is None:
            break
        line = line.strip()
        if not line:
            break  # Empty line = done
        # Split multi-line paste into individual lines
        sublines = [s.strip() for s in line.split('\n') if s.strip()]
        raw_lines.extend(sublines)
        if len(sublines) > 1:
            break  # Got bulk paste, done collecting

    if not raw_lines:
        if CYBER_UI_AVAILABLE:
            cyber_info("No hostnames entered.")
        else:
            print_info("No hostnames entered.")
        get_input("\nPress Enter to continue...")
        return

    # Parse input — handles both "worker_N hostname" pairs and plain hostnames
    parsed = _parse_aws_worker_input(raw_lines)

    if not parsed:
        if CYBER_UI_AVAILABLE:
            cyber_info("No valid hostnames found in input.")
        else:
            print_info("No valid hostnames found in input.")
        get_input("\nPress Enter to continue...")
        return

    has_tags = any(tag is not None for tag, _ in parsed)

    if has_tags:
        if CYBER_UI_AVAILABLE:
            console.print(f"[green]Detected {len(parsed)} workers with AWS tag names.[/]\n")
        else:
            print(f"Detected {len(parsed)} workers with AWS tag names.\n")

    # Find next worker number for auto-naming (only used for plain hostname input)
    existing_workers = config_manager.config.workers
    existing_nums = []
    for w in existing_workers:
        if w.nickname and w.nickname.startswith("worker_"):
            try:
                num = int(w.nickname.split("_")[1])
                existing_nums.append(num)
            except (ValueError, IndexError):
                pass
    next_num = max(existing_nums, default=0) + 1

    # Add each worker
    added = 0
    skipped = 0
    for tag_name, hostname in parsed:
        # Use AWS tag name if available, otherwise auto-generate
        if tag_name:
            nickname = tag_name
        else:
            nickname = f"worker_{next_num}"
            next_num += 1
        try:
            config_manager.add_worker(hostname, username, nickname)
            added += 1
            if CYBER_UI_AVAILABLE:
                console.print(f"  [green]✓[/] {nickname}: {hostname}")
            else:
                print(f"  ✓ {nickname}: {hostname}")
        except ValueError:
            skipped += 1
            if CYBER_UI_AVAILABLE:
                console.print(f"  [yellow]○[/] Skipped (exists): {hostname}")
            else:
                print(f"  ○ Skipped (exists): {hostname}")

    # Summary
    if CYBER_UI_AVAILABLE:
        console.print()
        if added:
            cyber_success(f"Added {added} worker(s)")
        if skipped:
            cyber_info(f"Skipped {skipped} (already existed)")
    else:
        print()
        if added:
            print_success(f"Added {added} worker(s)")
        if skipped:
            print_info(f"Skipped {skipped} (already existed)")

    get_input("\nPress Enter to continue...")


def _c2_replace_worker_addresses(config_manager):
    """Replace all worker hostnames when EC2 instances restart with new addresses."""
    clear_screen()

    workers = config_manager.get_all_workers()
    if not workers:
        if CYBER_UI_AVAILABLE:
            cyber_warning("No workers configured. Use [2] Add Worker first.")
        else:
            print_warning("No workers configured. Use [2] Add Worker first.")
        get_input("\nPress Enter to continue...")
        return

    sorted_workers = sorted(
        workers,
        key=lambda w: config_manager._extract_worker_num(w.nickname)
    )

    if CYBER_UI_AVAILABLE:
        cyber_header("REPLACE WORKER ADDRESSES")
        console = get_console()
        from rich.table import Table
        from rich.panel import Panel

        console.print(Panel(
            "[white]When you stop and restart EC2 instances, their public DNS\n"
            "addresses change. Use this to update worker addresses\n"
            "while keeping nicknames, ports, and all other settings intact.[/]\n\n"
            "[dim]Your SpiderFoot installations and scan data are preserved on\n"
            "the instances — no need to re-run setup after replacing addresses.[/]",
            border_style="yellow",
            width=80
        ))
        console.print()

        console.print("[bold white]Current workers:[/]")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("#", style="dim", width=4)
        table.add_column("Nickname", style="cyan", width=12)
        table.add_column("Current Hostname", style="white")
        for i, w in enumerate(sorted_workers, 1):
            table.add_row(str(i), w.nickname or "—", w.hostname)
        console.print(table)
        console.print()

        console.print("[bold white]Replace:[/]")
        console.print("  [cyan][1][/] Single worker  — update one worker's address")
        console.print("  [cyan][2][/] All workers    — bulk replace all addresses\n")
    else:
        print_section("Replace Worker Addresses", C.BRIGHT_YELLOW)
        print("When you stop and restart EC2 instances, their public DNS")
        print("addresses change. Use this to update worker addresses")
        print("while keeping nicknames, ports, and all other settings intact.\n")
        print("Your SpiderFoot installations and scan data are preserved on")
        print("the instances — no need to re-run setup after replacing addresses.\n")

        print(f"{C.WHITE}Current workers:{C.RESET}")
        for i, w in enumerate(sorted_workers, 1):
            print(f"  {i}. {w.nickname or '—'}: {w.hostname}")
        print()

        print(f"{C.WHITE}Replace:{C.RESET}")
        print(f"  {C.CYAN}[1]{C.RESET} Single worker  — update one worker's address")
        print(f"  {C.CYAN}[2]{C.RESET} All workers    — bulk replace all addresses\n")

    mode_choice = get_input("Choice", default="1")
    if mode_choice is None:
        return
    mode_choice = mode_choice.strip()

    # --- Single worker mode ---
    if mode_choice == "1":
        worker_choice = get_input("Worker # to update")
        if worker_choice is None:
            return
        try:
            idx = int(worker_choice.strip()) - 1
            if idx < 0 or idx >= len(sorted_workers):
                raise ValueError()
            target_worker = sorted_workers[idx]
        except (ValueError, IndexError):
            if CYBER_UI_AVAILABLE:
                cyber_error("Invalid selection.")
            else:
                print_error("Invalid selection.")
            get_input("\nPress Enter to continue...")
            return

        if CYBER_UI_AVAILABLE:
            console.print(f"\n[dim]Updating [cyan]{target_worker.nickname}[/cyan] (current: {target_worker.hostname})[/]")
        else:
            print(f"\nUpdating {target_worker.nickname} (current: {target_worker.hostname})")

        new_hostname = get_input("New hostname")
        if not new_hostname or not new_hostname.strip():
            if CYBER_UI_AVAILABLE:
                cyber_info("No hostname entered. Nothing changed.")
            else:
                print_info("No hostname entered. Nothing changed.")
            get_input("\nPress Enter to continue...")
            return

        new_hostname = new_hostname.strip()
        old_hostname = target_worker.hostname

        # Validate new hostname format
        try:
            from discovery.worker_config import validate_worker_input
            validate_worker_input(new_hostname, target_worker.username)
        except ValueError as e:
            print_error(f"Invalid hostname: {e}")
            get_input("\nPress Enter to continue...")
            return

        if CYBER_UI_AVAILABLE:
            console.print(f"\n[bold white]Preview:[/]")
            console.print(f"  [cyan]{target_worker.nickname}[/]: [red]{old_hostname}[/] → [green]{new_hostname}[/]\n")
        else:
            print(f"\nPreview:")
            print(f"  {target_worker.nickname}: {old_hostname} → {new_hostname}\n")

        if not confirm("Apply this change?"):
            if CYBER_UI_AVAILABLE:
                cyber_info("Cancelled. No changes made.")
            else:
                print_info("Cancelled. No changes made.")
            get_input("\nPress Enter to continue...")
            return

        target_worker.hostname = new_hostname
        # Reset stale data from old instance
        target_worker.completed_domains = 0
        target_worker.failed_domains = 0
        target_worker.assigned_domains = 0
        target_worker.spiderfoot_installed = False
        target_worker.status = "idle"
        config_manager.save_config()

        # Verify the save by reading back from config
        saved_worker = config_manager.get_worker(new_hostname)
        if saved_worker:
            verify_msg = f"Verified: config saved with hostname {saved_worker.hostname}"
        else:
            # Try to find by nickname as fallback verification
            verify_msg = f"Warning: could not verify save (lookup by new hostname failed)"
            # Check if old hostname still exists
            old_check = config_manager.get_worker(old_hostname)
            if old_check:
                verify_msg += f" — old hostname still in config!"

        if CYBER_UI_AVAILABLE:
            console.print()
            cyber_success(f"Updated {target_worker.nickname}: {new_hostname}")
            console.print(f"[dim]{verify_msg}[/]")
            console.print(f"\n[dim]Scan counters reset for {target_worker.nickname}.[/]")
            console.print(f"[dim]Config file: {config_manager.config_file}[/]")
            console.print(f"[yellow]Tip:[/] [dim]If this is a new instance, run [cyan][5] Setup Workers[/cyan] to install SpiderFoot.[/]")
            console.print(f"[dim]If you only stopped/started (same EBS), SpiderFoot is still installed — just start the GUI.[/]")
        else:
            print()
            print_success(f"Updated {target_worker.nickname}: {new_hostname}")
            print(f"  {verify_msg}")
            print(f"\nScan counters reset for {target_worker.nickname}.")
            print(f"Config file: {config_manager.config_file}")
            print(f"{C.YELLOW}Tip:{C.RESET} If this is a new instance, run [5] Setup Workers to install SpiderFoot.")
            print("If you only stopped/started (same EBS), SpiderFoot is still installed — just start the GUI.")
        get_input("\nPress Enter to continue...")
        return

    elif mode_choice != "2":
        if CYBER_UI_AVAILABLE:
            cyber_error("Invalid choice.")
        else:
            print_error("Invalid choice.")
        get_input("\nPress Enter to continue...")
        return

    # --- Bulk replace mode (original flow) ---
    if CYBER_UI_AVAILABLE:
        region = config_manager.config.aws_region
        aws_cmd = _get_aws_paired_command(region)
        console.print(f"\n[bold cyan]Paste {len(workers)} new hostnames below.[/]")
        console.print("[dim]Run this in AWS CloudShell to get updated addresses:[/]")
        console.print(f"[cyan]{aws_cmd}[/]")
        console.print(f"[dim]Or for a simple hostname list sorted by worker number:[/]")
        console.print(f"[cyan]{aws_cmd} | sort -V | cut -f2[/]")
        console.print(f"[dim]Adjust [bold]Values=worker_*[/dim][dim] if your instances use different tags.[/]")
        console.print(f"[dim](Change [bold]--region {region}[/dim][dim] if your workers are in a different region)[/]\n")
    else:
        region = config_manager.config.aws_region
        aws_cmd = _get_aws_paired_command(region)
        print(f"\n{C.CYAN}Paste {len(workers)} new hostnames below.{C.RESET}")
        print(f"{C.DIM}Run this in AWS CloudShell to get updated addresses:{C.RESET}")
        print(f"{C.CYAN}{aws_cmd}{C.RESET}")
        print(f"{C.DIM}Or for a simple hostname list sorted by worker number:")
        print(f"{C.CYAN}{aws_cmd} | sort -V | cut -f2{C.RESET}")
        print(f"{C.DIM}Adjust Values=worker_* if your instances use different tags.")
        print(f"(Change --region {region} if your workers are in a different region){C.RESET}\n")

    # Collect input (supports multi-line paste)
    raw_lines = []
    while True:
        line = get_input("Hostname", allow_multiline=True)
        if line is None:
            break
        line = line.strip()
        if not line:
            break
        # Split multi-line paste into individual lines
        sublines = [s.strip() for s in line.split('\n') if s.strip()]
        raw_lines.extend(sublines)
        if len(sublines) > 1:
            break  # Got bulk paste, done collecting

    if not raw_lines:
        if CYBER_UI_AVAILABLE:
            cyber_info("No hostnames entered. Nothing changed.")
        else:
            print_info("No hostnames entered. Nothing changed.")
        get_input("\nPress Enter to continue...")
        return

    # Parse input — handles both "worker_N hostname" pairs and plain hostnames
    parsed = _parse_aws_worker_input(raw_lines)

    if not parsed:
        if CYBER_UI_AVAILABLE:
            cyber_info("No valid hostnames found in input.")
        else:
            print_info("No valid hostnames found in input.")
        get_input("\nPress Enter to continue...")
        return

    has_tags = any(tag is not None for tag, _ in parsed)

    if has_tags:
        # Tag-based matching: match each parsed tag to a worker nickname
        tag_to_hostname = {tag: hostname for tag, hostname in parsed if tag}

        # Build the mapping: for each worker, find its new hostname by tag name
        changes_preview = []
        unmatched_workers = []
        unmatched_tags = set(tag_to_hostname.keys())

        for w in sorted_workers:
            nickname = w.nickname or ""
            if nickname in tag_to_hostname:
                new_h = tag_to_hostname[nickname]
                unmatched_tags.discard(nickname)
                changes_preview.append((w, new_h))
            else:
                unmatched_workers.append(w)
                changes_preview.append((w, None))  # No match

        # Warn about mismatches
        if unmatched_workers:
            if CYBER_UI_AVAILABLE:
                console.print(f"[yellow]Warning: {len(unmatched_workers)} worker(s) have no matching AWS tag:[/]")
                for w in unmatched_workers:
                    console.print(f"  [yellow]• {w.nickname} (keeping current: {w.hostname})[/]")
                console.print()
            else:
                print(f"Warning: {len(unmatched_workers)} worker(s) have no matching AWS tag:")
                for w in unmatched_workers:
                    print(f"  • {w.nickname} (keeping current: {w.hostname})")
                print()

        if unmatched_tags:
            if CYBER_UI_AVAILABLE:
                console.print(f"[yellow]Warning: {len(unmatched_tags)} AWS tag(s) don't match any worker:[/]")
                for tag in sorted(unmatched_tags):
                    console.print(f"  [yellow]• {tag}: {tag_to_hostname[tag]}[/]")
                console.print()
            else:
                print(f"Warning: {len(unmatched_tags)} AWS tag(s) don't match any worker:")
                for tag in sorted(unmatched_tags):
                    print(f"  • {tag}: {tag_to_hostname[tag]}")
                print()

        # Show preview
        if CYBER_UI_AVAILABLE:
            console.print("[bold white]Preview of changes (matched by tag name):[/]\n")
            preview_table = Table(show_header=True, box=None, padding=(0, 2))
            preview_table.add_column("Worker", style="cyan", width=12)
            preview_table.add_column("Old Address", style="red")
            preview_table.add_column("", style="dim", width=3)
            preview_table.add_column("New Address", style="green")

            for w, new_h in changes_preview:
                if new_h is None:
                    preview_table.add_row(w.nickname or "—", w.hostname, "=", f"[dim]{w.hostname} (no match)[/]")
                else:
                    changed = w.hostname.lower() != new_h.strip().lower()
                    arrow = "→" if changed else "="
                    new_style = "green" if changed else "dim"
                    preview_table.add_row(w.nickname or "—", w.hostname, arrow, f"[{new_style}]{new_h.strip()}[/]")
            console.print(preview_table)
            console.print()
        else:
            print(f"\n{C.WHITE}Preview of changes (matched by tag name):{C.RESET}\n")
            for w, new_h in changes_preview:
                if new_h is None:
                    print(f"  {w.nickname or '—'}: {w.hostname} = {w.hostname} (no match)")
                else:
                    changed = w.hostname.lower() != new_h.strip().lower()
                    arrow = "→" if changed else "="
                    print(f"  {w.nickname or '—'}: {w.hostname} {arrow} {new_h.strip()}")
            print()

        # Confirm
        confirm_result = confirm("Apply these changes?")
        if not confirm_result:
            if CYBER_UI_AVAILABLE:
                cyber_info("Cancelled. No changes made.")
            else:
                print_info("Cancelled. No changes made.")
            get_input("\nPress Enter to continue...")
            return

        # Apply changes by tag name
        changes = []
        for w, new_h in changes_preview:
            old_h = w.hostname
            if new_h is not None:
                w.hostname = new_h.strip()
            changes.append((w.nickname or w.hostname, old_h, w.hostname))
        config_manager.save_config()

        changed_count = sum(1 for _, old, new in changes if old.lower() != new.lower())
        if CYBER_UI_AVAILABLE:
            console.print()
            cyber_success(f"Updated {changed_count} of {len(changes)} worker addresses")
        else:
            print()
            print_success(f"Updated {changed_count} of {len(changes)} worker addresses")

    else:
        # Plain hostnames (no tags) — use positional mapping with warning
        new_hostnames = [hostname for _, hostname in parsed]

        if CYBER_UI_AVAILABLE:
            console.print("[yellow]Warning: No tag names detected in input. Using positional matching.[/]")
            console.print("[dim]For reliable matching, use the AWS command above which includes tag names.[/]\n")
        else:
            print(f"{C.YELLOW}Warning: No tag names detected in input. Using positional matching.{C.RESET}")
            print("For reliable matching, use the AWS command above which includes tag names.\n")

        # Validate count matches
        if len(new_hostnames) != len(workers):
            if CYBER_UI_AVAILABLE:
                cyber_error(
                    f"Count mismatch: pasted {len(new_hostnames)} hostnames "
                    f"but have {len(workers)} workers."
                )
                console.print("[dim]Counts must match exactly. No changes made.[/]")
            else:
                print_error(
                    f"Count mismatch: pasted {len(new_hostnames)} hostnames "
                    f"but have {len(workers)} workers."
                )
                print("Counts must match exactly. No changes made.")
            get_input("\nPress Enter to continue...")
            return

        # Show preview
        if CYBER_UI_AVAILABLE:
            console.print("[bold white]Preview of changes (positional — may not match AWS tags!):[/]\n")
            preview_table = Table(show_header=True, box=None, padding=(0, 2))
            preview_table.add_column("Worker", style="cyan", width=12)
            preview_table.add_column("Old Address", style="red")
            preview_table.add_column("", style="dim", width=3)
            preview_table.add_column("New Address", style="green")

            for w, new_h in zip(sorted_workers, new_hostnames):
                changed = w.hostname.lower() != new_h.strip().lower()
                arrow = "→" if changed else "="
                new_style = "green" if changed else "dim"
                preview_table.add_row(w.nickname or "—", w.hostname, arrow, f"[{new_style}]{new_h.strip()}[/]")
            console.print(preview_table)
            console.print()
        else:
            print(f"\n{C.WHITE}Preview of changes (positional — may not match AWS tags!):{C.RESET}\n")
            for w, new_h in zip(sorted_workers, new_hostnames):
                changed = w.hostname.lower() != new_h.strip().lower()
                arrow = "→" if changed else "="
                print(f"  {w.nickname or '—'}: {w.hostname} {arrow} {new_h.strip()}")
            print()

        # Confirm
        confirm_result = confirm("Apply these changes?")
        if not confirm_result:
            if CYBER_UI_AVAILABLE:
                cyber_info("Cancelled. No changes made.")
            else:
                print_info("Cancelled. No changes made.")
            get_input("\nPress Enter to continue...")
            return

        # Apply changes
        try:
            changes = config_manager.replace_worker_hostnames(new_hostnames)
            changed_count = sum(1 for _, old, new in changes if old.lower() != new.lower())

            if CYBER_UI_AVAILABLE:
                console.print()
                for nickname, old_h, new_h in changes:
                    if old_h.lower() != new_h.lower():
                        console.print(f"  [green]✓[/] {nickname}: [red]{old_h}[/] → [green]{new_h}[/]")
                    else:
                        console.print(f"  [dim]=[/] {nickname}: [dim]unchanged[/]")
                console.print()
                cyber_success(f"Updated {changed_count} of {len(changes)} worker addresses")
            else:
                print()
                for nickname, old_h, new_h in changes:
                    if old_h.lower() != new_h.lower():
                        print(f"  ✓ {nickname}: {old_h} → {new_h}")
                    else:
                        print(f"  = {nickname}: unchanged")
                print()
                print_success(f"Updated {changed_count} of {len(changes)} worker addresses")
        except ValueError as e:
            if CYBER_UI_AVAILABLE:
                cyber_error(str(e))
            else:
                print_error(str(e))

    get_input("\nPress Enter to continue...")


def _c2_remove_worker(config_manager):
    """Remove one or more workers."""
    clear_screen()

    # Take a snapshot of workers at start to avoid reference issues
    workers = list(config_manager.config.workers)

    if not workers:
        if CYBER_UI_AVAILABLE:
            cyber_error("No workers configured.")
        else:
            print_error("No workers configured.")
        get_input("\nPress Enter to continue...")
        return

    if CYBER_UI_AVAILABLE:
        cyber_header("REMOVE WORKER")
        console = get_console()
        console.print("[dim]Select worker(s) to remove from the pool:[/]\n")
        for i, w in enumerate(workers, 1):
            console.print(f"  [{i}] {w.get_display_name()} ({w.hostname})")
        console.print()
        console.print("[bold]How to select:[/]")
        console.print("  [cyan]•[/] Single worker: [white]1[/]")
        console.print("  [cyan]•[/] Multiple workers: [white]1,3,5[/]")
        console.print("  [cyan]•[/] Range of workers: [white]1-3[/]")
        console.print("  [cyan]•[/] Remove all: [white]all[/]")
    else:
        print_section("Remove Worker", C.BRIGHT_YELLOW)
        print("Select worker(s) to remove from the pool:\n")
        for i, w in enumerate(workers, 1):
            print(f"  [{i}] {w.get_display_name()} ({w.hostname})")
        print()
        print("How to select:")
        print(f"  {C.CYAN}•{C.RESET} Single worker: 1")
        print(f"  {C.CYAN}•{C.RESET} Multiple workers: 1,3,5")
        print(f"  {C.CYAN}•{C.RESET} Range of workers: 1-3")
        print(f"  {C.CYAN}•{C.RESET} Remove all: all")

    choice = get_input("\nWorker(s) to remove (or Enter to cancel)")
    if not choice or not choice.strip():
        return

    choice = choice.strip().lower()
    workers_to_remove = []
    indices_to_remove = set()  # Use set to avoid duplicates

    def parse_indices(choice_str):
        """Parse selection string into indices."""
        indices = set()
        parts = [p.strip() for p in choice_str.split(',')]
        for part in parts:
            if '-' in part and part != '-':
                # Range: 1-3
                try:
                    range_parts = part.split('-')
                    if len(range_parts) == 2:
                        start = int(range_parts[0]) - 1
                        end = int(range_parts[1]) - 1
                        for i in range(start, end + 1):
                            if 0 <= i < len(workers):
                                indices.add(i)
                except ValueError:
                    pass
            else:
                # Single number
                try:
                    idx = int(part) - 1
                    if 0 <= idx < len(workers):
                        indices.add(idx)
                except ValueError:
                    pass
        return indices

    if choice == 'all':
        workers_to_remove = list(workers)
    else:
        indices_to_remove = parse_indices(choice)
        if not indices_to_remove:
            if CYBER_UI_AVAILABLE:
                cyber_error("Invalid input. Use numbers, ranges (1-3), or 'all'.")
            else:
                print_error("Invalid input. Use numbers, ranges (1-3), or 'all'.")
            get_input("\nPress Enter to continue...")
            return
        workers_to_remove = [workers[i] for i in sorted(indices_to_remove)]

    if not workers_to_remove:
        if CYBER_UI_AVAILABLE:
            cyber_error("No valid workers selected.")
        else:
            print_error("No valid workers selected.")
        get_input("\nPress Enter to continue...")
        return

    # Show which workers will be removed
    print()
    if CYBER_UI_AVAILABLE:
        console.print("[bold yellow]Workers to be removed:[/]")
        for w in workers_to_remove:
            console.print(f"  [red]✗[/] {w.get_display_name()} ({w.hostname})")
        print()
    else:
        print(f"{C.BRIGHT_YELLOW}Workers to be removed:{C.RESET}")
        for w in workers_to_remove:
            print(f"  {C.RED}✗{C.RESET} {w.get_display_name()} ({w.hostname})")
        print()

    # Confirm removal
    if len(workers_to_remove) == 1:
        confirm_msg = f"Remove {workers_to_remove[0].get_display_name()}?"
    else:
        confirm_msg = f"Remove these {len(workers_to_remove)} workers?"

    confirmed = False
    if CYBER_UI_AVAILABLE:
        confirmed = cyber_confirm(confirm_msg)
    else:
        confirmed = confirm(confirm_msg)

    if confirmed:
        removed_count = 0
        failed = []
        for worker in workers_to_remove:
            if config_manager.remove_worker(worker.hostname):
                removed_count += 1
            else:
                failed.append(worker.get_display_name())

        if removed_count > 0:
            if CYBER_UI_AVAILABLE:
                cyber_success(f"Removed {removed_count} worker(s).")
            else:
                print_success(f"Removed {removed_count} worker(s).")

        if failed:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Failed to remove: {', '.join(failed)}")
            else:
                print_error(f"Failed to remove: {', '.join(failed)}")

    get_input("\nPress Enter to continue...")


def _c2_configure_ssh_key(config_manager):
    """Configure SSH authentication (agent mode or key file)."""
    clear_screen()

    from discovery.distributed import SSHExecutor

    if CYBER_UI_AVAILABLE:
        cyber_header("CONFIGURE SSH AUTHENTICATION")
        console = get_console()

        # Show current config
        use_agent = config_manager.config.use_ssh_agent
        current_key = config_manager.config.ssh_key_path

        console.print("[bold]Current Configuration:[/]")
        if use_agent:
            agent_ok, agent_msg = SSHExecutor.check_agent_status()
            status_color = "green" if agent_ok else "red"
            console.print(f"  Mode: [cyan]SSH Agent (recommended)[/]")
            console.print(f"  Status: [{status_color}]{agent_msg}[/]")
        else:
            console.print(f"  Mode: [yellow]Key File[/]")
            console.print(f"  Path: [cyan]{current_key or '(not set)'}[/]")

        console.print()
        console.print("[bold]Choose authentication mode:[/]")
        console.print()
        console.print("[green][1][/] SSH Agent (RECOMMENDED)")
        console.print("    [dim]Key stays on your local machine, never on EC2[/]")
        console.print("    [dim]Run: ssh-add ~/.ssh/your-key.pem before using[/]")
        console.print()
        console.print("[yellow][2][/] Key File (legacy)")
        console.print("    [dim]Specify path to .pem file[/]")
        console.print("    [dim]Less secure - key path stored in config[/]")
        console.print()
    else:
        print_section("Configure SSH Authentication", C.BRIGHT_MAGENTA)

        use_agent = config_manager.config.use_ssh_agent
        current_key = config_manager.config.ssh_key_path

        print("Current Configuration:")
        if use_agent:
            agent_ok, agent_msg = SSHExecutor.check_agent_status()
            status_color = C.GREEN if agent_ok else C.RED
            print(f"  Mode: SSH Agent (recommended)")
            print(f"  Status: {status_color}{agent_msg}{C.RESET}")
        else:
            print(f"  Mode: Key File")
            print(f"  Path: {current_key or '(not set)'}")

        print()
        print("Choose authentication mode:")
        print()
        print(f"{C.GREEN}[1]{C.RESET} SSH Agent (RECOMMENDED)")
        print(f"    {C.DIM}Key stays on your local machine, never on EC2{C.RESET}")
        print(f"    {C.DIM}Run: ssh-add ~/.ssh/your-key.pem before using{C.RESET}")
        print()
        print(f"{C.YELLOW}[2]{C.RESET} Key File (legacy)")
        print(f"    {C.DIM}Specify path to .pem file{C.RESET}")
        print(f"    {C.DIM}Less secure - key path stored in config{C.RESET}")
        print()

    choice = get_input("Select mode [1/2]")
    if not choice or not choice.strip():
        return

    choice = choice.strip()

    if choice == '1':
        # SSH Agent mode
        agent_ok, agent_msg = SSHExecutor.check_agent_status()
        if agent_ok:
            config_manager.update_settings(use_ssh_agent=True)
            if CYBER_UI_AVAILABLE:
                cyber_success(f"SSH Agent mode enabled: {agent_msg}")
                console.print("\n[dim]The -A flag will be used for all SSH connections.[/]")
                console.print("[dim]Your key never leaves your local machine.[/]")
            else:
                print_success(f"SSH Agent mode enabled: {agent_msg}")
                print("\nThe -A flag will be used for all SSH connections.")
                print("Your key never leaves your local machine.")
        else:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"SSH Agent has no keys: {agent_msg}")
                console.print("\n[yellow]To fix this, run:[/]")
                console.print("  [cyan]eval \"$(ssh-agent -s)\"[/]")
                console.print("  [cyan]ssh-add ~/.ssh/your-key.pem[/]")
                console.print("\n[dim]Then try configuring again.[/]")
            else:
                print_error(f"SSH Agent has no keys: {agent_msg}")
                print("\nTo fix this, run:")
                print("  eval \"$(ssh-agent -s)\"")
                print("  ssh-add ~/.ssh/your-key.pem")
                print("\nThen try configuring again.")

    elif choice == '2':
        # Key file mode
        if CYBER_UI_AVAILABLE:
            console.print("\n[dim]Enter path to your .pem file.[/]")
            console.print("[dim]Example: ~/.ssh/my-key.pem[/]\n")
        else:
            print("\nEnter path to your .pem file.")
            print("Example: ~/.ssh/my-key.pem\n")

        key_path = get_input("Key path")
        if not key_path or not key_path.strip():
            return

        key_path = sanitize_path(key_path.strip())

        if not os.path.exists(key_path):
            if CYBER_UI_AVAILABLE:
                cyber_error(f"File not found: {key_path}")
            else:
                print_error(f"File not found: {key_path}")
            get_input("\nPress Enter to continue...")
            return

        # Disable agent mode and set key path
        config_manager.update_settings(use_ssh_agent=False)
        config_manager.set_ssh_key(key_path)

        if CYBER_UI_AVAILABLE:
            cyber_success(f"Key file mode enabled: {key_path}")
            console.print("\n[yellow]Note: SSH Agent mode is more secure.[/]")
            console.print("[dim]Consider switching to agent mode for better security.[/]")
        else:
            print_success(f"Key file mode enabled: {key_path}")
            print(f"\n{C.YELLOW}Note: SSH Agent mode is more secure.{C.RESET}")
            print("Consider switching to agent mode for better security.")

    get_input("\nPress Enter to continue...")


def _c2_ec2_cost_guide(config_manager=None):
    """Display EC2 instance setup guide and cost recommendations."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        from rich.text import Text
        from rich.table import Table
        from rich.panel import Panel

        cyber_header("EC2 SETUP & COST GUIDE")
        console = get_console()

        # Recommendation box
        rec_text = Text()
        rec_text.append("★ RECOMMENDED: ", style="bold #00ff00")
        rec_text.append("18-20× t3.large\n", style="bold white")
        rec_text.append("  • 8GB RAM each (safe for 2 parallel scans)\n", style="#888888")
        rec_text.append("  • ~$1.50-1.66/hr total = ~$36-40/day\n", style="#888888")
        rec_text.append("  • 36-40 parallel scans across all workers\n", style="#888888")
        rec_text.append("  • Best cost-per-scan ratio", style="#00ff00")
        console.print(Panel(rec_text, title="[bold #00ff00]Best Value[/]", border_style="#00ff00"))
        console.print()

        # Cost comparison table
        table = Table(title="EC2 Instance Comparison (us-east-1 prices)", border_style="cyan")
        table.add_column("Instance", style="white", justify="left")
        table.add_column("RAM", style="cyan", justify="center")
        table.add_column("$/hr", style="yellow", justify="right")
        table.add_column("Parallel", style="green", justify="center")
        table.add_column("20 Workers", style="magenta", justify="center")
        table.add_column("Daily Cost", style="red", justify="right")

        table.add_row("t3.medium", "4GB", "$0.042", "1 each", "20 scans", "~$20")
        table.add_row("[bold #00ff00]t3.large ★[/]", "[bold]8GB[/]", "[bold]$0.083[/]", "[bold]2 each[/]", "[bold]40 scans[/]", "[bold]~$40[/]")
        table.add_row("t3.xlarge", "16GB", "$0.166", "3 each", "60 scans", "~$80")
        table.add_row("m5a.xlarge", "16GB", "$0.172", "3 each", "60 scans", "~$83")
        table.add_row("m5a.2xlarge", "32GB", "$0.344", "5 each", "100 scans", "~$165")

        console.print(table)
        console.print()

        # Why t3.large box
        why_text = Text()
        why_text.append("Why t3.large is the sweet spot:\n\n", style="bold white")
        why_text.append("• ", style="cyan")
        why_text.append("8GB RAM", style="bold")
        why_text.append(" - Enough for 2 parallel SpiderFoot scans without OOM\n", style="#888888")
        why_text.append("• ", style="cyan")
        why_text.append("$0.083/hr", style="bold")
        why_text.append(" - Half the cost of m5a.xlarge for same parallel capacity\n", style="#888888")
        why_text.append("• ", style="cyan")
        why_text.append("20 instances", style="bold")
        why_text.append(" - Stays within AWS default limit (no support ticket needed)\n", style="#888888")
        why_text.append("• ", style="cyan")
        why_text.append("More IPs", style="bold")
        why_text.append(" - Distributed scanning = less rate limiting from targets\n", style="#888888")
        console.print(Panel(why_text, title="[bold cyan]Analysis[/]", border_style="cyan"))
        console.print()

        # Example calculation
        example_text = Text()
        example_text.append("EXAMPLE: Scanning 500 domains @ ~15 min each\n\n", style="bold white")
        example_text.append("  20× t3.large (40 parallel):\n", style="#00ff00")
        example_text.append("    └─ Time: ~3.1 hours | Cost: ~$3.30\n\n", style="#888888")
        example_text.append("  5× m5a.2xlarge (25 parallel):\n", style="yellow")
        example_text.append("    └─ Time: ~5 hours | Cost: ~$8.60\n\n", style="#888888")
        example_text.append("  Savings: ", style="white")
        example_text.append("62% cheaper + 38% faster", style="bold #00ff00")
        console.print(Panel(example_text, title="[bold yellow]Cost Estimate[/]", border_style="yellow"))
        console.print()

        # Quick Setup section
        region = config_manager.config.aws_region if config_manager else "us-east-1"
        setup_text = Text()
        setup_text.append("STEP 1: ", style="bold #00ff00")
        setup_text.append("Launch your first worker manually in AWS Console\n", style="white")
        setup_text.append("         (Kali Linux AMI, t3.large, your security group & key)\n\n", style="#888888")

        setup_text.append("STEP 2: ", style="bold #00ff00")
        setup_text.append("Get your instance details (run from master):\n\n", style="white")
        setup_text.append("  # Get AMI ID:\n", style="#888888")
        setup_text.append(f"  aws ec2 describe-instances --filters \"Name=tag:Name,Values=worker_1\" \\\n", style="cyan")
        setup_text.append(f"    --region {region} --query 'Reservations[0].Instances[0].ImageId' --output text\n\n", style="cyan")
        setup_text.append("  # Get Security Group ID:\n", style="#888888")
        setup_text.append(f"  aws ec2 describe-instances --filters \"Name=tag:Name,Values=worker_1\" \\\n", style="cyan")
        setup_text.append(f"    --region {region} --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text\n\n", style="cyan")
        setup_text.append("  # Get Subnet ID:\n", style="#888888")
        setup_text.append(f"  aws ec2 describe-instances --filters \"Name=tag:Name,Values=worker_1\" \\\n", style="cyan")
        setup_text.append(f"    --region {region} --query 'Reservations[0].Instances[0].SubnetId' --output text\n\n", style="cyan")

        setup_text.append("STEP 3: ", style="bold #00ff00")
        setup_text.append("Launch 19 more workers (replace YOUR_* values):\n\n", style="white")
        setup_text.append("  for i in {2..20}; do aws ec2 run-instances \\\n", style="bold cyan")
        setup_text.append("    --image-id YOUR_AMI_ID \\\n", style="bold cyan")
        setup_text.append("    --instance-type t3.large \\\n", style="bold cyan")
        setup_text.append("    --key-name YOUR_KEY_NAME \\\n", style="bold cyan")
        setup_text.append("    --security-group-ids YOUR_SG_ID \\\n", style="bold cyan")
        setup_text.append("    --subnet-id YOUR_SUBNET_ID \\\n", style="bold cyan")
        setup_text.append("    --tag-specifications \"ResourceType=instance,Tags=[{Key=Name,Value=worker_$i}]\" \\\n", style="bold cyan")
        setup_text.append(f"    --count 1 --region {region} > /dev/null && echo \"Launched worker_$i\"; done\n\n", style="bold cyan")

        setup_text.append("STEP 4: ", style="bold #00ff00")
        setup_text.append("Get all worker hostnames (for Add Workers [2] or Replace Addresses [7]):\n\n", style="white")
        setup_text.append(f"aws ec2 describe-instances --filters \"Name=tag:Name,Values=worker_*\" \"Name=instance-state-name,Values=running\" --region {region} --query 'Reservations[].Instances[].PublicDnsName' --output text\n\n", style="bold yellow")
        setup_text.append(f"(Change --region {region} if your workers are in a different region)\n", style="#888888")
        setup_text.append("IMPORTANT: This must be pasted as ONE line in CloudShell.\n", style="bold yellow")
        setup_text.append("If copy-paste adds line breaks, paste into a text editor first,\n", style="#888888")
        setup_text.append("make sure it's all on one line, then copy that into CloudShell.\n", style="#888888")

        console.print(Panel(setup_text, title="[bold #00ff00]Quick Setup - Launch 20 Workers[/]", border_style="#00ff00"))

    else:
        # Classic terminal fallback
        region = config_manager.config.aws_region if config_manager else "us-east-1"
        print_section("EC2 Setup & Cost Guide", C.BRIGHT_CYAN)
        print(f"""
{C.BRIGHT_GREEN}★ RECOMMENDED: 18-20× t3.large{C.RESET}
  • 8GB RAM each (safe for 2 parallel scans)
  • ~$1.50-1.66/hr total = ~$36-40/day
  • 36-40 parallel scans across all workers

{C.WHITE}Instance Comparison (us-east-1 prices){C.RESET}
{C.DIM}{'─' * 65}{C.RESET}
  Instance        RAM     $/hr    Parallel   20 Workers   Daily
{C.DIM}{'─' * 65}{C.RESET}
  t3.medium       4GB     $0.042  1 each     20 scans     ~$20
  {C.BRIGHT_GREEN}t3.large ★      8GB     $0.083  2 each     40 scans     ~$40{C.RESET}
  t3.xlarge       16GB    $0.166  3 each     60 scans     ~$80
  m5a.xlarge      16GB    $0.172  3 each     60 scans     ~$83
  m5a.2xlarge     32GB    $0.344  5 each     100 scans    ~$165
{C.DIM}{'─' * 65}{C.RESET}

{C.CYAN}Why t3.large is the sweet spot:{C.RESET}
  • 8GB RAM - Enough for 2 parallel scans without OOM
  • $0.083/hr - Half the cost of m5a.xlarge
  • 20 instances - Stays within AWS default limit
  • More IPs - Less rate limiting from targets

{C.YELLOW}EXAMPLE: 500 domains @ ~15 min each{C.RESET}
  20× t3.large (40 parallel): ~3.1 hours = ~$3.30
  5× m5a.2xlarge (25 parallel): ~5 hours = ~$8.60
  {C.BRIGHT_GREEN}Savings: 62% cheaper + 38% faster{C.RESET}

{C.BRIGHT_GREEN}━━━ QUICK SETUP - Launch 20 Workers ━━━{C.RESET}

{C.WHITE}STEP 1:{C.RESET} Launch your first worker manually in AWS Console
         (Kali Linux AMI, t3.large, your security group & key)

{C.WHITE}STEP 2:{C.RESET} Get your instance details (run from master):

  {C.CYAN}# Get AMI ID:{C.RESET}
  aws ec2 describe-instances --filters "Name=tag:Name,Values=worker_1" \\
    --region {region} --query 'Reservations[0].Instances[0].ImageId' --output text

  {C.CYAN}# Get Security Group ID:{C.RESET}
  aws ec2 describe-instances --filters "Name=tag:Name,Values=worker_1" \\
    --region {region} --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text

  {C.CYAN}# Get Subnet ID:{C.RESET}
  aws ec2 describe-instances --filters "Name=tag:Name,Values=worker_1" \\
    --region {region} --query 'Reservations[0].Instances[0].SubnetId' --output text

{C.WHITE}STEP 3:{C.RESET} Launch 19 more workers (replace YOUR_* values):

  {C.BRIGHT_CYAN}for i in {{2..20}}; do aws ec2 run-instances \\
    --image-id YOUR_AMI_ID \\
    --instance-type t3.large \\
    --key-name YOUR_KEY_NAME \\
    --security-group-ids YOUR_SG_ID \\
    --subnet-id YOUR_SUBNET_ID \\
    --tag-specifications "ResourceType=instance,Tags=[{{Key=Name,Value=worker_$i}}]" \\
    --count 1 --region {region} > /dev/null && echo "Launched worker_$i"; done{C.RESET}

{C.WHITE}STEP 4:{C.RESET} Get all worker hostnames (for Add Workers [2] or Replace Addresses [7]):

{C.BRIGHT_YELLOW}aws ec2 describe-instances --filters "Name=tag:Name,Values=worker_*" "Name=instance-state-name,Values=running" --region {region} --query 'Reservations[].Instances[].PublicDnsName' --output text{C.RESET}

{C.DIM}(Change --region {region} if your workers are in a different region)
{C.BRIGHT_YELLOW}IMPORTANT:{C.RESET} {C.DIM}This must be pasted as ONE line in CloudShell.
If copy-paste adds line breaks, paste into a text editor first,
make sure it's all on one line, then copy that into CloudShell.{C.RESET}
""")

    get_input("\nPress Enter to continue...")


def _c2_setup_workers(config_manager):
    """Setup all workers (apt update, tmux, SpiderFoot install)."""
    clear_screen()

    if not config_manager.has_ssh_key():
        if CYBER_UI_AVAILABLE:
            cyber_error("SSH key not configured. Use option [4] first.")
        else:
            print_error("SSH key not configured. Use option [4] first.")
        get_input("\nPress Enter to continue...")
        return

    all_workers = config_manager.get_enabled_workers()
    if not all_workers:
        if CYBER_UI_AVAILABLE:
            cyber_error("No workers configured. Use option [2] to add workers.")
        else:
            print_error("No workers configured. Use option [2] to add workers.")
        get_input("\nPress Enter to continue...")
        return

    sorted_workers = sorted(
        all_workers,
        key=lambda w: config_manager._extract_worker_num(w.nickname)
    )

    if CYBER_UI_AVAILABLE:
        cyber_header("SETUP WORKERS")
        console = get_console()
        from rich.table import Table

        console.print("[dim]Setup installs SpiderFoot and dependencies on workers.[/]\n")
        console.print("[bold white]Workers:[/]")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("#", style="dim", width=4)
        table.add_column("Nickname", style="cyan", width=12)
        table.add_column("Hostname", style="white")
        table.add_column("SF", style="dim", width=4)
        for i, w in enumerate(sorted_workers, 1):
            sf = "Yes" if w.spiderfoot_installed else "No"
            sf_style = "green" if w.spiderfoot_installed else "red"
            table.add_row(str(i), w.nickname or "—", w.hostname, f"[{sf_style}]{sf}[/]")
        console.print(table)
        console.print()

        console.print("[bold white]Setup:[/]")
        console.print("  [cyan][1][/] Single worker  — setup one specific worker")
        console.print("  [cyan][2][/] All workers    — setup all workers\n")
    else:
        print_section("Setup Workers", C.BRIGHT_BLUE)

        print("Setup installs SpiderFoot and dependencies on workers.\n")
        print(f"{C.WHITE}Workers:{C.RESET}")
        for i, w in enumerate(sorted_workers, 1):
            sf = "Yes" if w.spiderfoot_installed else "No"
            print(f"  {i}. {w.nickname or '—'}: {w.hostname} (SF: {sf})")
        print()

        print(f"{C.WHITE}Setup:{C.RESET}")
        print(f"  {C.CYAN}[1]{C.RESET} Single worker  — setup one specific worker")
        print(f"  {C.CYAN}[2]{C.RESET} All workers    — setup all workers\n")

    mode_choice = get_input("Choice", default="1")
    if mode_choice is None:
        return
    mode_choice = mode_choice.strip()

    if mode_choice == "1":
        worker_choice = get_input("Worker # to setup")
        if worker_choice is None:
            return
        try:
            idx = int(worker_choice.strip()) - 1
            if idx < 0 or idx >= len(sorted_workers):
                raise ValueError()
            target_workers = [sorted_workers[idx]]
        except (ValueError, IndexError):
            if CYBER_UI_AVAILABLE:
                cyber_error("Invalid selection.")
            else:
                print_error("Invalid selection.")
            get_input("\nPress Enter to continue...")
            return
    elif mode_choice == "2":
        target_workers = sorted_workers
    else:
        if CYBER_UI_AVAILABLE:
            cyber_error("Invalid choice.")
        else:
            print_error("Invalid choice.")
        get_input("\nPress Enter to continue...")
        return

    worker_names = ", ".join(w.nickname or w.hostname for w in target_workers)
    if CYBER_UI_AVAILABLE:
        console.print(f"\n[dim]Will setup {len(target_workers)} worker(s): {worker_names}[/]")
        console.print("[dim]  • apt update && apt full-upgrade[/]")
        console.print("[dim]  • Install tmux[/]")
        console.print("[dim]  • Clone & install SpiderFoot[/]")
        console.print("[dim]  • Detect resources (RAM/CPU)[/]\n")

        if not cyber_confirm("Proceed with setup?"):
            return
    else:
        print(f"\nWill setup {len(target_workers)} worker(s): {worker_names}")
        print("  • apt update && apt full-upgrade")
        print("  • Install tmux")
        print("  • Clone & install SpiderFoot")
        print("  • Detect resources (RAM/CPU)\n")

        if not confirm("Proceed with setup?"):
            return

    # Create controller and run setup
    try:
        from discovery.distributed import DistributedScanController

        controller = DistributedScanController(config_manager)

        def on_progress(msg):
            if CYBER_UI_AVAILABLE:
                console.print(f"[dim]{msg}[/]")
            else:
                print(f"  {msg}")

        if CYBER_UI_AVAILABLE:
            console.print("\n[bold cyan]Starting setup...[/]\n")
        else:
            print("\nStarting setup...\n")

        # First validate connections
        if CYBER_UI_AVAILABLE:
            console.print("[yellow]Testing connections...[/]")
        else:
            print("Testing connections...")

        validation = controller.validate_workers(
            lambda h, s: on_progress(f"  {h}: {s}"),
            workers=target_workers
        )

        failed = [h for h, (ok, _) in validation.items() if not ok]
        if failed:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Failed to connect to: {', '.join(failed)}")
            else:
                print_error(f"Failed to connect to: {', '.join(failed)}")
            get_input("\nPress Enter to continue...")
            return

        # Detect resources
        if CYBER_UI_AVAILABLE:
            console.print("\n[yellow]Detecting resources...[/]")
        else:
            print("\nDetecting resources...")

        resources = controller.detect_all_resources(
            lambda h, s: on_progress(f"  {h}: {s}"),
            workers=target_workers
        )

        # Run full setup
        if CYBER_UI_AVAILABLE:
            console.print("\n[yellow]Installing software (this may take 10-15 minutes)...[/]\n")
        else:
            print("\nInstalling software (this may take 10-15 minutes)...\n")

        results = controller.setup_all_workers(on_progress, workers=target_workers)

        # Summary
        success_count = sum(1 for r in results.values() if r.success)

        if CYBER_UI_AVAILABLE:
            console.print(f"\n[bold green]Setup complete: {success_count}/{len(target_workers)} workers ready[/]")
        else:
            print(f"\nSetup complete: {success_count}/{len(target_workers)} workers ready")

        for hostname, result in results.items():
            if not result.success:
                if CYBER_UI_AVAILABLE:
                    console.print(f"[red]  ✗ {hostname}: {result.error_message}[/]")
                else:
                    print(f"  ✗ {hostname}: {result.error_message}")

    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Setup failed: {e}")
        else:
            print_error(f"Setup failed: {e}")

    get_input("\nPress Enter to continue...")


def _c2_start_distributed_scan(config_manager):
    """Start a distributed scan across all workers."""
    from discovery.distributed import check_local_security

    clear_screen()

    if not config_manager.has_ssh_key():
        if CYBER_UI_AVAILABLE:
            cyber_error("SSH key not configured. Use option [4] first.")
        else:
            print_error("SSH key not configured. Use option [4] first.")
        get_input("\nPress Enter to continue...")
        return

    workers = config_manager.get_enabled_workers()
    if not workers:
        if CYBER_UI_AVAILABLE:
            cyber_error("No workers configured.")
        else:
            print_error("No workers configured.")
        get_input("\nPress Enter to continue...")
        return

    # Check if SpiderFoot is installed on all workers
    workers_without_sf = [w for w in workers if not w.spiderfoot_installed]
    if workers_without_sf:
        worker_names = ", ".join([w.get_display_name() for w in workers_without_sf])
        if CYBER_UI_AVAILABLE:
            cyber_error(f"SpiderFoot not installed on: {worker_names}")
            console = get_console()
            console.print("\n[yellow]Run option [5] 'Setup Workers' to install SpiderFoot, or[/]")
            console.print("[yellow]Run option [1] 'View Worker Status' to refresh detection.[/]")
        else:
            print_error(f"SpiderFoot not installed on: {worker_names}")
            print(f"\n{C.YELLOW}Run option [5] 'Setup Workers' to install SpiderFoot, or{C.RESET}")
            print(f"{C.YELLOW}Run option [1] 'View Worker Status' to refresh detection.{C.RESET}")
        get_input("\nPress Enter to continue...")
        return

    # Pre-flight security check - warn if sensitive files detected
    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print("\n[dim]Running pre-flight security check...[/]")
    else:
        print("\nRunning pre-flight security check...")

    local_safe, local_warnings = check_local_security()
    if not local_safe:
        if CYBER_UI_AVAILABLE:
            console.print("\n[bold red]SECURITY WARNING[/]")
            for warning in local_warnings:
                console.print(f"  [red]{warning}[/]")
            console.print()
            if not cyber_confirm("Security issues detected. Continue anyway?"):
                return
        else:
            print(f"\n{C.RED}SECURITY WARNING{C.RESET}")
            for warning in local_warnings:
                print(f"  {C.RED}{warning}{C.RESET}")
            print()
            if not confirm("Security issues detected. Continue anyway?"):
                return
    else:
        if CYBER_UI_AVAILABLE:
            console.print("[green]Security check passed[/]\n")
        else:
            print(f"{C.GREEN}Security check passed{C.RESET}\n")

    # Check if using WebAPI mode - requires tmux on master to maintain connection
    scan_mode = getattr(config_manager.config, 'scan_mode', 'cli')
    if scan_mode == 'webapi' and not is_running_in_tmux():
        if CYBER_UI_AVAILABLE:
            console = get_console()
            from rich.panel import Panel
            console.print()
            console.print(Panel(
                "[bold yellow]WebAPI Mode Requires Persistent Connection[/]\n\n"
                "[white]In WebAPI mode, the master machine manages a rolling queue of scans.\n"
                "If you close this terminal, the scan queue will be interrupted.\n\n"
                "[bold cyan]Launching tmux session to maintain connection...[/]",
                title="[bold yellow]⟨ INITIALIZING TMUX ⟩[/]",
                border_style="yellow"
            ))
            console.print()
        else:
            print(f"\n{C.BRIGHT_YELLOW}{'='*60}{C.RESET}")
            print(f"{C.BRIGHT_YELLOW}  INITIALIZING TMUX SESSION{C.RESET}")
            print(f"{C.BRIGHT_YELLOW}{'='*60}{C.RESET}")
            print(f"\n{C.WHITE}WebAPI mode requires a persistent connection to manage scans.{C.RESET}")
            print(f"{C.CYAN}Launching tmux session to maintain connection...{C.RESET}\n")

        # Try to launch in tmux automatically
        # Pass "c2" to resume in the C2 distributed scanning menu (not main menu)
        if auto_launch_in_tmux("puppetmaster", start_menu="c2"):
            # This line is never reached if launch_in_tmux succeeds
            # (it uses execvp to replace the current process)
            pass
        else:
            # tmux not available - fall back to warning
            if CYBER_UI_AVAILABLE:
                cyber_error("tmux is not installed. Cannot maintain persistent connection.")
                console.print("\n[yellow]Install tmux: sudo apt install tmux[/]")
                console.print("[yellow]Or switch to CLI mode which doesn't require tmux.[/]\n")
                if not cyber_confirm("Continue anyway (connection may be lost)?"):
                    return
            else:
                print_error("tmux is not installed. Cannot maintain persistent connection.")
                print(f"\n{C.YELLOW}Install tmux: sudo apt install tmux{C.RESET}")
                print(f"{C.YELLOW}Or switch to CLI mode which doesn't require tmux.{C.RESET}\n")
                if not confirm("Continue anyway (connection may be lost)?"):
                    return
    elif scan_mode == 'webapi' and is_running_in_tmux():
        session_name = get_tmux_session_name()
        if CYBER_UI_AVAILABLE:
            console = get_console()
            session_info = f" ({session_name})" if session_name else ""
            console.print(f"[green]✓ Running in tmux{session_info} - connection will persist[/]\n")
        else:
            session_info = f" ({session_name})" if session_name else ""
            print(f"{C.GREEN}✓ Running in tmux{session_info} - connection will persist{C.RESET}\n")

    # Get domains from pending queue (check both sources)
    config = load_config()
    pending_domains = config.get('pending_domains', [])

    # Also check JobTracker for pending domains
    if not pending_domains:
        try:
            from discovery.jobs import JobTracker
            tracker = JobTracker()
            tracker_pending = tracker.get_pending()
            if tracker_pending:
                pending_domains = [job.domain for job in tracker_pending]
                if CYBER_UI_AVAILABLE:
                    console = get_console()
                    console.print(f"[cyan]Found {len(pending_domains)} domains in scan queue (JobTracker)[/]")
                else:
                    print_info(f"Found {len(pending_domains)} domains in scan queue (JobTracker)")
        except ImportError:
            pass

    if not pending_domains:
        if CYBER_UI_AVAILABLE:
            cyber_error("No domains found. Load domains via [1] Scrape, [2] Load file, or [12] Domain Queue Manager.")
        else:
            print_error("No domains found. Load domains via [1] Scrape, [2] Load file, or [12] Domain Queue Manager.")
        get_input("\nPress Enter to continue...")
        return

    if CYBER_UI_AVAILABLE:
        cyber_header("START DISTRIBUTED SCAN")
        console = get_console()
        from rich.panel import Panel

        # Distribution preview
        domains_per_worker = len(pending_domains) // len(workers)
        remainder = len(pending_domains) % len(workers)

        console.print(Panel(
            f"[white]Domains:[/] [cyan]{len(pending_domains)}[/]\n"
            f"[white]Workers:[/] [cyan]{len(workers)}[/]\n"
            f"[white]Per worker:[/] [green]~{domains_per_worker}[/] domains "
            f"[dim](+{remainder} distributed to first workers)[/]",
            title="[bold yellow]⟨ DISTRIBUTION ⟩[/]",
            border_style="yellow"
        ))
        console.print()

        # Intensity selection
        console.print("[bold]Select scan intensity:[/]\n")
        console.print("  [1] [green]ALL[/]        - Full scan with all modules (slowest, most thorough)")
        console.print("  [2] [yellow]FOOTPRINT[/]  - Focus on domain infrastructure")
        console.print("  [3] [cyan]INVESTIGATE[/] - Balanced for general investigation")
        console.print("  [4] [blue]PASSIVE[/]     - Passive only, no active probing (fastest)\n")
    else:
        print_section("Start Distributed Scan", C.BRIGHT_RED)

        domains_per_worker = len(pending_domains) // len(workers)

        print(f"\nDomains: {len(pending_domains)}")
        print(f"Workers: {len(workers)}")
        print(f"Per worker: ~{domains_per_worker} domains\n")

        print("Select scan intensity:\n")
        print("  [1] ALL        - Full scan with all modules")
        print("  [2] FOOTPRINT  - Focus on domain infrastructure")
        print("  [3] INVESTIGATE - Balanced investigation")
        print("  [4] PASSIVE    - Passive only (fastest)\n")

    intensity_choice = get_input("Intensity [1-4]")
    intensity_map = {'1': 'all', '2': 'footprint', '3': 'investigate', '4': 'passive'}
    intensity = intensity_map.get(intensity_choice, 'all')

    if CYBER_UI_AVAILABLE:
        if not cyber_confirm(f"\nStart scan with {intensity.upper()} intensity?"):
            return
    else:
        if not confirm(f"\nStart scan with {intensity.upper()} intensity?"):
            return

    # Start the scan
    try:
        from discovery.distributed import DistributedScanController

        controller = DistributedScanController(config_manager)

        def on_progress(msg):
            if CYBER_UI_AVAILABLE:
                console.print(f"[dim]{msg}[/]")
            else:
                print(f"  {msg}")

        if CYBER_UI_AVAILABLE:
            console.print("\n[bold cyan]Launching distributed scan...[/]\n")
        else:
            print("\nLaunching distributed scan...\n")

        success, message, details = controller.start_distributed_scan(
            pending_domains,
            intensity=intensity,
            on_progress=on_progress
        )

        if success:
            if CYBER_UI_AVAILABLE:
                cyber_success(message)
                console.print("\n[bold green]Scans are now running in the background on workers.[/]")
                console.print("[dim]The master manages the rolling queue - keep this session running.[/]")
                console.print("[dim]Use option [P] to check progress, [A] to abort all scans.[/]")
            else:
                print_success(message)
                print("\nScans are now running in the background on workers.")
                print("The master manages the rolling queue - keep this session running.")
                print("Use option [P] to check progress, [A] to abort all scans.")
        else:
            if CYBER_UI_AVAILABLE:
                cyber_error(message)
                # Show detailed per-worker errors
                if details and 'workers' in details:
                    console.print("\n[bold red]Worker Details:[/]")
                    for hostname, worker_info in details['workers'].items():
                        if not worker_info.get('success'):
                            error_msg = worker_info.get('message', 'Unknown error')
                            console.print(f"  [red]✗[/] {hostname}: {error_msg}")
            else:
                print_error(message)
                # Show detailed per-worker errors
                if details and 'workers' in details:
                    print("\nWorker Details:")
                    for hostname, worker_info in details['workers'].items():
                        if not worker_info.get('success'):
                            error_msg = worker_info.get('message', 'Unknown error')
                            print(f"  ✗ {hostname}: {error_msg}")

    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Failed to start scan: {e}")
        else:
            print_error(f"Failed to start scan: {e}")

    get_input("\nPress Enter to return to C2 menu...")


def _c2_display_progress(config_manager, controller, auto_mode_info=None):
    """Display progress from all workers. Returns (total_completed, total_domains)."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        cyber_header("SCAN PROGRESS")
        console = get_console()

        # Show auto-refresh status if active
        if auto_mode_info:
            elapsed_secs = time.time() - auto_mode_info['start_time']
            hours = int(elapsed_secs // 3600)
            minutes = int((elapsed_secs % 3600) // 60)
            elapsed_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            console.print(f"[bold cyan]🔄 Auto-refresh[/] [dim](every {auto_mode_info['interval']} min)[/] | "
                         f"[yellow]Running: {elapsed_str}[/] | "
                         f"[green]Updates: {auto_mode_info['update_count']}[/]\n")

        console.print("[dim]Fetching progress from workers...[/]\n")
    else:
        print_section("Scan Progress", C.BRIGHT_CYAN)
        if auto_mode_info:
            elapsed_secs = time.time() - auto_mode_info['start_time']
            hours = int(elapsed_secs // 3600)
            minutes = int((elapsed_secs % 3600) // 60)
            elapsed_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            print(f"Auto-refresh (every {auto_mode_info['interval']} min) | Running: {elapsed_str} | Updates: {auto_mode_info['update_count']}\n")
        print("Fetching progress from workers...\n")

    total_completed = 0
    total_domains = 0

    try:
        progress_data = controller.get_all_progress()

        if CYBER_UI_AVAILABLE:
            from rich.table import Table

            table = Table(title="Worker Progress", border_style="cyan")
            table.add_column("Worker", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Progress", style="white")
            table.add_column("Running", style="yellow")
            table.add_column("CSVs", style="magenta")
            table.add_column("Failed", style="red")

            for hostname, prog in progress_data.items():
                status_color = {
                    "scanning": "yellow",
                    "completed": "green",
                    "stopped": "red",
                    "starting": "cyan",
                    "idle": "dim",
                    "error": "red",
                    "unreachable": "red",
                }.get(prog.status, "white")

                pct = prog.progress_percent
                progress_str = f"{prog.domains_completed}/{prog.domains_total} ({pct:.0f}%)"

                table.add_row(
                    prog.nickname,
                    f"[{status_color}]{prog.status}[/]",
                    progress_str,
                    str(prog.running_processes),
                    str(prog.csv_files_count),
                    str(prog.domains_failed)
                )

                total_completed += prog.domains_completed
                total_domains += prog.domains_total

            console.print(table)

            if total_domains > 0:
                overall_pct = (total_completed / total_domains) * 100
                console.print(f"\n[bold]Overall:[/] [cyan]{total_completed}[/]/[white]{total_domains}[/] [dim]({overall_pct:.1f}%)[/]")
        else:
            for hostname, prog in progress_data.items():
                print(f"\n  {prog.nickname} ({hostname})")
                print(f"    Status: {prog.status}")
                print(f"    Progress: {prog.domains_completed}/{prog.domains_total} ({prog.progress_percent:.0f}%)")
                print(f"    Running processes: {prog.running_processes}")
                print(f"    CSV files: {prog.csv_files_count}")
                print(f"    Failed domains: {prog.domains_failed}")

                total_completed += prog.domains_completed
                total_domains += prog.domains_total

            if total_domains > 0:
                overall_pct = (total_completed / total_domains) * 100
                print(f"\nOverall: {total_completed}/{total_domains} ({overall_pct:.1f}%)")

    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Failed to get progress: {e}")
        else:
            print_error(f"Failed to get progress: {e}")

    return total_completed, total_domains


def _c2_auto_refresh_loop(config_manager, controller, interval_minutes):
    """Run auto-refresh loop until user presses Q."""
    import select
    import sys
    import termios
    import tty

    auto_mode_info = {
        'start_time': time.time(),
        'interval': interval_minutes,
        'update_count': 1
    }

    # Display initial progress
    _c2_display_progress(config_manager, controller, auto_mode_info)

    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print(f"\n[dim]Next refresh in {interval_minutes} min. Press [bold]Q[/bold] to stop auto-refresh...[/]")
    else:
        print(f"\nNext refresh in {interval_minutes} min. Press Q to stop auto-refresh...")

    interval_seconds = interval_minutes * 60
    last_refresh = time.time()

    # Check if stdin is a TTY (not available in CI/CD or backgrounded processes)
    if not sys.stdin.isatty():
        print_info("Auto-refresh not available in non-TTY mode.")
        return

    # Save terminal settings
    old_settings = termios.tcgetattr(sys.stdin)

    try:
        # Set terminal to raw mode for non-blocking input
        tty.setcbreak(sys.stdin.fileno())

        while True:
            # Check for input (non-blocking)
            if select.select([sys.stdin], [], [], 0.5)[0]:
                char = sys.stdin.read(1).lower()
                if char == 'q':
                    break

            # Check if it's time to refresh
            if time.time() - last_refresh >= interval_seconds:
                auto_mode_info['update_count'] += 1
                _c2_display_progress(config_manager, controller, auto_mode_info)

                if CYBER_UI_AVAILABLE:
                    console = get_console()
                    console.print(f"\n[dim]Next refresh in {interval_minutes} min. Press [bold]Q[/bold] to stop auto-refresh...[/]")
                else:
                    print(f"\nNext refresh in {interval_minutes} min. Press Q to stop auto-refresh...")

                last_refresh = time.time()

    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Auto-refresh error: {e}")
        else:
            print_error(f"Auto-refresh error: {e}")

    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print("\n[cyan]Auto-refresh stopped.[/]")
    else:
        print("\nAuto-refresh stopped.")


def _c2_check_progress(config_manager):
    """Check progress on all workers."""
    if not config_manager.has_ssh_key():
        if CYBER_UI_AVAILABLE:
            cyber_error("SSH key not configured.")
        else:
            print_error("SSH key not configured.")
        get_input("\nPress Enter to continue...")
        return

    workers = config_manager.get_enabled_workers()
    if not workers:
        if CYBER_UI_AVAILABLE:
            cyber_error("No workers configured.")
        else:
            print_error("No workers configured.")
        get_input("\nPress Enter to continue...")
        return

    try:
        from discovery.distributed import DistributedScanController
        controller = DistributedScanController(config_manager)
    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Failed to initialize controller: {e}")
        else:
            print_error(f"Failed to initialize controller: {e}")
        get_input("\nPress Enter to continue...")
        return

    # Initial display
    _c2_display_progress(config_manager, controller)

    # Refresh loop
    while True:
        if CYBER_UI_AVAILABLE:
            console = get_console()
            console.print("\n[dim]Options: [R] Refresh  [A] Auto-refresh  [Q] Return to menu[/]")
        else:
            print("\nOptions: [R] Refresh  [A] Auto-refresh  [Q] Return to menu")

        choice = get_input("► Choice")
        if choice is None or choice.lower() in ('q', ''):
            break
        elif choice.lower() == 'r':
            _c2_display_progress(config_manager, controller)
        elif choice.lower() == 'a':
            # Get refresh interval
            if CYBER_UI_AVAILABLE:
                console = get_console()
                console.print("\n[cyan]Enter refresh interval in minutes (default: 5):[/]")
            else:
                print("\nEnter refresh interval in minutes (default: 5):")

            interval_str = get_input("► Interval")
            try:
                interval = int(interval_str) if interval_str and interval_str.strip() else 5
                if interval < 1:
                    interval = 1
                    print_info("Interval clamped to minimum of 1 minute")
                elif interval > 60:
                    interval = 60
                    print_info("Interval clamped to maximum of 60 minutes")
            except ValueError:
                interval = 5

            _c2_auto_refresh_loop(config_manager, controller, interval)
            # After auto-refresh ends, show the display again
            _c2_display_progress(config_manager, controller)


def _c2_stop_all_scans(config_manager):
    """Stop scans and restart GUIs for result access."""
    clear_screen()

    all_workers = config_manager.get_enabled_workers()
    if not all_workers:
        if CYBER_UI_AVAILABLE:
            cyber_error("No workers configured.")
        else:
            print_error("No workers configured.")
        get_input("\nPress Enter to continue...")
        return

    sorted_workers = sorted(
        all_workers,
        key=lambda w: config_manager._extract_worker_num(w.nickname)
    )

    if CYBER_UI_AVAILABLE:
        cyber_header("STOP SCANS")
        console = get_console()
        from rich.table import Table

        console.print("[bold yellow]Stop running scans and restart GUIs for result access.[/]")
        console.print("[dim]Completed scan results will remain accessible via the GUI.[/]\n")

        console.print("[bold white]Workers:[/]")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("#", style="dim", width=4)
        table.add_column("Nickname", style="cyan", width=12)
        table.add_column("Hostname", style="white")
        table.add_column("Status", style="yellow", width=10)
        for i, w in enumerate(sorted_workers, 1):
            status_color = {"scanning": "yellow", "completed": "cyan", "idle": "dim"}.get(w.status, "white")
            table.add_row(str(i), w.nickname or "—", w.hostname, f"[{status_color}]{w.status}[/]")
        console.print(table)
        console.print()

        console.print("[bold white]Stop:[/]")
        console.print("  [cyan][1][/] Single worker  — stop one specific worker")
        console.print("  [cyan][2][/] All workers    — stop all workers\n")
    else:
        print_section("Stop Scans", C.BRIGHT_RED)
        print("Stop running scans and restart GUIs for result access.")
        print("Completed scan results will remain accessible via the GUI.\n")

        print(f"{C.WHITE}Workers:{C.RESET}")
        for i, w in enumerate(sorted_workers, 1):
            print(f"  {i}. {w.nickname or '—'}: {w.hostname} ({w.status})")
        print()

        print(f"{C.WHITE}Stop:{C.RESET}")
        print(f"  {C.CYAN}[1]{C.RESET} Single worker  — stop one specific worker")
        print(f"  {C.CYAN}[2]{C.RESET} All workers    — stop all workers\n")

    mode_choice = get_input("Choice", default="2")
    if mode_choice is None:
        return
    mode_choice = mode_choice.strip()

    if mode_choice == "1":
        worker_choice = get_input("Worker # to stop")
        if worker_choice is None:
            return
        try:
            idx = int(worker_choice.strip()) - 1
            if idx < 0 or idx >= len(sorted_workers):
                raise ValueError()
            target_workers = [sorted_workers[idx]]
        except (ValueError, IndexError):
            if CYBER_UI_AVAILABLE:
                cyber_error("Invalid selection.")
            else:
                print_error("Invalid selection.")
            get_input("\nPress Enter to continue...")
            return
    elif mode_choice == "2":
        target_workers = sorted_workers
    else:
        if CYBER_UI_AVAILABLE:
            cyber_error("Invalid choice.")
        else:
            print_error("Invalid choice.")
        get_input("\nPress Enter to continue...")
        return

    worker_names = ", ".join(w.nickname or w.hostname for w in target_workers)
    if CYBER_UI_AVAILABLE:
        if not cyber_confirm(f"Stop scans on {len(target_workers)} worker(s) ({worker_names})?"):
            return
    else:
        if not confirm(f"Stop scans on {len(target_workers)} worker(s)?"):
            return

    try:
        from discovery.distributed import DistributedScanController

        controller = DistributedScanController(config_manager)

        # Progress callback to show per-worker status
        def on_progress(msg):
            if CYBER_UI_AVAILABLE:
                console.print(msg)
            else:
                print(msg)

        if CYBER_UI_AVAILABLE:
            console.print()  # Blank line before progress

        if len(target_workers) == len(sorted_workers):
            # All workers — use abort_all_scans which also handles end_session
            results = controller.abort_all_scans(
                save_aborted=True,
                restart_gui=True,
                on_progress=on_progress
            )
            success_count = sum(1 for ok, _ in results.values() if ok)
        else:
            # Single worker(s)
            success_count = 0
            total = len(target_workers)
            for i, worker in enumerate(target_workers, 1):
                if on_progress:
                    on_progress(f"[{i}/{total}] Stopping {worker.nickname or worker.hostname}...")
                success, message, _ = controller.abort_worker_scans(
                    worker.hostname,
                    save_aborted=True
                )
                if success:
                    success_count += 1
                    # Restart GUI so results remain accessible
                    if config_manager.config.scan_mode == "webapi":
                        try:
                            controller.start_spiderfoot_web(worker, port=worker.gui_port, force_restart=True)
                        except Exception:
                            pass
                if on_progress:
                    status = "✓" if success else "✗"
                    on_progress(f"  {status} {worker.nickname or worker.hostname}")

        if CYBER_UI_AVAILABLE:
            console.print()  # Blank line after progress
            cyber_success(f"Stopped scans and restarted GUIs on {success_count}/{len(target_workers)} workers")
            console.print("[dim]You can now access completed results via the GUI tunnels.[/]")
        else:
            print()
            print_success(f"Stopped scans and restarted GUIs on {success_count}/{len(target_workers)} workers")
            print("You can now access completed results via the GUI tunnels.")

    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Stop failed: {e}")
        else:
            print_error(f"Stop failed: {e}")

    get_input("\nPress Enter to continue...")


def _c2_abort_all_scans(config_manager):
    """Brute force kill scans immediately without restarting GUIs."""
    clear_screen()

    all_workers = config_manager.get_enabled_workers()
    if not all_workers:
        if CYBER_UI_AVAILABLE:
            cyber_error("No workers configured.")
        else:
            print_error("No workers configured.")
        get_input("\nPress Enter to continue...")
        return

    sorted_workers = sorted(
        all_workers,
        key=lambda w: config_manager._extract_worker_num(w.nickname)
    )

    if CYBER_UI_AVAILABLE:
        cyber_header("ABORT SCANS")
        console = get_console()
        from rich.table import Table

        console.print("[bold red]Kill all scans and processes immediately.[/]")
        console.print("[dim]GUIs will NOT be restarted. Use this when things are stuck.[/]\n")

        console.print("[bold white]Workers:[/]")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("#", style="dim", width=4)
        table.add_column("Nickname", style="cyan", width=12)
        table.add_column("Hostname", style="white")
        table.add_column("Status", style="yellow", width=10)
        for i, w in enumerate(sorted_workers, 1):
            status_color = {"scanning": "yellow", "completed": "cyan", "idle": "dim"}.get(w.status, "white")
            table.add_row(str(i), w.nickname or "—", w.hostname, f"[{status_color}]{w.status}[/]")
        console.print(table)
        console.print()

        console.print("[bold white]Abort:[/]")
        console.print("  [cyan][1][/] Single worker  — abort one specific worker")
        console.print("  [cyan][2][/] All workers    — abort all workers\n")
    else:
        print_section("Abort Scans", C.BRIGHT_RED)
        print("Kill all scans and processes immediately.")
        print("GUIs will NOT be restarted. Use this when things are stuck.\n")

        print(f"{C.WHITE}Workers:{C.RESET}")
        for i, w in enumerate(sorted_workers, 1):
            print(f"  {i}. {w.nickname or '—'}: {w.hostname} ({w.status})")
        print()

        print(f"{C.WHITE}Abort:{C.RESET}")
        print(f"  {C.CYAN}[1]{C.RESET} Single worker  — abort one specific worker")
        print(f"  {C.CYAN}[2]{C.RESET} All workers    — abort all workers\n")

    mode_choice = get_input("Choice", default="2")
    if mode_choice is None:
        return
    mode_choice = mode_choice.strip()

    if mode_choice == "1":
        worker_choice = get_input("Worker # to abort")
        if worker_choice is None:
            return
        try:
            idx = int(worker_choice.strip()) - 1
            if idx < 0 or idx >= len(sorted_workers):
                raise ValueError()
            target_workers = [sorted_workers[idx]]
        except (ValueError, IndexError):
            if CYBER_UI_AVAILABLE:
                cyber_error("Invalid selection.")
            else:
                print_error("Invalid selection.")
            get_input("\nPress Enter to continue...")
            return
    elif mode_choice == "2":
        target_workers = sorted_workers
    else:
        if CYBER_UI_AVAILABLE:
            cyber_error("Invalid choice.")
        else:
            print_error("Invalid choice.")
        get_input("\nPress Enter to continue...")
        return

    worker_names = ", ".join(w.nickname or w.hostname for w in target_workers)
    if CYBER_UI_AVAILABLE:
        if not cyber_confirm(f"Abort scans on {len(target_workers)} worker(s) ({worker_names})?"):
            return
    else:
        if not confirm(f"Abort scans on {len(target_workers)} worker(s)?"):
            return

    try:
        from discovery.distributed import DistributedScanController

        controller = DistributedScanController(config_manager)

        # Progress callback to show per-worker status
        def on_progress(msg):
            if CYBER_UI_AVAILABLE:
                console.print(msg)
            else:
                print(msg)

        if CYBER_UI_AVAILABLE:
            console.print()  # Blank line before progress

        if len(target_workers) == len(sorted_workers):
            # All workers — use abort_all_scans which also handles end_session
            results = controller.abort_all_scans(
                save_aborted=True,
                restart_gui=False,
                on_progress=on_progress
            )
            success_count = sum(1 for ok, _ in results.values() if ok)
        else:
            # Single worker(s)
            success_count = 0
            total = len(target_workers)
            for i, worker in enumerate(target_workers, 1):
                if on_progress:
                    on_progress(f"[{i}/{total}] Aborting {worker.nickname or worker.hostname}...")
                success, message, _ = controller.abort_worker_scans(
                    worker.hostname,
                    save_aborted=True
                )
                if success:
                    success_count += 1
                if on_progress:
                    status = "✓" if success else "✗"
                    on_progress(f"  {status} {worker.nickname or worker.hostname}")

        if CYBER_UI_AVAILABLE:
            console.print()  # Blank line after progress
            cyber_success(f"Aborted scans on {success_count}/{len(target_workers)} workers")
        else:
            print_success(f"Aborted scans on {success_count}/{len(target_workers)} workers")

    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Abort failed: {e}")
        else:
            print_error(f"Abort failed: {e}")

    get_input("\nPress Enter to continue...")


def _c2_recover_worker(config_manager):
    """Recover results from a failed worker and redistribute unfinished domains."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        cyber_header("RECOVER FAILED WORKER")
        console = get_console()
    else:
        print_section("Recover Failed Worker", C.BRIGHT_YELLOW)

    workers = config_manager.get_all_workers()
    if not workers:
        msg = "No workers configured."
        if CYBER_UI_AVAILABLE:
            cyber_info(msg)
        else:
            print_info(msg)
        get_input("\nPress Enter to continue...")
        return

    # Show workers with status
    if CYBER_UI_AVAILABLE:
        console.print("[dim]Select the worker that failed or needs recovery:[/]\n")
        for i, w in enumerate(sorted(workers, key=lambda x: config_manager._extract_worker_num(x.nickname)), 1):
            status_color = "red" if w.status in ("error", "unreachable") else "yellow" if w.status == "scanning" else "green"
            sf_status = "No" if not w.spiderfoot_installed else "Yes"
            console.print(f"  [{status_color}]{i}[/] {w.nickname or '—'}: {w.hostname} [dim](status: {w.status or 'unknown'}, SF: {sf_status})[/]")
        console.print()
    else:
        print("Select the worker that failed or needs recovery:\n")
        sorted_workers = sorted(workers, key=lambda x: config_manager._extract_worker_num(x.nickname))
        for i, w in enumerate(sorted_workers, 1):
            print(f"  {i}. {w.nickname or '—'}: {w.hostname} (status: {w.status or 'unknown'})")
        print()

    sorted_workers = sorted(workers, key=lambda x: config_manager._extract_worker_num(x.nickname))

    choice = get_input("Worker number (or Q to cancel)")
    if not choice or choice.lower() == 'q':
        return

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(sorted_workers):
            raise ValueError()
        worker = sorted_workers[idx]
    except (ValueError, IndexError):
        if CYBER_UI_AVAILABLE:
            cyber_error("Invalid selection.")
        else:
            print_error("Invalid selection.")
        get_input("\nPress Enter to continue...")
        return

    # Validate SSH key (supports both key file and agent mode)
    if not config_manager.has_ssh_key():
        msg = "SSH key not configured. Use option [4] first."
        if CYBER_UI_AVAILABLE:
            cyber_error(msg)
        else:
            print_error(msg)
        get_input("\nPress Enter to continue...")
        return

    # Create controller
    from discovery.distributed import DistributedScanController
    controller = DistributedScanController(config_manager)

    output_dir = config_manager.config.master_output_dir or "./distributed_results"

    if CYBER_UI_AVAILABLE:
        console.print(f"\n[bold]Recovering {worker.nickname}[/] ({worker.hostname})...")
        console.print("[dim]Checking if worker is reachable...[/]\n")
    else:
        print(f"\nRecovering {worker.nickname} ({worker.hostname})...")
        print("Checking if worker is reachable...\n")

    # Run recovery
    def progress(msg):
        if CYBER_UI_AVAILABLE:
            console.print(f"  [dim]{msg}[/]")
        else:
            print(f"  {msg}")

    try:
        completed, unfinished, downloaded = controller.recover_failed_worker(
            worker, output_dir, on_progress=progress
        )
    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Recovery failed: {e}")
        else:
            print_error(f"Recovery failed: {e}")
        get_input("\nPress Enter to continue...")
        return

    # Show summary
    print()
    if CYBER_UI_AVAILABLE:
        console.print(f"[bold green]Completed domains:[/] {len(completed)}")
        if downloaded > 0:
            console.print(f"[bold green]Results downloaded:[/] {downloaded} files")
        console.print(f"[bold yellow]Unfinished domains:[/] {len(unfinished)}")
        if unfinished:
            console.print(f"\n[dim]Unfinished domains:[/]")
            for d in unfinished:
                console.print(f"  [yellow]•[/] {d}")
    else:
        print(f"Completed domains: {len(completed)}")
        if downloaded > 0:
            print(f"Results downloaded: {downloaded} files")
        print(f"Unfinished domains: {len(unfinished)}")
        if unfinished:
            print(f"\nUnfinished domains:")
            for d in unfinished:
                print(f"  • {d}")

    # Offer redistribution
    if unfinished:
        print()
        redistribute = confirm(f"Redistribute {len(unfinished)} domains to available workers?")
        if redistribute:
            # Get intensity from current session or default
            intensity = "passive"  # Safe default
            if CYBER_UI_AVAILABLE:
                console.print(f"\n[dim]Using intensity: {intensity}[/]")
                console.print("[dim]Starting redistribution...[/]\n")
            else:
                print(f"\nUsing intensity: {intensity}")
                print("Starting redistribution...\n")

            try:
                success, msg = controller.redistribute_domains(
                    unfinished, intensity=intensity, on_progress=progress
                )
            except Exception as e:
                if CYBER_UI_AVAILABLE:
                    cyber_error(f"Redistribution failed: {e}")
                else:
                    print_error(f"Redistribution failed: {e}")
                get_input("\nPress Enter to continue...")
                return

            print()
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
    elif not completed and not unfinished:
        msg = "No domain list found for this worker. Was it part of the current scan session?"
        if CYBER_UI_AVAILABLE:
            cyber_info(msg)
        else:
            print_info(msg)

    get_input("\nPress Enter to continue...")


def _c2_resume_all_workers(config_manager):
    """Resume scanning on all workers — find unsubmitted domains and restart rolling queues."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        cyber_header("RESUME ALL WORKERS")
        console = get_console()
    else:
        print_section("Resume All Workers", C.BRIGHT_CYAN)

    if not config_manager.has_ssh_key():
        msg = "SSH key not configured. Use option [4] first."
        if CYBER_UI_AVAILABLE:
            cyber_error(msg)
        else:
            print_error(msg)
        get_input("\nPress Enter to continue...")
        return

    workers = config_manager.get_enabled_workers()
    if not workers:
        if CYBER_UI_AVAILABLE:
            cyber_warning("No workers configured.")
        else:
            print_warning("No workers configured.")
        get_input("\nPress Enter to continue...")
        return

    if CYBER_UI_AVAILABLE:
        console.print("[dim]This will check all workers and resume any unsubmitted domains.[/]")
        console.print("[dim]Running and completed scans will NOT be duplicated.[/]\n")
    else:
        print("This will check all workers and resume any unsubmitted domains.")
        print("Running and completed scans will NOT be duplicated.\n")

    # Ask for intensity
    if CYBER_UI_AVAILABLE:
        console.print("[bold white]Scan intensity for resumed domains:[/]")
        console.print("  [cyan][1][/] All modules")
        console.print("  [cyan][2][/] Footprint")
        console.print("  [cyan][3][/] Investigate")
        console.print("  [cyan][4][/] Passive (Recommended)\n")
    else:
        print("Scan intensity for resumed domains:")
        print(f"  {C.CYAN}[1]{C.RESET} All modules")
        print(f"  {C.CYAN}[2]{C.RESET} Footprint")
        print(f"  {C.CYAN}[3]{C.RESET} Investigate")
        print(f"  {C.CYAN}[4]{C.RESET} Passive (Recommended)\n")

    intensity_map = {'1': 'all', '2': 'footprint', '3': 'investigate', '4': 'passive'}
    intensity_choice = get_input("Intensity", default="4")
    if intensity_choice is None:
        return
    intensity = intensity_map.get(intensity_choice.strip(), "passive")

    if not confirm(f"Resume unsubmitted domains with '{intensity}' intensity?"):
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled.")
        else:
            print_info("Cancelled.")
        get_input("\nPress Enter to continue...")
        return

    # Create controller and run resume
    from discovery.distributed import DistributedScanController
    controller = DistributedScanController(config_manager)

    def progress(msg):
        if CYBER_UI_AVAILABLE:
            console.print(f"  [dim]{msg}[/]")
        else:
            print(f"  {msg}")

    if CYBER_UI_AVAILABLE:
        console.print("\n[bold cyan]Analyzing workers...[/]\n")
    else:
        print(f"\n{C.CYAN}Analyzing workers...{C.RESET}\n")

    try:
        success, message, details = controller.resume_all_workers(
            intensity=intensity, on_progress=progress
        )
    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Resume failed: {e}")
        else:
            print_error(f"Resume failed: {e}")
        get_input("\nPress Enter to continue...")
        return

    # Show summary table
    print()
    if CYBER_UI_AVAILABLE:
        from rich.table import Table
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Worker", style="cyan", width=12)
        table.add_column("Assigned", style="white", justify="right", width=8)
        table.add_column("Submitted", style="green", justify="right", width=9)
        table.add_column("Unsubmitted", style="yellow", justify="right", width=11)
        table.add_column("Status", style="dim")

        for nickname in sorted(details.keys()):
            info = details[nickname]
            status_style = "green" if info.get('unsubmitted', 0) == 0 else "yellow"
            status_text = info.get('reason', info.get('status', ''))
            if info.get('status') == 'ok' and info.get('unsubmitted', 0) == 0:
                status_text = f"all submitted ({info.get('active_scans', 0)} active)"
            elif info.get('status') == 'ok':
                status_text = f"resuming ({info.get('active_scans', 0)} active)"
            table.add_row(
                nickname,
                str(info.get('assigned', 0)),
                str(info.get('submitted', 0)),
                str(info.get('unsubmitted', 0)),
                f"[{status_style}]{status_text}[/]"
            )
        console.print(table)
        console.print()
    else:
        print(f"{'Worker':<14} {'Assigned':>8} {'Submitted':>9} {'Unsub':>7}  Status")
        print(f"{'─'*14} {'─'*8} {'─'*9} {'─'*7}  {'─'*20}")
        for nickname in sorted(details.keys()):
            info = details[nickname]
            status_text = info.get('reason', info.get('status', ''))
            if info.get('status') == 'ok' and info.get('unsubmitted', 0) == 0:
                status_text = f"all submitted ({info.get('active_scans', 0)} active)"
            elif info.get('status') == 'ok':
                status_text = f"resuming ({info.get('active_scans', 0)} active)"
            print(f"{nickname:<14} {info.get('assigned', 0):>8} {info.get('submitted', 0):>9} {info.get('unsubmitted', 0):>7}  {status_text}")
        print()

    if success:
        if CYBER_UI_AVAILABLE:
            cyber_success(message)
        else:
            print_success(message)
    else:
        if CYBER_UI_AVAILABLE:
            cyber_error(message)
        else:
            print_error(message)

    get_input("\nPress Enter to continue...")


def _c2_view_aborted_domains(config_manager):
    """View list of aborted domains."""
    clear_screen()

    aborted = config_manager.config.aborted_domains

    if CYBER_UI_AVAILABLE:
        cyber_header("ABORTED DOMAINS")
        console = get_console()

        if not aborted:
            console.print("[green]No aborted domains.[/]")
        else:
            from rich.table import Table

            table = Table(title=f"Aborted Domains ({len(aborted)})", border_style="red")
            table.add_column("Domain", style="white")
            table.add_column("Reason", style="yellow")
            table.add_column("Worker", style="cyan")
            table.add_column("Time", style="dim")

            for item in aborted[:50]:  # Show first 50
                table.add_row(
                    item.get('domain', 'unknown'),
                    item.get('reason', 'unknown'),
                    item.get('worker', '-'),
                    item.get('timestamp', '-')[:19] if item.get('timestamp') else '-'
                )

            console.print(table)

            if len(aborted) > 50:
                console.print(f"\n[dim]... and {len(aborted) - 50} more[/]")
    else:
        print_section("Aborted Domains", C.BRIGHT_YELLOW)

        if not aborted:
            print_info("No aborted domains.")
        else:
            print(f"\nTotal: {len(aborted)} domains\n")
            for item in aborted[:20]:
                print(f"  {item.get('domain', 'unknown')} - {item.get('reason', 'unknown')}")
            if len(aborted) > 20:
                print(f"\n  ... and {len(aborted) - 20} more")

    get_input("\nPress Enter to continue...")


def _c2_collect_results(config_manager):
    """Collect results from all workers."""
    clear_screen()

    if not config_manager.has_ssh_key():
        if CYBER_UI_AVAILABLE:
            cyber_error("SSH key not configured.")
        else:
            print_error("SSH key not configured.")
        get_input("\nPress Enter to continue...")
        return

    if CYBER_UI_AVAILABLE:
        cyber_header("COLLECT RESULTS")
        console = get_console()
        console.print("[dim]Enter directory to save collected results.[/]")
        console.print("[dim]Default: ./distributed_results[/]\n")
    else:
        print_section("Collect Results", C.BRIGHT_GREEN)
        print("Enter directory to save collected results.")
        print("Default: ./distributed_results\n")

    output_dir = get_input("Output directory")
    if not output_dir or not output_dir.strip():
        output_dir = "./distributed_results"

    output_dir = sanitize_path(output_dir.strip())

    if CYBER_UI_AVAILABLE:
        console.print(f"\n[dim]Collecting to: {output_dir}[/]\n")
    else:
        print(f"\nCollecting to: {output_dir}\n")

    try:
        from discovery.distributed import DistributedScanController

        controller = DistributedScanController(config_manager)

        def on_progress(msg):
            if CYBER_UI_AVAILABLE:
                console.print(f"[dim]{msg}[/]")
            else:
                print(f"  {msg}")

        results = controller.collect_results(output_dir, on_progress)

        total_files = sum(count for _, _, count in results.values())

        if CYBER_UI_AVAILABLE:
            cyber_success(f"Collected {total_files} files to {output_dir}")
        else:
            print_success(f"Collected {total_files} files to {output_dir}")

    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Collection failed: {e}")
        else:
            print_error(f"Collection failed: {e}")

    get_input("\nPress Enter to continue...")


def _c2_gui_access(config_manager):
    """Show SSH tunnel commands for GUI access and option to start GUI on workers."""

    while True:
        # Reload workers each iteration to pick up address changes
        workers = config_manager.get_enabled_workers()

        if not workers:
            clear_screen()
            if CYBER_UI_AVAILABLE:
                cyber_header("GUI ACCESS")
                console = get_console()
                console.print("[yellow]No workers configured.[/]")
            else:
                print_section("GUI Access", C.BRIGHT_RED)
                print_info("No workers configured.")
            get_input("\nPress Enter to continue...")
            return

        clear_screen()

        if CYBER_UI_AVAILABLE:
            cyber_header("GUI ACCESS")
            console = get_console()
            from rich.panel import Panel
            from rich.table import Table

            # Show instructions
            console.print("[bold yellow]NOTE:[/] To access the GUI from your LOCAL machine:\n")
            console.print("  1. First, start the GUI on a worker using option [S] below")
            console.print("  2. Then run the SSH tunnel command on your LOCAL machine")
            console.print("  3. Replace the pem path with YOUR local path to the .pem file\n")

            console.print("[dim]SSH tunnel commands (run from YOUR LOCAL machine):[/]\n")

            for i, w in enumerate(workers):
                local_port = 5001 + i
                cmd = f"ssh -i [yellow]<</path/to/your/key.pem>>[/] -L {local_port}:localhost:{w.gui_port} {w.username}@{w.hostname}"

                console.print(Panel(
                    f"{cmd}\n\n"
                    f"Then open: [cyan]http://localhost:{local_port}[/]",
                    title=f"[bold cyan]{w.get_display_name()}[/]",
                    border_style="cyan"
                ))
                console.print()

            # Show worker table for starting GUI
            table = Table(title="Start GUI on Worker", border_style="green")
            table.add_column("#", style="cyan")
            table.add_column("Worker", style="white")
            table.add_column("Hostname", style="dim")

            for i, w in enumerate(workers, 1):
                table.add_row(str(i), w.get_display_name(), w.hostname)

            console.print(table)
            console.print("\n[S] Start GUI on a worker")
            console.print("[Q] Back\n")

            choice = get_input("► Select option: ", "q")
            choice = choice.lower() if choice else "q"

            if choice == 's':
                worker_num = get_input("► Worker number: ", "")
                try:
                    idx = int(worker_num) - 1
                    if 0 <= idx < len(workers):
                        _start_gui_on_worker(config_manager, workers[idx])
                    else:
                        cyber_error("Invalid worker number.")
                except ValueError:
                    cyber_error("Invalid input.")
                get_input("\nPress Enter to continue...")
                # Loop back to GUI menu
            elif choice == 'q':
                return
            else:
                # Try as worker number directly
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(workers):
                        _start_gui_on_worker(config_manager, workers[idx])
                        get_input("\nPress Enter to continue...")
                        # Loop back to GUI menu
                except ValueError:
                    pass
        else:
            print_section("GUI Access", C.BRIGHT_RED)

            print("NOTE: To access the GUI from your LOCAL machine:\n")
            print("  1. First, start the GUI on a worker using option [S] below")
            print("  2. Then run the SSH tunnel command on your LOCAL machine")
            print("  3. Replace the pem path with YOUR local path to the .pem file\n")

            print("SSH tunnel commands (run from YOUR LOCAL machine):\n")

            for i, w in enumerate(workers):
                local_port = 5001 + i
                cmd = f"ssh -i <</path/to/your/key.pem>> -L {local_port}:localhost:{w.gui_port} {w.username}@{w.hostname}"

                print(f"  {w.get_display_name()}:")
                print(f"    {cmd}")
                print(f"    Open: http://localhost:{local_port}\n")

            print("\n[S] Start GUI on a worker")
            print("[Q] Back\n")

            choice = get_input("► Select option: ", "q")
            choice = choice.lower() if choice else "q"

            if choice == 's':
                for i, w in enumerate(workers, 1):
                    print(f"  {i}. {w.get_display_name()} - {w.hostname}")
                worker_num = get_input("\n► Worker number: ", "")
                try:
                    idx = int(worker_num) - 1
                    if 0 <= idx < len(workers):
                        _start_gui_on_worker(config_manager, workers[idx])
                    else:
                        print_error("Invalid worker number.")
                except ValueError:
                    print_error("Invalid input.")
                get_input("\nPress Enter to continue...")
                # Loop back to GUI menu
            elif choice == 'q':
                return


def _start_gui_on_worker(config_manager, worker):
    """Start SpiderFoot GUI on a worker via SSH.

    IMPORTANT: This function checks if the GUI is already running first
    to avoid killing running scans. Only starts a new server if none is running.
    """
    from discovery.distributed import SSHExecutor
    import time

    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print(f"\n[cyan]Checking SpiderFoot GUI on {worker.get_display_name()}...[/]")
    else:
        print(f"\nChecking SpiderFoot GUI on {worker.get_display_name()}...")

    ssh = SSHExecutor(
        key_path=config_manager.config.ssh_key_path,
        timeout=config_manager.config.ssh_timeout,
        use_agent=config_manager.config.use_ssh_agent
    )

    # FIRST: Check if GUI is already running - DON'T kill running scans!
    port = worker.gui_port
    check_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/ 2>/dev/null || echo '000'"
    check_result = ssh.execute(worker.hostname, worker.username, check_cmd, timeout=10)

    if check_result.stdout.strip() == "200":
        # GUI is already running - use it
        if CYBER_UI_AVAILABLE:
            console.print(f"[green]✓ GUI already running on {worker.get_display_name()}![/]")
            console.print(f"[dim]Connect via SSH tunnel to access it (scans preserved).[/]")
        else:
            print_success(f"GUI already running on {worker.get_display_name()}!")
            print("Connect via SSH tunnel to access it (scans preserved).")
        return

    # GUI not running - safe to start
    if CYBER_UI_AVAILABLE:
        console.print(f"[cyan]Starting SpiderFoot GUI on {worker.get_display_name()}...[/]")
    else:
        print(f"Starting SpiderFoot GUI on {worker.get_display_name()}...")

    # Start GUI in tmux session (more reliable than nohup)
    sf_dir = config_manager.config.spiderfoot_install_dir.replace("~", f"/home/{worker.username}")
    start_cmd = (
        f'tmux kill-session -t sf-web 2>/dev/null || true && '
        f'tmux new-session -d -s sf-web "cd {sf_dir} && ./venv/bin/python3 sf.py -l 0.0.0.0:{port}" && '
        f'echo "STARTED"'
    )

    result = ssh.execute(worker.hostname, worker.username, start_cmd, timeout=30)

    if "STARTED" not in (result.stdout or ""):
        if CYBER_UI_AVAILABLE:
            console.print(f"[red]✗ Failed to launch tmux session: {result.stderr}[/]")
        else:
            print_error(f"Failed to launch tmux session: {result.stderr}")
        return

    # Retry loop: 15 attempts x 2s = 30s max wait for server to come up
    if CYBER_UI_AVAILABLE:
        console.print(f"[dim]Waiting for web server to become ready (up to 30s)...[/]")
    else:
        print("Waiting for web server to become ready (up to 30s)...")

    started = False
    for attempt in range(15):
        time.sleep(2)
        check_result = ssh.execute(
            worker.hostname, worker.username,
            f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/ 2>/dev/null || echo '000'",
            timeout=10
        )
        if check_result.stdout.strip() == "200":
            started = True
            break

    if started:
        if CYBER_UI_AVAILABLE:
            console.print(f"[green]✓ GUI started successfully on {worker.get_display_name()}![/]")
            console.print(f"[dim]Now run the SSH tunnel command on your local machine to access it.[/]")
        else:
            print_success(f"GUI started successfully on {worker.get_display_name()}!")
            print("Now run the SSH tunnel command on your local machine to access it.")
    else:
        # Fetch logs to show the actual error
        if CYBER_UI_AVAILABLE:
            console.print(f"[red]✗ GUI failed to start within 30s on {worker.get_display_name()}.[/]")
        else:
            print_error(f"GUI failed to start within 30s on {worker.get_display_name()}.")

        # Show tmux output
        tmux_result = ssh.execute(
            worker.hostname, worker.username,
            f"tmux capture-pane -t sf-web -p 2>/dev/null | tail -20",
            timeout=10
        )
        if tmux_result.success and tmux_result.stdout.strip():
            if CYBER_UI_AVAILABLE:
                console.print(f"[yellow]tmux session output:[/]")
                console.print(f"[dim]{tmux_result.stdout.strip()}[/]")
            else:
                print(f"tmux session output:")
                print(tmux_result.stdout.strip())

        # Show log file
        log_result = ssh.execute(
            worker.hostname, worker.username,
            "tail -30 /tmp/sf_gui.log 2>/dev/null || echo 'No log file found'",
            timeout=10
        )
        if log_result.success and log_result.stdout.strip():
            if CYBER_UI_AVAILABLE:
                console.print(f"[yellow]Startup log (/tmp/sf_gui.log):[/]")
                console.print(f"[dim]{log_result.stdout.strip()}[/]")
            else:
                print(f"Startup log (/tmp/sf_gui.log):")
                print(log_result.stdout.strip())


def _debug_print(title, content, error=False):
    """Print a debug section with title and content, adapting to Rich/non-Rich mode."""
    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        console = get_console()
        if error:
            console.print(Panel(content, title=f"[bold red]{title}[/]", border_style="red"))
        else:
            console.print(Panel(content, title=f"[bold green]{title}[/]", border_style="green"))
    else:
        color = C.RED if error else C.GREEN
        print(f"\n{color}{title}:{C.RESET}")
        print(f"{C.DIM}{'─' * 60}{C.RESET}")
        print(content)
        print(f"{C.DIM}{'─' * 60}{C.RESET}")


def _debug_print_header(text):
    """Print a debug status header."""
    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print(f"\n[yellow]{text}[/]")
    else:
        print(f"\n{text}")


def _c2_debug_worker_logs(config_manager):
    """View worker scan logs for debugging."""
    clear_screen()

    if not config_manager.has_ssh_key():
        if CYBER_UI_AVAILABLE:
            cyber_error("SSH key not configured.")
        else:
            print_error("SSH key not configured.")
        get_input("\nPress Enter to continue...")
        return

    workers = config_manager.get_enabled_workers()

    if not workers:
        if CYBER_UI_AVAILABLE:
            cyber_error("No workers configured.")
        else:
            print_error("No workers configured.")
        get_input("\nPress Enter to continue...")
        return

    if CYBER_UI_AVAILABLE:
        cyber_header("DEBUG WORKER LOGS")
        console = get_console()
        from rich.table import Table

        table = Table(title="Select Worker", border_style="cyan")
        table.add_column("#", style="cyan")
        table.add_column("Nickname", style="white")
        table.add_column("Hostname", style="dim")

        for i, w in enumerate(workers, 1):
            table.add_row(str(i), w.nickname or "N/A", w.hostname)

        console.print(table)
    else:
        print_section("Debug Worker Logs", C.YELLOW)
        print("\nSelect worker:\n")
        for i, w in enumerate(workers, 1):
            print(f"  [{i}] {w.get_display_name()}")

    choice = get_input("\nWorker number (or 'q' to cancel)")
    if not choice or choice.lower() == 'q':
        return

    try:
        worker_idx = int(choice.strip()) - 1
        if worker_idx < 0 or worker_idx >= len(workers):
            raise ValueError()
    except ValueError:
        if CYBER_UI_AVAILABLE:
            cyber_error("Invalid selection.")
        else:
            print_error("Invalid selection.")
        get_input("\nPress Enter to continue...")
        return

    worker = workers[worker_idx]

    try:
        from discovery.distributed import DistributedScanController

        controller = DistributedScanController(config_manager)
        ssh = controller.ssh  # Reuse controller's SSH connection
        scan_mode = config_manager.config.scan_mode

        if CYBER_UI_AVAILABLE:
            console.print(f"\n[bold cyan]═══ {worker.get_display_name()} ═══[/]")
            console.print(f"[dim]Scan mode: {scan_mode}[/]\n")
        else:
            print(f"\n{'=' * 60}")
            print(f"Worker: {worker.get_display_name()}")
            print(f"Scan mode: {scan_mode}")
            print('=' * 60)

        if scan_mode == "webapi":
            # WebAPI mode: query the SpiderFoot web server directly
            port = worker.gui_port

            # 1. Check web server status
            is_running, active_scans, ssh_ok = controller.check_web_server_status(worker)

            if not ssh_ok:
                _debug_print("Web Server", "SSH connection failed - worker may be unreachable", error=True)
            elif not is_running:
                _debug_print("Web Server", "NOT RUNNING - SpiderFoot web server is down", error=True)
            else:
                _debug_print("Web Server", f"Running on port {port} with {active_scans} active scan(s)")

            # 2. Query scanlist for scan statuses
            if ssh_ok:
                scanlist_cmd = f"""curl -s http://127.0.0.1:{port}/scanlist 2>/dev/null | python3 -c "
import sys,json
try:
    data=json.load(sys.stdin)
    for s in data:
        print(f'  {{s[2]:40s}} {{s[6]:15s}} started:{{s[4] or \"N/A\":20s}} ended:{{s[5] or \"running\":20s}}')
    if not data:
        print('  (no scans found)')
except (json.JSONDecodeError, ValueError, KeyError, IndexError, TypeError):
    print('  ERROR: Could not parse scanlist')
" 2>/dev/null || echo '  Web server not responding'"""
                result = ssh.execute(worker.hostname, worker.username, scanlist_cmd, timeout=15)
                _debug_print("Scan List", result.stdout.strip() if result.success else "Failed to query scanlist")

            # 3. Show sf-web tmux session output
            if ssh_ok:
                tmux_result = ssh.execute(
                    worker.hostname, worker.username,
                    "tmux capture-pane -t sf-web -p 2>/dev/null | tail -50",
                    timeout=15
                )
                if tmux_result.success and tmux_result.stdout.strip():
                    _debug_print("Web Server Output (tmux sf-web)", tmux_result.stdout.strip())
                else:
                    _debug_print("Web Server Output", "No sf-web tmux session found")

            # 4. Show startup log
            if ssh_ok:
                log_result = ssh.execute(
                    worker.hostname, worker.username,
                    "tail -30 /tmp/sf_gui.log 2>/dev/null || echo 'No startup log found'",
                    timeout=15
                )
                if log_result.success and log_result.stdout.strip():
                    _debug_print("Startup Log (/tmp/sf_gui.log)", log_result.stdout.strip())

            # 5. Show SpiderFoot processes
            if ssh_ok:
                ps_result = ssh.execute(
                    worker.hostname, worker.username,
                    "ps aux | grep -E 'sf\\.py|spiderfoot|python3' | grep -v grep || echo '  No SpiderFoot processes found'",
                    timeout=10
                )
                if ps_result.success:
                    _debug_print("SpiderFoot Processes", ps_result.stdout.strip())

        else:
            # CLI mode: show log files and tmux session (original behavior)
            # Get scan log
            _debug_print_header("Fetching scan log...")
            log_success, log_content = controller.get_worker_logs(worker.hostname, lines=100)
            if log_success:
                _debug_print("Scan Log (last 100 lines)", log_content)
            else:
                _debug_print("Scan Log", log_content, error=True)

            # Get tmux output
            _debug_print_header("Fetching tmux session output...")
            tmux_success, tmux_content = controller.get_tmux_output(worker.hostname, lines=50)
            if tmux_success:
                _debug_print("Tmux Session (last 50 lines)", tmux_content)
            else:
                _debug_print("Tmux Session", tmux_content, error=True)

            # Get error logs
            _debug_print_header("Checking for error logs...")
            error_success, error_content = controller.get_worker_errors(worker.hostname, limit=10)
            if error_success and "No error files found" not in error_content:
                _debug_print("Scan Errors", error_content, error=True)
            elif error_success:
                _debug_print("Scan Errors", error_content)
            else:
                _debug_print("Scan Errors", error_content, error=True)

    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Failed to fetch logs: {e}")
        else:
            print_error(f"Failed to fetch logs: {e}")

    get_input("\nPress Enter to continue...")


def _c2_reset_worker_databases(config_manager):
    """Reset SpiderFoot databases on all workers (wipe ~/.spiderfoot)."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        cyber_header("RESET WORKER DATABASES")
        console = get_console()
    else:
        print_section("Reset Worker Databases", C.BRIGHT_YELLOW)

    workers = config_manager.get_enabled_workers()

    if not workers:
        if CYBER_UI_AVAILABLE:
            cyber_warning("No workers configured.")
        else:
            print_warning("No workers configured.")
        get_input("\nPress Enter to continue...")
        return

    if not config_manager.has_ssh_key():
        if CYBER_UI_AVAILABLE:
            cyber_error("SSH key not configured. Use option [4] first.")
        else:
            print_error("SSH key not configured. Use option [4] first.")
        get_input("\nPress Enter to continue...")
        return

    sorted_workers = sorted(
        workers,
        key=lambda w: config_manager._extract_worker_num(w.nickname)
    )

    # Show workers and choose mode
    if CYBER_UI_AVAILABLE:
        console.print("[bold white]Workers:[/]")
        from rich.table import Table
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("#", style="dim", width=4)
        table.add_column("Nickname", style="cyan", width=12)
        table.add_column("Hostname", style="white")
        for i, w in enumerate(sorted_workers, 1):
            table.add_row(str(i), w.nickname or "—", w.hostname)
        console.print(table)
        console.print()

        console.print("[bold white]Reset:[/]")
        console.print("  [cyan][1][/] Single worker  — reset one worker's database")
        console.print("  [cyan][2][/] All workers    — reset ALL worker databases\n")
    else:
        print(f"{C.WHITE}Workers:{C.RESET}")
        for i, w in enumerate(sorted_workers, 1):
            print(f"  {i}. {w.nickname or '—'}: {w.hostname}")
        print()

        print(f"{C.WHITE}Reset:{C.RESET}")
        print(f"  {C.CYAN}[1]{C.RESET} Single worker  — reset one worker's database")
        print(f"  {C.CYAN}[2]{C.RESET} All workers    — reset ALL worker databases\n")

    mode_choice = get_input("Choice", default="1")
    if mode_choice is None:
        return
    mode_choice = mode_choice.strip()

    # Determine target workers
    if mode_choice == "1":
        worker_choice = get_input("Worker # to reset")
        if worker_choice is None:
            return
        try:
            idx = int(worker_choice.strip()) - 1
            if idx < 0 or idx >= len(sorted_workers):
                raise ValueError()
            target_workers = [sorted_workers[idx]]
        except (ValueError, IndexError):
            if CYBER_UI_AVAILABLE:
                cyber_error("Invalid selection.")
            else:
                print_error("Invalid selection.")
            get_input("\nPress Enter to continue...")
            return

        # Confirm single
        w = target_workers[0]
        if CYBER_UI_AVAILABLE:
            console.print(f"\n[bold yellow]WARNING:[/] This will delete [red]~/.spiderfoot[/] on [cyan]{w.nickname}[/] ({w.hostname}).")
            console.print("[dim]This kills all processes and removes scan history.[/]\n")
            proceed = cyber_confirm(f"Reset {w.nickname}?")
        else:
            print(f"\n{C.YELLOW}WARNING:{C.RESET} This will delete {C.RED}~/.spiderfoot{C.RESET} on {w.nickname} ({w.hostname}).")
            print(f"{C.DIM}This kills all processes and removes scan history.{C.RESET}\n")
            proceed = confirm(f"Reset {w.nickname}?")
    elif mode_choice == "2":
        target_workers = sorted_workers
        if CYBER_UI_AVAILABLE:
            console.print(f"\n[bold yellow]WARNING:[/] This will delete [red]~/.spiderfoot[/] on ALL {len(workers)} workers.")
            console.print("[dim]This removes all scan history and cached data from SpiderFoot.[/]")
            console.print("[dim]Use this to free up disk space or start fresh scans.[/]\n")
            proceed = cyber_confirm("Continue with database reset?")
        else:
            print(f"\n{C.YELLOW}WARNING:{C.RESET} This will delete {C.RED}~/.spiderfoot{C.RESET} on ALL {len(workers)} workers.")
            print(f"{C.DIM}This removes all scan history and cached data from SpiderFoot.{C.RESET}")
            print(f"{C.DIM}Use this to free up disk space or start fresh scans.{C.RESET}\n")
            proceed = confirm("Continue with database reset?")
    else:
        if CYBER_UI_AVAILABLE:
            cyber_error("Invalid choice.")
        else:
            print_error("Invalid choice.")
        get_input("\nPress Enter to continue...")
        return

    if not proceed:
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled.")
        else:
            print_info("Cancelled.")
        get_input("\nPress Enter to continue...")
        return

    # Execute reset
    from discovery.distributed import SSHExecutor

    ssh = SSHExecutor(
        key_path=config_manager.config.ssh_key_path,
        timeout=config_manager.config.ssh_timeout,
        use_agent=config_manager.config.use_ssh_agent
    )

    if CYBER_UI_AVAILABLE:
        console.print(f"\n[cyan]Resetting database on {len(target_workers)} worker(s)...[/]\n")
    else:
        print(f"\n{C.CYAN}Resetting database on {len(target_workers)} worker(s)...{C.RESET}\n")

    success_count = 0
    fail_count = 0

    import time as _time

    for worker in target_workers:
        hostname = worker.hostname
        username = worker.username
        nickname = worker.nickname or hostname

        # FIRST: Kill all scan-related processes to release database locks
        kill_cmd = f"""
tmux kill-server 2>/dev/null || true
pkill -9 -f run_scans.sh 2>/dev/null || true
pkill -9 -f timeout 2>/dev/null || true
killall -9 timeout 2>/dev/null || true
pkill -9 -u {username} python3 2>/dev/null || true
pkill -9 -u {username} python 2>/dev/null || true
killall -9 -u {username} python3 2>/dev/null || true
pkill -9 -f sf.py 2>/dev/null || true
pkill -9 -f spiderfoot 2>/dev/null || true
kill -9 $(pgrep -u {username} python3) 2>/dev/null || true
kill -9 $(pgrep -f sf.py) 2>/dev/null || true
true
"""
        ssh.execute(hostname, username, kill_cmd, timeout=30)

        # Brief pause to let processes die
        _time.sleep(2)

        # SECOND: Remove ~/.spiderfoot directory and output files
        reset_cmd = "rm -rf ~/.spiderfoot ~/sf_distributed/output ~/sf_distributed/logs && mkdir -p ~/sf_distributed/output ~/sf_distributed/logs && echo 'DB_RESET_OK'"
        result = ssh.execute(hostname, username, reset_cmd, timeout=30)

        if result.success and 'DB_RESET_OK' in result.stdout:
            success_count += 1
            config_manager.update_worker(
                hostname,
                status="idle",
                assigned_domains=0,
                completed_domains=0,
                failed_domains=0
            )
            if CYBER_UI_AVAILABLE:
                console.print(f"  [green]✓[/] {nickname}: Killed processes + reset database")
            else:
                print(f"  {C.GREEN}✓{C.RESET} {nickname}: Killed processes + reset database")
        else:
            fail_count += 1
            error_msg = result.stderr[:50] if result.stderr else "Unknown error"
            if CYBER_UI_AVAILABLE:
                console.print(f"  [red]✗[/] {nickname}: Failed - {error_msg}")
            else:
                print(f"  {C.RED}✗{C.RESET} {nickname}: Failed - {error_msg}")

    # Summary
    if CYBER_UI_AVAILABLE:
        console.print()
        if fail_count == 0:
            cyber_success(f"All {success_count} worker(s) reset successfully.")
        else:
            cyber_warning(f"{success_count} succeeded, {fail_count} failed.")
    else:
        print()
        if fail_count == 0:
            print_success(f"All {success_count} worker(s) reset successfully.")
        else:
            print_warning(f"{success_count} succeeded, {fail_count} failed.")

    get_input("\nPress Enter to continue...")


def _c2_verify_workers_clean(config_manager):
    """Verify all workers are clean (no running scans/processes)."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        cyber_header("VERIFY WORKERS CLEAN")
        console = get_console()
        console.print("[dim]Checking all workers for running scan processes...[/]\n")
    else:
        print_section("Verify Workers Clean", C.BRIGHT_CYAN)
        print("Checking all workers for running scan processes...\n")

    workers = config_manager.get_enabled_workers()
    if not workers:
        if CYBER_UI_AVAILABLE:
            cyber_warning("No workers configured.")
        else:
            print_warning("No workers configured.")
        get_input("\nPress Enter to continue...")
        return

    from discovery.distributed import SSHExecutor
    ssh = SSHExecutor(
        key_path=config_manager.config.ssh_key_path,
        timeout=config_manager.config.ssh_timeout,
        use_agent=config_manager.config.use_ssh_agent
    )

    all_clean = True

    for worker in workers:
        hostname = worker.hostname
        username = worker.username
        nickname = worker.nickname or hostname

        if CYBER_UI_AVAILABLE:
            console.print(f"\n[bold cyan]━━━ {nickname} ━━━[/]")
        else:
            print(f"\n{C.BRIGHT_CYAN}━━━ {nickname} ━━━{C.RESET}")

        # Check for scan-related processes
        check_cmd = f"""
echo "=== Python3 processes (user {username}) ==="
pgrep -u {username} -a python3 2>/dev/null | grep -v glances || echo "  (none)"

echo ""
echo "=== SpiderFoot processes ==="
ps aux | grep -E "(sf\\.py|spiderfoot)" | grep -v grep || echo "  (none)"

echo ""
echo "=== Timeout processes ==="
pgrep -a timeout 2>/dev/null || echo "  (none)"

echo ""
echo "=== run_scans.sh processes ==="
pgrep -af run_scans.sh 2>/dev/null | grep -v "pgrep" | grep -v "echo" || echo "  (none)"

echo ""
echo "=== Tmux sessions ==="
tmux ls 2>/dev/null || echo "  (no tmux server running)"

echo ""
echo "=== SpiderFoot database ==="
if [ -d ~/.spiderfoot ]; then
    ls -la ~/.spiderfoot/ 2>/dev/null | head -5
    echo "  (database exists)"
else
    echo "  (not found - clean)"
fi

echo ""
echo "=== Output directory ==="
OUTPUT_COUNT=$(find ~/sf_distributed/output -maxdepth 1 -name "*.csv" 2>/dev/null | wc -l)
ERROR_COUNT=$(find ~/sf_distributed/output -maxdepth 1 -name "error_*.log" 2>/dev/null | wc -l)
echo "  CSVs: $OUTPUT_COUNT, Errors: $ERROR_COUNT"
"""
        result = ssh.execute(hostname, username, check_cmd, timeout=30)

        if result.success:
            output = result.stdout.strip()

            # Check if worker is clean by counting "(none)" markers
            # Each clean section should have "(none)" - we expect 4 "(none)" markers for clean
            none_count = output.count('(none)')
            is_clean = none_count >= 4  # Python3, SpiderFoot, Timeout, run_scans.sh should all be "(none)"

            if not is_clean:
                all_clean = False

            # Print output
            if CYBER_UI_AVAILABLE:
                for line in output.split('\n'):
                    if line.startswith('==='):
                        console.print(f"[bold]{line}[/]")
                    elif '(none)' in line or '(clean)' in line or '(not found' in line or '(no tmux' in line:
                        console.print(f"[green]{line}[/]")
                    elif line.strip().startswith('(') or line.strip() == '':
                        console.print(f"[dim]{line}[/]")
                    elif 'CSVs:' in line or 'Errors:' in line:
                        console.print(f"[dim]{line}[/]")
                    else:
                        # Actual process line - show in red
                        console.print(f"[red]{line}[/]")
            else:
                for line in output.split('\n'):
                    if line.startswith('==='):
                        print(f"{C.BOLD}{line}{C.RESET}")
                    elif '(none)' in line or '(clean)' in line or '(not found' in line or '(no tmux' in line:
                        print(f"{C.GREEN}{line}{C.RESET}")
                    elif line.strip().startswith('(') or line.strip() == '' or 'CSVs:' in line:
                        print(f"{C.DIM}{line}{C.RESET}")
                    else:
                        print(f"{C.RED}{line}{C.RESET}")
        else:
            all_clean = False
            if CYBER_UI_AVAILABLE:
                console.print(f"[red]  Failed to check: {result.stderr[:50]}[/]")
            else:
                print(f"{C.RED}  Failed to check: {result.stderr[:50]}{C.RESET}")

    # Summary
    print()
    if all_clean:
        if CYBER_UI_AVAILABLE:
            cyber_success("All workers appear clean - no running scan processes detected.")
        else:
            print_success("All workers appear clean - no running scan processes detected.")
    else:
        if CYBER_UI_AVAILABLE:
            cyber_warning("Some workers may have running processes. Review output above.")
        else:
            print_warning("Some workers may have running processes. Review output above.")

    get_input("\nPress Enter to continue...")


def _c2_security_audit(config_manager):
    """Run comprehensive security audit on master and workers."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        cyber_header("SECURITY AUDIT")
        console = get_console()
        from rich.panel import Panel
        from rich.table import Table
        console.print("[dim]Scanning for sensitive files (keys, credentials, secrets)...[/]\n")
    else:
        print_section("Security Audit", C.RED)
        print("Scanning for sensitive files (keys, credentials, secrets)...\n")

    from discovery.distributed import (
        check_local_security,
        run_preflight_security_check,
        SSHExecutor,
    )

    all_safe = True
    issues_found = []

    # 1. Check local puppetmaster directory
    if CYBER_UI_AVAILABLE:
        console.print("[bold cyan]1. Local Puppetmaster Directory[/]")
    else:
        print(f"{C.BRIGHT_CYAN}1. Local Puppetmaster Directory{C.RESET}")

    local_safe, local_warnings = check_local_security()
    if local_safe:
        if CYBER_UI_AVAILABLE:
            console.print("   [green]SAFE - No sensitive files found[/]\n")
        else:
            print(f"   {C.GREEN}SAFE - No sensitive files found{C.RESET}\n")
    else:
        all_safe = False
        for warning in local_warnings:
            issues_found.append(warning)
            if CYBER_UI_AVAILABLE:
                if "CRITICAL" in warning:
                    console.print(f"   [bold red]{warning}[/]")
                else:
                    console.print(f"   [yellow]{warning}[/]")
            else:
                if "CRITICAL" in warning:
                    print(f"   {C.RED}{warning}{C.RESET}")
                else:
                    print(f"   {C.YELLOW}{warning}{C.RESET}")
        print()

    # 2. Check SSH agent (if using agent mode)
    if config_manager.config.use_ssh_agent:
        if CYBER_UI_AVAILABLE:
            console.print("[bold cyan]2. SSH Agent Status[/]")
        else:
            print(f"{C.BRIGHT_CYAN}2. SSH Agent Status{C.RESET}")

        agent_ok, agent_msg = SSHExecutor.check_agent_status()
        if agent_ok:
            if CYBER_UI_AVAILABLE:
                console.print(f"   [green]OK - {agent_msg}[/]\n")
            else:
                print(f"   {C.GREEN}OK - {agent_msg}{C.RESET}\n")
        else:
            all_safe = False
            issues_found.append(f"SSH Agent: {agent_msg}")
            if CYBER_UI_AVAILABLE:
                console.print(f"   [red]ISSUE - {agent_msg}[/]")
                console.print("   [yellow]Run: ssh-add ~/.ssh/your-key.pem[/]\n")
            else:
                print(f"   {C.RED}ISSUE - {agent_msg}{C.RESET}")
                print(f"   {C.YELLOW}Run: ssh-add ~/.ssh/your-key.pem{C.RESET}\n")
    else:
        if CYBER_UI_AVAILABLE:
            console.print("[bold cyan]2. SSH Key File[/]")
            if config_manager.has_ssh_key():
                console.print(f"   [green]OK - Key file configured[/]\n")
            else:
                console.print(f"   [red]ISSUE - No SSH key configured[/]\n")
                all_safe = False
                issues_found.append("No SSH key configured")
        else:
            print(f"{C.BRIGHT_CYAN}2. SSH Key File{C.RESET}")
            if config_manager.has_ssh_key():
                print(f"   {C.GREEN}OK - Key file configured{C.RESET}\n")
            else:
                print(f"   {C.RED}ISSUE - No SSH key configured{C.RESET}\n")
                all_safe = False
                issues_found.append("No SSH key configured")

    # 3. Check workers
    if CYBER_UI_AVAILABLE:
        console.print("[bold cyan]3. Worker Machines[/]")
    else:
        print(f"{C.BRIGHT_CYAN}3. Worker Machines{C.RESET}")

    workers = config_manager.get_enabled_workers()
    if not workers:
        if CYBER_UI_AVAILABLE:
            console.print("   [dim]No workers configured - skipping[/]\n")
        else:
            print(f"   {C.DIM}No workers configured - skipping{C.RESET}\n")
    elif not config_manager.has_ssh_key():
        if CYBER_UI_AVAILABLE:
            console.print("   [dim]Cannot check workers - no SSH access[/]\n")
        else:
            print(f"   {C.DIM}Cannot check workers - no SSH access{C.RESET}\n")
    else:
        try:
            ssh = SSHExecutor(
                key_path=config_manager.config.ssh_key_path,
                timeout=config_manager.config.ssh_timeout,
                use_agent=config_manager.config.use_ssh_agent
            )
            from discovery.distributed import ResourceDetector
            resource_detector = ResourceDetector(ssh)

            worker_results = resource_detector.security_check_all_workers(workers)

            workers_safe = 0
            workers_issues = 0

            for hostname, (is_safe, warnings) in worker_results.items():
                worker = next((w for w in workers if w.hostname == hostname), None)
                nickname = worker.nickname if worker and worker.nickname else hostname[:20]

                if is_safe:
                    workers_safe += 1
                    # Check if there are any INFO warnings to display
                    info_warnings = [w for w in warnings if w.startswith("INFO:")]
                    if info_warnings:
                        if CYBER_UI_AVAILABLE:
                            console.print(f"   [green]{nickname}: SAFE[/]")
                            for w in info_warnings:
                                console.print(f"      [dim cyan]{w}[/]")
                        else:
                            print(f"   {C.GREEN}{nickname}: SAFE{C.RESET}")
                            for w in info_warnings:
                                print(f"      {C.CYAN}{w}{C.RESET}")
                    else:
                        if CYBER_UI_AVAILABLE:
                            console.print(f"   [green]{nickname}: SAFE[/]")
                        else:
                            print(f"   {C.GREEN}{nickname}: SAFE{C.RESET}")
                else:
                    workers_issues += 1
                    all_safe = False
                    if CYBER_UI_AVAILABLE:
                        console.print(f"   [bold red]{nickname}: ISSUES FOUND[/]")
                        for w in warnings:
                            if w.startswith("INFO:"):
                                console.print(f"      [cyan]{w}[/]")
                            elif w.startswith("CRITICAL:"):
                                console.print(f"      [bold red]{w}[/]")
                                issues_found.append(f"{nickname}: {w}")
                            else:
                                console.print(f"      [yellow]{w}[/]")
                                issues_found.append(f"{nickname}: {w}")
                    else:
                        print(f"   {C.RED}{nickname}: ISSUES FOUND{C.RESET}")
                        for w in warnings:
                            if w.startswith("INFO:"):
                                print(f"      {C.CYAN}{w}{C.RESET}")
                            elif w.startswith("CRITICAL:"):
                                print(f"      {C.RED}{w}{C.RESET}")
                                issues_found.append(f"{nickname}: {w}")
                            else:
                                print(f"      {C.YELLOW}{w}{C.RESET}")
                                issues_found.append(f"{nickname}: {w}")

            if CYBER_UI_AVAILABLE:
                console.print(f"\n   Summary: {workers_safe} safe, {workers_issues} with issues\n")
            else:
                print(f"\n   Summary: {workers_safe} safe, {workers_issues} with issues\n")

        except Exception as e:
            if CYBER_UI_AVAILABLE:
                console.print(f"   [red]Error checking workers: {e}[/]\n")
            else:
                print(f"   {C.RED}Error checking workers: {e}{C.RESET}\n")

    # 4. Check for unexpected EC2 instances (if AWS CLI available)
    if CYBER_UI_AVAILABLE:
        console.print("[bold cyan]4. EC2 Instance Audit[/]")
    else:
        print(f"{C.BRIGHT_CYAN}4. EC2 Instance Audit{C.RESET}")

    from discovery.distributed import check_ec2_instances

    # Get known worker hostnames for comparison
    known_hosts = [w.hostname for w in workers] if workers else []

    aws_ok, instances = check_ec2_instances(known_hosts)
    if not aws_ok:
        if CYBER_UI_AVAILABLE:
            console.print("   [dim]AWS CLI not configured - skipping[/]")
            console.print("   [dim]Tip: Configure AWS CLI to enable instance auditing[/]\n")
        else:
            print(f"   {C.DIM}AWS CLI not configured - skipping{C.RESET}")
            print(f"   {C.DIM}Tip: Configure AWS CLI to enable instance auditing{C.RESET}\n")
    else:
        # Count running instances
        running = [i for i in instances if i['state'] == 'running']
        unknown_running = [i for i in running if not i['is_known']]

        if not running:
            if CYBER_UI_AVAILABLE:
                console.print("   [green]No running EC2 instances found[/]\n")
            else:
                print(f"   {C.GREEN}No running EC2 instances found{C.RESET}\n")
        elif unknown_running:
            # Found instances not in our worker list - potential rogue instances!
            all_safe = False
            if CYBER_UI_AVAILABLE:
                console.print(f"   [bold red]WARNING: {len(unknown_running)} unknown running instance(s)![/]")
                for inst in unknown_running[:5]:
                    console.print(f"      [red]{inst['region']}: {inst['instance_id']} ({inst['type']}) - {inst['public_ip'] or 'no public IP'}[/]")
                    issues_found.append(f"Unknown EC2: {inst['instance_id']} in {inst['region']}")
                if len(unknown_running) > 5:
                    console.print(f"      [red]... and {len(unknown_running) - 5} more[/]")
                console.print()
                console.print("   [yellow]These instances are not in your worker list.[/]")
                console.print("   [yellow]If you didn't launch them, your account may be compromised![/]\n")
            else:
                print(f"   {C.RED}WARNING: {len(unknown_running)} unknown running instance(s)!{C.RESET}")
                for inst in unknown_running[:5]:
                    print(f"      {C.RED}{inst['region']}: {inst['instance_id']} ({inst['type']}) - {inst['public_ip'] or 'no public IP'}{C.RESET}")
                    issues_found.append(f"Unknown EC2: {inst['instance_id']} in {inst['region']}")
                if len(unknown_running) > 5:
                    print(f"      {C.RED}... and {len(unknown_running) - 5} more{C.RESET}")
                print()
                print(f"   {C.YELLOW}These instances are not in your worker list.{C.RESET}")
                print(f"   {C.YELLOW}If you didn't launch them, your account may be compromised!{C.RESET}\n")
        else:
            if CYBER_UI_AVAILABLE:
                console.print(f"   [green]{len(running)} running instance(s) - all are known workers[/]\n")
            else:
                print(f"   {C.GREEN}{len(running)} running instance(s) - all are known workers{C.RESET}\n")

    # Final summary
    print()
    if all_safe:
        if CYBER_UI_AVAILABLE:
            console.print(Panel(
                "[bold green]ALL CLEAR - No security issues detected[/]\n\n"
                "[dim]Best practices:[/]\n"
                "  • Never place .pem files in puppetmaster directory\n"
                "  • Use SSH agent forwarding (-A) instead of copying keys\n"
                "  • Rotate AWS credentials regularly\n"
                "  • Monitor CloudTrail for suspicious API calls",
                title="[bold green]SECURITY STATUS[/]",
                border_style="green"
            ))
        else:
            print_success("ALL CLEAR - No security issues detected")
            print()
            print("Best practices:")
            print("  • Never place .pem files in puppetmaster directory")
            print("  • Use SSH agent forwarding (-A) instead of copying keys")
            print("  • Rotate AWS credentials regularly")
            print("  • Monitor CloudTrail for suspicious API calls")
    else:
        if CYBER_UI_AVAILABLE:
            issue_text = "\n".join([f"  • {issue}" for issue in issues_found[:10]])
            if len(issues_found) > 10:
                issue_text += f"\n  ... and {len(issues_found) - 10} more"
            console.print(Panel(
                f"[bold red]SECURITY ISSUES DETECTED[/]\n\n"
                f"[yellow]Issues found:[/]\n{issue_text}\n\n"
                f"[bold yellow]ACTION REQUIRED:[/]\n"
                f"  • Remove any .pem/.key files from puppetmaster directory\n"
                f"  • Remove any credentials from worker machines\n"
                f"  • Consider rotating compromised keys",
                title="[bold red]WARNING[/]",
                border_style="red"
            ))
        else:
            print_error("SECURITY ISSUES DETECTED")
            print()
            print("Issues found:")
            for issue in issues_found[:10]:
                print(f"  • {issue}")
            if len(issues_found) > 10:
                print(f"  ... and {len(issues_found) - 10} more")
            print()
            print(f"{C.YELLOW}ACTION REQUIRED:{C.RESET}")
            print("  • Remove any .pem/.key files from puppetmaster directory")
            print("  • Remove any credentials from worker machines")
            print("  • Consider rotating compromised keys")

    get_input("\nPress Enter to continue...")


def _c2_toggle_scan_mode(config_manager):
    """Toggle between WebAPI and CLI scan modes."""
    config = config_manager.config
    current_mode = getattr(config, 'scan_mode', 'cli')

    if CYBER_UI_AVAILABLE:
        console = get_console()

    if current_mode == "cli":
        # Switch to WebAPI
        config_manager.update_settings(scan_mode='webapi')
        if CYBER_UI_AVAILABLE:
            console.print("\n[bold green]✓ Switched to WebAPI mode![/]")
            console.print()
            console.print("[white]What this means:[/]")
            console.print("  • SpiderFoot web servers will be started on each worker")
            console.print("  • Scans submitted via HTTP API (no SQLite lock contention)")
            console.print("  • Parallelism can now go up to [cyan]50 scans per worker[/]")
            console.print("  • Much higher throughput for large domain lists")
            console.print()
            console.print("[dim]Tip: Increase parallelism with [T] > [P] to take advantage of WebAPI mode[/]")
        else:
            print_success("Switched to WebAPI mode!")
            print()
            print("What this means:")
            print("  • SpiderFoot web servers will be started on each worker")
            print("  • Scans submitted via HTTP API (no SQLite lock contention)")
            print("  • Parallelism can now go up to 50 scans per worker")
            print("  • Much higher throughput for large domain lists")
            print()
            print("Tip: Increase parallelism with [T] > [P] to take advantage of WebAPI mode")
    else:
        # Switch to CLI
        config_manager.update_settings(scan_mode='cli')
        if CYBER_UI_AVAILABLE:
            console.print("\n[yellow]✓ Switched to CLI mode[/]")
            console.print()
            console.print("[white]What this means:[/]")
            console.print("  • Using bash scripts with sf.py CLI commands")
            console.print("  • Limited to ~10 parallel scans due to SQLite locks")
            console.print("  • Good for debugging or when WebAPI has issues")
            console.print()
            console.print("[dim]Note: WebAPI mode is recommended for most use cases[/]")
        else:
            print_success("Switched to CLI mode")
            print()
            print("What this means:")
            print("  • Using bash scripts with sf.py CLI commands")
            print("  • Limited to ~10 parallel scans due to SQLite locks")
            print("  • Good for debugging or when WebAPI has issues")
            print()
            print("Note: WebAPI mode is recommended for most use cases")

    get_input("\nPress Enter to continue...")


def _c2_modify_timeouts(config_manager):
    """Modify scan settings (timeouts and parallelism) - Quick action menu."""
    while True:
        clear_screen()
        config = config_manager.config

        # Get current values
        scan_mode = getattr(config, 'scan_mode', 'webapi')
        parallel = config.parallel_scans_per_worker
        hard_timeout = config.hard_timeout_hours
        activity_timeout = config.activity_timeout_minutes
        max_parallel = 50 if scan_mode == 'webapi' else 20

        aws_region = config.aws_region

        if CYBER_UI_AVAILABLE:
            cyber_header("SCAN SETTINGS")
            console = get_console()

            # Current settings summary
            if scan_mode == "webapi":
                mode_display = "[green]WebAPI[/] [dim](high parallelism)[/]"
            else:
                mode_display = "[yellow]CLI[/] [dim](limited by SQLite)[/]"

            console.print(f"  Mode: {mode_display}  |  Parallel: [cyan]{parallel}[/]  |  Timeout: [cyan]{hard_timeout}h[/]  |  Region: [cyan]{aws_region}[/]\n")

            # Menu options
            console.print("[bold white]SCAN MODE[/]")
            if scan_mode == "cli":
                console.print("  [bold green][W][/] Switch to WebAPI mode [green](RECOMMENDED - 5x more parallel scans!)[/]")
            else:
                console.print("  [dim][C] Switch to CLI mode (legacy, limited parallelism)[/]")

            console.print("\n[bold white]SETTINGS[/]")
            console.print(f"  [bold cyan][P][/] Change parallelism [dim](current: {parallel}, max: {max_parallel})[/]")
            console.print(f"  [bold cyan][T][/] Change timeouts [dim](hard: {hard_timeout}h, activity: {activity_timeout}m)[/]")
            console.print(f"  [bold cyan][R][/] Change AWS region [dim](current: {aws_region})[/]")

            console.print(f"\n  [white][Q][/] Back to C2 menu\n")
        else:
            print_section("Scan Settings", C.BRIGHT_MAGENTA)

            # Current settings summary
            if scan_mode == "webapi":
                mode_display = f"{C.GREEN}WebAPI{C.RESET} (high parallelism)"
            else:
                mode_display = f"{C.YELLOW}CLI{C.RESET} (limited by SQLite)"

            print(f"  Mode: {mode_display}  |  Parallel: {parallel}  |  Timeout: {hard_timeout}h  |  Region: {aws_region}\n")

            # Menu options
            print(f"{C.WHITE}SCAN MODE{C.RESET}")
            if scan_mode == "cli":
                print(f"  {C.GREEN}[W]{C.RESET} Switch to WebAPI mode {C.GREEN}(RECOMMENDED - 5x more parallel scans!){C.RESET}")
            else:
                print(f"  {C.DIM}[C] Switch to CLI mode (legacy, limited parallelism){C.RESET}")

            print(f"\n{C.WHITE}SETTINGS{C.RESET}")
            print(f"  {C.CYAN}[P]{C.RESET} Change parallelism (current: {parallel}, max: {max_parallel})")
            print(f"  {C.CYAN}[T]{C.RESET} Change timeouts (hard: {hard_timeout}h, activity: {activity_timeout}m)")
            print(f"  {C.CYAN}[R]{C.RESET} Change AWS region (current: {aws_region})")

            print(f"\n  {C.WHITE}[Q]{C.RESET} Back to C2 menu\n")

        choice = get_input("Select option")
        if choice is None:
            choice = 'q'
        choice = choice.lower().strip()

        if choice == 'q':
            return

        elif choice == 'w':
            config_manager.update_settings(scan_mode='webapi')
            if CYBER_UI_AVAILABLE:
                console.print("\n[green]✓ Switched to WebAPI mode![/]")
                console.print("[dim]  SpiderFoot web servers will be started on workers.[/]")
                console.print("[dim]  Scans submitted via HTTP API - no SQLite lock contention.[/]")
            else:
                print_success("Switched to WebAPI mode!")
                print("  SpiderFoot web servers will be started on workers.")
                print("  Scans submitted via HTTP API - no SQLite lock contention.")
            get_input("\nPress Enter to continue...")

        elif choice == 'c':
            config_manager.update_settings(scan_mode='cli')
            if CYBER_UI_AVAILABLE:
                console.print("\n[yellow]✓ Switched to CLI mode[/]")
                console.print("[dim]  Using bash scripts with sf.py CLI.[/]")
                console.print("[dim]  Limited to ~10 parallel scans due to SQLite locks.[/]")
            else:
                print_success("Switched to CLI mode")
                print("  Using bash scripts with sf.py CLI.")
                print("  Limited to ~10 parallel scans due to SQLite locks.")
            get_input("\nPress Enter to continue...")

        elif choice == 'p':
            # Change parallelism
            current_mode = getattr(config_manager.config, 'scan_mode', 'webapi')
            max_p = 50 if current_mode == 'webapi' else 20

            if CYBER_UI_AVAILABLE:
                console.print(f"\n[dim]Current: {parallel} | Max for {current_mode} mode: {max_p}[/]")
            else:
                print(f"\nCurrent: {parallel} | Max for {current_mode} mode: {max_p}")

            new_parallel = get_input("New parallelism value")
            if new_parallel and new_parallel.strip():
                try:
                    parallel_val = int(new_parallel.strip())
                    parallel_val = max(1, min(max_p, parallel_val))
                    config_manager.update_settings(parallel_scans_per_worker=parallel_val)

                    # Update all workers
                    for worker in config_manager.get_all_workers():
                        config_manager.update_worker(worker.hostname, recommended_parallel=parallel_val)

                    if CYBER_UI_AVAILABLE:
                        console.print(f"[green]✓ Parallelism set to {parallel_val}[/]")
                    else:
                        print_success(f"Parallelism set to {parallel_val}")
                except ValueError:
                    pass
            get_input("\nPress Enter to continue...")

        elif choice == 't':
            # Change timeouts
            if CYBER_UI_AVAILABLE:
                console.print(f"\n[dim]Current timeouts:[/]")
                console.print(f"  Hard timeout: {hard_timeout} hours (max time per scan)")
                console.print(f"  Activity timeout: {activity_timeout} minutes (kill if no output)\n")
            else:
                print(f"\nCurrent timeouts:")
                print(f"  Hard timeout: {hard_timeout} hours (max time per scan)")
                print(f"  Activity timeout: {activity_timeout} minutes (kill if no output)\n")

            new_hard = get_input(f"Hard timeout in hours (Enter to keep {hard_timeout})")
            if new_hard and new_hard.strip():
                try:
                    config_manager.update_settings(hard_timeout_hours=float(new_hard.strip()))
                except ValueError:
                    pass

            new_activity = get_input(f"Activity timeout in minutes (Enter to keep {activity_timeout})")
            if new_activity and new_activity.strip():
                try:
                    config_manager.update_settings(activity_timeout_minutes=int(new_activity.strip()))
                except ValueError:
                    pass

            if CYBER_UI_AVAILABLE:
                console.print("[green]✓ Timeouts updated[/]")
            else:
                print_success("Timeouts updated")
            get_input("\nPress Enter to continue...")

        elif choice == 'r':
            # Change AWS region
            if CYBER_UI_AVAILABLE:
                console.print(f"\n[dim]Current AWS region: {aws_region}[/]")
                console.print("[dim]This region is used in the AWS CLI commands shown for[/]")
                console.print("[dim]getting worker hostnames and launching instances.[/]")
                console.print("[dim]Common regions: us-east-1, us-west-2, eu-west-1, ap-southeast-1[/]")
            else:
                print(f"\nCurrent AWS region: {aws_region}")
                print("This region is used in the AWS CLI commands shown for")
                print("getting worker hostnames and launching instances.")
                print("Common regions: us-east-1, us-west-2, eu-west-1, ap-southeast-1")

            new_region = get_input(f"New AWS region (Enter to keep {aws_region})")
            if new_region and new_region.strip():
                new_region = new_region.strip().lower()
                config_manager.update_settings(aws_region=new_region)
                if CYBER_UI_AVAILABLE:
                    console.print(f"[green]✓ AWS region set to {new_region}[/]")
                else:
                    print_success(f"AWS region set to {new_region}")
            get_input("\nPress Enter to continue...")


