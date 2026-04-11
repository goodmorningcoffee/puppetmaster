"""
domain_lists_service.py - Backend logic for domain list file operations.

Handles the puppetmaster/domain_lists/*.txt files that the user can save
domain lists to. Format is plain text, one domain per line, `#` lines as
comments. The directory is created on demand.

Operations:
  - list_domain_files()           -> List of file metadata dicts
  - parse_domain_list_file(path)  -> List of domains from a file
  - save_uploaded_list(name, txt) -> save uploaded text to a new file
  - delete_domain_files(names)    -> delete multiple files (path-validated)

All file operations are validated against the canonical domain_lists
directory using pm_paths.is_safe_path() to prevent path traversal.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# pm_paths is part of the puppetmaster package — always available
try:
    from pm_paths import is_safe_path
    _HAS_PM_PATHS = True
except ImportError:
    _HAS_PM_PATHS = False
    def is_safe_path(p, base=None):
        # Conservative fallback: reject anything containing ..
        return '..' not in str(p)


# Canonical domain lists directory — relative to the puppetmaster/ root
# (the CWD when puppetmaster.py / `python3 -m web` is run)
DOMAIN_LISTS_DIR = Path(os.environ.get(
    "PUPPETMASTER_DOMAIN_LISTS_DIR",
    "domain_lists",
)).resolve()

# Filename safety: only allow alphanumerics, dash, underscore, period
_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")

# Cap on individual file size we'll save (prevents trivial DOS via huge upload)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Cap on number of domains we'll parse from a single file
MAX_DOMAINS_PER_FILE = 100_000


def _ensure_dir() -> None:
    """Create the domain_lists directory if it doesn't exist."""
    try:
        DOMAIN_LISTS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _validate_filename(name: str) -> Optional[str]:
    """
    Validate a filename and return an error message string if invalid,
    or None if valid.
    """
    if not name:
        return "filename is empty"
    if not _SAFE_FILENAME_RE.match(name):
        return "filename contains invalid characters (allowed: a-z, A-Z, 0-9, ., _, -)"
    if len(name) > 200:
        return "filename too long"
    if not name.endswith(".txt"):
        return "filename must end in .txt"
    return None


def _format_size(num_bytes: int) -> str:
    """Format bytes as KB / MB."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def list_domain_files() -> List[Dict[str, Any]]:
    """
    Return metadata for every .txt file in the domain_lists directory.

    Each entry has: name, path, mtime (ISO), size_bytes, size_human,
    domain_count (parsed lazily — counts non-empty non-comment lines).
    Sorted by mtime descending (newest first).
    """
    _ensure_dir()

    if not DOMAIN_LISTS_DIR.is_dir():
        return []

    entries = []
    for path in DOMAIN_LISTS_DIR.glob("*.txt"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue

        # Quick line count — read once, count non-comment non-empty lines
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                count = sum(
                    1 for line in f
                    if line.strip() and not line.strip().startswith("#")
                )
        except OSError:
            count = 0

        entries.append({
            "name": path.name,
            "path": str(path),
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "size_bytes": stat.st_size,
            "size_human": _format_size(stat.st_size),
            "domain_count": count,
        })

    entries.sort(key=lambda e: e["mtime"], reverse=True)
    return entries


def parse_domain_list_file(filename: str) -> Tuple[List[str], Optional[str]]:
    """
    Parse a domain list file by basename and return (domains, error).

    Args:
        filename: A basename — NOT a full path. Validated and resolved
                  inside DOMAIN_LISTS_DIR.

    Returns:
        (domains, None) on success, or ([], error_message) on failure.
    """
    err = _validate_filename(filename)
    if err:
        return [], err

    target = (DOMAIN_LISTS_DIR / filename).resolve()
    # Defense in depth: ensure resolved path is still inside DOMAIN_LISTS_DIR
    try:
        target.relative_to(DOMAIN_LISTS_DIR)
    except ValueError:
        return [], "path traversal attempt blocked"

    if not target.is_file():
        return [], f"file not found: {filename}"

    try:
        with target.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        return [], f"failed to read: {e}"

    domains: List[str] = []
    for line in lines:
        domain = line.strip()
        if not domain or domain.startswith("#"):
            continue
        domains.append(domain)
        if len(domains) >= MAX_DOMAINS_PER_FILE:
            break

    return domains, None


def save_uploaded_list(filename: str, content: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Save uploaded text content to a new file in DOMAIN_LISTS_DIR.

    Args:
        filename: The basename to save as. Validated for safety.
        content: The raw text content to write.

    Returns:
        (saved_path, None) on success, or (None, error_message) on failure.
    """
    err = _validate_filename(filename)
    if err:
        return None, err

    if len(content.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
        return None, f"file too large (max {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB)"

    _ensure_dir()
    target = (DOMAIN_LISTS_DIR / filename).resolve()

    # Defense: must end up inside DOMAIN_LISTS_DIR
    try:
        target.relative_to(DOMAIN_LISTS_DIR)
    except ValueError:
        return None, "path traversal attempt blocked"

    # Don't overwrite existing files — pick a unique name if needed
    if target.exists():
        base = target.stem
        ext = target.suffix
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = DOMAIN_LISTS_DIR / f"{base}_{ts}{ext}"

    try:
        target.write_text(content, encoding="utf-8")
    except OSError as e:
        return None, f"failed to save: {e}"

    return str(target), None


def save_domain_list(filename: str, domains: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Save a list of domains as a new domain list file.

    Same as save_uploaded_list but takes a Python list and joins with newlines.
    Adds a header comment with the timestamp.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    header = f"# domain list saved {timestamp}\n# {len(domains)} domains\n"
    body = "\n".join(domains)
    return save_uploaded_list(filename, header + body + "\n")


def delete_domain_files(filenames: List[str]) -> Tuple[List[str], List[str]]:
    """
    Delete multiple domain list files by basename.

    Each filename is validated; valid ones are deleted, invalid/missing
    ones are reported as errors. Never raises — always returns the lists.

    Args:
        filenames: List of basenames to delete.

    Returns:
        (deleted_files, errors) — both lists of strings.
    """
    deleted: List[str] = []
    errors: List[str] = []

    for filename in filenames:
        err = _validate_filename(filename)
        if err:
            errors.append(f"{filename}: {err}")
            continue

        target = (DOMAIN_LISTS_DIR / filename).resolve()
        try:
            target.relative_to(DOMAIN_LISTS_DIR)
        except ValueError:
            errors.append(f"{filename}: path traversal blocked")
            continue

        if not target.is_file():
            errors.append(f"{filename}: not found")
            continue

        try:
            target.unlink()
            deleted.append(filename)
        except OSError as e:
            errors.append(f"{filename}: {e}")

    return deleted, errors
