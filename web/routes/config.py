"""
config.py - Configuration screen route (read-only).

Mirrors option [7] (show_config) from the TUI but as a read-only display.
Renders ~/.puppetmaster_config.json as a key/value table with type-aware
formatting.

Editing config values is intentionally NOT in scope for Phase 2 — users
can edit the JSON file directly with any text editor. Web-based editing
is a Phase 3 enhancement if needed.
"""

from typing import Any, List

from flask import Blueprint, render_template

try:
    from pm_config import load_config, CONFIG_FILE
    _HAS_PM_CONFIG = True
except ImportError:
    _HAS_PM_CONFIG = False
    CONFIG_FILE = None
    def load_config():
        return {}


bp = Blueprint('config', __name__)


def _classify_value(value: Any) -> str:
    """Return a CSS class name for type-aware rendering."""
    if isinstance(value, bool):
        return 'bool-true' if value else 'bool-false'
    if isinstance(value, (int, float)):
        return 'numeric'
    if isinstance(value, list):
        return 'list'
    if isinstance(value, dict):
        return 'dict'
    if isinstance(value, str):
        # Heuristic: paths are strings starting with / or ~
        if value.startswith(('/', '~', './')):
            return 'path'
        return 'string'
    return 'unknown'


def _format_value(value: Any) -> Any:
    """Pre-format a config value for display in the template."""
    if isinstance(value, list):
        return value  # template will iterate
    if isinstance(value, dict):
        return value
    return str(value) if value is not None else ''


@bp.route('/menu/config')
def config_screen():
    """Render the configuration screen."""
    config = load_config() if _HAS_PM_CONFIG else {}

    # Build a list of (key, value, type, formatted) tuples for the template
    entries = []
    for key in sorted(config.keys()):
        value = config[key]
        entries.append({
            'key': key,
            'value': _format_value(value),
            'type': _classify_value(value),
            'is_list': isinstance(value, list),
            'is_dict': isinstance(value, dict),
            'count': len(value) if isinstance(value, (list, dict, str)) else None,
        })

    return render_template(
        'config.html',
        entries=entries,
        config_file_path=str(CONFIG_FILE) if CONFIG_FILE else 'unavailable',
        empty=len(entries) == 0,
        pm_config_available=_HAS_PM_CONFIG,
    )
