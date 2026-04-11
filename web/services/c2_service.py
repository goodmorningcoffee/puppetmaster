"""
c2_service.py - Web GUI wrapper around the Distributed C2 Controller.

Wraps the lower-level callable APIs in:
  - discovery.worker_config.DistributedConfigManager (worker CRUD, no SSH needed)
  - discovery.distributed.create_controller / DistributedScanController
    (validate / detect / setup — all SSH-dependent)

Does NOT import from pm_c2.py — those functions are interactive TUI menus,
not web-safe. We go one level deeper to the pure callable layer.

Worker CRUD works without SSH keys loaded. The three async operations
(validate, detect, setup) require SSH agent keys or a configured key file
and will fail fast via catching ValueError from create_controller().
"""

import threading
from typing import Any, Dict, List, Optional, Tuple

from . import run_state


# Run kinds used in run_state for duplicate prevention.
# Phase 4 Commit 2b will add 'c2_scan' and 'c2_collect' — the duplicate check
# already scans all kinds in this tuple so 2b can extend it without touching
# the logic.
C2_RUN_KINDS: Tuple[str, ...] = ('c2_validate', 'c2_detect', 'c2_setup')


# =============================================================================
# SYNCHRONOUS HELPERS (called from routes)
# =============================================================================


def _get_config_manager():
    """
    Construct a DistributedConfigManager. Never fails — returns None on import
    error so the hub can still render with a friendly message.
    """
    try:
        from discovery.worker_config import DistributedConfigManager
        return DistributedConfigManager()
    except Exception:
        return None


def get_ssh_status() -> Dict[str, Any]:
    """
    Ground-truth SSH readiness check.

    Lazily attempts create_controller() and catches the ValueError it raises
    when SSH keys are unavailable. This is literally the same check each
    action endpoint does at the top of its _runner(), so the hub reflects
    exactly what will happen when the user clicks an action button.

    Returns a dict with:
      ready:       bool — True if controller construction succeeded
      mode:        'agent' or 'keyfile'
      error:       str or None — the caught ValueError message if not ready
      remediation: str or None — copy-paste hint to fix the error

    NEVER returns ssh_key_path or any other secret.
    """
    manager = _get_config_manager()
    if manager is None:
        return {
            'ready': False,
            'mode': 'unknown',
            'error': 'discovery.worker_config module not available.',
            'remediation': None,
        }

    mode = 'agent' if manager.config.use_ssh_agent else 'keyfile'

    try:
        from discovery.distributed import create_controller
        create_controller()
    except ValueError as e:
        return {
            'ready': False,
            'mode': mode,
            'error': str(e),
            'remediation': (
                'ssh-add ~/.ssh/your-key.pem'
                if mode == 'agent'
                else 'Set a valid SSH key path via the TUI configuration menu.'
            ),
        }
    except ImportError as e:
        return {
            'ready': False,
            'mode': mode,
            'error': f'discovery.distributed module not available: {e}',
            'remediation': None,
        }
    except Exception as e:
        return {
            'ready': False,
            'mode': mode,
            'error': f'Unexpected error: {e}',
            'remediation': None,
        }

    return {
        'ready': True,
        'mode': mode,
        'error': None,
        'remediation': None,
    }


def _serialize_worker(w) -> Dict[str, Any]:
    """Plain-dict snapshot of a WorkerConfig. No secrets."""
    return {
        'hostname': w.hostname,
        'display_name': w.get_display_name(),
        'username': w.username,
        'enabled': w.enabled,
        'nickname': w.nickname,
        'status': w.status,
        'last_seen': w.last_seen,
        'spiderfoot_installed': w.spiderfoot_installed,
        'tmux_installed': w.tmux_installed,
        'ram_gb': w.ram_gb,
        'cpu_cores': w.cpu_cores,
        'recommended_parallel': w.recommended_parallel,
        'resource_summary': w.get_resource_summary(),
        'gui_port': w.gui_port,
    }


def get_c2_snapshot() -> Dict[str, Any]:
    """
    Build the full payload for the C2 hub page.

    Safe against every common failure mode — never raises. If the config
    module is missing, returns a minimal dict with an 'error' key that
    the template can surface.
    """
    manager = _get_config_manager()
    if manager is None:
        return {
            'workers': [],
            'stats': {},
            'ssh_status': get_ssh_status(),
            'config_summary': {},
            'active_session': None,
            'error': 'discovery.worker_config module not available.',
        }

    workers = [_serialize_worker(w) for w in manager.get_all_workers()]
    stats = manager.get_stats_summary()

    cfg = manager.config
    config_summary = {
        'scan_mode': cfg.scan_mode,
        'parallel_scans_per_worker': cfg.parallel_scans_per_worker,
        'hard_timeout_hours': cfg.hard_timeout_hours,
        'activity_timeout_minutes': cfg.activity_timeout_minutes,
        'default_intensity': cfg.default_intensity,
        'remote_work_dir': cfg.remote_work_dir,
        'spiderfoot_install_dir': cfg.spiderfoot_install_dir,
    }

    active_session = None
    if manager.has_active_session():
        active_session = {
            'session_id': cfg.current_session_id,
            'session_start': cfg.current_session_start,
            'total_domains': cfg.total_domains_in_session,
        }

    return {
        'workers': workers,
        'stats': stats,
        'ssh_status': get_ssh_status(),
        'config_summary': config_summary,
        'active_session': active_session,
        'error': None,
    }


def add_worker(
    hostname: str,
    username: str = 'kali',
    nickname: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Add a worker via DistributedConfigManager.add_worker().

    Catches ValueError (shell-unsafe input or duplicate hostname) and
    returns a user-friendly tuple. On success, returns a message naming
    the auto-assigned nickname so the user knows what it's called.
    """
    manager = _get_config_manager()
    if manager is None:
        return False, 'discovery.worker_config module not available.'

    try:
        worker = manager.add_worker(hostname, username=username, nickname=nickname)
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f'Failed to add worker: {e}'

    return True, (
        f'Added worker {worker.nickname} ({worker.hostname}) '
        f'as user {worker.username}.'
    )


def remove_worker(hostname: str) -> Tuple[bool, str]:
    """Remove a worker by hostname."""
    manager = _get_config_manager()
    if manager is None:
        return False, 'discovery.worker_config module not available.'

    try:
        ok = manager.remove_worker(hostname)
    except Exception as e:
        return False, f'Failed to remove worker: {e}'

    if not ok:
        return False, f'No worker with hostname "{hostname}".'
    return True, f'Removed worker {hostname}.'


def toggle_worker(hostname: str) -> Tuple[bool, str]:
    """
    Toggle a worker's enabled flag. Flips current state.
    """
    manager = _get_config_manager()
    if manager is None:
        return False, 'discovery.worker_config module not available.'

    worker = manager.get_worker(hostname)
    if worker is None:
        return False, f'No worker with hostname "{hostname}".'

    try:
        if worker.enabled:
            ok = manager.disable_worker(hostname)
            action = 'Disabled'
        else:
            ok = manager.enable_worker(hostname)
            action = 'Enabled'
    except Exception as e:
        return False, f'Failed to toggle worker: {e}'

    if not ok:
        return False, f'Failed to toggle worker {hostname}.'
    return True, f'{action} worker {hostname}.'


# =============================================================================
# ASYNC RUNNERS (background thread + run_state + SSE)
# =============================================================================


def _fail_fast_check(run_id: str, manager) -> bool:
    """
    Apply the shared fast-fail guards for all three async C2 ops.

    Returns True if the run should proceed, False if it has already been
    marked failed. Checks (in order): duplicate C2 op running, active scan
    session, no enabled workers.
    """
    for kind in C2_RUN_KINDS:
        existing = run_state.has_running_run_of_kind(kind)
        if existing and existing != run_id:
            run_state.mark_failed(
                run_id,
                f'Another C2 operation is already running '
                f'({kind}, id={existing}). Wait for it to finish.',
            )
            return False

    if manager.has_active_session():
        run_state.mark_failed(
            run_id,
            f'A distributed scan session is currently active '
            f'(session {manager.config.current_session_id}). '
            f'Worker management actions are disabled while a scan is in flight.',
        )
        return False

    if not manager.get_enabled_workers():
        run_state.mark_failed(
            run_id,
            'No enabled workers configured. '
            'Add a worker first via the C2 hub.',
        )
        return False

    return True


def _build_controller_or_fail(run_id: str):
    """
    Try to construct a DistributedScanController. Returns the controller
    or None if it fails (in which case the run is already marked failed).
    """
    try:
        from discovery.distributed import create_controller
        return create_controller()
    except ValueError as e:
        run_state.mark_failed(run_id, f'SSH not ready: {e}')
        return None
    except ImportError as e:
        run_state.mark_failed(run_id, f'discovery.distributed not available: {e}')
        return None
    except Exception as e:
        run_state.mark_failed(run_id, f'Failed to build controller: {e}')
        return None


def start_validate_in_background(
    hostnames: Optional[List[str]] = None,
) -> str:
    """
    Start background SSH connectivity validation for all enabled workers.

    Per-worker progress streams through run_state events. Each worker's
    final status is recorded in the result payload for the result page.

    Args:
        hostnames: Optional subset of hostnames to validate. None = all enabled.
                   (Service accepts this from day one so 2b can extend without
                   refactoring.)

    Returns:
        run_id for redirect-to-progress-page.
    """
    run_id = run_state.create_run('c2_validate')

    manager = _get_config_manager()
    if manager is None:
        run_state.mark_failed(run_id, 'discovery.worker_config not available.')
        return run_id

    if not _fail_fast_check(run_id, manager):
        return run_id

    all_workers = manager.get_enabled_workers()
    if hostnames:
        wanted = set(hostnames)
        selected_workers = [w for w in all_workers if w.hostname in wanted]
    else:
        selected_workers = all_workers

    if not selected_workers:
        run_state.mark_failed(run_id, 'No matching enabled workers to validate.')
        return run_id

    run_state.append_event(
        run_id, 'info',
        f'Validating {len(selected_workers)} worker(s)...',
        stage='Initializing',
        total=len(selected_workers),
    )

    def _runner():
        controller = _build_controller_or_fail(run_id)
        if controller is None:
            return

        def on_progress(hostname: str, status: str):
            level = 'progress'
            if 'OK' in status:
                level = 'success'
            elif 'FAILED' in status or 'FAIL' in status:
                level = 'error'
            run_state.append_event(
                run_id, level,
                f'{hostname}: {status}',
                hostname=hostname,
                status=status,
            )

        try:
            run_state.append_event(
                run_id, 'stage',
                'Opening SSH connections...',
                stage='Connecting',
            )
            results = controller.validate_workers(
                on_progress=on_progress,
                workers=selected_workers,
            )
        except Exception as e:
            run_state.append_event(run_id, 'error', f'Validation crashed: {e}')
            run_state.mark_failed(run_id, str(e))
            return

        serialized = {
            hostname: {
                'success': success,
                'message': message,
            }
            for hostname, (success, message) in results.items()
        }
        success_count = sum(1 for v in serialized.values() if v['success'])
        run_state.mark_complete(run_id, {
            'kind': 'c2_validate',
            'total': len(serialized),
            'success_count': success_count,
            'fail_count': len(serialized) - success_count,
            'results': serialized,
        })

    thread = threading.Thread(
        target=_runner,
        name=f'web-c2-validate-{run_id}',
        daemon=True,
    )
    thread.start()
    return run_id


def start_detect_resources_in_background(
    hostnames: Optional[List[str]] = None,
) -> str:
    """
    Start background resource detection (RAM/CPU) for all enabled workers.

    Results update each worker's ram_gb/cpu_cores/recommended_parallel
    in the persisted config as a side effect of detect_all_resources().
    """
    run_id = run_state.create_run('c2_detect')

    manager = _get_config_manager()
    if manager is None:
        run_state.mark_failed(run_id, 'discovery.worker_config not available.')
        return run_id

    if not _fail_fast_check(run_id, manager):
        return run_id

    all_workers = manager.get_enabled_workers()
    if hostnames:
        wanted = set(hostnames)
        selected_workers = [w for w in all_workers if w.hostname in wanted]
    else:
        selected_workers = all_workers

    if not selected_workers:
        run_state.mark_failed(run_id, 'No matching enabled workers to detect.')
        return run_id

    run_state.append_event(
        run_id, 'info',
        f'Detecting resources on {len(selected_workers)} worker(s)...',
        stage='Initializing',
        total=len(selected_workers),
    )

    def _runner():
        controller = _build_controller_or_fail(run_id)
        if controller is None:
            return

        def on_progress(hostname: str, status: str):
            run_state.append_event(
                run_id, 'progress',
                f'{hostname}: {status}',
                hostname=hostname,
                status=status,
            )

        try:
            run_state.append_event(
                run_id, 'stage',
                'Probing worker resources via SSH...',
                stage='Detecting',
            )
            results = controller.detect_all_resources(
                on_progress=on_progress,
                workers=selected_workers,
            )
        except Exception as e:
            run_state.append_event(run_id, 'error', f'Detection crashed: {e}')
            run_state.mark_failed(run_id, str(e))
            return

        serialized = {}
        for hostname, (ram, cpu, rec) in results.items():
            serialized[hostname] = {
                'ram_gb': ram,
                'cpu_cores': cpu,
                'recommended_parallel': rec,
                'detected': ram is not None and cpu is not None,
            }
        detected_count = sum(1 for v in serialized.values() if v['detected'])
        run_state.mark_complete(run_id, {
            'kind': 'c2_detect',
            'total': len(serialized),
            'detected_count': detected_count,
            'results': serialized,
        })

    thread = threading.Thread(
        target=_runner,
        name=f'web-c2-detect-{run_id}',
        daemon=True,
    )
    thread.start()
    return run_id


def start_setup_in_background(
    hostnames: Optional[List[str]] = None,
) -> str:
    """
    Start background worker setup (apt update, tmux, SpiderFoot install).

    This is sequential and can take 10+ minutes per worker on cold hosts.
    We emit a [i/N] heartbeat at each worker boundary so the user sees
    progress even if installer is silent for minutes.
    """
    run_id = run_state.create_run('c2_setup')

    manager = _get_config_manager()
    if manager is None:
        run_state.mark_failed(run_id, 'discovery.worker_config not available.')
        return run_id

    if not _fail_fast_check(run_id, manager):
        return run_id

    all_workers = manager.get_enabled_workers()
    if hostnames:
        wanted = set(hostnames)
        selected_workers = [w for w in all_workers if w.hostname in wanted]
    else:
        selected_workers = all_workers

    if not selected_workers:
        run_state.mark_failed(run_id, 'No matching enabled workers to set up.')
        return run_id

    total = len(selected_workers)
    run_state.append_event(
        run_id, 'info',
        f'Setting up {total} worker(s) sequentially. This may take '
        f'several minutes per worker on cold hosts.',
        stage='Initializing',
        total=total,
    )

    def _runner():
        controller = _build_controller_or_fail(run_id)
        if controller is None:
            return

        # Heartbeat state: track which worker boundary we're on. The installer
        # emits progress strings but doesn't include worker indices, so we
        # wrap our own counter around each worker in the sequential loop.
        # However, setup_all_workers takes the workers list and iterates
        # internally, so we can't easily inject per-worker heartbeats from
        # outside. Solution: stream installer's raw on_progress(msg) events
        # verbatim, and rely on the installer's own "Setting up {name}..."
        # message as the boundary marker.
        def on_progress(msg: str):
            run_state.append_event(
                run_id, 'stage',
                msg,
                stage='Setup',
            )

        try:
            run_state.append_event(
                run_id, 'stage',
                'Beginning sequential worker setup...',
                stage='Setup',
            )
            results = controller.setup_all_workers(
                on_progress=on_progress,
                workers=selected_workers,
            )
        except Exception as e:
            run_state.append_event(run_id, 'error', f'Setup crashed: {e}')
            run_state.mark_failed(run_id, str(e))
            return

        # WorkerSetupResult is a dataclass — serialize to plain dict.
        serialized = {}
        for hostname, result in results.items():
            serialized[hostname] = {
                'hostname': result.hostname,
                'success': result.success,
                'tmux_installed': result.tmux_installed,
                'spiderfoot_installed': result.spiderfoot_installed,
                'apt_updated': result.apt_updated,
                'error_message': result.error_message,
            }
        success_count = sum(1 for v in serialized.values() if v['success'])
        run_state.mark_complete(run_id, {
            'kind': 'c2_setup',
            'total': len(serialized),
            'success_count': success_count,
            'fail_count': len(serialized) - success_count,
            'results': serialized,
        })

    thread = threading.Thread(
        target=_runner,
        name=f'web-c2-setup-{run_id}',
        daemon=True,
    )
    thread.start()
    return run_id
