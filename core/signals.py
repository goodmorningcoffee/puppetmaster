#!/usr/bin/env python3
"""
signals.py - Binary Signal Classification for Sock Puppet Detection

This module implements the signal classification system:
- SMOKING GUN: One match = definitive connection
- STRONG: 2+ matches = likely connected
- WEAK: Noise, not evidence

The key insight: A single shared Google Analytics ID is stronger evidence
than 10 shared hosting providers.
"""

import re
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

# =============================================================================
# SIGNAL TIERS
# =============================================================================

class SignalTier(Enum):
    """Signal strength classification"""
    SMOKING_GUN = "smoking_gun"     # One match = confirmed connection
    STRONG = "strong"               # 2+ matches = likely connected
    WEAK = "weak"                   # Supporting context only
    NOISE = "noise"                 # Ignore - too common to be meaningful


@dataclass
class Signal:
    """Represents a detected signal between domains"""
    tier: SignalTier
    signal_type: str
    value: str
    domains: Set[str] = field(default_factory=set)
    source_module: str = ""
    description: str = ""

    def __hash__(self):
        return hash((self.signal_type, self.value))


# =============================================================================
# SIGNAL PATTERNS - What we're looking for
# =============================================================================

# SMOKING GUNS - One match = definitive connection
#
# All signal patterns have been migrated to the modular detector system under
# core/detectors/. These dicts remain as empty placeholders for backward
# compatibility with any external code that imports them. New signal types
# should be added as BaseDetector subclasses, not here.
#
# Migration map:
#   google_analytics          -> core/detectors/analytics.py
#   adsense                   -> core/detectors/analytics.py
#   facebook_pixel            -> core/detectors/social.py
#   email                     -> core/detectors/identity.py
#   ssl_fingerprint           -> core/detectors/infrastructure.py
#   google_site_verification  -> core/detectors/verification.py
#   atlassian_verification    -> core/detectors/verification.py
#   whois_registrant          -> core/detectors/identity.py
#   phone                     -> core/detectors/identity.py
#   nameserver                -> core/detectors/infrastructure.py
#   ip_address                -> core/detectors/infrastructure.py
#   crypto_address            -> core/detectors/payment.py
#
SMOKING_GUN_PATTERNS = {}

# STRONG SIGNALS - 2+ matches = likely connected
# Empty — see migration map above. All STRONG signals are now BaseDetector subclasses.
STRONG_SIGNAL_PATTERNS = {}

# WEAK SIGNALS - Context only, not evidence
WEAK_SIGNAL_PATTERNS = {
    'hosting_provider': {
        'patterns': [r'.*'],  # Will be filtered
        'module': 'sfp_hosting',
        'description': 'Hosting Provider'
    },
    'country': {
        'patterns': [r'.*'],
        'module': 'sfp_geoinfo',
        'description': 'Country'
    },
    'cms': {
        'patterns': [r'wordpress|drupal|joomla|wix|squarespace'],
        'module': 'sfp_webframework',
        'description': 'CMS/Framework'
    },
}

# NOISE - Ignore these entirely
NOISE_PATTERNS = [
    r'cloudflare',
    r'amazonaws\.com',
    r'akamai',
    r'fastly',
    r'cloudfront',
    r'googleapis\.com',
    r'gstatic\.com',
    r'bootstrapcdn',
    r'jquery',
    r'fontawesome',
    r'google-analytics\.com',  # The script itself, not the ID
    r'gravatar\.com',
    r'wp-content',
    r'wp-includes',
]


# =============================================================================
# SIGNAL EXTRACTION
# =============================================================================

class SignalExtractor:
    """Extract and classify signals from SpiderFoot data.

    Supports two extraction sources running in parallel:
    1. Legacy dict-based patterns (SMOKING_GUN_PATTERNS, STRONG_SIGNAL_PATTERNS)
    2. Detector classes (BaseDetector subclasses from core.detectors)

    Both sources produce Signal objects that get merged into a single result.
    Migration path: signals defined as detector classes should be removed from
    the legacy dicts to avoid double-counting.
    """

    # Default threshold for flood detection. A signal value shared by more
    # than this many domains is suppressed as likely noise (e.g., a Google
    # verification token from a cloud provider, a CDN's shared SSL cert,
    # an analytics ID for a popular library that slipped past filtering).
    #
    # Tuning notes:
    #   - Most real sock puppet networks are 5-50 domains
    #   - Anything >100 domains sharing one ID is almost always infrastructure
    #   - 50 is a safe middle ground; raise if you're investigating large
    #     known networks, lower if you're getting noisy clusters
    DEFAULT_FLOOD_THRESHOLD = 50

    def __init__(self, detectors=None, flood_threshold=None):
        # Compile regex patterns for efficiency
        self.smoking_gun_compiled = self._compile_patterns(SMOKING_GUN_PATTERNS)
        self.strong_compiled = self._compile_patterns(STRONG_SIGNAL_PATTERNS)
        self.noise_compiled = [re.compile(p, re.I) for p in NOISE_PATTERNS]
        # Detector instances (BaseDetector subclasses) — runs alongside legacy dicts
        self.detectors = detectors or []
        # Flood threshold for over-shared signal suppression
        self.flood_threshold = (
            flood_threshold if flood_threshold is not None
            else self.DEFAULT_FLOOD_THRESHOLD
        )
        # Signals suppressed by flood filter (kept for reporting / inspection)
        self.flood_filtered_signals: List[Signal] = []

    def _compile_patterns(self, pattern_dict: Dict) -> Dict:
        """Compile regex patterns"""
        compiled = {}
        for signal_type, config in pattern_dict.items():
            compiled[signal_type] = {
                'patterns': [re.compile(p, re.I) for p in config['patterns']],
                'exclude': [re.compile(p, re.I) for p in config.get('exclude_patterns', [])],
                'module': config['module'],
                'description': config['description']
            }
        return compiled

    def is_noise(self, value: str) -> bool:
        """Check if a value should be ignored as noise"""
        for pattern in self.noise_compiled:
            if pattern.search(value):
                return True
        return False

    def extract_from_row(self, row: Dict) -> List[Signal]:
        """Extract all signals from a single data row"""
        signals = []
        data = row.get('data', '')
        module = row.get('module', '')
        domain = row.get('scan_name', '')

        if not data or self.is_noise(data):
            return signals

        # Check smoking gun patterns
        for signal_type, config in self.smoking_gun_compiled.items():
            # Skip module check if:
            # - config['module'] is None (match any module - e.g., emails appear in many modules)
            # - CLI format (no module info)
            # - Module matches expected
            if config['module'] and module and module != 'cli_scan' and config['module'] != module:
                continue

            for pattern in config['patterns']:
                matches = pattern.findall(data)
                # Limit matches per field to prevent ReDoS and memory exhaustion
                for match in matches[:100]:
                    value = match if isinstance(match, str) else match[0] if match else data

                    # Check exclusions
                    excluded = False
                    for excl in config['exclude']:
                        if excl.search(value):
                            excluded = True
                            break

                    if not excluded and len(value) > 5:
                        signal = Signal(
                            tier=SignalTier.SMOKING_GUN,
                            signal_type=signal_type,
                            value=value,
                            domains={domain},
                            source_module=module,
                            description=config['description']
                        )
                        signals.append(signal)

        # Check strong signal patterns
        for signal_type, config in self.strong_compiled.items():
            # Skip module check if:
            # - config['module'] is None (match any module)
            # - CLI format (no module info)
            # - Module matches expected
            if config['module'] and module and module != 'cli_scan' and config['module'] != module:
                continue

            for pattern in config['patterns']:
                matches = pattern.findall(data)
                # Limit matches per field to prevent ReDoS and memory exhaustion
                for match in matches[:100]:
                    value = match if isinstance(match, str) else match[0] if match else data

                    # Check exclusions
                    excluded = False
                    for excl in config['exclude']:
                        if excl.search(value):
                            excluded = True
                            break

                    if not excluded and len(value) > 3:
                        signal = Signal(
                            tier=SignalTier.STRONG,
                            signal_type=signal_type,
                            value=value,
                            domains={domain},
                            source_module=module,
                            description=config['description']
                        )
                        signals.append(signal)

        # Run detector classes (new modular extraction path)
        for detector in self.detectors:
            signals.extend(detector.extract(row))

        return signals

    def extract_all_signals(self, data: Dict, show_progress: bool = True) -> Dict[str, Signal]:
        """
        Extract all signals from loaded SpiderFoot data.

        Returns:
            Dict mapping (signal_type, value) -> Signal with all domains
        """
        # Optional tqdm import with fallback
        try:
            from tqdm import tqdm
        except ImportError:
            def tqdm(iterable, **kwargs):
                return iterable

        all_signals = {}

        # Validate data structure
        if 'rows_by_domain' not in data:
            print("  Warning: Invalid data structure - missing 'rows_by_domain'")
            return all_signals

        # Flatten all rows
        all_rows = []
        for domain, rows in data['rows_by_domain'].items():
            all_rows.extend(rows)

        print(f"\n🔬 Extracting signals from {len(all_rows):,} data rows...")

        iterator = tqdm(all_rows, desc="  Scanning", ncols=80) if show_progress else all_rows

        for row in iterator:
            signals = self.extract_from_row(row)

            for signal in signals:
                key = (signal.signal_type, signal.value)

                if key in all_signals:
                    # Merge domains
                    all_signals[key].domains.update(signal.domains)
                else:
                    all_signals[key] = signal

        # Flood filter: suppress signals shared by more than flood_threshold domains.
        # These are almost always noise — a CDN's shared cert, a cloud provider's
        # verification token, an analytics ID for a common library, etc. — that
        # slipped past the regex exclusion lists. Without this filter, one bad
        # signal can produce N(N-1)/2 fake edges in the network graph and drown
        # out real findings with a giant garbage cluster.
        #
        # Reset per-call so multiple pipeline runs don't accumulate state.
        self.flood_filtered_signals = []
        kept_signals = {}
        for key, signal in all_signals.items():
            if len(signal.domains) > self.flood_threshold:
                self.flood_filtered_signals.append(signal)
            else:
                kept_signals[key] = signal

        if self.flood_filtered_signals:
            print(f"\n⚠ Flood filter suppressed {len(self.flood_filtered_signals)} signal(s) "
                  f"shared by >{self.flood_threshold} domains:")
            # Show top 10 worst offenders, sorted by domain count
            worst = sorted(
                self.flood_filtered_signals,
                key=lambda s: len(s.domains),
                reverse=True
            )[:10]
            for s in worst:
                value_preview = s.value[:60] + "..." if len(s.value) > 60 else s.value
                print(f"  - {s.signal_type:25} ({len(s.domains):4} domains) {value_preview}")
            if len(self.flood_filtered_signals) > 10:
                print(f"  ... and {len(self.flood_filtered_signals) - 10} more")
            print(f"  These are likely noise (CDN, cloud provider, common library).")
            print(f"  Adjust flood_threshold or add to NOISE_PATTERNS if a real signal was suppressed.")

        # Filter to only signals with 2+ domains (shared signals)
        shared_signals = {
            k: v for k, v in kept_signals.items()
            if len(v.domains) >= 2
        }

        # Summary
        smoking_guns = sum(1 for s in shared_signals.values() if s.tier == SignalTier.SMOKING_GUN)
        strong = sum(1 for s in shared_signals.values() if s.tier == SignalTier.STRONG)

        print(f"\n✓ Found {len(shared_signals)} shared signals:")
        print(f"  🔴 {smoking_guns} SMOKING GUNS (definitive connections)")
        print(f"  🟡 {strong} STRONG signals (likely connections)")

        return shared_signals


def get_smoking_guns(signals: Dict[str, Signal]) -> List[Signal]:
    """Get only smoking gun signals"""
    return [s for s in signals.values() if s.tier == SignalTier.SMOKING_GUN]


def get_strong_signals(signals: Dict[str, Signal]) -> List[Signal]:
    """Get only strong signals"""
    return [s for s in signals.values() if s.tier == SignalTier.STRONG]


def get_signals_for_domain_pair(signals: Dict[str, Signal], domain1: str, domain2: str) -> List[Signal]:
    """Get all signals connecting two specific domains"""
    connecting = []
    for signal in signals.values():
        if domain1 in signal.domains and domain2 in signal.domains:
            connecting.append(signal)
    return connecting


def summarize_signals(signals: Dict[str, Signal]) -> Dict:
    """Create a summary of detected signals"""
    summary = {
        'total': len(signals),
        'by_tier': defaultdict(int),
        'by_type': defaultdict(int),
        'top_shared': [],
    }

    for signal in signals.values():
        summary['by_tier'][signal.tier.value] += 1
        summary['by_type'][signal.signal_type] += 1

    # Top signals by domain count
    sorted_signals = sorted(signals.values(), key=lambda s: len(s.domains), reverse=True)
    summary['top_shared'] = [
        {
            'type': s.signal_type,
            'value': s.value[:50] + '...' if len(s.value) > 50 else s.value,
            'tier': s.tier.value,
            'domain_count': len(s.domains)
        }
        for s in sorted_signals[:20]
    ]

    return summary
