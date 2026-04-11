"""
queue.py - Domain Queue Manager route (read-only).

Mirrors option [12] (manage_domain_queue_menu) from the TUI but as a
read-only display. Shows:
  - Loaded domains (config['pending_domains']) with count + first 50
  - Scan queue stats from JobTracker
  - Per-status counts (pending, running, completed, failed, cancelled)

Mutations (remove individual domain, clear queue, etc.) come in Phase 3.
"""

from flask import Blueprint, render_template

from ..services.queue_service import get_queue_snapshot


bp = Blueprint('queue', __name__)


@bp.route('/menu/queue')
def queue_screen():
    """Render the domain queue manager — equivalent to manage_domain_queue_menu()."""
    snapshot = get_queue_snapshot(max_per_status=50)
    return render_template(
        'queue.html',
        loaded_domains=snapshot['loaded_domains'],
        loaded_count=snapshot['loaded_count'],
        loaded_truncated=snapshot['loaded_count'] > 50,
        stats=snapshot['stats'],
        available=snapshot['available'],
        pending=snapshot['pending'],
        running=snapshot['running'],
        completed=snapshot['completed'],
        failed=snapshot['failed'],
    )
