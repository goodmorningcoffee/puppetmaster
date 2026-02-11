"""
Domain Blacklist Module

Provides filtering of known platform/noise domains to reduce false positives
in sock puppet detection. Applies to both keyword scraping and Kali expansion.

Features:
- Built-in list of ~150 known platform domains
- User-customizable additions (persistent)
- Pre-filter review before processing
"""

import os
from typing import Set, Tuple, List
from pathlib import Path


# User config file for custom blacklist additions
USER_BLACKLIST_FILE = os.path.expanduser("~/.puppetmaster_blacklist.txt")


# =============================================================================
# BUILT-IN BLACKLIST (~150 domains)
# =============================================================================

PLATFORM_BLACKLIST: Set[str] = {
    # ----- HOSTING PLATFORMS -----
    "webflow.com",
    "squarespace.com",
    "wix.com",
    "wordpress.com",
    "wordpress.org",
    "blogspot.com",
    "blogger.com",
    "pages.dev",           # Cloudflare Pages
    "netlify.app",
    "netlify.com",
    "vercel.app",
    "vercel.com",
    "github.io",
    "gitlab.io",
    "herokuapp.com",
    "heroku.com",
    "weebly.com",
    "godaddy.com",
    "bluehost.com",
    "hostgator.com",
    "namecheap.com",
    "siteground.com",
    "dreamhost.com",
    "ionos.com",
    "1and1.com",
    "shopify.com",
    "myshopify.com",
    "bigcommerce.com",
    "woocommerce.com",
    "magento.com",
    "jimdo.com",
    "strikingly.com",
    "cargo.site",
    "carrd.co",
    "notion.so",
    "notion.site",
    "coda.io",
    "airtable.com",

    # ----- SOCIAL/CONTENT PLATFORMS -----
    "fandom.com",
    "wikia.com",
    "medium.com",
    "behance.net",
    "dribbble.com",
    "deviantart.com",
    "tumblr.com",
    "reddit.com",
    "pinterest.com",
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "youtube.com",
    "tiktok.com",
    "snapchat.com",
    "discord.com",
    "discord.gg",
    "twitch.tv",
    "vimeo.com",
    "dailymotion.com",
    "soundcloud.com",
    "spotify.com",
    "substack.com",
    "ghost.io",
    "hashnode.dev",
    "dev.to",
    "quora.com",
    "stackoverflow.com",
    "stackexchange.com",

    # ----- MARKETPLACES -----
    "houzz.com",
    "tradeindia.com",
    "alibaba.com",
    "aliexpress.com",
    "amazon.com",
    "amazon.co.uk",
    "amazon.de",
    "ebay.com",
    "etsy.com",
    "fiverr.com",
    "upwork.com",
    "freelancer.com",
    "toptal.com",
    "99designs.com",
    "thumbtack.com",
    "taskrabbit.com",
    "craigslist.org",
    "yelp.com",

    # ----- ENTERPRISE GIANTS -----
    "oracle.com",
    "microsoft.com",
    "google.com",
    "apple.com",
    "salesforce.com",
    "adobe.com",
    "autodesk.com",
    "nvidia.com",
    "intel.com",
    "amd.com",
    "ibm.com",
    "cisco.com",
    "vmware.com",
    "sap.com",
    "workday.com",
    "servicenow.com",
    "atlassian.com",
    "atlassian.net",
    "zoom.us",
    "slack.com",
    "dropbox.com",
    "box.com",

    # ----- NEWS/PR -----
    "prnewswire.com",
    "businesswire.com",
    "globenewswire.com",
    "newsweek.com",
    "forbes.com",
    "bloomberg.com",
    "reuters.com",
    "cnn.com",
    "bbc.com",
    "bbc.co.uk",
    "nytimes.com",
    "washingtonpost.com",
    "theguardian.com",
    "wsj.com",
    "techcrunch.com",
    "wired.com",
    "theverge.com",
    "arstechnica.com",
    "engadget.com",
    "mashable.com",
    "huffpost.com",
    "buzzfeed.com",

    # ----- DEV PLATFORMS -----
    "npm.io",
    "npmjs.com",
    "pypi.org",
    "crates.io",
    "rubygems.org",
    "packagist.org",
    "nuget.org",
    "maven.org",
    "sourceforge.net",
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "codepen.io",
    "jsfiddle.net",
    "replit.com",
    "glitch.com",
    "codesandbox.io",
    "gitbook.io",
    "readthedocs.io",
    "readthedocs.org",

    # ----- CDN/INFRASTRUCTURE -----
    "cloudfront.net",
    "cloudflare.com",
    "akamai.com",
    "akamaized.net",
    "fastly.net",
    "jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
    "bootstrapcdn.com",
    "googleapis.com",
    "gstatic.com",
    "googleusercontent.com",
    "azureedge.net",
    "azurewebsites.net",
    "amazonaws.com",
    "s3.amazonaws.com",
    "elasticbeanstalk.com",

    # ----- DIRECTORIES/REVIEWS -----
    "capterra.com",
    "g2.com",
    "g2crowd.com",
    "softwareadvice.com",
    "getapp.com",
    "crunchbase.com",
    "ycombinator.com",
    "producthunt.com",
    "alternativeto.net",
    "trustpilot.com",
    "bbb.org",
    "glassdoor.com",
    "indeed.com",
    "ziprecruiter.com",
    "monster.com",
    "careerbuilder.com",
    "angellist.com",
    "wellfound.com",

    # ----- ACADEMIC/RESEARCH -----
    "wikipedia.org",
    "wikimedia.org",
    "archive.org",
    "researchgate.net",
    "academia.edu",
    "sciencedirect.com",
    "springer.com",
    "nature.com",
    "ieee.org",
    "acm.org",
    "arxiv.org",
    "scholar.google.com",

    # ----- MISC PLATFORMS -----
    "aol.com",
    "yahoo.com",
    "msn.com",
    "bing.com",
    "duckduckgo.com",
    "wikipedia.org",
    "imdb.com",
    "tripadvisor.com",
    "booking.com",
    "airbnb.com",
    "expedia.com",
    "kayak.com",
    "zillow.com",
    "realtor.com",
    "redfin.com",
    "trulia.com",
    "homedepot.com",
    "lowes.com",
    "ikea.com",
    "wayfair.com",
    "target.com",
    "walmart.com",
    "costco.com",
    "bestbuy.com",
}


# =============================================================================
# BLACKLIST FUNCTIONS
# =============================================================================

def load_user_blacklist() -> Set[str]:
    """Load user-customized blacklist from file"""
    user_domains = set()

    if os.path.exists(USER_BLACKLIST_FILE):
        try:
            with open(USER_BLACKLIST_FILE, 'r') as f:
                for line in f:
                    line = line.strip().lower()
                    if line and not line.startswith('#'):
                        user_domains.add(line)
        except Exception:
            pass

    return user_domains


def save_user_blacklist(domains: Set[str]) -> bool:
    """Save user-customized blacklist to file"""
    try:
        with open(USER_BLACKLIST_FILE, 'w') as f:
            f.write("# PUPPETMASTER Custom Blacklist\n")
            f.write("# One domain per line\n")
            f.write("# Lines starting with # are comments\n\n")
            for domain in sorted(domains):
                f.write(f"{domain}\n")
        return True
    except Exception:
        return False


def get_full_blacklist() -> Set[str]:
    """Get combined built-in + user blacklist"""
    return PLATFORM_BLACKLIST | load_user_blacklist()


def is_blacklisted(domain: str) -> bool:
    """Check if a domain is blacklisted"""
    domain = domain.lower().strip()
    blacklist = get_full_blacklist()

    # Direct match
    if domain in blacklist:
        return True

    # Check if it's a subdomain of a blacklisted domain
    for blocked in blacklist:
        if domain.endswith('.' + blocked):
            return True

    return False


def filter_domains(domains: Set[str]) -> Tuple[Set[str], Set[str]]:
    """
    Filter domains against blacklist.

    Returns:
        Tuple of (clean_domains, blacklisted_domains)
    """
    clean = set()
    blocked = set()

    for domain in domains:
        if is_blacklisted(domain):
            blocked.add(domain)
        else:
            clean.add(domain)

    return clean, blocked


def add_to_blacklist(domain: str, persistent: bool = True) -> bool:
    """
    Add a domain to the blacklist.

    Args:
        domain: Domain to add
        persistent: If True, save to user config file

    Returns:
        True if successful
    """
    domain = domain.lower().strip()

    if persistent:
        user_domains = load_user_blacklist()
        user_domains.add(domain)
        return save_user_blacklist(user_domains)

    return True


def remove_from_blacklist(domain: str) -> bool:
    """
    Remove a domain from user blacklist.

    Note: Cannot remove built-in domains, only user-added ones.

    Returns:
        True if successful, False if not found or is built-in
    """
    domain = domain.lower().strip()

    if domain in PLATFORM_BLACKLIST:
        return False  # Can't remove built-in

    user_domains = load_user_blacklist()
    if domain in user_domains:
        user_domains.remove(domain)
        return save_user_blacklist(user_domains)

    return False


def get_blacklist_stats() -> dict:
    """Get blacklist statistics"""
    user_domains = load_user_blacklist()

    return {
        'builtin_count': len(PLATFORM_BLACKLIST),
        'user_count': len(user_domains),
        'total_count': len(PLATFORM_BLACKLIST | user_domains),
        'user_domains': sorted(user_domains),
        'builtin_categories': {
            'hosting': len([d for d in PLATFORM_BLACKLIST if any(x in d for x in ['host', 'cloud', 'app', 'io'])]),
            'social': len([d for d in PLATFORM_BLACKLIST if any(x in d for x in ['facebook', 'twitter', 'instagram', 'linkedin', 'reddit'])]),
            'enterprise': len([d for d in PLATFORM_BLACKLIST if any(x in d for x in ['microsoft', 'google', 'apple', 'oracle', 'adobe'])]),
        }
    }


def reset_user_blacklist() -> bool:
    """Reset user blacklist to empty (keeps built-in)"""
    try:
        if os.path.exists(USER_BLACKLIST_FILE):
            os.remove(USER_BLACKLIST_FILE)
        return True
    except Exception:
        return False


def export_blacklist(filepath: str) -> bool:
    """Export full blacklist to file"""
    try:
        blacklist = get_full_blacklist()
        with open(filepath, 'w') as f:
            f.write("# PUPPETMASTER Domain Blacklist Export\n")
            f.write(f"# Total domains: {len(blacklist)}\n\n")
            for domain in sorted(blacklist):
                f.write(f"{domain}\n")
        return True
    except Exception:
        return False


def import_blacklist(filepath: str) -> Tuple[int, int]:
    """
    Import blacklist from file (adds to user blacklist).

    Returns:
        Tuple of (added_count, skipped_count)
    """
    added = 0
    skipped = 0

    try:
        with open(filepath, 'r') as f:
            user_domains = load_user_blacklist()
            existing = get_full_blacklist()

            for line in f:
                line = line.strip().lower()
                if line and not line.startswith('#'):
                    if line not in existing:
                        user_domains.add(line)
                        added += 1
                    else:
                        skipped += 1

            save_user_blacklist(user_domains)

    except Exception:
        pass

    return added, skipped


# =============================================================================
# CLI DISPLAY HELPERS
# =============================================================================

def format_blacklist_summary(blocked_domains: Set[str], max_display: int = 5) -> str:
    """Format a summary of blocked domains for display"""
    if not blocked_domains:
        return "  No domains blacklisted"

    lines = []
    sorted_blocked = sorted(blocked_domains)

    displayed = sorted_blocked[:max_display]
    remaining = len(sorted_blocked) - max_display

    lines.append(f"  Blacklisted: {', '.join(displayed)}")
    if remaining > 0:
        lines.append(f"               ... and {remaining} more")

    return "\n".join(lines)


# Quick test
if __name__ == '__main__':
    print(f"Built-in blacklist: {len(PLATFORM_BLACKLIST)} domains")
    print(f"User blacklist file: {USER_BLACKLIST_FILE}")

    stats = get_blacklist_stats()
    print(f"\nStats: {stats}")

    # Test filtering
    test_domains = {"example.com", "webflow.com", "mysite.blogspot.com", "target.com"}
    clean, blocked = filter_domains(test_domains)
    print(f"\nTest filter:")
    print(f"  Input: {test_domains}")
    print(f"  Clean: {clean}")
    print(f"  Blocked: {blocked}")
