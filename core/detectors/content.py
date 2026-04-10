"""
content.py - Content fingerprinting detectors.

Signals derived from page content rather than infrastructure metadata.
These catch sock puppet networks where the operator has compartmentalized
their infrastructure (separate analytics, separate certs, separate WHOIS)
but reused the SAME website template, branding, or boilerplate text.

Detectors:
- CopyrightDetector  (normalized copyright/footer text)  [STRONG]

The CopyrightDetector is intentionally STRONG (not SMOKING_GUN) because
shared boilerplate is meaningful evidence but not definitive — many real
sites copy each other's footer language for legitimate reasons (white-label
products, themes, agencies sharing templates).
"""

import re
from typing import List

from ..signals import Signal, SignalTier
from .base import BaseDetector


class CopyrightDetector(BaseDetector):
    """Normalized copyright text fingerprinting.

    Extracts copyright/footer text patterns from page content and normalizes
    them for cross-site comparison. Two domains showing the same normalized
    copyright string are usually:
      1. The same operator running multiple sites with shared template, OR
      2. Multiple sites using the same off-the-shelf product/theme

    Case (1) is what we want to catch. Case (2) is mitigated by:
      - The flood filter (one popular template appearing on 100+ domains
        gets suppressed automatically)
      - Tier=STRONG rather than SMOKING_GUN (requires 2+ such matches
        to register as a "likely connection")
      - Aggressive normalization that drops generic stock phrases

    Normalization:
      - Lowercase
      - Remove year(s) and date ranges
      - Remove "all rights reserved" / "alle rechte vorbehalten" / etc.
      - Remove common corporate suffixes (Inc, LLC, Ltd, Corp, GmbH, ...)
      - Collapse whitespace
      - Strip trailing punctuation

    Stop list filters out totally generic matches like "all rights reserved"
    on its own (no entity name attached).
    """

    name = "copyright_text"
    tier = SignalTier.STRONG
    description = "Normalized copyright/footer text"
    module = None  # Copyright text appears in many modules (sfp_pageinfo, sfp_spider, etc.)

    # Match `©` or `(c)` or `Copyright`, then up to 150 chars of "name-shaped"
    # content. Allow periods (so S.A., B.V., etc. survive), but stop at
    # newlines, HTML tags, or pipe separators. The normalization step
    # cleans up trailing sentence content.
    patterns = [
        r"(?:©|\(c\)|\(C\)|Copyright)\s*[^\n<>|]{5,150}",
    ]

    # Patterns to strip during normalization (year, "all rights reserved", etc.)
    # Order matters in two ways:
    #   1. Punctuation-sensitive patterns must run before the `[^\w\s&'-]`
    #      strip in _normalize() removes their delimiters.
    #   2. In alternation lists, longer alternatives must come first
    #      (e.g., "corporation" before "corp") because regex alternation
    #      is left-to-right and stops at first match.
    _NORMALIZE_STRIP = [
        # Drop trailing sentence content after a period followed by space+capital
        # (so "Acme Corp. All rights reserved." → "Acme Corp" before suffix stripping)
        re.compile(r"\.\s+[A-Z].*$"),
        # Year or year range (e.g., "2024", "2020-2024", "2020 - 2024")
        re.compile(r"\b(?:19|20)\d{2}(?:\s*[-–—]\s*(?:19|20)?\d{2,4})?\b"),
        # Copyright markers — no \b around literals because © and ( aren't word chars
        re.compile(r"©"),
        re.compile(r"\(c\)", re.I),
        re.compile(r"\bcopyright\b", re.I),
        # "All rights reserved" in multiple languages
        re.compile(r"\ball rights reserved\b", re.I),
        re.compile(r"\balle rechte vorbehalten\b", re.I),  # German
        re.compile(r"\btodos los derechos reservados\b", re.I),  # Spanish
        re.compile(r"\btous droits réservés\b", re.I),  # French
        # Common corporate suffixes (longer alternatives FIRST so e.g.
        # "corporation" matches before "corp" tries)
        re.compile(r"\b(?:corporation|incorporated|limited|holdings|holding|group|inc|llc|ltd|corp|gmbh|pty)\.?", re.I),
        # Latin corporate suffixes (S.A., B.V.) with explicit periods
        re.compile(r"\bs\.\s*a\.?", re.I),
        re.compile(r"\bb\.\s*v\.?", re.I),
    ]

    # Generic phrases that should not produce a signal even after normalization
    _STOP_VALUES = {
        "", "rights reserved", "all rights", "company", "all right",
        "the company", "this site", "this website", "our company",
    }

    # Minimum length of normalized text for it to count as a fingerprint
    _MIN_NORMALIZED_LENGTH = 4

    def _normalize(self, text: str) -> str:
        """Normalize a copyright string for cross-site comparison."""
        # Strip year, "all rights reserved", corporate suffixes, etc.
        for pattern in self._NORMALIZE_STRIP:
            text = pattern.sub("", text)

        # Lowercase, collapse whitespace, strip punctuation
        text = text.lower()
        text = re.sub(r"[^\w\s&'-]", " ", text)  # keep word chars, spaces, &, ', -
        text = re.sub(r"\s+", " ", text)
        text = text.strip(" -.,;:")

        return text

    def extract(self, row: dict) -> List[Signal]:
        """Custom extract: regex match, then normalize, then filter generic noise."""
        candidates = super().extract(row)
        normalized_signals = []
        seen_normalized = set()

        for sig in candidates:
            normalized = self._normalize(sig.value)

            # Filter: too short to be meaningful
            if len(normalized) < self._MIN_NORMALIZED_LENGTH:
                continue

            # Filter: generic stop phrases
            if normalized in self._STOP_VALUES:
                continue

            # Dedupe within row (multiple regex matches collapsing to same normalized form)
            if normalized in seen_normalized:
                continue
            seen_normalized.add(normalized)

            # Replace the raw matched text with the normalized form so the
            # network analyzer correlates on the normalized identifier.
            normalized_signals.append(Signal(
                tier=sig.tier,
                signal_type=sig.signal_type,
                value=normalized,
                domains=sig.domains,
                source_module=sig.source_module,
                description=sig.description,
            ))

        return normalized_signals
