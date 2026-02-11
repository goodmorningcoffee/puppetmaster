"""
Tool Registry Module

Tracks which tools are available and provides unified access to tool capabilities.
This is the central registry that other modules query to determine what's possible.
"""

import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from enum import Enum

from .detect import get_os_info, OSInfo
from .bootstrap import KALI_TOOLS, KaliTool, ToolCategory, check_tool_installed


class ToolStatus(Enum):
    """Tool availability status"""
    AVAILABLE = "available"      # Tool is installed and ready
    MISSING = "missing"          # Tool not installed
    UNAVAILABLE = "unavailable"  # Tool not available on this OS


@dataclass
class ToolInfo:
    """Runtime info about a tool"""
    name: str
    command: str
    status: ToolStatus
    category: ToolCategory
    description: str
    path: Optional[str] = None   # Full path to executable


class ToolRegistry:
    """
    Central registry of available tools.

    Singleton pattern - use get_registry() to access.
    """

    _instance = None

    def __init__(self):
        self.os_info: OSInfo = get_os_info()
        self._tools: Dict[str, ToolInfo] = {}
        self._scanned = False

    @classmethod
    def get_instance(cls) -> 'ToolRegistry':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = ToolRegistry()
        return cls._instance

    def scan(self, force: bool = False) -> None:
        """
        Scan system for available tools.

        Args:
            force: Re-scan even if already scanned
        """
        if self._scanned and not force:
            return

        self._tools.clear()

        for tool in KALI_TOOLS:
            path = shutil.which(tool.command)

            if path:
                status = ToolStatus.AVAILABLE
            elif not self.os_info.is_kali:
                # On non-Kali, mark as unavailable (not just missing)
                status = ToolStatus.UNAVAILABLE
            else:
                status = ToolStatus.MISSING

            self._tools[tool.command] = ToolInfo(
                name=tool.name,
                command=tool.command,
                status=status,
                category=tool.category,
                description=tool.description,
                path=path
            )

        self._scanned = True

    def is_available(self, command: str) -> bool:
        """Check if a tool is available"""
        self.scan()
        tool = self._tools.get(command)
        return tool is not None and tool.status == ToolStatus.AVAILABLE

    def get_tool(self, command: str) -> Optional[ToolInfo]:
        """Get tool info by command name"""
        self.scan()
        return self._tools.get(command)

    def get_available_tools(self) -> List[ToolInfo]:
        """Get all available tools"""
        self.scan()
        return [t for t in self._tools.values() if t.status == ToolStatus.AVAILABLE]

    def get_missing_tools(self) -> List[ToolInfo]:
        """Get all missing tools"""
        self.scan()
        return [t for t in self._tools.values() if t.status == ToolStatus.MISSING]

    def get_tools_by_category(self, category: ToolCategory) -> List[ToolInfo]:
        """Get tools in a category"""
        self.scan()
        return [t for t in self._tools.values() if t.category == category]

    def get_available_by_category(self, category: ToolCategory) -> List[ToolInfo]:
        """Get available tools in a category"""
        self.scan()
        return [
            t for t in self._tools.values()
            if t.category == category and t.status == ToolStatus.AVAILABLE
        ]

    def get_discovery_tools(self) -> List[ToolInfo]:
        """Get available discovery tools"""
        return self.get_available_by_category(ToolCategory.DISCOVERY)

    def get_scanning_tools(self) -> List[ToolInfo]:
        """Get available scanning tools"""
        return self.get_available_by_category(ToolCategory.SCANNING)

    def get_analysis_tools(self) -> List[ToolInfo]:
        """Get available analysis tools"""
        return self.get_available_by_category(ToolCategory.ANALYSIS)

    def has_enhanced_mode(self) -> bool:
        """Check if we have enough tools for enhanced mode"""
        available = self.get_available_tools()
        return len(available) >= 3  # At least 3 Kali tools

    def get_status_summary(self) -> Dict[str, int]:
        """Get summary of tool status"""
        self.scan()
        return {
            'available': len([t for t in self._tools.values() if t.status == ToolStatus.AVAILABLE]),
            'missing': len([t for t in self._tools.values() if t.status == ToolStatus.MISSING]),
            'unavailable': len([t for t in self._tools.values() if t.status == ToolStatus.UNAVAILABLE]),
            'total': len(self._tools)
        }

    def print_status(self) -> str:
        """Generate status display"""
        self.scan()
        lines = []

        status_icons = {
            ToolStatus.AVAILABLE: "\033[92m✓\033[0m",
            ToolStatus.MISSING: "\033[91m✗\033[0m",
            ToolStatus.UNAVAILABLE: "\033[90m-\033[0m",
        }

        # Group by category
        for category in ToolCategory:
            category_tools = self.get_tools_by_category(category)
            if category_tools:
                lines.append(f"\n  \033[36m{category.value.upper()}\033[0m")
                for tool in category_tools:
                    icon = status_icons[tool.status]
                    lines.append(f"  {icon} {tool.name:<15} {tool.description}")

        summary = self.get_status_summary()
        lines.append("")
        lines.append(f"  \033[92mAvailable: {summary['available']}\033[0m | "
                     f"\033[91mMissing: {summary['missing']}\033[0m | "
                     f"\033[90mN/A: {summary['unavailable']}\033[0m")

        return "\n".join(lines)


def get_registry() -> ToolRegistry:
    """Get the global tool registry"""
    return ToolRegistry.get_instance()


def get_available_tools() -> List[ToolInfo]:
    """Convenience function to get available tools"""
    return get_registry().get_available_tools()


def is_tool_available(command: str) -> bool:
    """Convenience function to check tool availability"""
    return get_registry().is_available(command)


# Quick test
if __name__ == '__main__':
    registry = get_registry()
    print(registry.print_status())
    print("\nSummary:", registry.get_status_summary())
