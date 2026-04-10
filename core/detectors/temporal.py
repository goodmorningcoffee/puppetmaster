"""
temporal.py - Temporal correlation detectors.

Sock puppet operators frequently batch-create their domains: they register
5-10 fake sites in one sitting, then issue SSL certs for all of them
within minutes. The infrastructure may be compartmentalized (separate
analytics, separate WHOIS, separate certs), but the timing of the
registrations and cert issuances betrays the coordination.

These detectors extract date stamps from SpiderFoot data (WHOIS creation
dates, SSL cert issuance dates) and bucket them into ISO weeks. Two
domains landing in the same bucket get correlated through the standard
graph-edge mechanism.

Detectors:
- RegistrationWeekDetector  (domain creation date → ISO week)         [STRONG]
- CertIssuanceWeekDetector  (SSL cert issuance date → ISO week)       [STRONG]

WHY ISO WEEK BUCKETS (not fuzzy ±N day matching):
  Bucketing fits the existing graph-edge model without needing custom
  network analysis logic. Weekly granularity catches practically all
  coordinated batch registrations (operators don't usually space their
  sock puppets out across weeks). The flood filter handles the false
  positive case where many unrelated domains happen to register in the
  same week — popular weeks (e.g., new TLD launches) get suppressed.

WHY STRONG, NOT SMOKING_GUN:
  Same-week registration is meaningful but not definitive. Two unrelated
  domains can land in the same week by chance. The tier requires
  corroborating signals from other detectors before the connection
  registers as "likely."
"""

import re
from datetime import datetime
from typing import List, Optional

from ..signals import Signal, SignalTier
from .base import BaseDetector


# Month name to number mapping (for human-readable date formats)
_MONTH_NAMES = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _date_to_iso_week(year: int, month: int, day: int) -> Optional[str]:
    """Convert (year, month, day) to ISO week bucket (e.g., '2024-W11')."""
    try:
        d = datetime(year, month, day)
    except ValueError:
        return None
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _parse_date(text: str) -> Optional[str]:
    """
    Parse a date from a free-text snippet and return the ISO week bucket.

    Handles multiple common WHOIS / cert date formats:
      - ISO 8601:        2024-03-15  /  2024-03-15T12:00:00Z
      - Slash YYYY/M/D:  2024/03/15  /  2024/3/15
      - Slash D/M/YYYY:  15/03/2024  /  15/3/2024
      - Month name:      15-Mar-2024  /  Mar 15, 2024  /  March 15 2024

    Returns the ISO week string ('2024-W11') or None if parsing fails.

    Note: uses (?<!\\d) / (?!\\d) lookarounds (not \\b) at numeric boundaries
    so ISO dates followed by `T` (a word char) still match.
    """
    # ISO 8601 (most common in modern WHOIS) — allow T/space/punctuation after day
    m = re.search(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)", text)
    if m:
        return _date_to_iso_week(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # YYYY/M/D
    m = re.search(r"(?<!\d)(\d{4})/(\d{1,2})/(\d{1,2})(?!\d)", text)
    if m:
        return _date_to_iso_week(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # D/M/YYYY (European convention) — only when first number is 1-31
    m = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # Heuristic: if first number > 12, it's definitely a day (D/M/Y)
        if d > 12:
            return _date_to_iso_week(y, mo, d)
        # Otherwise ambiguous — assume D/M/Y for non-US WHOIS data
        return _date_to_iso_week(y, mo, d)

    # 15-Mar-2024  /  15 Mar 2024  /  15-March-2024
    m = re.search(
        r"(?<!\d)(\d{1,2})[-\s]([A-Za-z]{3,9})[-\s](\d{4})(?!\d)", text
    )
    if m:
        d, mo_name, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        mo = _MONTH_NAMES.get(mo_name)
        if mo:
            return _date_to_iso_week(y, mo, d)

    # Mar 15, 2024  /  March 15 2024  /  Mar 15 2024
    m = re.search(
        r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})(?!\d)", text
    )
    if m:
        mo_name, d, y = m.group(1).lower(), int(m.group(2)), int(m.group(3))
        mo = _MONTH_NAMES.get(mo_name)
        if mo:
            return _date_to_iso_week(y, mo, d)

    return None


class _BaseTemporalDetector(BaseDetector):
    """
    Shared logic for temporal detectors that find a date in a row, parse it,
    bucket it to an ISO week, and emit one signal per row.

    Subclasses set the `name`, `description`, `module`, and `_DATE_LABELS`
    (a tuple of substrings that must appear in the row's data field — used
    as a cheap pre-filter to avoid trying to date-parse every random string).
    """

    # Substrings that must appear in row.data for this detector to consider it
    _DATE_LABELS: tuple = ()

    # Patterns is unused — extract() is fully overridden — but BaseDetector
    # __init__ requires the attribute to exist for regex compilation.
    patterns: List[str] = []

    def extract(self, row: dict) -> List[Signal]:
        data = row.get("data", "")
        domain = row.get("scan_name", "")
        row_module = row.get("module", "")

        if not data or not domain:
            return []

        # Module filter (None = match any module)
        if self.module and row_module and row_module != "cli_scan":
            if self.module != row_module:
                return []

        # Cheap pre-filter: data must contain at least one date label
        # (e.g., "Creation Date", "Not Before") before we try to parse a date.
        # This prevents date parsing from running on every random row.
        data_lower = data.lower()
        if self._DATE_LABELS and not any(label in data_lower for label in self._DATE_LABELS):
            return []

        week_bucket = _parse_date(data)
        if week_bucket is None:
            return []

        return [Signal(
            tier=self.tier,
            signal_type=self.name,
            value=week_bucket,
            domains={domain},
            source_module=row_module,
            description=self.description,
        )]


class RegistrationWeekDetector(_BaseTemporalDetector):
    """Domain registration week.

    Parses domain creation dates from WHOIS data and buckets them into
    ISO weeks. Two domains registered in the same ISO week share a
    correlation edge. Catches batch sock-puppet registration sprees.
    """
    name = "registration_week"
    tier = SignalTier.STRONG
    description = "Domain registration ISO week"
    module = "sfp_whois"
    # Cheap pre-filter substrings
    _DATE_LABELS = (
        "creation date",
        "created on",
        "created:",
        "domain name commencement date",
        "registration date",
        "registered on",
    )


class CertIssuanceWeekDetector(_BaseTemporalDetector):
    """SSL certificate issuance week.

    Parses cert validity start dates ("Not Before") from sfp_crt data and
    buckets them into ISO weeks. Operators batch-issuing certs for sock
    puppet networks (e.g., via certbot for multiple domains in one
    session) get correlated through this signal.
    """
    name = "cert_issuance_week"
    tier = SignalTier.STRONG
    description = "SSL certificate issuance ISO week"
    module = "sfp_crt"
    _DATE_LABELS = (
        "not before",
        "valid from",
        "validity start",
        "issued on",
    )
