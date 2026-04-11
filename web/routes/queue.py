"""
queue.py - Domain Queue Manager routes.

Mirrors option [12] (manage_domain_queue_menu) from the TUI. Phase 2
shipped the read-only display. Phase 3 adds mutating routes:

Routes:
  GET  /menu/queue              — display the queue (read-only)
  POST /menu/queue/remove       — remove one domain from loaded list
  POST /menu/queue/clear        — clear all loaded domains
  POST /menu/queue/commit       — move loaded domains to JobTracker scan queue
"""

from flask import Blueprint, redirect, render_template, request, url_for

from ..services.queue_service import get_queue_snapshot
from ..services.queue_mutations_service import (
    clear_loaded_domains,
    commit_loaded_to_jobtracker,
    remove_domain_from_loaded,
)


bp = Blueprint('queue', __name__)


def _render_queue(message=None):
    """Helper that re-renders the queue page with optional flash message."""
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
        message=message,
    )


@bp.route('/menu/queue')
def queue_screen():
    """Render the domain queue manager — equivalent to manage_domain_queue_menu()."""
    return _render_queue()


@bp.route('/menu/queue/remove', methods=['POST'])
def remove_one():
    """Remove a single domain from the loaded queue."""
    domain = request.form.get('domain', '').strip()
    if not domain:
        return _render_queue(message=("warning", "No domain specified."))

    if remove_domain_from_loaded(domain):
        return _render_queue(message=("success", f"Removed: {domain}"))
    return _render_queue(message=("warning", f"Domain not found: {domain}"))


@bp.route('/menu/queue/clear', methods=['POST'])
def clear_all():
    """Clear the entire loaded domains list."""
    count = clear_loaded_domains()
    if count > 0:
        return _render_queue(message=("success", f"Cleared {count} domain(s)."))
    return _render_queue(message=("info", "Loaded queue was already empty."))


@bp.route('/menu/queue/commit', methods=['POST'])
def commit_to_scan_queue():
    """Move loaded domains into the JobTracker scan queue."""
    count = commit_loaded_to_jobtracker()
    if count > 0:
        return _render_queue(
            message=("success", f"Committed {count} domain(s) to the scan queue.")
        )
    return _render_queue(
        message=("warning", "Nothing to commit (loaded queue empty or JobTracker unavailable).")
    )
