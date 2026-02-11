#!/usr/bin/env python3
"""
pipeline.py - Main Pipeline Orchestration

Runs the complete sock puppet detection pipeline:
1. Ingest SpiderFoot data
2. Extract and classify signals
3. Build network and detect clusters
4. Identify hubs
5. Generate reports
"""

import time
import random
from pathlib import Path
from typing import Optional

from .ingest import load_all_exports
from .signals import SignalExtractor
from .network import NetworkAnalyzer
from .report import generate_all_reports

# Import fun display utilities
try:
    from utils.display import (
        C, FunSpinner, print_stage_header, print_stage_complete,
        print_section, print_info, print_success, print_error,
        fun_progress_bar, animated_loading, random_hunting_message,
        celebrate, LOADING_ANIMATIONS
    )
    HAS_FUN_DISPLAY = True
except ImportError:
    HAS_FUN_DISPLAY = False
    # Fallback simple colors
    class C:
        RESET = BOLD = GREEN = YELLOW = CYAN = BRIGHT_CYAN = ''
        BRIGHT_GREEN = BRIGHT_MAGENTA = BRIGHT_YELLOW = ''

# Fun progress messages (fallback if utils not available)
PROGRESS_MESSAGES = [
    "🔍 Searching for puppet strings...",
    "🕵️ Analyzing digital fingerprints...",
    "🎭 Unmasking hidden connections...",
    "🕸️ Mapping the web of deceit...",
    "🔗 Following the money... I mean, data...",
    "🎯 Locking onto targets...",
    "🔬 Running forensic analysis...",
    "🌐 Tracing network patterns...",
    "💡 Connecting the dots...",
    "🔐 Decrypting relationships...",
]


def run_full_pipeline(
    input_dir: str,
    output_dir: str,
    show_progress: bool = True
) -> bool:
    """
    Run the complete sock puppet detection pipeline.

    Args:
        input_dir: Directory containing SpiderFoot CSV exports
        output_dir: Directory to save results
        show_progress: Whether to show progress bars

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        start_time = time.time()
        input_path = Path(input_dir)
        output_path = Path(output_dir)

        total_stages = 6

        # Opening animation
        if HAS_FUN_DISPLAY:
            print_section("PUPPETMASTER ANALYSIS PIPELINE")
            animation_style = random.choice(['spider', 'puppet', 'worm', 'fish'])
            animated_loading(random_hunting_message(), duration=1.5, animation=animation_style)
        else:
            print("\n" + "=" * 70)
            print("  PUPPETMASTER ANALYSIS PIPELINE")
            print("=" * 70)

        # =====================================================================
        # STAGE 1: Data Ingestion
        # =====================================================================
        if HAS_FUN_DISPLAY:
            print_stage_header(1, total_stages, "Loading SpiderFoot Data")
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n📥 STAGE 1: Loading SpiderFoot Data")
            print("-" * 50)

        if HAS_FUN_DISPLAY:
            # above_progress=True puts spinner on line above tqdm progress bar
            spinner = FunSpinner("Reading CSV files", style='detective', above_progress=True)
            spinner.start()

        data = load_all_exports(input_path, show_progress=show_progress)

        if HAS_FUN_DISPLAY:
            spinner.stop(f"Loaded {len(data['domains'])} domains from {data['total_rows']:,} records")

        data_summary = {
            'domains': len(data['domains']),
            'total_rows': data['total_rows'],
            'modules': len(data['rows_by_module'])
        }

        # =====================================================================
        # STAGE 2: Signal Extraction
        # =====================================================================
        if HAS_FUN_DISPLAY:
            print_stage_header(2, total_stages, "Extracting Signals")
            # above_progress=True for tqdm compatibility
            spinner = FunSpinner("Analyzing digital fingerprints", style='dots', above_progress=True)
            spinner.start()
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n🔬 STAGE 2: Extracting Signals")
            print("-" * 50)

        extractor = SignalExtractor()
        signals = extractor.extract_all_signals(data, show_progress=show_progress)

        if HAS_FUN_DISPLAY:
            spinner.stop(f"Extracted {len(signals)} signals")

        # =====================================================================
        # STAGE 3: Network Analysis
        # =====================================================================
        if HAS_FUN_DISPLAY:
            print_stage_header(3, total_stages, "Building Connection Network")
            # above_progress=True for tqdm compatibility
            spinner = FunSpinner("Mapping the web of deceit", style='spider', above_progress=True)
            spinner.start()
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n🕸️ STAGE 3: Building Connection Network")
            print("-" * 50)

        analyzer = NetworkAnalyzer()
        analyzer.build_network(signals, show_progress=show_progress)

        if HAS_FUN_DISPLAY:
            edges = analyzer.graph.number_of_edges() if hasattr(analyzer, 'graph') else 0
            spinner.stop(f"Built network with {edges} connections")

        # =====================================================================
        # STAGE 4: Cluster Detection
        # =====================================================================
        if HAS_FUN_DISPLAY:
            print_stage_header(4, total_stages, "Detecting Domain Clusters")
            spinner = FunSpinner("Finding sock puppet networks", style='puppet')
            spinner.start()
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n🔍 STAGE 4: Detecting Domain Clusters")
            print("-" * 50)

        clusters = analyzer.detect_clusters(min_size=2)

        if HAS_FUN_DISPLAY:
            high_conf = sum(1 for c in clusters if c.confidence == "HIGH")
            spinner.stop(f"Found {len(clusters)} clusters ({high_conf} high-confidence)")

        # =====================================================================
        # STAGE 5: Hub Identification
        # =====================================================================
        if HAS_FUN_DISPLAY:
            print_stage_header(5, total_stages, "Identifying Hub Domains")
            spinner = FunSpinner("Zeroing in on puppet masters", style='runner')
            spinner.start()
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n🎯 STAGE 5: Identifying Hub Domains")
            print("-" * 50)

        hubs = analyzer.identify_hubs(top_n=30)

        if HAS_FUN_DISPLAY:
            potential_c2 = sum(1 for h in hubs if h.is_potential_c2)
            spinner.stop(f"Identified {len(hubs)} hubs ({potential_c2} potential C2)")

        # =====================================================================
        # STAGE 6: Report Generation
        # =====================================================================
        if HAS_FUN_DISPLAY:
            print_stage_header(6, total_stages, "Generating Reports")
            spinner = FunSpinner("Writing analysis reports", style='moon')
            spinner.start()
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n📝 STAGE 6: Generating Reports")
            print("-" * 50)

        generate_all_reports(
            output_dir=output_path,
            signals=signals,
            analyzer=analyzer,
            hubs=hubs,
            data_summary=data_summary
        )

        # Export graph for external visualization
        graph_path = output_path / "network.graphml"
        analyzer.export_graph(str(graph_path))

        if HAS_FUN_DISPLAY:
            spinner.stop("Reports generated successfully")

        # =====================================================================
        # COMPLETION SUMMARY
        # =====================================================================
        elapsed = time.time() - start_time

        # Summary stats
        confirmed = len(analyzer.get_confirmed_connections())
        likely = len(analyzer.get_likely_connections())
        high_conf_clusters = sum(1 for c in clusters if c.confidence == "HIGH")
        potential_c2 = sum(1 for h in hubs if h.is_potential_c2)

        if HAS_FUN_DISPLAY:
            print()
            celebrate("ANALYSIS COMPLETE!")

            print(f"""
{C.BRIGHT_GREEN}{'═' * 60}{C.RESET}

{C.BOLD}📊 RESULTS SUMMARY:{C.RESET}

   {C.CYAN}Domains Analyzed:{C.RESET}        {data_summary['domains']}
   {C.CYAN}Data Rows Processed:{C.RESET}     {data_summary['total_rows']:,}
   {C.CYAN}Time Elapsed:{C.RESET}            {elapsed:.1f} seconds

   {C.BRIGHT_RED}🔴 Confirmed Connections:{C.RESET} {confirmed}
   {C.BRIGHT_YELLOW}🟡 Likely Connections:{C.RESET}    {likely}
   {C.BRIGHT_BLUE}📦 Clusters Found:{C.RESET}        {len(clusters)}
   {C.BRIGHT_GREEN}🏆 High-Confidence:{C.RESET}       {high_conf_clusters}
   {C.BRIGHT_MAGENTA}🎯 Potential Hubs/C2:{C.RESET}     {potential_c2}

{C.BOLD}📁 Output Directory:{C.RESET} {output_path}

   {C.BRIGHT_CYAN}Start with:{C.RESET} executive_summary.md

{C.BRIGHT_GREEN}{'═' * 60}{C.RESET}
""")
        else:
            print("\n" + "=" * 70)
            print("  ANALYSIS COMPLETE")
            print("=" * 70)

            print(f"""
📊 RESULTS SUMMARY:

   Domains Analyzed:        {data_summary['domains']}
   Data Rows Processed:     {data_summary['total_rows']:,}
   Time Elapsed:            {elapsed:.1f} seconds

   🔴 Confirmed Connections: {confirmed}
   🟡 Likely Connections:    {likely}
   📦 Clusters Found:        {len(clusters)}
   🏆 High-Confidence:       {high_conf_clusters}
   🎯 Potential Hubs/C2:     {potential_c2}

📁 Output Directory: {output_path}

   Start with: executive_summary.md
""")

        return True

    except Exception as e:
        if HAS_FUN_DISPLAY:
            print_error(f"Pipeline failed: {e}")
        else:
            print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_quick_analysis(input_dir: str, output_dir: str) -> Optional[dict]:
    """
    Run a quick analysis and return summary without full reports.
    Useful for testing or quick checks.
    """
    try:
        input_path = Path(input_dir)

        # Load data
        data = load_all_exports(input_path, show_progress=False)

        # Extract signals
        extractor = SignalExtractor()
        signals = extractor.extract_all_signals(data, show_progress=False)

        # Build network
        analyzer = NetworkAnalyzer()
        analyzer.build_network(signals, show_progress=False)

        # Detect clusters
        clusters = analyzer.detect_clusters(min_size=2)

        return {
            'domains': len(data['domains']),
            'signals': len(signals),
            'confirmed_connections': len(analyzer.get_confirmed_connections()),
            'likely_connections': len(analyzer.get_likely_connections()),
            'clusters': len(clusters),
            'high_confidence_clusters': sum(1 for c in clusters if c.confidence == "HIGH")
        }

    except Exception as e:
        print(f"Quick analysis failed: {e}")
        return None
