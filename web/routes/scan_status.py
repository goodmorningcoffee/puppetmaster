"""
scan_status.py - Scan queue status route with live SSE updates.

Mirrors option [4] (check_scan_status_menu) from the TUI. The initial
page load returns a snapshot via the route; subsequent updates flow
through /events/scan-jobs as SSE events.
"""

from flask import Blueprint, render_template

from ..services.queue_service import get_queue_snapshot


bp = Blueprint('scan_status', __name__)


@bp.route('/menu/scan-status')
def scan_status_screen():
    """Render the scan queue status with initial snapshot."""
    snapshot = get_queue_snapshot(max_per_status=20)
    return render_template(
        'scan_status.html',
        available=snapshot['available'],
        stats=snapshot['stats'],
        pending=snapshot['pending'],
        running=snapshot['running'],
        completed=snapshot['completed'],
        failed=snapshot['failed'],
        loaded_count=snapshot['loaded_count'],
    )
