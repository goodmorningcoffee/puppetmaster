"""
Nmap Tool Wrapper

Port scanning and service detection.
AGGRESSIVE - only use in Deep mode or with permission.
"""

import re
from typing import List, Dict
from .base import BaseTool, ToolResult


class Nmap(BaseTool):
    """Wrapper for Nmap"""

    name = "nmap"
    command = "nmap"
    timeout = 600  # Port scanning can take a while

    def build_command(self, target: str, ports: str = "21,22,25,53,80,443,8080,8443",
                      service_scan: bool = True, **options) -> List[str]:
        """
        Build nmap command.

        Args:
            target: Host to scan
            ports: Port specification (default: common web ports)
            service_scan: Enable service/version detection
        """
        cmd = [self.command, '-Pn']  # Skip host discovery

        if service_scan:
            cmd.append('-sV')

        cmd.extend(['-p', ports])
        cmd.append(target)

        return cmd

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse nmap output"""
        result = self._create_result(target)

        # Parse port lines
        # Format: PORT     STATE SERVICE    VERSION
        port_pattern = r'(\d+)/(\w+)\s+(\w+)\s+(\S+)\s*(.*)'

        for line in output.split('\n'):
            line = line.strip()

            match = re.match(port_pattern, line)
            if match:
                port = int(match.group(1))
                protocol = match.group(2)
                state = match.group(3)
                service = match.group(4)
                version = match.group(5).strip() if match.group(5) else ''

                if state == 'open':
                    service_info = service
                    if version:
                        service_info = f"{service} ({version})"
                    result.ports[port] = service_info

                    # Add as technology
                    result.technologies.add(service)
                    if version:
                        result.technologies.add(f"{service}/{version.split()[0]}")

            # Extract hostname if present
            if 'Nmap scan report for' in line:
                # Format: Nmap scan report for hostname (ip) or just hostname
                parts = line.replace('Nmap scan report for', '').strip()
                if '(' in parts:
                    hostname = parts.split('(')[0].strip()
                    ip = parts.split('(')[1].split(')')[0]
                    result.subdomains.add(hostname.lower())
                    result.ips.add(ip)

        return result
