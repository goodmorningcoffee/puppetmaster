"""
DNSRecon Tool Wrapper

DNS enumeration including SPF, DKIM, DMARC records.
"""

import re
from typing import List
from .base import BaseTool, ToolResult


class DNSRecon(BaseTool):
    """Wrapper for DNSRecon"""

    name = "dnsrecon"
    command = "dnsrecon"
    timeout = 300

    def build_command(self, target: str, record_types: str = "std",
                      bruteforce: bool = False, **options) -> List[str]:
        """
        Build dnsrecon command.

        Args:
            target: Domain to enumerate
            record_types: std, brt, axfr, etc.
            bruteforce: Enable subdomain brute-force
        """
        cmd = [self.command, '-d', target]

        if bruteforce:
            cmd.extend(['-t', 'brt'])
        else:
            cmd.extend(['-t', record_types])

        return cmd

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse dnsrecon output"""
        result = self._create_result(target)

        for line in output.split('\n'):
            line = line.strip()

            # Skip empty lines and headers
            if not line or line.startswith('[*]') and 'Performing' in line:
                continue

            # Parse DNS record lines
            # Format: [*] TYPE HOSTNAME VALUE
            if line.startswith('[*]'):
                parts = line[3:].strip().split()
                if len(parts) >= 3:
                    record_type = parts[0]
                    hostname = parts[1]
                    value = ' '.join(parts[2:])

                    # Store in dns_records
                    if record_type not in result.dns_records:
                        result.dns_records[record_type] = []
                    result.dns_records[record_type].append(value)

                    # Extract domains/subdomains
                    if record_type in ['A', 'AAAA', 'CNAME', 'NS', 'MX']:
                        if '.' in hostname:
                            result.subdomains.add(hostname.lower())

                    # Extract IPs
                    if record_type in ['A', 'AAAA']:
                        result.ips.add(value)

                    # SPF, DKIM, DMARC are valuable for correlation
                    if record_type == 'TXT':
                        if 'v=spf1' in value.lower():
                            result.metadata['spf'] = value
                        elif 'dkim' in value.lower():
                            result.metadata['dkim'] = value
                        elif 'dmarc' in value.lower():
                            result.metadata['dmarc'] = value

            # Zone transfer detection
            if 'Zone Transfer' in line and 'successful' in line.lower():
                result.metadata['zone_transfer'] = True

        # Filter subdomains
        result.subdomains = self._filter_subdomains(result.subdomains, target)

        return result
