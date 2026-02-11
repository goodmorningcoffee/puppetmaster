#!/usr/bin/env python3
"""
scanner.py - SpiderFoot Batch Scanner

Runs SpiderFoot scans on a queue of domains with configurable parallelism.
Handles progress tracking, error recovery, and CSV export collection.
"""

import os
import subprocess
import time
import shutil
from pathlib import Path
from typing import Optional, Callable, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .jobs import JobTracker, ScanJob, JobStatus


class SpiderFootScanner:
    """
    Manages batch SpiderFoot scanning with job queue.

    Features:
    - Configurable parallel scan limit
    - Progress tracking and callbacks
    - Automatic retry on failure
    - Resume capability after interruption
    """

    def __init__(
        self,
        spiderfoot_path: str,
        output_dir: str,
        max_parallel: int = 3,
        job_tracker: Optional[JobTracker] = None,
        spiderfoot_python: Optional[str] = None
    ):
        """
        Initialize the scanner.

        Args:
            spiderfoot_path: Path to sf.py (SpiderFoot CLI)
            output_dir: Directory to save CSV exports
            max_parallel: Maximum concurrent scans (default: 3)
            job_tracker: Optional existing JobTracker instance
            spiderfoot_python: Path to Python interpreter in SpiderFoot venv
        """
        self.sf_path = Path(spiderfoot_path)
        self.output_dir = Path(output_dir)
        self.max_parallel = max_parallel

        # Use venv python if provided, otherwise try to find it
        if spiderfoot_python and os.path.exists(spiderfoot_python):
            self.sf_python = spiderfoot_python
        else:
            # Try to find venv python relative to sf.py
            venv_python = self.sf_path.parent / "venv" / "bin" / "python3"
            if venv_python.exists():
                self.sf_python = str(venv_python)
            else:
                self.sf_python = "python3"  # Fallback to system python

        # Validate SpiderFoot path
        if not self.sf_path.exists():
            raise FileNotFoundError(f"SpiderFoot not found at: {spiderfoot_path}")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize or use provided job tracker
        self.tracker = job_tracker or JobTracker()
        self.tracker.set_config(
            spiderfoot_path=str(self.sf_path),
            output_dir=str(self.output_dir)
        )

        # Callbacks
        self.on_scan_start: Optional[Callable[[str], None]] = None
        self.on_scan_complete: Optional[Callable[[str, str], None]] = None
        self.on_scan_failed: Optional[Callable[[str, str], None]] = None
        self.on_progress: Optional[Callable[[int, int, int], None]] = None
        # New: module-level progress callback(domain, module, results_count, file_size_kb)
        self.on_module_progress: Optional[Callable[[str, str, int, float], None]] = None

        # Control flag for stopping
        self._stop_requested = False

    @staticmethod
    def find_spiderfoot() -> Optional[str]:
        """
        Try to find SpiderFoot installation.

        Returns:
            Path to sf.py if found, None otherwise
        """
        # Common locations to check
        common_paths = [
            # Current directory
            Path.cwd() / "spiderfoot" / "sf.py",
            Path.cwd() / "sf.py",
            # Home directory
            Path.home() / "spiderfoot" / "sf.py",
            Path.home() / "tools" / "spiderfoot" / "sf.py",
            # Opt directory (Linux)
            Path("/opt/spiderfoot/sf.py"),
            # Kali default
            Path("/usr/share/spiderfoot/sf.py"),
        ]

        for path in common_paths:
            if path.exists():
                return str(path)

        # Try using 'which' command
        try:
            result = subprocess.run(
                ["which", "sf.py"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

        return None

    @staticmethod
    def verify_spiderfoot(sf_path: str, sf_python: Optional[str] = None) -> tuple[bool, str]:
        """
        Verify SpiderFoot installation works.

        Args:
            sf_path: Path to sf.py
            sf_python: Path to Python interpreter (uses venv python if available)

        Returns:
            (success, message)
        """
        # Determine which python to use
        if sf_python and os.path.exists(sf_python):
            python_cmd = sf_python
        else:
            # Try to find venv python relative to sf.py
            venv_python = Path(sf_path).parent / "venv" / "bin" / "python3"
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = "python3"

        try:
            result = subprocess.run(
                [python_cmd, sf_path, "--help"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and "SpiderFoot" in result.stdout:
                return True, "SpiderFoot verified successfully"
            else:
                return False, f"SpiderFoot check failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "SpiderFoot check timed out"
        except Exception as e:
            return False, f"SpiderFoot check error: {str(e)}"

    def run_single_scan(self, domain: str, progress_callback: Optional[Callable] = None) -> tuple[bool, str, Optional[str]]:
        """
        Run a single SpiderFoot scan with real-time progress tracking.

        Args:
            domain: Domain to scan
            progress_callback: Optional callback(module, results_count, file_size_kb) for progress

        Returns:
            (success, message, csv_path)
        """
        import re
        import threading
        import io

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_domain = domain.replace(".", "_")
        csv_filename = f"{safe_domain}_{timestamp}.csv"
        csv_path = self.output_dir / csv_filename

        # Build SpiderFoot command (no -q flag to get stderr logs)
        cmd = [
            self.sf_python,
            str(self.sf_path),
            "-s", domain,
            "-u", "all",      # Use all module types
            "-o", "csv",      # Output format (goes to stdout)
            # No -q flag - we want stderr for progress tracking
        ]

        # Progress tracking state
        progress_state = {
            'current_module': None,
            'modules_completed': 0,
            'results_found': 0,
            'file_size_kb': 0.0,
            'rows_written': 0,  # Count actual CSV rows written
            'last_stderr': None,  # Last stderr line for debugging
        }

        # Debug log file for stderr (helps diagnose module detection)
        debug_log_path = self.output_dir / "_stderr_debug.log"

        def parse_stderr_line(line: str):
            """Parse SpiderFoot stderr for progress info"""
            line = line.strip()
            if not line:
                return

            progress_state['last_stderr'] = line

            # Log stderr for debugging (append mode)
            try:
                with open(debug_log_path, 'a') as f:
                    f.write(f"{domain}: {line}\n")
            except Exception:
                pass

            # Try multiple patterns for module detection:
            # Pattern 1: [*] sfp_xxx: ... (common format)
            # Pattern 2: sfp_xxx module ...
            # Pattern 3: Running sfp_xxx
            # Pattern 4: Module sfp_xxx
            # Pattern 5: Just sfp_ anywhere in line
            module_patterns = [
                r'\[\*\]\s*(sfp_\w+)',           # [*] sfp_xxx
                r'(?:Running|Starting|Module)\s+(sfp_\w+)',  # Running sfp_xxx
                r'(sfp_\w+)\s+module',           # sfp_xxx module
                r'(sfp_\w+):\s',                 # sfp_xxx:
                r'\b(sfp_\w+)\b',                # Any sfp_ word boundary
            ]

            for pattern in module_patterns:
                module_match = re.search(pattern, line, re.IGNORECASE)
                if module_match:
                    progress_state['current_module'] = module_match.group(1)
                    break

            # Module completed
            if 'module' in line.lower() and 'complete' in line.lower():
                progress_state['modules_completed'] += 1

            # Results found: various patterns
            result_match = re.search(r'(\d+)\s+(?:result|record|entr)', line.lower())
            if result_match:
                progress_state['results_found'] += int(result_match.group(1))

            # Call progress callback if provided
            if progress_callback:
                try:
                    progress_callback(
                        progress_state['current_module'],
                        progress_state['results_found'],
                        progress_state['file_size_kb']
                    )
                except Exception:
                    pass

        try:
            # Use Popen for real-time output capture
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )

            # Collect stdout (CSV data)
            stdout_data = io.StringIO()

            # Thread to read stderr for progress
            def read_stderr():
                try:
                    for line in process.stderr:
                        parse_stderr_line(line)
                except Exception:
                    pass

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            # Read stdout and write to file incrementally
            # Also count actual CSV rows as a reliable progress indicator
            row_count = 0
            with open(csv_path, 'w', encoding='utf-8') as csv_file:
                for line in process.stdout:
                    csv_file.write(line)
                    stdout_data.write(line)

                    # Count data rows (skip header)
                    if row_count == 0 or not line.startswith('Source,'):
                        row_count += 1

                    # Update progress state
                    progress_state['file_size_kb'] = csv_file.tell() / 1024
                    progress_state['rows_written'] = max(0, row_count - 1)  # Exclude header

                    # Use rows_written as results_found (more reliable than stderr parsing)
                    if progress_state['rows_written'] > progress_state['results_found']:
                        progress_state['results_found'] = progress_state['rows_written']

                    if progress_callback:
                        try:
                            progress_callback(
                                progress_state['current_module'],
                                progress_state['results_found'],
                                progress_state['file_size_kb']
                            )
                        except Exception:
                            pass

            # Wait for process to complete
            process.wait(timeout=1800)
            stderr_thread.join(timeout=5)

            # Check results
            stdout = stdout_data.getvalue().strip()

            if stdout:
                lines = stdout.split('\n')
                has_data = len(lines) > 1 and not all(
                    l.startswith('Source,') or l.strip() == '' for l in lines
                )

                if has_data:
                    result_count = len(lines) - 1
                    return True, f"Scan completed ({result_count} results)", str(csv_path)
                else:
                    return True, "Scan completed (no data found)", str(csv_path)

            # No stdout at all
            if process.returncode != 0:
                return False, f"Scan error (exit code {process.returncode})", None
            else:
                return False, "Scan produced no output", None

        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except Exception:
                pass
            return False, "Scan timed out after 30 minutes", None
        except Exception as e:
            return False, f"Scan error: {str(e)}", None

    def _process_job(self, job: ScanJob) -> ScanJob:
        """Process a single scan job."""
        domain = job.domain

        # Update status
        job.mark_running()
        self.tracker.save_state()

        if self.on_scan_start:
            self.on_scan_start(domain)

        # Create progress callback that includes domain
        def module_progress_wrapper(module, results_count, file_size_kb):
            if self.on_module_progress:
                self.on_module_progress(domain, module, results_count, file_size_kb)

        # Run the scan with progress callback
        success, message, csv_path = self.run_single_scan(domain, progress_callback=module_progress_wrapper)

        if success:
            job.mark_completed(csv_path)
            if self.on_scan_complete:
                self.on_scan_complete(domain, csv_path)
        else:
            job.mark_failed(message)
            if self.on_scan_failed:
                self.on_scan_failed(domain, message)

        self.tracker.save_state()
        return job

    def process_queue(
        self,
        progress_callback: Optional[Callable[[int, int, int], None]] = None
    ) -> dict:
        """
        Process all pending jobs in the queue.

        Args:
            progress_callback: Optional callback(completed, failed, total)

        Returns:
            Summary statistics
        """
        self._stop_requested = False
        pending = self.tracker.get_pending()

        if not pending:
            return {'completed': 0, 'failed': 0, 'total': 0}

        total = len(pending)
        completed = 0
        failed = 0

        # Process with thread pool
        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            # Submit all jobs
            future_to_job = {
                executor.submit(self._process_job, job): job
                for job in pending
            }

            # Process as they complete
            for future in as_completed(future_to_job):
                if self._stop_requested:
                    # Cancel remaining futures
                    for f in future_to_job:
                        f.cancel()
                    break

                job = future_to_job[future]
                try:
                    result = future.result()
                    if result.status == JobStatus.COMPLETED.value:
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    job.mark_failed(str(e))
                    self.tracker.save_state()

                if progress_callback:
                    progress_callback(completed, failed, total)

        return {
            'completed': completed,
            'failed': failed,
            'total': total
        }

    def stop(self):
        """Request stop of queue processing."""
        self._stop_requested = True

    def add_domains(self, domains: List[str]) -> int:
        """
        Add domains to the scan queue.

        Args:
            domains: List of domain names

        Returns:
            Number of new domains added
        """
        return self.tracker.add_domains(domains)

    def get_stats(self) -> dict:
        """Get queue statistics."""
        return self.tracker.get_stats()

    def get_completed_csvs(self) -> List[str]:
        """Get paths to all completed CSV files."""
        return [
            job.csv_path
            for job in self.tracker.get_completed()
            if job.csv_path and Path(job.csv_path).exists()
        ]

    def retry_failed(self) -> int:
        """Retry all failed scans."""
        return self.tracker.retry_failed()


# =============================================================================
# SPIDERFOOT INSTALLATION GUIDE
# =============================================================================

INSTALL_GUIDE = {
    'linux': """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SPIDERFOOT INSTALLATION - Linux (Debian/Ubuntu/Kali)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Copy and paste these commands:

  # Clone SpiderFoot
  git clone https://github.com/smicallef/spiderfoot.git
  cd spiderfoot

  # Install dependencies
  pip3 install -r requirements.txt

  # Test installation
  python3 sf.py --help

  # (Optional) Start web UI
  python3 sf.py -l 127.0.0.1:5001

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After installation, note the path to sf.py (e.g., /home/user/spiderfoot/sf.py)
You'll need to provide this path when running SpiderFoot scans.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""",

    'mac': """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SPIDERFOOT INSTALLATION - macOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Copy and paste these commands:

  # Install prerequisites (if needed)
  brew install python3 git

  # Clone SpiderFoot
  git clone https://github.com/smicallef/spiderfoot.git
  cd spiderfoot

  # Install dependencies
  pip3 install -r requirements.txt

  # Test installation
  python3 sf.py --help

  # (Optional) Start web UI
  python3 sf.py -l 127.0.0.1:5001

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After installation, note the path to sf.py (e.g., /Users/you/spiderfoot/sf.py)
You'll need to provide this path when running SpiderFoot scans.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""",

    'windows': """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SPIDERFOOT INSTALLATION - Windows
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Install Python 3 from https://www.python.org/downloads/
   (Make sure to check "Add Python to PATH")

2. Install Git from https://git-scm.com/download/win

3. Open Command Prompt or PowerShell and run:

  # Clone SpiderFoot
  git clone https://github.com/smicallef/spiderfoot.git
  cd spiderfoot

  # Install dependencies
  pip install -r requirements.txt

  # Test installation
  python sf.py --help

  # (Optional) Start web UI
  python sf.py -l 127.0.0.1:5001

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After installation, note the path to sf.py (e.g., C:\\Users\\You\\spiderfoot\\sf.py)
You'll need to provide this path when running SpiderFoot scans.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
}


def get_install_guide(os_type: str) -> str:
    """Get installation guide for the specified OS."""
    return INSTALL_GUIDE.get(os_type.lower(), INSTALL_GUIDE['linux'])
