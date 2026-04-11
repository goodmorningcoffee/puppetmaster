"""
load_domains.py - Load Domains screen routes (Phase 3, mutating).

Mirrors option [2] from the TUI: load a domain list either by uploading
a file or by picking from the existing files in domain_lists/.

Routes:
  GET  /menu/load-domains            — show form (upload + pick)
  POST /menu/load-domains/upload     — handle uploaded file
  POST /menu/load-domains/pick       — load from existing file
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..services.domain_lists_service import (
    list_domain_files,
    parse_domain_list_file,
    save_uploaded_list,
)
from ..services.queue_mutations_service import add_domains_to_loaded


bp = Blueprint('load_domains', __name__)


@bp.route('/menu/load-domains')
def load_domains_screen():
    """Show the Load Domains form (upload + existing file picker)."""
    files = list_domain_files()
    return render_template('load_domains.html', files=files, message=None)


@bp.route('/menu/load-domains/upload', methods=['POST'])
def upload():
    """
    Handle file upload.

    The form sends a file part named 'file'. We save it to domain_lists/
    and add the parsed domains to the loaded queue (config['pending_domains']).
    """
    files = list_domain_files()

    upload = request.files.get('file')
    if not upload or not upload.filename:
        return render_template(
            'load_domains.html',
            files=files,
            message=("error", "No file selected."),
        )

    # Read content (with size cap implicit in domain_lists_service)
    content = upload.read().decode('utf-8', errors='replace')

    # Save to domain_lists/ with the original filename (sanitized)
    saved_path, err = save_uploaded_list(upload.filename, content)
    if err:
        return render_template(
            'load_domains.html',
            files=files,
            message=("error", f"Failed to save: {err}"),
        )

    # Parse and add to loaded queue
    domains, parse_err = parse_domain_list_file(saved_path.split('/')[-1])
    if parse_err:
        return render_template(
            'load_domains.html',
            files=list_domain_files(),
            message=("warning", f"Saved but couldn't parse: {parse_err}"),
        )

    added = add_domains_to_loaded(domains)
    return render_template(
        'load_domains.html',
        files=list_domain_files(),
        message=("success", f"Saved {upload.filename} and added {added} domain(s) to queue."),
    )


@bp.route('/menu/load-domains/pick', methods=['POST'])
def pick():
    """
    Load an existing domain list file by basename.

    Form sends `filename` — basename only, validated by domain_lists_service.
    """
    filename = request.form.get('filename', '').strip()
    if not filename:
        return render_template(
            'load_domains.html',
            files=list_domain_files(),
            message=("error", "No file selected."),
        )

    domains, err = parse_domain_list_file(filename)
    if err:
        return render_template(
            'load_domains.html',
            files=list_domain_files(),
            message=("error", f"Failed to load {filename}: {err}"),
        )

    added = add_domains_to_loaded(domains)
    return render_template(
        'load_domains.html',
        files=list_domain_files(),
        message=("success", f"Loaded {filename}: added {added} new domain(s) ({len(domains)} total in file)."),
    )
