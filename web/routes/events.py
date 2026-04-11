"""
events.py - Server-Sent Events (SSE) routes.

Streams real-time updates to the browser. Provides:
  - /events/vitals       — system vitals (CPU/mem/disk) + scan status
  - /events/scan-jobs    — scan job queue snapshots from JobTracker
  - /events/run/<run_id> — per-run progress events from web/services/run_state

Each SSE endpoint is a Flask route that returns a streaming Response with
mimetype text/event-stream. The browser opens an EventSource connection
and receives JSON-encoded events as they arrive.
"""

import json
import time

from flask import Blueprint, Response, current_app

from ..services import run_state
from ..services.vitals import collect_vitals
from ..services.queue_service import get_queue_snapshot

# Background scan state from the existing pm_background module
try:
    from pm_background import is_background_scan_running, get_background_scan_stats
    _HAS_BG = True
except ImportError:
    _HAS_BG = False
    def is_background_scan_running():
        return False
    def get_background_scan_stats():
        return {}


bp = Blueprint('events', __name__)


@bp.route('/events/vitals')
def vitals_stream():
    """
    Server-Sent Events stream of system vitals + background scan status.

    The browser receives a JSON event every VITALS_INTERVAL seconds.
    Format:
        data: {"cpu": 12.3, "mem": 45.6, "disk": 78.9, "scan_running": false, ...}

    EventSource handles reconnection automatically if the connection drops.
    """
    interval = current_app.config.get("VITALS_INTERVAL", 2.0)

    def generate():
        """Generator that yields SSE-formatted lines."""
        while True:
            try:
                vitals = collect_vitals()
                payload = {
                    "cpu": round(vitals.cpu_percent, 1),
                    "mem": round(vitals.mem_percent, 1),
                    "disk": round(vitals.disk_percent, 1),
                    "vitals_available": vitals.available,
                    "scan_running": is_background_scan_running(),
                }
                if payload["scan_running"]:
                    stats = get_background_scan_stats()
                    payload["scan_stats"] = {
                        "completed": stats.get("completed", 0),
                        "failed": stats.get("failed", 0),
                        "total": stats.get("total", 0),
                        "current_domain": stats.get("current_domain"),
                    }

                yield f"data: {json.dumps(payload)}\n\n"
                time.sleep(interval)
            except GeneratorExit:
                # Client disconnected — stop streaming
                break
            except Exception as e:
                # Don't crash the stream on a single bad payload — log and continue
                error_payload = {"error": str(e)}
                yield f"data: {json.dumps(error_payload)}\n\n"
                time.sleep(interval)

    response = Response(generate(), mimetype="text/event-stream")
    # Disable proxy buffering — important for SSE through nginx etc.
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@bp.route('/events/run/<run_id>')
def run_events_stream(run_id: str):
    """
    Server-Sent Events stream of events for a single long-running operation.

    Polls run_state.get_events_since() every 0.5s and yields any new events.
    Closes the stream when the run reaches a terminal state (completed or
    failed) plus a brief grace period to ensure the final event reaches the
    browser.

    Used by all long-running operation screens (scrape in Commit 2, analysis
    in Commit 3, wildcard full mode in Commit 4).
    """
    poll_interval = 0.5  # seconds

    def generate():
        last_seq = 0
        terminal_count = 0

        # Send a hello event so the client knows the connection is open
        run = run_state.get_run(run_id)
        if run is None:
            yield f"data: {json.dumps({'event': 'error', 'error': 'unknown run_id', 'run_id': run_id})}\n\n"
            return
        yield f"data: {json.dumps({'event': 'hello', 'kind': run['kind'], 'status': run['status']})}\n\n"

        while True:
            try:
                events = run_state.get_events_since(run_id, last_seq)
                for ev in events:
                    last_seq = ev['seq']
                    payload = {'event': 'progress', **ev}
                    yield f"data: {json.dumps(payload)}\n\n"

                # Check if the run is in a terminal state
                if run_state.is_terminal(run_id):
                    terminal_count += 1
                    if terminal_count == 1:
                        snapshot = run_state.get_run(run_id)
                        if snapshot:
                            final_payload = {
                                'event': 'final',
                                'status': snapshot['status'],
                                'result': snapshot.get('result'),
                                'error': snapshot.get('error'),
                            }
                            yield f"data: {json.dumps(final_payload)}\n\n"
                    if terminal_count >= 2:
                        break

                time.sleep(poll_interval)
            except GeneratorExit:
                break
            except Exception as e:
                yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"
                break

    response = Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@bp.route('/events/scan-jobs')
def scan_jobs_stream():
    """
    Server-Sent Events stream of scan queue snapshots.

    Streams the full queue snapshot (loaded domains count + JobTracker
    stats + truncated job lists) every interval seconds. The browser
    re-renders the scan status table from each snapshot.

    Used by /menu/scan-status. Separate from /events/vitals because:
      - Different update cadence (could be tuned independently)
      - Different consumers (vitals are global; scan jobs are page-specific)
      - Can be opened/closed independently as user navigates pages
    """
    interval = current_app.config.get("VITALS_INTERVAL", 2.0)

    def generate():
        while True:
            try:
                snapshot = get_queue_snapshot(max_per_status=20)
                # Strip large fields the SSE consumer doesn't need
                payload = {
                    "available": snapshot["available"],
                    "loaded_count": snapshot["loaded_count"],
                    "stats": snapshot["stats"],
                    "pending": snapshot["pending"],
                    "running": snapshot["running"],
                    "completed": snapshot["completed"],
                    "failed": snapshot["failed"],
                    "scan_running": is_background_scan_running(),
                }
                if payload["scan_running"]:
                    bg_stats = get_background_scan_stats()
                    payload["bg_progress"] = {
                        "completed": bg_stats.get("completed", 0),
                        "failed": bg_stats.get("failed", 0),
                        "total": bg_stats.get("total", 0),
                        "current_domain": bg_stats.get("current_domain"),
                    }

                yield f"data: {json.dumps(payload)}\n\n"
                time.sleep(interval)
            except GeneratorExit:
                break
            except Exception as e:
                error_payload = {"error": str(e)}
                yield f"data: {json.dumps(error_payload)}\n\n"
                time.sleep(interval)

    response = Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response
