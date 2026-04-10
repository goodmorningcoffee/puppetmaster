"""
Security Tools - Tool definitions and wrappers for security auditing.

Follows the same patterns as the Kali module for consistency.
"""

import os
import subprocess
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from utils.colors import C

# _which fallback for minimal Python installations
try:
    from shutil import which as _which
except ImportError:
    def _which(cmd: str) -> Optional[str]:
        """Fallback which implementation if shutil is unavailable."""
        for path in os.environ.get("PATH", "").split(os.pathsep):
            full_path = os.path.join(path, cmd)
            if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                return full_path
        return None


# =============================================================================
# DATA CLASSES (Plain Python - no dataclasses dependency)
# =============================================================================

class SecurityTool:
    """Definition of a security audit tool."""

    def __init__(
        self,
        name: str,
        command: str,
        apt_package: str,
        description: str,
        requires_root: bool,
        timeout: int = 300,
        quiet_flag: str = ""
    ):
        self.name = name                 # Display name
        self.command = command           # Command to execute
        self.apt_package = apt_package   # Package name for apt install
        self.description = description   # Short description
        self.requires_root = requires_root  # Needs sudo to run
        self.timeout = timeout           # Default timeout in seconds
        self.quiet_flag = quiet_flag     # Flag for quiet/minimal output


class ToolResult:
    """Result from running a security tool."""

    def __init__(
        self,
        tool: str,
        success: bool,
        timestamp: str = None,
        findings: List[str] = None,
        warnings: List[str] = None,
        clean: bool = True,
        raw_output: str = "",
        error: str = "",
        return_code: int = 0
    ):
        self.tool = tool
        self.success = success
        self.timestamp = timestamp or datetime.now().isoformat()
        self.findings = findings or []
        self.warnings = warnings or []
        self.clean = clean
        self.raw_output = raw_output
        self.error = error
        self.return_code = return_code


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

SECURITY_TOOLS: Dict[str, SecurityTool] = {
    "chkrootkit": SecurityTool(
        name="chkrootkit",
        command="chkrootkit",
        apt_package="chkrootkit",
        description="Checks for signs of rootkits and known malware signatures",
        requires_root=True,
        timeout=300,
        quiet_flag="-q",
    ),
    "rkhunter": SecurityTool(
        name="rkhunter",
        command="rkhunter",
        apt_package="rkhunter",
        description="Rootkit Hunter - scans for rootkits, backdoors, and exploits",
        requires_root=True,
        timeout=600,  # rkhunter is thorough and slow
        quiet_flag="--quiet",
    ),
    "lynis": SecurityTool(
        name="lynis",
        command="lynis",
        apt_package="lynis",
        description="Security auditing tool for Unix/Linux systems",
        requires_root=True,
        timeout=600,
        quiet_flag="--quiet",
    ),
    "debsums": SecurityTool(
        name="debsums",
        command="debsums",
        apt_package="debsums",
        description="Verifies installed package file integrity against MD5 checksums",
        requires_root=False,
        timeout=300,
        quiet_flag="-s",  # silent, only report errors
    ),
    "unhide": SecurityTool(
        name="unhide",
        command="unhide",
        apt_package="unhide",
        description="Finds hidden processes and TCP/UDP ports (anti-rootkit)",
        requires_root=True,
        timeout=300,
        quiet_flag="",  # no quiet mode
    ),
}

# Tool execution commands (what to actually run)
TOOL_COMMANDS: Dict[str, List[str]] = {
    "chkrootkit": ["chkrootkit", "-q"],
    "rkhunter": ["rkhunter", "--check", "--skip-keypress", "--quiet"],
    "lynis": ["lynis", "audit", "system", "--quiet", "--no-colors"],
    "debsums": ["debsums", "-c", "-s"],  # -c = check config files, -s = silent
    "unhide": ["unhide", "sys", "proc"],  # check system calls and /proc
}


# =============================================================================
# TOOL DETECTION
# =============================================================================

def check_tool_installed(tool_name: str) -> bool:
    """Check if a specific tool is installed."""
    if tool_name not in SECURITY_TOOLS:
        return False
    return _which(SECURITY_TOOLS[tool_name].command) is not None


def check_tools_installed() -> Tuple[List[str], List[str]]:
    """
    Check which security tools are installed.

    Returns:
        Tuple of (installed_tools, missing_tools)
    """
    installed = []
    missing = []

    for name, tool in SECURITY_TOOLS.items():
        if _which(tool.command):
            installed.append(name)
        else:
            missing.append(name)

    return installed, missing


def check_sudo_available() -> bool:
    """Check if sudo is available and we can use it."""
    if _which("sudo") is None:
        return False

    # Check if we can sudo without password (for non-interactive use)
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def check_apt_available() -> bool:
    """Check if apt package manager is available."""
    return _which("apt-get") is not None


# =============================================================================
# TOOL INSTALLATION
# =============================================================================

def install_security_tools(
    tools: Optional[List[str]] = None,
    verbose: bool = True
) -> Tuple[bool, List[str], List[str]]:
    """
    Install security tools via apt.

    Args:
        tools: List of tool names to install, or None for all missing
        verbose: Print progress messages

    Returns:
        Tuple of (success, installed_tools, failed_tools)
    """
    if not check_apt_available():
        if verbose:
            print(f"{C.BRIGHT_RED}apt-get not available. Cannot install tools.{C.RESET}")
            print(f"{C.BRIGHT_YELLOW}On non-Debian systems, install manually:{C.RESET}")
            for name, tool in SECURITY_TOOLS.items():
                print(f"  - {tool.name}: {tool.description}")
        return False, [], list(SECURITY_TOOLS.keys())

    # Determine which tools to install
    if tools is None:
        _, missing = check_tools_installed()
        tools_to_install = missing
    else:
        tools_to_install = [t for t in tools if not check_tool_installed(t)]

    if not tools_to_install:
        if verbose:
            print(f"{C.BRIGHT_GREEN}All requested tools are already installed.{C.RESET}")
        return True, [], []

    if verbose:
        print(f"\n{C.BRIGHT_CYAN}Installing security tools...{C.RESET}")
        for tool_name in tools_to_install:
            tool = SECURITY_TOOLS.get(tool_name)
            if tool:
                print(f"  - {tool.name}: {tool.description}")

    # Build package list
    packages = []
    for tool_name in tools_to_install:
        tool = SECURITY_TOOLS.get(tool_name)
        if tool:
            packages.append(tool.apt_package)

    if not packages:
        return True, [], []

    # Run apt-get update
    if verbose:
        print(f"\n{C.BRIGHT_CYAN}Updating package lists...{C.RESET}")

    try:
        update_result = subprocess.run(
            ["sudo", "apt-get", "update", "-qq"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if update_result.returncode != 0:
            if verbose:
                print(f"{C.BRIGHT_YELLOW}Warning: apt-get update had issues{C.RESET}")
    except subprocess.TimeoutExpired:
        if verbose:
            print(f"{C.BRIGHT_YELLOW}Warning: apt-get update timed out{C.RESET}")
    except Exception as e:
        if verbose:
            print(f"{C.BRIGHT_YELLOW}Warning: apt-get update failed: {e}{C.RESET}")

    # Install packages
    if verbose:
        print(f"{C.BRIGHT_CYAN}Installing packages: {', '.join(packages)}{C.RESET}")

    try:
        install_cmd = ["sudo", "apt-get", "install", "-y", "-qq"] + packages
        install_result = subprocess.run(
            install_cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if install_result.returncode != 0:
            if verbose:
                print(f"{C.BRIGHT_RED}Installation failed:{C.RESET}")
                if install_result.stderr:
                    print(install_result.stderr[:500])
    except subprocess.TimeoutExpired:
        if verbose:
            print(f"{C.BRIGHT_RED}Installation timed out{C.RESET}")
        return False, [], tools_to_install
    except Exception as e:
        if verbose:
            print(f"{C.BRIGHT_RED}Installation error: {e}{C.RESET}")
        return False, [], tools_to_install

    # Verify installation
    installed = []
    failed = []

    for tool_name in tools_to_install:
        if check_tool_installed(tool_name):
            installed.append(tool_name)
            if verbose:
                print(f"  {C.BRIGHT_GREEN}[OK]{C.RESET} {tool_name}")
        else:
            failed.append(tool_name)
            if verbose:
                print(f"  {C.BRIGHT_RED}[FAIL]{C.RESET} {tool_name}")

    success = len(failed) == 0

    if verbose:
        if success:
            print(f"\n{C.BRIGHT_GREEN}All tools installed successfully!{C.RESET}")
        else:
            print(f"\n{C.BRIGHT_YELLOW}Some tools failed to install: {', '.join(failed)}{C.RESET}")

    return success, installed, failed


# =============================================================================
# TOOL EXECUTION
# =============================================================================

def run_tool(
    tool_name: str,
    timeout: Optional[int] = None,
    use_sudo: bool = True
) -> ToolResult:
    """
    Run a security tool and parse its output.

    Args:
        tool_name: Name of the tool (key in SECURITY_TOOLS)
        timeout: Override default timeout
        use_sudo: Use sudo for tools that require root

    Returns:
        ToolResult with findings and status
    """
    if tool_name not in SECURITY_TOOLS:
        return ToolResult(
            tool=tool_name,
            success=False,
            error=f"Unknown tool: {tool_name}",
            clean=False
        )

    tool = SECURITY_TOOLS[tool_name]

    if not check_tool_installed(tool_name):
        return ToolResult(
            tool=tool_name,
            success=False,
            error=f"{tool_name} is not installed",
            clean=False
        )

    # Build command
    cmd = TOOL_COMMANDS.get(tool_name, [tool.command])

    # Add sudo if required
    if tool.requires_root and use_sudo:
        cmd = ["sudo"] + cmd

    # Determine timeout
    actual_timeout = timeout if timeout is not None else tool.timeout

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=actual_timeout
        )

        # Parse output based on tool
        return _parse_tool_output(tool_name, result)

    except subprocess.TimeoutExpired:
        return ToolResult(
            tool=tool_name,
            success=False,
            error=f"Timeout after {actual_timeout} seconds",
            clean=False
        )
    except PermissionError:
        return ToolResult(
            tool=tool_name,
            success=False,
            error="Permission denied. Try running with sudo.",
            clean=False
        )
    except Exception as e:
        return ToolResult(
            tool=tool_name,
            success=False,
            error=str(e),
            clean=False
        )


def _parse_tool_output(tool_name: str, result: subprocess.CompletedProcess) -> ToolResult:
    """Parse output from a security tool."""

    output = result.stdout + result.stderr
    findings = []
    warnings = []
    clean = True

    if tool_name == "chkrootkit":
        # chkrootkit outputs "INFECTED" for positive matches
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            if "INFECTED" in line.upper():
                findings.append(line)
                clean = False
            elif "warning" in line.lower():
                warnings.append(line)
            elif "not found" not in line.lower() and "nothing found" not in line.lower():
                # Any other output could be suspicious
                if line and not line.startswith("Checking"):
                    warnings.append(line)

    elif tool_name == "rkhunter":
        # rkhunter uses "Warning:" prefix for issues
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("Warning:"):
                findings.append(line)
                clean = False
            elif "[ Warning ]" in line:
                findings.append(line)
                clean = False

    elif tool_name == "lynis":
        # lynis outputs warnings and suggestions
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            if "warning" in line.lower() and "0 warning" not in line.lower():
                warnings.append(line)
            if "[WARNING]" in line:
                findings.append(line)
                clean = False

    elif tool_name == "debsums":
        # debsums outputs files that have been modified
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            # Any output from debsums -c -s means modified files
            if line:
                findings.append(f"Modified: {line}")
                clean = False

    elif tool_name == "unhide":
        # unhide reports hidden processes/ports
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            if "found" in line.lower() and "hidden" in line.lower():
                findings.append(line)
                clean = False
            elif "hidden" in line.lower():
                findings.append(line)
                clean = False

    return ToolResult(
        tool=tool_name,
        success=True,
        findings=findings,
        warnings=warnings,
        clean=clean,
        raw_output=output,
        return_code=result.returncode
    )


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

def print_tool_status():
    """Print status of all security tools."""
    installed, missing = check_tools_installed()

    print(f"\n{C.BRIGHT_CYAN}Security Tools Status:{C.RESET}")
    print(f"{C.DIM}{'─' * 60}{C.RESET}")

    for name, tool in SECURITY_TOOLS.items():
        status = f"{C.BRIGHT_GREEN}[INSTALLED]{C.RESET}" if name in installed else f"{C.BRIGHT_RED}[MISSING]{C.RESET}"
        root_badge = f"{C.DIM}(root){C.RESET}" if tool.requires_root else ""
        print(f"  {status} {tool.name:12} - {tool.description} {root_badge}")

    print(f"{C.DIM}{'─' * 60}{C.RESET}")
    print(f"  Installed: {C.BRIGHT_GREEN}{len(installed)}{C.RESET} / {len(SECURITY_TOOLS)}")

    if missing:
        print(f"  Missing: {C.BRIGHT_RED}{', '.join(missing)}{C.RESET}")
        print(f"\n  {C.DIM}Run option [3] to install missing tools{C.RESET}")
