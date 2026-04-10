"""
services/ - Backend logic that wraps the existing pm_*.py modules.

The services layer mediates between the HTTP routes and the underlying
pipeline. Long-running operations are dispatched to background threads
via pm_background.start_background_thread() and progress is exposed via
SSE event streams.
"""
