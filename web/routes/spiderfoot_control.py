"""
spiderfoot_control.py - SpiderFoot Control Center routes (Phase 4 Commit 1).

Wires up main menu option [3]. The hub at /menu/spiderfoot is a multi-action
page (queue.py-style) with three inline POST actions (start GUI, reset DB,
kill processes) and outbound nav to the multi-page batch scan flow and the
existing scan status screen.

Routes:
  GET  /menu/spiderfoot                          — hub page
  POST /menu/spiderfoot/start-gui                — launch SpiderFoot's web GUI
  POST /menu/spiderfoot/reset-db                 — reset DB (with backup)
  POST /menu/spiderfoot/kill                     — kill SpiderFoot processes
  GET  /menu/spiderfoot/scan                     — batch scan form
  POST /menu/spiderfoot/scan/run                 — start batch scan, redirect to progress
  GET  /menu/spiderfoot/scan/progress/<run_id>   — live progress (SSE-driven)
  GET  /menu/spiderfoot/scan/result/<run_id>     — final summary
"""

from flask import Blueprint, abort, redirect, render_template, request, url_for

from ..services import run_state
from ..services.queue_service import get_queue_snapshot
from ..services.spiderfoot_control_service import (
    SPIDERFOOT_USECASES,
    get_spiderfoot_status,
    kill_spiderfoot,
    reset_spiderfoot_database,
    start_batch_scan_in_background,
    start_spiderfoot_server,
)


bp = Blueprint('spiderfoot_control', __name__)


def _render_hub(message=None):
    """Render the hub page with optional flash message tuple (level, text)."""
    snapshot = get_queue_snapshot(max_per_status=0)
    return render_template(
        'spiderfoot_control.html',
        status=get_spiderfoot_status(),
        pending_count=snapshot['stats'].get('pending', 0),
        message=message,
    )


@bp.route('/menu/spiderfoot')
def spiderfoot_hub():
    """SpiderFoot Control Center hub."""
    return _render_hub()


@bp.route('/menu/spiderfoot/start-gui', methods=['POST'])
def start_gui():
    """Launch SpiderFoot's web GUI as a detached background process."""
    ok, msg = start_spiderfoot_server()
    level = "success" if ok else "error"
    return _render_hub(message=(level, msg))


@bp.route('/menu/spiderfoot/reset-db', methods=['POST'])
def reset_db():
    """Reset the SpiderFoot database (with timestamped backup)."""
    ok, msg = reset_spiderfoot_database(backup=True)
    level = "success" if ok else "error"
    return _render_hub(message=(level, msg))


@bp.route('/menu/spiderfoot/kill', methods=['POST'])
def kill_processes():
    """Kill all running SpiderFoot processes."""
    count = kill_spiderfoot()
    if count > 0:
        return _render_hub(message=("success", f"Killed {count} SpiderFoot process(es)."))
    return _render_hub(message=("info", "No SpiderFoot processes were running."))


@bp.route('/menu/spiderfoot/scan')
def scan_form():
    """Show the batch scan configuration form."""
    snapshot = get_queue_snapshot(max_per_status=20)
    return render_template(
        'spiderfoot_scan_form.html',
        status=get_spiderfoot_status(),
        usecases=SPIDERFOOT_USECASES,
        pending_count=snapshot['stats'].get('pending', 0),
        pending_domains=snapshot.get('pending', []),
    )


@bp.route('/menu/spiderfoot/scan/run', methods=['POST'])
def scan_run():
    """Start a batch scan in the background, redirect to progress page."""
    usecase = request.form.get('usecase', 'all').strip()
    if usecase not in SPIDERFOOT_USECASES:
        usecase = 'all'

    run_id = start_batch_scan_in_background(usecase=usecase)
    return redirect(url_for('spiderfoot_control.scan_progress', run_id=run_id))


@bp.route('/menu/spiderfoot/scan/progress/<run_id>')
def scan_progress(run_id: str):
    """Show the live SSE progress page for an in-flight batch scan."""
    run = run_state.get_run(run_id)
    if run is None:
        abort(404)
    return render_template('spiderfoot_scan_progress.html', run_id=run_id, run=run)


@bp.route('/menu/spiderfoot/scan/result/<run_id>')
def scan_result(run_id: str):
    """Show the final summary of a completed batch scan."""
    run = run_state.get_run(run_id)
    if run is None:
        abort(404)
    if run['status'] == 'running':
        return redirect(url_for('spiderfoot_control.scan_progress', run_id=run_id))

    result = run.get('result') or {}
    return render_template(
        'spiderfoot_scan_result.html',
        run_id=run_id,
        run=run,
        completed=result.get('completed', 0),
        failed=result.get('failed', 0),
        total=result.get('total', 0),
        jobs=result.get('jobs', []),
        usecase=result.get('usecase', 'all'),
    )
