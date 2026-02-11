"""
OS Detection Module

Detects the operating system and determines if running on Kali Linux.
This is the first check that runs - if Kali is detected, enhanced features
are enabled and Kali tools are auto-installed.
"""

import os
import platform
import subprocess
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class OSInfo:
    """Operating system information"""
    os_type: str          # 'kali', 'debian', 'ubuntu', 'fedora', 'macos', 'windows', 'other'
    os_name: str          # Full OS name (e.g., 'Kali GNU/Linux Rolling')
    os_version: str       # Version string
    kernel: str           # Kernel version
    arch: str             # Architecture (x86_64, arm64, etc.)
    is_kali: bool         # True if running on Kali Linux
    is_wsl: bool          # True if running in WSL
    has_apt: bool         # True if apt package manager available
    has_root: bool        # True if running as root or can sudo


def detect_os() -> OSInfo:
    """
    Detect the operating system and return detailed info.

    Returns:
        OSInfo dataclass with OS details
    """
    os_type = 'other'
    os_name = 'Unknown'
    os_version = ''
    kernel = platform.release()
    arch = platform.machine()
    is_kali = False
    is_wsl = False
    has_apt = False
    has_root = False

    system = platform.system().lower()

    if system == 'linux':
        # Check /etc/os-release for distribution info
        os_release = _parse_os_release()

        if os_release:
            os_name = os_release.get('PRETTY_NAME', os_release.get('NAME', 'Linux'))
            os_version = os_release.get('VERSION_ID', os_release.get('VERSION', ''))
            distro_id = os_release.get('ID', '').lower()
            distro_like = os_release.get('ID_LIKE', '').lower()

            # Detect Kali Linux
            if distro_id == 'kali':
                os_type = 'kali'
                is_kali = True
            elif distro_id == 'debian' or 'debian' in distro_like:
                os_type = 'debian'
            elif distro_id == 'ubuntu':
                os_type = 'ubuntu'
            elif distro_id == 'fedora' or 'fedora' in distro_like:
                os_type = 'fedora'
            elif distro_id == 'arch':
                os_type = 'arch'
            elif distro_id == 'centos' or distro_id == 'rhel':
                os_type = 'rhel'
            else:
                os_type = 'linux'

        # Check for WSL
        is_wsl = _check_wsl()

        # Check for apt
        has_apt = _check_command('apt')

    elif system == 'darwin':
        os_type = 'macos'
        os_name = f"macOS {platform.mac_ver()[0]}"
        os_version = platform.mac_ver()[0]

    elif system == 'windows':
        os_type = 'windows'
        os_name = f"Windows {platform.win32_ver()[0]}"
        os_version = platform.win32_ver()[0]

    # Check for root/sudo access
    has_root = _check_root_access()

    return OSInfo(
        os_type=os_type,
        os_name=os_name,
        os_version=os_version,
        kernel=kernel,
        arch=arch,
        is_kali=is_kali,
        is_wsl=is_wsl,
        has_apt=has_apt,
        has_root=has_root
    )


def is_kali() -> bool:
    """Quick check if running on Kali Linux"""
    try:
        os_release = _parse_os_release()
        if os_release:
            return os_release.get('ID', '').lower() == 'kali'
    except Exception:
        pass
    return False


def get_os_info() -> OSInfo:
    """Get cached OS info (singleton pattern)"""
    if not hasattr(get_os_info, '_cached'):
        get_os_info._cached = detect_os()
    return get_os_info._cached


def _parse_os_release() -> Optional[dict]:
    """Parse /etc/os-release file"""
    os_release_paths = [
        '/etc/os-release',
        '/usr/lib/os-release',
    ]

    for path in os_release_paths:
        if os.path.exists(path):
            try:
                result = {}
                with open(path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            # Remove quotes from value
                            value = value.strip('"\'')
                            result[key] = value
                return result
            except Exception:
                continue
    return None


def _check_wsl() -> bool:
    """Check if running in Windows Subsystem for Linux"""
    # Check kernel name
    try:
        with open('/proc/version', 'r') as f:
            version = f.read().lower()
            if 'microsoft' in version or 'wsl' in version:
                return True
    except Exception:
        pass

    # Check for WSL-specific environment
    if os.environ.get('WSL_DISTRO_NAME'):
        return True

    return False


def _check_command(cmd: str) -> bool:
    """Check if a command is available in PATH"""
    try:
        result = subprocess.run(
            ['which', cmd],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_root_access() -> bool:
    """Check if running as root or can sudo without password"""
    # Check if running as root
    if os.geteuid() == 0:
        return True

    # Check if sudo is available without password
    try:
        result = subprocess.run(
            ['sudo', '-n', 'true'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def print_os_banner(os_info: OSInfo) -> str:
    """Generate OS detection banner for display"""
    if os_info.is_kali:
        return f"""
\033[92m╔═══════════════════════════════════════════════════════════════════════════════╗
║  ✓ KALI LINUX DETECTED                                                        ║
║                                                                               ║
║  {os_info.os_name:<69} ║
║  Kernel: {os_info.kernel:<62} ║
║  Arch: {os_info.arch:<64} ║
║                                                                               ║
║  Enhanced PUPPETMASTER mode enabled.                                          ║
║  Auto-installing Kali security tools...                                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝\033[0m
"""
    else:
        return f"""
\033[93m╔═══════════════════════════════════════════════════════════════════════════════╗
║  OS DETECTED: {os_info.os_name:<57} ║
║                                                                               ║
║  Running standard PUPPETMASTER pipeline.                                      ║
║  For enhanced features, run on Kali Linux.                                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝\033[0m
"""


# Quick test
if __name__ == '__main__':
    info = detect_os()
    print(f"OS Type: {info.os_type}")
    print(f"OS Name: {info.os_name}")
    print(f"Version: {info.os_version}")
    print(f"Kernel: {info.kernel}")
    print(f"Arch: {info.arch}")
    print(f"Is Kali: {info.is_kali}")
    print(f"Is WSL: {info.is_wsl}")
    print(f"Has APT: {info.has_apt}")
    print(f"Has Root: {info.has_root}")
    print()
    print(print_os_banner(info))
