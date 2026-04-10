#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ██████╗ ██╗   ██╗██████╗ ██████╗ ███████╗████████╗                          ║
║   ██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔════╝╚══██╔══╝                          ║
║   ██████╔╝██║   ██║██████╔╝██████╔╝█████╗     ██║                             ║
║   ██╔═══╝ ██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝     ██║                             ║
║   ██║     ╚██████╔╝██║     ██║     ███████╗   ██║                             ║
║   ╚═╝      ╚═════╝ ╚═╝     ╚═╝     ╚══════╝   ╚═╝                             ║
║                                                                               ║
║   ███╗   ███╗ █████╗ ███████╗████████╗███████╗██████╗                         ║
║   ████╗ ████║██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗                        ║
║   ██╔████╔██║███████║███████╗   ██║   █████╗  ██████╔╝                        ║
║   ██║╚██╔╝██║██╔══██║╚════██║   ██║   ██╔══╝  ██╔══██╗                        ║
║   ██║ ╚═╝ ██║██║  ██║███████║   ██║   ███████╗██║  ██║                        ║
║   ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝                        ║
║                                                                               ║
║   SpiderFoot Sock Puppet Detector                                             ║
║   "good morning coffee with a bacon egg and cheese"                           ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

PUPPETMASTER - The orchestrator for SpiderFoot Sock Puppet Detection

This tool analyzes SpiderFoot scan exports to identify coordinated networks
of domains (sock puppets) that are likely controlled by the same entity.

Author: Built with Claude
License: MIT
"""

import os
import sys
import time

# Enable readline for arrow key support in input() prompts
try:
    import readline  # noqa: F401 - imported for side effects
except ImportError:
    pass  # readline not available on Windows

# =============================================================================
# KALI LINUX INTEGRATION
# =============================================================================
# Try to import Kali module for enhanced features
try:
    from kali.integration import (
        kali_startup_check,
        is_enhanced_mode,
        print_enhanced_menu,
        handle_enhanced_menu_choice,
        get_kali_status_line,
        should_show_kali_menu,
        kali_expand_domains,
    )
    KALI_MODULE_AVAILABLE = True
except ImportError:
    KALI_MODULE_AVAILABLE = False
    def is_enhanced_mode(): return False
    def should_show_kali_menu(): return False
    def get_kali_status_line(): return ""
    def kali_expand_domains(domains, **kwargs): return domains

# =============================================================================
# CYBERPUNK HUD UI
# =============================================================================
# Try to import the new Cyberpunk HUD
try:
    from ui.integration import run_cyberpunk_hud_menu, map_hud_key_to_choice
    CYBERPUNK_HUD_AVAILABLE = True
    _HUD_IMPORT_ERROR = None
except ImportError as e:
    CYBERPUNK_HUD_AVAILABLE = False
    _HUD_IMPORT_ERROR = str(e)

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

# Toggle for Cyberpunk UI
USE_CYBERPUNK_HUD = True

# Backwards compatibility
GAMING_HUD_AVAILABLE = CYBERPUNK_HUD_AVAILABLE
USE_GAMING_HUD = USE_CYBERPUNK_HUD

# =============================================================================
# CONFIG FILE - Remember user's output directories
# =============================================================================
from pm_config import CONFIG_FILE, load_config, save_config, remember_output_dir, get_remembered_output_dirs

# =============================================================================
# COLOR CODES
# =============================================================================
from utils.colors import C

# =============================================================================
# EXTRACTED MODULES
# =============================================================================
from pm_background import (
    is_background_scan_running, get_background_scan_stats, stop_background_thread,
)
from pm_paths import is_safe_path, sanitize_path, get_data_directory, get_output_directory
from pm_ui_helpers import (
    clear_screen, print_banner, print_section, print_menu_item,
    print_success, print_error, print_warning, print_info,
    get_input, confirm,
)
from pm_environment import setup_environment, ensure_running_in_venv
from pm_infrastructure import launch_in_tmux, launch_glances
from pm_spiderfoot import (
    launch_spiderfoot_gui, spiderfoot_control_center_menu, _kill_spiderfoot_menu,
)
from pm_help import (
    show_help, show_help_overview, install_spiderfoot_interactive,
    show_spiderfoot_install_guide, show_help_signals, show_help_outputs,
)
from pm_results import show_config, find_results_directories, view_previous_results
from pm_domain_discovery import (
    run_domain_scrape, interactive_domain_removal,
    scrape_domains_menu, show_scrape_results_menu, load_domains_menu,
    _run_delete_domain_lists,
)
from pm_c2 import distributed_scanning_menu, _c2_start_distributed_scan
from pm_scan_monitoring import (
    check_scan_status_menu, manage_domain_queue_menu,
)
from pm_analysis import run_analysis, run_wildcard_analyzer

# =============================================================================
# MAIN MENU
# =============================================================================
def show_main_menu():
    """Display the main menu"""
    clear_screen()
    print_banner()

    # Check if background scan is running
    if is_background_scan_running():
        stats = get_background_scan_stats()
        progress = stats['completed'] + stats['failed']
        current = stats.get('current_domain', 'unknown')
        if len(current) > 30:
            current = current[:27] + "..."
        print(f"""
{C.BRIGHT_YELLOW}╔═══════════════════════════════════════════════════════════════════════════════╗
║  🔄 SPIDERFOOT SCAN IN PROGRESS — {progress}/{stats['total']} complete                             ║
║     Currently scanning: {current:<30}  Use [4] to view details  ║
╚═══════════════════════════════════════════════════════════════════════════════╝{C.RESET}
""")

    # Check if domains are ready for scanning
    config = load_config()
    if config.get('domains_ready_for_scan'):
        domain_count = config.get('domains_ready_count', 0)
        print(f"""
{C.BRIGHT_GREEN}╔═══════════════════════════════════════════════════════════════════════════════╗
║  ✓ {domain_count} DOMAINS LOADED — Proceed to option [3] to start SpiderFoot scans!      ║
╚═══════════════════════════════════════════════════════════════════════════════╝{C.RESET}
""")
        # Clear the flag after showing
        config['domains_ready_for_scan'] = False
        save_config(config)

    # Show Kali mode banner if active
    if KALI_MODULE_AVAILABLE and is_enhanced_mode():
        kali_status = get_kali_status_line()
        print(f"""
{C.BRIGHT_RED}╔═══════════════════════════════════════════════════════════════════════════════╗
║  🐉 KALI LINUX ENHANCED MODE ACTIVE                                                        
║     {kali_status:<69}                                                                       ║
║     Option [1] auto-expands domains with Kali tools after scraping!                         ║
╚═════════════════════════════════════════════════════════════════════════════════════════════╝{C.RESET}
""")

    print(f"""
{C.WHITE}{C.BOLD}Welcome to PUPPETMASTER!{C.RESET}
{C.DIM}End-to-end sock puppet detection pipeline{C.RESET}

{C.WHITE}What does this tool do?{C.RESET}
{C.DIM}━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}
Discovers, scans, and analyzes domains to expose "sock puppet" networks —
websites that {C.UNDERLINE}appear{C.RESET}{C.DIM} independent but are secretly controlled by the same operator.

{C.WHITE}The Pipeline:{C.RESET}
{C.DIM}━━━━━━━━━━━━━{C.RESET}
  {C.BRIGHT_CYAN}1. Discover{C.RESET}  Scrape search engines for domains you suspect are sock puppets
  {C.BRIGHT_CYAN}2. Scan{C.RESET}      Run SpiderFoot OSINT scans on scrapd list (batch or interactive GUI)
  {C.BRIGHT_CYAN}3. Analyze{C.RESET}   Analyze spiderfoot scans to detect if there are any sock puppet clusters

{C.WHITE}What We Find:{C.RESET}
{C.DIM}━━━━━━━━━━━━━{C.RESET}
  {C.BRIGHT_RED}•{C.RESET} Same Google Analytics/AdSense IDs {C.DIM}← definitive proof{C.RESET}
  {C.BRIGHT_YELLOW}•{C.RESET} Same WHOIS, nameservers, SSL certs {C.DIM}← strong evidence{C.RESET}

{C.BRIGHT_GREEN}One shared unique identifier = same operator.{C.RESET}

{C.WHITE}New here?{C.RESET} Press {C.BRIGHT_YELLOW}[8]{C.RESET} for the full guide.
{C.BRIGHT_YELLOW}Long scans?{C.RESET} Press {C.WHITE}[9]{C.RESET} to run in {C.WHITE}tmux{C.RESET} (survives SSH disconnects)

""")

    print_section("Main Menu", C.BRIGHT_YELLOW)

    # Discovery & Scanning Section
    print(f"  {C.BRIGHT_CYAN}DISCOVERY & SCANNING{C.RESET}")
    print_menu_item("1", "Scrape domains via keywords", "🔍")
    print_menu_item("2", "Load domains from file", "📂")
    print_menu_item("D", "Delete/Modify domain lists", "🗑️")
    print_menu_item("3", "SpiderFoot Control Center (scans, GUI, DB)", "🕷️")
    print_menu_item("4", "Check scan queue status", "📋")
    print()

    # Analysis Section
    print(f"  {C.BRIGHT_GREEN}ANALYSIS{C.RESET}")
    print_menu_item("5", "Run Puppet Analysis on SpiderFoot scans", "🎭")
    print_menu_item("6", "View previous results", "📊")
    print_menu_item("11", "Signal//Noise Wildcard DNS Analyzer", "📡")
    print()

    # Settings Section
    print(f"  {C.BRIGHT_MAGENTA}SETTINGS{C.RESET}")
    print_menu_item("7", "Configuration", "⚙️")
    print_menu_item("8", "Help & Documentation", "❓")
    print_menu_item("9", "Launch in tmux (for long scans)", "🖥️")
    print_menu_item("10", "System monitor (via Glances)", "📊")
    print()

    # Security Section
    print(f"  {C.BRIGHT_RED}SECURITY{C.RESET}")
    print_menu_item("S", "Security Audit (rootkit detection)", "🛡️")
    print()

    # Kali Enhanced Mode Section (only shown when Kali is detected)
    if should_show_kali_menu():
        print_enhanced_menu(print_func=print, colors=C)

    print_menu_item("q", "Quit", "👋")
    print()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    """Main entry point"""
    # Parse command-line arguments for menu routing
    # --start-menu c2  : Start directly in the C2 distributed scanning menu (used by tmux auto-launch)
    start_menu = None
    if '--start-menu' in sys.argv:
        try:
            idx = sys.argv.index('--start-menu')
            if idx + 1 < len(sys.argv):
                start_menu = sys.argv[idx + 1]
        except (ValueError, IndexError):
            pass

    # Check if we should be running in an existing venv
    ensure_running_in_venv()

    # Initial setup
    clear_screen()
    print_banner()

    # Check environment
    if not setup_environment():
        print_error("Environment setup failed. Please resolve the issues above and try again.")
        sys.exit(1)

    # Kali Linux detection and bootstrap
    if KALI_MODULE_AVAILABLE:
        print_section("OS Detection", C.BRIGHT_BLUE)
        is_kali, os_info = kali_startup_check(print_func=print)
        if is_kali:
            print_success("Kali Linux enhanced mode enabled!")
            time.sleep(1)
        else:
            print_info(f"Running on {os_info.os_name} - standard mode")
        time.sleep(1)

    time.sleep(1)

    # Report UI mode
    print_section("UI Mode", C.BRIGHT_MAGENTA)
    if USE_CYBERPUNK_HUD and CYBERPUNK_HUD_AVAILABLE:
        if sys.stdin.isatty():
            print_success("Cyberpunk HUD enabled (TTY detected)")
        else:
            print_warning("Cyberpunk HUD disabled (no TTY - using classic menu)")
    else:
        if not CYBERPUNK_HUD_AVAILABLE:
            print_info("Classic menu (Cyberpunk HUD not available - 'rich' not installed?)")
        else:
            print_info("Classic menu (Cyberpunk HUD disabled)")
    time.sleep(1)

    # Clear any buffered input from startup (prevents accidental quit)
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass  # Ignore on Windows or if stdin isn't a terminal

    # Handle --start-menu argument (used by tmux auto-launch)
    # This allows puppetmaster to resume in a specific menu after tmux session creation
    if start_menu == "c2":
        # Go directly to the "Start Distributed Scan" intensity selection screen
        try:
            from discovery.worker_config import DistributedConfigManager
            config_manager = DistributedConfigManager()
            _c2_start_distributed_scan(config_manager)
        except Exception as e:
            print_error(f"Failed to start distributed scan: {e}")
            get_input("\nPress Enter to continue to main menu...")
        # After scan starts (or fails), go to C2 menu so user can check progress
        distributed_scanning_menu()
        # After returning from C2 menu, continue to main menu loop

    # Main menu loop
    while True:
        # Use Cyberpunk HUD if available and enabled
        if USE_CYBERPUNK_HUD and CYBERPUNK_HUD_AVAILABLE:
            try:
                # Get scan mode function if Kali is available
                get_scan_mode = None
                if KALI_MODULE_AVAILABLE:
                    try:
                        from kali.integration import get_current_scan_mode
                        get_scan_mode = get_current_scan_mode
                    except ImportError:
                        pass

                hud_key = run_cyberpunk_hud_menu(
                    load_config=load_config,
                    is_background_scan_running=is_background_scan_running,
                    get_background_scan_stats=get_background_scan_stats,
                    should_show_kali_menu=should_show_kali_menu,
                    is_enhanced_mode=is_enhanced_mode if KALI_MODULE_AVAILABLE else None,
                    get_kali_status_line=get_kali_status_line if KALI_MODULE_AVAILABLE else None,
                    get_scan_mode=get_scan_mode,
                )
                choice = map_hud_key_to_choice(hud_key)
            except Exception as e:
                # Fallback to classic menu on error - show WHY it failed
                clear_screen()
                print_banner()
                print()
                print_warning(f"Cyberpunk HUD unavailable: {e}")
                print_info("Falling back to classic menu. Press Enter to continue...")
                try:
                    input()
                except (EOFError, KeyboardInterrupt):
                    pass
                show_main_menu()
                choice = get_input("Select an option")
                if choice is None:
                    choice = 'q'
                else:
                    choice = choice.lower()
        else:
            # Classic menu
            show_main_menu()
            choice = get_input("Select an option")

            # Handle Ctrl+C at main menu = exit gracefully
            if choice is None:
                choice = 'q'
            else:
                choice = choice.lower()

        # Discovery & Scanning
        if choice == '1':
            scrape_domains_menu()
        elif choice == '2':
            load_domains_menu()
        elif choice == 'd':
            _run_delete_domain_lists()
        elif choice == '3':
            spiderfoot_control_center_menu()  # Unified SpiderFoot Control Center
        elif choice == '4':
            check_scan_status_menu()
        # Analysis
        elif choice == '5':
            run_analysis()
        elif choice == '6':
            view_previous_results()
        # Settings
        elif choice == '7':
            show_config()
        elif choice == '8':
            show_help()
        elif choice == '9':
            launch_in_tmux()
        elif choice == '10':
            launch_glances()
        elif choice == '11':
            run_wildcard_analyzer()
        elif choice == '12':
            manage_domain_queue_menu()  # Domain queue manager
        # Security Audit
        elif choice == 's':
            try:
                from security import security_audit_menu
                security_audit_menu()
            except ImportError as e:
                print_error(f"Security module not available: {e}")
                time.sleep(2)
        # Kali Enhanced Mode options
        elif choice.startswith('k') and KALI_MODULE_AVAILABLE:
            handled = handle_enhanced_menu_choice(
                choice,
                print_func=print,
                get_input_func=get_input,
                clear_func=clear_screen,
                colors=C
            )
            if not handled:
                print_warning("Invalid Kali option.")
                time.sleep(1)
        elif choice in ('q', 'quit', 'exit'):
            # Check if background scan is running
            if is_background_scan_running():
                print_warning("Background scan is still running!")
                if not confirm("Quit anyway? (scans will be interrupted)"):
                    continue
                # Signal background thread to stop gracefully
                print_info("Waiting for background scan to stop...")
                stop_background_thread(timeout=5)

            clear_screen()
            print(f"""
{C.BRIGHT_CYAN}
╔═════════════════════════════════════════════════════════════════╗
║                                                                 ║
║              Thank you for using PUPPETMASTER! 🎭               ║
║                                                                 ║
║                  Enjoy your noodles al dente.                   ║
║                                                                 ║
╚═════════════════════════════════════════════════════════════════╝
{C.RESET}
""")
            sys.exit(0)
        else:
            print_warning("Invalid option. Please try again.")
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL] Unhandled error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
