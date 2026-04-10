"""
payment.py - Payment provider detectors.

Smoking-gun signals from payment processors. These keys are tied to specific
merchant accounts in the payment platform, so sharing them = same operator.

Detectors:
- StripePublicKeyDetector  (pk_live_* publishable keys only — pk_test_ is excluded)
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
