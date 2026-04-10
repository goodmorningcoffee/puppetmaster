"""
web — Cyberpunk-themed web GUI for PUPPETMASTER.

This package is OPTIONAL — PUPPETMASTER's CLI works without it. The web
GUI provides a browser-based interface that looks like the existing TUI
(banner, neon colors, box-drawing characters, arrow-key navigation) but
adds: live system vitals, multiple-tab views, remote access, mouse
interaction, and rich data visualization.

Two ways to run:

  Native (recommended for development and SSH-heavy use):
      cd puppetmaster
      python3 -m web

  From the TUI:
      cd puppetmaster
      python3 puppetmaster.py
      Then select [W] Launch Web GUI from the main menu

  Docker (Phase 5):
      docker compose up

The web GUI directly imports the existing pm_*.py modules — same code
paths the CLI uses. There is no shell-out, no IPC, no separate database.
"""

__version__ = "0.1.0"
