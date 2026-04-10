"""
Security Audit - Main orchestration for security auditing.

Provides local and distributed security auditing using tools like
chkrootkit, rkhunter, lynis, debsums, and unhide.
"""

import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any

from .tools import (
    SECURITY_TOOLS,
    check_tools_installed,
    install_security_tools,
    run_tool,
    print_tool_status,
    check_sudo_available,
    ToolResult,
)


from utils.colors import C


# =============================================================================
# DATA CLASSES (Plain Python - no dataclasses dependency)
# =============================================================================

class AuditReport:
    """Complete audit report for a machine."""

    def __init__(
        self,
        hostname: str,
        timestamp: str = None,
        tools_run: List[str] = None,
        tools_skipped: List[str] = None,
        findings: Dict[str, List[str]] = None,
        warnings: Dict[str, List[str]] = None,
        clean: bool = True,
        errors: List[str] = None
    ):
        self.hostname = hostname
        self.timestamp = timestamp or datetime.now().isoformat()
        self.tools_run = tools_run or []
        self.tools_skipped = tools_skipped or []
        self.findings = findings or {}
        self.warnings = warnings or {}
        self.clean = clean
        self.errors = errors or []

    def add_result(self, result: ToolResult):
        """Add a tool result to the report."""
        self.tools_run.append(result.tool)

        if result.findings:
            self.findings[result.tool] = result.findings
            self.clean = False

        if result.warnings:
            self.warnings[result.tool] = result.warnings

        if not result.success:
            self.errors.append(f"{result.tool}: {result.error}")


# =============================================================================
# DISCLAIMER
# =============================================================================

DISCLAIMER_TEXT = """
{CYAN}{BOLD}SECURITY AUDIT - IMPORTANT LIMITATIONS{RESET}

{GREEN}What this CAN detect:{RESET}
  {DIM}>{RESET} Known rootkit signatures (chkrootkit, rkhunter)
  {DIM}>{RESET} Modified system binaries (debsums)
  {DIM}>{RESET} Hidden processes and TCP/UDP ports (unhide)
  {DIM}>{RESET} Common security misconfigurations (lynis)
  {DIM}>{RESET} Backdoors with known signatures

{RED}What this CANNOT detect:{RESET}
  {DIM}>{RESET} Supply chain attacks (malicious pip/npm packages)
  {DIM}>{RESET} Credential theft (keys copied, no malware left behind)
  {DIM}>{RESET} Zero-day rootkits (unknown signatures)
  {DIM}>{RESET} Memory-only/fileless malware
  {DIM}>{RESET} Sophisticated APT-level threats
  {DIM}>{RESET} Compromised dependencies before installation

{YELLOW}For comprehensive protection, you MUST also:{RESET}
  {DIM}1.{RESET} Enable AWS CloudTrail + GuardDuty for cloud activity monitoring
  {DIM}2.{RESET} Set up billing alerts to catch unauthorized resource usage
  {DIM}3.{RESET} Use hash-pinned dependencies (pip install --require-hashes)
  {DIM}4.{RESET} NEVER store .pem files on worker machines (use ssh-agent forwarding)
  {DIM}5.{RESET} Use private VPNs (Tailscale) instead of public VPNs (Mullvad)
  {DIM}6.{RESET} Regularly rotate SSH keys and credentials

{MAGENTA}Remember:{RESET} The attack on your AWS account succeeded because of
credential theft and supply chain compromise - neither of which would
have been detected by these tools. Defense in depth is essential.

{DIM}Press Enter to continue...{RESET}
"""


def show_disclaimer():
    """Display the security audit limitations disclaimer."""
    # Format with colors
    text = DISCLAIMER_TEXT.format(
        CYAN=C.BRIGHT_CYAN, BOLD=C.BOLD, RESET=C.RESET,
        GREEN=C.BRIGHT_GREEN, RED=C.BRIGHT_RED, YELLOW=C.BRIGHT_YELLOW,
        MAGENTA=C.BRIGHT_MAGENTA, DIM=C.DIM
    )
    print(text)
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


# =============================================================================
# LOCAL AUDIT
# =============================================================================

def audit_local(
    tools: Optional[List[str]] = None,
    verbose: bool = True,
    on_progress: Optional[Callable[[str, str], None]] = None
) -> AuditReport:
    """
    Run security audit on the local machine.

    Args:
        tools: List of tools to run, or None for all installed
        verbose: Print progress and results
        on_progress: Callback(tool_name, status) for progress updates

    Returns:
        AuditReport with findings
    """
    import socket
    hostname = socket.gethostname()

    report = AuditReport(hostname=hostname)

    # Determine which tools to run
    installed, missing = check_tools_installed()

    if tools is None:
        tools_to_run = installed
    else:
        tools_to_run = [t for t in tools if t in installed]
        report.tools_skipped = [t for t in tools if t not in installed]

    if not tools_to_run:
        if verbose:
            print(f"{C.BRIGHT_RED}No security tools available to run.{C.RESET}")
            print(f"{C.BRIGHT_YELLOW}Use option [3] to install security tools.{C.RESET}")
        report.errors.append("No tools available")
        return report

    # Check sudo availability for tools that need it
    sudo_available = check_sudo_available()

    if verbose:
        print(f"\n{C.BRIGHT_CYAN}{C.BOLD}Starting Security Audit{C.RESET}")
        print(f"{C.DIM}{'─' * 50}{C.RESET}")
        print(f"  Host: {C.BRIGHT_WHITE}{hostname}{C.RESET}")
        print(f"  Tools: {C.BRIGHT_WHITE}{', '.join(tools_to_run)}{C.RESET}")
        print(f"  Sudo: {C.BRIGHT_GREEN if sudo_available else C.BRIGHT_YELLOW}{'available' if sudo_available else 'not available (some tools may fail)'}{C.RESET}")
        print(f"{C.DIM}{'─' * 50}{C.RESET}\n")

    # Run each tool
    for tool_name in tools_to_run:
        tool_info = SECURITY_TOOLS.get(tool_name)

        if verbose:
            print(f"{C.BRIGHT_CYAN}[RUNNING]{C.RESET} {tool_name}...", end=" ", flush=True)

        if on_progress:
            on_progress(tool_name, "running")

        # Skip root-required tools if sudo not available
        if tool_info and tool_info.requires_root and not sudo_available:
            if verbose:
                print(f"{C.BRIGHT_YELLOW}[SKIPPED]{C.RESET} (requires root)")
            report.tools_skipped.append(tool_name)
            report.errors.append(f"{tool_name}: requires root/sudo")
            continue

        # Run the tool
        result = run_tool(tool_name, use_sudo=sudo_available)

        if on_progress:
            on_progress(tool_name, "done" if result.success else "error")

        report.add_result(result)

        if verbose:
            if not result.success:
                print(f"{C.BRIGHT_RED}[ERROR]{C.RESET} {result.error}")
            elif result.clean:
                print(f"{C.BRIGHT_GREEN}[CLEAN]{C.RESET}")
            else:
                print(f"{C.BRIGHT_YELLOW}[FINDINGS]{C.RESET} {len(result.findings)} issue(s)")

    # Print summary
    if verbose:
        _print_audit_summary(report)

    return report


def _print_audit_summary(report: AuditReport):
    """Print a summary of the audit report."""
    print(f"\n{C.DIM}{'═' * 50}{C.RESET}")
    print(f"{C.BOLD}AUDIT SUMMARY - {report.hostname}{C.RESET}")
    print(f"{C.DIM}{'═' * 50}{C.RESET}")

    print(f"\n  Tools run: {C.BRIGHT_WHITE}{len(report.tools_run)}{C.RESET}")

    if report.tools_skipped:
        print(f"  Tools skipped: {C.BRIGHT_YELLOW}{len(report.tools_skipped)}{C.RESET}")

    if report.errors:
        print(f"  Errors: {C.BRIGHT_RED}{len(report.errors)}{C.RESET}")

    # Overall status
    if report.clean and not report.errors:
        print(f"\n  {C.BRIGHT_GREEN}{C.BOLD}STATUS: CLEAN{C.RESET}")
        print(f"  {C.DIM}No issues detected by security tools.{C.RESET}")
    elif report.clean:
        print(f"\n  {C.BRIGHT_YELLOW}{C.BOLD}STATUS: INCOMPLETE{C.RESET}")
        print(f"  {C.DIM}Some tools failed, but no issues found in completed scans.{C.RESET}")
    else:
        print(f"\n  {C.BRIGHT_RED}{C.BOLD}STATUS: ISSUES FOUND{C.RESET}")

    # Print findings
    if report.findings:
        print(f"\n{C.BRIGHT_RED}Findings:{C.RESET}")
        for tool, findings in report.findings.items():
            print(f"\n  {C.BRIGHT_YELLOW}[{tool}]{C.RESET}")
            for finding in findings[:10]:  # Limit output
                print(f"    {C.DIM}>{C.RESET} {finding}")
            if len(findings) > 10:
                print(f"    {C.DIM}... and {len(findings) - 10} more{C.RESET}")

    # Print warnings
    if report.warnings:
        print(f"\n{C.BRIGHT_YELLOW}Warnings:{C.RESET}")
        for tool, warnings in report.warnings.items():
            print(f"\n  {C.DIM}[{tool}]{C.RESET}")
            for warning in warnings[:5]:
                print(f"    {C.DIM}>{C.RESET} {warning}")
            if len(warnings) > 5:
                print(f"    {C.DIM}... and {len(warnings) - 5} more{C.RESET}")

    print(f"\n{C.DIM}{'═' * 50}{C.RESET}")


# =============================================================================
# DISTRIBUTED AUDIT (WORKERS)
# =============================================================================

def audit_workers(
    config: Any,  # DistributedConfig from worker_config.py
    tools: Optional[List[str]] = None,
    verbose: bool = True,
    on_progress: Optional[Callable[[str, str, str], None]] = None
) -> Dict[str, AuditReport]:
    """
    Run security audit on all configured workers.

    Args:
        config: DistributedConfig with worker definitions
        tools: List of tools to run, or None for all available
        verbose: Print progress and results
        on_progress: Callback(hostname, tool, status) for progress

    Returns:
        Dict mapping hostname to AuditReport
    """
    # Import here to avoid circular dependency
    try:
        from discovery.distributed import SSHExecutor
    except ImportError:
        try:
            from ..discovery.distributed import SSHExecutor
        except ImportError:
            if verbose:
                print(f"{C.BRIGHT_RED}Cannot import SSHExecutor. Distributed audit unavailable.{C.RESET}")
            return {}

    if not config or not config.workers:
        if verbose:
            print(f"{C.BRIGHT_YELLOW}No workers configured.{C.RESET}")
            print(f"{C.DIM}Configure workers in the SpiderFoot Control Center > Multi-EC2 C2{C.RESET}")
        return {}

    results: Dict[str, AuditReport] = {}

    # Determine tools to run
    tools_to_run = tools if tools else list(SECURITY_TOOLS.keys())

    if verbose:
        print(f"\n{C.BRIGHT_CYAN}{C.BOLD}Distributed Security Audit{C.RESET}")
        print(f"{C.DIM}{'─' * 50}{C.RESET}")
        print(f"  Workers: {C.BRIGHT_WHITE}{len(config.workers)}{C.RESET}")
        print(f"  Tools: {C.BRIGHT_WHITE}{', '.join(tools_to_run)}{C.RESET}")
        print(f"{C.DIM}{'─' * 50}{C.RESET}\n")

    # Create SSH executor
    executor = SSHExecutor(
        key_path=config.ssh_key_path if hasattr(config, 'ssh_key_path') else None,
        use_agent=True
    )

    # Audit each worker
    for worker in config.workers:
        hostname = worker.hostname
        username = worker.username

        if verbose:
            nickname = getattr(worker, 'nickname', hostname)
            print(f"\n{C.BRIGHT_CYAN}[{nickname}]{C.RESET} {hostname}")

        report = AuditReport(hostname=hostname)

        # Test connection first
        success, msg = executor.test_connection(hostname, username)
        if not success:
            if verbose:
                print(f"  {C.BRIGHT_RED}Connection failed:{C.RESET} {msg}")
            report.errors.append(f"Connection failed: {msg}")
            results[hostname] = report
            continue

        # Install tools if missing (one command for all)
        if verbose:
            print(f"  {C.DIM}Checking/installing tools...{C.RESET}")

        packages = " ".join([SECURITY_TOOLS[t].apt_package for t in tools_to_run])
        install_cmd = f"which chkrootkit || sudo apt-get update -qq && sudo apt-get install -y -qq {packages}"

        executor.execute(hostname, username, install_cmd, timeout=120)

        # Run each tool
        for tool_name in tools_to_run:
            tool = SECURITY_TOOLS.get(tool_name)
            if not tool:
                continue

            if verbose:
                print(f"  {C.BRIGHT_CYAN}[RUNNING]{C.RESET} {tool_name}...", end=" ", flush=True)

            if on_progress:
                on_progress(hostname, tool_name, "running")

            # Build remote command
            cmd = _get_remote_tool_command(tool_name)

            # Execute remotely
            result = executor.execute(
                hostname, username, cmd,
                timeout=tool.timeout + 30  # Extra buffer for SSH
            )

            if on_progress:
                on_progress(hostname, tool_name, "done" if result.success else "error")

            # Parse result
            tool_result = _parse_remote_result(tool_name, result)
            report.add_result(tool_result)

            if verbose:
                if not tool_result.success:
                    print(f"{C.BRIGHT_RED}[ERROR]{C.RESET}")
                elif tool_result.clean:
                    print(f"{C.BRIGHT_GREEN}[CLEAN]{C.RESET}")
                else:
                    print(f"{C.BRIGHT_YELLOW}[FINDINGS]{C.RESET} {len(tool_result.findings)}")

        results[hostname] = report

    # Print summary
    if verbose:
        _print_distributed_summary(results)

    return results


def _get_remote_tool_command(tool_name: str) -> str:
    """Get the command to run a tool remotely."""
    commands = {
        "chkrootkit": "sudo chkrootkit -q 2>/dev/null",
        "rkhunter": "sudo rkhunter --check --skip-keypress --quiet 2>/dev/null",
        "lynis": "sudo lynis audit system --quiet --no-colors 2>/dev/null",
        "debsums": "debsums -c -s 2>/dev/null",
        "unhide": "sudo unhide sys proc 2>/dev/null",
    }
    return commands.get(tool_name, f"sudo {tool_name}")


def _parse_remote_result(tool_name: str, ssh_result: Any) -> ToolResult:
    """Parse SSH execution result into ToolResult."""
    if not ssh_result.success:
        return ToolResult(
            tool=tool_name,
            success=False,
            error=ssh_result.stderr or "SSH execution failed",
            clean=False
        )

    # Reuse the local parsing logic
    from .tools import _parse_tool_output
    import subprocess

    # Create a fake CompletedProcess for the parser
    class FakeResult:
        def __init__(self, stdout, stderr, returncode):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    fake_result = FakeResult(
        ssh_result.stdout,
        ssh_result.stderr,
        ssh_result.return_code
    )

    return _parse_tool_output(tool_name, fake_result)


def _print_distributed_summary(results: Dict[str, AuditReport]):
    """Print summary of distributed audit."""
    print(f"\n{C.DIM}{'═' * 50}{C.RESET}")
    print(f"{C.BOLD}DISTRIBUTED AUDIT SUMMARY{C.RESET}")
    print(f"{C.DIM}{'═' * 50}{C.RESET}")

    clean_count = sum(1 for r in results.values() if r.clean and not r.errors)
    issue_count = sum(1 for r in results.values() if not r.clean)
    error_count = sum(1 for r in results.values() if r.errors)

    print(f"\n  Total workers: {C.BRIGHT_WHITE}{len(results)}{C.RESET}")
    print(f"  Clean: {C.BRIGHT_GREEN}{clean_count}{C.RESET}")
    print(f"  Issues: {C.BRIGHT_YELLOW if issue_count else C.DIM}{issue_count}{C.RESET}")
    print(f"  Errors: {C.BRIGHT_RED if error_count else C.DIM}{error_count}{C.RESET}")

    # List workers with issues
    for hostname, report in results.items():
        if not report.clean:
            print(f"\n  {C.BRIGHT_YELLOW}[ISSUES]{C.RESET} {hostname}")
            for tool, findings in report.findings.items():
                print(f"    {tool}: {len(findings)} finding(s)")

    print(f"\n{C.DIM}{'═' * 50}{C.RESET}")


# =============================================================================
# MENU
# =============================================================================

def security_audit_menu():
    """Interactive security audit menu."""

    def clear_screen():
        os.system('clear' if os.name == 'posix' else 'cls')

    def get_input(prompt: str, default: str = "") -> Optional[str]:
        try:
            if default:
                result = input(f"{C.BRIGHT_MAGENTA}> {prompt} [{default}]: {C.RESET}").strip()
                return result if result else default
            else:
                return input(f"{C.BRIGHT_MAGENTA}> {prompt}: {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            return None

    def print_menu_item(key: str, desc: str, icon: str = ""):
        print(f"  {C.BRIGHT_YELLOW}[{key}]{C.RESET} {icon} {desc}")

    # Try to load distributed config
    distributed_config = None
    try:
        from discovery.worker_config import DistributedConfigManager
        config_mgr = DistributedConfigManager()
        distributed_config = config_mgr.load()
    except ImportError:
        try:
            from ..discovery.worker_config import DistributedConfigManager
            config_mgr = DistributedConfigManager()
            distributed_config = config_mgr.load()
        except:
            pass
    except:
        pass

    has_workers = distributed_config and distributed_config.workers

    while True:
        clear_screen()

        # Banner
        print(f"""
{C.BRIGHT_RED}{C.BOLD}
  ╔═══════════════════════════════════════════════════════════╗
  ║              SECURITY AUDIT MODULE                        ║
  ║         Rootkit & System Integrity Scanner                ║
  ╚═══════════════════════════════════════════════════════════╝
{C.RESET}""")

        # Tool status
        print_tool_status()

        # Worker status
        if has_workers:
            worker_count = len(distributed_config.workers)
            print(f"\n  {C.BRIGHT_CYAN}Workers configured:{C.RESET} {C.BRIGHT_WHITE}{worker_count}{C.RESET}")
        else:
            print(f"\n  {C.DIM}No workers configured (distributed audit unavailable){C.RESET}")

        # Menu
        print(f"\n{C.BRIGHT_CYAN}Options:{C.RESET}")
        print_menu_item("1", "Audit Local Machine", "")
        if has_workers:
            print_menu_item("2", f"Audit All Workers ({len(distributed_config.workers)} machines)", "")
        else:
            print(f"  {C.DIM}[2] Audit All Workers (no workers configured){C.RESET}")
        print_menu_item("3", "Install Security Tools", "")
        print_menu_item("4", "What This Can/Can't Detect", "")
        print_menu_item("Q", "Back to Main Menu", "")
        print()

        choice = get_input("Select option")
        if choice is None:
            choice = 'q'
        choice = choice.lower().strip()

        if choice == 'q':
            return

        elif choice == '1':
            # Local audit
            clear_screen()
            print(f"\n{C.BRIGHT_CYAN}Starting local security audit...{C.RESET}\n")
            audit_local(verbose=True)
            print(f"\n{C.DIM}Press Enter to continue...{C.RESET}")
            try:
                input()
            except:
                pass

        elif choice == '2':
            # Distributed audit
            if not has_workers:
                print(f"\n{C.BRIGHT_YELLOW}No workers configured.{C.RESET}")
                print(f"{C.DIM}Configure workers in SpiderFoot Control Center > Multi-EC2 C2{C.RESET}")
                time.sleep(2)
                continue

            clear_screen()
            print(f"\n{C.BRIGHT_CYAN}Starting distributed security audit...{C.RESET}\n")
            audit_workers(distributed_config, verbose=True)
            print(f"\n{C.DIM}Press Enter to continue...{C.RESET}")
            try:
                input()
            except:
                pass

        elif choice == '3':
            # Install tools
            clear_screen()
            installed, missing = check_tools_installed()

            if not missing:
                print(f"\n{C.BRIGHT_GREEN}All security tools are already installed!{C.RESET}")
                time.sleep(2)
                continue

            print(f"\n{C.BRIGHT_YELLOW}Missing tools:{C.RESET} {', '.join(missing)}")
            confirm = get_input("Install missing tools? (y/n)", "y")

            if confirm and confirm.lower() == 'y':
                install_security_tools(verbose=True)
                print(f"\n{C.DIM}Press Enter to continue...{C.RESET}")
                try:
                    input()
                except:
                    pass

        elif choice == '4':
            # Disclaimer
            clear_screen()
            show_disclaimer()

        else:
            print(f"{C.BRIGHT_YELLOW}Invalid option{C.RESET}")
            time.sleep(1)
