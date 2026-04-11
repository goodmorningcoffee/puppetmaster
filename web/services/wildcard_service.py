"""
wildcard_service.py - Wildcard DNS analyzer wrapper for the web GUI.

Wraps wildcardDNS_analyzer.quick_wildcard_check() and the WildcardAnalyzer
class. Two modes:

  - Quick check: synchronous, fast (DNS resolution only). Tests one or
    more domains for wildcard DNS by resolving random subdomains and
    checking whether they all return the same IP.

  - Full analysis: background, slow (multi-phase: DNS, certificates, HTTP
    fingerprinting, infrastructure correlation). Operates on one domain
    at a time. Streams progress events via the run_state pattern.
"""

import io
import sys
import threading
from typing import Dict, List, Optional

from . import run_state


def _get_quick_check():
    """Return the quick_wildcard_check function, or None if missing."""
    try:
        from wildcardDNS_analyzer import quick_wildcard_check
        return quick_wildcard_check
    except ImportError:
        return None


def _get_analyzer_class():
    """Return the WildcardAnalyzer class, or None if missing."""
    try:
        from wildcardDNS_analyzer import WildcardAnalyzer
        return WildcardAnalyzer
    except ImportError:
        return None


def run_quick_check(domains: List[str], timeout: float = 2.0) -> Dict:
    """
    Synchronously check a list of domains for wildcard DNS.

    Args:
        domains: List of base domains to check (e.g. ["example.com", "fake.io"])
        timeout: Per-domain DNS resolution timeout in seconds

    Returns:
        Dict mapping domain → {is_wildcard, wildcard_ip, confidence}
        plus metadata fields. Returns {} on missing dependency.
    """
    quick = _get_quick_check()
    if quick is None:
        return {}

    if not domains:
        return {}

    try:
        return quick(domains, timeout=timeout)
    except Exception as e:
        # Wrap any failure in a structured error
        return {"_error": str(e)}


def start_full_analysis_in_background(
    domain: str,
    spiderfoot_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """
    Start a full WildcardAnalyzer.run_full_analysis() in a background thread.

    Args:
        domain: Single target domain to analyze
        spiderfoot_dir: Optional path to SpiderFoot CSV exports for cross-correlation
        output_dir: Optional output directory for the analyzer's reports

    Returns:
        run_id (string)
    """
    run_id = run_state.create_run('wildcard_full')

    WildcardAnalyzer = _get_analyzer_class()
    if WildcardAnalyzer is None:
        run_state.mark_failed(
            run_id,
            "wildcardDNS_analyzer not importable",
        )
        return run_id

    if not domain or not domain.strip():
        run_state.mark_failed(run_id, "domain is required")
        return run_id

    domain = domain.strip()

    def _runner():
        run_state.append_event(
            run_id, 'info',
            f'Starting full wildcard analysis on {domain}',
            stage='Initializing',
            domain=domain,
        )

        try:
            analyzer = WildcardAnalyzer(
                domain=domain,
                spiderfoot_dir=spiderfoot_dir,
                output_dir=output_dir,
            )

            # WildcardAnalyzer.run_full_analysis() prints to stdout via the
            # `ui` module. We can't easily intercept those prints without
            # touching that code, so we capture stdout for the duration of
            # the run and emit captured lines as info events. This is a
            # tolerable hack — the alternative is refactoring the analyzer
            # which is out of scope for Phase 3.
            captured = io.StringIO()
            old_stdout = sys.stdout

            class _TeeStream:
                """Mirror writes to both the captured buffer AND emit per-line events."""
                def __init__(self, buf):
                    self._buf = buf
                    self._line_buf = ""

                def write(self, s):
                    if not s:
                        return
                    self._buf.write(s)
                    self._line_buf += s
                    while '\n' in self._line_buf:
                        line, self._line_buf = self._line_buf.split('\n', 1)
                        line = line.strip()
                        if line:
                            run_state.append_event(run_id, 'info', line)

                def flush(self):
                    pass

            sys.stdout = _TeeStream(captured)
            try:
                run_state.append_event(run_id, 'stage', 'Running analyzer phases...', stage='Running')
                result = analyzer.run_full_analysis()
            finally:
                sys.stdout = old_stdout

            run_state.append_event(
                run_id, 'success',
                'Full analysis complete',
                stage='Done',
            )

            run_state.mark_complete(run_id, {
                'domain': domain,
                'analysis': result,
            })

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            run_state.append_event(run_id, 'error', f'Exception: {e}')
            run_state.append_event(run_id, 'error', tb[:500])
            run_state.mark_failed(run_id, str(e))

    thread = threading.Thread(
        target=_runner,
        name=f"web-wildcard-{run_id}",
        daemon=True,
    )
    thread.start()

    return run_id
