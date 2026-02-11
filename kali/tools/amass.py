"""
Amass Tool Wrapper

Advanced subdomain enumeration using multiple sources.
Supports passive and active modes.
"""

import re
import json
from typing import List, Set
from .base import BaseTool, ToolResult


class Amass(BaseTool):
    """Wrapper for OWASP Amass"""

    name = "amass"
    command = "amass"
    timeout = 600  # 10 minutes (amass can be slow)

    def build_command(self, target: str, passive: bool = True,
                      brute: bool = False, timeout_mins: int = 10, **options) -> List[str]:
        """
        Build amass command.

        Args:
            target: Domain to enumerate
            passive: Passive mode only (default: True)
            brute: Enable brute-force (only if not passive)
            timeout_mins: Timeout in minutes
        """
        cmd = [self.command, 'enum', '-d', target, '-timeout', str(timeout_mins)]

        if passive:
            cmd.append('-passive')
        elif brute:
            cmd.append('-brute')

        # Output format for easier parsing
        cmd.extend(['-json', '-'])

        return cmd

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse amass JSON output"""
        result = self._create_result(target)

        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)

                # Extract subdomain
                if 'name' in data:
                    result.subdomains.add(data['name'].lower())

                # Extract addresses
                if 'addresses' in data:
                    for addr in data['addresses']:
                        if 'ip' in addr:
                            result.ips.add(addr['ip'])

            except json.JSONDecodeError:
                # Fallback to regex extraction
                domains = self._extract_domains(line)
                result.subdomains.update(domains)

        # Filter to actual subdomains
        result.subdomains = self._filter_subdomains(result.subdomains, target)

        return result

    def run_passive(self, target: str, **options) -> ToolResult:
        """Run in passive mode"""
        return self.run(target, passive=True, **options)
