"""
content.py - Content fingerprinting detectors.

Signals derived from page content rather than infrastructure metadata.
These catch sock puppet networks where the operator has compartmentalized
their infrastructure (separate analytics, separate certs, separate WHOIS)
but reused the SAME website template, branding, or boilerplate.

Detectors:
- CopyrightDetector    (normalized copyright/footer text)            [STRONG]
- FaviconHashDetector  (MD5 hash of fetched favicon bytes)           [STRONG]

Both are STRONG (not SMOKING_GUN) because content reuse can happen for
legitimate reasons (themes, white-label products, shared agency work).
The flood filter handles popular templates appearing across many sites.
"""

import hashlib
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Optional

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


class FaviconHashDetector(BaseDetector):
    """Favicon MD5 hash fingerprinting (Shodan-style).

    Operators almost never bother creating unique favicons for their sock
    puppet sites — they ship the same icon across the whole network. Hashing
    the favicon bytes catches this even when every other identifier
    (analytics, WHOIS, SSL cert) has been compartmentalized.

    HOW IT WORKS:
    1. Parse `<link rel="icon" href="...">` tags from page content to
       discover the favicon URL. Falls back to `<scan_name>/favicon.ico`
       if no link tag is found.
    2. Resolve the URL to absolute form (handles relative paths).
    3. Fetch the URL via urllib (5s timeout, follow redirects).
    4. Validate the response is image-shaped (Content-Type starts with
       "image/" OR length is in a reasonable range for an icon).
    5. MD5-hash the bytes.
    6. Emit Signal(value=md5_hex).

    CACHING:
    Per-instance dict {url: md5_hex} prevents re-fetching the same favicon
    URL within a pipeline run. The cache is per-pipeline-run, not
    persistent — if you re-run the analysis, favicons get re-fetched. A
    future improvement could add disk-based caching to ~/.puppetmaster_cache/.

    ERROR HANDLING:
    Any fetch failure (timeout, 404, connection refused, DNS error,
    non-image response, oversized response) silently produces no signal.
    The detector NEVER raises an exception that could crash the pipeline.

    PERFORMANCE NOTES:
    - One favicon fetch per unique URL per pipeline run
    - 5s timeout per fetch
    - For 100 domains all serving distinct favicons, expect ~30-60s of
      additional pipeline time depending on network latency
    - For domains with shared favicons, the cache makes this much faster

    LIMITATIONS:
    - Only fetches favicons that are reachable at extraction time. If a
      domain is offline or behind auth, no signal is produced.
    - Doesn't normalize favicons (resize, color quantization). Two
      favicons that are visually identical but have a single byte
      difference will hash differently. This is the same limitation as
      Shodan's favicon hashing.
    """

    name = "favicon_hash"
    tier = SignalTier.STRONG
    description = "Favicon MD5 hash"
    # Operate on page-content modules where favicon URLs / HTML appear
    # (using None means any module — favicon URLs can show up unexpectedly)
    module = None

    # Patterns are unused — extract() is fully overridden — but BaseDetector
    # requires the attribute to exist for its __init__ regex compilation.
    patterns: List[str] = []

    # Reasonable bounds for a favicon download
    _FETCH_TIMEOUT = 5  # seconds
    _MIN_BYTES = 16  # below this, almost certainly not a real favicon
    _MAX_BYTES = 200_000  # 200 KB cap — most favicons are <10 KB

    # Match favicon link tags in HTML. Captures the href value.
    _LINK_RE = re.compile(
        r"""<link\s+[^>]*?rel\s*=\s*["']?(?:shortcut\s+icon|icon|apple-touch-icon)["']?[^>]*?href\s*=\s*["']([^"']+)["']""",
        re.I,
    )
    # Also catch the reverse attribute order: href before rel
    _LINK_RE_REVERSE = re.compile(
        r"""<link\s+[^>]*?href\s*=\s*["']([^"']+)["'][^>]*?rel\s*=\s*["']?(?:shortcut\s+icon|icon|apple-touch-icon)""",
        re.I,
    )

    def __init__(self):
        super().__init__()
        # Per-instance fetch cache: absolute URL -> md5 hex (or None if fetch failed)
        self._fetch_cache: dict = {}

    def _discover_favicon_url(self, page_html: str, domain: str) -> Optional[str]:
        """Extract a favicon URL from page HTML, or fall back to /favicon.ico.

        Returns an absolute URL string, or None if discovery failed.
        """
        href = None
        m = self._LINK_RE.search(page_html)
        if m:
            href = m.group(1)
        else:
            m = self._LINK_RE_REVERSE.search(page_html)
            if m:
                href = m.group(1)

        if href is None:
            # Fallback: try /favicon.ico at the domain root
            return f"https://{domain}/favicon.ico"

        # Resolve relative URLs against the domain
        if href.startswith("//"):
            return f"https:{href}"
        if href.startswith("/"):
            return f"https://{domain}{href}"
        if href.startswith(("http://", "https://")):
            return href
        # Relative path (e.g., "favicon.ico" or "static/favicon.png")
        return f"https://{domain}/{href.lstrip('./')}"

    def _fetch_and_hash(self, url: str) -> Optional[str]:
        """Fetch a favicon URL and return its MD5 hex digest, or None on any failure.

        Result is cached per-instance keyed by URL.
        """
        if url in self._fetch_cache:
            return self._fetch_cache[url]

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "PuppetMaster/1.0 favicon-fingerprinter"},
            )
            with urllib.request.urlopen(req, timeout=self._FETCH_TIMEOUT) as resp:
                # Read with size cap
                content = resp.read(self._MAX_BYTES + 1)

                # Reject too-small or too-large
                if len(content) < self._MIN_BYTES or len(content) > self._MAX_BYTES:
                    self._fetch_cache[url] = None
                    return None

                # Sanity check: content type should be image-ish (or absent)
                ctype = resp.headers.get("Content-Type", "").lower()
                if ctype and not (
                    ctype.startswith("image/")
                    or "octet-stream" in ctype
                    or "x-icon" in ctype
                ):
                    self._fetch_cache[url] = None
                    return None

                md5 = hashlib.md5(content).hexdigest()
                self._fetch_cache[url] = md5
                return md5

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
            # Any network/socket/value error → silent skip
            self._fetch_cache[url] = None
            return None
        except Exception:
            # Last-resort catch — never crash the pipeline because of a favicon
            self._fetch_cache[url] = None
            return None

    def extract(self, row: dict) -> List[Signal]:
        """Custom extract: discover favicon URL, fetch it, hash it, emit signal."""
        data = row.get("data", "")
        domain = row.get("scan_name", "")
        row_module = row.get("module", "")

        if not data or not domain:
            return []

        # Only process rows that look like they contain page HTML
        # (cheap heuristic — avoids fetching favicons for every random row)
        if "<link" not in data.lower() and "favicon" not in data.lower():
            return []

        favicon_url = self._discover_favicon_url(data, domain)
        if favicon_url is None:
            return []

        md5 = self._fetch_and_hash(favicon_url)
        if md5 is None:
            return []

        return [Signal(
            tier=self.tier,
            signal_type=self.name,
            value=md5,
            domains={domain},
            source_module=row_module,
            description=self.description,
        )]
