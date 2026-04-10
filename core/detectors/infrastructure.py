"""
infrastructure.py - Infrastructure-level signal detectors.

These signals correlate domains via shared physical/cryptographic
infrastructure: SSL certificates, nameservers, IP addresses. They tend to
be weaker individually than account-level identifiers (analytics, payment)
because shared hosting and CDN reuse can produce false positives — but
they're still meaningful when combined.

Detectors:
- SSLFingerprintDetector  (SHA1/SHA256 cert fingerprints)         [SMOKING_GUN]
- NameserverDetector      (custom non-generic nameservers)        [STRONG]
- IPAddressDetector       (IPv4 addresses)                        [STRONG]
"""

from ..signals import SignalTier
from .base import BaseDetector


class SSLFingerprintDetector(BaseDetector):
    """SSL certificate fingerprints (SHA1 or SHA256).

    Migrated from signals.py SMOKING_GUN_PATTERNS['ssl_fingerprint'].
    A SHA1 or SHA256 cert fingerprint uniquely identifies one specific
    certificate. Two domains presenting the same fingerprint are using
    the literal same certificate file — strong evidence of common ownership
    (though shared hosting on big providers can occasionally do this with
    SAN certs, hence why the wildcard DNS analyzer exists to filter those).
    """
    name = "ssl_fingerprint"
    tier = SignalTier.SMOKING_GUN
    description = "SSL Certificate Fingerprint"
    module = "sfp_crt"
    patterns = [
        r"\b[A-Fa-f0-9]{40}\b",   # SHA1 fingerprint (40 hex chars)
        r"\b[A-Fa-f0-9]{64}\b",   # SHA256 fingerprint (64 hex chars)
    ]


class NameserverDetector(BaseDetector):
    """Custom (non-generic) nameservers.

    Migrated from signals.py STRONG_SIGNAL_PATTERNS['nameserver'].
    Operators running their own DNS — or using a small/custom DNS provider —
    will have nameservers that don't match the big-provider patterns. The
    exclusion list filters out the ones that prove nothing (Cloudflare,
    Route53, GoDaddy, etc.).
    """
    name = "nameserver"
    tier = SignalTier.STRONG
    description = "Nameserver"
    module = "sfp_dnsresolve"
    patterns = [
        r"ns[0-9]?\.[a-zA-Z0-9-]+\.[a-zA-Z]{2,}",
    ]
    exclude_patterns = [
        r"cloudflare", r"awsdns", r"google", r"registrar",
        r"domaincontrol", r"godaddy", r"namecheap", r"hostgator",
    ]


class IPAddressDetector(BaseDetector):
    """Shared IPv4 addresses.

    Migrated from signals.py STRONG_SIGNAL_PATTERNS['ip_address'].
    Domains resolving to the same IP are usually colocated. This is a
    STRONG signal (not SMOKING_GUN) because shared hosting and CDN
    pools can legitimately put many unrelated domains on one IP.
    Combine with other signals for confidence.
    """
    name = "ip_address"
    tier = SignalTier.STRONG
    description = "IP Address"
    module = "sfp_dnsresolve"
    patterns = [
        r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
    ]
