"""
delete_lists.py - Delete domain list files (Phase 3, mutating).

Mirrors option [D] from the TUI. Lists files in domain_lists/ with
multi-select checkboxes. POST deletes the selected files.

Routes:
  GET  /menu/delete-lists           — show file list with checkboxes
  POST /menu/delete-lists/delete    — delete selected files (multi)
"""

from flask import Blueprint, render_template, request

from ..services.domain_lists_service import delete_domain_files, list_domain_files


bp = Blueprint('delete_lists', __name__)


@bp.route('/menu/delete-lists')
def delete_lists_screen():
    """Show the file list with checkboxes."""
    files = list_domain_files()
    return render_template('delete_lists.html', files=files, message=None)


@bp.route('/menu/delete-lists/delete', methods=['POST'])
def delete_selected():
    """Delete the files whose checkbox names are submitted."""
    # The form submits multiple `selected` values (one per checked file)
    selected = request.form.getlist('selected')
    if not selected:
        return render_template(
            'delete_lists.html',
            files=list_domain_files(),
            message=("warning", "No files selected."),
        )

    deleted, errors = delete_domain_files(selected)

    if errors and not deleted:
        msg = ("error", f"Failed: {'; '.join(errors)}")
    elif errors:
        msg = ("warning", f"Deleted {len(deleted)}, failed {len(errors)}: {'; '.join(errors)}")
    else:
        msg = ("success", f"Deleted {len(deleted)} file(s).")

    return render_template(
        'delete_lists.html',
        files=list_domain_files(),
        message=msg,
    )
