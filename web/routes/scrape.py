"""
scrape.py - Scrape Domains screen routes (Phase 3, mutating + long-running).

Mirrors option [1] from the TUI: scrape search engines for domains
matching keywords. Long-running operation — kicks off a background
thread and streams progress via /events/run/<run_id>.

Routes:
  GET  /menu/scrape                  — form (keywords, engines, max results)
  POST /menu/scrape/run              — start the scrape, redirect to progress
  GET  /menu/scrape/progress/<id>    — live progress page (SSE-driven)
  GET  /menu/scrape/result/<id>      — final result list with checkboxes
  POST /menu/scrape/commit/<id>      — commit selected domains to loaded queue
"""

from flask import Blueprint, abort, redirect, render_template, request, url_for

from ..services import run_state
from ..services.scrape_service import start_scrape_in_background
from ..services.queue_mutations_service import add_domains_to_loaded
from ..services.domain_lists_service import save_domain_list


bp = Blueprint('scrape', __name__)


@bp.route('/menu/scrape')
def scrape_form():
    """Show the scrape configuration form."""
    return render_template('scrape_form.html')


@bp.route('/menu/scrape/run', methods=['POST'])
def scrape_run():
    """
    Start a new scrape in the background.

    Form fields:
      keywords        — newline or comma-separated list of search terms
      max_results     — int, results per keyword per engine
      use_google      — checkbox
      use_duckduckgo  — checkbox
    """
    raw = request.form.get('keywords', '').strip()
    if not raw:
        return render_template(
            'scrape_form.html',
            error="At least one keyword is required.",
        )

    # Parse keywords — accept both newline and comma separators
    keywords = []
    for line in raw.replace(',', '\n').split('\n'):
        kw = line.strip()
        if kw:
            keywords.append(kw)

    if not keywords:
        return render_template(
            'scrape_form.html',
            error="No valid keywords found.",
        )

    try:
        max_results = int(request.form.get('max_results', '50'))
    except ValueError:
        max_results = 50
    max_results = max(1, min(max_results, 200))  # clamp to sane range

    use_google = request.form.get('use_google') == 'on'
    use_duckduckgo = request.form.get('use_duckduckgo') == 'on'

    run_id = start_scrape_in_background(
        keywords=keywords,
        max_results_per_keyword=max_results,
        use_google=use_google,
        use_duckduckgo=use_duckduckgo,
    )

    return redirect(url_for('scrape.scrape_progress', run_id=run_id))


@bp.route('/menu/scrape/progress/<run_id>')
def scrape_progress(run_id: str):
    """Show the live progress page for an in-flight scrape."""
    run = run_state.get_run(run_id)
    if run is None:
        abort(404)
    return render_template('scrape_progress.html', run_id=run_id, run=run)


@bp.route('/menu/scrape/result/<run_id>')
def scrape_result(run_id: str):
    """
    Show the final result of a completed scrape.

    Lists discovered domains with checkboxes for filtering. The user can
    commit selected domains to the loaded queue and optionally save to a file.
    """
    run = run_state.get_run(run_id)
    if run is None:
        abort(404)

    if run['status'] != 'completed':
        # Still running or failed — kick back to progress page
        return redirect(url_for('scrape.scrape_progress', run_id=run_id))

    result = run.get('result') or {}
    domains = result.get('domains', [])
    return render_template(
        'scrape_result.html',
        run_id=run_id,
        run=run,
        domains=domains,
        domain_count=len(domains),
        keywords=result.get('keywords', []),
        errors=result.get('errors', []),
    )


@bp.route('/menu/scrape/commit/<run_id>', methods=['POST'])
def scrape_commit(run_id: str):
    """
    Commit selected domains from a completed scrape.

    Form sends:
      selected     — list of domains to commit (checkbox values)
      save_as      — optional filename to also save the list to disk
    """
    run = run_state.get_run(run_id)
    if run is None:
        abort(404)
    if run['status'] != 'completed':
        return redirect(url_for('scrape.scrape_progress', run_id=run_id))

    selected = request.form.getlist('selected')
    if not selected:
        return render_template(
            'scrape_result.html',
            run_id=run_id,
            run=run,
            domains=(run.get('result') or {}).get('domains', []),
            domain_count=len((run.get('result') or {}).get('domains', [])),
            keywords=(run.get('result') or {}).get('keywords', []),
            errors=(run.get('result') or {}).get('errors', []),
            message=("warning", "No domains selected."),
        )

    added = add_domains_to_loaded(selected)

    # Optionally save to a file
    save_as = request.form.get('save_as', '').strip()
    save_msg = ""
    if save_as:
        if not save_as.endswith('.txt'):
            save_as = save_as + '.txt'
        saved_path, save_err = save_domain_list(save_as, selected)
        if save_err:
            save_msg = f" (file save failed: {save_err})"
        else:
            save_msg = f" Saved to {save_as}."

    # Redirect to the queue so the user sees the result
    return render_template(
        'scrape_result.html',
        run_id=run_id,
        run=run,
        domains=(run.get('result') or {}).get('domains', []),
        domain_count=len((run.get('result') or {}).get('domains', [])),
        keywords=(run.get('result') or {}).get('keywords', []),
        errors=(run.get('result') or {}).get('errors', []),
        message=("success", f"Added {added} domain(s) to loaded queue.{save_msg}"),
    )
