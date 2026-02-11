"""
PUPPETMASTER UI Module
Cyberpunk Terminal HUD using rich library
"""

from .cyberpunk_hud import CyberpunkHUD, MENU_ITEMS as CYBERPUNK_MENU_ITEMS
from .colors import COLORS
from .descriptions import TOOL_DESCRIPTIONS, MENU_ITEMS
from .integration import run_gaming_hud_menu, map_hud_key_to_choice, run_cyberpunk_hud_menu

# Cyberpunk UI components for submenus
from .cyberpunk_ui import (
    RICH_AVAILABLE,
    CyberColors,
    cyber_header,
    cyber_menu,
    cyber_info,
    cyber_success,
    cyber_warning,
    cyber_error,
    cyber_prompt,
    cyber_confirm,
    cyber_status,
    cyber_divider,
    cyber_table,
    CyberProgress,
    cyber_submenu,
    cyber_wait,
    # Themed banners for submenus
    cyber_banner_discovery,
    cyber_banner_import,
    cyber_banner_spider,
    cyber_banner_queue,
    cyber_banner_analysis,
    cyber_banner_wildcard,
    cyber_banner_help,
    cyber_banner_config,
    cyber_banner_results,
    cyber_banner_kali,
    cyber_banner_workflow,
)

__all__ = [
    'CyberpunkHUD',
    'CYBERPUNK_MENU_ITEMS',
    'COLORS',
    'TOOL_DESCRIPTIONS',
    'MENU_ITEMS',
    'run_gaming_hud_menu',
    'run_cyberpunk_hud_menu',
    'map_hud_key_to_choice',
    # Cyberpunk UI components
    'RICH_AVAILABLE',
    'CyberColors',
    'cyber_header',
    'cyber_menu',
    'cyber_info',
    'cyber_success',
    'cyber_warning',
    'cyber_error',
    'cyber_prompt',
    'cyber_confirm',
    'cyber_status',
    'cyber_divider',
    'cyber_table',
    'CyberProgress',
    'cyber_submenu',
    'cyber_wait',
    # Themed banners for submenus
    'cyber_banner_discovery',
    'cyber_banner_import',
    'cyber_banner_spider',
    'cyber_banner_queue',
    'cyber_banner_analysis',
    'cyber_banner_wildcard',
    'cyber_banner_help',
    'cyber_banner_config',
    'cyber_banner_results',
    'cyber_banner_kali',
    'cyber_banner_workflow',
]
