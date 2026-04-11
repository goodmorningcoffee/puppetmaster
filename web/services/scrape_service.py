"""
scrape_service.py - Background scraper for the web GUI Scrape screen.

Wraps discovery.scraper.DomainScraper with the run_state pattern. The
scraper is callback-based for progress, so wiring it up is straightforward:

  1. POST /menu/scrape/run creates a run via run_state.create_run('scrape')
  2. The route kicks off start_scrape_in_background() which spawns a thread
  3. The thread calls DomainScraper.search_all() with a callback that
     emits run_state events
  4. On completion, the discovered domains are stashed on the run.result
  5. /events/run/<run_id> SSE streams events to the browser
  6. The browser polls /menu/scrape/result/<run_id> to get the final list

The scraper imports are deferred so importing this module doesn't pull in
the (sometimes flaky) googlesearch and ddgs HTTP libraries.
"""

import threading
from typing import List, Optional

from . import run_state


# Defer the heavy import — DomainScraper pulls in googlesearch / ddgs
def _get_scraper_class():
    """Return the DomainScraper class, or None if discovery.scraper is missing."""
    try:
        from discovery.scraper import DomainScraper
        return DomainScraper
    except ImportError:
        return None


def start_scrape_in_background(
    keywords: List[str],
    max_results_per_keyword: int = 50,
    use_google: bool = True,
    use_duckduckgo: bool = True,
) -> str:
    """
    Start a domain scrape in a background thread.

    Returns a run_id that the caller uses to poll progress (via
    /events/run/<run_id>) and fetch the final result.

    Args:
        keywords: List of search terms (already split/stripped by the caller)
        max_results_per_keyword: Cap on results per keyword per engine
        use_google: Search Google?
        use_duckduckgo: Search DuckDuckGo?
    """
    run_id = run_state.create_run('scrape')

    DomainScraper = _get_scraper_class()
    if DomainScraper is None:
        run_state.mark_failed(
            run_id,
            "discovery.scraper module not importable. Install googlesearch-python and ddgs.",
        )
        return run_id

    if not keywords:
        run_state.mark_failed(run_id, "No keywords provided.")
        return run_id
    if not (use_google or use_duckduckgo):
        run_state.mark_failed(run_id, "Must enable at least one search engine.")
        return run_id

    def _runner():
        run_state.append_event(
            run_id, 'info',
            f'Starting scrape: {len(keywords)} keyword(s), '
            f'max {max_results_per_keyword} per engine, '
            f'google={use_google}, ddg={use_duckduckgo}',
            stage='Initializing',
        )

        try:
            scraper = DomainScraper()

            def on_progress(keyword: str, current: int, total: int):
                """Called by DomainScraper for each keyword's progress."""
                run_state.append_event(
                    run_id,
                    'progress',
                    f'{keyword}: {current}/{total}',
                    keyword=keyword,
                    current=current,
                    total=total,
                )

            run_state.append_event(run_id, 'stage', 'Searching...', stage='Searching')
            domains = scraper.search_all(
                keywords=keywords,
                max_results_per_keyword=max_results_per_keyword,
                use_google=use_google,
                use_duckduckgo=use_duckduckgo,
                progress_callback=on_progress,
            )

            domains_list = sorted(domains)
            errors = list(scraper.errors)

            run_state.append_event(
                run_id,
                'success',
                f'Found {len(domains_list)} unique domain(s).',
                stage='Done',
                domain_count=len(domains_list),
            )

            if errors:
                for err in errors:
                    run_state.append_event(run_id, 'warning', err)

            run_state.mark_complete(run_id, {
                'domains': domains_list,
                'count': len(domains_list),
                'keywords': keywords,
                'errors': errors,
            })

        except Exception as e:
            run_state.append_event(run_id, 'error', f'Scrape failed: {e}')
            run_state.mark_failed(run_id, str(e))

    thread = threading.Thread(
        target=_runner,
        name=f"web-scrape-{run_id}",
        daemon=True,
    )
    thread.start()

    return run_id
