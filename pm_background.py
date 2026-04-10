"""
pm_background.py - Background Scan State Management

Thread-safe state tracking for background SpiderFoot scans.
"""

import threading
from datetime import datetime


# =============================================================================
# GLOBAL STATE
# =============================================================================
_background_scan_thread = None
_background_scan_stop = threading.Event()
_background_scan_stats = {
    'running': False,
    'completed': 0,
    'failed': 0,
    'total': 0,
    'current_domain': None,
    'start_time': None,
    # Module-level progress
    'current_module': None,
    'results_found': 0,
    'file_size_kb': 0.0,
}
_background_scan_lock = threading.Lock()


# =============================================================================
# ACCESSORS (thread-safe)
# =============================================================================

def is_background_scan_running():
    """Check if a background scan is currently running"""
    with _background_scan_lock:
        return _background_scan_stats['running']


def get_background_scan_stats():
    """Get current background scan statistics"""
    with _background_scan_lock:
        return dict(_background_scan_stats)


def _update_background_stats(**kwargs):
    """Update background scan statistics"""
    with _background_scan_lock:
        _background_scan_stats.update(kwargs)


# =============================================================================
# THREAD MANAGEMENT
# =============================================================================

def start_background_thread(target, args):
    """Start a background scan thread (encapsulates global mutation)."""
    global _background_scan_thread
    _background_scan_stop.clear()
    _background_scan_thread = threading.Thread(target=target, args=args, daemon=True)
    _background_scan_thread.start()


def stop_background_thread(timeout=5):
    """Signal background thread to stop and optionally wait."""
    _background_scan_stop.set()
    if _background_scan_thread and _background_scan_thread.is_alive():
        _background_scan_thread.join(timeout=timeout)


# =============================================================================
# BACKGROUND SCAN RUNNER
# =============================================================================

def _run_background_scans(scanner, tracker):
    """Run scans in background thread"""
    global _background_scan_stats

    def on_start(domain):
        # Check if stop was requested between domains
        if _background_scan_stop.is_set():
            scanner._stop_requested = True
            return
        _update_background_stats(
            current_domain=domain,
            current_module=None,
            results_found=0,
            file_size_kb=0.0
        )

    def on_complete(domain, csv_path):
        with _background_scan_lock:
            _background_scan_stats['completed'] += 1

    def on_failed(domain, error):
        with _background_scan_lock:
            _background_scan_stats['failed'] += 1

    def on_progress(completed, failed, total):
        _update_background_stats(completed=completed, failed=failed, total=total)

    def on_module_progress(domain, module, results_count, file_size_kb):
        """Real-time module-level progress from SpiderFoot"""
        _update_background_stats(
            current_module=module,
            results_found=results_count,
            file_size_kb=file_size_kb
        )

    scanner.on_scan_start = on_start
    scanner.on_scan_complete = on_complete
    scanner.on_scan_failed = on_failed
    scanner.on_progress = on_progress
    scanner.on_module_progress = on_module_progress

    try:
        scanner.process_queue(progress_callback=on_progress)
    except Exception as e:
        print(f"  [ERROR] Background scan error: {e}")
    finally:
        _update_background_stats(running=False, current_domain=None, current_module=None)


def get_elapsed_time_str():
    """Get formatted elapsed time for background scan"""
    stats = get_background_scan_stats()
    start_time = stats.get('start_time')
    if not start_time:
        return "N/A"
    try:
        start = datetime.fromisoformat(start_time)
        elapsed = datetime.now() - start
        total_seconds = int(elapsed.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception:
        return "N/A"
