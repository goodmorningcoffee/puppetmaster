"""
routes/ - Flask route blueprints, one file per major menu screen.

Each module exports a `bp` (Blueprint) that gets registered in app.py.
Routes are thin wrappers that call into web/services/* and render
templates from web/templates/*.
"""
