"""
Fierce Tool Wrapper

DNS reconnaissance and zone transfer testing.
"""

from typing import List
from .base import BaseTool, ToolResult


class Fierce(BaseTool):
    """Wrapper for Fierce DNS scanner"""

    name = "fierce"
    command = "fierce"
    timeout = 300

    def build_command(self, target: str, **options) -> List[str]:
        """
        Build fierce command.

        Args:
            target: Domain to scan
        """
        return [self.command, '--domain', target]

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse fierce output"""
        result = self._create_result(target)

        for line in output.split('\n'):
            line = line.strip()

            # Fierce outputs: subdomain.domain.com (ip)
            if target.lower() in line.lower() and '(' in line:
                parts = line.split()
                if parts:
                    subdomain = parts[0].strip()
                    if subdomain.endswith('.'):
                        subdomain = subdomain[:-1]
                    result.subdomains.add(subdomain.lower())

                    # Extract IP if present
                    for part in parts:
                        if part.startswith('(') and part.endswith(')'):
                            ip = part[1:-1]
                            result.ips.add(ip)

        # Also extract with regex
        result.ips.update(self._extract_ips(output))
        all_domains = self._extract_domains(output)
        result.subdomains.update(self._filter_subdomains(all_domains, target))

        # Check for zone transfer success
        if 'Zone transfer' in output and 'successful' in output.lower():
            result.metadata['zone_transfer'] = True

        return result
