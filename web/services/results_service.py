"""
results_service.py - Backend logic for the View Previous Results screens.

Wraps pm_results.find_results_directories() and adds:
  - Per-directory metadata (mtime, file count, file sizes)
  - Markdown reading + lite rendering for executive_summary.md
  - CSV reading + parsing for the standard report files

Designed to never crash even when expected files are missing — investigators
might point at incomplete result dirs and we should still display what's there.
"""

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .markdown_lite import render_markdown


# Standard CSV files that core/report.py generates
STANDARD_CSV_FILES = [
    "smoking_guns.csv",
    "clusters.csv",
    "hub_analysis.csv",
    "all_connections.csv",
    "signals.csv",
]


# pm_results may not be importable in minimal installs
try:
    from pm_results import find_results_directories as _pm_find_results
    _HAS_PM_RESULTS = True
except ImportError:
    _HAS_PM_RESULTS = False
    def _pm_find_results():
        return []


@dataclass
class ResultDirInfo:
    """Metadata about a single result directory."""
    path: str               # absolute path
    name: str               # basename for use in URLs
    mtime: str              # ISO timestamp
    has_summary: bool       # whether executive_summary.md exists
    csv_files: List[str] = field(default_factory=list)
    csv_count: int = 0
    total_size_bytes: int = 0


def _format_size(num_bytes: int) -> str:
    """Format a byte count as KB / MB / GB."""
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def list_result_directories() -> List[ResultDirInfo]:
    """
    Return metadata about all known result directories.

    Calls pm_results.find_results_directories() if available, then
    enriches each with file metadata. Filters out directories that
    don't actually exist anymore (stale config entries).
    """
    if not _HAS_PM_RESULTS:
        return []

    try:
        raw_paths = _pm_find_results()
    except Exception:
        return []

    results: List[ResultDirInfo] = []
    for raw in raw_paths:
        path = Path(raw)
        if not path.is_dir():
            continue

        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            mtime = "unknown"

        has_summary = (path / "executive_summary.md").is_file()

        csv_files = []
        total_size = 0
        for csv_name in STANDARD_CSV_FILES:
            csv_path = path / csv_name
            if csv_path.is_file():
                csv_files.append(csv_name)
                try:
                    total_size += csv_path.stat().st_size
                except OSError:
                    pass

        results.append(ResultDirInfo(
            path=str(path.absolute()),
            name=path.name,
            mtime=mtime,
            has_summary=has_summary,
            csv_files=csv_files,
            csv_count=len(csv_files),
            total_size_bytes=total_size,
        ))

    return results


def find_result_directory_by_name(name: str) -> Optional[Path]:
    """
    Find a result directory by its basename.

    Searches the same paths pm_results does. Returns None if not found.
    The basename is what we use as a URL parameter (cleaner than escaping
    the full path through Flask routing).
    """
    if not _HAS_PM_RESULTS:
        return None

    try:
        for raw in _pm_find_results():
            path = Path(raw)
            if path.name == name and path.is_dir():
                return path
    except Exception:
        return None

    return None


def read_executive_summary(result_dir: Path) -> Optional[str]:
    """
    Read executive_summary.md from a result directory and render it to HTML.

    Returns:
        HTML string (rendered via markdown_lite) or None if the file is missing.
    """
    summary_path = result_dir / "executive_summary.md"
    if not summary_path.is_file():
        return None

    try:
        md_text = summary_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    return render_markdown(md_text)


def read_csv_file(
    result_dir: Path,
    csv_name: str,
    max_rows: int = 500,
) -> Optional[Dict[str, Any]]:
    """
    Read a CSV file from a result directory and return structured data
    for rendering as an HTML table.

    Args:
        result_dir: The result directory Path
        csv_name: One of STANDARD_CSV_FILES (or any CSV in the dir)
        max_rows: Cap on rows returned (the rest get a "...N more rows" footer)

    Returns:
        Dict with shape:
          {
            "name": str,
            "headers": List[str],
            "rows": List[List[str]],
            "total_rows": int,
            "truncated": bool,
            "size_bytes": int,
          }
        or None if the file is missing / unreadable.
    """
    csv_path = result_dir / csv_name
    if not csv_path.is_file():
        return None

    try:
        size_bytes = csv_path.stat().st_size
    except OSError:
        size_bytes = 0

    try:
        with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                return {
                    "name": csv_name,
                    "headers": [],
                    "rows": [],
                    "total_rows": 0,
                    "truncated": False,
                    "size_bytes": size_bytes,
                }

            rows: List[List[str]] = []
            total_rows = 0
            for row in reader:
                total_rows += 1
                if len(rows) < max_rows:
                    rows.append(row)
    except OSError:
        return None

    return {
        "name": csv_name,
        "headers": headers,
        "rows": rows,
        "total_rows": total_rows,
        "truncated": total_rows > max_rows,
        "size_bytes": size_bytes,
        "size_human": _format_size(size_bytes),
    }
