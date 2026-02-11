"""
Sherlock Tool Wrapper

Social media username search across 300+ platforms.
Useful for linking domains to social accounts.
"""

import json
from typing import List, Dict
from .base import BaseTool, ToolResult


class Sherlock(BaseTool):
    """Wrapper for Sherlock username hunter"""

    name = "sherlock"
    command = "sherlock"
    timeout = 300  # Can take a while checking many sites

    def build_command(self, target: str, timeout_per_site: int = 10,
                      print_found: bool = True, **options) -> List[str]:
        """
        Build sherlock command.

        Args:
            target: Username to search for
            timeout_per_site: Timeout per site in seconds
            print_found: Only print found results
        """
        cmd = [
            self.command,
            '--timeout', str(timeout_per_site),
            '--print-found',
            '--json', '-',  # JSON output
            target
        ]

        return cmd

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse sherlock output"""
        result = self._create_result(target)

        # Try to parse JSON output
        try:
            # Sherlock outputs JSON for each username
            # Find JSON in output
            json_start = output.find('{')
            json_end = output.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = output[json_start:json_end]
                data = json.loads(json_str)

                if 'social_profiles' not in result.metadata:
                    result.metadata['social_profiles'] = []

                for site_name, site_data in data.items():
                    if isinstance(site_data, dict):
                        status = site_data.get('status', {})
                        if status.get('status') == 'Claimed':
                            url = site_data.get('url_user', '')
                            result.metadata['social_profiles'].append({
                                'platform': site_name,
                                'url': url,
                                'username': target
                            })

                            # Extract domain from URL
                            if url and '/' in url:
                                domain = url.split('/')[2] if len(url.split('/')) > 2 else ''
                                if domain:
                                    result.domains.add(domain.lower())

        except json.JSONDecodeError:
            # Fall back to text parsing
            for line in output.split('\n'):
                line = line.strip()

                # Look for positive matches
                # Format: [+] Site: URL
                if line.startswith('[+]') or 'http' in line.lower():
                    if 'http' in line:
                        # Extract URL
                        parts = line.split()
                        for part in parts:
                            if part.startswith('http'):
                                url = part.strip()
                                if 'social_profiles' not in result.metadata:
                                    result.metadata['social_profiles'] = []
                                result.metadata['social_profiles'].append({
                                    'url': url,
                                    'username': target
                                })

                                # Extract domain
                                domain = url.split('/')[2] if len(url.split('/')) > 2 else ''
                                if domain:
                                    result.domains.add(domain.lower())

        # Count total profiles found
        if result.metadata.get('social_profiles'):
            result.metadata['profiles_found'] = len(result.metadata['social_profiles'])

        return result

    def search_username(self, username: str) -> ToolResult:
        """Search for a username across social platforms"""
        return self.run(username)
