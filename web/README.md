# PUPPETMASTER Web GUI

A cyberpunk-themed browser interface for PUPPETMASTER. Looks like the
existing Rich-based TUI (banner, neon colors, box-drawing characters,
arrow-key navigation) but adds: live system vitals via SSE, multiple-tab
views, mouse interaction, and the ability to run remotely.

This is **optional** — PUPPETMASTER's CLI works fine without the web GUI.

## Status: Phase 1 (foundation only)

The current build is the **Phase 1 foundation**:

- ✅ Cyberpunk-themed Flask skeleton
- ✅ Main menu with all 14 items rendered (faithfully matches the TUI)
- ✅ Arrow-key navigation (`↑↓`, `Tab`, `Enter`, `Esc`, vim-style `j/k`,
     direct number/letter shortcuts)
- ✅ Live system vitals via Server-Sent Events
- ✅ Help & Documentation screens fully wired up
- ✅ Launch from CLI via `[W]` main menu option
- ⏳ Other menu options: not yet wired up — they 404 for now

Phase 2-5 will add the remaining screens. See
`/home/vscode/.claude/plans/delegated-gliding-bachman.md` for the full plan.

## Two ways to run

### Mode A — Native (recommended for development and SSH-heavy use)

```bash
cd puppetmaster
python3 -m web
```

Then open <http://127.0.0.1:8080> in your browser.

This is the recommended mode for:
- Active development on your own machine
- Operations that need full host SSH access (distributed C2 over EC2)
- The user's day-to-day workflow

The web server runs in the foreground; press `Ctrl+C` to stop it.

### Mode B — From the CLI's main menu

Launch the CLI as usual and pick the new `[W]` option:

```bash
cd puppetmaster
python3 puppetmaster.py
# At the main menu, press W
```

This starts the web GUI in a **background thread** of the same Python
process and auto-opens your browser. The TUI keeps running in the same
terminal — you can use both side by side, and they share state (config,
background scan tracking, etc.) automatically.

### Mode C — Docker (Phase 5, not yet implemented)

For shared/remote deployment. Will mount `~/.ssh`, `~/.aws`, and the
`SSH_AUTH_SOCK` socket into the container so SSH-to-AWS still works. See
the plan file for details.

## Configuration

Override defaults via environment variables:

| Variable | Default | Description |
|---|---|---|
| `PUPPETMASTER_WEB_HOST` | `127.0.0.1` | Bind address. Set to `0.0.0.0` for external access (use with caution — there's no auth in Phase 1). |
| `PUPPETMASTER_WEB_PORT` | `8080` | TCP port |
| `PUPPETMASTER_WEB_DEBUG` | `0` | Set to `1` to enable Flask debug mode |
| `PUPPETMASTER_VITALS_INTERVAL` | `2.0` | Seconds between SSE vitals updates |
| `PUPPETMASTER_AUTO_OPEN` | `0` | Set to `1` to auto-open browser when starting via `python3 -m web` (CLI launcher always auto-opens) |

## Keyboard shortcuts

- `↑` / `↓` — focus previous/next menu item (also `j` / `k` vim-style)
- `Enter` / `Space` — activate the focused item
- `Tab` / `Shift+Tab` — same as arrow keys
- `Home` / `End` — first / last menu item
- `Esc` — back to previous page
- Direct shortcuts — press `1-9`, `0`, `D`, `S`, `W`, `Q` to jump to that menu item

## Architecture

The web GUI is a **thin frontend over the existing pipeline**, not a
rewrite. Every feature already exists as `pm_*.py` Python functions
thanks to the god-file refactor. The web app:

1. Imports the existing modules directly (no shell-out, no IPC)
2. Wraps long-running operations in background threads via
   `pm_background.start_background_thread()`
3. Streams progress events to the browser via Server-Sent Events
4. Renders cyberpunk-themed HTML that mirrors the Rich TUI

```
web/
├── __init__.py
├── __main__.py              # python3 -m web entry point
├── app.py                   # Flask app factory
├── config.py                # Env var configuration
├── routes/                  # One file per major menu screen
│   ├── home.py              # Main menu
│   ├── help.py              # Help & Documentation
│   └── events.py            # SSE endpoints
├── templates/               # Jinja2 HTML templates
│   ├── base.html            # Cyberpunk chrome (banner, status, body)
│   ├── menu.html            # Main menu
│   ├── help.html            # Help index
│   ├── help_overview.html
│   ├── help_signals.html
│   └── help_outputs.html
├── static/
│   ├── css/cyberpunk.css    # TUI-aesthetic theme (~300 lines)
│   └── js/
│       ├── keynav.js        # Arrow-key navigation
│       └── sse.js           # EventSource client
└── services/
    └── vitals.py            # psutil-based system vitals collector
```

## Color theme

The cyberpunk CSS palette is mapped from `puppetmaster/utils/colors.py`
(the canonical color module from the refactor). Standard ANSI codes
become hex equivalents, neon 256-color codes become CSS hex, and the
glow effects use `box-shadow` to evoke the terminal phosphor look.

## Security notes

- **Localhost-only by default.** The default `PUPPETMASTER_WEB_HOST` is
  `127.0.0.1`. To expose the GUI externally, you'd set it to `0.0.0.0`
  AND add authentication (Phase 6). Don't expose Phase 1 to the open
  internet — there's no login.
- **No CSRF protection** in Phase 1 because there are no mutating
  endpoints yet. When Phase 3 lands, mutating routes will use Flask's
  built-in CSRF tokens.
- **No file uploads** in Phase 1. When Phase 3 adds the "Load domains
  from file" screen, the upload handler will validate MIME type and
  apply the same `is_safe_path()` checks the CLI uses.
