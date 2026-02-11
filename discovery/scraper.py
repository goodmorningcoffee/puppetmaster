#!/usr/bin/env python3
"""
scraper.py - Domain Discovery via Search Engines

Scrapes Google and DuckDuckGo to find domains related to keywords.
No API keys required - uses safe/slow mode with delays to avoid blocking.
"""

import os
import time
import random
import re
from typing import List, Set, Optional, Callable
from urllib.parse import urlparse
import tldextract


def validate_file_path(filepath: str) -> Optional[str]:
    """
    Validate and sanitize a file path to prevent path traversal attacks.

    Args:
        filepath: The file path to validate

    Returns:
        Sanitized absolute path, or None if invalid/dangerous
    """
    if not filepath:
        return None

    filepath = filepath.strip()

    # Expand user home directory (~)
    filepath = os.path.expanduser(filepath)

    # Normalize and get absolute path
    filepath = os.path.abspath(os.path.normpath(filepath))

    # Block path traversal attempts
    if '..' in filepath:
        return None

    # Block access to sensitive system directories
    sensitive_paths = ['/etc/', '/usr/', '/bin/', '/sbin/', '/var/', '/root/']
    for sensitive in sensitive_paths:
        if filepath.startswith(sensitive):
            return None

    return filepath

# Try to import search libraries
try:
    from googlesearch import search as google_search
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

try:
    # Try new package name first
    from ddgs import DDGS
    HAS_DUCKDUCKGO = True
except ImportError:
    try:
        # Fall back to old package name
        from duckduckgo_search import DDGS
        HAS_DUCKDUCKGO = True
    except ImportError:
        HAS_DUCKDUCKGO = False


# =============================================================================
# DOMAIN FILTERING
# =============================================================================

# Common domains to exclude (not targets, just infrastructure/big sites)
EXCLUDED_DOMAINS = {
    # Search engines
    'google.com', 'bing.com', 'yahoo.com', 'duckduckgo.com', 'baidu.com',
    'yandex.com', 'ask.com',

    # Social media
    'facebook.com', 'twitter.com', 'x.com', 'instagram.com', 'linkedin.com',
    'pinterest.com', 'reddit.com', 'tiktok.com', 'youtube.com', 'tumblr.com',

    # Big tech
    'amazon.com', 'apple.com', 'microsoft.com', 'github.com', 'gitlab.com',
    'wikipedia.org', 'wikimedia.org',

    # Common utilities
    'cloudflare.com', 'amazonaws.com', 'googleusercontent.com', 'gstatic.com',
    'cdnjs.com', 'jsdelivr.net', 'unpkg.com',

    # News/media (usually not targets)
    'cnn.com', 'bbc.com', 'nytimes.com', 'washingtonpost.com', 'forbes.com',
    'medium.com', 'wordpress.com', 'blogger.com', 'wix.com', 'squarespace.com',

    # Business directories (too generic)
    'yelp.com', 'yellowpages.com', 'bbb.org', 'glassdoor.com', 'indeed.com',
    'craigslist.org',
}

# TLDs that are usually not interesting
EXCLUDED_TLDS = {
    'gov', 'edu', 'mil',  # Government/education
}


def extract_domain(url: str) -> Optional[str]:
    """
    Extract the root domain from a URL.

    Examples:
        https://www.example.com/path -> example.com
        http://subdomain.example.co.uk/page -> example.co.uk
    """
    try:
        # Handle cases where URL might not have protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        extracted = tldextract.extract(url)

        if extracted.domain and extracted.suffix:
            return f"{extracted.domain}.{extracted.suffix}".lower()
        return None
    except Exception:
        return None


def is_valid_target(domain: str) -> bool:
    """Check if a domain is a valid target (not excluded)."""
    if not domain:
        return False

    # Check against excluded domains
    if domain.lower() in EXCLUDED_DOMAINS:
        return False

    # Check TLD
    extracted = tldextract.extract(domain)
    if extracted.suffix in EXCLUDED_TLDS:
        return False

    # Basic format validation
    if len(domain) < 4 or '.' not in domain:
        return False

    return True


# =============================================================================
# DOMAIN SCRAPER CLASS
# =============================================================================

class DomainScraper:
    """
    Scrapes domains from search engines based on keywords.

    Supports Google and DuckDuckGo without requiring API keys.
    Uses safe/slow mode with random delays to avoid rate limiting.
    """

    def __init__(self, delay_range: tuple = (2, 4)):
        """
        Initialize the scraper.

        Args:
            delay_range: (min, max) seconds to wait between requests
        """
        self.delay_range = delay_range
        self.domains: Set[str] = set()
        self.errors: List[str] = []

    def _delay(self):
        """Random delay between requests to avoid rate limiting."""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)

    def search_google(
        self,
        keyword: str,
        max_results: int = 50,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Set[str]:
        """
        Search Google for domains related to a keyword.

        Args:
            keyword: Search term
            max_results: Maximum number of results to fetch
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Set of unique domains found
        """
        if not HAS_GOOGLE:
            self.errors.append("googlesearch-python not installed. Run: pip install googlesearch-python")
            return set()

        found = set()

        try:
            # Google search with safe delays
            results = google_search(
                keyword,
                num_results=max_results,
                sleep_interval=self.delay_range[0]  # Minimum delay
            )

            count = 0
            for url in results:
                domain = extract_domain(url)
                if domain and is_valid_target(domain):
                    found.add(domain)

                count += 1
                if progress_callback:
                    progress_callback(count, max_results)

        except Exception as e:
            self.errors.append(f"Google search error for '{keyword}': {str(e)}")

        return found

    def search_duckduckgo(
        self,
        keyword: str,
        max_results: int = 50,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Set[str]:
        """
        Search DuckDuckGo for domains related to a keyword.

        Args:
            keyword: Search term
            max_results: Maximum number of results to fetch
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Set of unique domains found
        """
        if not HAS_DUCKDUCKGO:
            self.errors.append("duckduckgo_search not installed. Run: pip install duckduckgo_search")
            return set()

        found = set()

        try:
            # Try different API styles (package has changed over time)
            try:
                ddgs = DDGS()
                results = list(ddgs.text(keyword, max_results=max_results))
            except TypeError:
                # Older API style
                with DDGS() as ddgs:
                    results = list(ddgs.text(keyword, max_results=max_results))

            for i, result in enumerate(results):
                # Check multiple possible URL keys (API has changed)
                url = (result.get('href') or
                       result.get('link') or
                       result.get('url') or
                       result.get('body', ''))  # Sometimes URL is in body

                domain = extract_domain(url)
                if domain and is_valid_target(domain):
                    found.add(domain)

                if progress_callback:
                    progress_callback(i + 1, len(results))

        except Exception as e:
            self.errors.append(f"DuckDuckGo search error for '{keyword}': {str(e)}")

        return found

    def search_all(
        self,
        keywords: List[str],
        max_results_per_keyword: int = 50,
        use_google: bool = True,
        use_duckduckgo: bool = True,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Set[str]:
        """
        Search multiple keywords across search engines.

        Args:
            keywords: List of search terms
            max_results_per_keyword: Max results per keyword per engine
            use_google: Whether to search Google
            use_duckduckgo: Whether to search DuckDuckGo
            progress_callback: Optional callback(keyword, current, total) for progress

        Returns:
            Set of all unique domains found
        """
        all_domains = set()
        total_keywords = len(keywords)

        for i, keyword in enumerate(keywords):
            keyword = keyword.strip()
            if not keyword:
                continue

            if progress_callback:
                progress_callback(keyword, i + 1, total_keywords)

            # Search Google
            if use_google and HAS_GOOGLE:
                google_results = self.search_google(keyword, max_results_per_keyword)
                all_domains.update(google_results)
                self._delay()

            # Search DuckDuckGo
            if use_duckduckgo and HAS_DUCKDUCKGO:
                ddg_results = self.search_duckduckgo(keyword, max_results_per_keyword)
                all_domains.update(ddg_results)
                self._delay()

        self.domains = all_domains
        return all_domains

    def load_from_file(self, filepath: str) -> "tuple[Set[str], List[str]]":
        """
        Load domains from a text file.

        Args:
            filepath: Path to text file with one domain per line

        Returns:
            Tuple of (valid_domains, invalid_lines)
        """
        valid = set()
        invalid = []

        # Validate file path to prevent path traversal
        safe_path = validate_file_path(filepath)
        if safe_path is None:
            self.errors.append(f"Invalid or unsafe file path: {filepath}")
            return valid, invalid

        try:
            with open(safe_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Try to extract domain
                    domain = extract_domain(line)

                    if domain:
                        if is_valid_target(domain):
                            valid.add(domain)
                        else:
                            invalid.append((line_num, line, "excluded domain"))
                    else:
                        invalid.append((line_num, line, "invalid format"))

        except FileNotFoundError:
            self.errors.append(f"File not found: {filepath}")
        except Exception as e:
            self.errors.append(f"Error reading file: {str(e)}")

        self.domains.update(valid)
        return valid, invalid

    def save_to_file(self, filepath: str, domains: Optional[Set[str]] = None) -> bool:
        """
        Save domains to a text file.

        Args:
            filepath: Output file path
            domains: Domains to save (uses self.domains if not provided)

        Returns:
            True if successful
        """
        domains = domains or self.domains

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for domain in sorted(domains):
                    f.write(domain + '\n')
            return True
        except Exception as e:
            self.errors.append(f"Error saving file: {str(e)}")
            return False

    def get_stats(self) -> dict:
        """Get scraping statistics."""
        return {
            'total_domains': len(self.domains),
            'errors': len(self.errors),
            'has_google': HAS_GOOGLE,
            'has_duckduckgo': HAS_DUCKDUCKGO,
        }

    @staticmethod
    def check_dependencies() -> dict:
        """Check which search libraries are available."""
        return {
            'google': HAS_GOOGLE,
            'duckduckgo': HAS_DUCKDUCKGO,
            'missing': [
                pkg for pkg, available in [
                    ('googlesearch-python', HAS_GOOGLE),
                    ('duckduckgo_search', HAS_DUCKDUCKGO)
                ] if not available
            ]
        }
