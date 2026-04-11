"""
queue_mutations_service.py - Mutating operations for the domain queue.

Wraps pm_config.load_config() / save_config() to provide thread-safe
mutating operations on the loaded domains list (config['pending_domains']).

These are distinct from JobTracker mutations — config['pending_domains']
is the "loaded but not yet committed to scan queue" list. JobTracker
manages the actual scan job state.

Operations:
  - get_loaded_domains()                  -> List[str]
  - add_domains_to_loaded(domains)        -> int (count added)
  - remove_domain_from_loaded(domain)     -> bool
  - clear_loaded_domains()                -> int (count cleared)
  - commit_loaded_to_jobtracker()         -> int (count committed)
"""

import threading
from typing import List

try:
    from pm_config import load_config, save_config
    _HAS_PM_CONFIG = True
except ImportError:
    _HAS_PM_CONFIG = False
    def load_config():
        return {}
    def save_config(cfg):
        return False


# Lock to serialize concurrent mutations across HTTP requests
_mutation_lock = threading.Lock()


def get_loaded_domains() -> List[str]:
    """Return the current list of loaded (but not yet queued) domains."""
    config = load_config() if _HAS_PM_CONFIG else {}
    return list(config.get("pending_domains", []))


def add_domains_to_loaded(domains: List[str]) -> int:
    """
    Append domains to config['pending_domains'], deduplicating against existing.

    Returns the number of newly-added domains (excludes duplicates).
    """
    if not _HAS_PM_CONFIG:
        return 0

    with _mutation_lock:
        config = load_config()
        existing = list(config.get("pending_domains", []))
        existing_set = set(existing)

        added = 0
        for d in domains:
            d = d.strip()
            if not d or d in existing_set:
                continue
            existing.append(d)
            existing_set.add(d)
            added += 1

        config["pending_domains"] = existing
        if added > 0:
            # Set the "domains ready" flag so the main menu shows the banner
            config["domains_ready_for_scan"] = True
            config["domains_ready_count"] = len(existing)

        save_config(config)
        return added


def remove_domain_from_loaded(domain: str) -> bool:
    """
    Remove a single domain from config['pending_domains'].

    Returns True if the domain was found and removed, False otherwise.
    """
    if not _HAS_PM_CONFIG:
        return False

    with _mutation_lock:
        config = load_config()
        existing = list(config.get("pending_domains", []))
        if domain not in existing:
            return False

        existing.remove(domain)
        config["pending_domains"] = existing
        config["domains_ready_count"] = len(existing)
        if not existing:
            config["domains_ready_for_scan"] = False
        save_config(config)
        return True


def clear_loaded_domains() -> int:
    """
    Clear config['pending_domains'] entirely.

    Returns the number of domains that were cleared.
    """
    if not _HAS_PM_CONFIG:
        return 0

    with _mutation_lock:
        config = load_config()
        existing = list(config.get("pending_domains", []))
        count = len(existing)

        config["pending_domains"] = []
        config["domains_ready_for_scan"] = False
        config["domains_ready_count"] = 0
        save_config(config)
        return count


def commit_loaded_to_jobtracker() -> int:
    """
    Move all loaded domains into the JobTracker scan queue.

    This is the bridge between "loaded" (config['pending_domains']) and
    "queued for scanning" (JobTracker). After this operation, loaded
    domains are cleared and the scan queue has them.

    Returns the number of domains committed, or 0 if JobTracker isn't available.
    """
    if not _HAS_PM_CONFIG:
        return 0

    try:
        from discovery.jobs import JobTracker
    except ImportError:
        return 0

    with _mutation_lock:
        config = load_config()
        loaded = list(config.get("pending_domains", []))
        if not loaded:
            return 0

        try:
            tracker = JobTracker()
            added = tracker.add_domains(loaded)
        except Exception:
            return 0

        # Clear the loaded list
        config["pending_domains"] = []
        config["domains_ready_for_scan"] = False
        config["domains_ready_count"] = 0
        save_config(config)

        return added
