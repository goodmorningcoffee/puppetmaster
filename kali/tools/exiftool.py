"""
ExifTool Tool Wrapper

Image and document metadata extraction.
SMOKING GUN potential: Camera serials, GPS, author names, software.
"""

import json
import re
from typing import List, Dict, Any
from pathlib import Path
from .base import BaseTool, ToolResult


class ExifTool(BaseTool):
    """Wrapper for ExifTool metadata extractor"""

    name = "exiftool"
    command = "exiftool"
    timeout = 60

    # Metadata fields that are SMOKING GUN signals
    SMOKING_GUN_FIELDS = [
        'SerialNumber', 'InternalSerialNumber', 'CameraSerialNumber',
        'LensSerialNumber', 'Author', 'Creator', 'Artist',
        'OwnerName', 'Copyright', 'CreatorTool', 'Producer',
        'Company', 'Manager', 'LastModifiedBy',
    ]

    # Fields useful for correlation
    CORRELATION_FIELDS = [
        'Software', 'CreateDate', 'ModifyDate', 'GPSLatitude', 'GPSLongitude',
        'Make', 'Model', 'LensModel', 'ImageUniqueID',
    ]

    def build_command(self, target: str, **options) -> List[str]:
        """
        Build exiftool command.

        Args:
            target: File or directory to analyze
        """
        return [
            self.command,
            '-json',
            '-r',  # Recursive
            target
        ]

    def parse_output(self, output: str, target: str) -> ToolResult:
        """Parse exiftool JSON output"""
        result = self._create_result(target)

        try:
            data = json.loads(output)

            for item in data:
                file_path = item.get('SourceFile', 'unknown')

                # Extract SMOKING GUN fields
                for field in self.SMOKING_GUN_FIELDS:
                    if field in item and item[field]:
                        value = str(item[field])
                        if value and value != 'unknown':
                            key = f'smoking_gun_{field.lower()}'
                            if key not in result.metadata:
                                result.metadata[key] = []
                            result.metadata[key].append({
                                'value': value,
                                'file': file_path
                            })

                # Extract correlation fields
                for field in self.CORRELATION_FIELDS:
                    if field in item and item[field]:
                        value = str(item[field])
                        if value:
                            key = f'meta_{field.lower()}'
                            if key not in result.metadata:
                                result.metadata[key] = []
                            result.metadata[key].append(value)

                            # Software as technology
                            if field == 'Software':
                                result.technologies.add(value)

                # Extract GPS if present
                if 'GPSLatitude' in item and 'GPSLongitude' in item:
                    lat = item['GPSLatitude']
                    lon = item['GPSLongitude']
                    if lat and lon:
                        if 'gps_locations' not in result.metadata:
                            result.metadata['gps_locations'] = []
                        result.metadata['gps_locations'].append({
                            'lat': lat,
                            'lon': lon,
                            'file': file_path
                        })

                # Extract author/creator
                for field in ['Author', 'Creator', 'Artist', 'OwnerName']:
                    if field in item and item[field]:
                        if 'authors' not in result.metadata:
                            result.metadata['authors'] = set()
                        result.metadata['authors'].add(item[field])

            # Convert authors set to list
            if 'authors' in result.metadata:
                result.metadata['authors'] = list(result.metadata['authors'])

            # Flag if we found smoking gun data
            if any(k.startswith('smoking_gun_') for k in result.metadata):
                result.metadata['smoking_gun_found'] = True

        except json.JSONDecodeError:
            result.errors.append("Failed to parse exiftool JSON output")
            result.success = False

        return result

    def analyze_file(self, file_path: str) -> ToolResult:
        """Analyze a single file"""
        return self.run(file_path)

    def analyze_directory(self, dir_path: str) -> ToolResult:
        """Analyze all files in a directory recursively"""
        return self.run(dir_path)
