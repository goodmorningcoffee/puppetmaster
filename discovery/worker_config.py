#!/usr/bin/env python3
"""
worker_config.py - Distributed Worker Configuration Management

Manages EC2 worker configurations for distributed SpiderFoot scanning.
All configs stored in JSON with atomic writes for safety.
"""

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class WorkerConfig:
    """Configuration for a single EC2 worker."""
    hostname: str                    # EC2 hostname or IP address
    username: str = "kali"           # SSH username (default: kali)
    enabled: bool = True             # Can disable without deleting
    nickname: Optional[str] = None   # Human-readable name: "worker-1"

    # Status fields (populated at runtime, not user-configured)
    status: str = "unknown"          # "unknown", "ready", "scanning", "completed", "error"
    last_seen: Optional[str] = None  # ISO timestamp of last successful connection
    spiderfoot_installed: bool = False
    tmux_installed: bool = False

    # Resource info (detected via SSH)
    ram_gb: Optional[int] = None
    cpu_cores: Optional[int] = None
    recommended_parallel: Optional[int] = None

    # Scan state
    assigned_domains: int = 0        # How many domains assigned in current run
    completed_domains: int = 0       # How many completed
    failed_domains: int = 0          # How many failed/aborted

    # GUI port for SSH tunnel
    gui_port: int = 5001             # Default SpiderFoot GUI port

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'WorkerConfig':
        """Create from dictionary."""
        return cls(**data)

    def get_display_name(self) -> str:
        """Get display name (nickname or truncated hostname)."""
        if self.nickname:
            return self.nickname
        # Truncate long EC2 hostnames
        if len(self.hostname) > 25:
            return self.hostname[:22] + "..."
        return self.hostname

    def get_resource_summary(self) -> str:
        """Get resource summary string."""
        if self.ram_gb and self.cpu_cores:
            return f"{self.ram_gb}GB RAM, {self.cpu_cores} cores"
        return "resources unknown"


@dataclass
class DistributedConfig:
    """Global distributed scanning configuration."""
    # SSH settings
    ssh_key_path: str = ""                    # Path to .pem file (same for all workers)
    ssh_timeout: int = 30                     # SSH connection timeout in seconds
    use_ssh_agent: bool = True                # Use ssh-agent instead of key file (RECOMMENDED)
    # SECURITY NOTE: use_ssh_agent=True is the secure default.
    # This means the .pem file stays on your LOCAL machine (not on EC2).
    # You must run: ssh-add ~/.ssh/your-key.pem before using puppetmaster.

    # Worker list
    workers: List[WorkerConfig] = field(default_factory=list)

    # Remote paths on workers
    remote_work_dir: str = "~/sf_distributed"         # Where to put domains/results
    spiderfoot_install_dir: str = "~/spiderfoot"      # Where SF is installed

    # AWS region for EC2 commands
    aws_region: str = "us-east-1"              # AWS region where workers are launched

    # Scan settings (user-adjustable defaults)
    parallel_scans_per_worker: int = 5         # Default parallel scans (reduced from 10 to prevent OOM)
    hard_timeout_hours: float = 6.0           # Max time per domain scan
    activity_timeout_minutes: int = 60        # Kill if no output for this long
    default_intensity: str = "all"            # "all", "footprint", "investigate", "passive"
    scan_mode: str = "webapi"                 # "webapi" (HTTP to web server) or "cli" (spawn sf.py processes)

    # Result collection
    master_output_dir: str = "./distributed_results"  # Where to collect results

    # Aborted domains tracking
    aborted_domains: List[Dict[str, Any]] = field(default_factory=list)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())

    # Current scan session info
    current_session_id: Optional[str] = None
    current_session_start: Optional[str] = None
    total_domains_in_session: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            'ssh_key_path': self.ssh_key_path,
            'ssh_timeout': self.ssh_timeout,
            'use_ssh_agent': self.use_ssh_agent,
            'aws_region': self.aws_region,
            'workers': [w.to_dict() for w in self.workers],
            'remote_work_dir': self.remote_work_dir,
            'spiderfoot_install_dir': self.spiderfoot_install_dir,
            'parallel_scans_per_worker': self.parallel_scans_per_worker,
            'hard_timeout_hours': self.hard_timeout_hours,
            'activity_timeout_minutes': self.activity_timeout_minutes,
            'default_intensity': self.default_intensity,
            'scan_mode': self.scan_mode,
            'master_output_dir': self.master_output_dir,
            'aborted_domains': self.aborted_domains,
            'created_at': self.created_at,
            'last_modified': self.last_modified,
            'current_session_id': self.current_session_id,
            'current_session_start': self.current_session_start,
            'total_domains_in_session': self.total_domains_in_session,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'DistributedConfig':
        """Create from dictionary."""
        workers = [WorkerConfig.from_dict(w) for w in data.get('workers', [])]
        return cls(
            ssh_key_path=data.get('ssh_key_path', ''),
            ssh_timeout=data.get('ssh_timeout', 30),
            use_ssh_agent=data.get('use_ssh_agent', True),  # Default to agent mode (secure)
            aws_region=data.get('aws_region', 'us-east-1'),
            workers=workers,
            remote_work_dir=data.get('remote_work_dir', '~/sf_distributed'),
            spiderfoot_install_dir=data.get('spiderfoot_install_dir', '~/spiderfoot'),
            parallel_scans_per_worker=data.get('parallel_scans_per_worker', 5),
            hard_timeout_hours=data.get('hard_timeout_hours', 6.0),
            activity_timeout_minutes=data.get('activity_timeout_minutes', 60),
            default_intensity=data.get('default_intensity', 'all'),
            scan_mode=data.get('scan_mode', 'webapi'),
            master_output_dir=data.get('master_output_dir', './distributed_results'),
            aborted_domains=data.get('aborted_domains', []),
            created_at=data.get('created_at', datetime.now().isoformat()),
            last_modified=data.get('last_modified', datetime.now().isoformat()),
            current_session_id=data.get('current_session_id'),
            current_session_start=data.get('current_session_start'),
            total_domains_in_session=data.get('total_domains_in_session', 0),
        )


class DistributedConfigManager:
    """
    Manages distributed worker configuration with JSON persistence.

    Config file: ~/.puppetmaster_workers.json in the home directory
    Uses atomic writes (temp file + rename) to prevent corruption.
    Stored in home directory so it survives puppetmaster directory deletions.
    """

    # Store in home directory so it survives puppetmaster directory deletions
    CONFIG_FILE = Path.home() / ".puppetmaster_workers.json"

    # Legacy config path for migration
    LEGACY_CONFIG_FILE = Path(__file__).parent.parent / ".distributed_workers.json"

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the config manager.

        Args:
            config_path: Optional custom path to config file
        """
        if config_path:
            self.config_file = Path(config_path)
        else:
            self.config_file = self.CONFIG_FILE
            # Migrate from legacy location if needed
            self._migrate_legacy_config()

        self.config = self._load_config()
        self._save_lock = threading.Lock()  # Prevent concurrent saves

    def _migrate_legacy_config(self):
        """Migrate config from legacy location (inside puppetmaster dir) to home directory."""
        if not self.config_file.exists() and self.LEGACY_CONFIG_FILE.exists():
            try:
                import shutil
                shutil.copy2(self.LEGACY_CONFIG_FILE, self.config_file)
                print(f"Migrated config from {self.LEGACY_CONFIG_FILE} to {self.config_file}")
            except Exception as e:
                print(f"Warning: Failed to migrate config: {e}")

    def _load_config(self) -> DistributedConfig:
        """Load config from JSON file, or create default if not exists."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    return DistributedConfig.from_dict(data)
            except json.JSONDecodeError as e:
                print(f"Warning: Config file corrupted, starting fresh: {e}")
                # Backup corrupted file
                backup_path = self.config_file.with_suffix('.json.bak')
                try:
                    self.config_file.rename(backup_path)
                except Exception:
                    pass
            except Exception as e:
                print(f"Warning: Could not load config: {e}")

        return DistributedConfig()

    def save_config(self):
        """Save current config to file with atomic write (thread-safe)."""
        self.config.last_modified = datetime.now().isoformat()

        # Use lock to prevent concurrent saves from multiple threads
        with self._save_lock:
            try:
                # Ensure parent directory exists
                self.config_file.parent.mkdir(parents=True, exist_ok=True)

                # Write to temp file first
                temp_file = self.config_file.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(self.config.to_dict(), f, indent=2)

                # Atomic rename
                temp_file.replace(self.config_file)
            except Exception as e:
                print(f"Warning: Could not save config: {e}")
                raise

    # =========================================================================
    # WORKER MANAGEMENT
    # =========================================================================

    def add_worker(
        self,
        hostname: str,
        username: str = "kali",
        nickname: Optional[str] = None
    ) -> WorkerConfig:
        """
        Add a new worker to the configuration.

        Args:
            hostname: EC2 hostname or IP address
            username: SSH username (default: kali)
            nickname: Human-readable name (optional)

        Returns:
            The created WorkerConfig

        Raises:
            ValueError: If worker with same hostname already exists
        """
        # Check for duplicates
        for worker in self.config.workers:
            if worker.hostname.lower() == hostname.lower():
                raise ValueError(f"Worker with hostname '{hostname}' already exists")

        # Assign unique GUI port
        used_ports = {w.gui_port for w in self.config.workers}
        gui_port = 5001
        while gui_port in used_ports:
            gui_port += 1

        # Auto-generate nickname if not provided
        if not nickname:
            nickname = f"worker-{len(self.config.workers) + 1}"

        worker = WorkerConfig(
            hostname=hostname.strip(),
            username=username.strip(),
            nickname=nickname,
            gui_port=gui_port,
        )

        self.config.workers.append(worker)
        self.save_config()

        return worker

    def remove_worker(self, hostname: str) -> bool:
        """
        Remove a worker by hostname.

        Args:
            hostname: The hostname to remove

        Returns:
            True if removed, False if not found
        """
        original_count = len(self.config.workers)
        self.config.workers = [
            w for w in self.config.workers
            if w.hostname.lower() != hostname.lower()
        ]

        if len(self.config.workers) < original_count:
            self.save_config()
            return True
        return False

    def get_worker(self, hostname: str) -> Optional[WorkerConfig]:
        """Get a worker by hostname."""
        for worker in self.config.workers:
            if worker.hostname.lower() == hostname.lower():
                return worker
        return None

    def get_worker_by_nickname(self, nickname: str) -> Optional[WorkerConfig]:
        """Get a worker by nickname."""
        for worker in self.config.workers:
            if worker.nickname and worker.nickname.lower() == nickname.lower():
                return worker
        return None

    def get_enabled_workers(self) -> List[WorkerConfig]:
        """Get list of enabled workers."""
        return [w for w in self.config.workers if w.enabled]

    def get_all_workers(self) -> List[WorkerConfig]:
        """Get all workers (enabled and disabled)."""
        return self.config.workers

    def update_worker(self, hostname: str, **kwargs) -> bool:
        """
        Update a worker's attributes.

        Args:
            hostname: The worker to update
            **kwargs: Attributes to update

        Returns:
            True if updated, False if worker not found
        """
        worker = self.get_worker(hostname)
        if not worker:
            return False

        for key, value in kwargs.items():
            if hasattr(worker, key):
                setattr(worker, key, value)

        self.save_config()
        return True

    def enable_worker(self, hostname: str) -> bool:
        """Enable a worker."""
        return self.update_worker(hostname, enabled=True)

    def disable_worker(self, hostname: str) -> bool:
        """Disable a worker without removing."""
        return self.update_worker(hostname, enabled=False)

    def replace_worker_hostnames(self, new_hostnames: List[str]) -> List[tuple]:
        """
        Replace hostnames for all workers, preserving all other metadata.

        Maps new hostnames to existing workers by position (sorted by nickname).
        Use this when EC2 instances are stopped and restarted with new addresses.

        Args:
            new_hostnames: List of new hostnames in order (worker_1 first, etc.)

        Returns:
            List of (nickname, old_hostname, new_hostname) tuples

        Raises:
            ValueError: If hostname count doesn't match worker count
        """
        workers = sorted(
            self.config.workers,
            key=lambda w: self._extract_worker_num(w.nickname)
        )

        if len(new_hostnames) != len(workers):
            raise ValueError(
                f"Got {len(new_hostnames)} hostnames but have {len(workers)} workers. "
                f"Counts must match."
            )

        changes = []
        for worker, new_hostname in zip(workers, new_hostnames):
            old_hostname = worker.hostname
            new_hostname = new_hostname.strip()
            worker.hostname = new_hostname
            changes.append((
                worker.nickname or worker.hostname,
                old_hostname,
                new_hostname
            ))

        self.save_config()
        return changes

    @staticmethod
    def _extract_worker_num(nickname: Optional[str]) -> int:
        """Extract numeric suffix from worker nickname for sorting."""
        if not nickname:
            return 999999
        try:
            return int(nickname.split('_')[-1])
        except (ValueError, IndexError):
            return 999999

    # =========================================================================
    # SSH KEY MANAGEMENT
    # =========================================================================

    def set_ssh_key(self, key_path: str) -> bool:
        """
        Set the SSH key path.

        Args:
            key_path: Path to .pem file

        Returns:
            True if valid and set, False if file doesn't exist
        """
        expanded_path = os.path.expanduser(key_path)

        if not os.path.isfile(expanded_path):
            return False

        self.config.ssh_key_path = expanded_path
        self.save_config()
        return True

    def get_ssh_key(self) -> str:
        """Get the SSH key path."""
        return self.config.ssh_key_path

    def has_ssh_key(self) -> bool:
        """Check if SSH authentication is configured (either agent mode or key file)."""
        if self.config.use_ssh_agent:
            # Agent mode: check if ssh-agent has keys loaded
            # Use the auto-fix functionality from distributed.py to handle stale sockets
            try:
                from .distributed import fix_ssh_auth_sock
                import subprocess

                def check_agent() -> bool:
                    result = subprocess.run(
                        ["ssh-add", "-l"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    return result.returncode == 0 and bool(result.stdout.strip())

                # First try
                if check_agent():
                    return True

                # Try to fix and retry
                fix_success, _ = fix_ssh_auth_sock()
                if fix_success:
                    return check_agent()

                return False
            except Exception:
                return False
        else:
            # Key file mode: check if file exists
            if not self.config.ssh_key_path:
                return False
            return os.path.isfile(os.path.expanduser(self.config.ssh_key_path))

    # =========================================================================
    # SETTINGS MANAGEMENT
    # =========================================================================

    def get_settings(self) -> Dict[str, Any]:
        """Get all configurable settings."""
        return {
            'ssh_key_path': self.config.ssh_key_path,
            'ssh_timeout': self.config.ssh_timeout,
            'remote_work_dir': self.config.remote_work_dir,
            'spiderfoot_install_dir': self.config.spiderfoot_install_dir,
            'parallel_scans_per_worker': self.config.parallel_scans_per_worker,
            'hard_timeout_hours': self.config.hard_timeout_hours,
            'activity_timeout_minutes': self.config.activity_timeout_minutes,
            'default_intensity': self.config.default_intensity,
            'scan_mode': self.config.scan_mode,
            'master_output_dir': self.config.master_output_dir,
        }

    def update_settings(self, **kwargs) -> None:
        """Update configuration settings."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.save_config()

    # =========================================================================
    # ABORTED DOMAINS TRACKING
    # =========================================================================

    def add_aborted_domain(
        self,
        domain: str,
        reason: str,
        worker_hostname: str
    ) -> None:
        """
        Add a domain to the aborted list.

        Args:
            domain: The domain that was aborted
            reason: Why it was aborted (e.g., "timeout", "user_abort")
            worker_hostname: Which worker was scanning it
        """
        self.config.aborted_domains.append({
            'domain': domain,
            'reason': reason,
            'worker': worker_hostname,
            'timestamp': datetime.now().isoformat(),
            'session_id': self.config.current_session_id,
        })
        self.save_config()

    def get_aborted_domains(self) -> List[Dict[str, Any]]:
        """Get list of aborted domains."""
        return self.config.aborted_domains

    def clear_aborted_domains(self) -> int:
        """
        Clear the aborted domains list.

        Returns:
            Number of domains cleared
        """
        count = len(self.config.aborted_domains)
        self.config.aborted_domains = []
        self.save_config()
        return count

    def export_aborted_domains(self, filepath: str) -> int:
        """
        Export aborted domains to a text file (one per line).

        Args:
            filepath: Output file path

        Returns:
            Number of domains exported
        """
        domains = [d['domain'] for d in self.config.aborted_domains]
        with open(filepath, 'w') as f:
            for domain in domains:
                f.write(domain + '\n')
        return len(domains)

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def start_session(self, total_domains: int) -> str:
        """
        Start a new scanning session.

        Args:
            total_domains: Total number of domains to scan

        Returns:
            Session ID
        """
        # Include microseconds to prevent collisions for same-second starts
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.config.current_session_id = session_id
        self.config.current_session_start = datetime.now().isoformat()
        self.config.total_domains_in_session = total_domains

        # Reset worker scan counts
        for worker in self.config.workers:
            worker.assigned_domains = 0
            worker.completed_domains = 0
            worker.failed_domains = 0
            worker.status = "unknown"

        self.save_config()
        return session_id

    def end_session(self) -> None:
        """End the current scanning session."""
        self.config.current_session_id = None
        self.config.current_session_start = None
        self.config.total_domains_in_session = 0
        self.save_config()

    def has_active_session(self) -> bool:
        """Check if there's an active scanning session."""
        return self.config.current_session_id is not None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_worker_count(self) -> int:
        """Get total number of workers."""
        return len(self.config.workers)

    def get_enabled_worker_count(self) -> int:
        """Get number of enabled workers."""
        return len(self.get_enabled_workers())

    def get_gui_tunnel_command(self, worker: WorkerConfig) -> str:
        """
        Generate SSH tunnel command for GUI access.

        Args:
            worker: The worker to generate command for

        Returns:
            SSH tunnel command string
        """
        if not self.config.ssh_key_path:
            return "# SSH key not configured"

        return (
            f"ssh -i {self.config.ssh_key_path} "
            f"-L {worker.gui_port}:localhost:{worker.gui_port} "
            f"{worker.username}@{worker.hostname}"
        )

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        workers = self.config.workers
        enabled = [w for w in workers if w.enabled]

        total_assigned = sum(w.assigned_domains for w in workers)
        total_completed = sum(w.completed_domains for w in workers)
        total_failed = sum(w.failed_domains for w in workers)

        return {
            'total_workers': len(workers),
            'enabled_workers': len(enabled),
            'workers_ready': sum(1 for w in enabled if w.status == 'ready'),
            'workers_scanning': sum(1 for w in enabled if w.status == 'scanning'),
            'workers_completed': sum(1 for w in enabled if w.status == 'completed'),
            'workers_error': sum(1 for w in enabled if w.status == 'error'),
            'total_assigned': total_assigned,
            'total_completed': total_completed,
            'total_failed': total_failed,
            'aborted_domains': len(self.config.aborted_domains),
            'has_active_session': self.has_active_session(),
            'session_id': self.config.current_session_id,
        }


# =============================================================================
# QUICK TEST
# =============================================================================
if __name__ == '__main__':
    # Quick test
    manager = DistributedConfigManager()

    print("Current workers:", manager.get_worker_count())
    print("Settings:", manager.get_settings())
    print("Stats:", manager.get_stats_summary())
