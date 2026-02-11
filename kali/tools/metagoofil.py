"""
Metagoofil Tool Wrapper

Document metadata extraction from public documents.
Searches for PDFs, DOCs, XLS, etc. and extracts metadata.
"""

import os
import tempfile
from typing import List
from .base import BaseTool, ToolResult


class Metagoofil(BaseTool):
    """Wrapper for Metagoofil metadata extractor"""

    name = "metagoofil"
    command = "metagoofil"
    timeout = 600  # Document download/analysis takes time

    def build_command(self, target: str, file_types: str = "pdf,doc,xls,ppt,docx,xlsx,pptx",
                      limit: int = 20, download_dir: str = None, **options) -> List[str]:
        """
        Build metagoofil command.

        Args:
            target: Domain to search
            file_types: File types to search for
            limit: Max files to download
            download_dir: Directory for downloaded files
        """
        if download_dir is None:
            download_dir = tempfile.mkdtemp(prefix='metagoofil_')

        cmd = [
            self.command,
            '-d', target,
            '-t', file_types,
            '-l', str(limit),
            '-o', download_dir,
            '-n', str(limit)
        ]

        return cmd

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse metagoofil output"""
        result = self._create_result(target)

        current_section = None

        for line in output.split('\n'):
            line = line.strip()

            # Detect sections
            if 'Users found:' in line:
                current_section = 'users'
            elif 'Software found:' in line:
                current_section = 'software'
            elif 'Emails found:' in line:
                current_section = 'emails'
            elif 'Paths found:' in line:
                current_section = 'paths'

            # Parse findings
            if current_section == 'users' and line and not line.endswith(':'):
                if 'authors' not in result.metadata:
                    result.metadata['authors'] = []
                # Clean up the line
                user = line.strip('- ').strip()
                if user and user != 'Users found':
                    result.metadata['authors'].append(user)

            if current_section == 'software' and line and not line.endswith(':'):
                software = line.strip('- ').strip()
                if software and software != 'Software found':
                    result.technologies.add(software)

            if current_section == 'emails' and '@' in line:
                email = line.strip('- ').strip()
                result.emails.add(email.lower())

            if current_section == 'paths' and line and not line.endswith(':'):
                path = line.strip('- ').strip()
                if path and path != 'Paths found':
                    if 'paths' not in result.metadata:
                        result.metadata['paths'] = []
                    result.metadata['paths'].append(path)

        # Authors are SMOKING GUN signals!
        if result.metadata.get('authors'):
            result.metadata['smoking_gun_potential'] = True

        return result
