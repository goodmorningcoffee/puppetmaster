"""
payment.py - Payment provider and cryptocurrency detectors.

Smoking-gun signals from payment processors and crypto addresses. These
identifiers are tied to specific merchant/wallet accounts.

Detectors:
- StripePublicKeyDetector   (pk_live_* publishable keys only)
- CryptoAddressDetector     (Bitcoin / Ethereum / Bech32 wallet addresses)  [STRONG]
"""

from ..signals import SignalTier
from .base import BaseDetector


class StripePublicKeyDetector(BaseDetector):
    """Stripe publishable keys (live mode only).

    Stripe publishable keys come in two flavors:
        pk_live_*  - real payments, tied to a specific Stripe account
        pk_test_*  - test mode, often shared in tutorials/examples

    We only flag `pk_live_*` because:
    1. Test keys appear in copy-pasted Stripe documentation across many sites
    2. Live keys are tied to a real merchant account = real operator identity

    Keys are typically embedded in the page source on Stripe Elements pages.
    No module filter — could appear in scraped HTML or JS from any module.
    """
    name = "stripe_pk_live"
    tier = SignalTier.SMOKING_GUN
    description = "Stripe Publishable Key (live mode)"
    module = None
    patterns = [
        r"\b(pk_live_[A-Za-z0-9]{24,99})\b",
    ]


class CryptoAddressDetector(BaseDetector):
    """Cryptocurrency wallet addresses.

    Migrated from signals.py STRONG_SIGNAL_PATTERNS['crypto_address'].

    Matches Bitcoin (legacy P2PKH/P2SH and Bech32) and Ethereum addresses.
    Tier is STRONG (not SMOKING_GUN) because the regex patterns can produce
    false positives on hex/base58-encoded random data — but a real wallet
    address shared across "independent" sites is meaningful evidence.

    KNOWN ISSUE (to be tuned in a follow-up): The Bitcoin Base58 pattern
    will match any 26-35 character base58 string starting with 1 or 3,
    which catches some non-address data. The next iteration should
    validate the Base58Check checksum (last 4 bytes = SHA256(SHA256(payload))[:4])
    to drop those false positives.
    """
    name = "crypto_address"
    tier = SignalTier.STRONG
    description = "Cryptocurrency Address"
    module = "sfp_spider"
    patterns = [
        r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b",      # Bitcoin legacy (26-35 chars)
        r"\b0x[a-fA-F0-9]{40}\b",                     # Ethereum (42 chars)
        r"\bbc1[a-zA-HJ-NP-Z0-9]{39,59}\b",           # Bitcoin Bech32 (42-62 chars)
    ]
