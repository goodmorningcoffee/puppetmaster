#!/usr/bin/env python3
"""
CSV Keyword Cleaner - Remove rows containing specific keywords from large CSV files
"""

import os
import csv
import sys
from pathlib import Path

# Keywords to search for (case-insensitive)
KEYWORDS = [
    'ryan watson',
    'kusandesignbuild',
    'kapsaroff',
    'wenzhe yang',
    'christopher kapsaroff'
]

# Exclude these from matches (even if they contain keywords)
EXCLUDE_PATTERNS = [
    'thetakeoffcompany.com',  # Legit target, keep it
]

def scan_csv_for_keywords(csv_path, keywords):
    """Scan a CSV file and find rows containing any keyword"""
    matches = []

    print(f"\nScanning: {csv_path.name}")

    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for row_num, row in enumerate(reader, 1):
            # Join all columns to search entire row
            row_text = ','.join(row).lower()

            # Check if should exclude
            should_exclude = False
            for exclude in EXCLUDE_PATTERNS:
                if exclude.lower() in row_text:
                    should_exclude = True
                    break

            if should_exclude:
                continue

            # Check each keyword
            for keyword in keywords:
                if keyword.lower() in row_text:
                    matches.append({
                        'row_num': row_num,
                        'keyword': keyword,
                        'preview': row[0] if row else '',  # First column (Scan Name)
                        'full_row': row
                    })
                    break  # Only count each row once

            # Progress indicator for large files
            if row_num % 100000 == 0:
                print(f"  ... processed {row_num:,} rows", end='\r')

    print(f"  ✓ Found {len(matches)} matching rows")
    return matches

def show_summary(all_matches):
    """Display summary of findings"""
    print("\n" + "="*70)
    print("KEYWORD MATCH SUMMARY")
    print("="*70)

    # Group by file
    by_file = {}
    for match in all_matches:
        file_name = match['file']
        if file_name not in by_file:
            by_file[file_name] = []
        by_file[file_name].append(match)

    total_rows = 0
    for file_name, matches in by_file.items():
        print(f"\n{file_name}: {len(matches)} rows")

        # Show keyword breakdown
        keyword_counts = {}
        for m in matches:
            kw = m['keyword']
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

        for kw, count in sorted(keyword_counts.items()):
            print(f"  - '{kw}': {count} occurrences")

        # Show first few scan names
        scan_names = list(set([m['preview'] for m in matches[:10] if m['preview']]))
        if scan_names:
            print(f"  Sample scan names: {', '.join(scan_names[:5])}")

        total_rows += len(matches)

    print(f"\n{'='*70}")
    print(f"TOTAL: {total_rows} rows across {len(by_file)} files")
    print("="*70)

def clean_csv_file(csv_path, matches, dry_run=True):
    """Remove matching rows from CSV file"""
    if not matches:
        return

    # Get row numbers to delete
    rows_to_delete = set([m['row_num'] for m in matches])

    if dry_run:
        print(f"\n[DRY RUN] Would delete {len(rows_to_delete)} rows from {csv_path.name}")
        return

    # Create backup
    backup_path = csv_path.with_suffix('.csv.bak')
    print(f"\n  Creating backup: {backup_path.name}")
    os.rename(csv_path, backup_path)

    # Write cleaned file
    print(f"  Writing cleaned file: {csv_path.name}")
    rows_written = 0
    rows_deleted = 0

    with open(backup_path, 'r', encoding='utf-8', errors='ignore') as infile:
        with open(csv_path, 'w', encoding='utf-8', newline='') as outfile:
            reader = csv.reader(infile)
            writer = csv.writer(outfile)

            for row_num, row in enumerate(reader, 1):
                if row_num in rows_to_delete:
                    rows_deleted += 1
                else:
                    writer.writerow(row)
                    rows_written += 1

                if row_num % 100000 == 0:
                    print(f"  ... processed {row_num:,} rows", end='\r')

    print(f"  ✓ Wrote {rows_written:,} rows, deleted {rows_deleted:,} rows")

def main():
    global KEYWORDS, EXCLUDE_PATTERNS

    # Parse command line args
    mode = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    filter_keyword = sys.argv[2].lower() if len(sys.argv) > 2 else None

    # Get CSV directory from user if not in automated mode
    if len(sys.argv) > 3:
        # Use provided path
        export_dir = Path(sys.argv[3])
    else:
        # Interactive mode - ask user
        print("="*70)
        print("CSV KEYWORD CLEANER - Interactive Mode")
        print("="*70)

        # Ask for CSV directory
        default_path = '/workspaces/spiderfoot_2025/spiderfoot_export'
        csv_path_input = input(f"\nEnter path to CSV files [{default_path}]: ").strip()
        export_dir = Path(csv_path_input) if csv_path_input else Path(default_path)

        # Ask for keywords
        print(f"\nCurrent keywords: {', '.join(KEYWORDS)}")
        keywords_input = input("Enter keywords to search (comma-separated) or press Enter to use current: ").strip()

        if keywords_input:
            KEYWORDS = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
            print(f"Updated keywords: {', '.join(KEYWORDS)}")

        # Ask for exclude patterns
        if EXCLUDE_PATTERNS:
            print(f"\nCurrent exclude patterns: {', '.join(EXCLUDE_PATTERNS)}")
        exclude_input = input("Enter patterns to EXCLUDE (comma-separated) or press Enter to skip: ").strip()

        if exclude_input:
            EXCLUDE_PATTERNS = [pat.strip() for pat in exclude_input.split(',') if pat.strip()]
            print(f"Exclude patterns: {', '.join(EXCLUDE_PATTERNS)}")

        print()

    # Path to spiderfoot_export directory
    export_dir = Path(export_dir)

    if not export_dir.exists():
        print(f"Error: {export_dir} not found")
        sys.exit(1)

    # Find all CSV files
    csv_files = list(export_dir.glob('SpiderFoot*.csv'))

    if not csv_files:
        print(f"No CSV files found in {export_dir}")
        sys.exit(1)

    print(f"Found {len(csv_files)} CSV files to scan")
    print(f"Keywords: {', '.join(KEYWORDS)}")

    # Scan all files
    all_matches = []
    for csv_path in sorted(csv_files):
        matches = scan_csv_for_keywords(csv_path, KEYWORDS)
        for match in matches:
            match['file'] = csv_path.name
            match['path'] = csv_path
        all_matches.extend(matches)

    # Show summary
    show_summary(all_matches)

    if not all_matches:
        print("\n✓ No matches found - files are clean!")
        return

    # Mode handling
    if mode == 'scan':
        print("\n" + "="*70)
        print("To delete rows, run: python3 csv_keyword_cleaner.py delete")
        print("To see samples, run: python3 csv_keyword_cleaner.py sample")
        print("="*70)
        return

    if mode == 'sample':
        # Filter by keyword if specified
        if filter_keyword:
            filtered = [m for m in all_matches if filter_keyword in m['keyword'].lower()]
            print(f"\nSAMPLE MATCHING ROWS (keyword: '{filter_keyword}'):")
            print(f"Total matches for '{filter_keyword}': {len(filtered)}")
        else:
            filtered = all_matches
            print("\nSAMPLE MATCHING ROWS (all keywords):")

        for i, match in enumerate(filtered[:30], 1):
            print(f"\n{i}. {match['file']}:{match['row_num']}")
            print(f"   Keyword: '{match['keyword']}'")
            print(f"   Scan: {match['preview']}")
            if len(match['full_row']) > 1:
                print(f"   Data: {match['full_row'][1][:100]}...")

        if len(filtered) > 30:
            print(f"\n... and {len(filtered) - 30} more rows")

        print("\nTo delete, run: python3 csv_keyword_cleaner.py delete")
        return

    if mode == 'delete':
        # Delete mode
        print(f"\n⚠️  About to delete {len(all_matches)} rows from {len(set([m['file'] for m in all_matches]))} files")
        print("Backups will be created as *.csv.bak")

        # Group by file and clean
        by_file = {}
        for match in all_matches:
            file_path = match['path']
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(match)

        for csv_path, matches in by_file.items():
            clean_csv_file(csv_path, matches, dry_run=False)

        print(f"\n✓ Cleanup complete! Backups saved as *.csv.bak")
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python3 csv_keyword_cleaner.py [scan|sample|delete]")

if __name__ == '__main__':
    main()
