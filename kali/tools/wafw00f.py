"""
wafw00f Tool Wrapper

Web Application Firewall detection.
"""

from typing import List
from .base import BaseTool, ToolResult


class Wafw00f(BaseTool):
    """Wrapper for wafw00f WAF detector"""

    name = "wafw00f"
    command = "wafw00f"
    timeout = 60

    def build_command(self, target: str, **options) -> List[str]:
        """
        Build wafw00f command.

        Args:
            target: URL or domain to check
        """
        if not target.startswith('http'):
            target = f'https://{target}'

        return [self.command, target]

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse wafw00f output"""
        result = self._create_result(target)

        for line in output.split('\n'):
            line = line.strip()

            # Look for WAF detection
            if 'is behind' in line.lower():
                # Extract WAF name
                # Format: "The site https://... is behind ... (WAF_NAME)"
                if '(' in line and ')' in line:
                    waf = line.split('(')[-1].split(')')[0]
                    result.metadata['waf'] = waf
                    result.technologies.add(f"WAF:{waf}")
                elif 'is behind' in line:
                    parts = line.split('is behind')
                    if len(parts) > 1:
                        waf = parts[1].strip()
                        result.metadata['waf'] = waf
                        result.technologies.add(f"WAF:{waf}")

            elif 'No WAF detected' in line or 'seems to be unprotected' in line.lower():
                result.metadata['waf'] = None
                result.metadata['waf_detected'] = False

        return result
