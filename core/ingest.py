#!/usr/bin/env python3
"""
ingest.py - SpiderFoot CSV Data Ingestion Module

Handles loading and normalizing SpiderFoot CSV exports.
Designed to handle large files efficiently and deal with encoding issues.
"""

import os
import csv
import io
from pathlib import Path
from typing import List, Dict, Generator, Tuple
from collections import defaultdict
from tqdm import tqdm

# =============================================================================
# CONSTANTS
# =============================================================================

# SpiderFoot CSV column formats
# Web UI export has 7 columns
WEB_UI_COLUMNS = ['Scan Name', 'Updated', 'Type', 'Module', 'Source', 'F/P', 'Data']
# CLI output has 3 columns (when using -o csv)
CLI_COLUMNS = ['Source', 'Type', 'Data']

# For backwards compatibility
EXPECTED_COLUMNS = WEB_UI_COLUMNS

# Modules we care about for sock puppet detection (high-signal modules)
HIGH_VALUE_MODULES = {
    'sfp_webanalytics',   # Google Analytics, AdSense, etc.
    'sfp_email',          # Email addresses
    'sfp_crt',            # SSL certificates
    'sfp_whois',          # WHOIS data
    'sfp_dnsresolve',     # DNS resolution
    'sfp_spider',         # Web content
    'sfp_phone',          # Phone numbers
    'sfp_social',         # Social media
    'sfp_pageinfo',       # Page metadata
}

# =============================================================================
# LOADING FUNCTIONS
# =============================================================================

def clean_text(text: str) -> str:
    """Clean text data - remove NUL bytes and other problematic characters"""
    if not text:
        return ""
    # Remove NUL bytes
    text = text.replace('\x00', '')
    # Normalize whitespace
    text = ' '.join(text.split())
    return text.strip()


def count_csv_lines(filepath: Path) -> int:
    """Count lines in a CSV file efficiently"""
    with open(filepath, 'rb') as f:
        return sum(1 for _ in f) - 1  # Subtract header


def extract_domain_from_filename(filepath: Path) -> str:
    """Extract domain name from SpiderFoot export filename.

    Filename format: domain_com_YYYYMMDD_HHMMSS.csv
    Returns: domain.com
    """
    stem = filepath.stem  # filename without extension
    # Remove timestamp suffix (last 2 underscore-separated parts)
    parts = stem.rsplit('_', 2)
    if len(parts) >= 3:
        domain_part = parts[0]
        # Convert underscores back to dots
        return domain_part.replace('_', '.')
    return stem.replace('_', '.')


def load_spiderfoot_csv(filepath: Path, show_progress: bool = True) -> Generator[Dict, None, None]:
    """
    Load a SpiderFoot CSV file and yield rows as dictionaries.

    Handles:
    - NUL bytes in data
    - Encoding issues
    - Multiline data in fields
    - Both CLI format (3 columns) and Web UI export format (7 columns)

    Yields:
        dict: Row data with keys matching column names
    """
    # Get total lines for progress bar
    total_lines = count_csv_lines(filepath) if show_progress else None

    # Read file and clean NUL bytes
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read().replace('\x00', '')

    # Parse CSV from cleaned content
    reader = csv.DictReader(io.StringIO(content))
    fieldnames = reader.fieldnames or []

    # Detect format: CLI (3 cols) vs Web UI (7 cols)
    is_cli_format = fieldnames == CLI_COLUMNS
    is_webui_format = fieldnames == WEB_UI_COLUMNS

    # Log format detection (only for first file or unknown formats)
    if not is_cli_format and not is_webui_format:
        # Unknown format - try to work with it anyway
        print(f"  ⚠ Note: Non-standard columns in {filepath.name}, attempting to parse...")
        print(f"    Got: {fieldnames}")

    # For CLI format, extract domain from filename
    domain_from_filename = None
    if is_cli_format:
        domain_from_filename = extract_domain_from_filename(filepath)

    # Create progress bar
    if show_progress and total_lines:
        pbar = tqdm(total=total_lines, desc=f"  Loading {filepath.name[:30]}",
                    unit=" rows", ncols=80, leave=False)

    # Yield rows
    for row in reader:
        if show_progress and total_lines:
            pbar.update(1)

        if is_cli_format:
            # CLI format: Source, Type, Data
            # Source contains the scanned domain (target)
            # The "Source" column in CLI output is actually the target domain
            source_val = clean_text(row.get('Source', ''))

            cleaned_row = {
                'scan_name': domain_from_filename or source_val,  # Use filename or Source as domain
                'updated': '',
                'type': row.get('Type', ''),
                'module': 'cli_scan',  # Unknown module in CLI format
                'source': source_val,
                'false_positive': False,
                'data': clean_text(row.get('Data', ''))
            }
        else:
            # Web UI format or unknown - use standard column mapping
            cleaned_row = {
                'scan_name': clean_text(row.get('Scan Name', '')),
                'updated': row.get('Updated', ''),
                'type': row.get('Type', ''),
                'module': row.get('Module', ''),
                'source': clean_text(row.get('Source', '')),
                'false_positive': row.get('F/P', '0') == '1',
                'data': clean_text(row.get('Data', ''))
            }

        # Skip rows with no scan name and no data (invalid)
        if cleaned_row['scan_name'] or cleaned_row['data']:
            # Ensure we have a scan_name (fallback to filename)
            if not cleaned_row['scan_name']:
                cleaned_row['scan_name'] = domain_from_filename or filepath.stem
            yield cleaned_row

    if show_progress and total_lines:
        pbar.close()


def load_all_exports(directory: Path, show_progress: bool = True) -> Dict:
    """
    Load all SpiderFoot CSV exports from a directory.

    Args:
        directory: Path to directory containing CSV exports
        show_progress: Whether to show progress bars

    Returns:
        dict with:
            - 'domains': Set of all scanned domains
            - 'rows_by_module': Dict mapping module name to list of rows
            - 'rows_by_domain': Dict mapping domain to list of rows
            - 'total_rows': Total number of rows loaded
    """
    directory = Path(directory)
    csv_files = list(directory.glob("*.csv"))

    if not csv_files:
        raise ValueError(f"No CSV files found in {directory}")

    print(f"\n🔍 Found {len(csv_files)} SpiderFoot export file(s)\n")

    # Initialize storage
    all_domains = set()
    rows_by_module = defaultdict(list)
    rows_by_domain = defaultdict(list)
    total_rows = 0

    # Load each file
    for csv_file in csv_files:
        file_size = csv_file.stat().st_size / (1024 * 1024)
        print(f"📂 Loading {csv_file.name} ({file_size:.1f} MB)")

        for row in load_spiderfoot_csv(csv_file, show_progress):
            domain = row['scan_name']
            module = row['module']

            all_domains.add(domain)
            rows_by_module[module].append(row)
            rows_by_domain[domain].append(row)
            total_rows += 1

    print(f"\n✓ Loaded {total_rows:,} rows across {len(all_domains)} domains")
    print(f"✓ Found data from {len(rows_by_module)} SpiderFoot modules")

    return {
        'domains': all_domains,
        'rows_by_module': dict(rows_by_module),
        'rows_by_domain': dict(rows_by_domain),
        'total_rows': total_rows
    }


def get_module_summary(data: Dict) -> Dict[str, int]:
    """Get a summary of rows per module"""
    return {
        module: len(rows)
        for module, rows in sorted(
            data['rows_by_module'].items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
    }


def extract_shared_elements(data: Dict, module: str) -> Dict[str, set]:
    """
    Extract data elements shared across multiple domains for a specific module.

    Returns:
        Dict mapping data element -> set of domains that share it
    """
    element_to_domains = defaultdict(set)

    for row in data['rows_by_module'].get(module, []):
        element = row['data']
        domain = row['scan_name']

        # Skip empty or very short data
        if len(element) < 3:
            continue

        element_to_domains[element].add(domain)

    # Only keep elements shared by 2+ domains
    shared = {
        element: domains
        for element, domains in element_to_domains.items()
        if len(domains) >= 2
    }

    return shared


def get_domain_data(data: Dict, domain: str, module: str = None) -> List[Dict]:
    """Get all data rows for a specific domain, optionally filtered by module"""
    rows = data['rows_by_domain'].get(domain, [])
    if module:
        rows = [r for r in rows if r['module'] == module]
    return rows
