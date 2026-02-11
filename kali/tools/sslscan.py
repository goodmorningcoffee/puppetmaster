"""
SSLScan Tool Wrapper

SSL/TLS certificate and cipher analysis.
Extracts certificate details useful for correlation.
"""

import re
from typing import List
from .base import BaseTool, ToolResult


class SSLScan(BaseTool):
    """Wrapper for SSLScan"""

    name = "sslscan"
    command = "sslscan"
    timeout = 60

    def build_command(self, target: str, port: int = 443, **options) -> List[str]:
        """
        Build sslscan command.

        Args:
            target: Host to scan
            port: Port number (default: 443)
        """
        return [
            self.command,
            '--no-colour',
            f'{target}:{port}'
        ]

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse sslscan output"""
        result = self._create_result(target)

        current_section = None

        for line in output.split('\n'):
            line = line.strip()

            # Detect sections
            if 'SSL/TLS Protocols:' in line:
                current_section = 'protocols'
            elif 'Supported Server Cipher(s):' in line:
                current_section = 'ciphers'
            elif 'SSL Certificate:' in line:
                current_section = 'certificate'

            # Parse certificate info
            if current_section == 'certificate':
                if line.startswith('Subject:'):
                    result.ssl_info['subject'] = line.replace('Subject:', '').strip()
                elif line.startswith('Altnames:'):
                    altnames = line.replace('Altnames:', '').strip()
                    # Extract domains from altnames
                    names = [n.strip() for n in altnames.split(',')]
                    for name in names:
                        name = name.replace('DNS:', '').strip()
                        if name and '.' in name:
                            result.subdomains.add(name.lower())
                    result.ssl_info['altnames'] = names
                elif line.startswith('Issuer:'):
                    result.ssl_info['issuer'] = line.replace('Issuer:', '').strip()
                elif line.startswith('Not valid before:'):
                    result.ssl_info['not_before'] = line.replace('Not valid before:', '').strip()
                elif line.startswith('Not valid after:'):
                    result.ssl_info['not_after'] = line.replace('Not valid after:', '').strip()
                elif line.startswith('Signature Algorithm:'):
                    result.ssl_info['sig_algo'] = line.replace('Signature Algorithm:', '').strip()

            # Parse protocols
            if current_section == 'protocols':
                if 'enabled' in line.lower():
                    # Extract protocol name
                    proto = line.split()[0] if line.split() else ''
                    if proto:
                        if 'ssl_protocols' not in result.ssl_info:
                            result.ssl_info['ssl_protocols'] = []
                        result.ssl_info['ssl_protocols'].append(proto)

            # Parse cipher suites
            if current_section == 'ciphers':
                if line and not line.startswith('Preferred') and not line.startswith('Accepted'):
                    # Check for weak ciphers
                    if any(weak in line.lower() for weak in ['rc4', 'des', 'md5', 'null', 'export']):
                        if 'weak_ciphers' not in result.ssl_info:
                            result.ssl_info['weak_ciphers'] = []
                        result.ssl_info['weak_ciphers'].append(line.split()[0] if line.split() else line)

        # Extract any additional domains from output
        all_domains = self._extract_domains(output)
        result.subdomains.update(self._filter_subdomains(all_domains, target))

        return result
