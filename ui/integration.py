"""
PUPPETMASTER UI Integration
Bridge between Gaming HUD and existing puppetmaster.py
"""

import os
import sys
from pathlib import Path
from typing import Callable, Optional, Dict, Any

from .gaming_hud import GamingHUD
from .cyberpunk_hud import CyberpunkHUD

# Try to import JobTracker for real queue stats
try:
    from discovery.jobs import JobTracker
    HAS_JOB_TRACKER = True
except ImportError:
    HAS_JOB_TRACKER = False


class NoTTYError(Exception):
    """Raised when stdin is not a TTY and Gaming HUD cannot run"""
    pass


def create_stats_callback(
    load_config: Callable,
    is_background_scan_running: Callable,
    get_background_scan_stats: Callable,
    should_show_kali_menu: Callable,
    is_enhanced_mode: Optional[Callable] = None,
    get_kali_status_line: Optional[Callable] = None,
    get_scan_mode: Optional[Callable] = None,
) -> Callable[[], Dict[str, Any]]:
    """
    Create a stats callback function for the Gaming HUD

    Args:
        load_config: Function to load puppetmaster config
        is_background_scan_running: Function to check if bg scan is active
        get_background_scan_stats: Function to get bg scan stats
        should_show_kali_menu: Function to check if Kali menu should show
        is_enhanced_mode: Optional function to check Kali enhanced mode
        get_kali_status_line: Optional function to get Kali status string
        get_scan_mode: Optional function to get current scan mode

    Returns:
        A callback function that returns current stats dict
    """

    def get_stats() -> Dict[str, Any]:
        stats = {
            'queue_count': 0,
            'scan_count': 0,
            'cluster_count': 0,
            'blacklist_count': 231,  # Default
            'status': 'STANDBY',
            'discover_progress': 0,
            'scan_progress': 0,
            'analyze_progress': 0,
            'show_kali': False,
            'scan_mode': 'STANDARD',
            'bg_scan_running': False,
            'bg_scan_domain': '',
            'bg_scan_completed': 0,
            'bg_scan_total': 0,
            'kali_active': False,
            'kali_status': '',
            'domains_ready': False,
            'domains_ready_count': 0,
            'pending_domains': [],  # List of pending domain names for display
        }

        try:
            # Load config
            config = load_config()

            # Check domains ready
            if config.get('domains_ready_for_scan'):
                stats['domains_ready'] = True
                stats['domains_ready_count'] = config.get('domains_ready_count', 0)

            # Get blacklist count from config if available
            stats['blacklist_count'] = config.get('blacklist_count', 231)

            # Get REAL queue stats from JobTracker
            if HAS_JOB_TRACKER:
                try:
                    tracker = JobTracker()
                    job_stats = tracker.get_stats()

                    # Update stats with real values
                    stats['queue_count'] = job_stats.get('pending', 0) + job_stats.get('running', 0)
                    stats['scan_count'] = job_stats.get('completed', 0)

                    # Get pending domain names for display
                    pending_jobs = tracker.get_pending()[:5]
                    stats['pending_domains'] = [j.domain for j in pending_jobs]

                    # Calculate scan progress
                    total = job_stats.get('total', 0)
                    if total > 0:
                        completed = job_stats.get('completed', 0)
                        stats['scan_progress'] = int((completed / total) * 100)
                except Exception:
                    pass

            # Also check for domains staged in config (from module 1, not yet in JobTracker)
            config_pending = config.get('pending_domains', [])
            if config_pending and stats['queue_count'] == 0:
                # Domains are staged but not yet added to JobTracker
                # Show them as ready to scan
                stats['queue_count'] = len(config_pending)
                stats['pending_domains'] = config_pending[:5]
                stats['status'] = 'READY'  # Indicate domains are ready to scan

            # Check background scan
            if is_background_scan_running():
                stats['bg_scan_running'] = True
                stats['status'] = 'SCANNING'
                bg_stats = get_background_scan_stats()
                stats['bg_scan_domain'] = bg_stats.get('current_domain', '')
                stats['bg_scan_completed'] = bg_stats.get('completed', 0)
                stats['bg_scan_total'] = bg_stats.get('total', 0)

                # Calculate progress from background scan
                if bg_stats.get('total', 0) > 0:
                    pct = int((bg_stats['completed'] / bg_stats['total']) * 100)
                    stats['scan_progress'] = pct
                    # Also update queue/scan counts from background scan
                    stats['queue_count'] = bg_stats.get('total', 0) - bg_stats.get('completed', 0)
                    stats['scan_count'] = bg_stats.get('completed', 0)

            # Check Kali menu
            stats['show_kali'] = should_show_kali_menu()

            # Check Kali enhanced mode
            if is_enhanced_mode and callable(is_enhanced_mode):
                stats['kali_active'] = is_enhanced_mode()

            if get_kali_status_line and callable(get_kali_status_line):
                stats['kali_status'] = get_kali_status_line()

            # Get scan mode
            if get_scan_mode and callable(get_scan_mode):
                stats['scan_mode'] = get_scan_mode()

            # Try to get cluster count from results
            output_dirs = config.get('output_dirs', [])
            for output_dir in output_dirs[:1]:  # Check most recent
                out_path = Path(output_dir)
                if out_path.exists():
                    # Count clusters from latest analysis
                    results_dir = out_path / 'results'
                    if results_dir.exists():
                        cluster_files = list(results_dir.glob('*clusters*.json'))
                        if cluster_files:
                            import json
                            latest = max(cluster_files, key=lambda x: x.stat().st_mtime)
                            try:
                                data = json.loads(latest.read_text())
                                stats['cluster_count'] = len(data.get('clusters', []))
                            except Exception:
                                pass
                    break

        except Exception:
            pass  # Return defaults on any error

        return stats

    return get_stats


def run_gaming_hud_menu(
    load_config: Callable,
    is_background_scan_running: Callable,
    get_background_scan_stats: Callable,
    should_show_kali_menu: Callable,
    is_enhanced_mode: Optional[Callable] = None,
    get_kali_status_line: Optional[Callable] = None,
    get_scan_mode: Optional[Callable] = None,
) -> str:
    """
    Run the Gaming HUD and return the selected option

    Returns:
        The selected tool key (e.g., "01", "K1", "Q")

    Raises:
        NoTTYError: If stdin is not a TTY (keyboard input won't work)
    """
    # Gaming HUD requires a real TTY for keyboard input (termios/tty)
    if not sys.stdin.isatty():
        raise NoTTYError("Gaming HUD requires a TTY for keyboard input")

    stats_callback = create_stats_callback(
        load_config=load_config,
        is_background_scan_running=is_background_scan_running,
        get_background_scan_stats=get_background_scan_stats,
        should_show_kali_menu=should_show_kali_menu,
        is_enhanced_mode=is_enhanced_mode,
        get_kali_status_line=get_kali_status_line,
        get_scan_mode=get_scan_mode,
    )

    show_kali = should_show_kali_menu()

    hud = GamingHUD(
        show_kali=show_kali,
        stats_callback=stats_callback,
    )

    return hud.run()


def map_hud_key_to_choice(key: str) -> str:
    """
    Map Gaming HUD key to the original choice format

    Args:
        key: The key from Gaming HUD (e.g., "01", "K1", "Q")

    Returns:
        The choice string for the original menu handler
    """
    # Mapping from HUD key format to original choice format
    mapping = {
        "01": "1",
        "02": "2",
        "03": "3",
        "04": "4",
        "05": "5",
        "06": "6",
        "07": "7",
        "08": "8",
        "09": "9",
        "10": "10",
        "11": "11",
        "12": "12",
        "K1": "k1",
        "K2": "k2",
        "K3": "k3",
        "K4": "k4",
        "K5": "k5",
        "Q": "q",
    }

    return mapping.get(key, key.lower())


def run_cyberpunk_hud_menu(
    load_config: Callable,
    is_background_scan_running: Callable,
    get_background_scan_stats: Callable,
    should_show_kali_menu: Callable,
    is_enhanced_mode: Optional[Callable] = None,
    get_kali_status_line: Optional[Callable] = None,
    get_scan_mode: Optional[Callable] = None,
) -> str:
    """
    Run the Cyberpunk HUD and return the selected option

    Returns:
        The selected tool key (e.g., "01", "K1", "Q")

    Raises:
        NoTTYError: If stdin is not a TTY (keyboard input won't work)
    """
    # Cyberpunk HUD requires a real TTY for keyboard input
    if not sys.stdin.isatty():
        raise NoTTYError("Cyberpunk HUD requires a TTY for keyboard input")

    stats_callback = create_stats_callback(
        load_config=load_config,
        is_background_scan_running=is_background_scan_running,
        get_background_scan_stats=get_background_scan_stats,
        should_show_kali_menu=should_show_kali_menu,
        is_enhanced_mode=is_enhanced_mode,
        get_kali_status_line=get_kali_status_line,
        get_scan_mode=get_scan_mode,
    )

    show_kali = should_show_kali_menu()

    hud = CyberpunkHUD(
        show_kali=show_kali,
        stats_callback=stats_callback,
    )

    return hud.run()
