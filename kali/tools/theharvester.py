"""
theHarvester Tool Wrapper

Email, subdomain, and host discovery from public sources.
Supports passive mode for zero target contact.
"""

import re
from typing import List, Set
from .base import BaseTool, ToolResult


class TheHarvester(BaseTool):
    """Wrapper for theHarvester OSINT tool"""

    name = "theHarvester"
    command = "theHarvester"
    timeout = 300  # 5 minutes

    # Data sources (passive = no direct target contact)
    PASSIVE_SOURCES = [
        'anubis', 'baidu', 'bing', 'bingapi', 'bufferoverun', 'certspotter',
        'crtsh', 'dnsdumpster', 'duckduckgo', 'fullhunt', 'github-code',
        'hackertarget', 'hunter', 'intelx', 'omnisint', 'otx', 'pentesttools',
        'projectdiscovery', 'qwant', 'rapiddns', 'rocketreach', 'securityTrails',
        'sublist3r', 'threatcrowd', 'threatminer', 'urlscan', 'virustotal', 'yahoo'
    ]

    # Active sources (makes requests to target)
    ACTIVE_SOURCES = ['dnssearch', 'dnsbrute']

    def build_command(self, target: str, passive: bool = True,
                      sources: List[str] = None, limit: int = 500, **options) -> List[str]:
        """
        Build theHarvester command.

        Args:
            target: Domain to search
            passive: Only use passive sources (default: True)
            sources: Specific sources to use (default: all passive)
            limit: Result limit per source
        """
        cmd = [self.command, '-d', target, '-l', str(limit)]

        if sources:
            cmd.extend(['-b', ','.join(sources)])
        elif passive:
            # Use a subset of reliable passive sources
            reliable = ['crtsh', 'dnsdumpster', 'hackertarget', 'rapiddns',
                        'threatcrowd', 'urlscan', 'yahoo', 'bing']
            cmd.extend(['-b', ','.join(reliable)])
        else:
            cmd.extend(['-b', 'all'])

        return cmd

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse theHarvester output"""
        result = self._create_result(target)

        # Extract emails
        email_section = False
        for line in output.split('\n'):
            line = line.strip()

            if 'Emails found:' in line or '[*] Emails found:' in line:
                email_section = True
                continue
            if email_section and line.startswith('['):
                email_section = False

            if email_section and '@' in line:
                result.emails.add(line.lower())

        # Also extract with regex for robustness
        result.emails.update(self._extract_emails(output))

        # Extract hosts/subdomains
        host_section = False
        for line in output.split('\n'):
            line = line.strip()

            if 'Hosts found:' in line or '[*] Hosts found:' in line:
                host_section = True
                continue
            if host_section and line.startswith('['):
                host_section = False

            if host_section and line and not line.startswith('-'):
                # May include IP: domain:ip format
                if ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 1:
                        domain = parts[0].strip()
                        if '.' in domain:
                            result.subdomains.add(domain.lower())
                    if len(parts) >= 2:
                        ip = parts[1].strip()
                        if re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                            result.ips.add(ip)
                elif '.' in line:
                    result.subdomains.add(line.lower())

        # Extract IPs with regex
        result.ips.update(self._extract_ips(output))

        # Filter to actual subdomains
        result.subdomains = self._filter_subdomains(result.subdomains, target)

        return result

    def run_passive(self, target: str, **options) -> ToolResult:
        """Run in passive mode only"""
        return self.run(target, passive=True, **options)
