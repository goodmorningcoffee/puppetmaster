"""
Scan Mode Selection Module

Provides different scan modes with varying levels of stealth vs thoroughness:
- GHOST: Passive only, zero target contact
- STEALTH: Light touch, 1-2 requests per domain
- STANDARD: Balanced reconnaissance
- DEEP: Maximum coverage, high noise

Only available when running on Kali with tools installed.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from enum import Enum

from .registry import get_registry, ToolInfo
from .bootstrap import ToolCategory


class ScanMode(Enum):
    """Available scan modes"""
    GHOST = "ghost"           # Passive only
    STEALTH = "stealth"       # Light touch
    STANDARD = "standard"     # Balanced (default)
    DEEP = "deep"             # Maximum coverage


@dataclass
class ModeConfig:
    """Configuration for a scan mode"""
    mode: ScanMode
    name: str
    description: str
    target_contact: str       # None, Minimal, Moderate, High
    detection_risk: str       # None, Low, Medium, High
    tools: Dict[str, List[str]]  # category -> list of tool commands
    spiderfoot_enabled: bool
    nmap_enabled: bool
    active_dns: bool          # Active DNS enumeration
    subdomain_brute: bool     # Subdomain brute-forcing


# Mode definitions
MODE_CONFIGS: Dict[ScanMode, ModeConfig] = {
    ScanMode.GHOST: ModeConfig(
        mode=ScanMode.GHOST,
        name="GHOST MODE",
        description="Passive only - zero target contact",
        target_contact="None",
        detection_risk="None",
        tools={
            "discovery": ["theHarvester"],  # passive mode only
            "scanning": [],                  # no active scanning
            "analysis": ["exiftool"],        # analyze cached/downloaded content
        },
        spiderfoot_enabled=False,
        nmap_enabled=False,
        active_dns=False,
        subdomain_brute=False,
    ),

    ScanMode.STEALTH: ModeConfig(
        mode=ScanMode.STEALTH,
        name="STEALTH MODE",
        description="Light touch - 1-2 requests per domain",
        target_contact="Minimal",
        detection_risk="Low",
        tools={
            "discovery": ["theHarvester", "amass"],  # passive + light active
            "scanning": ["whatweb", "sslscan"],      # single request tools
            "analysis": ["exiftool"],
        },
        spiderfoot_enabled=False,  # Too noisy
        nmap_enabled=False,
        active_dns=True,           # Basic DNS lookups OK
        subdomain_brute=False,
    ),

    ScanMode.STANDARD: ModeConfig(
        mode=ScanMode.STANDARD,
        name="STANDARD MODE",
        description="Balanced reconnaissance",
        target_contact="Moderate",
        detection_risk="Medium",
        tools={
            "discovery": ["theHarvester", "amass", "sublist3r", "fierce"],
            "scanning": ["whatweb", "sslscan", "dnsrecon", "wafw00f"],
            "analysis": ["exiftool", "metagoofil"],
            "cross": ["dmitry"],
        },
        spiderfoot_enabled=True,
        nmap_enabled=False,        # Still skip port scanning
        active_dns=True,
        subdomain_brute=False,     # Skip brute-force
    ),

    ScanMode.DEEP: ModeConfig(
        mode=ScanMode.DEEP,
        name="DEEP MODE",
        description="Maximum coverage - high noise",
        target_contact="High",
        detection_risk="High",
        tools={
            "discovery": ["theHarvester", "amass", "sublist3r", "fierce"],
            "scanning": ["whatweb", "sslscan", "dnsrecon", "dnsenum", "wafw00f", "nikto", "nmap"],
            "analysis": ["exiftool", "metagoofil"],
            "cross": ["dmitry", "sherlock"],
        },
        spiderfoot_enabled=True,
        nmap_enabled=True,
        active_dns=True,
        subdomain_brute=True,
    ),
}


def get_mode_config(mode: ScanMode) -> ModeConfig:
    """Get configuration for a scan mode"""
    return MODE_CONFIGS[mode]


def get_mode_tools(mode: ScanMode) -> List[str]:
    """
    Get list of tool commands for a mode.

    Returns only tools that are actually available.
    """
    registry = get_registry()
    config = MODE_CONFIGS[mode]

    available_tools = []

    for category_tools in config.tools.values():
        for tool_cmd in category_tools:
            if registry.is_available(tool_cmd):
                available_tools.append(tool_cmd)

    return available_tools


def get_available_modes() -> List[ScanMode]:
    """
    Get list of modes that can be used based on available tools.

    All modes are always available, but with varying tool coverage.
    """
    # All modes are always available - they just use what's installed
    return list(ScanMode)


def get_mode_coverage(mode: ScanMode) -> Dict[str, any]:
    """
    Get coverage info for a mode based on available tools.

    Returns dict with:
    - total_tools: Number of tools defined for mode
    - available_tools: Number of tools available
    - coverage_pct: Percentage of tools available
    - missing_tools: List of missing tool names
    """
    registry = get_registry()
    config = MODE_CONFIGS[mode]

    all_tools = []
    for category_tools in config.tools.values():
        all_tools.extend(category_tools)

    available = [t for t in all_tools if registry.is_available(t)]
    missing = [t for t in all_tools if not registry.is_available(t)]

    total = len(all_tools)
    avail_count = len(available)

    return {
        'total_tools': total,
        'available_tools': avail_count,
        'coverage_pct': (avail_count / total * 100) if total > 0 else 0,
        'missing_tools': missing,
        'available_list': available,
    }


def select_scan_mode(current_mode: Optional[ScanMode] = None) -> str:
    """
    Generate mode selection menu display.

    Returns formatted string for display.
    """
    lines = []
    lines.append("\n\033[1m  SELECT SCAN MODE\033[0m\n")

    mode_icons = {
        ScanMode.GHOST: "👻",
        ScanMode.STEALTH: "🥷",
        ScanMode.STANDARD: "🎯",
        ScanMode.DEEP: "🔬",
    }

    for i, mode in enumerate(ScanMode, 1):
        config = MODE_CONFIGS[mode]
        coverage = get_mode_coverage(mode)
        icon = mode_icons.get(mode, "")

        # Current mode indicator
        current = " ◀" if mode == current_mode else ""

        # Coverage color
        pct = coverage['coverage_pct']
        if pct >= 80:
            pct_color = "\033[92m"  # Green
        elif pct >= 50:
            pct_color = "\033[93m"  # Yellow
        else:
            pct_color = "\033[91m"  # Red

        lines.append(f"  \033[1m[{i}] {icon} {config.name}\033[0m{current}")
        lines.append(f"      {config.description}")
        lines.append(f"      Target Contact: {config.target_contact} | Detection Risk: {config.detection_risk}")
        lines.append(f"      {pct_color}Tools: {coverage['available_tools']}/{coverage['total_tools']} available ({pct:.0f}%)\033[0m")

        if coverage['missing_tools']:
            missing_str = ", ".join(coverage['missing_tools'][:3])
            if len(coverage['missing_tools']) > 3:
                missing_str += f" +{len(coverage['missing_tools']) - 3} more"
            lines.append(f"      \033[90mMissing: {missing_str}\033[0m")

        lines.append("")

    return "\n".join(lines)


def print_mode_details(mode: ScanMode) -> str:
    """Print detailed info about a mode"""
    config = MODE_CONFIGS[mode]
    coverage = get_mode_coverage(mode)

    lines = []
    lines.append(f"\n\033[1m  {config.name}\033[0m")
    lines.append(f"  {'─' * 50}")
    lines.append(f"  {config.description}")
    lines.append("")
    lines.append(f"  Target Contact:  {config.target_contact}")
    lines.append(f"  Detection Risk:  {config.detection_risk}")
    lines.append(f"  SpiderFoot:      {'Enabled' if config.spiderfoot_enabled else 'Disabled'}")
    lines.append(f"  Port Scanning:   {'Enabled' if config.nmap_enabled else 'Disabled'}")
    lines.append(f"  Active DNS:      {'Enabled' if config.active_dns else 'Disabled'}")
    lines.append(f"  Subdomain Brute: {'Enabled' if config.subdomain_brute else 'Disabled'}")
    lines.append("")

    lines.append("  \033[36mAvailable Tools:\033[0m")
    for tool in coverage['available_list']:
        lines.append(f"    \033[92m✓\033[0m {tool}")

    if coverage['missing_tools']:
        lines.append("")
        lines.append("  \033[90mMissing Tools:\033[0m")
        for tool in coverage['missing_tools']:
            lines.append(f"    \033[91m✗\033[0m {tool}")

    return "\n".join(lines)


# Quick test
if __name__ == '__main__':
    print(select_scan_mode())
    print("\n" + "=" * 60)
    print(print_mode_details(ScanMode.STANDARD))
