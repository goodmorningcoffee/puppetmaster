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
    from .routes.queue import bp as queue_bp
    from .routes.config import bp as config_bp
    from .routes.results import bp as results_bp
    from .routes.scan_status import bp as scan_status_bp
    from .routes.load_domains import bp as load_domains_bp
    from .routes.delete_lists import bp as delete_lists_bp
    from .routes.scrape import bp as scrape_bp
    from .routes.analysis import bp as analysis_bp
    from .routes.wildcard import bp as wildcard_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(help_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(results_bp)
    app.register_blueprint(scan_status_bp)
    app.register_blueprint(load_domains_bp)
    app.register_blueprint(delete_lists_bp)
    app.register_blueprint(scrape_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(wildcard_bp)

    return app
