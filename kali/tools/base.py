"""
Base Tool Wrapper Class

Provides common functionality for all Kali tool wrappers:
- Subprocess execution with timeout
- Output parsing
- Error handling
- Logging
"""

import subprocess
import shutil
import json
import re
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any
from datetime import datetime
from pathlib import Path


class ToolError(Exception):
    """Exception raised when a tool fails"""
    def __init__(self, tool: str, message: str, stderr: str = ""):
        self.tool = tool
        self.message = message
        self.stderr = stderr
        super().__init__(f"{tool}: {message}")


@dataclass
class ToolResult:
    """
    Standardized result from any tool.

    All tools normalize their output to this format for pipeline integration.
    """
    tool: str                           # Tool name
    target: str                         # Target (domain, IP, etc.)
    success: bool                       # Whether the tool ran successfully
    timestamp: str                      # ISO timestamp

    # Discovery results
    domains: Set[str] = field(default_factory=set)          # Discovered domains
    subdomains: Set[str] = field(default_factory=set)       # Discovered subdomains
    emails: Set[str] = field(default_factory=set)           # Discovered emails
    ips: Set[str] = field(default_factory=set)              # Discovered IPs

    # Scanning results
    ports: Dict[int, str] = field(default_factory=dict)     # port -> service
    technologies: Set[str] = field(default_factory=set)     # Detected technologies
    headers: Dict[str, str] = field(default_factory=dict)   # HTTP headers
    ssl_info: Dict[str, Any] = field(default_factory=dict)  # SSL/TLS info
    dns_records: Dict[str, List[str]] = field(default_factory=dict)  # type -> values

    # Metadata results
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extracted metadata

    # Raw output
    raw_output: str = ""                # Raw tool output
    errors: List[str] = field(default_factory=list)         # Error messages

    def merge(self, other: 'ToolResult') -> 'ToolResult':
        """Merge another result into this one"""
        self.domains.update(other.domains)
        self.subdomains.update(other.subdomains)
        self.emails.update(other.emails)
        self.ips.update(other.ips)
        self.ports.update(other.ports)
        self.technologies.update(other.technologies)
        self.headers.update(other.headers)
        self.ssl_info.update(other.ssl_info)
        self.dns_records.update(other.dns_records)
        self.metadata.update(other.metadata)
        self.errors.extend(other.errors)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'tool': self.tool,
            'target': self.target,
            'success': self.success,
            'timestamp': self.timestamp,
            'domains': list(self.domains),
            'subdomains': list(self.subdomains),
            'emails': list(self.emails),
            'ips': list(self.ips),
            'ports': self.ports,
            'technologies': list(self.technologies),
            'headers': self.headers,
            'ssl_info': self.ssl_info,
            'dns_records': self.dns_records,
            'metadata': self.metadata,
            'errors': self.errors,
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class BaseTool(ABC):
    """
    Abstract base class for tool wrappers.

    Subclasses must implement:
    - command: The shell command to execute
    - parse_output: Parse raw output into ToolResult
    """

    # Tool configuration (override in subclasses)
    name: str = "base"
    command: str = ""
    timeout: int = 300  # 5 minute default timeout

    def __init__(self):
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if the tool is installed"""
        if self._available is None:
            self._available = shutil.which(self.command) is not None
        return self._available

    def get_path(self) -> Optional[str]:
        """Get full path to the tool executable"""
        return shutil.which(self.command)

    @abstractmethod
    def build_command(self, target: str, **options) -> List[str]:
        """
        Build the command line arguments.

        Args:
            target: Target domain/IP/etc
            **options: Tool-specific options

        Returns:
            List of command arguments
        """
        pass

    @abstractmethod
    def parse_output(self, output: str, target: str) -> ToolResult:
        """
        Parse tool output into standardized ToolResult.

        Args:
            output: Raw stdout from tool
            target: The target that was scanned

        Returns:
            ToolResult with parsed data
        """
        pass

    def run(self, target: str, timeout: Optional[int] = None, **options) -> ToolResult:
        """
        Execute the tool and return results.

        Args:
            target: Target to scan
            timeout: Override default timeout
            **options: Tool-specific options

        Returns:
            ToolResult with parsed output

        Raises:
            ToolError: If tool fails to execute
        """
        if not self.is_available():
            raise ToolError(self.name, f"{self.command} not found in PATH")

        cmd = self.build_command(target, **options)
        effective_timeout = timeout or self.timeout

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout
            )

            # Parse output regardless of return code (some tools return non-zero on warnings)
            parsed = self.parse_output(result.stdout, target)
            parsed.raw_output = result.stdout

            # Add any stderr as errors
            if result.stderr:
                parsed.errors.append(result.stderr.strip())

            return parsed

        except subprocess.TimeoutExpired:
            raise ToolError(self.name, f"Timeout after {effective_timeout}s")
        except Exception as e:
            raise ToolError(self.name, str(e))

    def run_passive(self, target: str, **options) -> ToolResult:
        """
        Run tool in passive mode (if supported).

        Default implementation just calls run() - override in subclasses
        that support passive mode.
        """
        return self.run(target, **options)

    def _create_result(self, target: str, success: bool = True) -> ToolResult:
        """Create a new ToolResult with common fields set"""
        return ToolResult(
            tool=self.name,
            target=target,
            success=success,
            timestamp=datetime.now().isoformat()
        )

    def _extract_domains(self, text: str) -> Set[str]:
        """Extract domain names from text"""
        # Common domain pattern
        pattern = r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
        matches = re.findall(pattern, text)
        return set(m.lower() for m in matches)

    def _extract_emails(self, text: str) -> Set[str]:
        """Extract email addresses from text"""
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(pattern, text)
        return set(m.lower() for m in matches)

    def _extract_ips(self, text: str) -> Set[str]:
        """Extract IP addresses from text"""
        # IPv4 pattern
        pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        matches = re.findall(pattern, text)
        return set(matches)

    def _filter_subdomains(self, domains: Set[str], base_domain: str) -> Set[str]:
        """Filter domains to only subdomains of base domain"""
        base = base_domain.lower()
        return set(d for d in domains if d.lower().endswith('.' + base) or d.lower() == base)
