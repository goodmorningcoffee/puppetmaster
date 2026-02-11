"""
Sublist3r Tool Wrapper

Fast subdomain enumeration using search engines.
"""

from typing import List
from .base import BaseTool, ToolResult


class Sublist3r(BaseTool):
    """Wrapper for Sublist3r"""

    name = "sublist3r"
    command = "sublist3r"
    timeout = 300

    def build_command(self, target: str, threads: int = 30,
                      bruteforce: bool = False, **options) -> List[str]:
        """
        Build sublist3r command.

        Args:
            target: Domain to enumerate
            threads: Number of threads
            bruteforce: Enable bruteforce (slow)
        """
        cmd = [self.command, '-d', target, '-t', str(threads)]

        if bruteforce:
            cmd.append('-b')

        return cmd

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse sublist3r output"""
        result = self._create_result(target)

        # Sublist3r outputs one subdomain per line after "Total Unique Subdomains Found:"
        capture = False
        for line in output.split('\n'):
            line = line.strip()

            if 'Total Unique Subdomains Found:' in line:
                capture = True
                continue

            if capture and line and '.' in line:
                # Clean up any ANSI codes
                clean = line.replace('\x1b[0m', '').replace('\x1b[92m', '').strip()
                if clean and not clean.startswith('['):
                    result.subdomains.add(clean.lower())

        # Also use regex as backup
        all_domains = self._extract_domains(output)
        result.subdomains.update(self._filter_subdomains(all_domains, target))

        return result
