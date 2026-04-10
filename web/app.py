"""
app.py - Flask app factory.

Creates and configures the Flask app. Registers all route blueprints.
Designed to be called from either:
  - `python3 -m puppetmaster.web` (standalone module mode)
  - puppetmaster.py [W] menu option (in-process from the CLI)
"""

from flask import Flask

from .config import WebConfig


def create_app(config_class=WebConfig):
    """Create and configure the Flask app instance.

    Args:
        config_class: Configuration class (default: WebConfig).

    Returns:
        Configured Flask app ready to run.
    """
    # __name__ here is "puppetmaster.web.app" — Flask uses this to find
    # the templates/ and static/ directories relative to the package.
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_class)

    # Register blueprints
    # Import here (not at module top) to avoid circular import issues
    # if any route module ends up importing back from app.py
    from .routes.home import bp as home_bp
    from .routes.help import bp as help_bp
    from .routes.events import bp as events_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(help_bp)
    app.register_blueprint(events_bp)

    return app
