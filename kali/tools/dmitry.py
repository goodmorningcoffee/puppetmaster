"""
DMitry Tool Wrapper

Deepmagic Information Gathering Tool.
Multi-purpose: WHOIS, subdomains, emails, ports.
"""

from typing import List
from .base import BaseTool, ToolResult


class DMitry(BaseTool):
    """Wrapper for DMitry"""

    name = "dmitry"
    command = "dmitry"
    timeout = 300

    def build_command(self, target: str, whois: bool = True, subdomains: bool = True,
                      emails: bool = True, ports: bool = False, **options) -> List[str]:
        """
        Build dmitry command.

        Args:
            target: Domain to investigate
            whois: Perform WHOIS lookup
            subdomains: Search for subdomains
            emails: Search for email addresses
            ports: Perform port scan (aggressive)
        """
        cmd = [self.command]

        if whois:
            cmd.append('-w')
        if subdomains:
            cmd.append('-s')
        if emails:
            cmd.append('-e')
        if ports:
            cmd.append('-p')

        cmd.append(target)

        return cmd

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse dmitry output"""
        result = self._create_result(target)

        current_section = None

        for line in output.split('\n'):
            line = line.strip()

            # Detect sections
            if 'HostIP:' in line:
                ip = line.split(':')[-1].strip()
                if ip:
                    result.ips.add(ip)

            elif 'Gathered Subdomain information' in line:
                current_section = 'subdomains'
            elif 'Gathered E-Mail information' in line:
                current_section = 'emails'
            elif 'Gathered TCP Port information' in line:
                current_section = 'ports'

            # Parse subdomains
            if current_section == 'subdomains' and line and not line.startswith('Gathered'):
                if '.' in line and not line.startswith('-'):
                    subdomain = line.strip()
                    if subdomain:
                        result.subdomains.add(subdomain.lower())

            # Parse emails
            if current_section == 'emails' and '@' in line:
                # Clean up the line
                email = line.strip()
                if '@' in email:
                    result.emails.add(email.lower())

            # Parse ports
            if current_section == 'ports' and '/' in line:
                # Format: 80/tcp open
                parts = line.split()
                if parts:
                    port_proto = parts[0]
                    if '/' in port_proto:
                        port = int(port_proto.split('/')[0])
                        state = parts[1] if len(parts) > 1 else 'unknown'
                        if state == 'open':
                            result.ports[port] = 'open'

        # Also extract with regex
        result.emails.update(self._extract_emails(output))
        result.ips.update(self._extract_ips(output))

        # Filter subdomains
        result.subdomains = self._filter_subdomains(result.subdomains, target)

        return result
