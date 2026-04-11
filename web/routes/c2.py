"""
c2.py - Distributed C2 Controller routes (Phase 4 Commit 2a).

Wires up the Distributed C2 worker management hub — reached in the TUI
via [3] SpiderFoot Control Center -> [D] Distributed multi-EC2 scanning.
In the web GUI it's a top-level /menu/c2 hub linked from the existing
/menu/spiderfoot hub.

This commit (2a) handles worker fleet inventory + SSH-dependent prep
actions (validate, detect, setup). The scan orchestration (start, stop,
progress polling, collect) lands in Commit 2b.

Routes:
  GET  /menu/c2                                  -- hub (worker list, SSH status, actions)
  GET  /menu/c2/workers/add                      -- add-worker form
  POST /menu/c2/workers/add                      -- submit new worker
  POST /menu/c2/workers/<hostname>/remove        -- remove a worker
  POST /menu/c2/workers/<hostname>/toggle        -- enable/disable a worker
  POST /menu/c2/validate                         -- start background SSH validate
  POST /menu/c2/detect                           -- start background resource detection
  POST /menu/c2/setup                            -- start background install/setup
  GET  /menu/c2/progress/<run_id>                -- live SSE progress page
  GET  /menu/c2/result/<run_id>                  -- final summary page
"""

from flask import Blueprint, abort, redirect, render_template, request, url_for

from ..services import c2_service, run_state


bp = Blueprint('c2', __name__)


def _render_hub(message=None):
    """Render the hub page with optional flash message tuple (level, text)."""
    snapshot = c2_service.get_c2_snapshot()
    return render_template(
        'c2_hub.html',
        workers=snapshot['workers'],
        stats=snapshot['stats'],
        ssh_status=snapshot['ssh_status'],
        config_summary=snapshot['config_summary'],
        active_session=snapshot['active_session'],
        snapshot_error=snapshot['error'],
        message=message,
    )


@bp.route('/menu/c2')
def hub():
    """Distributed C2 Controller hub."""
    return _render_hub()


@bp.route('/menu/c2/workers/add', methods=['GET'])
def worker_add_form():
    """Show the add-worker form."""
    return render_template('c2_worker_add_form.html')


@bp.route('/menu/c2/workers/add', methods=['POST'])
def worker_add():
    """Submit a new worker. Re-renders form with error on validation failure."""
    hostname = request.form.get('hostname', '').strip()
    username = request.form.get('username', 'kali').strip() or 'kali'
    nickname = request.form.get('nickname', '').strip() or None

    if not hostname:
        return render_template(
            'c2_worker_add_form.html',
            error='Hostname is required.',
            hostname=hostname,
            username=username,
            nickname=nickname or '',
        )

    ok, msg = c2_service.add_worker(hostname, username=username, nickname=nickname)
    if not ok:
        return render_template(
            'c2_worker_add_form.html',
            error=msg,
            hostname=hostname,
            username=username,
            nickname=nickname or '',
        )
    return _render_hub(message=('success', msg))


@bp.route('/menu/c2/workers/<hostname>/remove', methods=['POST'])
def worker_remove(hostname: str):
    """Remove a worker by hostname."""
    ok, msg = c2_service.remove_worker(hostname)
    return _render_hub(message=('success' if ok else 'error', msg))


@bp.route('/menu/c2/workers/<hostname>/toggle', methods=['POST'])
def worker_toggle(hostname: str):
    """Toggle a worker's enabled flag."""
    ok, msg = c2_service.toggle_worker(hostname)
    return _render_hub(message=('success' if ok else 'error', msg))


@bp.route('/menu/c2/validate', methods=['POST'])
def validate():
    """Start background SSH connectivity validation."""
    run_id = c2_service.start_validate_in_background()
    return redirect(url_for('c2.progress', run_id=run_id))


@bp.route('/menu/c2/detect', methods=['POST'])
def detect():
    """Start background worker resource detection."""
    run_id = c2_service.start_detect_resources_in_background()
    return redirect(url_for('c2.progress', run_id=run_id))


@bp.route('/menu/c2/setup', methods=['POST'])
def setup():
    """Start background worker install/setup."""
    run_id = c2_service.start_setup_in_background()
    return redirect(url_for('c2.progress', run_id=run_id))


@bp.route('/menu/c2/progress/<run_id>')
def progress(run_id: str):
    """Live SSE progress page for a running C2 action."""
    run = run_state.get_run(run_id)
    if run is None:
        abort(404)
    return render_template('c2_progress.html', run_id=run_id, run=run)


@bp.route('/menu/c2/result/<run_id>')
def result(run_id: str):
    """Final summary for a completed C2 action."""
    run = run_state.get_run(run_id)
    if run is None:
        abort(404)
    if run['status'] == 'running':
        return redirect(url_for('c2.progress', run_id=run_id))

    result_data = run.get('result') or {}
    return render_template(
        'c2_result.html',
        run_id=run_id,
        run=run,
        result=result_data,
        kind=result_data.get('kind', run.get('kind', 'c2_validate')),
    )
