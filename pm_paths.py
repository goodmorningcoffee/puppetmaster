"""
pm_paths.py - Path Security and Directory Selection

Path validation, sanitization, and interactive directory selection.
"""

import os
from pathlib import Path
from datetime import datetime

from pm_config import load_config, remember_output_dir
from pm_ui_helpers import (
    C, print_section, print_success, print_error, print_warning, print_info,
    get_input, confirm,
)


def is_safe_path(user_path: str, base_dir: str = None) -> bool:
    """
    Check if a path is safe (no path traversal).

    Args:
        user_path: User-provided path to check
        base_dir: Optional base directory the path should stay within

    Returns:
        True if path is safe, False if it contains traversal attempts
    """
    # Expand user path
    expanded = os.path.expanduser(user_path)
    resolved = os.path.realpath(expanded)

    # Check for obvious traversal attempts in the original input
    if '..' in user_path:
        return False

    # If base_dir specified, ensure resolved path is within it
    if base_dir:
        base_resolved = os.path.realpath(os.path.expanduser(base_dir))
        if not resolved.startswith(base_resolved):
            return False

    return True


def sanitize_path(user_path: str, base_dir: str = None) -> str:
    """
    Sanitize a user-provided path, rejecting unsafe paths.

    Args:
        user_path: User-provided path
        base_dir: Optional base directory to enforce

    Returns:
        Sanitized path or raises ValueError if unsafe
    """
    if not is_safe_path(user_path, base_dir):
        raise ValueError(f"Unsafe path detected: {user_path}")
    return os.path.realpath(os.path.expanduser(user_path))


def get_data_directory():
    """Interactively get the SpiderFoot data directory from user"""
    print_section("Data Input", C.BRIGHT_MAGENTA)

    # Check for existing exports in known locations
    config = load_config()
    default_export_dir = config.get('spiderfoot_output_dir', './spiderfoot_exports')
    default_export_dir = os.path.expanduser(default_export_dir)

    # Also check common locations
    possible_dirs = [
        default_export_dir,
        './spiderfoot_exports',
        os.path.expanduser('~/spiderfoot_exports'),
    ]

    # Find directories with CSV files
    found_dirs = []
    for d in possible_dirs:
        if os.path.isdir(d):
            csv_files = list(Path(d).glob("*.csv"))
            if csv_files:
                if d not in [x[0] for x in found_dirs]:  # Avoid duplicates
                    found_dirs.append((d, csv_files))

    # If we found directories with exports, show selection menu
    if found_dirs:
        print(f"""
{C.WHITE}Found existing SpiderFoot exports:{C.RESET}
""")
        for i, (dir_path, csv_files) in enumerate(found_dirs, 1):
            total_size = sum(f.stat().st_size for f in csv_files)
            size_mb = total_size / (1024 * 1024)
            print(f"  {C.BRIGHT_GREEN}[{i}]{C.RESET} {dir_path}")
            print(f"      {C.DIM}{len(csv_files)} CSV files ({size_mb:.1f} MB){C.RESET}")
            # Show most recent files
            sorted_files = sorted(csv_files, key=lambda f: f.stat().st_mtime, reverse=True)
            for f in sorted_files[:3]:
                print(f"      {C.DIM}\u2022 {f.name}{C.RESET}")
            if len(csv_files) > 3:
                print(f"      {C.DIM}  ... and {len(csv_files) - 3} more{C.RESET}")
            print()

        print(f"  {C.BRIGHT_YELLOW}[{len(found_dirs) + 1}]{C.RESET} Enter a different path...")
        print()

        choice = get_input("Select option", "1")
        if choice is None:
            print_info("Cancelled.")
            return None

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(found_dirs):
                selected_dir = found_dirs[choice_num - 1][0]
                print_success(f"Using: {selected_dir}")
                return os.path.abspath(selected_dir)
        except ValueError:
            pass

        # Fall through to manual entry

    # Manual path entry
    print(f"""
{C.WHITE}Enter the directory containing your SpiderFoot CSV exports.{C.RESET}

{C.DIM}\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
\U0001f4a1 TIP: Drag and drop your SpiderFoot exports folder directly
   into this terminal window - the path will appear automatically!
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500{C.RESET}
""")

    while True:
        path = get_input("Enter the path to your SpiderFoot exports")

        # Ctrl+C = cancel
        if path is None:
            print_info("Cancelled.")
            return None

        if not path:
            print_warning("Path cannot be empty. Please try again.")
            continue

        # Expand user home directory
        path = os.path.expanduser(path)

        # Check if path exists
        if not os.path.exists(path):
            print_error(f"Path does not exist: {path}")
            if confirm("Would you like to try again?"):
                continue
            else:
                return None

        # Check if it's a directory
        if not os.path.isdir(path):
            print_error("That's a file, not a directory. Please provide a directory path.")
            continue

        # Check for CSV files
        csv_files = list(Path(path).glob("*.csv"))
        if not csv_files:
            print_warning(f"No CSV files found in: {path}")
            if confirm("This doesn't look like a SpiderFoot export directory. Continue anyway?"):
                pass
            else:
                continue
        else:
            print_success(f"Found {len(csv_files)} CSV file(s)")

            # Show file sizes
            total_size = sum(f.stat().st_size for f in csv_files)
            size_mb = total_size / (1024 * 1024)
            print_info(f"Total data size: {size_mb:.1f} MB")

            # Preview files
            print(f"\n{C.DIM}Files found:{C.RESET}")
            for f in csv_files[:5]:
                size = f.stat().st_size / (1024 * 1024)
                print(f"  \u2022 {f.name} ({size:.1f} MB)")
            if len(csv_files) > 5:
                print(f"  ... and {len(csv_files) - 5} more")

        print()
        if confirm("Use this directory?"):
            return os.path.abspath(path)


def get_output_directory():
    """Get or create output directory"""
    print_section("Output Location", C.BRIGHT_GREEN)

    # Default output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_output = os.path.join(os.getcwd(), f"results_{timestamp}")

    print(f"""
{C.WHITE}Where should we save the results?{C.RESET}

{C.DIM}The output directory will contain:
  \u2022 executive_summary.md - The main findings report
  \u2022 detailed_connections.csv - All domain connections
  \u2022 clusters.csv - Identified sock puppet groups
  \u2022 network_visualization.html - Interactive graph
  \u2022 And more...{C.RESET}
""")

    path = get_input(f"Output directory", default_output)

    # Ctrl+C = cancel
    if path is None:
        print_info("Cancelled.")
        return None

    path = os.path.expanduser(path)

    # Create directory if it doesn't exist
    if not os.path.exists(path):
        if confirm(f"Directory doesn't exist. Create it?"):
            try:
                os.makedirs(path, exist_ok=True)
                print_success(f"Created: {path}")
            except OSError as e:
                print_error(f"Failed to create directory: {e}")
                return None
        else:
            return None

    # Remember this directory for "View Previous Results"
    abs_path = os.path.abspath(path)
    remember_output_dir(abs_path)
    return abs_path
