"""
analysis.py - Run Puppet Analysis screen routes (Phase 3).

Mirrors option [5] from the TUI: run the full sock puppet detection
pipeline against a SpiderFoot exports directory. Long-running operation —
streams stage progress via /events/run/<run_id> and auto-redirects to
/menu/results/<basename> when complete.

Routes:
  GET  /menu/analysis                 — form (input dir, output dir, optional kali dir)
  POST /menu/analysis/run             — kick off pipeline, redirect to progress
  GET  /menu/analysis/progress/<id>   — live progress page
"""

import os
from datetime import datetime

from flask import Blueprint, abort, redirect, render_template, request, url_for

from ..services import run_state
from ..services.analysis_service import start_analysis_in_background
from ..services.results_service import list_result_directories


bp = Blueprint('analysis', __name__)


@bp.route('/menu/analysis')
def analysis_form():
    """Show the analysis form with directory pickers."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_output = os.path.abspath(f"./results_{timestamp}")
    previous = list_result_directories()
    return render_template(
        'analysis_form.html',
        default_output=default_output,
        previous_results=previous,
    )


@bp.route('/menu/analysis/run', methods=['POST'])
def analysis_run():
    """Start a new analysis run in the background."""
    input_dir = request.form.get('input_dir', '').strip()
    output_dir = request.form.get('output_dir', '').strip()
    kali_infra_dir = request.form.get('kali_infra_dir', '').strip() or None

    if not input_dir:
        return render_template(
            'analysis_form.html',
            default_output=output_dir or '',
            previous_results=list_result_directories(),
            error="Input directory is required.",
        )

    if not output_dir:
        return render_template(
            'analysis_form.html',
            default_output='',
            previous_results=list_result_directories(),
            error="Output directory is required.",
        )

    # Quick existence check before starting the background thread
    if not os.path.isdir(input_dir):
        return render_template(
            'analysis_form.html',
            default_output=output_dir,
            previous_results=list_result_directories(),
            error=f"Input directory does not exist: {input_dir}",
        )

    run_id = start_analysis_in_background(
        input_dir=input_dir,
        output_dir=output_dir,
        kali_infra_dir=kali_infra_dir,
    )

    return redirect(url_for('analysis.analysis_progress', run_id=run_id))


@bp.route('/menu/analysis/progress/<run_id>')
def analysis_progress(run_id: str):
    """Show the live progress page for an in-flight analysis."""
    run = run_state.get_run(run_id)
    if run is None:
        abort(404)
    return render_template('analysis_progress.html', run_id=run_id, run=run)
