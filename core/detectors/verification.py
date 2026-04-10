"""
verification.py - Domain verification token detectors.

Smoking-gun signals from domain verification services. These tokens are
issued per-domain by a service (Google Search Console, Atlassian, etc.) and
prove ownership of the domain. Two "independent" domains showing the same
verification token = same operator who got both verified by the same service
account.

Detectors:
- GoogleSiteVerificationDetector  (google-site-verification meta tag tokens)
- AtlassianVerificationDetector   (atlassian-domain-verification tokens)

Notes:
- Both detectors include exclusion lists for known false-positive tokens
  from major cloud providers (Amazon, Microsoft, Microsoft Online), because
  SpiderFoot can incorrectly attribute these to customer domains while
  following DNS chains.
"""

from ..signals import SignalTier
from .base import BaseDetector


class GoogleSiteVerificationDetector(BaseDetector):
    """Google Search Console domain verification tokens.

    Migrated from signals.py SMOKING_GUN_PATTERNS['google_site_verification'].
    These appear as <meta name="google-site-verification" content="..."> tags
    or in Google Search Console DNS TXT records. Tokens are 43-44 characters
    of base64url and are unique per (domain, GSC account) pair.
    """
    name = "google_site_verification"
    tier = SignalTier.SMOKING_GUN
    description = "Google Site Verification Token"
    module = "sfp_webanalytics"
    patterns = [
        r"google-site-verification[=:]\s*([A-Za-z0-9_-]{43,44})",
        r"Google Site Verification:\s*([A-Za-z0-9_-]{20,50})",
    ]
    # Known false positive tokens from major cloud providers — SpiderFoot
    # follows DNS chains and may attribute these to customer domains.
    exclude_patterns = [
        r"EEVHeL7fVZb5ix5bR0draHWtJ5MfS0538OwXAfY8",  # amazonaws.com
        r"qF4YFDz-nQ_gKOOlNIxI0rC79sLnCbrUMF9fmKlj",  # microsoft.com
        r"cW7L-_2lD9bWyDxO79sYTdr0tKphk1quplaAfLS3pjY",  # microsoftonline-p.net (Azure AD)
    ]


class AtlassianVerificationDetector(BaseDetector):
    """Atlassian domain verification tokens.

    Migrated from signals.py SMOKING_GUN_PATTERNS['atlassian_verification'].
    These verify domain ownership for Atlassian products (Jira, Confluence,
    Bitbucket). Tokens are unique per (domain, Atlassian account) pair.
    """
    name = "atlassian_verification"
    tier = SignalTier.SMOKING_GUN
    description = "Atlassian Domain Verification"
    module = "sfp_webanalytics"
    patterns = [
        r"atlassian-domain-verification[=:]\s*([A-Za-z0-9+/=]{30,100})",
        r"Atlassian Domain Verification:\s*([A-Za-z0-9+/=]{30,100})",
    ]
    exclude_patterns = [
        r"ZT4AapXgobCpXIWoNcd7gtMjZyOUdr4EDFMnFUWr",  # amazonaws.com
    ]
