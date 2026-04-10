"""
base.py - Abstract base class for signal detectors.

Each detector subclasses BaseDetector and declares:
- name: short identifier (used as Signal.signal_type)
- tier: SignalTier (SMOKING_GUN, STRONG, WEAK)
- description: human-readable description
- module: SpiderFoot module to filter on (None = match any module)
- patterns: list of regex strings
- exclude_patterns: list of regex strings to filter out matches

The default extract() method handles regex matching against the row's data field.
Subclasses can override extract() for custom logic (e.g., favicon hashing).
"""

import re
from typing import List, Optional

from ..signals import Signal, SignalTier


class BaseDetector:
    """Abstract base for signal detectors. Subclass and set class attributes."""

    name: str = ""
    tier: SignalTier = SignalTier.WEAK
    description: str = ""
    module: Optional[str] = None  # SpiderFoot module to filter on, or None for any
    patterns: List[str] = []
    exclude_patterns: List[str] = []

    def __init__(self):
        self._compiled_patterns = [re.compile(p, re.I) for p in self.patterns]
        self._compiled_exclusions = [re.compile(p, re.I) for p in self.exclude_patterns]

    def extract(self, row: dict) -> List[Signal]:
        """
        Extract signals from a single SpiderFoot data row.

        Default implementation: regex match against `data` field, filter by module,
        respect exclusion patterns. Deduplicates within a single row so that
        multiple overlapping patterns matching the same value emit one signal.
        Override for custom extraction logic.

        Args:
            row: dict with keys 'data', 'module', 'scan_name' (domain)

        Returns:
            List of Signal objects (empty if no matches)
        """
        signals = []
        seen_values = set()  # Dedupe within a single row across all patterns
        data = row.get('data', '')
        row_module = row.get('module', '')
        domain = row.get('scan_name', '')

        if not data:
            return signals

        # Module filter (None = match any module)
        # Skip module check if config module is None, or row module is empty/cli_scan
        if self.module and row_module and row_module != 'cli_scan':
            if self.module != row_module:
                return signals

        for pattern in self._compiled_patterns:
            # Cap matches per row to prevent ReDoS / memory exhaustion
            for match in pattern.findall(data)[:100]:
                # findall returns either str or tuple depending on capture groups
                if isinstance(match, tuple):
                    value = match[0] if match else ''
                else:
                    value = match

                if not value:
                    continue

                # Apply exclusions
                if any(excl.search(value) for excl in self._compiled_exclusions):
                    continue

                # Skip if we already emitted this exact value from another pattern
                if value in seen_values:
                    continue
                seen_values.add(value)

                signals.append(Signal(
                    tier=self.tier,
                    signal_type=self.name,
                    value=value,
                    domains={domain},
                    source_module=row_module,
                    description=self.description,
                ))
        return signals
