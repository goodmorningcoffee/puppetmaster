"""
observability.py - Observability platform detectors.

Smoking-gun signals from error tracking and observability platforms.
These tend to embed account-specific keys in client-side code.

Detectors:
- SentryDSNDetector  (Sentry DSN URLs — embed both project ID and public key)
"""

from ..signals import SignalTier
from .base import BaseDetector


class SentryDSNDetector(BaseDetector):
    """Sentry DSN URLs.

    A Sentry DSN looks like:
        https://[32-char hex public key]@[org-id].ingest.sentry.io/[project-id]

    The public key + project ID combo is unique to one Sentry project, which
    belongs to one Sentry organization, which is one operator. Sharing a DSN
    across "independent" sites = same Sentry account = same operator.

    DSNs can appear in any module's data — they're embedded in HTML, JS,
    sometimes leaked in error responses, etc. — so module=None.
    """
    name = "sentry_dsn"
    tier = SignalTier.SMOKING_GUN
    description = "Sentry DSN (project key)"
    module = None
    patterns = [
        # Modern format: https://[hex]@oNNN.ingest.sentry.io/NNN
        r"(https://[a-f0-9]{32}@o\d+\.ingest\.sentry\.io/\d+)",
        # Legacy format: https://[hex]@sentry.io/NNN
        r"(https://[a-f0-9]{32}@sentry\.io/\d+)",
        # Self-hosted: https://[hex]@<domain>/NNN where context says sentry
        r"Sentry\.init\(\s*\{[^}]*dsn:\s*['\"]([^'\"]+)['\"]",
    ]
