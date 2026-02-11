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
SMOKING_GUN_PATTERNS = {
    # Google Analytics / Tag Manager
    'google_analytics': {
        'patterns': [
            r'\bUA-\d{4,10}-\d{1,4}\b',        # Universal Analytics (with word boundaries)
            r'\bG-[A-Z0-9]{10,12}\b',          # GA4
            r'\bGTM-[A-Z0-9]{6,8}\b',          # Tag Manager
            r'\bGT-[A-Z0-9]{6,12}\b',          # Google Tag
        ],
        'module': 'sfp_webanalytics',
        'description': 'Google Analytics/Tag Manager ID'
    },

    # Google AdSense
    'adsense': {
        'patterns': [
            r'\bpub-\d{10,20}\b',              # AdSense Publisher ID (with word boundaries)
            r'\bca-pub-\d{10,20}\b',           # AdSense with prefix
        ],
        'module': 'sfp_webanalytics',
        'description': 'Google AdSense Publisher ID'
    },

    # Facebook Pixel
    'facebook_pixel': {
        'patterns': [
            r'facebook[_\s]?pixel[:\s]+(\d{15,20})',
            r'fbq\([\'"]init[\'"]\s*,\s*[\'"](\d{15,20})[\'"]',
        ],
        'module': 'sfp_webanalytics',
        'description': 'Facebook Pixel ID'
    },

    # Unique email addresses (not generic)
    # CRITICAL: Must filter out registrar, hosting, and infrastructure emails
    'email': {
        'patterns': [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        ],
        'module': None,  # Match ALL modules - emails appear in sfp_email, sfp_whois, sfp_spider, etc.
        'description': 'Email Address',
        'exclude_patterns': [
            # Free email providers
            r'@gmail\.com$', r'@yahoo\.', r'@hotmail\.',
            r'@outlook\.', r'@aol\.com$', r'@example\.com$',
            r'@protonmail\.', r'@icloud\.com$', r'@live\.com$',
            r'@msn\.com$', r'@mail\.com$', r'@ymail\.com$',

            # Generic prefixes (abuse, admin, etc.)
            r'^abuse@', r'^admin@', r'^webmaster@', r'^hostmaster@',
            r'^noreply@', r'^no-reply@', r'^support@', r'^info@',
            r'^postmaster@', r'^security@', r'^contact@', r'^help@',
            r'^sales@', r'^billing@', r'^legal@', r'^privacy@',
            r'^dns@', r'^noc@', r'^registry@', r'^registrar@',
            r'^domains?@', r'^whois@', r'^cert@', r'^csirt@',
            r'^trustandsafety@', r'^compliance@', r'^dmca@',

            # Domain registrars and WHOIS services
            r'@markmonitor\.com$', r'@godaddy\.com$', r'@namecheap\.com$',
            r'@enom\.com$', r'@gandi\.net$', r'@contact\.gandi\.net$',
            r'@networksolutions\.com$', r'@register\.com$',
            r'@tucows\.com$', r'@publicdomainregistry\.com$',
            r'@name\.com$', r'@hover\.com$', r'@dynadot\.com$',
            r'@porkbun\.com$', r'@epik\.com$', r'@ionos\.',
            r'@1and1\.', r'@united-domains\.', r'@key-systems\.net$',
            r'@sav\.com$', r'@dropped\.pl$', r'@domaincontrol\.com$',
            r'whoisprotect', r'privacyprotect', r'domainprivacy',
            r'contactprivacy', r'whoisprivacy', r'proxy@',

            # Cloud providers (abuse/NOC contacts)
            r'@amazon\.com$', r'@amazonaws\.com$', r'@aws\.com$',
            r'@microsoft\.com$', r'@azure\.com$', r'@office\.com$',
            r'@google\.com$', r'@cloud\.google\.com$',
            r'@cloudflare\.com$', r'@akamai\.com$', r'@fastly\.com$',
            r'@digitalocean\.com$', r'@linode\.com$', r'@vultr\.com$',
            r'@ovh\.', r'@hetzner\.', r'@scaleway\.com$',

            # Hosting providers
            r'@godaddy\.com$', r'@hostgator\.com$', r'@bluehost\.com$',
            r'@siteground\.com$', r'@inmotionhosting\.com$',
            r'@dreamhost\.com$', r'@a2hosting\.com$',
            r'@secureserver\.net$', r'@idcloudhost\.',
            r'@wix\.com$', r'@squarespace\.com$', r'@shopify\.com$',
            r'@wordpress\.com$', r'@web\.com$',
            r'@wixanswers\.com$', r'@zendesk\.com$',

            # Security/CERT teams
            r'@cert\.', r'@csirt\.', r'@us-cert\.gov$',
            r'@ic3\.gov$', r'@fbi\.gov$', r'@interpol\.int$',

            # Other infrastructure
            r'@verisign\.com$', r'@icann\.org$', r'@iana\.org$',
            r'@apnic\.net$', r'@arin\.net$', r'@ripe\.net$',
            r'@lacnic\.net$', r'@afrinic\.net$',
            r'@thnic\.co\.th$', r'@big\.jp$',

            # AWS WHOIS anonymization (all domains using AWS get these)
            r'@anonymised\.email$',
            r'amazonaws\.[^@]+@',  # amazonaws.* prefix emails

            # Other registrar/TLD contacts picked up by SpiderFoot
            r'@nic\.[a-z]{2,}$',  # nic.ru, nic.mx, nic.fo, etc.
            r'@service\.aliyun\.com$',
            r'@webnic\.cc$',
            r'\.protect@withheldforprivacy\.com$',
            r'@spamfree\.bookmyname\.com$',
            r'@regprivate\.ru$',
            r'@internationaladmin\.com$',
            r'@hosteuropegroup\.com$',
            r'@cscglobal\.com$', r'@cscinfo\.com$',
            r'@o-w-o\.info$',  # Spam protection
            r'@qq\.com$',  # Chinese free email
            r'@163\.com$', r'@126\.com$',  # NetEase free email
            r'@daum\.net$',  # Korean free email

            # More registrar/registry abuse contacts from SpiderFoot crawling
            r'abuse.*@',  # Any abuse email
            r'@psi-usa\.info$', r'@eurodns\.com$', r'@opensrs\.com$',
            r'@nexigen\.digital$', r'@dinahosting\.com$',
            r'@hkdnr\.hk$', r'@nixi\.in$', r'@internetx\.de$',
            r'@nazwa\.pl$', r'@dinfo\.pl$', r'@premium\.pl$',
            r'@fareastone\.com\.tw$', r'@url\.com\.tw$', r'@net-chinese\.com\.tw$',
            r'@sakura\.ad\.jp$', r'@wind\.ad\.jp$', r'@muumuu-domain\.com$',
            r'@west\.cn$', r'@hezoon\.com$',
            r'@inwimail\.com$', r'@usp\.ac\.fj$',
            r'@ok\.is$', r'@tolvustod\.is$',
            r'@domains\.coop$', r'@netim\.com$',
            r'hexonet\.net$', r'kalengo\.com$',
            r'hostpro\.ua$', r'actaprise\.com$',
            r'sigelsberg\.com$', r'media\.us$',
            r'advania\.com$', r'\.hk$',
            r'internetx\.de$', r'url\.com\.tw$',  # Fix subdomain matching

            # Spam protection services
            r'o-w-o\.info$',

            # Generic TLD/registry contacts
            r'-admin@', r'-registrant@', r'-tech@',
            r'registry@', r'registrar@', r'tld@',
        ]
    },

    # SSL Certificate fingerprints (non-wildcard, non-LE)
    'ssl_fingerprint': {
        'patterns': [
            r'[A-Fa-f0-9]{40}',  # SHA1 fingerprint
            r'[A-Fa-f0-9]{64}',  # SHA256 fingerprint
        ],
        'module': 'sfp_crt',
        'description': 'SSL Certificate Fingerprint'
    },

    # Google Site Verification
    # NOTE: Must be careful - SpiderFoot follows DNS chains and may pick up
    # verification tokens from cloud providers (amazonaws.com, microsoft.com)
    # that get incorrectly attributed to customer domains
    'google_site_verification': {
        'patterns': [
            r'google-site-verification[=:]\s*([A-Za-z0-9_-]{43,44})',
            r'Google Site Verification:\s*([A-Za-z0-9_-]{20,50})',
        ],
        'module': 'sfp_webanalytics',
        'description': 'Google Site Verification Token',
        # Known tokens from major providers (false positives)
        'exclude_patterns': [
            r'EEVHeL7fVZb5ix5bR0draHWtJ5MfS0538OwXAfY8',  # amazonaws.com
            r'qF4YFDz-nQ_gKOOlNIxI0rC79sLnCbrUMF9fmKlj',  # microsoft.com
            r'cW7L-_2lD9bWyDxO79sYTdr0tKphk1quplaAfLS3pjY',  # microsoftonline-p.net (Azure AD)
        ]
    },

    # Atlassian verification
    'atlassian_verification': {
        'patterns': [
            r'atlassian-domain-verification[=:]\s*([A-Za-z0-9+/=]{30,100})',
            r'Atlassian Domain Verification:\s*([A-Za-z0-9+/=]{30,100})',
        ],
        'module': 'sfp_webanalytics',
        'description': 'Atlassian Domain Verification',
        # Known tokens from major providers (false positives)
        'exclude_patterns': [
            r'ZT4AapXgobCpXIWoNcd7gtMjZyOUdr4EDFMnFUWr',  # amazonaws.com
        ]
    },
}

# STRONG SIGNALS - 2+ matches = likely connected
STRONG_SIGNAL_PATTERNS = {
    # WHOIS registrant (if not privacy-protected)
    'whois_registrant': {
        'patterns': [
            r'Registrant\s+Name:\s*([^\n]+)',
            r'Registrant\s+Organization:\s*([^\n]+)',
        ],
        'module': 'sfp_whois',
        'description': 'WHOIS Registrant',
        'exclude_patterns': [
            r'privacy', r'redacted', r'data protected', r'withheld',
            r'contact privacy', r'domains by proxy', r'whoisguard',
        ]
    },

    # Phone numbers
    'phone': {
        'patterns': [
            r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',
            r'\+[0-9]{1,3}[-.\s]?[0-9]{6,14}',
        ],
        'module': 'sfp_phone',
        'description': 'Phone Number'
    },

    # Custom/unique nameservers (not generic)
    'nameserver': {
        'patterns': [
            r'ns[0-9]?\.[a-zA-Z0-9-]+\.[a-zA-Z]{2,}',
        ],
        'module': 'sfp_dnsresolve',
        'description': 'Nameserver',
        'exclude_patterns': [
            r'cloudflare', r'awsdns', r'google', r'registrar',
            r'domaincontrol', r'godaddy', r'namecheap', r'hostgator',
        ]
    },

    # Shared IP (if not CDN/hosting)
    'ip_address': {
        'patterns': [
            r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
        ],
        'module': 'sfp_dnsresolve',
        'description': 'IP Address'
    },

    # Crypto addresses (already have word boundaries, adding length validation)
    'crypto_address': {
        'patterns': [
            r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b',      # Bitcoin (26-35 chars total)
            r'\b0x[a-fA-F0-9]{40}\b',                     # Ethereum (42 chars total)
            r'\bbc1[a-zA-HJ-NP-Z0-9]{39,59}\b',          # Bech32 Bitcoin (42-62 chars)
        ],
        'module': 'sfp_spider',
        'description': 'Cryptocurrency Address'
    },
}

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
    """Extract and classify signals from SpiderFoot data"""

    def __init__(self):
        # Compile regex patterns for efficiency
        self.smoking_gun_compiled = self._compile_patterns(SMOKING_GUN_PATTERNS)
        self.strong_compiled = self._compile_patterns(STRONG_SIGNAL_PATTERNS)
        self.noise_compiled = [re.compile(p, re.I) for p in NOISE_PATTERNS]

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

        # Filter to only signals with 2+ domains (shared signals)
        shared_signals = {
            k: v for k, v in all_signals.items()
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
