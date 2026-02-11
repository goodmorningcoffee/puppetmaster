"""
Nikto Tool Wrapper

Web server vulnerability scanner.
AGGRESSIVE - generates many requests.
"""

from typing import List
from .base import BaseTool, ToolResult


class Nikto(BaseTool):
    """Wrapper for Nikto web scanner"""

    name = "nikto"
    command = "nikto"
    timeout = 600  # Can take a while

    def build_command(self, target: str, port: int = 443, ssl: bool = True, **options) -> List[str]:
        """
        Build nikto command.

        Args:
            target: Host to scan
            port: Port number
            ssl: Use SSL
        """
        cmd = [self.command, '-h', target, '-p', str(port)]

        if ssl:
            cmd.append('-ssl')

        # Limit output noise
        cmd.extend(['-Format', 'txt', '-nointeractive'])

        return cmd

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse nikto output"""
        result = self._create_result(target)

        for line in output.split('\n'):
            line = line.strip()

            # Extract server info
            if '+ Server:' in line:
                server = line.replace('+ Server:', '').strip()
                result.technologies.add(server)
                result.metadata['server'] = server

            # Extract findings
            if line.startswith('+') and ':' in line:
                # Potential finding
                if 'retrieved' in line.lower() or 'found' in line.lower():
                    if 'findings' not in result.metadata:
                        result.metadata['findings'] = []
                    result.metadata['findings'].append(line[1:].strip())

            # Look for interesting headers
            if 'X-Powered-By' in line:
                powered = line.split(':')[-1].strip()
                result.technologies.add(powered)
                result.headers['X-Powered-By'] = powered

        return result
