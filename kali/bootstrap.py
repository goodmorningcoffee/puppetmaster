"""
Kali Linux Bootstrap Module

Auto-installs all required Kali security tools when running on Kali Linux.
This runs automatically at startup when Kali is detected.
"""

import subprocess
import sys
import shutil
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from enum import Enum


class ToolCategory(Enum):
    """Tool categories for organization"""
    DISCOVERY = "discovery"      # Domain/subdomain discovery
    SCANNING = "scanning"        # Active scanning tools
    ANALYSIS = "analysis"        # Data analysis tools
    CROSS = "cross"              # Multi-purpose tools


@dataclass
class KaliTool:
    """Kali tool definition"""
    name: str                    # Display name
    apt_package: str             # apt package name
    command: str                 # Command to check availability
    category: ToolCategory       # Tool category
    description: str             # Short description
    priority: int = 1            # Install priority (1=highest)


# All Kali tools to install
KALI_TOOLS: List[KaliTool] = [
    # DISCOVERY TOOLS
    KaliTool(
        name="theHarvester",
        apt_package="theharvester",
        command="theHarvester",
        category=ToolCategory.DISCOVERY,
        description="Email/domain discovery from 30+ sources",
        priority=1
    ),
    KaliTool(
        name="Amass",
        apt_package="amass",
        command="amass",
        category=ToolCategory.DISCOVERY,
        description="Advanced subdomain enumeration & OSINT",
        priority=1
    ),
    KaliTool(
        name="Sublist3r",
        apt_package="sublist3r",
        command="sublist3r",
        category=ToolCategory.DISCOVERY,
        description="Fast subdomain enumeration",
        priority=2
    ),
    KaliTool(
        name="Fierce",
        apt_package="fierce",
        command="fierce",
        category=ToolCategory.DISCOVERY,
        description="DNS reconnaissance & zone transfers",
        priority=2
    ),

    # SCANNING TOOLS
    KaliTool(
        name="WhatWeb",
        apt_package="whatweb",
        command="whatweb",
        category=ToolCategory.SCANNING,
        description="Web fingerprinting (CMS, tech stack)",
        priority=1
    ),
    KaliTool(
        name="wafw00f",
        apt_package="wafw00f",
        command="wafw00f",
        category=ToolCategory.SCANNING,
        description="WAF detection",
        priority=2
    ),
    KaliTool(
        name="SSLScan",
        apt_package="sslscan",
        command="sslscan",
        category=ToolCategory.SCANNING,
        description="SSL/TLS certificate & cipher analysis",
        priority=1
    ),
    KaliTool(
        name="Nmap",
        apt_package="nmap",
        command="nmap",
        category=ToolCategory.SCANNING,
        description="Port scanning & service detection",
        priority=1
    ),
    KaliTool(
        name="Nikto",
        apt_package="nikto",
        command="nikto",
        category=ToolCategory.SCANNING,
        description="Web server vulnerability scanner",
        priority=2
    ),
    KaliTool(
        name="DNSRecon",
        apt_package="dnsrecon",
        command="dnsrecon",
        category=ToolCategory.SCANNING,
        description="DNS enumeration (SPF, DKIM, DMARC)",
        priority=1
    ),
    KaliTool(
        name="DNSEnum",
        apt_package="dnsenum",
        command="dnsenum",
        category=ToolCategory.SCANNING,
        description="DNS enumeration & zone transfers",
        priority=2
    ),

    # ANALYSIS TOOLS
    KaliTool(
        name="Metagoofil",
        apt_package="metagoofil",
        command="metagoofil",
        category=ToolCategory.ANALYSIS,
        description="Document metadata extraction",
        priority=2
    ),
    KaliTool(
        name="ExifTool",
        apt_package="libimage-exiftool-perl",
        command="exiftool",
        category=ToolCategory.ANALYSIS,
        description="Image/file metadata extraction",
        priority=1
    ),

    # CROSS-PHASE TOOLS
    KaliTool(
        name="DMitry",
        apt_package="dmitry",
        command="dmitry",
        category=ToolCategory.CROSS,
        description="Multi-tool (WHOIS, ports, subdomains)",
        priority=2
    ),
    KaliTool(
        name="Sherlock",
        apt_package="sherlock",
        command="sherlock",
        category=ToolCategory.CROSS,
        description="Social media username search",
        priority=3
    ),
]


def check_tool_installed(tool: KaliTool) -> bool:
    """Check if a tool is installed and available"""
    return shutil.which(tool.command) is not None


def check_kali_tools() -> Tuple[List[KaliTool], List[KaliTool]]:
    """
    Check which Kali tools are installed.

    Returns:
        Tuple of (installed_tools, missing_tools)
    """
    installed = []
    missing = []

    for tool in KALI_TOOLS:
        if check_tool_installed(tool):
            installed.append(tool)
        else:
            missing.append(tool)

    return installed, missing


def check_sudo_available() -> bool:
    """
    Check if sudo is available without requiring a password.

    Returns:
        True if sudo can be used without prompting for password
    """
    try:
        result = subprocess.run(
            ['sudo', '-n', 'true'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def bootstrap_kali_tools(verbose: bool = True) -> bool:
    """
    Install all missing Kali tools via apt.

    Args:
        verbose: Print progress messages

    Returns:
        True if all tools installed successfully
    """
    installed, missing = check_kali_tools()

    if not missing:
        if verbose:
            print("\033[92m  All Kali tools already installed!\033[0m")
        return True

    # Verify sudo is available before proceeding
    if not check_sudo_available():
        if verbose:
            print("\033[91m  Error: sudo access required but not available.\033[0m")
            print("  Please run with sudo privileges or configure passwordless sudo.")
        return False

    if verbose:
        print(f"\n\033[93m  Installing {len(missing)} missing Kali tools...\033[0m\n")

    # Sort by priority
    missing.sort(key=lambda t: t.priority)

    # Build apt install command
    packages = [tool.apt_package for tool in missing]

    try:
        # Update apt first
        if verbose:
            print("  Updating apt package lists...")

        result = subprocess.run(
            ['sudo', 'apt-get', 'update', '-qq'],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            if verbose:
                print(f"\033[91m  apt update failed: {result.stderr}\033[0m")
            return False

        # Install all packages at once
        if verbose:
            print(f"  Installing: {', '.join(packages)}")
            print("  This may take a few minutes...\n")

        cmd = ['sudo', 'apt-get', 'install', '-y', '-qq'] + packages

        result = subprocess.run(
            cmd,
            capture_output=not verbose,  # Show output if verbose
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode != 0:
            if verbose:
                print(f"\033[91m  apt install failed\033[0m")
                if result.stderr:
                    print(f"  {result.stderr}")
            return False

        # Verify installation
        if verbose:
            print("\n  Verifying installation...")

        _, still_missing = check_kali_tools()

        if still_missing:
            if verbose:
                print(f"\033[93m  Warning: {len(still_missing)} tools failed to install:\033[0m")
                for tool in still_missing:
                    print(f"    - {tool.name} ({tool.apt_package})")
            return False

        if verbose:
            print("\033[92m  All Kali tools installed successfully!\033[0m")

        return True

    except subprocess.TimeoutExpired:
        if verbose:
            print("\033[91m  Installation timed out\033[0m")
        return False
    except Exception as e:
        if verbose:
            print(f"\033[91m  Installation failed: {e}\033[0m")
        return False


def print_tool_status() -> str:
    """Generate tool status table for display"""
    installed, missing = check_kali_tools()

    lines = []
    lines.append("\n\033[1m  KALI TOOL STATUS\033[0m\n")

    # Group by category
    categories = {
        ToolCategory.DISCOVERY: "DISCOVERY",
        ToolCategory.SCANNING: "SCANNING",
        ToolCategory.ANALYSIS: "ANALYSIS",
        ToolCategory.CROSS: "CROSS-PHASE",
    }

    for category, label in categories.items():
        lines.append(f"\n  \033[36m{label}\033[0m")
        lines.append("  " + "─" * 50)

        category_tools = [t for t in KALI_TOOLS if t.category == category]

        for tool in category_tools:
            is_installed = check_tool_installed(tool)
            status = "\033[92m✓\033[0m" if is_installed else "\033[91m✗\033[0m"
            lines.append(f"  {status} {tool.name:<15} {tool.description}")

    lines.append("")
    lines.append(f"  \033[92mInstalled: {len(installed)}\033[0m  |  \033[91mMissing: {len(missing)}\033[0m")
    lines.append("")

    return "\n".join(lines)


def get_tools_by_category(category: ToolCategory) -> List[KaliTool]:
    """Get all tools in a category"""
    return [t for t in KALI_TOOLS if t.category == category]


def get_installed_tools() -> List[KaliTool]:
    """Get list of installed tools"""
    installed, _ = check_kali_tools()
    return installed


# Quick test
if __name__ == '__main__':
    print(print_tool_status())
    print("\nChecking tools...")
    installed, missing = check_kali_tools()
    print(f"Installed: {[t.name for t in installed]}")
    print(f"Missing: {[t.name for t in missing]}")
