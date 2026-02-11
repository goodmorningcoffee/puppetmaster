"""
PUPPETMASTER Kali Linux Integration Module

This module provides Kali Linux tool integration for enhanced OSINT capabilities.
When running on Kali, additional tools are automatically installed and made available.
On non-Kali systems, the standard PuppetMaster pipeline is used unchanged.

Modules:
    detect      - OS detection (Kali vs other)
    bootstrap   - Kali tool auto-installation
    registry    - Tool availability tracking
    modes       - Scan mode selection (Ghost/Stealth/Standard/Deep)
    aggregator  - Domain discovery aggregation
    tools/      - Individual tool wrappers
"""

from .detect import detect_os, is_kali, get_os_info
from .bootstrap import bootstrap_kali_tools, check_kali_tools
from .registry import ToolRegistry, get_available_tools
from .modes import ScanMode, get_mode_tools, select_scan_mode

__all__ = [
    'detect_os',
    'is_kali',
    'get_os_info',
    'bootstrap_kali_tools',
    'check_kali_tools',
    'ToolRegistry',
    'get_available_tools',
    'ScanMode',
    'get_mode_tools',
    'select_scan_mode',
]

__version__ = '1.0.0'
