"""
queue_service.py - Backend logic for the Domain Queue and Scan Status screens.

Wraps the existing pm_config.load_config() and discovery.jobs.JobTracker
classes with safe import + null-object fallbacks. The web GUI must render
even when the JobTracker state file is missing or the discovery module
hasn't been initialized — these are normal "fresh install" conditions.
"""

from typing import Any, Dict, List, Optional


# pm_config is always available — it's part of the puppetmaster package
try:
    from pm_config import load_config
    _HAS_PM_CONFIG = True
except ImportError:
    _HAS_PM_CONFIG = False
    def load_config():
        return {}


# JobTracker may not be importable in minimal installs
try:
    from discovery.jobs import JobTracker
    _HAS_JOB_TRACKER = True
except ImportError:
    _HAS_JOB_TRACKER = False
    JobTracker = None  # type: ignore


def _scanjob_to_dict(job) -> Dict[str, Any]:
    """Convert a ScanJob dataclass instance to a JSON-friendly dict."""
    return {
        "domain": getattr(job, "domain", ""),
        "status": getattr(job, "status", ""),
        "created_at": getattr(job, "created_at", None),
        "started_at": getattr(job, "started_at", None),
        "completed_at": getattr(job, "completed_at", None),
        "csv_path": getattr(job, "csv_path", None),
        "error": getattr(job, "error", None),
        "retry_count": getattr(job, "retry_count", 0),
    }


def get_loaded_domains() -> List[str]:
    """
    Return the list of domains loaded into config['pending_domains'].

    These are domains the user has scraped/loaded but not yet committed
    to the scan queue. Distinct from JobTracker's pending list.
    """
    config = load_config()
    return list(config.get("pending_domains", []))


def get_queue_snapshot(max_per_status: int = 50) -> Dict[str, Any]:
    """
    Return a complete snapshot of the queue and scan job state.

    Safe against:
      - Missing JobTracker module (returns empty stats + lists)
      - Missing/corrupt .working_set.json (JobTracker handles internally)
      - Any unexpected exception (returns empty snapshot with available=False)

    Args:
        max_per_status: cap number of jobs returned per status list

    Returns:
        Dict with shape:
          {
            "available": bool,         # whether JobTracker loaded successfully
            "loaded_domains": List[str],
            "loaded_count": int,
            "stats": {total, pending, running, completed, failed, cancelled},
            "pending": List[ScanJob dict],
            "running": List[ScanJob dict],
            "completed": List[ScanJob dict],   # most recent first
            "failed": List[ScanJob dict],
          }
    """
    snapshot: Dict[str, Any] = {
        "available": False,
        "loaded_domains": get_loaded_domains(),
        "loaded_count": 0,
        "stats": {
            "total": 0,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        },
        "pending": [],
        "running": [],
        "completed": [],
        "failed": [],
    }
    snapshot["loaded_count"] = len(snapshot["loaded_domains"])

    if not _HAS_JOB_TRACKER:
        return snapshot

    try:
        tracker = JobTracker()
        snapshot["available"] = True
        snapshot["stats"] = tracker.get_stats()
        snapshot["pending"] = [_scanjob_to_dict(j) for j in tracker.get_pending()[:max_per_status]]
        snapshot["running"] = [_scanjob_to_dict(j) for j in tracker.get_running()[:max_per_status]]
        # Most recent completed/failed first — sort by completed_at descending
        completed = sorted(
            tracker.get_completed(),
            key=lambda j: getattr(j, "completed_at", "") or "",
            reverse=True,
        )
        failed = sorted(
            tracker.get_failed(),
            key=lambda j: getattr(j, "completed_at", "") or "",
            reverse=True,
        )
        snapshot["completed"] = [_scanjob_to_dict(j) for j in completed[:max_per_status]]
        snapshot["failed"] = [_scanjob_to_dict(j) for j in failed[:max_per_status]]
    except Exception:
        # Any unexpected failure — return the empty snapshot we already built
        # so the page still renders (with `available: False`)
        pass

    return snapshot


def get_quick_stats() -> Dict[str, Any]:
    """
    Lightweight version of get_queue_snapshot() — only stats + counts,
    no per-job data. Used by the SSE stream where we send updates frequently
    and don't want to ship 50+ ScanJob objects every 2 seconds.
    """
    snapshot: Dict[str, Any] = {
        "available": False,
        "loaded_count": len(get_loaded_domains()),
        "stats": {
            "total": 0,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        },
    }

    if not _HAS_JOB_TRACKER:
        return snapshot

    try:
        tracker = JobTracker()
        snapshot["available"] = True
        snapshot["stats"] = tracker.get_stats()
    except Exception:
        pass

    return snapshot
