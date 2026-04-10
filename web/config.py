"""
config.py - Web GUI configuration.

Centralizes runtime configuration for the Flask app. Values can be
overridden via environment variables for Docker deployment.
"""

import os


class WebConfig:
    """Web GUI runtime configuration."""

    # Flask app config
    SECRET_KEY = os.environ.get("PUPPETMASTER_WEB_SECRET", "dev-only-not-secure")
    DEBUG = os.environ.get("PUPPETMASTER_WEB_DEBUG", "0") == "1"

    # Server bind address
    # Default: localhost only (no external access). Set to 0.0.0.0 for
    # Docker or remote access — but at that point you should add auth.
    HOST = os.environ.get("PUPPETMASTER_WEB_HOST", "127.0.0.1")
    PORT = int(os.environ.get("PUPPETMASTER_WEB_PORT", "8080"))

    # SSE vitals stream interval (seconds)
    VITALS_INTERVAL = float(os.environ.get("PUPPETMASTER_VITALS_INTERVAL", "2.0"))

    # Whether to auto-open browser when running standalone module mode
    # CLI launcher (puppetmaster.py [W]) always auto-opens regardless of this.
    AUTO_OPEN_BROWSER = os.environ.get("PUPPETMASTER_AUTO_OPEN", "0") == "1"
