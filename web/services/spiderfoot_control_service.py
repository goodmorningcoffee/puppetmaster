"""
spiderfoot_control_service.py - Web GUI wrapper around discovery.spiderfoot_control.

Wraps the lower-level callable APIs in:
  - discovery.spiderfoot_control (presets, DB reset, kill, status helpers)
  - discovery.scanner.SpiderFootScanner (batch scanning with callbacks)
  - discovery.jobs.JobTracker (queue persistence)

Does NOT import from pm_spiderfoot.py — those functions are interactive TUI
menus, not web-safe. We go one level deeper to the pure callable layer.

This is the FIRST web/services module to use subprocess.Popen — used by
start_spiderfoot_server() to launch the SpiderFoot CLI as a detached
background process.
"""

import os
import socket
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import run_state


# SpiderFoot's actual usecase presets, as documented in
# discovery/spiderfoot_api.py:185 and discovery/distributed.py:2849-2855.
# These map to SpiderFoot's `-u {usecase}` CLI flag.
SPIDERFOOT_USECASES: Dict[str, str] = {
    'all':         "All modules — full scan, slowest and most thorough",
    'footprint':   "Modules that gather footprint information",
    'investigate': "Modules for investigating a specific entity",
    'passive':     "Only passive modules — no active scanning",
}


def _load_sf_config() -> Dict[str, Any]:
    """
    Return the SpiderFoot-related config keys.

    Safe against missing pm_config (returns empty dict). Keys returned:
      sf_path: str or None
      sf_python: str or None
      output_dir: str (default './spiderfoot_exports')
    """
    try:
        from pm_config import load_config
        cfg = load_config()
    except Exception:
        cfg = {}
    return {
        'sf_path': cfg.get('spiderfoot_path'),
        'sf_python': cfg.get('spiderfoot_python'),
        'output_dir': cfg.get('spiderfoot_output_dir', './spiderfoot_exports'),
    }


def get_spiderfoot_status() -> Dict[str, Any]:
    """
    Return a comprehensive status snapshot for the Control Center hub.

    Safe against:
      - SpiderFoot not installed (sf_installed=False)
      - discovery.spiderfoot_control unavailable (error field set)
      - DB missing (db_path=None)
      - port check failing (gui_running=False)

    Always returns a complete dict — never raises.
    """
    sf_cfg = _load_sf_config()
    sf_path = sf_cfg['sf_path']

    status: Dict[str, Any] = {
        'sf_path': sf_path,
        'sf_python': sf_cfg['sf_python'],
        'output_dir': sf_cfg['output_dir'],
        'sf_installed': False,
        'db_path': None,
        'db_size': None,
        'db_scans': {},
        'gui_running': False,
        'gui_port': 5001,
        'in_tmux': False,
        'error': None,
    }

    if sf_path and os.path.exists(sf_path):
        status['sf_installed'] = True

    # Defer the import — discovery layer may be missing in minimal installs
    try:
        from discovery.spiderfoot_control import (
            find_spiderfoot_db,
            get_db_size,
            count_db_scans,
            is_in_tmux,
        )
    except ImportError as e:
        status['error'] = f"discovery.spiderfoot_control not available: {e}"
        return status

    try:
        status['in_tmux'] = is_in_tmux()
    except Exception:
        pass

    if status['sf_installed']:
        try:
            db_path = find_spiderfoot_db(sf_path)
            if db_path:
                status['db_path'] = db_path
                status['db_size'] = get_db_size(db_path)
                status['db_scans'] = count_db_scans(db_path)
        except Exception as e:
            status['error'] = f"DB inspection failed: {e}"

    # Is SpiderFoot's web GUI already listening on port 5001?
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            status['gui_running'] = s.connect_ex(('127.0.0.1', 5001)) == 0
    except Exception:
        status['gui_running'] = False

    return status


def reset_spiderfoot_database(backup: bool = True) -> Tuple[bool, str]:
    """Wraps discovery.spiderfoot_control.reset_spiderfoot_db with config lookup."""
    sf_cfg = _load_sf_config()
    sf_path = sf_cfg['sf_path']
    if not sf_path:
        return False, "SpiderFoot is not installed or not configured."
    if not os.path.exists(sf_path):
        return False, f"SpiderFoot path is invalid: {sf_path}"
    try:
        from discovery.spiderfoot_control import reset_spiderfoot_db
    except ImportError:
        return False, "discovery.spiderfoot_control module not available."
    try:
        return reset_spiderfoot_db(sf_path, backup=backup)
    except Exception as e:
        return False, f"Reset failed: {e}"


def kill_spiderfoot() -> int:
    """Wraps discovery.spiderfoot_control.kill_spiderfoot_processes."""
    try:
        from discovery.spiderfoot_control import kill_spiderfoot_processes
    except ImportError:
        return 0
    try:
        return kill_spiderfoot_processes()
    except Exception:
        return 0


def start_spiderfoot_server(port: int = 5001) -> Tuple[bool, str]:
    """
    Launch SpiderFoot's web GUI as a detached background process.

    Uses subprocess.Popen with start_new_session=True so the child outlives
    this Flask request. Does NOT wait for the port to bind — returns
    immediately with a success message. The caller refreshes the hub,
    which will pick up the new port state via get_spiderfoot_status().

    Pre-checks the port — if something is already listening, returns a
    friendly error instead of spawning a doomed second process.
    """
    sf_cfg = _load_sf_config()
    sf_path = sf_cfg['sf_path']
    sf_python = sf_cfg['sf_python']

    if not sf_path or not os.path.exists(sf_path):
        return False, (
            "SpiderFoot is not installed. Use the TUI ([I] Install SpiderFoot) "
            "to install it first."
        )

    # Fall back to system python if no venv python configured
    if not sf_python or not os.path.exists(sf_python):
        sf_python = 'python3'

    # Pre-check the port
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                return False, (
                    f"Port {port} is already in use. SpiderFoot may already "
                    f"be running — click [G] Open in new tab."
                )
    except Exception:
        pass

    sf_dir = str(Path(sf_path).parent)
    try:
        subprocess.Popen(
            [sf_python, sf_path, '-l', f'127.0.0.1:{port}'],
            cwd=sf_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except (OSError, FileNotFoundError) as e:
        return False, f"Failed to launch SpiderFoot: {e}"

    return True, (
        f"SpiderFoot GUI launched on port {port}. "
        f"Click [G] Open in new tab in a few seconds."
    )


def start_batch_scan_in_background(
    usecase: str = 'all',
    timeout_seconds: int = 1800,
    max_parallel: int = 3,
) -> str:
    """
    Start a SpiderFoot batch scan in a background daemon thread.

    Mirrors web/services/scrape_service.py:start_scrape_in_background pattern.

    Returns a run_id that the caller redirects to for the progress page.

    On fast-fail paths (missing SpiderFoot, empty queue, duplicate scan,
    bad usecase), the run is created AND immediately marked failed — the
    UI will show the error on the progress page.
    """
    run_id = run_state.create_run('spiderfoot_scan')

    # Validate usecase
    if usecase not in SPIDERFOOT_USECASES:
        usecase = 'all'

    # Duplicate scan prevention
    existing = run_state.has_running_run_of_kind('spiderfoot_scan')
    if existing and existing != run_id:
        run_state.mark_failed(
            run_id,
            f"Another batch scan is already running ({existing}). "
            f"Wait for it to finish or kill SpiderFoot processes from the hub."
        )
        return run_id

    sf_cfg = _load_sf_config()
    sf_path = sf_cfg['sf_path']
    sf_python = sf_cfg['sf_python']
    output_dir = sf_cfg['output_dir']

    if not sf_path or not os.path.exists(sf_path):
        run_state.mark_failed(run_id, "SpiderFoot is not installed or not configured.")
        return run_id

    # Defer heavy imports
    try:
        from discovery.scanner import SpiderFootScanner
        from discovery.jobs import JobTracker
    except ImportError as e:
        run_state.mark_failed(run_id, f"discovery modules not available: {e}")
        return run_id

    # Pull pending domains from JobTracker (the committed scan queue)
    try:
        tracker = JobTracker()
        pending_jobs = tracker.get_pending()
        pending_domains: List[str] = [j.domain for j in pending_jobs]
    except Exception as e:
        run_state.mark_failed(run_id, f"Failed to read job tracker: {e}")
        return run_id

    if not pending_domains:
        run_state.mark_failed(
            run_id,
            "No domains in the scan queue. "
            "Commit domains first via [12] Domain Queue Manager."
        )
        return run_id

    run_state.append_event(
        run_id, 'info',
        f"Usecase: {usecase} | {len(pending_domains)} domain(s) | "
        f"{max_parallel} parallel | {timeout_seconds // 60}m timeout per scan",
        stage='Initializing',
        total=len(pending_domains),
        usecase=usecase,
    )

    def _runner():
        try:
            scanner = SpiderFootScanner(
                spiderfoot_path=sf_path,
                output_dir=output_dir,
                max_parallel=max_parallel,
                job_tracker=tracker,
                spiderfoot_python=sf_python,
                timeout_seconds=timeout_seconds,
                modules=None,
                usecase=usecase,
            )

            def on_scan_start(domain: str):
                run_state.append_event(
                    run_id, 'stage',
                    f"Starting scan: {domain}",
                    domain=domain,
                    stage='Scanning',
                )

            def on_scan_complete(domain: str, csv_path: str):
                run_state.append_event(
                    run_id, 'success',
                    f"Completed: {domain} -> {os.path.basename(csv_path)}",
                    domain=domain,
                    csv_path=csv_path,
                )

            def on_scan_failed(domain: str, error: str):
                run_state.append_event(
                    run_id, 'error',
                    f"Failed: {domain} - {error}",
                    domain=domain,
                    error=error,
                )

            def on_progress(completed: int, failed: int, total: int):
                pct = int((completed + failed) / total * 100) if total > 0 else 0
                run_state.append_event(
                    run_id, 'progress',
                    f"{completed + failed}/{total} ({pct}%) — "
                    f"{completed} done, {failed} failed",
                    completed=completed,
                    failed=failed,
                    total=total,
                    progress=pct,
                )

            scanner.on_scan_start = on_scan_start
            scanner.on_scan_complete = on_scan_complete
            scanner.on_scan_failed = on_scan_failed
            scanner.on_progress = on_progress
            # Skip on_module_progress — fires 20-80x per domain, would
            # flood the 1000-event run_state cap.

            run_state.append_event(
                run_id, 'stage',
                'Processing scan queue...',
                stage='Processing',
            )

            # The tracker passed to the scanner already contains the pending
            # domains. Do NOT call scanner.add_domains() — that would add them
            # again as duplicates.
            result = scanner.process_queue()  # blocks until done

            # Snapshot final tracker state for the result page.
            # Filter by domain set rather than slicing by count: get_completed
            # / get_failed return jobs in dict insertion order, not completion
            # order, so a count-based slice could mix in unrelated old jobs.
            jobs_snapshot: List[Dict[str, Any]] = []
            try:
                pending_set = set(pending_domains)
                for j in tracker.get_completed():
                    if getattr(j, 'domain', '') in pending_set:
                        jobs_snapshot.append({
                            'domain': getattr(j, 'domain', ''),
                            'status': 'completed',
                            'csv_path': getattr(j, 'csv_path', None),
                            'error': None,
                        })
                for j in tracker.get_failed():
                    if getattr(j, 'domain', '') in pending_set:
                        jobs_snapshot.append({
                            'domain': getattr(j, 'domain', ''),
                            'status': 'failed',
                            'csv_path': None,
                            'error': getattr(j, 'error', None),
                        })
            except Exception:
                pass

            run_state.mark_complete(run_id, {
                'completed': result.get('completed', 0),
                'failed': result.get('failed', 0),
                'total': result.get('total', len(pending_domains)),
                'jobs': jobs_snapshot,
                'usecase': usecase,
            })

        except Exception as e:
            run_state.append_event(run_id, 'error', f"Batch scan crashed: {e}")
            run_state.mark_failed(run_id, str(e))

    thread = threading.Thread(
        target=_runner,
        name=f"web-sf-scan-{run_id}",
        daemon=True,
    )
    thread.start()
    return run_id
