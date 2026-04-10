"""
help.py - Help & Documentation routes.

Mirrors the existing pm_help screens (overview, signals, outputs, install
guide) as web pages. Pure read-only — these screens have no side effects,
making them the safest first menu option to wire up end-to-end.
"""

from flask import Blueprint, render_template


bp = Blueprint('help', __name__)


@bp.route('/help')
def help_index():
    """Help landing page — links to each sub-section."""
    return render_template('help.html')


@bp.route('/help/overview')
def help_overview():
    """The 'how PUPPETMASTER works' overview screen."""
    return render_template('help_overview.html')


@bp.route('/help/signals')
def help_signals():
    """Signal classification reference (smoking guns vs strong vs weak)."""
    return render_template('help_signals.html')


@bp.route('/help/outputs')
def help_outputs():
    """Output file reference — what each generated file contains."""
    return render_template('help_outputs.html')
