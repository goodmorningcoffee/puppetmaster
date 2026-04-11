"""
results.py - View Previous Results routes (read-only).

Mirrors option [6] (view_previous_results) from the TUI as two routes:
  GET /menu/results               — list all known result directories
  GET /menu/results/<dirname>      — drill into one (executive summary + CSV tabs)
  GET /menu/results/<dirname>/csv/<csv_name> — fetch a single CSV as JSON
                                                 (used by the CSV tabs)
"""

from flask import Blueprint, abort, jsonify, render_template

from ..services.results_service import (
    STANDARD_CSV_FILES,
    find_result_directory_by_name,
    list_result_directories,
    read_csv_file,
    read_executive_summary,
)


bp = Blueprint('results', __name__)


@bp.route('/menu/results')
def results_list():
    """List all known result directories."""
    dirs = list_result_directories()
    return render_template(
        'results_list.html',
        dirs=dirs,
        empty=len(dirs) == 0,
    )


@bp.route('/menu/results/<path:dirname>')
def results_detail(dirname: str):
    """
    Show one result directory in detail.

    Renders the executive_summary.md as HTML and provides links/tabs to
    view each CSV file.
    """
    result_dir = find_result_directory_by_name(dirname)
    if result_dir is None:
        abort(404)

    summary_html = read_executive_summary(result_dir)

    # Find which CSV files actually exist
    available_csvs = []
    for csv_name in STANDARD_CSV_FILES:
        if (result_dir / csv_name).is_file():
            available_csvs.append(csv_name)

    return render_template(
        'results_detail.html',
        dirname=dirname,
        result_path=str(result_dir),
        summary_html=summary_html,
        available_csvs=available_csvs,
        has_summary=summary_html is not None,
    )


@bp.route('/menu/results/<path:dirname>/csv/<csv_name>')
def results_csv(dirname: str, csv_name: str):
    """
    Return a single CSV file's contents as JSON.

    Used by the detail page to populate CSV tabs lazily — only loads
    when the user clicks the tab. Cap at 500 rows for browser performance.
    """
    # Defense: only allow CSV files we know about
    if csv_name not in STANDARD_CSV_FILES:
        abort(404)

    result_dir = find_result_directory_by_name(dirname)
    if result_dir is None:
        abort(404)

    data = read_csv_file(result_dir, csv_name)
    if data is None:
        abort(404)

    return jsonify(data)
