#!/usr/bin/env python3
"""
jobs.py - Scan Job Queue and Tracking

Manages the queue of SpiderFoot scan jobs, tracks progress,
and persists state for resume capability.
"""

import json
import re
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from enum import Enum


def sanitize_domain(domain: str) -> Optional[str]:
    """
    Sanitize and validate a domain name.

    Handles:
    - Removing protocols (http://, https://)
    - Removing paths and query strings
    - Removing port numbers
    - Removing leading/trailing whitespace and dots
    - Lowercasing

    Returns:
        Cleaned domain name, or None if invalid
    """
    if not domain:
        return None

    domain = domain.strip().lower()

    # Remove protocol
    if domain.startswith('http://'):
        domain = domain[7:]
    elif domain.startswith('https://'):
        domain = domain[8:]

    # Remove path/query/fragment
    domain = domain.split('/')[0]
    domain = domain.split('?')[0]
    domain = domain.split('#')[0]

    # Remove port number
    domain = domain.split(':')[0]

    # Remove leading/trailing dots and whitespace
    domain = domain.strip('. \t\n\r')

    # Basic validation: must have at least one dot, no spaces, reasonable length
    if not domain or ' ' in domain or '.' not in domain:
        return None

    # Must match basic domain pattern (alphanumeric, hyphens, dots)
    if not re.match(r'^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$', domain):
        return None

    # No consecutive dots
    if '..' in domain:
        return None

    return domain


class JobStatus(Enum):
    """Status of a scan job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScanJob:
    """Represents a single SpiderFoot scan job."""
    domain: str
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    csv_path: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ScanJob':
        """Create from dictionary."""
        return cls(**data)

    def mark_running(self):
        """Mark job as running."""
        self.status = JobStatus.RUNNING.value
        self.started_at = datetime.now().isoformat()

    def mark_completed(self, csv_path: str):
        """Mark job as completed with output path."""
        self.status = JobStatus.COMPLETED.value
        self.completed_at = datetime.now().isoformat()
        self.csv_path = csv_path

    def mark_failed(self, error: str):
        """Mark job as failed with error message."""
        self.status = JobStatus.FAILED.value
        self.completed_at = datetime.now().isoformat()
        self.error = error
        self.retry_count += 1

    def reset_for_retry(self):
        """Reset job for retry."""
        self.status = JobStatus.PENDING.value
        self.started_at = None
        self.completed_at = None
        self.error = None


class JobTracker:
    """
    Manages a queue of scan jobs with persistence.

    Saves state to JSON file so scans can be resumed after interruption.
    """
    # Class-level lock shared by all instances
    _class_lock = threading.Lock()

    def __init__(self, state_file: Optional[str] = None):
        """
        Initialize the job tracker.

        Args:
            state_file: Path to JSON file for persisting state.
                        Defaults to .working_set.json in discovery/
        """
        if state_file:
            self.state_file = Path(state_file)
        else:
            self.state_file = Path(__file__).parent / ".working_set.json"

        self._lock = JobTracker._class_lock  # Use class-level lock
        self.jobs: Dict[str, ScanJob] = {}
        self.metadata: dict = {
            "created_at": datetime.now().isoformat(),
            "spiderfoot_path": None,
            "output_dir": None,
        }
        self._load_state()

    def _load_state(self):
        """Load state from file if it exists."""
        with self._lock:
            if self.state_file.exists():
                try:
                    with open(self.state_file, 'r') as f:
                        data = json.load(f)
                        self.metadata = data.get('metadata', self.metadata)
                        jobs_data = data.get('jobs', {})
                        self.jobs = {
                            domain: ScanJob.from_dict(job_data)
                            for domain, job_data in jobs_data.items()
                        }
                except json.JSONDecodeError as e:
                    print(f"Warning: State file corrupted, starting fresh: {e}")
                    # Delete corrupted file
                    try:
                        self.state_file.unlink()
                    except Exception:
                        pass
                except Exception as e:
                    print(f"Warning: Could not load state file: {e}")

    def save_state(self):
        """Save current state to file."""
        with self._lock:
            try:
                data = {
                    'metadata': self.metadata,
                    'jobs': {
                        domain: job.to_dict()
                        for domain, job in self.jobs.items()
                    }
                }
                # Write to temp file first, then rename (atomic operation)
                temp_file = self.state_file.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(data, f, indent=2)
                temp_file.replace(self.state_file)
            except Exception as e:
                print(f"Warning: Could not save state file: {e}")

    def set_config(self, spiderfoot_path: str = None, output_dir: str = None):
        """Set configuration metadata."""
        if spiderfoot_path:
            self.metadata['spiderfoot_path'] = spiderfoot_path
        if output_dir:
            self.metadata['output_dir'] = output_dir
        self.save_state()

    def add_domains(self, domains: List[str]) -> int:
        """
        Add domains to the job queue.

        Args:
            domains: List of domain names (URLs and raw domains accepted)

        Returns:
            Number of new domains added (excludes duplicates and invalid entries)
        """
        added = 0
        with self._lock:
            for domain in domains:
                # Sanitize and validate domain
                clean_domain = sanitize_domain(domain)
                if clean_domain and clean_domain not in self.jobs:
                    self.jobs[clean_domain] = ScanJob(domain=clean_domain)
                    added += 1
        self.save_state()
        return added

    def get_pending(self) -> List[ScanJob]:
        """Get all pending jobs."""
        with self._lock:
            return [j for j in self.jobs.values() if j.status == JobStatus.PENDING.value]

    def get_running(self) -> List[ScanJob]:
        """Get all running jobs."""
        with self._lock:
            return [j for j in self.jobs.values() if j.status == JobStatus.RUNNING.value]

    def get_completed(self) -> List[ScanJob]:
        """Get all completed jobs."""
        with self._lock:
            return [j for j in self.jobs.values() if j.status == JobStatus.COMPLETED.value]

    def get_failed(self) -> List[ScanJob]:
        """Get all failed jobs."""
        with self._lock:
            return [j for j in self.jobs.values() if j.status == JobStatus.FAILED.value]

    def get_job(self, domain: str) -> Optional[ScanJob]:
        """Get a specific job by domain."""
        with self._lock:
            return self.jobs.get(domain.lower())

    def update_job(self, domain: str, **kwargs):
        """Update a job's attributes."""
        with self._lock:
            job = self.jobs.get(domain.lower())
            if job:
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
        self.save_state()

    def retry_failed(self) -> int:
        """
        Reset all failed jobs for retry.

        Returns:
            Number of jobs reset
        """
        with self._lock:
            count = 0
            for job in list(self.jobs.values()):
                if job.status == JobStatus.FAILED.value:
                    job.reset_for_retry()
                    count += 1
        self.save_state()
        return count

    def clear_completed(self):
        """Remove completed jobs from the queue."""
        with self._lock:
            self.jobs = {
                domain: job for domain, job in self.jobs.items()
                if job.status != JobStatus.COMPLETED.value
            }
        self.save_state()

    def clear_all(self):
        """Clear all jobs."""
        with self._lock:
            self.jobs = {}
        self.save_state()

    def get_stats(self) -> dict:
        """Get queue statistics."""
        with self._lock:
            statuses = {}
            for job in self.jobs.values():
                statuses[job.status] = statuses.get(job.status, 0) + 1

            return {
                'total': len(self.jobs),
                'pending': statuses.get(JobStatus.PENDING.value, 0),
                'running': statuses.get(JobStatus.RUNNING.value, 0),
                'completed': statuses.get(JobStatus.COMPLETED.value, 0),
                'failed': statuses.get(JobStatus.FAILED.value, 0),
                'cancelled': statuses.get(JobStatus.CANCELLED.value, 0),
            }

    def get_progress_string(self) -> str:
        """Get a human-readable progress string."""
        stats = self.get_stats()
        total = stats['total']
        if total == 0:
            return "No jobs in queue"

        completed = stats['completed']
        failed = stats['failed']
        running = stats['running']
        pending = stats['pending']

        return (
            f"Total: {total} | "
            f"Completed: {completed} | "
            f"Failed: {failed} | "
            f"Running: {running} | "
            f"Pending: {pending}"
        )

    def has_pending_work(self) -> bool:
        """Check if there's pending work to do."""
        return len(self.get_pending()) > 0 or len(self.get_running()) > 0
