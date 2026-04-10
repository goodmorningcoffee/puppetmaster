"""
events.py - Server-Sent Events (SSE) routes.

Streams real-time updates to the browser. Currently provides:
  - /events/vitals — system vitals (CPU/mem/disk) every N seconds
                      plus background scan status

Each SSE endpoint is a Flask route that returns a streaming Response with
mimetype text/event-stream. The browser opens an EventSource connection
and receives JSON-encoded events as they arrive.
"""

import json
import time

from flask import Blueprint, Response, current_app

from ..services.vitals import collect_vitals

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
