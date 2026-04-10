"""
pm_web_launcher.py - In-process launcher for the web GUI from the CLI.

When the user picks [W] from the main TUI menu, this module starts the
Flask app in a background thread and opens the user's browser. The TUI
keeps running in the same terminal — no process replacement, no fork.

Both layers share the same Python process, which means they share state
(config, background scan tracking, etc.) automatically. Hot-reloading
edits to web/ files requires a restart.
"""

import threading
import time
import webbrowser

from pm_ui_helpers import print_success, print_info, print_error


# Module-level flag to prevent double-starts
_server_thread = None
_server_started = False


def launch_web_gui(host="127.0.0.1", port=8080, auto_open=True):
    """
    Start the web GUI in a background thread and optionally open the browser.

    Idempotent: if the server is already running, just opens a new tab.

    Args:
        host: Bind address (default: 127.0.0.1, localhost only)
        port: TCP port (default: 8080)
        auto_open: Whether to open the system browser to the GUI URL
    """
    global _server_thread, _server_started

    url = f"http://{host}:{port}"

    if _server_started:
        print_info(f"Web GUI already running at {url}")
        if auto_open:
            try:
                webbrowser.open(url)
            except Exception:
                pass  # Headless or no display
        return

    try:
        from web.app import create_app
    except ImportError as e:
        print_error(f"Web GUI module not importable: {e}")
        print_info("Install Flask first: pip install flask")
        raise

    app = create_app()
    print_info(f"Starting Web GUI on {url}...")

    def _run_server():
        # use_reloader=False prevents Flask from spawning a child process,
        # which would break in-process state sharing with the TUI
        app.run(
            host=host,
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,  # multiple browser tabs work concurrently
        )

    _server_thread = threading.Thread(
        target=_run_server,
        name="puppetmaster-web-gui",
        daemon=True,  # dies with the parent process when TUI exits
    )
    _server_thread.start()
    _server_started = True

    # Give Flask a moment to bind before opening browser
    time.sleep(0.8)
    print_success(f"Web GUI is running at {url}")
    print_info("The TUI is still active in this terminal — use both side by side.")
    print_info("Press Enter to return to the main menu (Web GUI keeps running).")

    if auto_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    # Wait for user to acknowledge before returning to menu
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass
