"""
DNSEnum Tool Wrapper

DNS enumeration and zone transfer testing.
"""

from typing import List
from .base import BaseTool, ToolResult


class DNSEnum(BaseTool):
    """Wrapper for DNSEnum"""

    name = "dnsenum"
    command = "dnsenum"
    timeout = 300

    def build_command(self, target: str, threads: int = 10,
                      bruteforce: bool = False, **options) -> List[str]:
        """
        Build dnsenum command.

        Args:
            target: Domain to enumerate
            threads: Number of threads
            bruteforce: Enable subdomain brute-force
        """
        cmd = [self.command, '--threads', str(threads), '--noreverse']

        if not bruteforce:
            cmd.append('--nobrute')

        cmd.append(target)

        return cmd

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse dnsenum output"""
        result = self._create_result(target)

        current_section = None

        for line in output.split('\n'):
            line = line.strip()

            # Detect sections
            if 'Host' in line and 'Address' in line:
                current_section = 'hosts'
            elif 'Name Servers:' in line:
                current_section = 'ns'
            elif 'Mail (MX)' in line:
                current_section = 'mx'
            elif 'Zone Transfer:' in line:
                current_section = 'zone'

            # Parse host entries
            # Format: hostname.domain.com.    A    192.168.1.1
            if current_section in ['hosts', 'ns', 'mx']:
                parts = line.split()
                if len(parts) >= 3:
                    hostname = parts[0].rstrip('.')
                    record_type = parts[1] if len(parts) > 1 else ''
                    value = parts[-1]

                    if '.' in hostname:
                        result.subdomains.add(hostname.lower())

                    # Extract IP
                    if record_type in ['A', 'AAAA'] or self._is_ip(value):
                        result.ips.add(value)

                    # Store nameservers
                    if current_section == 'ns':
                        if 'nameservers' not in result.dns_records:
                            result.dns_records['nameservers'] = []
                        result.dns_records['nameservers'].append(hostname)

                    # Store MX
                    if current_section == 'mx':
                        if 'mx' not in result.dns_records:
                            result.dns_records['mx'] = []
                        result.dns_records['mx'].append(hostname)

            # Zone transfer detection
            if current_section == 'zone':
                if 'successful' in line.lower():
                    result.metadata['zone_transfer'] = True

        # Filter subdomains
        result.subdomains = self._filter_subdomains(result.subdomains, target)

        return result

    def _is_ip(self, s: str) -> bool:
        """Check if string is an IP address"""
        parts = s.split('.')
        if len(parts) == 4:
            return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
        return False
