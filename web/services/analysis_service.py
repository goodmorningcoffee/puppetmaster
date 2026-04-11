"""
analysis_service.py - Background runner for the Run Puppet Analysis screen.

Wraps core.pipeline.run_full_pipeline() with the run_state pattern.
The pipeline now accepts a progress_callback parameter (added in this
commit) — we hook that into run_state.append_event() to stream stage
events to the browser via SSE.

The pipeline is heavy (loads SpiderFoot CSV exports, extracts signals,
builds graphs, generates reports). Caller MUST go through
start_analysis_in_background() — never block the request thread.
"""

import os
import threading
from pathlib import Path
from typing import Optional

from . import run_state


# Defer the heavy import — core.pipeline pulls in networkx, scipy, etc.
def _get_run_pipeline():
    """Return the run_full_pipeline function, or None if it's not importable."""
    try:
        from core.pipeline import run_full_pipeline
        return run_full_pipeline
    except ImportError:
        return None


# Mapping from pipeline stage tags to friendly progress messages
_STAGE_LABELS = {
    "start":    ("stage", "Starting pipeline"),
    "ingest":   ("stage", "📥 Stage 1: Loading SpiderFoot CSV exports"),
    "signals":  ("stage", "🔬 Stage 2: Extracting signals"),
    "network":  ("stage", "🕸️ Stage 3: Building connection network"),
    "clusters": ("stage", "🔍 Stage 4: Detecting domain clusters"),
    "hubs":     ("stage", "🎯 Stage 5: Identifying hub domains"),
    "reports":  ("stage", "📝 Stage 6: Generating reports"),
    "complete": ("success", "✓ Pipeline complete"),
    "error":    ("error", "Pipeline failed"),
}


def start_analysis_in_background(
    input_dir: str,
    output_dir: str,
    kali_infra_dir: Optional[str] = None,
) -> str:
    """
    Start the full pipeline in a background thread.

    Returns a run_id that the caller uses to poll progress (via
    /events/run/<run_id>) and link to the result page.

    Args:
        input_dir: Directory containing SpiderFoot CSV exports
        output_dir: Where to write reports (will be created if missing)
        kali_infra_dir: Optional Kali infra analysis dir to merge

    Returns:
        run_id (string)
    """
    run_id = run_state.create_run('analysis')

    run_full_pipeline = _get_run_pipeline()
    if run_full_pipeline is None:
        run_state.mark_failed(
            run_id,
            "core.pipeline not importable. Required dependencies missing (networkx, scipy, etc.)",
        )
        return run_id

    # Validate input directory
    if not input_dir:
        run_state.mark_failed(run_id, "input directory is required")
        return run_id
    if not os.path.isdir(input_dir):
        run_state.mark_failed(run_id, f"input directory does not exist: {input_dir}")
        return run_id

    # Validate / create output directory
    if not output_dir:
        run_state.mark_failed(run_id, "output directory is required")
        return run_id

    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        run_state.mark_failed(run_id, f"failed to create output directory: {e}")
        return run_id

    # Stash the output directory basename on the run so the result page
    # can link to /menu/results/<basename>
    output_basename = Path(output_dir).name

    def _runner():
        run_state.append_event(
            run_id, 'info',
            f'Analysis starting: {input_dir} → {output_dir}',
            stage='Initializing',
            input_dir=input_dir,
            output_dir=output_dir,
        )

        def on_progress(stage: str, message: str):
            """Bridge from core.pipeline._emit() into run_state events."""
            level, prefix = _STAGE_LABELS.get(stage, ('info', stage))
            # Use the prefix label if it's more descriptive than the raw message
            run_state.append_event(
                run_id,
                level,
                message or prefix,
                stage=stage,
            )

        try:
            success = run_full_pipeline(
                input_dir=input_dir,
                output_dir=output_dir,
                show_progress=False,        # don't print tqdm bars to web server stdout
                kali_infra_dir=kali_infra_dir,
                progress_callback=on_progress,
            )

            if success:
                run_state.mark_complete(run_id, {
                    'input_dir': input_dir,
                    'output_dir': output_dir,
                    'output_basename': output_basename,
                })
            else:
                run_state.mark_failed(
                    run_id,
                    "Pipeline returned False — check server logs for details.",
                )

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            run_state.append_event(run_id, 'error', f'Exception: {e}')
            run_state.append_event(run_id, 'error', tb[:500])
            run_state.mark_failed(run_id, str(e))

    thread = threading.Thread(
        target=_runner,
        name=f"web-analysis-{run_id}",
        daemon=True,
    )
    thread.start()

    return run_id
