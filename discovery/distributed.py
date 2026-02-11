#!/usr/bin/env python3
"""
distributed.py - Distributed Multi-EC2 SpiderFoot Scanning

Core components for coordinating SpiderFoot scans across multiple EC2 workers.
The master machine (running puppetmaster.py) orchestrates everything via SSH.

Components:
- SSHExecutor: Executes commands on remote workers
- SpiderFootInstaller: Installs SpiderFoot and dependencies on workers
- ResourceDetector: Detects RAM/CPU to recommend parallel scan count
- DomainDistributor: Splits domains evenly across workers
- DistributedScanController: Orchestrates the entire distributed scan
"""

import os
import re
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .worker_config import (
    DistributedConfigManager,
    DistributedConfig,
    WorkerConfig,
)


# =============================================================================
# CONSTANTS
# =============================================================================

# SSH options for security and reliability
# Note: StrictHostKeyChecking=accept-new accepts new keys on first connection
# but rejects if the key changes (prevents MITM attacks on known hosts)
#
# SECURITY WARNING: Never copy .pem files to worker machines!
# The master should be the only machine with the private key.
# If workers need to SSH elsewhere, use -A (agent forwarding) instead.
SSH_OPTIONS = [
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "LogLevel=ERROR",
    "-o", "BatchMode=yes",
]

# SSH options with agent forwarding (for when workers need to access other resources)
# Agent forwarding (-A) allows workers to use your SSH agent without having the private key
SSH_OPTIONS_WITH_AGENT = [
    "-A",  # Enable agent forwarding
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "LogLevel=ERROR",
    "-o", "BatchMode=yes",
]

# Timeouts
DEFAULT_SSH_TIMEOUT = 30
INSTALL_TIMEOUT = 900      # 15 minutes for full install
SCAN_START_TIMEOUT = 120   # 2 minutes to start scans
SCP_TIMEOUT = 600          # 10 minutes for file transfers

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# SpiderFoot intensity presets (modules)
INTENSITY_PRESETS = {
    'all': None,  # All modules (default)
    'footprint': 'sfp_dnsresolve,sfp_dnsbrute,sfp_hackertarget,sfp_robtex,sfp_securitytrails',
    'investigate': 'sfp_dnsresolve,sfp_dnsbrute,sfp_whois,sfp_sslcert,sfp_hackertarget',
    'passive': 'sfp_dnsresolve,sfp_whois,sfp_sslcert',
}

# SpiderFoot version pinning for supply chain security
# Pin to a specific release tag to prevent malicious code injection
# Update this when you want to upgrade SpiderFoot (after reviewing the release)
SPIDERFOOT_VERSION = "v4.0"  # Release tag to clone
SPIDERFOOT_REPO = "https://github.com/smicallef/spiderfoot.git"

# ANSI escape sequence pattern for stripping colored output from SSH commands
# Matches CSI sequences ([), OSC sequences (]), and single-character escapes
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def strip_ansi(text: str) -> str:
    """
    Remove ANSI escape sequences from text.

    SSH command output may contain colored text (from apt, pip, etc.)
    which needs to be stripped for clean display.

    Args:
        text: Text potentially containing ANSI escape sequences

    Returns:
        Clean text without escape sequences
    """
    return ANSI_ESCAPE_PATTERN.sub('', text)


def fix_ssh_auth_sock() -> Tuple[bool, str]:
    """
    Try to fix SSH_AUTH_SOCK by finding the newest valid agent socket.

    This solves the common tmux problem where the SSH agent socket path
    becomes stale after disconnecting and reconnecting SSH sessions.

    Strategy:
    1. First try the stable symlink at ~/.ssh/agent_sock (if it exists)
    2. Otherwise, search /tmp/ssh-*/agent.* for the newest valid socket
    3. Update os.environ['SSH_AUTH_SOCK'] if a working socket is found

    Returns:
        Tuple of (success, message)
    """
    import glob

    # First try the stable symlink (set up by setup_ssh_agent_symlink)
    stable_path = os.path.expanduser("~/.ssh/agent_sock")
    if os.path.exists(stable_path):
        os.environ['SSH_AUTH_SOCK'] = stable_path
        try:
            result = subprocess.run(
                ["ssh-add", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return True, f"Using stable symlink: {stable_path}"
        except Exception:
            pass

    # Search for newest valid agent socket
    sockets = glob.glob("/tmp/ssh-*/agent.*")
    if not sockets:
        return False, "No SSH agent sockets found in /tmp/ssh-*/"

    # Sort by modification time, newest first
    try:
        sockets.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    except Exception:
        pass

    for sock in sockets:
        os.environ['SSH_AUTH_SOCK'] = sock
        try:
            result = subprocess.run(
                ["ssh-add", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return True, f"Found working socket: {sock}"
        except Exception:
            continue

    return False, "No working SSH agent socket found"


def check_ssh_agent_symlink_setup() -> Tuple[bool, str]:
    """
    Check if the SSH agent symlink setup exists in the user's shell config.

    The symlink setup ensures that ~/.ssh/agent_sock always points to
    the current SSH agent socket, which solves tmux compatibility issues.

    Returns:
        Tuple of (is_configured, message)
    """
    # Check both .zshrc and .bashrc
    for rc_file in ["~/.zshrc", "~/.bashrc"]:
        rc_path = os.path.expanduser(rc_file)
        if os.path.exists(rc_path):
            try:
                with open(rc_path, 'r') as f:
                    content = f.read()
                    if 'agent_sock' in content and 'SSH_AUTH_SOCK' in content:
                        return True, f"SSH agent symlink configured in {rc_file}"
            except Exception:
                pass

    return False, "SSH agent symlink not configured"


def setup_ssh_agent_symlink(shell_rc: str = "~/.zshrc") -> Tuple[bool, str]:
    """
    Set up the SSH agent symlink by adding configuration to shell rc file.

    This adds lines to the user's shell config that:
    1. Create a stable symlink at ~/.ssh/agent_sock pointing to the current socket
    2. Export SSH_AUTH_SOCK to use the stable symlink

    This runs on each login, keeping the symlink updated, so tmux sessions
    can use the stable path and always get the current agent socket.

    Args:
        shell_rc: Path to shell rc file (default: ~/.zshrc)

    Returns:
        Tuple of (success, message)
    """
    rc_path = os.path.expanduser(shell_rc)

    # Ensure ~/.ssh directory exists
    ssh_dir = os.path.expanduser("~/.ssh")
    if not os.path.exists(ssh_dir):
        try:
            os.makedirs(ssh_dir, mode=0o700)
        except Exception as e:
            return False, f"Failed to create ~/.ssh directory: {e}"

    # The setup lines to add
    setup_lines = '''
# SSH agent symlink for tmux compatibility (added by puppetmaster)
# This ensures tmux sessions can access your SSH agent after reconnecting
if [ -n "$SSH_AUTH_SOCK" ] && [ "$SSH_AUTH_SOCK" != "$HOME/.ssh/agent_sock" ]; then
    ln -sf "$SSH_AUTH_SOCK" "$HOME/.ssh/agent_sock"
    export SSH_AUTH_SOCK="$HOME/.ssh/agent_sock"
fi
'''

    try:
        # Check if already configured
        if os.path.exists(rc_path):
            with open(rc_path, 'r') as f:
                if 'agent_sock' in f.read():
                    return True, "SSH agent symlink already configured"

        # Append to rc file
        with open(rc_path, 'a') as f:
            f.write(setup_lines)

        # Also create the symlink now if SSH_AUTH_SOCK is set
        current_sock = os.environ.get('SSH_AUTH_SOCK', '')
        if current_sock and os.path.exists(current_sock):
            symlink_path = os.path.join(ssh_dir, "agent_sock")
            try:
                # Remove existing symlink if present
                if os.path.islink(symlink_path):
                    os.unlink(symlink_path)
                os.symlink(current_sock, symlink_path)
                # Update environment to use the new symlink
                os.environ['SSH_AUTH_SOCK'] = symlink_path
            except Exception as e:
                # Non-fatal: symlink will be created on next login
                pass

        return True, f"SSH agent symlink configured in {shell_rc}"

    except Exception as e:
        return False, f"Failed to configure SSH agent symlink: {e}"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SSHResult:
    """Result of an SSH command execution."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool = False


@dataclass
class WorkerProgress:
    """Progress information for a single worker."""
    hostname: str
    nickname: str
    status: str                    # "idle", "scanning", "completed", "error", "unreachable"
    domains_total: int
    domains_completed: int
    domains_failed: int
    running_processes: int
    csv_files_count: int
    last_updated: str
    error_message: Optional[str] = None

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.domains_total == 0:
            return 0.0
        return (self.domains_completed / self.domains_total) * 100


@dataclass
class WorkerSetupResult:
    """Result of setting up a worker."""
    hostname: str
    success: bool
    tmux_installed: bool
    spiderfoot_installed: bool
    apt_updated: bool
    error_message: Optional[str] = None


# =============================================================================
# SSH EXECUTOR
# =============================================================================

class SSHExecutor:
    """
    Executes commands on remote workers via SSH.

    Supports two modes:
    1. Agent mode (RECOMMENDED): Uses ssh-agent for authentication. No key file on EC2.
    2. Key file mode (legacy): Uses a .pem file directly.

    Reuses patterns from upload.py for reliability.
    All commands are properly escaped using shlex.quote().
    """

    def __init__(
        self,
        key_path: str = "",
        timeout: int = DEFAULT_SSH_TIMEOUT,
        use_agent: bool = True
    ):
        """
        Initialize SSH executor.

        Args:
            key_path: Path to SSH private key (.pem file) - only needed if use_agent=False
            timeout: Default timeout for SSH commands in seconds
            use_agent: If True, use ssh-agent instead of key file (RECOMMENDED)
        """
        self.use_agent = use_agent
        self.timeout = timeout

        if use_agent:
            # Agent mode: verify ssh-agent has keys loaded
            self.key_path = ""
            agent_ok, agent_msg = self._check_ssh_agent()
            if not agent_ok:
                raise RuntimeError(
                    f"SSH agent mode enabled but no keys loaded.\n"
                    f"Run: ssh-add ~/.ssh/your-key.pem\n"
                    f"Error: {agent_msg}"
                )
        else:
            # Key file mode (legacy)
            self.key_path = os.path.expanduser(key_path)
            if not os.path.isfile(self.key_path):
                raise FileNotFoundError(f"SSH key not found: {self.key_path}")

    @staticmethod
    def _check_ssh_agent(auto_fix: bool = True) -> Tuple[bool, str]:
        """
        Check if ssh-agent is running and has keys loaded.

        If the initial check fails and auto_fix is True, attempts to fix
        the SSH_AUTH_SOCK environment variable by finding a valid socket.
        This solves tmux compatibility issues where the socket path becomes stale.

        Args:
            auto_fix: If True, attempt to fix SSH_AUTH_SOCK on failure

        Returns:
            Tuple of (success, message)
        """
        def do_check() -> Tuple[bool, str]:
            try:
                result = subprocess.run(
                    ["ssh-add", "-l"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    key_count = len(result.stdout.strip().split('\n'))
                    return True, f"{key_count} key(s) loaded in ssh-agent"
                elif result.returncode == 1:
                    return False, "ssh-agent has no keys loaded"
                else:
                    return False, f"ssh-agent not running or not accessible: {result.stderr}"
            except FileNotFoundError:
                return False, "ssh-add command not found"
            except Exception as e:
                return False, str(e)

        # First attempt
        success, message = do_check()
        if success:
            return success, message

        # If failed and auto_fix is enabled, try to fix SSH_AUTH_SOCK
        if auto_fix:
            fix_success, fix_message = fix_ssh_auth_sock()
            if fix_success:
                # Retry the check with the fixed socket
                success, message = do_check()
                if success:
                    return success, f"{message} (auto-fixed: {fix_message})"

        return success, message

    @staticmethod
    def check_agent_status(auto_fix: bool = True) -> Tuple[bool, str]:
        """Public method to check ssh-agent status."""
        return SSHExecutor._check_ssh_agent(auto_fix=auto_fix)

    def _build_ssh_command(
        self,
        hostname: str,
        username: str,
        command: str,
        timeout: Optional[int] = None,
        use_agent_forwarding: bool = False
    ) -> List[str]:
        """Build SSH command list."""
        timeout = timeout or self.timeout

        cmd = ["ssh"]

        # Add key file if not using agent mode
        if not self.use_agent and self.key_path:
            cmd.extend(["-i", self.key_path])

        cmd.extend(["-o", f"ConnectTimeout={timeout}"])

        # Use agent forwarding options if requested or if in agent mode
        if use_agent_forwarding or self.use_agent:
            cmd.extend(SSH_OPTIONS_WITH_AGENT)
        else:
            cmd.extend(SSH_OPTIONS)

        cmd.extend([
            f"{username}@{hostname}",
            command,
        ])

        return cmd

    def execute(
        self,
        hostname: str,
        username: str,
        command: str,
        timeout: Optional[int] = None,
        retries: int = 1,
        _agent_fix_attempted: bool = False
    ) -> SSHResult:
        """
        Execute a command on a remote worker.

        Args:
            hostname: Worker hostname or IP
            username: SSH username
            command: Command to execute (will be escaped)
            timeout: Timeout in seconds (None = use default)
            retries: Number of retry attempts
            _agent_fix_attempted: Internal flag to prevent infinite recursion

        Returns:
            SSHResult with success status, stdout, stderr, return code
        """
        timeout = timeout or self.timeout

        cmd = self._build_ssh_command(hostname, username, command, timeout)

        last_error = None
        was_timeout = False
        for attempt in range(retries):
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout + 10,  # Allow a bit more than SSH timeout
                )

                # Check for SSH authentication/connection failures that might be fixed by refreshing agent
                if result.returncode != 0 and self.use_agent and not _agent_fix_attempted:
                    stderr_lower = result.stderr.lower()
                    # Common SSH agent-related error patterns
                    agent_errors = [
                        'permission denied',
                        'connection closed',
                        'connection reset',
                        'no identities',
                        'agent refused',
                        'authentication failed',
                        'could not read from remote',
                    ]
                    if any(err in stderr_lower for err in agent_errors):
                        # Try to fix SSH agent and retry
                        fix_success, _ = fix_ssh_auth_sock()
                        if fix_success:
                            # Rebuild command (env may have changed) and retry
                            return self.execute(
                                hostname, username, command, timeout, retries,
                                _agent_fix_attempted=True
                            )

                return SSHResult(
                    success=(result.returncode == 0),
                    stdout=strip_ansi(result.stdout),
                    stderr=strip_ansi(result.stderr),
                    return_code=result.returncode,
                )

            except subprocess.TimeoutExpired:
                last_error = "Command timed out"
                was_timeout = True
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)

            except Exception as e:
                last_error = str(e)
                was_timeout = False  # Not a timeout error
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)

        return SSHResult(
            success=False,
            stdout="",
            stderr=last_error or "Unknown error",
            return_code=-1,
            timed_out=was_timeout,
        )

    def test_connection(self, hostname: str, username: str) -> Tuple[bool, str]:
        """
        Test SSH connectivity to a worker.

        Args:
            hostname: Worker hostname or IP
            username: SSH username

        Returns:
            Tuple of (success, message)
        """
        result = self.execute(
            hostname, username,
            "echo 'CONNECTION_OK'",
            timeout=15,
            retries=2
        )

        if result.success and "CONNECTION_OK" in result.stdout:
            return True, "Connected successfully"
        elif result.timed_out:
            return False, "Connection timed out"
        else:
            return False, result.stderr.strip() or "Connection failed"

    def upload_file(
        self,
        hostname: str,
        username: str,
        local_path: str,
        remote_path: str,
        timeout: int = SCP_TIMEOUT
    ) -> Tuple[bool, str]:
        """
        Upload a file to a worker via SCP.

        Args:
            hostname: Worker hostname or IP
            username: SSH username
            local_path: Local file path
            remote_path: Remote destination path
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, message)
        """
        if not os.path.isfile(local_path):
            return False, f"Local file not found: {local_path}"

        # Create remote directory if needed
        remote_dir = os.path.dirname(remote_path)
        if remote_dir:
            mkdir_result = self.execute(
                hostname, username,
                f"mkdir -p {shlex.quote(remote_dir)}",
                timeout=30
            )
            if not mkdir_result.success:
                return False, f"Could not create remote directory: {mkdir_result.stderr}"

        cmd = ["scp"]
        # Add key file if not using agent mode
        if not self.use_agent and self.key_path:
            cmd.extend(["-i", self.key_path])
        cmd.extend(SSH_OPTIONS_WITH_AGENT if self.use_agent else SSH_OPTIONS)
        cmd.extend([
            local_path,
            f"{username}@{hostname}:{remote_path}",
        ])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                return True, "Upload successful"
            else:
                return False, result.stderr.strip() or "Upload failed"

        except subprocess.TimeoutExpired:
            return False, "Upload timed out"
        except Exception as e:
            return False, str(e)

    def download_file(
        self,
        hostname: str,
        username: str,
        remote_path: str,
        local_path: str,
        timeout: int = SCP_TIMEOUT
    ) -> Tuple[bool, str]:
        """
        Download a file from a worker via SCP.

        Args:
            hostname: Worker hostname or IP
            username: SSH username
            remote_path: Remote file path
            local_path: Local destination path
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, message)
        """
        # Create local directory if needed
        local_dir = os.path.dirname(local_path)
        if local_dir:
            os.makedirs(local_dir, exist_ok=True)

        cmd = ["scp"]
        # Add key file if not using agent mode
        if not self.use_agent and self.key_path:
            cmd.extend(["-i", self.key_path])
        cmd.extend(SSH_OPTIONS_WITH_AGENT if self.use_agent else SSH_OPTIONS)
        cmd.extend([
            f"{username}@{hostname}:{remote_path}",
            local_path,
        ])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                return True, "Download successful"
            else:
                return False, result.stderr.strip() or "Download failed"

        except subprocess.TimeoutExpired:
            return False, "Download timed out"
        except Exception as e:
            return False, str(e)

    def download_directory(
        self,
        hostname: str,
        username: str,
        remote_dir: str,
        local_dir: str,
        file_pattern: str = "*",
        timeout: int = SCP_TIMEOUT
    ) -> Tuple[bool, str, int]:
        """
        Download files from a remote directory.

        Args:
            hostname: Worker hostname or IP
            username: SSH username
            remote_dir: Remote directory path
            local_dir: Local destination directory
            file_pattern: Glob pattern for files (default: *)
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, message, file_count)
        """
        # Validate file_pattern to prevent command injection
        # Only allow safe characters: alphanumeric, *, ?, ., -, _
        import re
        if not re.match(r'^[\w\*\?\.\-]+$', file_pattern):
            return False, f"Invalid file pattern: {file_pattern}", 0

        os.makedirs(local_dir, exist_ok=True)

        # First, list files to get count
        list_result = self.execute(
            hostname, username,
            f"ls -1 {shlex.quote(remote_dir)}/{file_pattern} 2>/dev/null | wc -l",
            timeout=30
        )

        try:
            file_count = int(list_result.stdout.strip())
        except ValueError:
            file_count = 0

        if file_count == 0:
            return True, "No files to download", 0

        # Use rsync if available, fall back to scp
        rsync_check = self.execute(hostname, username, "which rsync", timeout=10)

        if rsync_check.success:
            # Use rsync - build SSH command for -e option
            ssh_opts = SSH_OPTIONS_WITH_AGENT if self.use_agent else SSH_OPTIONS
            if self.use_agent:
                ssh_cmd = "ssh -A " + " ".join(ssh_opts[1:])  # Skip -A, already included
            else:
                ssh_cmd = f"ssh -i {self.key_path} " + " ".join(ssh_opts)
            cmd = [
                "rsync", "-avz", "--progress",
                "-e", ssh_cmd,
                f"{username}@{hostname}:{remote_dir}/{file_pattern}",
                local_dir + "/",
            ]
        else:
            # Fall back to scp
            cmd = ["scp", "-r"]
            if not self.use_agent and self.key_path:
                cmd.extend(["-i", self.key_path])
            cmd.extend(SSH_OPTIONS_WITH_AGENT if self.use_agent else SSH_OPTIONS)
            cmd.extend([
                f"{username}@{hostname}:{remote_dir}/{file_pattern}",
                local_dir + "/",
            ])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                # Count actual downloaded files
                actual_count = len([f for f in os.listdir(local_dir) if os.path.isfile(os.path.join(local_dir, f))])
                return True, f"Downloaded {actual_count} files", actual_count
            else:
                return False, result.stderr.strip() or "Download failed", 0

        except subprocess.TimeoutExpired:
            return False, "Download timed out", 0
        except Exception as e:
            return False, str(e), 0


# =============================================================================
# RESOURCE DETECTOR
# =============================================================================

class ResourceDetector:
    """
    Detects compute resources on workers to recommend optimal parallelism.
    """

    # RAM to parallel scans recommendation for CLI mode (SQLite constrained)
    RAM_TO_PARALLEL_CLI = {
        4: 3,    # 4GB -> 3 parallel
        8: 5,    # 8GB -> 5 parallel
        16: 7,   # 16GB -> 7 parallel
        32: 9,   # 32GB -> 9 parallel
        64: 10,  # 64GB+ -> 10 parallel (max due to SQLite locks)
    }

    # RAM to parallel scans for WebAPI mode (no SQLite contention)
    RAM_TO_PARALLEL_WEBAPI = {
        4: 5,     # 4GB -> 5 parallel
        8: 10,    # 8GB -> 10 parallel
        16: 20,   # 16GB -> 20 parallel
        32: 35,   # 32GB -> 35 parallel
        64: 50,   # 64GB+ -> 50 parallel
    }

    # Default to CLI mode limits (backwards compatible)
    RAM_TO_PARALLEL = RAM_TO_PARALLEL_CLI

    def __init__(self, ssh_executor: SSHExecutor):
        """
        Initialize resource detector.

        Args:
            ssh_executor: SSH executor for running commands
        """
        self.ssh = ssh_executor

    def detect_resources(
        self,
        hostname: str,
        username: str,
        scan_mode: str = "cli"
    ) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Detect RAM and CPU on a worker.

        Args:
            hostname: Worker hostname
            username: SSH username
            scan_mode: "cli" or "webapi" - affects parallelism recommendation

        Returns:
            Tuple of (ram_gb, cpu_cores, recommended_parallel)
        """
        # Get RAM in GB
        ram_result = self.ssh.execute(
            hostname, username,
            "free -g | awk '/Mem:/{print $2}'",
            timeout=15
        )

        try:
            ram_gb = int(ram_result.stdout.strip())
        except ValueError:
            ram_gb = None

        # Get CPU cores
        cpu_result = self.ssh.execute(
            hostname, username,
            "nproc",
            timeout=15
        )

        try:
            cpu_cores = int(cpu_result.stdout.strip())
        except ValueError:
            cpu_cores = None

        # Calculate recommended parallel scans based on mode
        recommended = None
        if ram_gb:
            # Use appropriate limits based on scan mode
            ram_to_parallel = (
                self.RAM_TO_PARALLEL_WEBAPI if scan_mode == "webapi"
                else self.RAM_TO_PARALLEL_CLI
            )
            max_parallel = 50 if scan_mode == "webapi" else 10

            for ram_threshold, parallel in sorted(ram_to_parallel.items()):
                if ram_gb >= ram_threshold:
                    recommended = parallel

            # Cap at mode-appropriate max
            if recommended and recommended > max_parallel:
                recommended = max_parallel

        return ram_gb, cpu_cores, recommended

    def detect_all_workers(
        self,
        workers: List[WorkerConfig],
        on_progress: Optional[Callable[[str, str], None]] = None
    ) -> Dict[str, Tuple[Optional[int], Optional[int], Optional[int]]]:
        """
        Detect resources on all workers in parallel.

        Args:
            workers: List of worker configs
            on_progress: Optional callback(hostname, status)

        Returns:
            Dict mapping hostname to (ram_gb, cpu_cores, recommended_parallel)
        """
        results = {}

        def detect_one(worker: WorkerConfig):
            if on_progress:
                on_progress(worker.hostname, "detecting")

            ram, cpu, rec = self.detect_resources(worker.hostname, worker.username)

            if on_progress:
                status = f"{ram}GB/{cpu}cores" if ram and cpu else "failed"
                on_progress(worker.hostname, status)

            return worker.hostname, (ram, cpu, rec)

        with ThreadPoolExecutor(max_workers=min(20, len(workers))) as executor:
            futures = [executor.submit(detect_one, w) for w in workers]

            for future in as_completed(futures):
                hostname, resources = future.result()
                results[hostname] = resources

        return results

    def security_check_worker(
        self,
        hostname: str,
        username: str
    ) -> Tuple[bool, List[str]]:
        """
        Check for security issues on a worker.

        Scans for:
        - .pem files (private keys should never be on workers)
        - AWS credentials files
        - Other sensitive files that shouldn't be on workers

        Args:
            hostname: Worker hostname
            username: SSH username

        Returns:
            Tuple of (is_safe, list_of_warnings)
        """
        warnings = []

        # Check for .pem files in common locations
        pem_check = self.ssh.execute(
            hostname, username,
            "find ~/ /home /tmp -name '*.pem' -type f 2>/dev/null | head -10",
            timeout=30
        )
        if pem_check.success and pem_check.stdout.strip():
            pem_files = pem_check.stdout.strip().split('\n')
            # Separate CA certificates from potential private keys
            ca_cert_patterns = ['cacert.pem', 'ca-bundle.pem', 'ca-certificates', 'site-packages', 'certifi']
            ca_certs = []
            private_keys = []
            for pem_file in pem_files:
                pem_lower = pem_file.lower()
                if any(pattern in pem_lower for pattern in ca_cert_patterns):
                    ca_certs.append(pem_file)
                else:
                    private_keys.append(pem_file)

            # Report private keys as CRITICAL
            if private_keys:
                warnings.append(f"CRITICAL: Found .pem files on worker: {', '.join(private_keys)}")
            # Report CA certs as INFO (not critical)
            if ca_certs:
                warnings.append(f"INFO: Found public CA certificates (safe): {', '.join(ca_certs[:3])}")

        # Check for AWS credentials
        aws_check = self.ssh.execute(
            hostname, username,
            "ls -la ~/.aws/credentials 2>/dev/null",
            timeout=10
        )
        if aws_check.success and aws_check.return_code == 0:
            warnings.append("CRITICAL: Found AWS credentials file (~/.aws/credentials) on worker")

        # Check for SSH private keys (id_rsa, id_ed25519, etc.)
        ssh_key_check = self.ssh.execute(
            hostname, username,
            "ls ~/.ssh/id_* 2>/dev/null | grep -v '.pub$' | head -5",
            timeout=10
        )
        if ssh_key_check.success and ssh_key_check.stdout.strip():
            key_files = ssh_key_check.stdout.strip().split('\n')
            warnings.append(f"WARNING: Found SSH private keys on worker: {', '.join(key_files)}")

        # Only count CRITICAL and WARNING as issues, not INFO
        critical_warnings = [w for w in warnings if not w.startswith("INFO:")]
        is_safe = len(critical_warnings) == 0
        return is_safe, warnings

    def security_check_all_workers(
        self,
        workers: List['WorkerConfig'],
        on_progress: Optional[Callable[[str, str], None]] = None
    ) -> Dict[str, Tuple[bool, List[str]]]:
        """
        Run security checks on all workers.

        Args:
            workers: List of worker configs
            on_progress: Optional callback(hostname, status)

        Returns:
            Dict mapping hostname to (is_safe, warnings)
        """
        results = {}

        def check_one(worker: 'WorkerConfig'):
            if on_progress:
                on_progress(worker.hostname, "checking")

            is_safe, warnings = self.security_check_worker(worker.hostname, worker.username)

            if on_progress:
                status = "SAFE" if is_safe else f"ISSUES: {len(warnings)}"
                on_progress(worker.hostname, status)

            return worker.hostname, (is_safe, warnings)

        with ThreadPoolExecutor(max_workers=min(20, len(workers))) as executor:
            futures = [executor.submit(check_one, w) for w in workers]

            for future in as_completed(futures):
                hostname, result = future.result()
                results[hostname] = result

        return results


# =============================================================================
# LOCAL SECURITY CHECK
# =============================================================================

def check_local_security(puppetmaster_dir: Optional[str] = None) -> Tuple[bool, List[str]]:
    """
    Check for security issues on the local machine (master).

    Scans for:
    - .pem files in puppetmaster directory (should NEVER be there)
    - AWS credentials in common locations
    - SSH private keys that could be accidentally uploaded

    Args:
        puppetmaster_dir: Path to puppetmaster directory (auto-detected if None)

    Returns:
        Tuple of (is_safe, list_of_warnings)
    """
    warnings = []

    # Auto-detect puppetmaster directory
    if puppetmaster_dir is None:
        puppetmaster_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Check for .pem files in puppetmaster directory
    dangerous_extensions = ['.pem', '.key', '.ppk', '.p12', '.pfx']
    for root, dirs, files in os.walk(puppetmaster_dir):
        # Skip hidden directories and venv
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', '__pycache__', 'node_modules')]

        for f in files:
            for ext in dangerous_extensions:
                if f.lower().endswith(ext):
                    full_path = os.path.join(root, f)
                    warnings.append(f"CRITICAL: Found {ext} file in puppetmaster dir: {full_path}")

    # Check for AWS credentials in puppetmaster dir
    aws_dir = os.path.join(puppetmaster_dir, '.aws')
    if os.path.isdir(aws_dir):
        warnings.append(f"CRITICAL: Found .aws directory in puppetmaster: {aws_dir}")

    creds_file = os.path.join(puppetmaster_dir, 'credentials')
    if os.path.isfile(creds_file):
        warnings.append(f"CRITICAL: Found credentials file in puppetmaster: {creds_file}")

    # Check for .env files
    env_file = os.path.join(puppetmaster_dir, '.env')
    if os.path.isfile(env_file):
        warnings.append(f"WARNING: Found .env file in puppetmaster: {env_file}")

    is_safe = len(warnings) == 0
    return is_safe, warnings


def run_preflight_security_check(
    config_manager: 'DistributedConfigManager',
    check_workers: bool = True,
    on_progress: Optional[Callable[[str, str], None]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Run comprehensive pre-flight security check before starting scans.

    Checks:
    1. Local puppetmaster directory for sensitive files
    2. SSH agent status (if using agent mode)
    3. Worker machines for sensitive files (optional)

    Args:
        config_manager: Configuration manager
        check_workers: Whether to check remote workers (slower but more thorough)
        on_progress: Optional callback(component, status)

    Returns:
        Tuple of (all_safe, details_dict)
    """
    results = {
        'local': {'safe': True, 'warnings': []},
        'agent': {'safe': True, 'message': ''},
        'workers': {}
    }

    # 1. Check local directory
    if on_progress:
        on_progress("local", "checking")
    local_safe, local_warnings = check_local_security()
    results['local'] = {'safe': local_safe, 'warnings': local_warnings}
    if on_progress:
        on_progress("local", "SAFE" if local_safe else f"ISSUES: {len(local_warnings)}")

    # 2. Check SSH agent (if using agent mode)
    if config_manager.config.use_ssh_agent:
        if on_progress:
            on_progress("ssh-agent", "checking")
        agent_ok, agent_msg = SSHExecutor.check_agent_status()
        results['agent'] = {'safe': agent_ok, 'message': agent_msg}
        if on_progress:
            on_progress("ssh-agent", "OK" if agent_ok else "NO KEYS")

    # 3. Check workers (if requested and possible)
    if check_workers and config_manager.has_ssh_key():
        workers = config_manager.get_enabled_workers()
        if workers:
            try:
                ssh = SSHExecutor(
                    key_path=config_manager.config.ssh_key_path,
                    timeout=config_manager.config.ssh_timeout,
                    use_agent=config_manager.config.use_ssh_agent
                )
                resource_detector = ResourceDetector(ssh)

                worker_results = resource_detector.security_check_all_workers(
                    workers,
                    on_progress=on_progress
                )
                results['workers'] = worker_results
            except Exception as e:
                results['workers'] = {'error': str(e)}

    # Determine overall safety
    all_safe = results['local']['safe']
    if config_manager.config.use_ssh_agent and not results['agent']['safe']:
        all_safe = False
    for hostname, (is_safe, _) in results.get('workers', {}).items():
        if isinstance(is_safe, bool) and not is_safe:
            all_safe = False
            break

    return all_safe, results


def check_ec2_instances(known_hostnames: Optional[List[str]] = None) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Check for EC2 instances in all regions using AWS CLI.

    This helps detect rogue instances that an attacker may have launched.

    Args:
        known_hostnames: List of expected instance hostnames/IPs. If provided,
                        instances not in this list are flagged as unknown.

    Returns:
        Tuple of (aws_cli_available, list_of_instances)
        Each instance is a dict with: region, instance_id, state, type, public_ip, launch_time
    """
    known_hostnames = known_hostnames or []

    # Check if AWS CLI is available
    try:
        result = subprocess.run(
            ["aws", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False, []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, []

    # Get list of all regions
    try:
        regions_result = subprocess.run(
            ["aws", "ec2", "describe-regions", "--query", "Regions[].RegionName", "--output", "text"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if regions_result.returncode != 0:
            return False, []

        regions = regions_result.stdout.strip().split()
    except Exception:
        # Default to common regions if we can't list them
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"]

    all_instances = []

    for region in regions:
        try:
            # Query instances in this region
            cmd = [
                "aws", "ec2", "describe-instances",
                "--region", region,
                "--query", "Reservations[].Instances[].[InstanceId,State.Name,InstanceType,PublicIpAddress,LaunchTime]",
                "--output", "text"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    parts = line.split('\t')
                    if len(parts) >= 5:
                        instance_id, state, inst_type, public_ip, launch_time = parts[:5]

                        # Check if this is a known instance
                        is_known = False
                        if public_ip and public_ip != 'None':
                            for hostname in known_hostnames:
                                if public_ip in hostname or hostname in public_ip:
                                    is_known = True
                                    break

                        all_instances.append({
                            'region': region,
                            'instance_id': instance_id,
                            'state': state,
                            'type': inst_type,
                            'public_ip': public_ip if public_ip != 'None' else None,
                            'launch_time': launch_time,
                            'is_known': is_known,
                        })
        except Exception:
            # Skip regions that fail
            continue

    return True, all_instances


# =============================================================================
# SPIDERFOOT INSTALLER
# =============================================================================

class SpiderFootInstaller:
    """
    Installs SpiderFoot and dependencies on remote workers.
    """

    def __init__(self, ssh_executor: SSHExecutor):
        """
        Initialize installer.

        Args:
            ssh_executor: SSH executor for running commands
        """
        self.ssh = ssh_executor

    def check_tmux_installed(self, hostname: str, username: str) -> bool:
        """Check if tmux is installed on worker."""
        result = self.ssh.execute(
            hostname, username,
            "which tmux",
            timeout=15
        )
        return result.success

    def check_spiderfoot_installed(
        self,
        hostname: str,
        username: str,
        install_dir: str
    ) -> Tuple[bool, str]:
        """
        Check if SpiderFoot is installed on a worker.

        Args:
            hostname: Worker hostname
            username: SSH username
            install_dir: Expected SpiderFoot directory

        Returns:
            Tuple of (installed, version_or_error)
        """
        install_dir = install_dir.replace("~", f"/home/{username}")

        # Check if sf.py exists
        check_result = self.ssh.execute(
            hostname, username,
            f"test -f {shlex.quote(install_dir)}/sf.py && echo 'EXISTS'",
            timeout=15
        )

        if not check_result.success or "EXISTS" not in check_result.stdout:
            return False, "SpiderFoot not found"

        # Try to get version
        version_result = self.ssh.execute(
            hostname, username,
            f"cd {shlex.quote(install_dir)} && source venv/bin/activate && python3 sf.py --version 2>/dev/null || echo 'unknown'",
            timeout=30
        )

        version = version_result.stdout.strip() or "installed"
        return True, version

    def install_apt_updates(
        self,
        hostname: str,
        username: str,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Run apt update and full-upgrade on a worker.

        Args:
            hostname: Worker hostname
            username: SSH username
            on_progress: Optional progress callback

        Returns:
            Tuple of (success, message)
        """
        if on_progress:
            on_progress("Running apt update...")

        # apt update
        update_result = self.ssh.execute(
            hostname, username,
            "sudo apt update -qq",
            timeout=300,
            retries=2
        )

        if not update_result.success:
            return False, f"apt update failed: {update_result.stderr}"

        if on_progress:
            on_progress("Running apt full-upgrade (this may take a while)...")

        # apt full-upgrade
        upgrade_result = self.ssh.execute(
            hostname, username,
            "sudo DEBIAN_FRONTEND=noninteractive apt full-upgrade -y -qq",
            timeout=600,
            retries=1
        )

        if not upgrade_result.success:
            return False, f"apt upgrade failed: {upgrade_result.stderr}"

        return True, "System updated successfully"

    def install_tmux(
        self,
        hostname: str,
        username: str
    ) -> Tuple[bool, str]:
        """
        Install tmux on a worker.

        Args:
            hostname: Worker hostname
            username: SSH username

        Returns:
            Tuple of (success, message)
        """
        result = self.ssh.execute(
            hostname, username,
            "sudo apt install -y -qq tmux",
            timeout=120,
            retries=2
        )

        if result.success:
            return True, "tmux installed"
        else:
            return False, f"Failed to install tmux: {result.stderr}"

    def install_spiderfoot(
        self,
        hostname: str,
        username: str,
        install_dir: str,
        work_dir: str,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Install SpiderFoot on a worker.

        Args:
            hostname: Worker hostname
            username: SSH username
            install_dir: Directory to install SpiderFoot
            work_dir: Work directory for scans
            on_progress: Optional progress callback

        Returns:
            Tuple of (success, message)
        """
        install_dir = install_dir.replace("~", f"/home/{username}")
        work_dir = work_dir.replace("~", f"/home/{username}")

        steps = [
            ("Installing dependencies",
             "sudo apt install -y -qq git python3-venv python3-pip libxml2-dev libxslt1-dev python3-dev build-essential"),

            ("Wiping old installation",
             f"rm -rf {install_dir} {work_dir} ~/.spiderfoot"),

            ("Cloning fresh SpiderFoot",
             f"git clone --depth 1 --branch {SPIDERFOOT_VERSION} {SPIDERFOOT_REPO} {shlex.quote(install_dir)}"),

            ("Creating virtual environment",
             f"cd {shlex.quote(install_dir)} && python3 -m venv venv"),

            ("Upgrading pip and installing pip-tools",
             f"{shlex.quote(install_dir)}/venv/bin/pip install --upgrade pip setuptools wheel pip-tools"),

            ("Removing lxml from requirements.txt",
             f"sed -i '/^lxml/d' {shlex.quote(install_dir)}/requirements.txt"),

            # Install lxml binary wheel - pinned version for reproducibility
            # Note: Hash verification skipped because wheel hash is platform-specific
            # Security: pip uses HTTPS + PyPI's TLS, version pinning prevents upgrade attacks
            ("Installing lxml binary wheel",
             f"{shlex.quote(install_dir)}/venv/bin/pip install --no-cache-dir --only-binary=lxml 'lxml==5.3.1'"),

            # PyYAML has Cython build issues with Python 3.13 - install binary wheel
            ("Removing PyYAML from requirements.txt",
             f"sed -i '/^[Pp]y[Yy][Aa][Mm][Ll]/d' {shlex.quote(install_dir)}/requirements.txt"),

            # Install PyYAML binary wheel - pinned version for reproducibility
            ("Installing PyYAML binary wheel",
             f"{shlex.quote(install_dir)}/venv/bin/pip install --no-cache-dir --only-binary=:all: 'PyYAML==6.0.2'"),

            # Generate hash-pinned requirements and install with verification
            # This prevents supply chain attacks by verifying package integrity
            ("Generating hash-pinned requirements",
             f"cd {shlex.quote(install_dir)} && ./venv/bin/pip-compile --generate-hashes requirements.txt -o requirements.locked.txt 2>/dev/null || cp requirements.txt requirements.locked.txt"),

            ("Installing Python dependencies with hash verification",
             f"cd {shlex.quote(install_dir)} && ./venv/bin/pip install --no-cache-dir --require-hashes -r requirements.locked.txt 2>/dev/null || ./venv/bin/pip install --no-cache-dir -r requirements.txt"),

            ("Verifying installation",
             f"cd {shlex.quote(install_dir)} && ./venv/bin/python3 sf.py --help"),
        ]

        # Different timeouts for different steps
        step_timeouts = {
            "Installing dependencies": 300,
            "Wiping old installation": 60,
            "Cloning fresh SpiderFoot": 300,
            "Creating virtual environment": 120,
            "Upgrading pip and installing pip-tools": 180,
            "Removing lxml from requirements.txt": 30,
            "Installing lxml binary wheel": 300,
            "Removing PyYAML from requirements.txt": 30,
            "Installing PyYAML binary wheel": 300,
            "Generating hash-pinned requirements": 300,  # pip-compile can be slow
            "Installing Python dependencies with hash verification": 600,
            "Verifying installation": 60,
        }

        for step_name, command in steps:
            if on_progress:
                on_progress(step_name)

            timeout = step_timeouts.get(step_name, 300)

            result = self.ssh.execute(
                hostname, username,
                command,
                timeout=timeout,
                retries=2
            )

            if not result.success:
                error_msg = result.stderr or result.stdout or f"exit code {result.return_code}"
                return False, f"{step_name} failed: {error_msg}"

        return True, "SpiderFoot installed successfully"

    def setup_work_directory(
        self,
        hostname: str,
        username: str,
        work_dir: str
    ) -> Tuple[bool, str]:
        """
        Create the work directory structure on a worker.

        Args:
            hostname: Worker hostname
            username: SSH username
            work_dir: Work directory path

        Returns:
            Tuple of (success, message)
        """
        work_dir = work_dir.replace("~", f"/home/{username}")

        result = self.ssh.execute(
            hostname, username,
            f"mkdir -p {shlex.quote(work_dir)}/output {shlex.quote(work_dir)}/domains {shlex.quote(work_dir)}/logs",
            timeout=30
        )

        if result.success:
            return True, "Work directory created"
        else:
            return False, f"Failed to create work directory: {result.stderr}"

    def full_setup(
        self,
        hostname: str,
        username: str,
        install_dir: str,
        work_dir: str,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> WorkerSetupResult:
        """
        Perform full worker setup: apt update, tmux, SpiderFoot, work directory.

        Args:
            hostname: Worker hostname
            username: SSH username
            install_dir: SpiderFoot install directory
            work_dir: Work directory for scans
            on_progress: Optional progress callback

        Returns:
            WorkerSetupResult with detailed status
        """
        result = WorkerSetupResult(
            hostname=hostname,
            success=False,
            tmux_installed=False,
            spiderfoot_installed=False,
            apt_updated=False,
        )

        # 1. apt update/upgrade
        if on_progress:
            on_progress(f"[{hostname}] Updating system...")

        apt_success, apt_msg = self.install_apt_updates(hostname, username, on_progress)
        result.apt_updated = apt_success

        if not apt_success:
            result.error_message = apt_msg
            return result

        # 2. Install tmux
        if on_progress:
            on_progress(f"[{hostname}] Installing tmux...")

        if not self.check_tmux_installed(hostname, username):
            tmux_success, tmux_msg = self.install_tmux(hostname, username)
            result.tmux_installed = tmux_success

            if not tmux_success:
                result.error_message = tmux_msg
                return result
        else:
            result.tmux_installed = True

        # 3. Install SpiderFoot (ALWAYS reinstall to ensure clean state)
        if on_progress:
            on_progress(f"[{hostname}] Installing SpiderFoot...")

        # Force fresh installation every time
        sf_success, sf_msg = self.install_spiderfoot(
            hostname, username, install_dir, work_dir,
            lambda msg: on_progress(f"[{hostname}] {msg}") if on_progress else None
        )
        result.spiderfoot_installed = sf_success

        if not sf_success:
            result.error_message = sf_msg
            return result

        # 4. Setup work directory
        if on_progress:
            on_progress(f"[{hostname}] Setting up work directory...")

        dir_success, dir_msg = self.setup_work_directory(hostname, username, work_dir)

        if not dir_success:
            result.error_message = dir_msg
            return result

        result.success = True
        return result


# =============================================================================
# DOMAIN DISTRIBUTOR
# =============================================================================

class DomainDistributor:
    """
    Splits domains evenly across workers.
    """

    @staticmethod
    def split_domains(
        domains: List[str],
        num_workers: int
    ) -> List[List[str]]:
        """
        Split domain list evenly across workers.

        Args:
            domains: List of domains to scan
            num_workers: Number of workers

        Returns:
            List of domain lists, one per worker
        """
        if num_workers <= 0:
            return []

        if num_workers == 1:
            return [domains]

        # Calculate base size and remainder
        base_size = len(domains) // num_workers
        remainder = len(domains) % num_workers

        result = []
        start = 0

        for i in range(num_workers):
            # First 'remainder' workers get one extra domain
            size = base_size + (1 if i < remainder else 0)
            result.append(domains[start:start + size])
            start += size

        return result

    @staticmethod
    def create_domain_file(domains: List[str], output_path: str) -> str:
        """
        Create a domain file for upload to worker.

        Args:
            domains: List of domains
            output_path: Where to write the file

        Returns:
            Path to created file
        """
        with open(output_path, 'w') as f:
            for domain in domains:
                f.write(domain.strip() + '\n')

        return output_path


# =============================================================================
# DISTRIBUTED SCAN CONTROLLER
# =============================================================================

class DistributedScanController:
    """
    Orchestrates distributed SpiderFoot scanning across multiple EC2 workers.

    This is the main controller that coordinates:
    - Worker validation
    - Domain distribution
    - Scan execution via tmux
    - Progress monitoring
    - Result collection
    """

    def __init__(self, config_manager: DistributedConfigManager):
        """
        Initialize the scan controller.

        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.config = config_manager.config

        if not config_manager.has_ssh_key():
            if self.config.use_ssh_agent:
                raise ValueError(
                    "SSH agent mode enabled but no keys loaded.\n"
                    "Run: ssh-add ~/.ssh/your-key.pem"
                )
            else:
                raise ValueError("SSH key not configured. Use set_ssh_key() first.")

        self.ssh = SSHExecutor(
            key_path=self.config.ssh_key_path,
            timeout=self.config.ssh_timeout,
            use_agent=self.config.use_ssh_agent
        )
        self.installer = SpiderFootInstaller(self.ssh)
        self.resource_detector = ResourceDetector(self.ssh)
        self._last_submit_error: Optional[str] = None  # For debugging scan submission failures

    def validate_workers(
        self,
        on_progress: Optional[Callable[[str, str], None]] = None
    ) -> Dict[str, Tuple[bool, str]]:
        """
        Validate connectivity to all enabled workers.

        Args:
            on_progress: Optional callback(hostname, status)

        Returns:
            Dict mapping hostname to (success, message)
        """
        workers = self.config_manager.get_enabled_workers()
        results = {}

        def validate_one(worker: WorkerConfig):
            if on_progress:
                on_progress(worker.hostname, "connecting...")

            success, message = self.ssh.test_connection(worker.hostname, worker.username)

            # Update worker status
            self.config_manager.update_worker(
                worker.hostname,
                status="ready" if success else "error",
                last_seen=datetime.now().isoformat() if success else None,
            )

            if on_progress:
                on_progress(worker.hostname, "OK" if success else f"FAILED: {message}")

            return worker.hostname, (success, message)

        with ThreadPoolExecutor(max_workers=min(20, len(workers))) as executor:
            futures = [executor.submit(validate_one, w) for w in workers]

            for future in as_completed(futures):
                hostname, result = future.result()
                results[hostname] = result

        return results

    def setup_all_workers(
        self,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Dict[str, WorkerSetupResult]:
        """
        Setup all enabled workers (apt update, tmux, SpiderFoot).

        Args:
            on_progress: Optional progress callback

        Returns:
            Dict mapping hostname to WorkerSetupResult
        """
        workers = self.config_manager.get_enabled_workers()
        results = {}

        # Setup workers sequentially to avoid overwhelming apt
        for worker in workers:
            if on_progress:
                on_progress(f"Setting up {worker.get_display_name()}...")

            result = self.installer.full_setup(
                worker.hostname,
                worker.username,
                self.config.spiderfoot_install_dir,
                self.config.remote_work_dir,
                on_progress
            )

            # Update worker config
            self.config_manager.update_worker(
                worker.hostname,
                tmux_installed=result.tmux_installed,
                spiderfoot_installed=result.spiderfoot_installed,
                status="ready" if result.success else "error",
            )

            results[worker.hostname] = result

        return results

    def detect_all_resources(
        self,
        on_progress: Optional[Callable[[str, str], None]] = None
    ) -> Dict[str, Tuple[Optional[int], Optional[int], Optional[int]]]:
        """
        Detect resources on all enabled workers.

        Args:
            on_progress: Optional callback(hostname, status)

        Returns:
            Dict mapping hostname to (ram_gb, cpu_cores, recommended_parallel)
        """
        workers = self.config_manager.get_enabled_workers()
        results = self.resource_detector.detect_all_workers(workers, on_progress)

        # Update worker configs
        for hostname, (ram, cpu, rec) in results.items():
            self.config_manager.update_worker(
                hostname,
                ram_gb=ram,
                cpu_cores=cpu,
                recommended_parallel=rec,
            )

        return results

    # =========================================================================
    # WEB API MODE - Web Server Management
    # =========================================================================

    def start_spiderfoot_web(
        self,
        worker: WorkerConfig,
        port: int = 5001,
        on_progress: Optional[Callable[[str], None]] = None,
        force_restart: bool = False
    ) -> Tuple[bool, str]:
        """
        Start SpiderFoot web server on a worker.

        IMPORTANT: If the server is already running, this function returns success
        WITHOUT restarting - to avoid killing running scans.

        Args:
            worker: Worker configuration
            port: Port to listen on (default 5001)
            on_progress: Optional progress callback
            force_restart: If True, kill and restart even if already running (WILL KILL SCANS!)

        Returns:
            (success, message)
        """
        hostname = worker.hostname
        username = worker.username
        sf_dir = self.config.spiderfoot_install_dir

        # FIRST: Check if web server is already running
        # This prevents killing active scans when user clicks "Start GUI"
        if not force_restart:
            check_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/ 2>/dev/null || echo '000'"
            check_result = self.ssh.execute(hostname, username, check_cmd, timeout=10)
            if check_result.stdout.strip() == "200":
                if on_progress:
                    on_progress(f"Web server already running on {worker.get_display_name()} - using existing server")
                return True, f"Web server already running on port {port}"

        if on_progress:
            on_progress(f"Starting SpiderFoot web server on {worker.get_display_name()}...")

        # Kill any existing SpiderFoot processes first
        # WARNING: This will kill running scans!
        kill_cmd = f"""
pkill -9 -f 'sf.py.*-l' 2>/dev/null || true
pkill -9 -u {username} -f spiderfoot 2>/dev/null || true
sleep 1
"""
        self.ssh.execute(hostname, username, kill_cmd, timeout=30)

        # Start SpiderFoot web server in tmux
        # Use 0.0.0.0 to allow remote connections from puppetmaster
        start_cmd = f"""
cd {sf_dir} && \\
tmux kill-session -t sf-web 2>/dev/null || true && \\
tmux new-session -d -s sf-web "cd {sf_dir} && ./venv/bin/python3 sf.py -l 0.0.0.0:{port}" && \\
echo "STARTED"
"""
        result = self.ssh.execute(hostname, username, start_cmd, timeout=30)

        if "STARTED" not in result.stdout:
            return False, f"Failed to start web server: {result.stderr}"

        # Wait for the web server to become ready
        if on_progress:
            on_progress(f"Waiting for web server to be ready on {worker.get_display_name()}...")

        # Poll until web server responds
        for attempt in range(15):  # 15 attempts, 2 seconds apart = 30 seconds max
            time.sleep(2)
            check_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/ 2>/dev/null || echo '000'"
            check_result = self.ssh.execute(hostname, username, check_cmd, timeout=10)
            if check_result.stdout.strip() == "200":
                return True, f"Web server running on port {port}"

        return False, "Web server started but not responding after 30 seconds"

    def stop_spiderfoot_web(
        self,
        worker: WorkerConfig,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Stop SpiderFoot web server on a worker.

        Args:
            worker: Worker configuration
            on_progress: Optional progress callback

        Returns:
            (success, message)
        """
        hostname = worker.hostname
        username = worker.username

        if on_progress:
            on_progress(f"Stopping SpiderFoot web server on {worker.get_display_name()}...")

        stop_cmd = f"""
tmux kill-session -t sf-web 2>/dev/null || true
pkill -9 -f 'sf.py.*-l' 2>/dev/null || true
pkill -9 -u {username} -f spiderfoot 2>/dev/null || true
echo "STOPPED"
"""
        result = self.ssh.execute(hostname, username, stop_cmd, timeout=30)
        return True, "Web server stopped"

    def start_all_web_servers(
        self,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Tuple[bool, str]]:
        """
        Start SpiderFoot web servers on all enabled workers.

        Args:
            on_progress: Optional progress callback

        Returns:
            Dict mapping hostname to (success, message)
        """
        workers = self.config_manager.get_enabled_workers()
        results = {}

        for worker in workers:
            port = worker.gui_port  # Use the configured GUI port
            success, message = self.start_spiderfoot_web(worker, port, on_progress)
            results[worker.hostname] = (success, message)

            if on_progress:
                status = "OK" if success else f"FAILED: {message}"
                on_progress(f"  {worker.get_display_name()}: {status}")

        return results

    def stop_all_web_servers(
        self,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Tuple[bool, str]]:
        """
        Stop SpiderFoot web servers on all enabled workers.

        Args:
            on_progress: Optional progress callback

        Returns:
            Dict mapping hostname to (success, message)
        """
        workers = self.config_manager.get_enabled_workers()
        results = {}

        def stop_one(worker: WorkerConfig):
            return worker.hostname, self.stop_spiderfoot_web(worker, on_progress)

        with ThreadPoolExecutor(max_workers=min(20, len(workers))) as executor:
            futures = [executor.submit(stop_one, w) for w in workers]
            for future in as_completed(futures):
                hostname, result = future.result()
                results[hostname] = result

        return results

    def check_web_server_status(
        self,
        worker: WorkerConfig
    ) -> Tuple[bool, int]:
        """
        Check if SpiderFoot web server is running on a worker.

        Args:
            worker: Worker configuration

        Returns:
            (is_running, running_scan_count)
        """
        hostname = worker.hostname
        username = worker.username
        port = worker.gui_port

        # Check if web server is responding
        check_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/ 2>/dev/null || echo '000'"
        result = self.ssh.execute(hostname, username, check_cmd, timeout=10)

        is_running = result.stdout.strip() == "200"

        # If running, get active scan count (all non-finished statuses)
        active_scans = 0
        if is_running:
            # Query scanlist endpoint to count active scans
            # NOTE: Status is at index [6], not [5]. Index [5] is the end timestamp.
            scan_cmd = f"""curl -s http://127.0.0.1:{port}/scanlist 2>/dev/null | \\
python3 -c "import sys,json; data=json.load(sys.stdin); print(sum(1 for s in data if s[6] not in ('FINISHED','ABORTED','FAILED','ERROR-FAILED')))" 2>/dev/null || echo '0'
"""
            scan_result = self.ssh.execute(hostname, username, scan_cmd, timeout=10)
            try:
                active_scans = int(scan_result.stdout.strip())
            except ValueError:
                active_scans = 0

        return is_running, active_scans

    def start_distributed_scan(
        self,
        domains: List[str],
        intensity: str = "all",
        parallel_override: Optional[Dict[str, int]] = None,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Start a distributed scan across all enabled workers.

        For CLI mode: Workers are set up sequentially (quick, just uploads scripts).
        For WebAPI mode: Workers run their rolling queues in parallel threads.

        Args:
            domains: List of domains to scan
            intensity: Scan intensity preset ("all", "footprint", "investigate", "passive")
            parallel_override: Optional dict mapping hostname to parallel scan count
            on_progress: Optional progress callback

        Returns:
            Tuple of (success, message, details_dict)
        """
        workers = self.config_manager.get_enabled_workers()

        if not workers:
            return False, "No enabled workers configured", {}

        if not domains:
            return False, "No domains provided", {}

        # Start a new session
        session_id = self.config_manager.start_session(len(domains))

        if on_progress:
            on_progress(f"Starting session {session_id} with {len(domains)} domains across {len(workers)} workers")

        # Distribute domains
        domain_splits = DomainDistributor.split_domains(domains, len(workers))

        details = {
            'session_id': session_id,
            'workers': {},
            'total_domains': len(domains),
        }

        # Prepare worker tasks
        worker_tasks = []
        for i, worker in enumerate(workers):
            worker_domains = domain_splits[i]

            if not worker_domains:
                continue

            # Get parallel count
            # Priority: 1) explicit override, 2) global setting, 3) worker recommendation
            parallel = parallel_override.get(worker.hostname) if parallel_override else None
            if parallel is None:
                # Use global setting - it's what the user explicitly configured
                parallel = self.config.parallel_scans_per_worker

            worker_tasks.append((worker, worker_domains, parallel))

        # For WebAPI mode with rolling queue, run all workers in parallel
        # This is important because each worker's queue blocks until all domains are submitted
        if self.config.scan_mode == "webapi":
            if on_progress:
                on_progress(f"Starting rolling queues on {len(worker_tasks)} workers in parallel...")

            # Thread-safe dict to collect results
            import threading
            results_lock = threading.Lock()
            worker_results = {}

            def run_worker_queue(worker, worker_domains, parallel):
                """Run a single worker's rolling queue in a thread."""
                hostname = worker.hostname
                try:
                    # Progress callback with worker prefix (thread-safe printing)
                    def worker_progress(msg):
                        if on_progress:
                            on_progress(msg)

                    worker_progress(f"[{worker.get_display_name()}] Assigning {len(worker_domains)} domains...")

                    success, message = self._start_worker_scan_webapi(
                        worker,
                        worker_domains,
                        intensity,
                        parallel,
                        worker_progress
                    )

                    # Thread-safe result storage
                    with results_lock:
                        worker_results[hostname] = {
                            'success': success,
                            'message': message,
                            'domains_assigned': len(worker_domains),
                            'parallel': parallel,
                        }

                    # Update worker status
                    self.config_manager.update_worker(
                        hostname,
                        assigned_domains=len(worker_domains),
                        status="scanning" if success else "error",
                    )

                except Exception as e:
                    import traceback
                    error_detail = f"Exception: {str(e)} | Traceback: {traceback.format_exc()}"
                    with results_lock:
                        worker_results[hostname] = {
                            'success': False,
                            'message': error_detail,
                            'domains_assigned': len(worker_domains),
                            'parallel': parallel,
                        }
                    self.config_manager.update_worker(hostname, status="error")

            # Start all worker threads
            with ThreadPoolExecutor(max_workers=len(worker_tasks)) as executor:
                futures = [
                    executor.submit(run_worker_queue, worker, domains_list, parallel)
                    for worker, domains_list, parallel in worker_tasks
                ]

                # Wait for all to complete
                for future in as_completed(futures):
                    try:
                        future.result()  # Raises if thread threw exception
                    except Exception as e:
                        if on_progress:
                            on_progress(f"Worker thread error: {e}")

            details['workers'] = worker_results

        else:
            # CLI mode: Sequential setup (quick, just uploads scripts and starts tmux)
            for worker, worker_domains, parallel in worker_tasks:
                if on_progress:
                    on_progress(f"[{worker.get_display_name()}] Assigning {len(worker_domains)} domains...")

                success, message = self._start_worker_scan(
                    worker,
                    worker_domains,
                    intensity,
                    parallel,
                    on_progress
                )

                # Update worker status
                self.config_manager.update_worker(
                    worker.hostname,
                    assigned_domains=len(worker_domains),
                    status="scanning" if success else "error",
                )

                details['workers'][worker.hostname] = {
                    'success': success,
                    'message': message,
                    'domains_assigned': len(worker_domains),
                    'parallel': parallel,
                }

        # Check overall success
        all_success = all(w['success'] for w in details['workers'].values())

        if all_success:
            return True, f"Distributed scan started on {len(workers)} workers", details
        else:
            failed = [h for h, w in details['workers'].items() if not w['success']]
            return False, f"Some workers failed to start: {', '.join(failed)}", details

    def _start_worker_scan(
        self,
        worker: WorkerConfig,
        domains: List[str],
        intensity: str,
        parallel: int,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Start SpiderFoot scans on a single worker.

        Args:
            worker: Worker config
            domains: Domains to scan on this worker
            intensity: Scan intensity preset
            parallel: Number of parallel scans
            on_progress: Optional progress callback

        Returns:
            Tuple of (success, message)
        """
        hostname = worker.hostname
        username = worker.username
        work_dir = self.config.remote_work_dir.replace("~", f"/home/{username}")
        sf_dir = self.config.spiderfoot_install_dir.replace("~", f"/home/{username}")

        # 1. Create domains file locally (with validation)
        # Validate domains to prevent command injection
        valid_domain_pattern = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]*[a-zA-Z0-9]$')
        validated_domains = []
        for domain in domains:
            domain = domain.strip()
            if domain and valid_domain_pattern.match(domain) and len(domain) <= 253:
                validated_domains.append(domain)

        if not validated_domains:
            return False, "No valid domains after validation"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for domain in validated_domains:
                f.write(domain + '\n')
            local_domains_file = f.name

        try:
            # 2. Upload domains file to worker
            if on_progress:
                on_progress(f"[{worker.get_display_name()}] Uploading domain list...")

            remote_domains_file = f"{work_dir}/domains/domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

            success, msg = self.ssh.upload_file(
                hostname, username,
                local_domains_file,
                remote_domains_file
            )

            if not success:
                return False, f"Failed to upload domains: {msg}"

            # 3. Create scan script on worker
            if on_progress:
                on_progress(f"[{worker.get_display_name()}] Creating scan script...")

            # Modules parameter
            modules_param = ""
            if intensity in INTENSITY_PRESETS and INTENSITY_PRESETS[intensity]:
                modules_param = f"-m {INTENSITY_PRESETS[intensity]}"

            # Timeout in seconds
            timeout_seconds = int(self.config.hard_timeout_hours * 3600)

            # Create the scan script
            scan_script = f'''#!/bin/bash
# SpiderFoot distributed scan script
# Generated by PUPPETMASTER

# NOTE: We intentionally do NOT use set -e since we handle errors explicitly
# and use background jobs which have their own error handling
set -u  # Exit on undefined variable

# Trap unexpected exits to help diagnose script failures
_exit_trap() {{
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] FATAL: Script exited unexpectedly with code $exit_code" >> "$LOG_FILE" 2>/dev/null || true
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] FATAL: Last command may have triggered set -u (undefined variable)" >> "$LOG_FILE" 2>/dev/null || true
    fi
}}
trap '_exit_trap' EXIT

DOMAINS_FILE="{remote_domains_file}"
OUTPUT_DIR="{work_dir}/output"
SF_DIR="{sf_dir}"
LOG_DIR="{work_dir}/logs"
PARALLEL={parallel}
TIMEOUT={timeout_seconds}
LOG_FILE="$LOG_DIR/scan_$(date +%Y%m%d_%H%M%S).log"

# Create directories
mkdir -p "$LOG_DIR" "$OUTPUT_DIR"

log() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}}

# Safe logging for background jobs - uses flock to prevent interleaved writes
log_safe() {{
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    (
        flock -w 5 200 || true
        echo "$msg" >> "$LOG_FILE"
    ) 200>"$LOG_FILE.lock"
}}

log "=========================================="
log "PUPPETMASTER DISTRIBUTED SCAN STARTING"
log "=========================================="
log "SpiderFoot dir: $SF_DIR"
log "Output dir: $OUTPUT_DIR"
log "Domains file: $DOMAINS_FILE"
log "Parallel scans: $PARALLEL"
log "Timeout per domain: $TIMEOUT seconds"

# Verify SpiderFoot directory exists
if [ ! -d "$SF_DIR" ]; then
    log "FATAL: SpiderFoot directory not found: $SF_DIR"
    exit 1
fi

# Change to SpiderFoot directory
cd "$SF_DIR" || {{
    log "FATAL: Failed to cd to $SF_DIR"
    exit 1
}}

# Verify venv exists
if [ ! -f venv/bin/python3 ]; then
    log "FATAL: Virtual environment python not found at $SF_DIR/venv/bin/python3"
    exit 1
fi

# Verify sf.py exists
if [ ! -f sf.py ]; then
    log "FATAL: sf.py not found in $SF_DIR"
    exit 1
fi

# Test that Python and SpiderFoot work
log "Testing SpiderFoot installation..."
PYTHON_VERSION=$("$SF_DIR/venv/bin/python3" --version 2>&1)
log "Python version: $PYTHON_VERSION"

SF_TEST=$("$SF_DIR/venv/bin/python3" sf.py --help 2>&1 | head -3)
if [ $? -ne 0 ]; then
    log "FATAL: SpiderFoot test failed. Output: $SF_TEST"
    exit 1
fi
log "SpiderFoot test passed"

# Initialize the SpiderFoot database BEFORE starting parallel scans
# This prevents race conditions when multiple scans try to create the schema simultaneously
log "Initializing SpiderFoot database..."
DB_INIT=$("$SF_DIR/venv/bin/python3" << PYEOF
import sys
import os
sys.path.insert(0, '$SF_DIR')
from spiderfoot.db import SpiderFootDb

# SpiderFoot default database location
db_path = os.path.expanduser('~/.spiderfoot/spiderfoot.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)

opts = dict()
opts['__database'] = db_path
try:
    db = SpiderFootDb(opts)
    print('Database initialized successfully at ' + db_path)
except Exception as e:
    print('Database init error: ' + str(e))
    sys.exit(1)
PYEOF
)
if [ $? -ne 0 ]; then
    log "FATAL: Database initialization failed: $DB_INIT"
    exit 1
fi
log "$DB_INIT"

# Verify domains file exists and is not empty
if [ ! -f "$DOMAINS_FILE" ]; then
    log "FATAL: Domains file not found: $DOMAINS_FILE"
    exit 1
fi

domain_count=$(wc -l < "$DOMAINS_FILE" | tr -d ' ')
if [ "$domain_count" -eq 0 ]; then
    log "FATAL: Domains file is empty"
    exit 1
fi
log "Processing $domain_count domains"

# Process each domain
processed=0
skipped=0
started=0

while IFS= read -r domain || [ -n "$domain" ]; do
    # Skip empty lines
    [ -z "$domain" ] && continue

    # Create safe filename from domain
    safe_domain=$(echo "$domain" | tr '.' '_' | tr -cd 'a-zA-Z0-9_-')

    # Skip if already scanned (CSV exists)
    if ls "$OUTPUT_DIR"/${{safe_domain}}_*.csv 1>/dev/null 2>&1; then
        log "[SKIP] $domain - already scanned"
        ((skipped++)) || true
        continue
    fi

    timestamp=$(date +%Y%m%d_%H%M%S%N)
    output_file="${{OUTPUT_DIR}}/${{safe_domain}}_${{timestamp}}.csv"
    temp_file="${{OUTPUT_DIR}}/.tmp_${{safe_domain}}_${{timestamp}}.csv"
    error_file="${{OUTPUT_DIR}}/.err_${{safe_domain}}_${{timestamp}}.log"

    log "[START] $domain (parallel slot $((started % PARALLEL + 1))/$PARALLEL)"
    ((started++)) || true

    # Run SpiderFoot in subshell with timeout
    # Using full path to venv python since subshells don't inherit activated venv
    (
        if timeout $TIMEOUT "$SF_DIR/venv/bin/python3" "$SF_DIR/sf.py" -s "$domain" -o csv{' ' + modules_param if modules_param else ''} > "$temp_file" 2> "$error_file"; then
            # Success - move temp to final output
            if [ -s "$temp_file" ]; then
                mv "$temp_file" "$output_file"
                rm -f "$error_file"
                log_safe "[DONE] $domain -> $output_file"
            else
                # Empty output is also a failure
                log_safe "[FAIL] $domain - empty output"
                rm -f "$temp_file"
                [ -s "$error_file" ] && mv "$error_file" "${{OUTPUT_DIR}}/error_${{safe_domain}}.log"
            fi
        else
            exit_code=$?
            # Save error for debugging
            if [ -f "$error_file" ] && [ -s "$error_file" ]; then
                error_msg=$(head -5 "$error_file" | tr '\\n' ' ')
                log_safe "[FAIL] $domain (exit $exit_code) - $error_msg"
                mv "$error_file" "${{OUTPUT_DIR}}/error_${{safe_domain}}.log"
            else
                if [ $exit_code -eq 124 ]; then
                    log_safe "[TIMEOUT] $domain (exceeded $TIMEOUT seconds)"
                else
                    log_safe "[FAIL] $domain (exit $exit_code, no error output)"
                fi
                rm -f "$error_file"
            fi
            rm -f "$temp_file"
        fi
    ) &

    # Limit parallelism - wait if we have too many running jobs
    while [ $(jobs -rp | wc -l) -ge $PARALLEL ]; do
        sleep 5
    done

    ((processed++)) || true
done < "$DOMAINS_FILE"

log "Finished queuing $processed domains (skipped: $skipped, started: $started)"
log "Waiting for all background scans to complete..."
wait

# Count results
csv_count=$(ls -1 "$OUTPUT_DIR"/*.csv 2>/dev/null | wc -l || echo 0)
error_count=$(ls -1 "$OUTPUT_DIR"/error_*.log 2>/dev/null | wc -l || echo 0)

log "=========================================="
log "SCAN COMPLETE"
log "Successful: $csv_count CSVs generated"
log "Failed: $error_count domains with errors"
log "=========================================="

# Clear the exit trap on successful completion
trap - EXIT
'''

            # Upload scan script
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                f.write(scan_script)
                local_script = f.name

            remote_script = f"{work_dir}/run_scans.sh"
            success, msg = self.ssh.upload_file(hostname, username, local_script, remote_script)
            os.unlink(local_script)

            if not success:
                return False, f"Failed to upload scan script: {msg}"

            # Make script executable
            self.ssh.execute(hostname, username, f"chmod +x {shlex.quote(remote_script)}")

            # 4. Start scans in tmux session
            if on_progress:
                on_progress(f"[{worker.get_display_name()}] Starting scans in tmux...")

            # Kill any existing SpiderFoot processes and tmux session
            # Use multiple approaches for reliability (pkill, killall, kill with pgrep)
            kill_cmd = f"""
tmux kill-session -t sf-scans 2>/dev/null || true
tmux kill-server 2>/dev/null || true
pkill -9 -f run_scans.sh 2>/dev/null || true
pkill -9 -f timeout 2>/dev/null || true
killall -9 timeout 2>/dev/null || true
pkill -9 -u {username} python3 2>/dev/null || true
pkill -9 -u {username} python 2>/dev/null || true
killall -9 -u {username} python3 2>/dev/null || true
pkill -9 -f sf.py 2>/dev/null || true
kill -9 $(pgrep -u {username} python3) 2>/dev/null || true
true
"""
            self.ssh.execute(hostname, username, kill_cmd, timeout=30)

            # Brief pause to ensure processes are dead before starting new ones
            time.sleep(2)

            # Clean ALL old output files from previous scans (CSVs, error logs, temp files)
            # Remove entire dir and recreate to avoid zsh glob errors on empty dirs
            self.ssh.execute(hostname, username, f"rm -rf {shlex.quote(work_dir)}/output && mkdir -p {shlex.quote(work_dir)}/output")

            # Start new tmux session with scan script
            start_cmd = f"tmux new-session -d -s sf-scans 'bash {shlex.quote(remote_script)}'"

            result = self.ssh.execute(hostname, username, start_cmd, timeout=60)

            if not result.success:
                return False, f"Failed to start tmux session: {result.stderr}"

            # Verify tmux session is running
            verify_result = self.ssh.execute(hostname, username, "tmux has-session -t sf-scans 2>/dev/null && echo 'RUNNING'")

            if "RUNNING" in verify_result.stdout:
                return True, f"Scans started ({len(domains)} domains, {parallel} parallel)"
            else:
                return False, "tmux session failed to start"

        finally:
            # Cleanup local temp file
            if os.path.exists(local_domains_file):
                os.unlink(local_domains_file)

    def _get_running_scan_count(self, worker: WorkerConfig, max_concurrent: int = 5) -> int:
        """
        Get the number of currently running scans on a worker's web server.

        IMPORTANT: On error, returns max_concurrent (not 0) to prevent runaway submissions.
        This is a safety measure - if we can't verify the count, assume the queue is full.

        Args:
            worker: Worker configuration
            max_concurrent: The concurrency limit - returned on error as a safe default

        Returns:
            Number of scans in active status, or max_concurrent on error
        """
        hostname = worker.hostname
        username = worker.username
        port = worker.gui_port

        # Query scanlist to count active scans
        # CRITICAL: Must verify curl succeeded before counting, otherwise we get "0" on timeout
        # which would cause us to flood the worker with scans
        # Step 1: Get the scanlist JSON
        # Step 2: Only if we got valid data, count active statuses
        count_cmd = f'data=$(curl -s --max-time 10 http://127.0.0.1:{port}/scanlist 2>/dev/null) && echo "$data" | grep -q "\\[" && echo "$data" | grep -oE \'"RUNNING"|"STARTING"|"STARTED"\' | wc -l || echo "ERROR"'
        result = self.ssh.execute(hostname, username, count_cmd, timeout=20)

        if not result.success:
            # SSH failed - assume queue is full to prevent runaway submissions
            return max_concurrent

        stdout = result.stdout.strip()
        if not stdout or stdout == "ERROR":
            # curl failed or didn't get valid JSON - assume queue is full for safety
            return max_concurrent

        try:
            count = int(stdout)
            return count
        except ValueError:
            # Parse failed - assume queue is full for safety
            return max_concurrent

    def _submit_single_scan(
        self,
        worker: WorkerConfig,
        domain: str,
        usecase: str,
        port: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Submit a single scan to a worker's web server.

        Args:
            worker: Worker configuration
            domain: Domain to scan
            usecase: SpiderFoot usecase preset
            port: Web server port

        Returns:
            Tuple of (success, scan_id or None)
        """
        hostname = worker.hostname
        scan_name = f"pm_{domain}_{datetime.now().strftime('%H%M%S')}"

        # All 5 parameters are required by SpiderFoot: scanname, scantarget, modulelist, typelist, usecase
        # Single-line curl command to avoid SSH escaping issues
        # IMPORTANT: Do NOT use -L (follow redirects). SpiderFoot's /startscan creates the scan
        # then returns a 302 redirect to the scan status page. If we follow the redirect, we get
        # HTML back and can't detect the scan ID, but the scan was already created — causing the
        # parallelism limit to be bypassed (submissions counted as failures but scans actually run).
        # Instead, use -w to capture HTTP status code and check for 302 (redirect = success).
        form_data = f"scanname={scan_name}&scantarget={domain}&modulelist=&typelist=&usecase={usecase}"
        curl_cmd = f'curl -s -m 20 -o /dev/null -w "%{{http_code}}" -X POST "http://127.0.0.1:{port}/startscan" -d "{form_data}" 2>&1'
        result = self.ssh.execute(hostname, worker.username, curl_cmd, timeout=30)

        # Check SSH execution first
        if not result.success:
            # SSH itself failed - store error for debugging
            self._last_submit_error = f"SSH failed for {worker.get_display_name()}: {result.stderr.strip() or 'connection error'}"
            return False, None

        stdout = result.stdout.strip()
        if not stdout:
            self._last_submit_error = f"Empty response from {worker.get_display_name()} - web server may not be running"
            return False, None

        # With -o /dev/null -w "%{http_code}", stdout is just the HTTP status code
        # SpiderFoot returns 302 (redirect to scaninfo page) on success
        # 200 with JSON body is also possible in some versions
        http_code = stdout.strip()

        if http_code in ('302', '303'):
            # Redirect = scan was created and SpiderFoot is redirecting to status page
            self._last_submit_error = None
            return True, scan_name  # Use scan_name as ID since we can't get the real ID from redirect

        if http_code == '200':
            # Some SpiderFoot versions return 200 with JSON body
            # We suppressed the body with -o /dev/null, so just assume success
            self._last_submit_error = None
            return True, scan_name

        if http_code == '000':
            # curl couldn't connect
            self._last_submit_error = f"Cannot connect to web server on {worker.get_display_name()} (port {port})"
            return False, None

        # Any other status code (4xx, 5xx) is an error
        self._last_submit_error = f"HTTP {http_code} from {worker.get_display_name()} - scan submission failed"
        return False, None

    def _start_worker_scan_webapi(
        self,
        worker: WorkerConfig,
        domains: List[str],
        intensity: str,
        parallel: int,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Start SpiderFoot scans on a worker using the Web API with rolling queue.

        This method implements a rolling queue that respects the parallelism limit:
        1. Submit up to N scans initially (where N = parallel limit)
        2. Poll the web server to check how many scans are RUNNING
        3. When running count drops below N, submit more scans
        4. Continue until all domains are submitted

        The master machine must remain running to manage this queue.

        Args:
            worker: Worker config
            domains: Domains to scan on this worker
            intensity: Scan intensity preset
            parallel: Max concurrent scans to maintain
            on_progress: Optional progress callback

        Returns:
            Tuple of (success, message)
        """
        try:
            from .spiderfoot_api import SpiderFootAPI, SpiderFootAPIError
        except ImportError as e:
            return False, f"SpiderFootAPI not available: {e}"

        hostname = worker.hostname
        port = worker.gui_port
        work_dir = self.config.remote_work_dir.replace("~", f"/home/{worker.username}")

        # Validate domains
        valid_domain_pattern = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]*[a-zA-Z0-9]$')
        validated_domains = []
        for domain in domains:
            domain = domain.strip()
            if domain and valid_domain_pattern.match(domain) and len(domain) <= 253:
                validated_domains.append(domain)

        if not validated_domains:
            return False, "No valid domains after validation"

        # Ensure web server is running
        if on_progress:
            on_progress(f"[{worker.get_display_name()}] Checking web server...")

        is_running, _ = self.check_web_server_status(worker)
        if not is_running:
            if on_progress:
                on_progress(f"[{worker.get_display_name()}] Starting web server...")
            success, msg = self.start_spiderfoot_web(worker, port, on_progress)
            if not success:
                return False, f"Failed to start web server: {msg}"

        # Create output directory on worker
        self.ssh.execute(
            hostname, worker.username,
            f"mkdir -p {shlex.quote(work_dir)}/output {shlex.quote(work_dir)}/logs"
        )

        # Determine usecase from intensity
        # SpiderFoot checks: usecase == 'all' OR usecase in module['group']
        # 'all' must be lowercase (special case), others must be capitalized to match module groups
        usecase_map = {
            'all': 'all',  # lowercase - special case in SpiderFoot
            'footprint': 'Footprint',
            'investigate': 'Investigate',
            'passive': 'Passive',
        }
        usecase = usecase_map.get(intensity.lower(), 'all')

        # Rolling queue implementation
        submitted = 0
        failed = 0
        scan_ids = []
        domain_queue = list(validated_domains)  # Copy to track remaining
        poll_interval = 30  # Seconds between checking running scan count (increased for stability)

        # HARD RATE LIMIT: Never submit more than parallel scans per poll cycle
        # This is a failsafe in case status checks fail
        max_submissions_per_cycle = parallel

        if on_progress:
            on_progress(f"[{worker.get_display_name()}] Starting rolling queue: {len(domain_queue)} domains, max {parallel} concurrent...")

        # Initial submission: fill up to parallel limit
        # Wait longer between initial submissions to let SpiderFoot initialize
        consecutive_failures = 0
        while domain_queue and submitted < parallel:
            domain = domain_queue.pop(0)
            success, scan_id = self._submit_single_scan(worker, domain, usecase, port)

            if success:
                submitted += 1
                consecutive_failures = 0
                if scan_id:
                    scan_ids.append(scan_id)
            else:
                failed += 1
                consecutive_failures += 1
                # Show error on first failure or every 5 failures
                if on_progress and (consecutive_failures == 1 or consecutive_failures % 5 == 0):
                    error_msg = getattr(self, '_last_submit_error', 'Unknown error')
                    on_progress(f"[{worker.get_display_name()}] Scan submission failed: {error_msg}")
                # If we have many consecutive failures, abort early
                if consecutive_failures >= 5:
                    if on_progress:
                        on_progress(f"[{worker.get_display_name()}] Too many consecutive failures, aborting...")
                    break

            # Longer delay for initial batch to let SpiderFoot initialize each scan
            time.sleep(2)

        if on_progress:
            on_progress(f"[{worker.get_display_name()}] Initial batch: {submitted} scans started, {len(domain_queue)} remaining in queue...")

        # Wait for initial batch to fully initialize before polling
        time.sleep(10)

        # Rolling queue loop: poll and submit more as slots become available
        last_progress_update = time.time()
        last_submission_time = time.time()
        last_agent_check = time.time()
        agent_check_interval = 300  # Check agent health every 5 minutes

        while domain_queue:
            # CRITICAL: Always wait at least poll_interval between submission cycles
            # This is our primary defense against flooding
            time_since_last = time.time() - last_submission_time
            if time_since_last < poll_interval:
                time.sleep(poll_interval - time_since_last)

            # Proactively check and fix SSH agent periodically
            # This ensures we don't get stuck if the agent socket becomes stale
            if self.config.use_ssh_agent and (time.time() - last_agent_check > agent_check_interval):
                fix_ssh_auth_sock()  # Refresh agent socket if needed
                last_agent_check = time.time()

            # Check how many scans are currently running
            # Pass parallel as max_concurrent - on error, assumes queue is full (safe default)
            running_count = self._get_running_scan_count(worker, max_concurrent=parallel)

            # Calculate available slots
            available_slots = max(0, parallel - running_count)

            # HARD RATE LIMIT: Never submit more than max_submissions_per_cycle per poll
            # Even if running_count returns 0 (error), we won't flood
            to_submit = min(available_slots, len(domain_queue), max_submissions_per_cycle)

            if to_submit > 0 and running_count < parallel:
                # Only submit if we genuinely have slots AND running count is below limit
                cycle_failures = 0
                for _ in range(to_submit):
                    if not domain_queue:
                        break

                    domain = domain_queue.pop(0)
                    success, scan_id = self._submit_single_scan(worker, domain, usecase, port)

                    if success:
                        submitted += 1
                        cycle_failures = 0
                        if scan_id:
                            scan_ids.append(scan_id)
                    else:
                        failed += 1
                        cycle_failures += 1
                        if on_progress and cycle_failures == 1:
                            error_msg = getattr(self, '_last_submit_error', 'Unknown error')
                            on_progress(f"[{worker.get_display_name()}] Submission error: {error_msg}")

                    # Delay between submissions
                    time.sleep(1)

                last_submission_time = time.time()

            # Progress update
            now = time.time()
            if on_progress and (now - last_progress_update >= 30 or not domain_queue):
                on_progress(f"[{worker.get_display_name()}] Progress: {submitted}/{len(validated_domains)} submitted, "
                           f"{running_count} active, {len(domain_queue)} queued...")
                last_progress_update = now
            # Note: poll_interval wait is at the start of the loop

        # Save scan IDs to a file on the worker for tracking
        if scan_ids:
            scan_ids_content = '\n'.join(scan_ids)
            save_cmd = f"echo '{scan_ids_content}' > {shlex.quote(work_dir)}/scan_ids.txt"
            self.ssh.execute(hostname, worker.username, save_cmd)

        if on_progress:
            on_progress(f"[{worker.get_display_name()}] All {submitted} scans submitted ({failed} failed). Queue complete.")

        if submitted > 0:
            return True, f"Submitted {submitted}/{len(validated_domains)} scans via rolling queue ({failed} failed)"
        else:
            return False, f"All {failed} scan submissions failed"

    def get_all_progress(
        self,
        on_progress: Optional[Callable[[str, str], None]] = None
    ) -> Dict[str, WorkerProgress]:
        """
        Get progress from all workers.

        Args:
            on_progress: Optional callback(hostname, status)

        Returns:
            Dict mapping hostname to WorkerProgress
        """
        workers = self.config_manager.get_enabled_workers()
        results = {}

        def check_one(worker: WorkerConfig):
            if on_progress:
                on_progress(worker.hostname, "checking...")

            progress = self._get_worker_progress(worker)

            # Update worker config
            self.config_manager.update_worker(
                worker.hostname,
                completed_domains=progress.domains_completed,
                failed_domains=progress.domains_failed,
                status=progress.status,
            )

            if on_progress:
                on_progress(worker.hostname, f"{progress.domains_completed}/{progress.domains_total}")

            return worker.hostname, progress

        if not workers:
            return results

        with ThreadPoolExecutor(max_workers=min(20, len(workers))) as executor:
            futures = {executor.submit(check_one, w): w for w in workers}

            for future in as_completed(futures):
                worker = futures[future]
                try:
                    hostname, progress = future.result()
                    results[hostname] = progress
                except Exception as e:
                    # Create error progress entry instead of silently ignoring
                    results[worker.hostname] = WorkerProgress(
                        hostname=worker.hostname,
                        nickname=worker.nickname or worker.hostname,
                        status="unreachable",
                        domains_total=worker.assigned_domains,
                        domains_completed=0,
                        domains_failed=0,
                        running_processes=0,
                        csv_files_count=0,
                        last_updated=datetime.now().isoformat(),
                        error_message=str(e),
                    )

        return results

    def _get_worker_progress(self, worker: WorkerConfig) -> WorkerProgress:
        """
        Get progress from a single worker.

        Args:
            worker: Worker config

        Returns:
            WorkerProgress object
        """
        # Use appropriate progress method based on scan mode
        if self.config.scan_mode == "webapi":
            return self._get_worker_progress_webapi(worker)
        else:
            return self._get_worker_progress_cli(worker)

    def _get_worker_progress_webapi(self, worker: WorkerConfig) -> WorkerProgress:
        """
        Get progress from a worker running in WebAPI mode.

        Queries the SpiderFoot web server to get scan status.
        """
        hostname = worker.hostname
        username = worker.username
        port = worker.gui_port

        progress = WorkerProgress(
            hostname=hostname,
            nickname=worker.nickname or hostname,
            status="unknown",
            domains_total=worker.assigned_domains,
            domains_completed=0,
            domains_failed=0,
            running_processes=0,
            csv_files_count=0,
            last_updated=datetime.now().isoformat(),
        )

        # Check if web server is running
        is_running, running_scans = self.check_web_server_status(worker)

        if not is_running:
            progress.status = "idle"
            return progress

        # Query scanlist to get scan counts by status
        # Count ALL active statuses, not just "RUNNING"
        scan_cmd = f"""
curl -s http://127.0.0.1:{port}/scanlist 2>/dev/null | \\
python3 -c "
import sys,json
try:
    data=json.load(sys.stdin)
    # Count by status category
    # NOTE: Status is at index [6], not [5]. Index [5] is the end timestamp.
    finished_statuses = ('FINISHED',)
    failed_statuses = ('ABORTED', 'FAILED', 'ERROR-FAILED')
    # Active = anything not finished or failed
    active = sum(1 for s in data if s[6] not in finished_statuses + failed_statuses)
    finished = sum(1 for s in data if s[6] in finished_statuses)
    failed = sum(1 for s in data if s[6] in failed_statuses)
    total = len(data)
    print(f'{{active}} {{finished}} {{failed}} {{total}}')
except:
    print('0 0 0 0')
"
"""
        result = self.ssh.execute(hostname, username, scan_cmd, timeout=15)

        try:
            parts = result.stdout.strip().split()
            if len(parts) >= 4:
                active = int(parts[0])
                finished = int(parts[1])
                failed = int(parts[2])
                total = int(parts[3])

                progress.running_processes = active
                progress.domains_completed = finished
                progress.domains_failed = failed
                progress.domains_total = total  # Use actual total from SpiderFoot
                progress.csv_files_count = finished  # Each finished scan = 1 result

                # Determine status
                if active > 0:
                    progress.status = "scanning"
                elif total > 0:
                    progress.status = "completed"
                else:
                    progress.status = "idle"
        except (ValueError, IndexError):
            progress.status = "error"
            progress.error_message = "Failed to parse scan status"

        return progress

    def _get_worker_progress_cli(self, worker: WorkerConfig) -> WorkerProgress:
        """
        Get progress from a worker running in CLI mode (bash script).

        Checks tmux session, log files, and CSV outputs.
        """
        hostname = worker.hostname
        username = worker.username
        work_dir = self.config.remote_work_dir.replace("~", f"/home/{username}")

        progress = WorkerProgress(
            hostname=hostname,
            nickname=worker.nickname or hostname,
            status="unknown",
            domains_total=worker.assigned_domains,
            domains_completed=0,
            domains_failed=0,
            running_processes=0,
            csv_files_count=0,
            last_updated=datetime.now().isoformat(),
        )

        # Check if tmux session exists
        tmux_result = self.ssh.execute(
            hostname, username,
            "tmux has-session -t sf-scans 2>/dev/null && echo 'RUNNING' || echo 'STOPPED'"
        )

        session_running = "RUNNING" in tmux_result.stdout

        # Count CSV files
        csv_result = self.ssh.execute(
            hostname, username,
            f"ls -1 {shlex.quote(work_dir)}/output/*.csv 2>/dev/null | wc -l"
        )

        try:
            progress.csv_files_count = int(csv_result.stdout.strip())
        except ValueError:
            pass

        # Count failed domains from log (grep for [FAIL] and [TIMEOUT] entries)
        # Use -h to suppress filenames when multiple files match, then sum the counts
        fail_result = self.ssh.execute(
            hostname, username,
            f"grep -ch '\\[FAIL\\]\\|\\[TIMEOUT\\]' {shlex.quote(work_dir)}/logs/scan_*.log 2>/dev/null | awk '{{sum+=$1}} END {{print sum+0}}'"
        )

        try:
            progress.domains_failed = int(fail_result.stdout.strip())
        except ValueError:
            progress.domains_failed = 0

        # Check if scan completed by looking for "SCAN COMPLETE" in log
        # Use -l to just check if pattern exists in any file
        complete_result = self.ssh.execute(
            hostname, username,
            f"grep -l 'SCAN COMPLETE' {shlex.quote(work_dir)}/logs/scan_*.log 2>/dev/null | wc -l"
        )

        try:
            scan_completed = int(complete_result.stdout.strip()) > 0
        except ValueError:
            scan_completed = False

        # Total processed = successful CSVs + failed domains
        progress.domains_completed = progress.csv_files_count + progress.domains_failed

        # Count running SpiderFoot processes
        # Use more specific pattern to match only Python processes running sf.py with -s flag (scans)
        # Exclude timeout wrappers (which also contain the full command in their args)
        # and exclude the GUI process which runs without -s
        proc_result = self.ssh.execute(
            hostname, username,
            "pgrep -af 'python.*sf\\.py.*-s' 2>/dev/null | grep -v '^[0-9]* timeout' | wc -l || echo '0'"
        )

        try:
            progress.running_processes = int(proc_result.stdout.strip())
        except (ValueError, AttributeError):
            progress.running_processes = 0

        # Determine status
        if not tmux_result.success:
            progress.status = "unreachable"
            progress.error_message = "Could not connect to worker"
        elif scan_completed:
            # Scan script logged "SCAN COMPLETE" - definitively done
            progress.status = "completed"
        elif progress.running_processes > 0:
            # Active scan processes running
            progress.status = "scanning"
        elif session_running and progress.csv_files_count == 0 and progress.domains_failed == 0:
            # Session running but no results yet - starting up
            progress.status = "starting"
        elif session_running:
            # Session running with some results - actively scanning
            progress.status = "scanning"
        elif progress.csv_files_count > 0 or progress.domains_failed > 0:
            # No session, no processes, but we have results - stopped prematurely
            progress.status = "stopped"
        else:
            progress.status = "idle"

        return progress

    def collect_results(
        self,
        output_dir: str,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Tuple[bool, str, int]]:
        """
        Collect results from all workers.

        Args:
            output_dir: Local directory to save results
            on_progress: Optional progress callback

        Returns:
            Dict mapping hostname to (success, message, file_count)
        """
        workers = self.config_manager.get_enabled_workers()
        results = {}

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        for worker in workers:
            hostname = worker.hostname
            username = worker.username
            work_dir = self.config.remote_work_dir.replace("~", f"/home/{username}")

            if on_progress:
                on_progress(f"Collecting from {worker.get_display_name()}...")

            # Create worker-specific subdirectory
            worker_dir = os.path.join(output_dir, worker.nickname or hostname.replace('.', '_'))
            os.makedirs(worker_dir, exist_ok=True)

            # Use appropriate collection method based on scan mode
            if self.config.scan_mode == "webapi":
                success, message, count = self._collect_results_webapi(
                    worker, worker_dir, on_progress
                )
            else:
                # CLI mode: Download CSV files from output directory
                success, message, count = self.ssh.download_directory(
                    hostname, username,
                    f"{work_dir}/output",
                    worker_dir,
                    "*.csv"
                )

            results[hostname] = (success, message, count)

            if on_progress:
                on_progress(f"  Downloaded {count} files")

        return results

    def _collect_results_webapi(
        self,
        worker: 'WorkerConfig',
        output_dir: str,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str, int]:
        """
        Collect results from a worker running in WebAPI mode.

        Exports finished scans via SpiderFoot's API and downloads the CSVs.

        Args:
            worker: Worker configuration
            output_dir: Local directory to save results
            on_progress: Optional progress callback

        Returns:
            Tuple of (success, message, file_count)
        """
        hostname = worker.hostname
        username = worker.username
        port = worker.gui_port
        work_dir = self.config.remote_work_dir.replace("~", f"/home/{username}")
        export_dir = f"{work_dir}/exports"

        try:
            # Create export directory on worker
            self.ssh.execute(hostname, username, f"mkdir -p {shlex.quote(export_dir)}")

            # Get list of finished scans and export each to CSV
            # This script runs on the worker and exports all FINISHED scans
            export_script = f'''
import json
import urllib.request
import os

export_dir = "{export_dir}"
port = {port}

try:
    # Get scan list
    with urllib.request.urlopen(f"http://127.0.0.1:{{port}}/scanlist", timeout=30) as resp:
        scans = json.load(resp)

    exported = 0
    for scan in scans:
        scan_id = scan[0]
        target = scan[2]
        status = scan[6] if len(scan) > 6 else "UNKNOWN"

        if status == "FINISHED":
            # Create safe filename from target
            safe_name = target.replace(".", "_").replace("/", "_").replace(":", "_")
            csv_path = os.path.join(export_dir, f"{{safe_name}}_{{scan_id[:8]}}.csv")

            # Skip if already exported
            if os.path.exists(csv_path):
                exported += 1
                continue

            # Export CSV via API
            try:
                export_url = f"http://127.0.0.1:{{port}}/scaneventresultexport?id={{scan_id}}&filetype=csv"
                with urllib.request.urlopen(export_url, timeout=60) as resp:
                    csv_data = resp.read()

                with open(csv_path, "wb") as f:
                    f.write(csv_data)
                exported += 1
            except Exception as e:
                print(f"Failed to export {{target}}: {{e}}", file=__import__("sys").stderr)

    print(exported)
except Exception as e:
    print(f"ERROR: {{e}}", file=__import__("sys").stderr)
    print(0)
'''

            # Run export script on worker
            result = self.ssh.execute(
                hostname, username,
                f'python3 -c {shlex.quote(export_script)}',
                timeout=300  # 5 min timeout for large exports
            )

            # Parse export count
            try:
                export_count = int(result.stdout.strip().split()[-1])
            except (ValueError, IndexError):
                export_count = 0

            if on_progress and export_count > 0:
                on_progress(f"  Exported {export_count} scans via API")

            # Download the exported CSVs
            success, message, download_count = self.ssh.download_directory(
                hostname, username,
                export_dir,
                output_dir,
                "*.csv"
            )

            # Clean up export directory on worker
            self.ssh.execute(hostname, username, f"rm -rf {shlex.quote(export_dir)}")

            return success, message, download_count

        except Exception as e:
            return False, f"WebAPI collection failed: {e}", 0

    def abort_worker_scans(
        self,
        hostname: str,
        save_aborted: bool = True,
        clean_output: bool = False
    ) -> Tuple[bool, str, List[str]]:
        """
        Stop all scans on a worker and restart the GUI.

        Kills all scan processes, then restarts the SpiderFoot GUI (in webapi mode)
        so that completed scan results remain accessible via the web interface.
        Results are stored in ~/.spiderfoot/spiderfoot.db and persist after the kill.

        Args:
            hostname: Worker hostname
            save_aborted: Whether to save aborted domains to the list
            clean_output: Whether to also clean the output directory

        Returns:
            Tuple of (success, message, aborted_domains)
        """
        worker = self.config_manager.get_worker(hostname)
        if not worker:
            return False, f"Worker not found: {hostname}", []

        username = worker.username
        work_dir = self.config.remote_work_dir.replace("~", f"/home/{username}")

        # Get list of domains that were being scanned (not yet completed)
        aborted_domains = []

        # For WebAPI mode, try to stop scans gracefully first
        if self.config.scan_mode == "webapi":
            port = worker.gui_port
            # Stop all running scans via API
            # NOTE: Status is at index [6], not [5]. Index [5] is the end timestamp.
            stop_cmd = f"""
curl -s http://127.0.0.1:{port}/scanlist 2>/dev/null | \\
python3 -c "import sys,json
try:
    data=json.load(sys.stdin)
    for s in data:
        if s[6]=='RUNNING':
            import urllib.request
            urllib.request.urlopen(f'http://127.0.0.1:{port}/stopscan?id={{s[0]}}')
except: pass" 2>/dev/null || true
"""
            self.ssh.execute(hostname, username, stop_cmd, timeout=30)
            time.sleep(2)

            # Stop the web server
            self.stop_spiderfoot_web(worker)
            time.sleep(1)

        # Kill SpiderFoot processes (use -9 for force kill)
        # Must kill ALL python3 processes because SpiderFoot spawns multiprocessing workers
        # that don't have sf.py or spiderfoot in their command line
        # Also kill bash scan scripts and timeout wrappers which can become orphaned
        # Use multiple approaches for reliability (pkill, killall, kill with pgrep)
        kill_cmd = f"""
tmux kill-server 2>/dev/null || true
pkill -9 -f run_scans.sh 2>/dev/null || true
pkill -9 -f timeout 2>/dev/null || true
killall -9 timeout 2>/dev/null || true
pkill -9 -u {username} python3 2>/dev/null || true
pkill -9 -u {username} python 2>/dev/null || true
killall -9 -u {username} python3 2>/dev/null || true
pkill -9 -f sf.py 2>/dev/null || true
pkill -9 -f spiderfoot 2>/dev/null || true
kill -9 $(pgrep -u {username} python3) 2>/dev/null || true
kill -9 $(pgrep -f sf.py) 2>/dev/null || true
true
"""
        self.ssh.execute(hostname, username, kill_cmd, timeout=30)

        # Brief pause to let processes die
        time.sleep(2)

        # Verify processes are dead - retry kill if any remain
        verify_cmd = f"pgrep -u {username} python3 2>/dev/null | wc -l"
        verify_result = self.ssh.execute(hostname, username, verify_cmd, timeout=15)

        try:
            remaining = int(verify_result.stdout.strip())
            if remaining > 0:
                # Second kill attempt - more aggressive
                self.ssh.execute(hostname, username, f"kill -9 $(pgrep -u {username} python3) 2>/dev/null || true; killall -9 python3 2>/dev/null || true", timeout=30)
                time.sleep(2)
        except ValueError:
            pass

        # Optionally clean output directory
        if clean_output:
            # Remove entire dirs and recreate to avoid zsh glob errors on empty dirs
            clean_cmd = f"rm -rf {shlex.quote(work_dir)}/output {shlex.quote(work_dir)}/logs && mkdir -p {shlex.quote(work_dir)}/output {shlex.quote(work_dir)}/logs"
            self.ssh.execute(hostname, username, clean_cmd, timeout=30)

        # Update worker status and reset progress counters
        self.config_manager.update_worker(
            hostname,
            status="idle",
            assigned_domains=0,
            completed_domains=0,
            failed_domains=0
        )

        # TODO: Parse domain list and compare with completed CSVs to find aborted ones
        # For now, just mark as aborted

        if save_aborted and aborted_domains:
            for domain in aborted_domains:
                self.config_manager.add_aborted_domain(domain, "user_abort", hostname)

        return True, "Scans aborted", aborted_domains

    def abort_all_scans(
        self,
        save_aborted: bool = True,
        clean_output: bool = False,
        restart_gui: bool = False,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Tuple[bool, str]]:
        """
        Stop scans on all workers, optionally restart GUIs.

        Stops all running scans across all workers. If restart_gui is True,
        restarts the SpiderFoot GUIs so completed results remain accessible.

        Args:
            save_aborted: Whether to save aborted domains
            clean_output: Whether to also clean output directories
            restart_gui: Whether to restart GUIs after stopping (default: False)
            on_progress: Optional callback for progress updates

        Returns:
            Dict mapping hostname to (success, message)
        """
        workers = self.config_manager.get_enabled_workers()
        results = {}
        total = len(workers)

        for i, worker in enumerate(workers, 1):
            if on_progress:
                on_progress(f"[{i}/{total}] Stopping {worker.nickname or worker.hostname}...")

            success, message, _ = self.abort_worker_scans(
                worker.hostname,
                save_aborted,
                clean_output
            )
            results[worker.hostname] = (success, message)

            if on_progress:
                status = "✓" if success else "✗"
                on_progress(f"  {status} {worker.nickname or worker.hostname}")

        # Optionally restart GUIs so results remain accessible
        if restart_gui and self.config.scan_mode == "webapi":
            if on_progress:
                on_progress(f"\nRestarting GUIs on {total} workers...")

            for i, worker in enumerate(workers, 1):
                if results.get(worker.hostname, (False, ""))[0]:  # Only if abort succeeded
                    if on_progress:
                        on_progress(f"[{i}/{total}] Starting GUI on {worker.nickname or worker.hostname}...")
                    try:
                        self.start_spiderfoot_web(worker, port=worker.gui_port, force_restart=True)
                        if on_progress:
                            on_progress(f"  ✓ {worker.nickname or worker.hostname}")
                    except Exception as e:
                        if on_progress:
                            on_progress(f"  ✗ {worker.nickname or worker.hostname}: {e}")

        # End the session after aborting all scans
        self.config_manager.end_session()

        return results

    def get_worker_logs(
        self,
        hostname: str,
        lines: int = 50
    ) -> Tuple[bool, str]:
        """
        Get recent scan logs from a worker for debugging.

        Args:
            hostname: Worker hostname
            lines: Number of lines to retrieve (default: 50)

        Returns:
            Tuple of (success, log_content)
        """
        worker = self.config_manager.get_worker(hostname)
        if not worker:
            return False, f"Worker not found: {hostname}"

        username = worker.username
        work_dir = self.config.remote_work_dir.replace("~", f"/home/{username}")

        # Get the most recent log file
        log_result = self.ssh.execute(
            hostname, username,
            f"ls -t {shlex.quote(work_dir)}/logs/scan_*.log 2>/dev/null | head -1",
            timeout=30
        )

        if not log_result.success or not log_result.stdout.strip():
            return False, "No log files found on worker"

        log_file = log_result.stdout.strip()

        # Get the last N lines
        tail_result = self.ssh.execute(
            hostname, username,
            f"tail -n {lines} {shlex.quote(log_file)}",
            timeout=30
        )

        if not tail_result.success:
            return False, f"Failed to read log file: {tail_result.stderr}"

        return True, tail_result.stdout

    def get_tmux_output(
        self,
        hostname: str,
        lines: int = 50
    ) -> Tuple[bool, str]:
        """
        Get recent output from the tmux session on a worker.

        Args:
            hostname: Worker hostname
            lines: Number of lines to retrieve (default: 50)

        Returns:
            Tuple of (success, output)
        """
        worker = self.config_manager.get_worker(hostname)
        if not worker:
            return False, f"Worker not found: {hostname}"

        username = worker.username

        # Capture the tmux pane content
        capture_result = self.ssh.execute(
            hostname, username,
            f"tmux capture-pane -t sf-scans -p 2>/dev/null | tail -n {lines}",
            timeout=30
        )

        if not capture_result.success:
            return False, "Failed to capture tmux output (session may not be running)"

        return True, capture_result.stdout

    def get_worker_errors(
        self,
        hostname: str,
        limit: int = 10
    ) -> Tuple[bool, str]:
        """
        Get error logs from failed scans on a worker.

        Args:
            hostname: Worker hostname
            limit: Maximum number of error files to show (default: 10)

        Returns:
            Tuple of (success, error_summary)
        """
        worker = self.config_manager.get_worker(hostname)
        if not worker:
            return False, f"Worker not found: {hostname}"

        username = worker.username
        work_dir = self.config.remote_work_dir.replace("~", f"/home/{username}")

        # List error files
        list_result = self.ssh.execute(
            hostname, username,
            f"ls -1t {shlex.quote(work_dir)}/output/error_*.log 2>/dev/null | head -{limit}",
            timeout=30
        )

        if not list_result.success or not list_result.stdout.strip():
            return True, "No error files found (all scans succeeded or haven't run yet)"

        error_files = list_result.stdout.strip().split('\n')

        # Read first few error files
        error_summary = []
        for error_file in error_files[:5]:  # Show first 5 in detail
            domain = error_file.split('/')[-1].replace('error_', '').replace('.log', '').replace('_', '.')

            cat_result = self.ssh.execute(
                hostname, username,
                f"head -10 {shlex.quote(error_file)}",
                timeout=30
            )

            if cat_result.success:
                error_summary.append(f"\n=== {domain} ===\n{cat_result.stdout.strip()}")

        if error_summary:
            result = f"Found {len(error_files)} error files. Showing first {len(error_summary)}:\n"
            result += "\n".join(error_summary)
            return True, result
        else:
            return True, f"Found {len(error_files)} error files but couldn't read them"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_controller(config_path: Optional[str] = None) -> DistributedScanController:
    """
    Create a distributed scan controller.

    Args:
        config_path: Optional custom config path

    Returns:
        DistributedScanController instance
    """
    manager = DistributedConfigManager(config_path)
    return DistributedScanController(manager)


# =============================================================================
# QUICK TEST
# =============================================================================
if __name__ == '__main__':
    print("Distributed scanning module loaded")
    print("Classes available:")
    print("  - SSHExecutor")
    print("  - SpiderFootInstaller")
    print("  - ResourceDetector")
    print("  - DomainDistributor")
    print("  - DistributedScanController")
