"""
PUPPETMASTER Color Scheme
Gaming HUD inspired colors using rich styling
"""

COLORS = {
    # Primary borders and structure
    "border": "bright_cyan",
    "border_alt": "cyan",
    "header": "bold bright_white",
    "accent": "bright_magenta",
    "accent_alt": "magenta",

    # Status indicators
    "standby": "bright_yellow",
    "active": "bright_green",
    "scanning": "bright_cyan",
    "error": "bright_red",
    "warning": "yellow",

    # Progress bars
    "progress_full": "bright_green",
    "progress_partial": "yellow",
    "progress_empty": "dim white",

    # Menu styling
    "selected": "bold bright_white on blue",
    "selected_key": "bold bright_yellow on blue",
    "unselected": "white",
    "unselected_key": "bright_yellow",
    "category": "bold bright_cyan",
    "category_line": "dim cyan",

    # Text styling
    "title": "bold bright_magenta",
    "subtitle": "bright_cyan",
    "description": "white",
    "hint": "dim bright_white",
    "bullet": "bright_green",
    "next_step": "bright_yellow",

    # Banner colors
    "banner_puppet": "bright_magenta",
    "banner_master": "bright_yellow",
    "banner_info": "white",
    "banner_quote": "dim white",

    # Stats bar
    "stat_label": "dim white",
    "stat_value": "bright_white",
    "stat_high": "bright_green",
    "stat_medium": "yellow",
    "stat_low": "bright_red",
}

# Rich style strings for common uses
STYLES = {
    "panel_border": "bright_cyan",
    "panel_title": "bold bright_magenta",
    "panel_subtitle": "bright_cyan",
    "menu_category": "bold bright_cyan",
    "menu_selected": "bold white on blue",
    "menu_normal": "white",
    "status_ok": "bold bright_green",
    "status_warn": "bold yellow",
    "status_error": "bold bright_red",
}
