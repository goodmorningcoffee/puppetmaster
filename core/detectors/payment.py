"""
payment.py - Payment provider and cryptocurrency detectors.

Smoking-gun signals from payment processors and crypto addresses. These
identifiers are tied to specific merchant/wallet accounts.

Detectors:
- StripePublicKeyDetector   (pk_live_* publishable keys only)
- CryptoAddressDetector     (Bitcoin / Ethereum / Bech32 wallet addresses)  [STRONG]
"""

import hashlib
import re
from typing import List

from ..signals import Signal, SignalTier
from .base import BaseDetector


# Bitcoin Base58 alphabet (note: no 0, O, I, l to avoid confusion)
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {c: i for i, c in enumerate(_BASE58_ALPHABET)}


def _base58_decode(s: str) -> bytes:
    """Decode a base58 string to bytes. Raises ValueError on invalid characters."""
    num = 0
    for c in s:
        if c not in _BASE58_INDEX:
            raise ValueError(f"Invalid base58 character: {c!r}")
        num = num * 58 + _BASE58_INDEX[c]

    # Convert integer to bytes
    full_bytes = num.to_bytes((num.bit_length() + 7) // 8, byteorder="big")

    # Restore leading zero bytes (each leading '1' in input = leading null byte)
    leading_zeros = 0
    for c in s:
        if c == "1":
            leading_zeros += 1
        else:
            break

    return b"\x00" * leading_zeros + full_bytes


def _is_valid_bitcoin_base58check(addr: str) -> bool:
    """Validate a Bitcoin legacy address (P2PKH '1...' or P2SH '3...').

    A valid Base58Check address is 25 bytes after decoding:
        [1 version byte] [20 payload bytes] [4 checksum bytes]
    The checksum is the first 4 bytes of SHA256(SHA256(version + payload)).

    Returns True only if both the format and the checksum verify.
    """
    try:
        decoded = _base58_decode(addr)
    except ValueError:
        return False

    if len(decoded) != 25:
        return False

    payload, checksum = decoded[:-4], decoded[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return checksum == expected


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
    """Cryptocurrency wallet addresses with checksum validation.

    Matches Bitcoin (legacy P2PKH/P2SH and Bech32) and Ethereum addresses.
    Tier is STRONG (not SMOKING_GUN) because even with checksum validation
    a real wallet shared across "independent" sites is meaningful evidence
    but not a definitive identity link (one operator can use many wallets).

    Tuning over the legacy regex-only version:
    - Bitcoin legacy (1.../3...): validates Base58Check checksum, dropping
      most false positives on random base58 strings (drops ~99.6% — only
      ~0.4% of random base58-shaped strings happen to checksum-validate).
    - Ethereum (0x...): unchanged 40-hex pattern. True EIP-55 mixed-case
      checksum validation would require keccak256 which is not in stdlib.
      Length filter alone keeps false positives manageable.
    - Bech32 (bc1...): unchanged. Bech32 has its own checksum but the
      validation is non-trivial and the pattern is already specific enough.

    Module is sfp_spider where SpiderFoot extracts these from page content.
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

    # Internal regex to identify which family a candidate belongs to
    _BTC_LEGACY_RE = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$")

    def extract(self, row: dict) -> List[Signal]:
        """Custom extract: regex match, then validate Base58Check for legacy BTC.

        Calls the BaseDetector implementation to get all regex matches, then
        post-filters legacy Bitcoin addresses (1.../3...) by validating their
        Base58Check checksum. Ethereum and Bech32 addresses pass through
        unchanged (validation either requires deps not in stdlib or is
        already specific enough).
        """
        candidates = super().extract(row)
        validated = []
        for sig in candidates:
            # Only post-validate legacy Bitcoin (1... or 3...).
            # Ethereum (0x...) and Bech32 (bc1...) are passed through.
            if self._BTC_LEGACY_RE.match(sig.value):
                if _is_valid_bitcoin_base58check(sig.value):
                    validated.append(sig)
                # else: drop the false positive silently
            else:
                validated.append(sig)
        return validated
