#!/usr/bin/env python3
"""
discovery/ - Domain Discovery and SpiderFoot Scanning Module

This module handles:
1. Scraping domains from search engines (Google, DuckDuckGo)
2. Loading domains from user-provided files
3. Running batch SpiderFoot scans with job queue
4. Tracking scan progress and status
"""

from .scraper import DomainScraper
from .scanner import SpiderFootScanner
from .jobs import JobTracker, ScanJob

__all__ = ['DomainScraper', 'SpiderFootScanner', 'JobTracker', 'ScanJob']
