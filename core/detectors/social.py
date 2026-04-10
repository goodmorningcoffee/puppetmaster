"""
social.py - Social platform / community detectors.

Smoking-gun signals from social platforms and community widgets that embed
account-specific identifiers.

Detectors:
- FacebookPixelDetector  (Facebook Pixel IDs)  [migrated from signals.py]
- DisqusDetector         (Disqus shortname / forum identifier)
"""

from ..signals import SignalTier
from .base import BaseDetector


class FacebookPixelDetector(BaseDetector):
    """Facebook Pixel IDs.

    Migrated from signals.py SMOKING_GUN_PATTERNS['facebook_pixel'].
    Same patterns, same module filter.
    """
    name = "facebook_pixel"
    tier = SignalTier.SMOKING_GUN
    description = "Facebook Pixel ID"
    module = "sfp_webanalytics"
    patterns = [
        r"facebook[_\s]?pixel[:\s]+(\d{15,20})",
        r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{15,20})['\"]",
    ]


class DisqusDetector(BaseDetector):
    """Disqus shortname (forum identifier).

    A Disqus shortname identifies a specific Disqus forum, which is bound to
    a single Disqus account. Operators running a blog network often share
    one Disqus account across all sites so they can moderate comments
    centrally — this is a common OPSEC slip.

    No module filter — Disqus snippets appear in HTML/JS from various modules.
    """
    name = "disqus_shortname"
    tier = SignalTier.SMOKING_GUN
    description = "Disqus Shortname"
    module = None
    patterns = [
        r"var\s+disqus_shortname\s*=\s*['\"]([a-z0-9][a-z0-9-]{2,30})['\"]",
        r"disqus_shortname\s*[:=]\s*['\"]([a-z0-9][a-z0-9-]{2,30})['\"]",
        # Subdomain in URL (handles https://, http://, and protocol-relative //)
        r"(?:https?:)?//([a-z0-9][a-z0-9-]{2,30})\.disqus\.com/",
        r"disqus\.com/embed/comments/\?[^\"']*shortname=([a-z0-9][a-z0-9-]{2,30})",
    ]
