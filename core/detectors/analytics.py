"""
analytics.py - Analytics platform detectors.

Smoking-gun signals from analytics/tracking platforms. Sharing one of these
IDs across "independent" sites is essentially a signed confession of common
ownership — these IDs are tied to a specific account in the platform.

Detectors:
- GoogleAnalyticsDetector  (UA-, G-, GTM-, GT- IDs)  [migrated from signals.py]
- HotjarDetector           (hjid)
- MixpanelDetector         (mixpanel project tokens)
- SegmentDetector          (segment writeKeys)
- HeapDetector             (heap app IDs)
- MatomoDetector           (matomo/piwik tracker URLs and site IDs)
"""

from ..signals import SignalTier
from .base import BaseDetector


class GoogleAnalyticsDetector(BaseDetector):
    """Google Analytics / Tag Manager IDs.

    Migrated from signals.py SMOKING_GUN_PATTERNS['google_analytics'].
    Same patterns, same module filter.
    """
    name = "google_analytics"
    tier = SignalTier.SMOKING_GUN
    description = "Google Analytics/Tag Manager ID"
    module = "sfp_webanalytics"
    patterns = [
        r"\bUA-\d{4,10}-\d{1,4}\b",     # Universal Analytics
        r"\bG-[A-Z0-9]{10,12}\b",       # GA4
        r"\bGTM-[A-Z0-9]{6,8}\b",       # Tag Manager
        r"\bGT-[A-Z0-9]{6,12}\b",       # Google Tag
    ]


class HotjarDetector(BaseDetector):
    """Hotjar tracking IDs (hjid).

    Hotjar site IDs are integer identifiers (~6-8 digits) tied to a specific
    Hotjar account. Sharing across sites = same operator.
    """
    name = "hotjar"
    tier = SignalTier.SMOKING_GUN
    description = "Hotjar Site ID"
    module = "sfp_webanalytics"
    patterns = [
        r"hjid['\"]?\s*[:=]\s*['\"]?(\d{6,8})['\"]?",
        r"static\.hotjar\.com/c/hotjar-(\d{6,8})\.js",
    ]


class MixpanelDetector(BaseDetector):
    """Mixpanel project tokens.

    Mixpanel tokens are 32-char hex strings unique per project. Found in
    inline JS as `mixpanel.init("...")` or in API URLs.
    """
    name = "mixpanel_token"
    tier = SignalTier.SMOKING_GUN
    description = "Mixpanel Project Token"
    module = "sfp_webanalytics"
    patterns = [
        r"mixpanel\.init\(\s*['\"]([a-f0-9]{32})['\"]",
        r"api\.mixpanel\.com/[\w/]*[?&]token=([a-f0-9]{32})",
    ]


class SegmentDetector(BaseDetector):
    """Segment write keys.

    Segment write keys are 32-char alphanumeric strings unique per source.
    Often inlined as `analytics.load("...")` or as a writeKey config value.
    """
    name = "segment_writekey"
    tier = SignalTier.SMOKING_GUN
    description = "Segment Write Key"
    module = "sfp_webanalytics"
    patterns = [
        r"analytics\.load\(\s*['\"]([A-Za-z0-9]{32})['\"]",
        r"writeKey['\"]?\s*[:=]\s*['\"]([A-Za-z0-9]{32})['\"]",
        r"cdn\.segment\.com/analytics\.js/v1/([A-Za-z0-9]{32})/",
    ]


class HeapDetector(BaseDetector):
    """Heap analytics application IDs.

    Heap app IDs are numeric (~8-12 digits) and uniquely identify a Heap
    project / account.
    """
    name = "heap_appid"
    tier = SignalTier.SMOKING_GUN
    description = "Heap Analytics App ID"
    module = "sfp_webanalytics"
    patterns = [
        r"heap\.load\(\s*['\"]?(\d{8,12})['\"]?",
        r"cdn\.heapanalytics\.com/js/heap-(\d{8,12})\.js",
    ]


class MatomoDetector(BaseDetector):
    """Matomo (formerly Piwik) self-hosted analytics tracker URLs.

    Matomo is privacy-focused self-hosted analytics. Operators who care about
    not feeding Google often use it — finding the same Matomo tracker URL
    across sites is a strong indicator. Site ID alone is not unique enough
    across instances, so we match on the tracker URL itself.
    """
    name = "matomo_tracker"
    tier = SignalTier.SMOKING_GUN
    description = "Matomo / Piwik Tracker URL"
    module = "sfp_webanalytics"
    patterns = [
        r"u\s*=\s*['\"](https?://[^'\"]+/matomo[^'\"]*)['\"]",
        r"u\s*=\s*['\"](https?://[^'\"]+/piwik[^'\"]*)['\"]",
        r"['\"](https?://[^'\"]+/matomo\.js)['\"]",
        r"['\"](https?://[^'\"]+/piwik\.js)['\"]",
    ]
