"""
run_state.py - In-memory tracking for long-running web operations.

Long-running operations (scrape, analysis, wildcard full mode) need:
  1. A way to start without blocking the HTTP request
  2. A way to track progress in memory
  3. A way to stream that progress to the browser via SSE
  4. A way to surface the final result

This module provides #2 and #4 — a thread-safe dict of run state keyed
by run_id. The route allocates a run_id, kicks off a background thread
that updates the state, then returns. The SSE endpoint polls this state
and streams new events to the browser.

State is in-memory only — survives across HTTP requests but not across
Flask server restarts. Single-process Flask, single-user, localhost-only
in current phases. If multi-process becomes a thing in Phase 6, swap this
for SQLite or Redis.

Run kinds: 'scrape', 'analysis', 'wildcard_full'. Each has the same shape
but different `result` payloads (set on completion).

Usage from a background worker:

    from web.services.run_state import (
        create_run, append_event, update_run, mark_complete, mark_failed
    )

    def _worker():
        run_id = create_run('scrape')
        try:
            for keyword in keywords:
                append_event(run_id, 'info', f'Searching: {keyword}')
                result = scrape_one(keyword)
            mark_complete(run_id, {'domains': sorted(result)})
        except Exception as e:
            mark_failed(run_id, str(e))
"""

import threading
import time
import uuid
from typing import Any, Dict, List, Optional


# Module-level state — protected by _runs_lock
_runs: Dict[str, Dict[str, Any]] = {}
_runs_lock = threading.Lock()

# Cap on event history per run to prevent unbounded memory growth
# (after this, oldest events are dropped — current state still tracked)
MAX_EVENTS_PER_RUN = 1000

# Cap on number of runs kept in memory simultaneously
# (after this, oldest completed/failed runs are reaped)
MAX_TOTAL_RUNS = 100


def create_run(kind: str) -> str:
    """
    Allocate a new run_id and initialize state.

    Args:
        kind: A short string identifying what's being run, e.g. 'scrape',
              'analysis', 'wildcard_full'. Used in event filtering.

    Returns:
        A new run_id (12-char hex string).
    """
    run_id = uuid.uuid4().hex[:12]
    now = time.time()
    with _runs_lock:
        # Reap old runs if we're at the cap
        if len(_runs) >= MAX_TOTAL_RUNS:
            _reap_old_runs_locked()

        _runs[run_id] = {
            'run_id': run_id,
            'kind': kind,
            'status': 'running',     # 'running', 'completed', 'failed'
            'created_at': now,
            'updated_at': now,
            'completed_at': None,
            'events': [],            # List[dict] — see append_event
            'event_seq': 0,          # monotonically increasing event counter
            'result': None,          # set by mark_complete
            'error': None,           # set by mark_failed
            'progress': 0,           # 0-100, optional
            'stage': '',             # current stage label, optional
        }
    return run_id


def _reap_old_runs_locked() -> None:
    """Drop the oldest completed/failed runs to make room. Caller holds lock."""
    # Find runs that have finished (completed or failed) sorted by completed_at ASC
    finished = sorted(
        ((rid, r) for rid, r in _runs.items() if r['status'] != 'running'),
        key=lambda kv: kv[1].get('completed_at') or kv[1]['updated_at'],
    )
    # Drop the oldest ones until we have headroom
    target_size = MAX_TOTAL_RUNS - 10  # leave 10 slots free
    for rid, _ in finished:
        if len(_runs) <= target_size:
            break
        del _runs[rid]


def append_event(
    run_id: str,
    level: str,
    message: str,
    **extra: Any,
) -> None:
    """
    Append a structured event to the run's event log.

    Args:
        run_id: The run to append to (no-op if missing)
        level: 'info', 'success', 'warning', 'error', 'stage', 'progress'
               (used by the browser to style the event)
        message: Human-readable message for the event log
        **extra: Additional structured fields (e.g., progress=50, stage='Loading')
    """
    with _runs_lock:
        run = _runs.get(run_id)
        if run is None:
            return
        run['event_seq'] += 1
        event = {
            'seq': run['event_seq'],
            'ts': time.time(),
            'level': level,
            'msg': message,
            **extra,
        }
        run['events'].append(event)
        run['updated_at'] = event['ts']

        # Mirror specific fields to top-level for easier consumption
        if 'progress' in extra:
            run['progress'] = extra['progress']
        if 'stage' in extra:
            run['stage'] = extra['stage']

        # Cap event history
        if len(run['events']) > MAX_EVENTS_PER_RUN:
            # Drop oldest 10% to amortize the cost
            drop_count = MAX_EVENTS_PER_RUN // 10
            run['events'] = run['events'][drop_count:]


def update_run(run_id: str, **kwargs: Any) -> None:
    """Thread-safe in-place update of arbitrary run state fields."""
    with _runs_lock:
        run = _runs.get(run_id)
        if run is None:
            return
        run.update(kwargs)
        run['updated_at'] = time.time()


def mark_complete(run_id: str, result: Any = None) -> None:
    """Mark a run as completed and stash its result."""
    now = time.time()
    with _runs_lock:
        run = _runs.get(run_id)
        if run is None:
            return
        run['status'] = 'completed'
        run['completed_at'] = now
        run['updated_at'] = now
        run['result'] = result
        run['event_seq'] += 1
        run['events'].append({
            'seq': run['event_seq'],
            'ts': now,
            'level': 'success',
            'msg': 'Completed.',
            'final': True,
        })


def mark_failed(run_id: str, error: str) -> None:
    """Mark a run as failed and stash its error message."""
    now = time.time()
    with _runs_lock:
        run = _runs.get(run_id)
        if run is None:
            return
        run['status'] = 'failed'
        run['completed_at'] = now
        run['updated_at'] = now
        run['error'] = error
        run['event_seq'] += 1
        run['events'].append({
            'seq': run['event_seq'],
            'ts': now,
            'level': 'error',
            'msg': f'Failed: {error}',
            'final': True,
        })


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    """
    Snapshot the current state of a run.

    Returns a copy so callers can't mutate the live state. Returns None
    if the run_id is unknown.
    """
    with _runs_lock:
        run = _runs.get(run_id)
        if run is None:
            return None
        # Shallow copy at the dict level + copy event list
        snapshot = dict(run)
        snapshot['events'] = list(run['events'])
        return snapshot


def get_events_since(run_id: str, last_seq: int) -> List[Dict[str, Any]]:
    """
    Return all events with seq > last_seq for a given run.

    Used by the SSE endpoint to stream only new events to the browser
    rather than re-sending the entire history each tick.
    """
    with _runs_lock:
        run = _runs.get(run_id)
        if run is None:
            return []
        return [e for e in run['events'] if e['seq'] > last_seq]


def is_terminal(run_id: str) -> bool:
    """Return True if the run is in a final state (completed or failed)."""
    with _runs_lock:
        run = _runs.get(run_id)
        if run is None:
            return True  # unknown run = nothing to wait for
        return run['status'] in ('completed', 'failed')
