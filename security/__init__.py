"""
Security Audit Module for PuppetMaster

Provides rootkit detection, system integrity verification, and security auditing
for both local machines and distributed workers.

Tools supported:
- chkrootkit: Rootkit signature detection
- rkhunter: Rootkit hunter + backdoor detection
- lynis: Full security audit
- debsums: Package integrity verification (Debian/Ubuntu)
- unhide: Hidden process/port detection
"""

from .audit import (
    security_audit_menu,
    audit_local,
    audit_workers,
    show_disclaimer,
    AuditReport,
)

from .tools import (
    SECURITY_TOOLS,
    check_tools_installed,
    install_security_tools,
    run_tool,
    ToolResult,
)

__all__ = [
    # Menu and orchestration
    "security_audit_menu",
    "audit_local",
    "audit_workers",
    "show_disclaimer",
    "AuditReport",
    # Tools
    "SECURITY_TOOLS",
    "check_tools_installed",
    "install_security_tools",
    "run_tool",
    "ToolResult",
]
