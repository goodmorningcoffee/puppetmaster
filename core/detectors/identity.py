"""
identity.py - Personal/organizational identity signal detectors.

Signals tied to a real-world person or organization: email addresses,
WHOIS registrant info, phone numbers. These USED to be the bread and
butter of sock puppet detection but are increasingly weak as WHOIS
privacy services and disposable email become standard.

Detectors:
- EmailDetector             (unique email addresses)              [SMOKING_GUN]
- WhoisRegistrantDetector   (WHOIS registrant name/org)           [STRONG]
- PhoneDetector             (phone numbers)                       [STRONG]

Notes on EmailDetector:
- Ranks as SMOKING_GUN because a TRULY unique personal email shared across
  domains is essentially a signed confession.
- BUT — most matches in real data are noise: registrar contacts, abuse@,
  cloud provider WHOIS proxies, free webmail. The exclusion list is large
  and growing. New noise patterns should be added there.
- Module=None because emails appear in many SpiderFoot modules
  (sfp_email, sfp_whois, sfp_spider, etc.).
"""

from ..signals import SignalTier
from .base import BaseDetector


class EmailDetector(BaseDetector):
    """Unique email addresses, with extensive noise filtering.

    Migrated from signals.py SMOKING_GUN_PATTERNS['email']. The exclusion
    list is intentionally massive — every entry exists because we got
    bitten by it in real data at some point. Add to it freely; deletions
    should be rare.
    """
    name = "email"
    tier = SignalTier.SMOKING_GUN
    description = "Email Address"
    module = None  # Match all modules — emails appear in many
    patterns = [
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    ]
    exclude_patterns = [
        # Free email providers
        r"@gmail\.com$", r"@yahoo\.", r"@hotmail\.",
        r"@outlook\.", r"@aol\.com$", r"@example\.com$",
        r"@protonmail\.", r"@icloud\.com$", r"@live\.com$",
        r"@msn\.com$", r"@mail\.com$", r"@ymail\.com$",

        # Generic prefixes (abuse, admin, etc.)
        r"^abuse@", r"^admin@", r"^webmaster@", r"^hostmaster@",
        r"^noreply@", r"^no-reply@", r"^support@", r"^info@",
        r"^postmaster@", r"^security@", r"^contact@", r"^help@",
        r"^sales@", r"^billing@", r"^legal@", r"^privacy@",
        r"^dns@", r"^noc@", r"^registry@", r"^registrar@",
        r"^domains?@", r"^whois@", r"^cert@", r"^csirt@",
        r"^trustandsafety@", r"^compliance@", r"^dmca@",

        # Domain registrars and WHOIS services
        r"@markmonitor\.com$", r"@godaddy\.com$", r"@namecheap\.com$",
        r"@enom\.com$", r"@gandi\.net$", r"@contact\.gandi\.net$",
        r"@networksolutions\.com$", r"@register\.com$",
        r"@tucows\.com$", r"@publicdomainregistry\.com$",
        r"@name\.com$", r"@hover\.com$", r"@dynadot\.com$",
        r"@porkbun\.com$", r"@epik\.com$", r"@ionos\.",
        r"@1and1\.", r"@united-domains\.", r"@key-systems\.net$",
        r"@sav\.com$", r"@dropped\.pl$", r"@domaincontrol\.com$",
        r"whoisprotect", r"privacyprotect", r"domainprivacy",
        r"contactprivacy", r"whoisprivacy", r"proxy@",

        # Cloud providers (abuse/NOC contacts)
        r"@amazon\.com$", r"@amazonaws\.com$", r"@aws\.com$",
        r"@microsoft\.com$", r"@azure\.com$", r"@office\.com$",
        r"@google\.com$", r"@cloud\.google\.com$",
        r"@cloudflare\.com$", r"@akamai\.com$", r"@fastly\.com$",
        r"@digitalocean\.com$", r"@linode\.com$", r"@vultr\.com$",
        r"@ovh\.", r"@hetzner\.", r"@scaleway\.com$",

        # Hosting providers (godaddy already listed under registrars)
        r"@hostgator\.com$", r"@bluehost\.com$",
        r"@siteground\.com$", r"@inmotionhosting\.com$",
        r"@dreamhost\.com$", r"@a2hosting\.com$",
        r"@secureserver\.net$", r"@idcloudhost\.",
        r"@wix\.com$", r"@squarespace\.com$", r"@shopify\.com$",
        r"@wordpress\.com$", r"@web\.com$",
        r"@wixanswers\.com$", r"@zendesk\.com$",

        # Security/CERT teams
        r"@cert\.", r"@csirt\.", r"@us-cert\.gov$",
        r"@ic3\.gov$", r"@fbi\.gov$", r"@interpol\.int$",

        # Other infrastructure
        r"@verisign\.com$", r"@icann\.org$", r"@iana\.org$",
        r"@apnic\.net$", r"@arin\.net$", r"@ripe\.net$",
        r"@lacnic\.net$", r"@afrinic\.net$",
        r"@thnic\.co\.th$", r"@big\.jp$",

        # AWS WHOIS anonymization (all domains using AWS get these)
        r"@anonymised\.email$",
        r"amazonaws\.[^@]+@",  # amazonaws.* prefix emails

        # Sentry DSN false positive — DSN URLs (https://hex@oNNN.ingest.sentry.io/NNN)
        # contain an @ that the email regex matches. Detected separately by SentryDSNDetector.
        r"@o\d+\.ingest\.sentry\.io",
        r"@[\w.-]*sentry\.io",

        # Other registrar/TLD contacts picked up by SpiderFoot
        r"@nic\.[a-z]{2,}$",  # nic.ru, nic.mx, nic.fo, etc.
        r"@service\.aliyun\.com$",
        r"@webnic\.cc$",
        r"\.protect@withheldforprivacy\.com$",
        r"@spamfree\.bookmyname\.com$",
        r"@regprivate\.ru$",
        r"@internationaladmin\.com$",
        r"@hosteuropegroup\.com$",
        r"@cscglobal\.com$", r"@cscinfo\.com$",
        r"@o-w-o\.info$",  # Spam protection
        r"@qq\.com$",  # Chinese free email
        r"@163\.com$", r"@126\.com$",  # NetEase free email
        r"@daum\.net$",  # Korean free email

        # More registrar/registry abuse contacts from SpiderFoot crawling
        r"abuse.*@",  # Any abuse email
        r"@psi-usa\.info$", r"@eurodns\.com$", r"@opensrs\.com$",
        r"@nexigen\.digital$", r"@dinahosting\.com$",
        r"@hkdnr\.hk$", r"@nixi\.in$", r"@internetx\.de$",
        r"@nazwa\.pl$", r"@dinfo\.pl$", r"@premium\.pl$",
        r"@fareastone\.com\.tw$", r"@url\.com\.tw$", r"@net-chinese\.com\.tw$",
        r"@sakura\.ad\.jp$", r"@wind\.ad\.jp$", r"@muumuu-domain\.com$",
        r"@west\.cn$", r"@hezoon\.com$",
        r"@inwimail\.com$", r"@usp\.ac\.fj$",
        r"@ok\.is$", r"@tolvustod\.is$",
        r"@domains\.coop$", r"@netim\.com$",
        r"hexonet\.net$", r"kalengo\.com$",
        r"hostpro\.ua$", r"actaprise\.com$",
        r"sigelsberg\.com$", r"media\.us$",
        r"advania\.com$", r"@.*registrar.*\.hk$",

        # Generic TLD/registry contacts
        r"-admin@", r"-registrant@", r"-tech@",
        r"tld@",
    ]


class WhoisRegistrantDetector(BaseDetector):
    """WHOIS registrant name and organization.

    Migrated from signals.py STRONG_SIGNAL_PATTERNS['whois_registrant'].

    NOTE: This signal is increasingly weak as WHOIS privacy services have
    become standard. Most domains today return REDACTED FOR PRIVACY or
    point at a privacy proxy service. The exclusion list catches the
    obvious ones, but the practical hit rate on modern data is low.
    Useful for older data and for the minority of registrants who don't
    use privacy protection.
    """
    name = "whois_registrant"
    tier = SignalTier.STRONG
    description = "WHOIS Registrant"
    module = "sfp_whois"
    patterns = [
        r"Registrant\s+Name:\s*([^\n]+)",
        r"Registrant\s+Organization:\s*([^\n]+)",
    ]
    exclude_patterns = [
        r"privacy", r"redacted", r"data protected", r"withheld",
        r"contact privacy", r"domains by proxy", r"whoisguard",
    ]


class PhoneDetector(BaseDetector):
    """Phone numbers, with stricter formatting requirements.

    Migrated from signals.py STRONG_SIGNAL_PATTERNS['phone'], then tuned
    to require explicit phone-number formatting:

    1. Parenthesized area code:    (NNN) NNN-NNNN  /  (NNN)NNN-NNNN
    2. Dash/dot/space separators:  NNN-NNN-NNNN  /  NNN.NNN.NNNN  /  NNN NNN NNNN
    3. Explicit country code:      +N NNN NNN NNNN  /  +NN NNN NNNN

    The previous regex matched any unformatted 10-digit sequence which produced
    false positives on raw page content (account numbers, IDs, ZIP+phone runs).
    The new patterns require at least one of: parens, separator, or +country
    code prefix. A bare 10-digit run no longer matches.

    Module is still sfp_phone (SpiderFoot pre-filters somewhat) but the
    stricter regex protects against the noisier sfp_spider data when
    cross-module matching happens.
    """
    name = "phone"
    tier = SignalTier.STRONG
    description = "Phone Number"
    module = "sfp_phone"
    patterns = [
        # (NNN) NNN-NNNN  /  (NNN)NNN-NNNN  /  (NNN) NNN NNNN
        r"\(\d{3}\)\s*\d{3}[-.\s]\d{4}",
        # NNN-NNN-NNNN  /  NNN.NNN.NNNN — separators required (not all-spaces)
        r"\b\d{3}[-.]\d{3}[-.]\d{4}\b",
        # +1 NNN NNN NNNN  /  +1-NNN-NNN-NNNN  /  +1.NNN.NNN.NNNN
        r"\+1[-.\s]\d{3}[-.\s]\d{3}[-.\s]\d{4}",
        # International: +CC NNNN... with at least one separator inside
        r"\+\d{1,3}[-.\s]\d{1,4}[-.\s]\d{3,8}(?:[-.\s]\d{0,8})?",
    ]
