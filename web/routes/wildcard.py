"""
wildcard.py - Wildcard DNS Analyzer screen routes (Phase 3).

Mirrors option [11] from the TUI: detect wildcard DNS in domains so you
can filter false-positive "shared infrastructure" signals out of the
main analysis.

Two modes:
  - Quick: synchronous, fast (DNS only). Operates on a list of domains.
  - Full: background, slow (multi-phase: DNS + crt.sh + HTTP fingerprinting
          + infra correlation). Operates on one domain at a time. SSE-driven.

Routes:
  GET  /menu/wildcard                 — form (both modes)
  POST /menu/wildcard/quick           — synchronous quick check
  POST /menu/wildcard/full            — kick off background full analysis
  GET  /menu/wildcard/progress/<id>   — live progress page for full mode
"""

from flask import Blueprint, abort, redirect, render_template, request, url_for

from ..services import run_state
from ..services.wildcard_service import (
    run_quick_check,
    start_full_analysis_in_background,
)


bp = Blueprint('wildcard', __name__)


@bp.route('/menu/wildcard')
def wildcard_form():
    """Show the wildcard analyzer form (quick + full mode)."""
    return render_template('wildcard_form.html')


@bp.route('/menu/wildcard/quick', methods=['POST'])
def wildcard_quick():
    """
    Run synchronous quick wildcard check on a list of domains.

    Form fields:
      domains  — newline-separated list of domains
    """
    raw = request.form.get('domains', '').strip()
    if not raw:
        return render_template(
            'wildcard_form.html',
            error="At least one domain is required.",
        )

    # Parse domains: one per line, strip whitespace and comments
    domains = []
    for line in raw.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            domains.append(line)

    if not domains:
        return render_template(
            'wildcard_form.html',
            error="No valid domains found.",
        )

    raw_results = run_quick_check(domains)

    # Handle missing dependency case
    if not raw_results or raw_results.get("_error"):
        error_msg = (
            raw_results.get("_error")
            if raw_results
            else "wildcardDNS_analyzer module not available"
        )
        return render_template(
            'wildcard_form.html',
            error=f"Quick check failed: {error_msg}",
        )

    # Convert to a sorted list for the template
    results = []
    wildcard_count = 0
    for domain in domains:
        info = raw_results.get(domain, {}) or {}
        is_wildcard = bool(info.get('is_wildcard', False))
        if is_wildcard:
            wildcard_count += 1
        results.append({
            'domain': domain,
            'is_wildcard': is_wildcard,
            'wildcard_ip': info.get('wildcard_ip', '—'),
            'confidence': info.get('confidence', '—'),
        })

    return render_template(
        'wildcard_quick_result.html',
        results=results,
        total=len(results),
        wildcard_count=wildcard_count,
    )


@bp.route('/menu/wildcard/full', methods=['POST'])
def wildcard_full():
    """
    Start a background WildcardAnalyzer.run_full_analysis() on one domain.

    Form fields:
      domain          — single target domain
      spiderfoot_dir  — optional path to SpiderFoot exports for correlation
    """
    domain = request.form.get('domain', '').strip()
    spiderfoot_dir = request.form.get('spiderfoot_dir', '').strip() or None

    if not domain:
        return render_template(
            'wildcard_form.html',
            error="Target domain is required.",
        )

    run_id = start_full_analysis_in_background(
        domain=domain,
        spiderfoot_dir=spiderfoot_dir,
    )

    return redirect(url_for('wildcard.wildcard_progress', run_id=run_id))


@bp.route('/menu/wildcard/progress/<run_id>')
def wildcard_progress(run_id: str):
    """Show the live progress page for an in-flight full analysis."""
    run = run_state.get_run(run_id)
    if run is None:
        abort(404)
    return render_template('wildcard_progress.html', run_id=run_id, run=run)
