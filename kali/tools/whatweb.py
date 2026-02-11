"""
WhatWeb Tool Wrapper

Web technology fingerprinting.
Identifies CMS, frameworks, server software, etc.
"""

import re
import json
from typing import List, Dict
from .base import BaseTool, ToolResult


class WhatWeb(BaseTool):
    """Wrapper for WhatWeb fingerprinter"""

    name = "whatweb"
    command = "whatweb"
    timeout = 60  # Single request, should be fast

    def build_command(self, target: str, aggression: int = 1, **options) -> List[str]:
        """
        Build whatweb command.

        Args:
            target: URL or domain to fingerprint
            aggression: 1=stealthy, 3=aggressive (default: 1)
        """
        # Ensure target has protocol
        if not target.startswith('http'):
            target = f'https://{target}'

        return [
            self.command,
            '-a', str(aggression),
            '--log-json=-',  # JSON output to stdout
            target
        ]

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse whatweb JSON output"""
        result = self._create_result(target)

        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)

                # Extract detected technologies
                if 'plugins' in data:
                    for plugin_name, plugin_data in data['plugins'].items():
                        result.technologies.add(plugin_name)

                        # Extract version if available
                        if isinstance(plugin_data, dict):
                            if 'version' in plugin_data:
                                versions = plugin_data['version']
                                if versions:
                                    ver = versions[0] if isinstance(versions, list) else versions
                                    result.technologies.add(f"{plugin_name}/{ver}")

                            # Extract specific fingerprints
                            if 'string' in plugin_data:
                                for s in plugin_data['string']:
                                    result.metadata[f'{plugin_name}_string'] = s

                # Extract HTTP status
                if 'http_status' in data:
                    result.metadata['http_status'] = data['http_status']

                # Extract target URL
                if 'target' in data:
                    result.metadata['final_url'] = data['target']

            except json.JSONDecodeError:
                # Fallback: parse text output
                # Format: http://domain [tech1] [tech2 version] ...
                techs = re.findall(r'\[([^\]]+)\]', line)
                for tech in techs:
                    result.technologies.add(tech.strip())

        return result
