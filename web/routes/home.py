"""
home.py - Main menu route.

GET / serves the main menu screen, which mirrors show_main_menu() from
puppetmaster.py. Pulls in any user-facing config flags (e.g., the
domains-loaded banner) so the web menu shows the same status the TUI does.
"""

from flask import Blueprint, render_template

# Import config from the existing pm_config module
try:
    from pm_config import load_config
    _HAS_PM_CONFIG = True
except ImportError:
    _HAS_PM_CONFIG = False
    def load_config():
        return {}


bp = Blueprint('home', __name__)


@bp.route('/')
def main_menu():
    """Render the main menu — equivalent to show_main_menu() in puppetmaster.py."""
    config = load_config() if _HAS_PM_CONFIG else {}
    return render_template(
        'menu.html',
        domains_ready_for_scan=config.get('domains_ready_for_scan', False),
        domains_ready_count=config.get('domains_ready_count', 0),
    )
