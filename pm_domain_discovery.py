"""pm_domain_discovery.py - Domain Discovery, Scraping & Loading Menus"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

from pm_config import load_config, save_config
from pm_ui_helpers import (
    C, clear_screen, print_banner, print_section, print_menu_item,
    print_success, print_error, print_warning, print_info,
    get_input, confirm, animated_print,
)

# Try to import Kali module for enhanced features (used in show_scrape_results_menu)
try:
    from kali.integration import is_enhanced_mode, kali_expand_domains
    KALI_MODULE_AVAILABLE = True
except ImportError:
    KALI_MODULE_AVAILABLE = False
    def is_enhanced_mode(): return False
    def kali_expand_domains(domains, **kwargs): return domains

# Try to import cyberpunk UI components
try:
    from ui.cyberpunk_ui import (
        cyber_header, cyber_info, cyber_success, cyber_warning,
        cyber_error, cyber_prompt, cyber_confirm, get_console,
        cyber_banner_discovery, cyber_banner_import,
    )
    CYBER_UI_AVAILABLE = True
except ImportError:
    CYBER_UI_AVAILABLE = False


def run_domain_scrape(keywords, use_google, use_duckduckgo, max_results, existing_domains=None):
    """Run the actual domain scraping and return results"""
    from discovery.scraper import DomainScraper

    print_section("Scraping Domains", C.BRIGHT_MAGENTA)
    print(f"{C.DIM}Safe mode enabled - 2-3 second delays between requests{C.RESET}\n")

    scraper = DomainScraper(delay_range=(2, 4))

    # If we have existing domains, add them to the scraper
    if existing_domains:
        scraper.domains = set(existing_domains)

    def progress_callback(keyword, current, total):
        print(f"  {C.CYAN}[{current}/{total}]{C.RESET} Searching: \"{keyword}\"")

    try:
        domains = scraper.search_all(
            keywords=keywords,
            max_results_per_keyword=max_results,
            use_google=use_google,
            use_duckduckgo=use_duckduckgo,
            progress_callback=progress_callback
        )
    except KeyboardInterrupt:
        print_warning("\nScraping interrupted by user.")
        domains = scraper.domains

    # Show errors if any
    if scraper.errors:
        print()
        print_warning("Search errors occurred:")
        for error in scraper.errors[:5]:  # Limit to first 5
            print(f"  {C.DIM}• {error}{C.RESET}")
        if len(scraper.errors) > 5:
            print(f"  {C.DIM}• ... and {len(scraper.errors) - 5} more{C.RESET}")

    return domains


def interactive_domain_removal(domains: set) -> set:
    """
    Interactive UI for reviewing and removing domains.
    Uses simple-term-menu for arrow key navigation with search.
    Loops until user chooses to proceed.

    Args:
        domains: Set of domains to review

    Returns:
        Filtered set of domains (with removals applied)
    """
    if not domains:
        return domains

    # Try to import simple-term-menu
    try:
        from simple_term_menu import TerminalMenu
    except ImportError:
        print_warning("simple-term-menu not installed, skipping interactive review")
        print_info("Install with: pip install simple-term-menu")
        return domains

    # Try to import blacklist for permanent additions
    try:
        from core.blacklist import add_to_blacklist
        blacklist_available = True
    except ImportError:
        blacklist_available = False

    current_domains = set(domains)  # Work with a copy

    # Main review loop
    while True:
        sorted_domains = sorted(current_domains)
        domain_count = len(sorted_domains)

        # Show pre-review menu
        print(f"\n{C.BRIGHT_CYAN}{'━' * 65}{C.RESET}")
        print(f"  {C.BRIGHT_WHITE}DOMAIN REVIEW{C.RESET} {C.DIM}// {domain_count} domains{C.RESET}")
        print(f"{C.BRIGHT_CYAN}{'━' * 65}{C.RESET}")

        # Warn about large lists
        if domain_count > 500:
            print(f"\n  {C.BRIGHT_YELLOW}⚠ Large list ({domain_count} domains) - review may be slow{C.RESET}")

        print(f"\n  {C.BRIGHT_MAGENTA}[r]{C.RESET} Review & remove domains (↑/↓ navigate, TAB select, / search)")
        print(f"  {C.BRIGHT_MAGENTA}[d]{C.RESET} Done - proceed with {domain_count} domains")
        print(f"  {C.BRIGHT_MAGENTA}[q]{C.RESET} Cancel\n")

        choice = get_input("Choice", "d")
        if choice is None or choice.lower() == 'q':
            print_info("Cancelled")
            return current_domains
        elif choice.lower() == 'd':
            print_success(f"Proceeding with {domain_count} domains")
            return current_domains
        elif choice.lower() != 'r':
            print_warning("Invalid choice. Proceeding with current domains.")
            return current_domains

        # Show interactive picker
        print(f"\n{C.BRIGHT_MAGENTA}{'━' * 65}{C.RESET}")
        print(f"  {C.BRIGHT_WHITE}SELECT DOMAINS TO REMOVE{C.RESET}")
        print(f"{C.BRIGHT_MAGENTA}{'━' * 65}{C.RESET}")
        print(f"  {C.BRIGHT_CYAN}↑/↓{C.RESET} Navigate  {C.BRIGHT_CYAN}TAB{C.RESET} Toggle  {C.BRIGHT_CYAN}/{C.RESET} Search  {C.BRIGHT_CYAN}ESC{C.RESET} Exit search  {C.BRIGHT_CYAN}ENTER{C.RESET} Confirm")
        print(f"{C.DIM}{'─' * 65}{C.RESET}\n")

        try:
            menu = TerminalMenu(
                sorted_domains,
                title=f"  [{domain_count} domains] - TAB to select, ENTER when done",
                multi_select=True,
                show_multi_select_hint=True,
                multi_select_select_on_accept=False,
                multi_select_empty_ok=True,
                # Cyberpunk styling
                menu_cursor="▸ ",
                menu_cursor_style=("fg_purple", "bold"),
                menu_highlight_style=("fg_cyan", "bold"),
                search_key="/",
                search_highlight_style=("fg_yellow", "bold"),
                cycle_cursor=True,
                clear_screen=False,
            )

            selected_indices = menu.show()

        except Exception as e:
            print_warning(f"Interactive menu failed: {e}")
            continue  # Go back to review menu

        # Handle no selection
        if not selected_indices:
            print_info("No domains selected")
            continue  # Loop back to review menu

        # Convert indices to domain names
        to_remove = {sorted_domains[i] for i in selected_indices}

        # Confirmation
        print(f"\n{C.BRIGHT_YELLOW}{'═' * 65}{C.RESET}")
        print(f"  {C.BRIGHT_WHITE}CONFIRM REMOVAL{C.RESET} - {len(to_remove)} domain(s) selected")
        print(f"{C.DIM}{'─' * 65}{C.RESET}")

        for d in sorted(to_remove)[:15]:
            print(f"  {C.BRIGHT_RED}✗{C.RESET} {d}")
        if len(to_remove) > 15:
            print(f"  {C.DIM}... and {len(to_remove) - 15} more{C.RESET}")

        print(f"{C.BRIGHT_YELLOW}{'═' * 65}{C.RESET}")

        print(f"\n  {C.BRIGHT_CYAN}[1]{C.RESET} Remove (this session only)")
        if blacklist_available:
            print(f"  {C.BRIGHT_CYAN}[2]{C.RESET} Remove + add to permanent blacklist")
        print(f"  {C.BRIGHT_CYAN}[3]{C.RESET} Cancel - go back\n")

        confirm_choice = get_input("Choice", "1")

        if confirm_choice == '1':
            current_domains = current_domains - to_remove
            print_success(f"Removed {len(to_remove)} domains ({len(current_domains)} remaining)")
            # Loop continues - user can review more or choose [d] to proceed
        elif confirm_choice == '2' and blacklist_available:
            for d in to_remove:
                add_to_blacklist(d, persistent=True)
            current_domains = current_domains - to_remove
            print_success(f"Removed {len(to_remove)} domains + added to permanent blacklist ({len(current_domains)} remaining)")
            # Loop continues
        else:
            print_info("Cancelled - no changes made")
            # Loop continues


def _run_delete_domain_lists():
    """Main menu entry point for Delete/Modify domain lists."""
    puppetmaster_dir = Path(__file__).parent
    domain_lists_dir = puppetmaster_dir / "domain_lists"
    available_lists = []

    if domain_lists_dir.exists():
        for txt_file in sorted(domain_lists_dir.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                with open(txt_file, 'r') as f:
                    domain_count = sum(1 for line in f if line.strip() and not line.strip().startswith('#'))
                mod_time = datetime.fromtimestamp(txt_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                available_lists.append({
                    'path': txt_file,
                    'name': txt_file.name,
                    'domains': domain_count,
                    'modified': mod_time
                })
            except Exception:
                pass

    _delete_modify_domain_lists(domain_lists_dir, available_lists)


def _delete_modify_domain_lists(domain_lists_dir, available_lists):
    """Submenu for deleting/managing domain list files."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_header("DELETE / MODIFY DOMAIN LISTS")
    else:
        print_section("Delete / Modify Domain Lists", C.BRIGHT_RED)

    if not available_lists:
        if CYBER_UI_AVAILABLE:
            cyber_info("No domain list files found.")
            cyber_prompt("Press Enter to return...")
        else:
            print_info("No domain list files found.")
            get_input("\nPress Enter to return...")
        return

    if CYBER_UI_AVAILABLE:
        console.print(f"[dim]Directory: {domain_lists_dir}[/]")
        console.print(f"[dim]{len(available_lists)} file(s) found[/]\n")
        console.print(f"  [bold yellow]\\[1][/] Select which files to delete")
        console.print(f"  [bold red]\\[2][/] Delete ALL domain list files")
        console.print(f"  [bold cyan]\\[B][/] Back\n")
        choice = cyber_prompt("Choice", "b")
    else:
        print(f"{C.DIM}Directory: {domain_lists_dir}{C.RESET}")
        print(f"{C.DIM}{len(available_lists)} file(s) found{C.RESET}\n")
        print(f"  {C.BRIGHT_YELLOW}[1]{C.RESET} Select which files to delete")
        print(f"  {C.BRIGHT_RED}[2]{C.RESET} Delete ALL domain list files")
        print(f"  {C.BRIGHT_CYAN}[B]{C.RESET} Back\n")
        choice = get_input("Choice", "b")

    if not choice or choice.lower() == 'b':
        return
    elif choice == '1':
        _select_and_delete_domain_files(domain_lists_dir, available_lists)
    elif choice == '2':
        _delete_all_domain_files(domain_lists_dir, available_lists)


def _select_and_delete_domain_files(domain_lists_dir, available_lists):
    """Show numbered list of domain files and let user select which to delete."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_header("SELECT FILES TO DELETE")
        console.print()
        for i, lst in enumerate(available_lists, 1):
            console.print(f"  [bold yellow]\\[{i}][/] {lst['name']}")
            console.print(f"      [dim]{lst['domains']} domains • {lst['modified']}[/]")
        console.print()
        cyber_info("Enter file numbers separated by commas (e.g. 1,3,5) or 'all'")
        selection = cyber_prompt("Files to delete")
    else:
        print_section("Select Files to Delete", C.BRIGHT_RED)
        print()
        for i, lst in enumerate(available_lists, 1):
            print(f"  {C.BRIGHT_YELLOW}[{i}]{C.RESET} {lst['name']}")
            print(f"      {C.DIM}{lst['domains']} domains • {lst['modified']}{C.RESET}")
        print()
        print_info("Enter file numbers separated by commas (e.g. 1,3,5) or 'all'")
        selection = get_input("Files to delete")

    if not selection or selection.strip().lower() == 'b':
        return

    # Parse selection
    if selection.strip().lower() == 'all':
        selected = list(available_lists)
    else:
        selected = []
        for part in selection.split(','):
            part = part.strip()
            if not part:
                continue
            if not part.isdigit():
                if CYBER_UI_AVAILABLE:
                    cyber_warning(f"Skipping invalid input: '{part}'")
                else:
                    print_warning(f"Skipping invalid input: '{part}'")
                continue
            idx = int(part) - 1
            if 0 <= idx < len(available_lists):
                if available_lists[idx] not in selected:
                    selected.append(available_lists[idx])
            else:
                if CYBER_UI_AVAILABLE:
                    cyber_warning(f"Skipping invalid number: {part} (valid range: 1-{len(available_lists)})")
                else:
                    print_warning(f"Skipping invalid number: {part} (valid range: 1-{len(available_lists)})")

    if not selected:
        if CYBER_UI_AVAILABLE:
            cyber_info("No valid files selected.")
            cyber_prompt("Press Enter to return...")
        else:
            print_info("No valid files selected.")
            get_input("\nPress Enter to return...")
        return

    # Show confirmation
    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print(f"\n[bold red]The following {len(selected)} file(s) will be permanently deleted:[/]\n")
        for lst in selected:
            console.print(f"  [red]✗[/] {lst['name']} [dim]({lst['domains']} domains)[/]")
        console.print()
        confirmed = cyber_confirm(f"Delete {len(selected)} file(s)?", default=False)
    else:
        print(f"\n{C.BRIGHT_RED}The following {len(selected)} file(s) will be permanently deleted:{C.RESET}\n")
        for lst in selected:
            print(f"  {C.BRIGHT_RED}✗{C.RESET} {lst['name']} {C.DIM}({lst['domains']} domains){C.RESET}")
        print()
        confirmed = confirm(f"Delete {len(selected)} file(s)?", default=False)

    if not confirmed:
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled - no files deleted.")
        else:
            print_info("Cancelled - no files deleted.")
        return

    # Delete files
    deleted = 0
    errors = 0
    for lst in selected:
        try:
            Path(lst['path']).unlink()
            deleted += 1
        except Exception as e:
            errors += 1
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Failed to delete {lst['name']}: {e}")
            else:
                print_error(f"Failed to delete {lst['name']}: {e}")

    if deleted > 0:
        if CYBER_UI_AVAILABLE:
            cyber_success(f"Deleted {deleted} file(s)")
        else:
            print_success(f"Deleted {deleted} file(s)")
    if errors > 0:
        if CYBER_UI_AVAILABLE:
            cyber_warning(f"{errors} file(s) could not be deleted")
        else:
            print_warning(f"{errors} file(s) could not be deleted")

    if CYBER_UI_AVAILABLE:
        cyber_prompt("Press Enter to return...")
    else:
        get_input("\nPress Enter to return...")


def _delete_all_domain_files(domain_lists_dir, available_lists):
    """Delete all domain list files after confirmation."""
    clear_screen()

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_header("DELETE ALL DOMAIN LIST FILES")
        console.print(f"\n[bold red]The following {len(available_lists)} file(s) will be permanently deleted:[/]\n")
        for lst in available_lists:
            console.print(f"  [red]✗[/] {lst['name']} [dim]({lst['domains']} domains)[/]")
        console.print()
        confirmed = cyber_confirm(f"Delete ALL {len(available_lists)} file(s)?", default=False)
    else:
        print_section("Delete ALL Domain List Files", C.BRIGHT_RED)
        print(f"\n{C.BRIGHT_RED}The following {len(available_lists)} file(s) will be permanently deleted:{C.RESET}\n")
        for lst in available_lists:
            print(f"  {C.BRIGHT_RED}✗{C.RESET} {lst['name']} {C.DIM}({lst['domains']} domains){C.RESET}")
        print()
        confirmed = confirm(f"Delete ALL {len(available_lists)} file(s)?", default=False)

    if not confirmed:
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled - no files deleted.")
        else:
            print_info("Cancelled - no files deleted.")
        return

    # Delete all files
    deleted = 0
    errors = 0
    for lst in available_lists:
        try:
            Path(lst['path']).unlink()
            deleted += 1
        except Exception as e:
            errors += 1
            if CYBER_UI_AVAILABLE:
                cyber_error(f"Failed to delete {lst['name']}: {e}")
            else:
                print_error(f"Failed to delete {lst['name']}: {e}")

    if deleted > 0:
        if CYBER_UI_AVAILABLE:
            cyber_success(f"Deleted {deleted} of {len(available_lists)} file(s)")
        else:
            print_success(f"Deleted {deleted} of {len(available_lists)} file(s)")
    if errors > 0:
        if CYBER_UI_AVAILABLE:
            cyber_warning(f"{errors} file(s) could not be deleted")
        else:
            print_warning(f"{errors} file(s) could not be deleted")

    if CYBER_UI_AVAILABLE:
        cyber_prompt("Press Enter to return...")
    else:
        get_input("\nPress Enter to return...")


def show_scrape_results_menu(domains, keywords, use_google, use_duckduckgo, max_results):
    """Show post-scrape menu with options to view, re-run, add more, etc."""
    from discovery.scraper import DomainScraper

    while True:
        clear_screen()

        # Use cyberpunk UI if available
        if CYBER_UI_AVAILABLE:
            console = get_console()
            from rich.panel import Panel
            from rich.text import Text

            cyber_banner_discovery()
            cyber_header("SCRAPE RESULTS")

            # Show summary in panel
            summary_text = Text()
            summary_text.append("Current Working Set:\n", style="bold white")
            summary_text.append("  Domains collected:  ", style="dim")
            summary_text.append(f"{len(domains)}\n", style="bold green")
            summary_text.append("  Keywords used:      ", style="dim")
            summary_text.append(f"{len(keywords)}\n\n", style="white")
            keywords_preview = ', '.join(keywords[:3]) + ('...' if len(keywords) > 3 else '')
            summary_text.append(f"Last keywords: {keywords_preview}", style="dim italic")

            console.print(Panel(summary_text, title="[bold green]⟨ RESULTS ⟩[/]", border_style="green"))
            console.print()

            console.print("[bold white]What would you like to do?[/]\n")
            console.print("  [bold yellow]\\[1][/] View domains")
            console.print("  [bold yellow]\\[2][/] Add more keywords (keep current domains)")
            console.print("  [bold green]\\[A][/] Manually add domains")
            console.print("  [bold yellow]\\[3][/] Re-run with same keywords")
            console.print("  [bold yellow]\\[4][/] Start fresh (new keywords)")
            console.print("  [bold yellow]\\[5][/] Save list to file")
            console.print("  [bold magenta]\\[R][/] Review & remove domains")
            if KALI_MODULE_AVAILABLE and is_enhanced_mode():
                console.print("  [bold cyan]\\[K][/] Expand with Kali tools")
            console.print("  [bold yellow]\\[6][/] Load into SpiderFoot scan queue")
            console.print("  [bold yellow]\\[7][/] Back to main menu")
            console.print()
        else:
            print_banner()
            print_section("Scrape Results", C.BRIGHT_GREEN)

            # Show summary
            print(f"""
{C.WHITE}Current Working Set:{C.RESET}
  Domains collected:  {C.BRIGHT_GREEN}{len(domains)}{C.RESET}
  Keywords used:      {len(keywords)}

{C.DIM}Last keywords: {', '.join(keywords[:3])}{'...' if len(keywords) > 3 else ''}{C.RESET}
""")

            print(f"{C.WHITE}What would you like to do?{C.RESET}\n")
            print_menu_item("1", "View domains", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("2", "Add more keywords (keep current domains)", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("a", "Manually add domains", f"{C.BRIGHT_GREEN}◆{C.RESET}")
            print_menu_item("3", "Re-run with same keywords", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("4", "Start fresh (new keywords)", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("5", "Save list to file", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("r", "Review & remove domains", f"{C.BRIGHT_MAGENTA}◆{C.RESET}")
            # Show Kali option if available
            if KALI_MODULE_AVAILABLE and is_enhanced_mode():
                print_menu_item("k", "Expand with Kali tools", f"{C.BRIGHT_CYAN}◆{C.RESET}")
            print_menu_item("6", "Load into SpiderFoot scan queue", f"{C.BRIGHT_RED}◆{C.RESET}")
            print_menu_item("7", "Back to main menu", f"{C.BRIGHT_RED}◆{C.RESET}")
            print()

        choice = get_input("Choice", "6")
        if choice is None:
            choice = "7"

        if choice == "1":
            # View domains
            clear_screen()
            print_banner()
            print_section(f"Domains Found ({len(domains)})", C.BRIGHT_CYAN)

            sorted_domains = sorted(domains)
            # Paginate if too many
            page_size = 30
            total_pages = (len(sorted_domains) + page_size - 1) // page_size

            page = 0
            while True:
                start = page * page_size
                end = min(start + page_size, len(sorted_domains))

                print(f"\n{C.DIM}Showing {start + 1}-{end} of {len(sorted_domains)}{C.RESET}\n")
                for i, domain in enumerate(sorted_domains[start:end], start + 1):
                    print(f"  {C.DIM}{i:4d}.{C.RESET} {domain}")

                print()
                if total_pages > 1:
                    print(f"{C.DIM}[n] Next page  [p] Previous page  [q] Back{C.RESET}")
                    nav = get_input("", "q")
                    if nav == 'n' and page < total_pages - 1:
                        page += 1
                    elif nav == 'p' and page > 0:
                        page -= 1
                    elif nav == 'q' or nav is None:
                        break
                else:
                    get_input("Press Enter to go back...")
                    break

        elif choice == "2":
            # Add more keywords
            clear_screen()
            print_banner()
            print_section("Add More Keywords", C.BRIGHT_CYAN)

            print(f"""
{C.WHITE}Current domains:{C.RESET} {len(domains)}
{C.DIM}New domains will be added to your existing set.{C.RESET}

{C.WHITE}Enter additional keywords:{C.RESET}
{C.DIM}Separate multiple keywords with commas.{C.RESET}
""")
            new_keywords_input = get_input("Keywords")
            if new_keywords_input and new_keywords_input.strip():
                new_keywords = [k.strip() for k in new_keywords_input.split(',') if k.strip()]
                if new_keywords:
                    print(f"\n{C.GREEN}✓{C.RESET} {len(new_keywords)} new keyword(s)\n")
                    new_domains = run_domain_scrape(
                        new_keywords, use_google, use_duckduckgo, max_results,
                        existing_domains=domains
                    )
                    added = len(new_domains) - len(domains)
                    domains = new_domains
                    keywords = keywords + new_keywords
                    print(f"\n{C.GREEN}✓{C.RESET} Added {added} new unique domains")
                    print(f"  Total domains: {len(domains)}")
                    get_input("\nPress Enter to continue...")

        elif choice == "3":
            # Re-run with same keywords
            print(f"\n{C.CYAN}Re-running with {len(keywords)} keywords...{C.RESET}\n")
            domains = run_domain_scrape(
                keywords, use_google, use_duckduckgo, max_results
            )
            print(f"\n{C.GREEN}✓{C.RESET} Found {len(domains)} unique domains")
            get_input("\nPress Enter to continue...")

        elif choice == "4":
            # Start fresh
            if confirm("Clear current domains and start with new keywords?"):
                return None  # Signal to restart the whole flow

        elif choice.lower() == "a":
            # Manually add domains
            clear_screen()
            print_banner()
            print_section("Manually Add Domains", C.BRIGHT_GREEN)

            print(f"""
{C.WHITE}Enter domains to add to your list.{C.RESET}
{C.DIM}Single domain or comma-separated. URLs auto-cleaned (http:// stripped).{C.RESET}

{C.DIM}Examples:{C.RESET}
  example.com
  example.com, another.com, third.com
  https://example.com/page  {C.DIM}→ becomes: example.com{C.RESET}
""")
            domain_input = get_input("Domains")
            if domain_input and domain_input.strip():
                # Parse comma-separated domains
                new_domains = []
                for d in domain_input.split(','):
                    d = d.strip().lower()
                    # Basic cleanup - remove protocols
                    if d.startswith('http://'):
                        d = d[7:]
                    elif d.startswith('https://'):
                        d = d[8:]
                    d = d.split('/')[0].strip()
                    import re as _re
                    if (d and '.' in d and len(d) <= 253
                            and _re.match(r'^[a-z0-9][a-z0-9.\-]*[a-z0-9]$', d)):
                        new_domains.append(d)

                if new_domains:
                    before_count = len(domains)
                    domains = domains | set(new_domains)
                    added = len(domains) - before_count
                    print(f"\n{C.GREEN}✓{C.RESET} Added {added} new domain(s)")
                    print(f"  Total domains: {len(domains)}")
                else:
                    print_warning("No valid domains entered")
            get_input("\nPress Enter to continue...")

        elif choice == "5":
            # Save to file - with domain_lists directory
            from discovery.scraper import DomainScraper
            scraper = DomainScraper()

            # Determine domain_lists directory (relative to puppetmaster)
            puppetmaster_dir = Path(__file__).parent
            domain_lists_dir = puppetmaster_dir / "domain_lists"

            print(f"""
{C.WHITE}Save Domain List{C.RESET}
{C.DIM}Lists are saved to: {domain_lists_dir}{C.RESET}

  {C.BRIGHT_YELLOW}[1]{C.RESET} Auto-name with timestamp
  {C.BRIGHT_YELLOW}[2]{C.RESET} Enter custom name
  {C.BRIGHT_YELLOW}[3]{C.RESET} Save to custom path
""")
            save_choice = get_input("Choice", "1")

            if save_choice == "1":
                # Auto timestamp name
                filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                save_path = domain_lists_dir / filename
            elif save_choice == "2":
                # Custom name
                custom_name = get_input("Enter list name (without .txt)")
                if custom_name and custom_name.strip():
                    # Sanitize filename
                    safe_name = "".join(c for c in custom_name.strip() if c.isalnum() or c in '-_').strip()
                    if safe_name:
                        save_path = domain_lists_dir / f"{safe_name}.txt"
                    else:
                        print_warning("Invalid name, using timestamp")
                        filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        save_path = domain_lists_dir / filename
                else:
                    filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    save_path = domain_lists_dir / filename
            elif save_choice == "3":
                # Custom path
                default_filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                user_path = get_input("File path", default_filename)
                if user_path:
                    save_path = Path(os.path.expanduser(user_path))
                else:
                    save_path = domain_lists_dir / default_filename
            else:
                filename = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                save_path = domain_lists_dir / filename

            # Ensure directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)

            if scraper.save_to_file(str(save_path), domains):
                print_success(f"Saved {len(domains)} domains to: {save_path}")
            else:
                print_error("Failed to save file.")
            get_input("\nPress Enter to continue...")

        elif choice == "6":
            # Load into SpiderFoot queue
            config = load_config()
            existing_pending = set(config.get('pending_domains', []))
            combined = existing_pending | domains
            config['pending_domains'] = list(combined)
            config['last_scrape_keywords'] = keywords
            config['domains_ready_for_scan'] = True  # Flag to show notification
            config['domains_ready_count'] = len(combined)
            save_config(config)

            added = len(combined) - len(existing_pending)
            print_success(f"Added {added} new domains to scan queue.")
            print_info(f"Total in queue: {len(combined)}")
            print()
            print(f"{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
            print(f"{C.BRIGHT_GREEN}  Returning to main menu. Select option [3] to start scanning!{C.RESET}")
            print(f"{C.BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
            time.sleep(1.5)
            break  # Return to main menu

        elif choice.lower() == "r":
            # Review & remove domains interactively
            domains = interactive_domain_removal(domains)

        elif choice.lower() == "k":
            # Expand with Kali tools
            if KALI_MODULE_AVAILABLE and is_enhanced_mode():
                domains = kali_expand_domains(domains, print_func=print, get_input_func=get_input)
                get_input("\nPress Enter to continue...")
            else:
                print_warning("Kali enhanced mode not available")
                get_input("\nPress Enter to continue...")

        elif choice == "7":
            # Save state before exiting
            config = load_config()
            config['last_scrape_domains'] = list(domains)
            config['last_scrape_keywords'] = keywords
            save_config(config)
            break

    return domains


def scrape_domains_menu():
    """Menu for scraping domains via keywords"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        cyber_banner_discovery()
    else:
        print_banner()
        print_section("Scrape Domains via Keywords", C.BRIGHT_CYAN)

    # Check dependencies
    try:
        from discovery.scraper import DomainScraper
    except ImportError as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Discovery module not available: {e}")
            cyber_info("Make sure you're running from the correct directory.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error(f"Discovery module not available: {e}")
            print_info("Make sure you're running from the correct directory.")
            get_input("\nPress Enter to return to main menu...")
        return

    # Check if search libraries are available
    deps = DomainScraper.check_dependencies()
    if not deps['google'] and not deps['duckduckgo']:
        if CYBER_UI_AVAILABLE:
            cyber_error("No search libraries available!")
            cyber_info("Install with: pip install googlesearch-python duckduckgo_search")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error("No search libraries available!")
            print_info("Install with: pip install googlesearch-python duckduckgo_search")
            get_input("\nPress Enter to return to main menu...")
        return

    # Check for previous session
    config = load_config()
    last_domains = config.get('last_scrape_domains', [])
    last_keywords = config.get('last_scrape_keywords', [])

    if last_domains:
        if CYBER_UI_AVAILABLE:
            console = get_console()
            console.print(f"\n[bright_yellow]Previous session found:[/]")
            console.print(f"  [dim]Domains:[/] [bright_green]{len(last_domains)}[/]")
            console.print(f"  [dim]Keywords:[/] [bright_cyan]{', '.join(last_keywords[:3])}{'...' if len(last_keywords) > 3 else ''}[/]\n")
            console.print("  [bright_yellow][1][/] Continue with previous results")
            console.print("  [bright_yellow][2][/] Add new keywords (merge with existing)")
            console.print("  [bright_red][3][/] Clear all & start fresh\n")
            resume_choice = cyber_prompt("Choice", "1")
        else:
            print(f"""
{C.BRIGHT_YELLOW}Previous session found:{C.RESET}
  Domains: {len(last_domains)}
  Keywords: {', '.join(last_keywords[:3])}{'...' if len(last_keywords) > 3 else ''}
""")
            print_menu_item("1", "Continue with previous results", "▶️")
            print_menu_item("2", "Add new keywords (merge with existing)", "➕")
            print_menu_item("3", "Clear all & start fresh", "🆕")
            print()
            resume_choice = get_input("Choice", "1")

        if resume_choice == "1":
            # Resume previous session
            use_google = deps['google']
            use_duckduckgo = deps['duckduckgo']
            max_results = 50

            result = show_scrape_results_menu(
                set(last_domains), last_keywords,
                use_google, use_duckduckgo, max_results
            )
            if result is not None:
                return

        elif resume_choice == "2":
            # Add new keywords but merge with existing domains
            use_google = deps['google']
            use_duckduckgo = deps['duckduckgo']
            max_results = 50
            existing_domains = set(last_domains)

            clear_screen()
            if CYBER_UI_AVAILABLE:
                cyber_banner_discovery()
                console = get_console()
                console.print(f"\n[bright_green]Keeping {len(existing_domains)} existing domains[/]")
                console.print("[white]Enter additional keywords to search for more domains.[/]")
                console.print("[dim]Separate multiple keywords with commas.[/]\n")
            else:
                print_banner()
                print_section("Add More Keywords", C.BRIGHT_CYAN)
                print(f"\n{C.GREEN}Keeping {len(existing_domains)} existing domains{C.RESET}")
                print(f"\n{C.WHITE}Enter additional keywords to search for more domains.{C.RESET}")
                print(f"{C.DIM}Separate multiple keywords with commas.{C.RESET}\n")

            if CYBER_UI_AVAILABLE:
                keywords_input = cyber_prompt("Keywords")
            else:
                keywords_input = get_input("Keywords")

            if keywords_input and keywords_input.strip():
                new_keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
                if new_keywords:
                    new_domains = run_domain_scrape(
                        new_keywords, use_google, use_duckduckgo, max_results,
                        existing_domains=existing_domains
                    )
                    # Merge keywords
                    all_keywords = last_keywords + [k for k in new_keywords if k not in last_keywords]
                    added = len(new_domains) - len(existing_domains)
                    print(f"\n{C.GREEN}✓{C.RESET} Added {added} new unique domains")
                    print(f"  Total domains: {len(new_domains)}")
                    get_input("\nPress Enter to continue...")

                    # Go to results menu with merged data
                    result = show_scrape_results_menu(
                        new_domains, all_keywords,
                        use_google, use_duckduckgo, max_results
                    )
                    if result is not None:
                        return
            return

        # resume_choice == "3" or anything else: clear and start fresh
        clear_screen()
        if CYBER_UI_AVAILABLE:
            cyber_banner_discovery()
        else:
            print_banner()
            print_section("Scrape Domains via Keywords", C.BRIGHT_CYAN)

    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print("\n[white]Enter keywords to search for domains.[/]")
        console.print("[dim]Separate multiple keywords with commas.[/]\n")
        console.print("[dim]Examples:[/]")
        console.print("  [bright_cyan]•[/] electrical contractors NYC, electrical services New York")
        console.print("  [bright_cyan]•[/] plastic surgery clinic, cosmetic surgeon")
        console.print("  [bright_cyan]•[/] online tutoring, math help\n")
    else:
        print(f"""
{C.WHITE}Enter keywords to search for domains.{C.RESET}
{C.DIM}Separate multiple keywords with commas.{C.RESET}

{C.DIM}Examples:{C.RESET}
  • electrical contractors NYC, electrical services New York
  • plastic surgery clinic, cosmetic surgeon
  • online tutoring, math help
""")

    # Get keywords
    if CYBER_UI_AVAILABLE:
        keywords_input = cyber_prompt("Keywords")
    else:
        keywords_input = get_input("Keywords")
    if keywords_input is None or not keywords_input.strip():
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
        return

    keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
    if not keywords:
        if CYBER_UI_AVAILABLE:
            cyber_error("No valid keywords provided.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error("No valid keywords provided.")
            get_input("\nPress Enter to return to main menu...")
        return

    if CYBER_UI_AVAILABLE:
        cyber_success(f"{len(keywords)} keyword(s) entered")
        console = get_console()
        console.print("\n[white]Search engine:[/]")
        if deps['google']:
            console.print("  [bright_yellow][1][/] Google [dim](no API key, uses delays)[/]")
        else:
            console.print("  [dim][1] Google (not available)[/]")
        if deps['duckduckgo']:
            console.print("  [bright_yellow][2][/] DuckDuckGo [dim](no API key, reliable)[/]")
        else:
            console.print("  [dim][2] DuckDuckGo (not available)[/]")
        if deps['google'] and deps['duckduckgo']:
            console.print("  [bright_yellow][3][/] Both [dim](recommended)[/]")
        console.print()
    else:
        print(f"\n{C.GREEN}✓{C.RESET} {len(keywords)} keyword(s) entered\n")
        print(f"{C.WHITE}Search engine:{C.RESET}")
        if deps['google']:
            print_menu_item("1", "Google (no API key, uses delays to avoid blocking)", "")
        else:
            print(f"  {C.DIM}[1] Google (not available - install googlesearch-python){C.RESET}")
        if deps['duckduckgo']:
            print_menu_item("2", "DuckDuckGo (no API key, more reliable)", "")
        else:
            print(f"  {C.DIM}[2] DuckDuckGo (not available - install duckduckgo_search){C.RESET}")
        if deps['google'] and deps['duckduckgo']:
            print_menu_item("3", "Both (searches both, combines results)", "")
        print()

    # Default to what's available
    default_engine = "3" if (deps['google'] and deps['duckduckgo']) else ("1" if deps['google'] else "2")
    if CYBER_UI_AVAILABLE:
        engine_choice = cyber_prompt("Choice", default_engine)
    else:
        engine_choice = get_input(f"Choice", default_engine)
    if engine_choice is None:
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
        return

    use_google = engine_choice in ('1', '3') and deps['google']
    use_duckduckgo = engine_choice in ('2', '3') and deps['duckduckgo']

    if not use_google and not use_duckduckgo:
        if CYBER_UI_AVAILABLE:
            cyber_error("No search engine selected.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error("No search engine selected.")
            get_input("\nPress Enter to return to main menu...")
        return

    # Max results per keyword
    if CYBER_UI_AVAILABLE:
        max_results = cyber_prompt("Max results per keyword", "50")
    else:
        max_results = get_input("Max results per keyword", "50")
    if max_results is None:
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
        return
    try:
        max_results = int(max_results)
    except ValueError:
        max_results = 50

    # Run the scraper
    domains = run_domain_scrape(keywords, use_google, use_duckduckgo, max_results)

    # Show results summary
    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print("\n[bright_green]" + "━" * 60 + "[/]")
        cyber_success("Scraping complete!")
        console.print(f"  [dim]Keywords searched:[/]    [bright_cyan]{len(keywords)}[/]")
        console.print(f"  [dim]Unique domains found:[/] [bright_green]{len(domains)}[/]")
        console.print("[bright_green]" + "━" * 60 + "[/]\n")
    else:
        print(f"""
{C.BRIGHT_GREEN}{'━' * 60}{C.RESET}
{C.GREEN}✓{C.RESET} Scraping complete!

  Keywords searched:     {len(keywords)}
  Unique domains found:  {len(domains)}
{C.BRIGHT_GREEN}{'━' * 60}{C.RESET}
""")

    if not domains:
        if CYBER_UI_AVAILABLE:
            cyber_warning("No domains found. Try different keywords.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_warning("No domains found. Try different keywords.")
            get_input("\nPress Enter to return to main menu...")
        return

    # BLACKLIST FILTER: Remove known platform domains
    try:
        from core.blacklist import filter_domains, get_blacklist_stats

        original_count = len(domains)
        clean_domains, blocked_domains = filter_domains(domains)

        if blocked_domains:
            stats = get_blacklist_stats()
            if CYBER_UI_AVAILABLE:
                console = get_console()
                console.print("\n[bright_yellow]" + "━" * 60 + "[/]")
                console.print("[bright_yellow]BLACKLIST FILTER[/]\n")
                console.print(f"  [bright_red]Filtered out:[/] {len(blocked_domains)} platform domains")
                console.print(f"  [bright_green]Remaining:[/]    {len(clean_domains)} target domains\n")
                console.print(f"  [dim]Blacklisted: {', '.join(sorted(blocked_domains)[:5])}{'...' if len(blocked_domains) > 5 else ''}[/]")
                console.print("[bright_yellow]" + "━" * 60 + "[/]\n")
                console.print(f"  [bright_yellow][1][/] Use filtered list ({len(clean_domains)} domains) [dim]- recommended[/]")
                console.print(f"  [bright_yellow][2][/] Keep all domains ({original_count} domains)")
                console.print(f"  [bright_yellow][3][/] View all filtered domains\n")
                filter_choice = cyber_prompt("Choice", "1") or "1"
            else:
                print(f"""
{C.BRIGHT_YELLOW}{'━' * 60}{C.RESET}
{C.YELLOW}BLACKLIST FILTER{C.RESET}

  {C.RED}Filtered out:{C.RESET} {len(blocked_domains)} platform domains
  {C.GREEN}Remaining:{C.RESET}    {len(clean_domains)} target domains

  {C.DIM}Blacklisted: {', '.join(sorted(blocked_domains)[:5])}{'...' if len(blocked_domains) > 5 else ''}{C.RESET}
{C.BRIGHT_YELLOW}{'━' * 60}{C.RESET}
""")
                print(f"  [1] Use filtered list ({len(clean_domains)} domains) - recommended")
                print(f"  [2] Keep all domains ({original_count} domains)")
                print(f"  [3] View all filtered domains")
                print()
                filter_choice = get_input("Choice [1]: ") or "1"

            if filter_choice == "3":
                if CYBER_UI_AVAILABLE:
                    console.print("\n  [dim]Filtered domains:[/]")
                    for d in sorted(blocked_domains):
                        console.print(f"    [bright_red]✗[/] {d}")
                    console.print()
                    filter_choice = cyber_prompt("Use filtered list? [Y/n]") or "y"
                else:
                    print(f"\n  {C.DIM}Filtered domains:{C.RESET}")
                    for d in sorted(blocked_domains):
                        print(f"    {C.RED}✗{C.RESET} {d}")
                    print()
                    filter_choice = get_input("Use filtered list? [Y/n]: ") or "y"
                if filter_choice.lower() != 'n':
                    domains = clean_domains
            elif filter_choice == "2":
                if CYBER_UI_AVAILABLE:
                    cyber_info("Keeping all domains (including platforms)")
                else:
                    print_info("Keeping all domains (including platforms)")
            else:
                domains = clean_domains
                if CYBER_UI_AVAILABLE:
                    cyber_success(f"Using {len(domains)} filtered domains")
                else:
                    print_success(f"Using {len(domains)} filtered domains")

    except ImportError:
        pass  # Blacklist module not available, skip filtering

    # Note: Interactive domain review and Kali expansion are now in the Results Menu
    if CYBER_UI_AVAILABLE:
        cyber_prompt("Press Enter to continue to results menu")
    else:
        get_input("Press Enter to continue to results menu...")

    # Show results menu
    while True:
        result = show_scrape_results_menu(
            domains, keywords, use_google, use_duckduckgo, max_results
        )
        if result is None:
            scrape_domains_menu()
            return
        else:
            break


def load_domains_menu():
    """Menu for loading domains from a file"""
    clear_screen()

    # Use cyberpunk UI if available
    if CYBER_UI_AVAILABLE:
        cyber_banner_import()
    else:
        print_banner()
        print_section("Load Domains from File", C.BRIGHT_CYAN)

    try:
        from discovery.scraper import DomainScraper
    except ImportError as e:
        if CYBER_UI_AVAILABLE:
            cyber_error(f"Discovery module not available: {e}")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error(f"Discovery module not available: {e}")
            get_input("\nPress Enter to return to main menu...")
        return

    # Check for saved lists in domain_lists directory
    puppetmaster_dir = Path(__file__).parent
    domain_lists_dir = puppetmaster_dir / "domain_lists"
    available_lists = []

    if domain_lists_dir.exists():
        for txt_file in sorted(domain_lists_dir.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                # Count domains and get file info
                with open(txt_file, 'r') as f:
                    domain_count = sum(1 for line in f if line.strip() and not line.strip().startswith('#'))
                mod_time = datetime.fromtimestamp(txt_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                available_lists.append({
                    'path': txt_file,
                    'name': txt_file.name,
                    'domains': domain_count,
                    'modified': mod_time
                })
            except Exception:
                pass

    # Show available lists if any exist
    if available_lists:
        if CYBER_UI_AVAILABLE:
            console = get_console()
            console.print("\n[bold white]Available Domain Lists:[/]")
            console.print(f"[dim]Saved in: {domain_lists_dir}[/]\n")
            for i, lst in enumerate(available_lists[:10], 1):
                console.print(f"  [bold yellow]\\[{i}][/] {lst['name']}")
                console.print(f"      [dim]{lst['domains']} domains • {lst['modified']}[/]")
            if len(available_lists) > 10:
                console.print(f"  [dim]... and {len(available_lists) - 10} more files[/]")
            console.print(f"\n  [bold cyan]\\[C][/] Enter custom file path")
            console.print(f"  [bold red]\\[D][/] Delete/Modify domain lists")
            console.print()
            list_choice = cyber_prompt("Select list", "1")
        else:
            print(f"\n{C.WHITE}Available Domain Lists:{C.RESET}")
            print(f"{C.DIM}Saved in: {domain_lists_dir}{C.RESET}\n")
            for i, lst in enumerate(available_lists[:10], 1):
                print(f"  {C.BRIGHT_YELLOW}[{i}]{C.RESET} {lst['name']}")
                print(f"      {C.DIM}{lst['domains']} domains • {lst['modified']}{C.RESET}")
            if len(available_lists) > 10:
                print(f"  {C.DIM}... and {len(available_lists) - 10} more files{C.RESET}")
            print(f"\n  {C.BRIGHT_CYAN}[C]{C.RESET} Enter custom file path")
            print(f"  {C.BRIGHT_RED}[D]{C.RESET} Delete/Modify domain lists")
            print()
            list_choice = get_input("Select list", "1")

        # Handle selection
        file_path = None
        if list_choice and list_choice.lower() == 'd':
            _delete_modify_domain_lists(domain_lists_dir, available_lists)
            return
        elif list_choice and list_choice.lower() == 'c':
            # Custom path input
            if CYBER_UI_AVAILABLE:
                console = get_console()
                console.print("\n[white]Enter path to domain file:[/]")
                file_path = cyber_prompt("File path")
            else:
                print(f"\n{C.WHITE}Enter path to domain file:{C.RESET}")
                file_path = get_input("File path")
        elif list_choice and list_choice.isdigit():
            idx = int(list_choice) - 1
            if 0 <= idx < len(available_lists):
                file_path = str(available_lists[idx]['path'])
            else:
                print_warning("Invalid selection")
                get_input("\nPress Enter to return to main menu...")
                return
        else:
            # Default to first list if nothing entered
            if available_lists:
                file_path = str(available_lists[0]['path'])
            else:
                return
    else:
        # No saved lists, show traditional input
        if CYBER_UI_AVAILABLE:
            console = get_console()
            console.print("\n[white]Load a list of domains from a text file.[/]")
            console.print("[dim]File should contain one domain per line.[/]\n")
            console.print("[dim]Example file format:[/]")
            console.print("  [bright_green]example1.com[/]")
            console.print("  [bright_green]example2.com[/]")
            console.print("  [bright_green]www.example3.com[/]")
            console.print("  [bright_cyan]https://example4.com/page[/]  [dim](URLs will be parsed)[/]\n")
            console.print(f"[dim]Tip: Save lists from option [1] to {domain_lists_dir}[/]\n")
            file_path = cyber_prompt("Enter path to file")
        else:
            print(f"""
{C.WHITE}Load a list of domains from a text file.{C.RESET}
{C.DIM}File should contain one domain per line.{C.RESET}

{C.DIM}Example file format:{C.RESET}
  example1.com
  example2.com
  www.example3.com
  https://example4.com/page  {C.DIM}(URLs will be parsed){C.RESET}

{C.DIM}Tip: Save lists from option [1] to {domain_lists_dir}{C.RESET}
""")
            file_path = get_input("Enter path to file")
    if file_path is None or not file_path.strip():
        if CYBER_UI_AVAILABLE:
            cyber_info("Cancelled.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_info("Cancelled.")
            get_input("\nPress Enter to return to main menu...")
        return

    file_path = os.path.expanduser(file_path.strip())

    # Check file exists
    if not os.path.exists(file_path):
        if CYBER_UI_AVAILABLE:
            cyber_error(f"File not found: {file_path}")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error(f"File not found: {file_path}")
            get_input("\nPress Enter to return to main menu...")
        return

    if not os.path.isfile(file_path):
        if CYBER_UI_AVAILABLE:
            cyber_error("That's not a file.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error("That's not a file.")
            get_input("\nPress Enter to return to main menu...")
        return

    # Load and validate
    if CYBER_UI_AVAILABLE:
        console = get_console()
        console.print("\n[bright_magenta]" + "━" * 50 + "[/]")
        console.print("[bright_magenta]VALIDATING FILE[/]")
        console.print("[bright_magenta]" + "━" * 50 + "[/]\n")
    else:
        print_section("Validating File", C.BRIGHT_MAGENTA)

    scraper = DomainScraper()
    valid_domains, invalid_lines = scraper.load_from_file(file_path)

    if CYBER_UI_AVAILABLE:
        console = get_console()
        cyber_success(f"File found: {os.path.basename(file_path)}")
        console.print("\n[dim]Parsing domains...[/]")
        console.print(f"  [bright_cyan]•[/] Valid domains:     [bright_green]{len(valid_domains)}[/]")
        console.print(f"  [bright_cyan]•[/] Invalid/skipped:   [bright_yellow]{len(invalid_lines)}[/]\n")
    else:
        print(f"""
{C.GREEN}✓{C.RESET} File found: {os.path.basename(file_path)}

Parsing domains...
  • Valid domains:     {C.GREEN}{len(valid_domains)}{C.RESET}
  • Invalid/skipped:   {C.YELLOW}{len(invalid_lines)}{C.RESET}
""")

    # Show invalid lines (up to 5)
    if invalid_lines:
        if CYBER_UI_AVAILABLE:
            console.print("[dim]Invalid lines:[/]")
            for line_num, line, reason in invalid_lines[:5]:
                console.print(f"  [dim]Line {line_num}: \"{line[:30]}...\" ({reason})[/]")
            if len(invalid_lines) > 5:
                console.print(f"  [dim]... and {len(invalid_lines) - 5} more[/]")
            console.print()
        else:
            print(f"{C.DIM}Invalid lines:{C.RESET}")
            for line_num, line, reason in invalid_lines[:5]:
                print(f"  {C.DIM}Line {line_num}: \"{line[:30]}...\" ({reason}){C.RESET}")
            if len(invalid_lines) > 5:
                print(f"  {C.DIM}... and {len(invalid_lines) - 5} more{C.RESET}")
            print()

    if not valid_domains:
        if CYBER_UI_AVAILABLE:
            cyber_error("No valid domains found in file.")
            cyber_prompt("Press Enter to return to main menu")
        else:
            print_error("No valid domains found in file.")
            get_input("\nPress Enter to return to main menu...")
        return

    if CYBER_UI_AVAILABLE:
        cyber_success(f"Loaded {len(valid_domains)} domains")
    else:
        print_success(f"Loaded {len(valid_domains)} domains")

    # Interactive menu for loaded domains - allow review before adding to queue
    while True:
        if CYBER_UI_AVAILABLE:
            console = get_console()
            console.print(f"\n[bold white]Loaded Domains:[/] [cyan]{len(valid_domains)}[/] domains ready")
            console.print()
            console.print("  [bold green]\\[1][/] Add to SpiderFoot scan queue")
            console.print("  [bold magenta]\\[R][/] Review & remove domains")
            console.print("  [bold yellow]\\[Q][/] Cancel - return to main menu")
            console.print()
            choice = cyber_prompt("Select option", "1")
        else:
            print(f"\n{C.WHITE}Loaded Domains:{C.RESET} {C.CYAN}{len(valid_domains)}{C.RESET} domains ready")
            print()
            print(f"  {C.GREEN}[1]{C.RESET} Add to SpiderFoot scan queue")
            print(f"  {C.BRIGHT_MAGENTA}[R]{C.RESET} Review & remove domains")
            print(f"  {C.YELLOW}[Q]{C.RESET} Cancel - return to main menu")
            print()
            choice = get_input("Select option", "1")

        if choice is None or choice.lower() == 'q':
            if CYBER_UI_AVAILABLE:
                cyber_info("Cancelled.")
            else:
                print_info("Cancelled.")
            break

        elif choice.lower() == 'r':
            # Review & remove domains interactively
            valid_domains = interactive_domain_removal(valid_domains)
            if not valid_domains:
                if CYBER_UI_AVAILABLE:
                    cyber_warning("No domains remaining after review.")
                else:
                    print_warning("No domains remaining after review.")
                break
            # Loop back to menu

        elif choice == '1':
            config = load_config()
            # MERGE with existing queue (don't replace!)
            existing_pending = set(config.get('pending_domains', []))
            combined = existing_pending | valid_domains
            config['pending_domains'] = list(combined)
            save_config(config)

            added = len(combined) - len(existing_pending)
            if CYBER_UI_AVAILABLE:
                if existing_pending:
                    cyber_success(f"Added {added} new domains to scan queue.")
                    cyber_info(f"Total in queue: {len(combined)}")
                else:
                    cyber_success(f"Loaded {len(valid_domains)} domains into scan queue.")
                cyber_info("Use option [3] Run SpiderFoot scans to start scanning.")
            else:
                if existing_pending:
                    print_success(f"Added {added} new domains to scan queue.")
                    print_info(f"Total in queue: {len(combined)}")
                else:
                    print_success(f"Loaded {len(valid_domains)} domains into scan queue.")
                print_info("Use option [3] Run SpiderFoot scans to start scanning.")
            break

    if CYBER_UI_AVAILABLE:
        cyber_prompt("Press Enter to return to main menu")
    else:
        get_input("\nPress Enter to return to main menu...")


