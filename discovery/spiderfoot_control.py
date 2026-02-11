#!/usr/bin/env python3
"""
spiderfoot_control.py - Unified SpiderFoot Control Center

Consolidates CLI batch scanning and Web GUI into a single interface with:
- Intensity presets with configurable timeouts
- ETA tracking based on completed scan times
- Reset SpiderFoot database function
- Stuck scan detection
- tmux warning for long scan sessions
"""

import os
import re
import sys
import time
import subprocess
import threading
import shutil
import shlex
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable, Tuple
from dataclasses import dataclass

from .jobs import JobTracker, JobStatus
from .scanner import SpiderFootScanner


# =============================================================================
# INTENSITY PRESETS
# =============================================================================

@dataclass
class IntensityPreset:
    """Defines a scan intensity preset"""
    name: str
    description: str
    timeout_seconds: int
    modules: Optional[str]  # None = all modules, or specific module list
    parallel_scans: int
    estimated_time_per_domain: int  # seconds, for ETA calculation
    color: str  # For UI display


INTENSITY_PRESETS = {
    'safe': IntensityPreset(
        name='Safe',
        description='Quick scan, basic modules only. ~5 min/domain.',
        timeout_seconds=900,  # 15 min timeout
        modules='sfp_dnsresolve,sfp_dnsbrute,sfp_ssl,sfp_webserver,sfp_emailcrawlr',
        parallel_scans=5,
        estimated_time_per_domain=300,  # 5 min
        color='green'
    ),
    'moderate': IntensityPreset(
        name='Moderate',
        description='Standard scan, most modules. ~30 min/domain.',
        timeout_seconds=2700,  # 45 min timeout
        modules=None,  # All modules but with timeout
        parallel_scans=3,
        estimated_time_per_domain=1800,  # 30 min
        color='yellow'
    ),
    'committed': IntensityPreset(
        name='Committed',
        description='Full scan, all modules, longer timeout. ~2 hrs/domain.',
        timeout_seconds=14400,  # 4 hour timeout
        modules=None,  # All modules
        parallel_scans=2,
        estimated_time_per_domain=7200,  # 2 hrs
        color='red'
    ),
    'custom': IntensityPreset(
        name='Custom',
        description='Configure your own timeout and parallelism.',
        timeout_seconds=3600,  # 1 hr default
        modules=None,
        parallel_scans=3,
        estimated_time_per_domain=2700,
        color='magenta'
    )
}


# =============================================================================
# SECURITY HELPERS
# =============================================================================

# Safe domain pattern - alphanumeric, dots, hyphens only
SAFE_DOMAIN_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\.\-]*[a-zA-Z0-9]$')

def is_safe_domain(domain: str) -> bool:
    """Check if domain contains only safe characters for shell use"""
    if not domain or len(domain) > 253:
        return False
    return bool(SAFE_DOMAIN_PATTERN.match(domain))

def sanitize_for_pgrep(domain: str) -> str:
    """Sanitize domain for safe use in pgrep pattern"""
    # Only allow alphanumeric, dots, hyphens - escape regex special chars
    if not is_safe_domain(domain):
        return ""  # Return empty to prevent matching
    return re.escape(domain)


# =============================================================================
# ETA TRACKER
# =============================================================================

class ETATracker:
    """Tracks scan completion times and calculates ETA for remaining scans"""

    def __init__(self):
        self.completed_times: List[float] = []  # seconds per scan
        self.start_time: Optional[datetime] = None
        self.total_scans: int = 0
        self.completed_scans: int = 0
        self.parallel_scans: int = 1

    def start(self, total_scans: int, parallel_scans: int = 1):
        """Start tracking a new batch"""
        self.start_time = datetime.now()
        self.total_scans = total_scans
        self.completed_scans = 0
        self.completed_times = []
        self.parallel_scans = max(1, parallel_scans)

    def record_completion(self, duration_seconds: float):
        """Record a scan completion time"""
        self.completed_times.append(duration_seconds)
        self.completed_scans += 1

    def get_avg_time(self) -> float:
        """Get average time per scan in seconds"""
        if not self.completed_times:
            return 0
        return sum(self.completed_times) / len(self.completed_times)

    def get_eta(self) -> Optional[timedelta]:
        """Calculate ETA for remaining scans"""
        remaining = self.total_scans - self.completed_scans
        if remaining <= 0:
            return timedelta(0)

        avg_time = self.get_avg_time()
        if avg_time == 0:
            return None  # Can't estimate yet

        # Account for parallelism
        batches_remaining = remaining / self.parallel_scans
        eta_seconds = batches_remaining * avg_time
        return timedelta(seconds=int(eta_seconds))

    def get_eta_string(self) -> str:
        """Get human-readable ETA string"""
        eta = self.get_eta()
        if eta is None:
            return "Calculating..."

        total_seconds = int(eta.total_seconds())
        if total_seconds <= 0:
            return "Complete"

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def get_progress_string(self) -> str:
        """Get progress summary string"""
        if self.total_scans == 0:
            return "No scans"

        pct = (self.completed_scans / self.total_scans) * 100
        avg = self.get_avg_time()
        avg_str = f"{avg/60:.1f} min" if avg > 0 else "N/A"

        return (f"{self.completed_scans}/{self.total_scans} ({pct:.0f}%) | "
                f"Avg: {avg_str} | ETA: {self.get_eta_string()}")


# =============================================================================
# STUCK SCAN DETECTION
# =============================================================================

class StuckScanDetector:
    """Detects scans that appear to be stuck (running much longer than average)"""

    def __init__(self, threshold_multiplier: float = 3.0):
        self.threshold_multiplier = threshold_multiplier
        self.scan_start_times: Dict[str, datetime] = {}
        self.avg_scan_time: float = 0  # seconds
        self.completed_count: int = 0

    def scan_started(self, domain: str):
        """Record that a scan has started"""
        self.scan_start_times[domain] = datetime.now()

    def scan_completed(self, domain: str, duration: float):
        """Record that a scan completed, update average"""
        if domain in self.scan_start_times:
            del self.scan_start_times[domain]

        # Update running average
        self.avg_scan_time = (
            (self.avg_scan_time * self.completed_count + duration) /
            (self.completed_count + 1)
        )
        self.completed_count += 1

    def get_stuck_scans(self, min_samples: int = 3) -> List[Tuple[str, float, float]]:
        """
        Get list of potentially stuck scans.

        Returns:
            List of (domain, running_time_seconds, threshold_seconds)
        """
        if self.completed_count < min_samples:
            return []  # Not enough data yet

        threshold = self.avg_scan_time * self.threshold_multiplier
        now = datetime.now()
        stuck = []

        for domain, start_time in self.scan_start_times.items():
            running_time = (now - start_time).total_seconds()
            if running_time > threshold:
                stuck.append((domain, running_time, threshold))

        return stuck

    def get_stuck_warning(self) -> Optional[str]:
        """Get a warning message if there are stuck scans"""
        stuck = self.get_stuck_scans()
        if not stuck:
            return None

        lines = ["Potentially stuck scans detected:"]
        for domain, running, threshold in stuck:
            lines.append(f"  - {domain}: running {running/60:.0f}m (threshold: {threshold/60:.0f}m)")
        return "\n".join(lines)


# =============================================================================
# SPIDERFOOT DATABASE MANAGEMENT
# =============================================================================

def find_spiderfoot_db(sf_path: str) -> Optional[str]:
    """
    Find the SpiderFoot database file.

    SpiderFoot stores its database in the installation directory.
    """
    sf_dir = Path(sf_path).parent

    # Common database locations
    possible_paths = [
        sf_dir / "spiderfoot.db",
        sf_dir / "sf.db",
        sf_dir / "data" / "spiderfoot.db",
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    # Search for any .db file in the SpiderFoot directory
    for db_file in sf_dir.glob("*.db"):
        return str(db_file)

    return None


def get_db_size(db_path: str) -> str:
    """Get human-readable database size"""
    try:
        size = os.path.getsize(db_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    except Exception:
        return "Unknown"


def count_db_scans(db_path: str) -> Dict[str, int]:
    """
    Count scans in the SpiderFoot database by status.

    Returns dict with keys: total, running, finished, aborted
    """
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get scan counts by status
        cursor.execute("""
            SELECT status, COUNT(*) FROM tbl_scan_instance
            GROUP BY status
        """)

        counts = {'total': 0, 'running': 0, 'finished': 0, 'aborted': 0, 'created': 0}
        status_map = {
            'RUNNING': 'running',
            'FINISHED': 'finished',
            'ABORTED': 'aborted',
            'CREATED': 'created'
        }

        for status, count in cursor.fetchall():
            counts['total'] += count
            key = status_map.get(status, status.lower())
            if key in counts:
                counts[key] = count

        conn.close()
        return counts
    except Exception as e:
        return {'total': 0, 'running': 0, 'finished': 0, 'aborted': 0, 'error': str(e)}


def reset_spiderfoot_db(sf_path: str, backup: bool = True) -> Tuple[bool, str]:
    """
    Reset SpiderFoot database by deleting it.

    Args:
        sf_path: Path to sf.py
        backup: If True, create a backup before deletion

    Returns:
        (success, message)
    """
    db_path = find_spiderfoot_db(sf_path)
    if not db_path:
        return False, "SpiderFoot database not found"

    try:
        # Get info before deletion
        size = get_db_size(db_path)
        counts = count_db_scans(db_path)

        if backup:
            backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(db_path, backup_path)

        # Delete the database
        os.remove(db_path)

        msg = f"Deleted SpiderFoot database ({size}, {counts['total']} scans)"
        if backup:
            msg += f"\nBackup saved to: {backup_path}"

        return True, msg

    except PermissionError:
        return False, "Permission denied - is SpiderFoot running?"
    except Exception as e:
        return False, f"Failed to delete database: {e}"


def kill_spiderfoot_processes() -> int:
    """Kill all running SpiderFoot processes. Returns count of killed processes."""
    killed = 0
    try:
        result = subprocess.run(
            ["pgrep", "-f", "sf.py"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            pids = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
            for pid in pids:
                try:
                    subprocess.run(["kill", "-9", pid], capture_output=True)
                    killed += 1
                except Exception:
                    pass
    except Exception:
        pass
    return killed


# =============================================================================
# TMUX WARNING
# =============================================================================

def is_in_tmux() -> bool:
    """Check if currently running inside tmux"""
    return os.environ.get('TMUX') is not None


def estimate_total_time(num_domains: int, preset: IntensityPreset) -> timedelta:
    """Estimate total time for a batch of scans"""
    batches = num_domains / preset.parallel_scans
    total_seconds = batches * preset.estimated_time_per_domain
    return timedelta(seconds=int(total_seconds))


def should_warn_tmux(num_domains: int, preset: IntensityPreset, threshold_hours: float = 1.0) -> bool:
    """Check if we should warn about using tmux for this scan"""
    if is_in_tmux():
        return False  # Already in tmux

    estimated = estimate_total_time(num_domains, preset)
    threshold = timedelta(hours=threshold_hours)
    return estimated > threshold


def get_tmux_warning(num_domains: int, preset: IntensityPreset) -> Optional[str]:
    """Get tmux warning message if applicable"""
    if not should_warn_tmux(num_domains, preset):
        return None

    estimated = estimate_total_time(num_domains, preset)
    hours = estimated.total_seconds() / 3600

    return (
        f"This scan batch is estimated to take {hours:.1f} hours.\n"
        f"Consider running in tmux to prevent interruption on disconnect.\n"
        f"Use option [9] from main menu to launch in tmux session."
    )


# =============================================================================
# UNIFIED CONTROL CENTER
# =============================================================================

class SpiderFootControlCenter:
    """
    Unified control center for all SpiderFoot operations.

    Consolidates:
    - CLI batch scanning
    - Web GUI management
    - Database management
    - Scan monitoring with ETA
    - Stuck scan detection
    """

    def __init__(
        self,
        sf_path: str,
        sf_python: str,
        output_dir: str,
        config_loader: Callable,
        config_saver: Callable
    ):
        self.sf_path = sf_path
        self.sf_python = sf_python
        self.output_dir = output_dir
        self.load_config = config_loader
        self.save_config = config_saver

        self.eta_tracker = ETATracker()
        self.stuck_detector = StuckScanDetector()
        self.job_tracker = JobTracker()
        self.scanner: Optional[SpiderFootScanner] = None

        self._current_preset: Optional[IntensityPreset] = None

    def get_status(self) -> Dict:
        """Get comprehensive status of SpiderFoot operations"""
        status = {
            'sf_path': self.sf_path,
            'sf_python': self.sf_python,
            'output_dir': self.output_dir,
            'sf_installed': os.path.exists(self.sf_path),
            'db_path': None,
            'db_size': None,
            'db_scans': {},
            'queue_stats': self.job_tracker.get_stats(),
            'current_preset': self._current_preset.name if self._current_preset else None,
            'eta': self.eta_tracker.get_progress_string() if self.eta_tracker.total_scans > 0 else None,
            'stuck_warning': self.stuck_detector.get_stuck_warning(),
            'in_tmux': is_in_tmux(),
        }

        # Database info
        if status['sf_installed']:
            db_path = find_spiderfoot_db(self.sf_path)
            if db_path:
                status['db_path'] = db_path
                status['db_size'] = get_db_size(db_path)
                status['db_scans'] = count_db_scans(db_path)

        return status

    def select_intensity(self, preset_key: str) -> IntensityPreset:
        """Select an intensity preset"""
        if preset_key not in INTENSITY_PRESETS:
            preset_key = 'moderate'
        self._current_preset = INTENSITY_PRESETS[preset_key]
        return self._current_preset

    def configure_custom_preset(
        self,
        timeout_minutes: int,
        parallel_scans: int,
        modules: Optional[str] = None
    ) -> IntensityPreset:
        """Configure custom intensity preset"""
        preset = IntensityPreset(
            name='Custom',
            description=f'Custom: {timeout_minutes}m timeout, {parallel_scans} parallel',
            timeout_seconds=timeout_minutes * 60,
            modules=modules,
            parallel_scans=parallel_scans,
            estimated_time_per_domain=timeout_minutes * 60 // 2,  # Rough estimate
            color='magenta'
        )
        self._current_preset = preset
        return preset

    def start_batch_scan(
        self,
        domains: List[str],
        preset: Optional[IntensityPreset] = None,
        on_scan_start: Optional[Callable] = None,
        on_scan_complete: Optional[Callable] = None,
        on_scan_failed: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
        background: bool = False
    ) -> Dict:
        """
        Start a batch scan with the selected preset.

        Returns:
            Summary dict with completed/failed/total counts
        """
        if preset is None:
            preset = self._current_preset or INTENSITY_PRESETS['moderate']

        # Initialize tracking
        self.eta_tracker.start(len(domains), preset.parallel_scans)

        # Create scanner with timeout and modules from preset
        self.scanner = SpiderFootScanner(
            spiderfoot_path=self.sf_path,
            output_dir=self.output_dir,
            max_parallel=preset.parallel_scans,
            job_tracker=self.job_tracker,
            spiderfoot_python=self.sf_python,
            timeout_seconds=preset.timeout_seconds,
            modules=preset.modules
        )

        # Add domains
        added = self.scanner.add_domains(domains)

        # Wrap callbacks to add tracking
        original_on_start = on_scan_start
        original_on_complete = on_scan_complete

        def tracked_on_start(domain):
            self.stuck_detector.scan_started(domain)
            if original_on_start:
                original_on_start(domain)

        def tracked_on_complete(domain, csv_path):
            # Calculate duration
            if domain in self.stuck_detector.scan_start_times:
                start = self.stuck_detector.scan_start_times[domain]
                duration = (datetime.now() - start).total_seconds()
                self.eta_tracker.record_completion(duration)
                self.stuck_detector.scan_completed(domain, duration)
            if original_on_complete:
                original_on_complete(domain, csv_path)

        self.scanner.on_scan_start = tracked_on_start
        self.scanner.on_scan_complete = tracked_on_complete
        self.scanner.on_scan_failed = on_scan_failed
        self.scanner.on_progress = on_progress

        if background:
            # Return immediately, scan runs in background
            thread = threading.Thread(
                target=self.scanner.process_queue,
                daemon=True
            )
            thread.start()
            return {'started': True, 'total': len(domains), 'thread': thread}
        else:
            # Run synchronously
            return self.scanner.process_queue()

    def reset_database(self, backup: bool = True) -> Tuple[bool, str]:
        """Reset the SpiderFoot database"""
        # First, kill any running SpiderFoot processes
        killed = kill_spiderfoot_processes()
        time.sleep(1)  # Give processes time to die

        # Then delete the database
        success, msg = reset_spiderfoot_db(self.sf_path, backup=backup)

        if killed > 0:
            msg = f"Killed {killed} SpiderFoot process(es).\n" + msg

        return success, msg

    def launch_web_gui(self, port: int = 5001) -> Tuple[bool, str, Optional[str]]:
        """
        Launch SpiderFoot web GUI.

        Returns:
            (success, message, url)
        """
        # Check if port is in use
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) == 0:
                return False, f"Port {port} is already in use", None

        # Get SpiderFoot directory
        sf_dir = Path(self.sf_path).parent

        # Check if in tmux
        if is_in_tmux():
            # Create new tmux window - use shlex.quote for safety
            safe_cmd = f'cd {shlex.quote(str(sf_dir))} && {shlex.quote(self.sf_python)} sf.py -l 127.0.0.1:{port}'
            subprocess.run([
                'tmux', 'new-window', '-n', 'spiderfoot-gui', safe_cmd
            ])
            return True, f"SpiderFoot GUI launched in new tmux window", f"http://127.0.0.1:{port}"
        else:
            # Run in background - use argument list instead of shell=True
            subprocess.Popen(
                [self.sf_python, str(sf_dir / 'sf.py'), '-l', f'127.0.0.1:{port}'],
                cwd=str(sf_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return True, "SpiderFoot GUI launched in background", f"http://127.0.0.1:{port}"

    def get_tmux_warning(self, num_domains: int) -> Optional[str]:
        """Get tmux warning if applicable"""
        preset = self._current_preset or INTENSITY_PRESETS['moderate']
        return get_tmux_warning(num_domains, preset)

    def abort_stuck_scans(self) -> int:
        """Abort scans that appear to be stuck. Returns count of aborted scans."""
        stuck = self.stuck_detector.get_stuck_scans()
        aborted = 0

        for domain, _, _ in stuck:
            # Find and kill the process for this domain
            safe_domain = sanitize_for_pgrep(domain)
            if not safe_domain:
                continue  # Skip unsafe domain names
            try:
                result = subprocess.run(
                    ['pgrep', '-f', f'sf.py.*{safe_domain}'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    for pid in result.stdout.strip().split('\n'):
                        if pid:
                            subprocess.run(['kill', '-9', pid], capture_output=True)
                            aborted += 1
            except Exception:
                pass

            # Update job tracker
            job = self.job_tracker.get_job(domain)
            if job:
                job.mark_failed("Aborted - detected as stuck")
                self.job_tracker.save_state()

        return aborted


# =============================================================================
# MENU HELPERS
# =============================================================================

def format_preset_option(key: str, preset: IntensityPreset, selected: bool = False) -> str:
    """Format a preset option for display"""
    indicator = ">" if selected else " "
    timeout_str = f"{preset.timeout_seconds // 60}m" if preset.timeout_seconds < 3600 else f"{preset.timeout_seconds // 3600}h"
    return f"{indicator}[{key.upper()}] {preset.name} - {timeout_str} timeout, {preset.parallel_scans} parallel - {preset.description}"


def format_status_panel(status: Dict) -> str:
    """Format status dict as a display panel"""
    lines = []

    # SpiderFoot status
    if status['sf_installed']:
        lines.append(f"SpiderFoot: INSTALLED")
        lines.append(f"  Path: {status['sf_path']}")
    else:
        lines.append(f"SpiderFoot: NOT INSTALLED")

    # Database status
    if status['db_path']:
        lines.append(f"Database: {status['db_size']}")
        scans = status['db_scans']
        lines.append(f"  Scans: {scans.get('total', 0)} total, "
                    f"{scans.get('running', 0)} running, "
                    f"{scans.get('finished', 0)} finished")

    # Queue status
    q = status['queue_stats']
    lines.append(f"Queue: {q['total']} total ({q['pending']} pending, "
                f"{q['running']} running, {q['completed']} done)")

    # ETA
    if status['eta']:
        lines.append(f"Progress: {status['eta']}")

    # Stuck warning
    if status['stuck_warning']:
        lines.append(f"WARNING: {status['stuck_warning']}")

    # tmux status
    lines.append(f"tmux: {'Active' if status['in_tmux'] else 'Not in tmux'}")

    return "\n".join(lines)
