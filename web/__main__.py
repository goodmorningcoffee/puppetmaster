"""
__main__.py - Standalone module-mode entry point.

Run the web GUI directly as a module from the puppetmaster/ directory:

    cd puppetmaster
    python3 -m web

This binds to localhost:8080 by default. Override via environment variables:

    PUPPETMASTER_WEB_HOST=0.0.0.0  # external access (use with caution!)
    PUPPETMASTER_WEB_PORT=9090
    PUPPETMASTER_WEB_DEBUG=1       # Flask debug mode
    PUPPETMASTER_AUTO_OPEN=1       # auto-open browser on startup

For in-process launch from the CLI, use puppetmaster.py [W] instead.
"""

import sys
import webbrowser

from .app import create_app
from .config import WebConfig


def main():
    """Entry point when run as `python3 -m puppetmaster.web`."""
    app = create_app()

    url = f"http://{WebConfig.HOST}:{WebConfig.PORT}"
    print()
    print("=" * 60)
    print("  PUPPETMASTER Web GUI")
    print("=" * 60)
    print(f"  URL:    {url}")
    print(f"  Mode:   {'DEBUG' if WebConfig.DEBUG else 'production'}")
    print(f"  Host:   {WebConfig.HOST}")
    print(f"  Port:   {WebConfig.PORT}")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 60)
    print()

    if WebConfig.AUTO_OPEN_BROWSER:
        try:
            webbrowser.open(url)
        except Exception:
            pass  # Headless server: nothing to open

    try:
        app.run(
            host=WebConfig.HOST,
            port=WebConfig.PORT,
            debug=WebConfig.DEBUG,
            use_reloader=False,  # Don't double-start on file changes
        )
    except KeyboardInterrupt:
        print("\n  Web GUI stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
