"""pm_spiderfoot.py - SpiderFoot Control Center, GUI Launch, Batch Scanning"""

import os
import sys
import time
import subprocess
import socket
import webbrowser
from pathlib import Path
from datetime import datetime

from pm_config import load_config, save_config
from pm_ui_helpers import (
    C, clear_screen, print_banner, print_section, print_menu_item,
    print_success, print_error, print_warning, print_info,
    get_input, confirm, is_running_in_tmux,
)
from pm_background import (
    is_background_scan_running, get_background_scan_stats,
    _update_background_stats, _run_background_scans, start_background_thread,
)
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
    port_input = get_input(f"Enter port for SpiderFoot web UI [{default_port}]: ", str(default_port))
    port = int(port_input) if port_input and port_input.isdigit() else default_port
    if not (1 <= port <= 65535):
        print_warning(f"Port {port} out of valid range (1-65535), using default {default_port}")
        port = default_port

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
        # Use shlex.quote to prevent command injection via path variables
        import shlex
        sf_cmd = f"{shlex.quote(python_exe)} {shlex.quote(str(sf_path))} -l 127.0.0.1:{port}"

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


def spiderfoot_control_center_menu():
    """
    Unified SpiderFoot Control Center menu.

    Consolidates:
    - CLI batch scanning
    - Web GUI
    - Database management
    - Intensity presets
    - ETA tracking
    - Stuck scan detection
    """
    # Deferred imports to avoid circular dependencies
    from pm_scan_monitoring import check_scan_status_menu
    from pm_c2 import distributed_scanning_menu

    while True:  # Loop to allow returning to submenu
        clear_screen()

        # Use cyberpunk UI if available
        if CYBER_UI_AVAILABLE:
            console = get_console()
            cyber_banner_spider()
            cyber_header("SPIDERFOOT CONTROL CENTER")
        else:
            print_banner()
            print_section("SpiderFoot Control Center", C.BRIGHT_CYAN)

        # Import the control center module
        try:
            from discovery.spiderfoot_control import (
                SpiderFootControlCenter, INTENSITY_PRESETS,
                find_spiderfoot_db, get_db_size, count_db_scans,
                reset_spiderfoot_db, kill_spiderfoot_processes,
                is_in_tmux, estimate_total_time, should_warn_tmux
            )
            from discovery.jobs import JobTracker
        except ImportError as e:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Failed to import control center: {e}")
            else:
                print_error(f"Failed to import control center: {e}")
            get_input("\nPress Enter to return to main menu...")
            return

        # Load configuration
        config = load_config()
        sf_path = config.get('spiderfoot_path')
        sf_python = config.get('spiderfoot_python')
        sf_output = config.get('spiderfoot_output_dir', './spiderfoot_exports')

        # Auto-detect SpiderFoot if not configured
        if not sf_path or not os.path.exists(sf_path):
            script_dir = Path(__file__).parent
            project_sf_path = script_dir / "spiderfoot" / "sf.py"
            project_sf_python = script_dir / "spiderfoot" / "venv" / "bin" / "python3"

            if project_sf_path.exists() and project_sf_python.exists():
                sf_path = str(project_sf_path)
                sf_python = str(project_sf_python)
                config['spiderfoot_path'] = sf_path
                config['spiderfoot_python'] = sf_python
                save_config(config)

        # Get status information
        sf_installed = sf_path and os.path.exists(sf_path)
        db_path = find_spiderfoot_db(sf_path) if sf_installed else None
        db_size = get_db_size(db_path) if db_path else "N/A"
        db_scans = count_db_scans(db_path) if db_path else {}

        # Get queue status
        tracker = JobTracker()
        queue_stats = tracker.get_stats()
        pending_domains = config.get('pending_domains', [])

        # Check if background scan is running
        bg_running = is_background_scan_running()
        bg_stats = get_background_scan_stats() if bg_running else None

        # Display status panel
        if CYBER_UI_AVAILABLE:
            from rich.panel import Panel
            from rich.table import Table
            from rich.text import Text

            # Status table
            status_table = Table(show_header=False, box=None, padding=(0, 2))
            status_table.add_column("Label", style="dim white", width=25)
            status_table.add_column("Value")

            # SpiderFoot status
            if sf_installed:
                status_table.add_row("◈ SpiderFoot", "[green]INSTALLED[/]")
            else:
                status_table.add_row("◈ SpiderFoot", "[red]NOT INSTALLED[/]")

            # Database status
            if db_path:
                status_table.add_row("◈ Database", f"[cyan]{db_size}[/]")
                status_table.add_row("  └─ Scans", f"[white]{db_scans.get('total', 0)} total[/] | "
                                    f"[yellow]{db_scans.get('running', 0)} running[/] | "
                                    f"[green]{db_scans.get('finished', 0)} finished[/]")
            else:
                status_table.add_row("◈ Database", "[dim]Not found[/]")

            # Queue status
            status_table.add_row("◈ Scan Queue",
                f"[white]{queue_stats['total']} total[/] | "
                f"[cyan]{queue_stats['pending']} pending[/] | "
                f"[green]{queue_stats['completed']} done[/]")

            # Pending domains (not yet in queue)
            if pending_domains:
                status_table.add_row("◈ Domains Loaded", f"[yellow]{len(pending_domains)} ready to add[/]")

            # Background scan status
            if bg_running:
                progress = bg_stats['completed'] + bg_stats['failed']
                status_table.add_row("◈ Active Scan", f"[bold yellow]RUNNING[/] - {progress}/{bg_stats['total']}")

            # tmux status
            status_table.add_row("◈ tmux", "[green]Active[/]" if is_in_tmux() else "[dim]Not in tmux[/]")

            console.print(Panel(
                status_table,
                title="[bold magenta]⟨ SYSTEM STATUS ⟩[/]",
                border_style="magenta",
                padding=(1, 2),
                width=80
            ))
            console.print()

            # Menu options
            menu_text = Text()

            # Show install option prominently if not installed
            if not sf_installed:
                menu_text.append("SETUP REQUIRED\n", style="bold red underline")
                menu_text.append("  [I] ", style="bold yellow")
                menu_text.append("Install SpiderFoot      ", style="bold white")
                menu_text.append("Auto-install SpiderFoot OSINT tool\n\n", style="yellow")

            menu_text.append("SCAN OPERATIONS\n", style="bold white underline")
            menu_text.append("  [1] ", style="bold green")
            menu_text.append("Start Batch Scans       ", style="white")
            menu_text.append("CLI mode with intensity presets\n", style="dim")
            menu_text.append("  [2] ", style="bold cyan")
            menu_text.append("View Scan Status        ", style="white")
            menu_text.append("Progress, ETA, stuck detection\n", style="dim")
            menu_text.append("  [3] ", style="bold yellow")
            menu_text.append("Open Web GUI            ", style="white")
            menu_text.append("Interactive browser interface\n\n", style="dim")

            menu_text.append("DATABASE MANAGEMENT\n", style="bold white underline")
            menu_text.append("  [4] ", style="bold red")
            menu_text.append("Reset SpiderFoot DB     ", style="white")
            menu_text.append("Wipe all scan data (creates backup)\n", style="dim")
            menu_text.append("  [5] ", style="bold magenta")
            menu_text.append("Kill SpiderFoot         ", style="white")
            menu_text.append("Stop all running processes\n\n", style="dim")

            menu_text.append("DISTRIBUTED SCANNING\n", style="bold white underline")
            menu_text.append("  [D] ", style="bold #ff6b6b")
            menu_text.append("Multi-EC2 C2 Controller ", style="white")
            menu_text.append("For 100+ domains - coordinate across workers, weeks → days\n\n", style="#888888")

            menu_text.append("  [Q] ", style="bold white")
            menu_text.append("Back to Main Menu\n", style="dim")

            console.print(Panel(menu_text, title="[bold cyan]⟨ CONTROL CENTER ⟩[/]", border_style="cyan", width=80))
            console.print()
        else:
            # Classic terminal output
            install_section = ""
            if not sf_installed:
                install_section = f"""
{C.BRIGHT_RED}SETUP REQUIRED{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.BRIGHT_YELLOW}[I]{C.RESET} {C.WHITE}Install SpiderFoot{C.RESET}      Auto-install SpiderFoot OSINT tool
"""
            print(f"""
{C.WHITE}SYSTEM STATUS{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  SpiderFoot:     {C.GREEN + "[INSTALLED]" + C.RESET if sf_installed else C.RED + "[NOT INSTALLED]" + C.RESET}
  Database:       {db_size} ({db_scans.get('total', 0)} scans, {db_scans.get('running', 0)} running)
  Scan Queue:     {queue_stats['total']} total ({queue_stats['pending']} pending, {queue_stats['completed']} done)
  Domains Loaded: {len(pending_domains)}
  Background:     {"[RUNNING]" if bg_running else "[idle]"}
  tmux:           {"[Active]" if is_in_tmux() else "[Not in tmux]"}
{install_section}
{C.WHITE}SCAN OPERATIONS{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.GREEN}[1]{C.RESET} Start Batch Scans       CLI mode with intensity presets
  {C.CYAN}[2]{C.RESET} View Scan Status        Progress, ETA, stuck detection
  {C.YELLOW}[3]{C.RESET} Open Web GUI            Interactive browser interface

{C.WHITE}DATABASE MANAGEMENT{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.RED}[4]{C.RESET} Reset SpiderFoot DB     Wipe all scan data (creates backup)
  {C.BRIGHT_MAGENTA}[5]{C.RESET} Kill SpiderFoot         Stop all running processes

{C.WHITE}DISTRIBUTED SCANNING{C.RESET}
{C.DIM}{'━' * 50}{C.RESET}
  {C.BRIGHT_RED}[D]{C.RESET} Multi-EC2 C2 Controller For 100+ domains, weeks → days

  {C.WHITE}[Q]{C.RESET} Back to Main Menu
""")

        choice = get_input("Select an option")
        if choice is None:
            choice = 'q'
        choice = choice.lower().strip()

        if choice == 'q':
            return

        elif choice == '1':
            # Start batch scans with intensity presets
            _spiderfoot_batch_scan_menu(config, sf_path, sf_python, sf_output)

        elif choice == '2':
            # View scan status
            check_scan_status_menu()

        elif choice == '3':
            # Open Web GUI
            launch_spiderfoot_gui()

        elif choice == '4':
            # Reset SpiderFoot database
            _reset_spiderfoot_menu(sf_path)

        elif choice == '5':
            # Kill SpiderFoot processes
            _kill_spiderfoot_menu()

        elif choice == 'i':
            # Install SpiderFoot
            result = install_spiderfoot_interactive()
            if result:
                sf_path, sf_python = result
                config['spiderfoot_path'] = sf_path
                config['spiderfoot_python'] = sf_python
                save_config(config)
                if CYBER_UI_AVAILABLE:
                    cyber_success("SpiderFoot installed successfully!")
                else:
                    print_success("SpiderFoot installed successfully!")
            get_input("\nPress Enter to continue...")

        elif choice == 'd':
            # Distributed multi-EC2 scanning
            distributed_scanning_menu()


def _check_port_in_use(port: int) -> bool:
    """Check if a port is in use"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def _start_gui_server_background(sf_path: str, sf_python: str, port: int = 5001) -> bool:
    """
    Start SpiderFoot GUI server in background.

    Returns:
        True if server started or already running, False on failure
    """
    # Check if already running on this port
    if _check_port_in_use(port):
        return True  # Already running, that's fine

    # Get SpiderFoot directory
    sf_dir = Path(sf_path).parent

    # Build command
    python_exe = sf_python if sf_python and os.path.exists(sf_python) else "python3"

    # Check if we're in tmux - if so, create a new window
    if os.environ.get('TMUX'):
        # Already in tmux, create a new window for the GUI
        import shlex
        sf_cmd = f"cd {shlex.quote(str(sf_dir))} && {shlex.quote(python_exe)} sf.py -l 127.0.0.1:{port}"
        try:
            subprocess.run([
                'tmux', 'new-window', '-d', '-n', 'spiderfoot-gui', sf_cmd
            ], check=True, capture_output=True)
            return True
        except Exception:
            pass  # Fall through to direct subprocess

    # Start as background subprocess
    try:
        subprocess.Popen(
            [python_exe, sf_path, "-l", f"127.0.0.1:{port}"],
            cwd=str(sf_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        # Give it a moment to start
        time.sleep(1)
        return True
    except Exception:
        return False


def _open_or_show_gui_url(port: int = 5001):
    """
    Open browser to GUI URL, or show SSH tunnel instructions if remote.
    """
    # Check if remote (SSH connection)
    ssh_connection = os.environ.get('SSH_CONNECTION', '')

    if ssh_connection:
        # Parse SSH_CONNECTION for IPs
        parts = ssh_connection.split()
        server_ip = parts[2] if len(parts) > 2 else 'THIS_SERVER'
        username = os.environ.get('USER', 'user')

        # Try to get EC2 public IP
        public_ip = None
        try:
            result = subprocess.run(
                ["curl", "-s", "--connect-timeout", "2",
                 "http://169.254.169.254/latest/meta-data/public-ipv4"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                public_ip = result.stdout.strip()
        except Exception:
            pass

        remote_ip = public_ip or server_ip

        if CYBER_UI_AVAILABLE:
            console = get_console()
            from rich.panel import Panel
            console.print(Panel(
                f"[bold]SSH Tunnel Required[/]\n\n"
                f"Run this in a [cyan]NEW[/] terminal on your local machine:\n\n"
                f"  [bold white]ssh -L {port}:localhost:{port} {username}@{remote_ip}[/]\n\n"
                f"Then open: [bold white]http://localhost:{port}[/]",
                title="[bold yellow]⟨ REMOTE ACCESS ⟩[/]",
                border_style="yellow"
            ))
        else:
            print(f"""
{C.BRIGHT_YELLOW}SSH Tunnel Required{C.RESET}

Run this in a {C.UNDERLINE}NEW{C.RESET} terminal on your local machine:

  {C.BRIGHT_WHITE}ssh -L {port}:localhost:{port} {username}@{remote_ip}{C.RESET}

Then open: {C.BRIGHT_WHITE}http://localhost:{port}{C.RESET}
""")
    else:
        # Local - try to open browser
        url = f"http://localhost:{port}"
        try:
            import webbrowser
            webbrowser.open(url)
            if CYBER_UI_AVAILABLE:
                cyber_success(f"Opened browser to {url}")
            else:
                print_success(f"Opened browser to {url}")
        except Exception:
            if CYBER_UI_AVAILABLE:
                cyber_info(f"Open in browser: {url}")
            else:
                print_info(f"Open in browser: {url}")


def _spiderfoot_batch_scan_menu(config, sf_path, sf_python, sf_output):
    """Sub-menu for starting batch scans with intensity presets"""
    clear_screen()

    try:
        from discovery.spiderfoot_control import (
            INTENSITY_PRESETS, estimate_total_time, should_warn_tmux, is_in_tmux
        )
        from discovery.jobs import JobTracker
    except ImportError as e:
        print_error(f"Import error: {e}")
        get_input("\nPress Enter to return...")
        return

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_header("BATCH SCAN CONFIGURATION")
    else:
        print_section("Batch Scan Configuration", C.BRIGHT_GREEN)

    # Check SpiderFoot installation
    if not sf_path or not os.path.exists(sf_path):
        if CYBER_UI_AVAILABLE:
            cyber_error("SpiderFoot not installed!")
            cyber_info("Use Help → Install SpiderFoot to set it up")
        else:
            print_error("SpiderFoot not installed!")
            print_info("Use Help → Install SpiderFoot to set it up")
        get_input("\nPress Enter to return...")
        return

    # Get queue info
    tracker = JobTracker()
    pending_domains = config.get('pending_domains', [])
    existing_pending = len(tracker.get_pending())

    total_domains = len(pending_domains) + existing_pending

    if total_domains == 0:
        if CYBER_UI_AVAILABLE:
            cyber_warning("No domains in queue!")
            cyber_info("Use [1] Scrape or [2] Load domains first")
        else:
            print_warning("No domains in queue!")
            print_info("Use [1] Scrape or [2] Load domains first")
        get_input("\nPress Enter to return...")
        return

    # Display intensity presets
    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        console.print(f"\n[bold white]Domains to scan:[/] [cyan]{total_domains}[/]\n")

        preset_table = Table(show_header=True, header_style="bold white", box=None)
        preset_table.add_column("Key", style="bold", width=5)
        preset_table.add_column("Preset", width=12)
        preset_table.add_column("Timeout", width=10)
        preset_table.add_column("Parallel", width=10)
        preset_table.add_column("Est. Time/Domain", width=15)
        preset_table.add_column("Description")

        for key, preset in INTENSITY_PRESETS.items():
            timeout_str = f"{preset.timeout_seconds // 60}m" if preset.timeout_seconds < 3600 else f"{preset.timeout_seconds // 3600}h"
            est_str = f"~{preset.estimated_time_per_domain // 60}m"
            color = preset.color
            preset_table.add_row(
                f"[{color}]{key[0].upper()}[/]",
                f"[{color}]{preset.name}[/]",
                timeout_str,
                str(preset.parallel_scans),
                est_str,
                preset.description[:40]
            )

        console.print(Panel(preset_table, title="[bold green]⟨ INTENSITY PRESETS ⟩[/]", border_style="green"))
        console.print()
    else:
        print(f"\n{C.WHITE}Domains to scan: {C.CYAN}{total_domains}{C.RESET}\n")
        print(f"{C.WHITE}INTENSITY PRESETS{C.RESET}")
        print(f"{C.DIM}{'━' * 70}{C.RESET}")
        for key, preset in INTENSITY_PRESETS.items():
            timeout_str = f"{preset.timeout_seconds // 60}m" if preset.timeout_seconds < 3600 else f"{preset.timeout_seconds // 3600}h"
            print(f"  [{key[0].upper()}] {preset.name:<12} | {timeout_str} timeout | {preset.parallel_scans} parallel | {preset.description[:35]}")
        print()

    # Select preset
    preset_choice = get_input("Select intensity preset [S/M/C/X for custom]", "M")
    if preset_choice is None:
        return

    preset_choice = preset_choice.lower().strip()
    preset_map = {'s': 'safe', 'm': 'moderate', 'c': 'committed', 'x': 'custom'}
    preset_key = preset_map.get(preset_choice, 'moderate')

    if preset_key == 'custom':
        # Custom configuration
        timeout_input = get_input("Timeout per scan (minutes)", "60")
        parallel_input = get_input("Parallel scans", "3")
        try:
            timeout_min = int(timeout_input) if timeout_input else 60
            parallel = int(parallel_input) if parallel_input else 3
            parallel = max(1, min(10, parallel))

            from discovery.spiderfoot_control import IntensityPreset
            preset = IntensityPreset(
                name='Custom',
                description=f'{timeout_min}m timeout, {parallel} parallel',
                timeout_seconds=timeout_min * 60,
                modules=None,
                parallel_scans=parallel,
                estimated_time_per_domain=timeout_min * 30,  # Rough estimate
                color='magenta'
            )
        except ValueError:
            print_warning("Invalid input, using Moderate preset")
            preset = INTENSITY_PRESETS['moderate']
    else:
        preset = INTENSITY_PRESETS[preset_key]

    # Calculate ETA
    total_time = estimate_total_time(total_domains, preset)
    hours = total_time.total_seconds() / 3600

    # tmux warning
    if should_warn_tmux(total_domains, preset):
        if CYBER_UI_AVAILABLE:
            from rich.panel import Panel
            console.print(Panel(
                f"[yellow]This scan batch is estimated to take {hours:.1f} hours.\n"
                f"Consider running in tmux to prevent interruption on disconnect.\n"
                f"Use option [9] from main menu to launch in tmux session.[/]",
                title="[bold yellow]⚠ LONG SCAN WARNING[/]",
                border_style="yellow"
            ))
        else:
            print(f"""
{C.YELLOW}{'━' * 60}
  WARNING: This scan batch is estimated to take {hours:.1f} hours.
  Consider running in tmux to prevent interruption on disconnect.
  Use option [9] from main menu to launch in tmux session.
{'━' * 60}{C.RESET}
""")

    # Confirmation
    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        console.print(Panel(
            f"[bold]Preset:[/] {preset.name}\n"
            f"[bold]Domains:[/] {total_domains}\n"
            f"[bold]Timeout:[/] {preset.timeout_seconds // 60} minutes per scan\n"
            f"[bold]Parallel:[/] {preset.parallel_scans} simultaneous scans\n"
            f"[bold]Est. Total:[/] ~{hours:.1f} hours",
            title="[bold green]⟨ SCAN SUMMARY ⟩[/]",
            border_style="green"
        ))
        console.print()
        do_scan = cyber_confirm("Start scanning?")
    else:
        print(f"""
{C.GREEN}{'━' * 50}{C.RESET}
  Preset:     {preset.name}
  Domains:    {total_domains}
  Timeout:    {preset.timeout_seconds // 60} minutes per scan
  Parallel:   {preset.parallel_scans} simultaneous scans
  Est. Total: ~{hours:.1f} hours
{C.GREEN}{'━' * 50}{C.RESET}
""")
        do_scan = confirm("Start scanning?")

    if not do_scan:
        print_info("Cancelled.")
        get_input("\nPress Enter to return...")
        return

    # Ask about GUI monitoring
    if CYBER_UI_AVAILABLE:
        open_gui = cyber_confirm("Monitor scans in browser?")
    else:
        open_gui = confirm("Monitor scans in browser?")

    if open_gui:
        # Start GUI server in background
        if _start_gui_server_background(sf_path, sf_python, port=5001):
            if CYBER_UI_AVAILABLE:
                cyber_success("SpiderFoot GUI started on port 5001")
            else:
                print_success("SpiderFoot GUI started on port 5001")
            # Open browser or show SSH tunnel instructions
            _open_or_show_gui_url(port=5001)
        else:
            if CYBER_UI_AVAILABLE:
                cyber_warning("Could not start GUI server")
            else:
                print_warning("Could not start GUI server")

    # Add pending domains to tracker
    if pending_domains:
        added = tracker.add_domains(pending_domains)
        config['pending_domains'] = []
        save_config(config)
        if CYBER_UI_AVAILABLE:
            cyber_success(f"Added {added} domains to scan queue")
        else:
            print_success(f"Added {added} domains to scan queue")

    # Create output directory
    if not os.path.exists(sf_output):
        os.makedirs(sf_output, exist_ok=True)

    # Import scanner
    from discovery.scanner import SpiderFootScanner

    scanner = SpiderFootScanner(
        spiderfoot_path=sf_path,
        output_dir=sf_output,
        max_parallel=preset.parallel_scans,
        job_tracker=tracker,
        spiderfoot_python=sf_python,
        timeout_seconds=preset.timeout_seconds,
        modules=preset.modules
    )

    # Ask for run mode
    if CYBER_UI_AVAILABLE:
        console.print("\n[bold white]Run Mode:[/]")
        console.print("  [1] Background (return to menu)")
        console.print("  [2] Foreground (watch progress)")
        console.print()
    else:
        print(f"""
{C.WHITE}Run Mode:{C.RESET}
  [1] Background (return to menu)
  [2] Foreground (watch progress)
""")

    run_mode = get_input("Select run mode", "1")
    if run_mode is None:
        return

    total_pending = len(tracker.get_pending())

    if run_mode == "1":
        # Run in background

        # Check if scan is already running (prevent duplicate threads)
        if is_background_scan_running():
            if CYBER_UI_AVAILABLE:
                cyber_warning("A background scan is already running!")
                cyber_info("Use [2] View Scan Status to check progress, or wait for it to complete.")
            else:
                print_warning("A background scan is already running!")
                print_info("Use [2] View Scan Status to check progress, or wait for it to complete.")
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
            cyber_info("Use [2] View Scan Status to check progress")
        else:
            print_success("Scans started in background!")
            print_info("Use [2] View Scan Status to check progress")
        time.sleep(1.5)
        return
    else:
        # Run in foreground
        if CYBER_UI_AVAILABLE:
            cyber_header("RUNNING SCANS")
            console.print("[dim]Press Ctrl+C to pause. Progress auto-saves.[/]\n")

            def on_start(domain):
                console.print(f"  [cyan]▶[/] Starting: [bold]{domain}[/]")

            def on_complete(domain, csv_path):
                console.print(f"  [green]✓[/] Completed: [bold green]{domain}[/]")

            def on_failed(domain, error):
                console.print(f"  [red]✗[/] Failed: [bold]{domain}[/] - [dim]{error[:50]}[/]")

            def on_progress(completed, failed, total):
                console.print(f"\n  [bold cyan]Progress: {completed + failed}/{total}[/]\n")
        else:
            print_section("Running Scans", C.BRIGHT_MAGENTA)
            print(f"{C.DIM}Press Ctrl+C to pause. Progress auto-saves.{C.RESET}\n")

            def on_start(domain):
                print(f"  {C.CYAN}▶{C.RESET} Starting: {domain}")

            def on_complete(domain, csv_path):
                print(f"  {C.GREEN}✓{C.RESET} Completed: {domain}")

            def on_failed(domain, error):
                print(f"  {C.RED}✗{C.RESET} Failed: {domain} - {error[:50]}")

            def on_progress(completed, failed, total):
                print(f"\n  {C.CYAN}Progress: {completed + failed}/{total}{C.RESET}\n")

        scanner.on_scan_start = on_start
        scanner.on_scan_complete = on_complete
        scanner.on_scan_failed = on_failed
        scanner.on_progress = on_progress

        try:
            results = scanner.process_queue(progress_callback=on_progress)
            if CYBER_UI_AVAILABLE:
                cyber_success(f"Batch complete! {results['completed']} succeeded, {results['failed']} failed")
            else:
                print_success(f"Batch complete! {results['completed']} succeeded, {results['failed']} failed")
        except KeyboardInterrupt:
            scanner.stop()
            if CYBER_UI_AVAILABLE:
                cyber_warning("Scan paused. Progress saved.")
            else:
                print_warning("Scan paused. Progress saved.")
        except Exception as e:
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Error: {e}")
            else:
                print_error(f"Error: {e}")

        get_input("\nPress Enter to return...")


def _reset_spiderfoot_menu(sf_path):
    """Sub-menu for resetting SpiderFoot database"""
    clear_screen()

    try:
        from discovery.spiderfoot_control import (
            find_spiderfoot_db, get_db_size, count_db_scans,
            reset_spiderfoot_db, kill_spiderfoot_processes
        )
    except ImportError as e:
        print_error(f"Import error: {e}")
        get_input("\nPress Enter to return...")
        return

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_header("RESET SPIDERFOOT DATABASE")
    else:
        print_section("Reset SpiderFoot Database", C.BRIGHT_RED)

    if not sf_path or not os.path.exists(sf_path):
        if CYBER_UI_AVAILABLE:
            cyber_error("SpiderFoot not found!")
        else:
            print_error("SpiderFoot not found!")
        get_input("\nPress Enter to return...")
        return

    # Find database
    db_path = find_spiderfoot_db(sf_path)
    if not db_path:
        if CYBER_UI_AVAILABLE:
            cyber_warning("SpiderFoot database not found. Nothing to reset.")
        else:
            print_warning("SpiderFoot database not found. Nothing to reset.")
        get_input("\nPress Enter to return...")
        return

    # Show current status
    db_size = get_db_size(db_path)
    db_scans = count_db_scans(db_path)

    if CYBER_UI_AVAILABLE:
        from rich.panel import Panel
        console.print(Panel(
            f"[bold]Database:[/] {db_path}\n"
            f"[bold]Size:[/] {db_size}\n"
            f"[bold]Total Scans:[/] {db_scans.get('total', 0)}\n"
            f"  └─ Running: {db_scans.get('running', 0)}\n"
            f"  └─ Finished: {db_scans.get('finished', 0)}\n"
            f"  └─ Aborted: {db_scans.get('aborted', 0)}",
            title="[bold red]⟨ DATABASE STATUS ⟩[/]",
            border_style="red"
        ))
        console.print()
        console.print("[yellow]WARNING: This will delete ALL SpiderFoot scan data![/]")
        console.print("[dim]A backup will be created before deletion.[/]\n")
        do_reset = cyber_confirm("Reset SpiderFoot database?")
    else:
        print(f"""
{C.RED}{'━' * 50}{C.RESET}
  Database:     {db_path}
  Size:         {db_size}
  Total Scans:  {db_scans.get('total', 0)}
    └─ Running:   {db_scans.get('running', 0)}
    └─ Finished:  {db_scans.get('finished', 0)}
    └─ Aborted:   {db_scans.get('aborted', 0)}
{C.RED}{'━' * 50}{C.RESET}

{C.YELLOW}WARNING: This will delete ALL SpiderFoot scan data!{C.RESET}
{C.DIM}A backup will be created before deletion.{C.RESET}
""")
        do_reset = confirm("Reset SpiderFoot database?")

    if not do_reset:
        print_info("Cancelled.")
        get_input("\nPress Enter to return...")
        return

    # Kill any running processes first
    if CYBER_UI_AVAILABLE:
        cyber_info("Stopping SpiderFoot processes...")
    else:
        print_info("Stopping SpiderFoot processes...")

    killed = kill_spiderfoot_processes()
    if killed > 0:
        if CYBER_UI_AVAILABLE:
            cyber_success(f"Killed {killed} SpiderFoot process(es)")
        else:
            print_success(f"Killed {killed} SpiderFoot process(es)")
        time.sleep(1)

    # Reset database
    success, msg = reset_spiderfoot_db(sf_path, backup=True)

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

    get_input("\nPress Enter to return...")


def _kill_spiderfoot_menu():
    """Sub-menu for killing SpiderFoot processes"""
    clear_screen()

    try:
        from discovery.spiderfoot_control import kill_spiderfoot_processes
    except ImportError as e:
        print_error(f"Import error: {e}")
        get_input("\nPress Enter to return...")
        return

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_header("KILL SPIDERFOOT PROCESSES")
    else:
        print_section("Kill SpiderFoot Processes", C.BRIGHT_RED)

    # Find running processes
    try:
        result = subprocess.run(
            ["pgrep", "-af", "sf.py"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            processes = result.stdout.strip().split('\n')
            if CYBER_UI_AVAILABLE:
                console.print(f"[yellow]Found {len(processes)} SpiderFoot process(es):[/]\n")
                for proc in processes:
                    console.print(f"  [dim]{proc}[/]")
                console.print()
            else:
                print(f"\n{C.YELLOW}Found {len(processes)} SpiderFoot process(es):{C.RESET}\n")
                for proc in processes:
                    print(f"  {C.DIM}{proc}{C.RESET}")
                print()
        else:
            if CYBER_UI_AVAILABLE:
                cyber_info("No SpiderFoot processes found running.")
            else:
                print_info("No SpiderFoot processes found running.")
            get_input("\nPress Enter to return...")
            return
    except Exception as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Could not check processes: {e}")
        else:
            print_error(f"Could not check processes: {e}")
        get_input("\nPress Enter to return...")
        return

    # Confirm
    do_kill = cyber_confirm("Kill all SpiderFoot processes?") if CYBER_UI_AVAILABLE else confirm("Kill all SpiderFoot processes?")

    if not do_kill:
        print_info("Cancelled.")
        get_input("\nPress Enter to return...")
        return

    killed = kill_spiderfoot_processes()

    if CYBER_UI_AVAILABLE:
        cyber_success(f"Killed {killed} process(es)")
    else:
        print_success(f"Killed {killed} process(es)")

    get_input("\nPress Enter to return...")
