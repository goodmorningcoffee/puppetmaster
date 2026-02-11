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

# Import wildcard DNS analyzer
try:
    import sys
    from pathlib import Path
    # Add parent directory to path for wildcardDNS_analyzer
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from wildcardDNS_analyzer import quick_wildcard_check, extract_base_domains_from_clusters
    HAS_WILDCARD_ANALYZER = True
except ImportError:
    HAS_WILDCARD_ANALYZER = False

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
        BRIGHT_RED = BRIGHT_BLUE = BRIGHT_WHITE = WHITE = RED = ''
        DIM = UNDERLINE = ''

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

        spinner = None
        if HAS_FUN_DISPLAY:
            # above_progress=True puts spinner on line above tqdm progress bar
            spinner = FunSpinner("Reading CSV files", style='detective', above_progress=True)
            spinner.start()

        try:
            data = load_all_exports(input_path, show_progress=show_progress)
            if spinner:
                spinner.stop(f"Loaded {len(data['domains'])} domains from {data['total_rows']:,} records")
        except Exception:
            if spinner:
                spinner.stop("Error loading data")
            raise

        data_summary = {
            'domains': len(data['domains']),
            'total_rows': data['total_rows'],
            'modules': len(data['rows_by_module'])
        }

        # =====================================================================
        # STAGE 2: Signal Extraction
        # =====================================================================
        spinner = None
        if HAS_FUN_DISPLAY:
            print_stage_header(2, total_stages, "Extracting Signals")
            # above_progress=True for tqdm compatibility
            spinner = FunSpinner("Analyzing digital fingerprints", style='dots', above_progress=True)
            spinner.start()
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n🔬 STAGE 2: Extracting Signals")
            print("-" * 50)

        try:
            extractor = SignalExtractor()
            signals = extractor.extract_all_signals(data, show_progress=show_progress)
            if spinner:
                spinner.stop(f"Extracted {len(signals)} signals")
        except Exception:
            if spinner:
                spinner.stop("Error extracting signals")
            raise

        # =====================================================================
        # STAGE 3: Network Analysis
        # =====================================================================
        spinner = None
        if HAS_FUN_DISPLAY:
            print_stage_header(3, total_stages, "Building Connection Network")
            # above_progress=True for tqdm compatibility
            spinner = FunSpinner("Mapping the web of deceit", style='spider', above_progress=True)
            spinner.start()
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n🕸️ STAGE 3: Building Connection Network")
            print("-" * 50)

        try:
            analyzer = NetworkAnalyzer()
            analyzer.build_network(signals, show_progress=show_progress)
            if spinner:
                edges = analyzer.graph.number_of_edges() if hasattr(analyzer, 'graph') else 0
                spinner.stop(f"Built network with {edges} connections")
        except Exception:
            if spinner:
                spinner.stop("Error building network")
            raise

        # =====================================================================
        # STAGE 4: Cluster Detection
        # =====================================================================
        spinner = None
        if HAS_FUN_DISPLAY:
            print_stage_header(4, total_stages, "Detecting Domain Clusters")
            spinner = FunSpinner("Finding sock puppet networks", style='puppet')
            spinner.start()
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n🔍 STAGE 4: Detecting Domain Clusters")
            print("-" * 50)

        try:
            clusters = analyzer.detect_clusters(min_size=2)
            if spinner:
                high_conf = sum(1 for c in clusters if c.confidence == "HIGH")
                spinner.stop(f"Found {len(clusters)} clusters ({high_conf} high-confidence)")
        except Exception:
            if spinner:
                spinner.stop("Error detecting clusters")
            raise

        # =====================================================================
        # STAGE 4b: Wildcard DNS Check (Optional)
        # =====================================================================
        wildcard_suspects = {}
        if HAS_WILDCARD_ANALYZER:
            if HAS_FUN_DISPLAY:
                print()
                print(f"  {C.CYAN}[i]{C.RESET} Checking for wildcard DNS false positives...")

            # Extract unique base domains from clusters that have many subdomains
            try:
                # Get domains from clusters WITH FREQUENCY COUNTING
                # This ensures we check the most common domains first
                from collections import Counter
                domain_counts = Counter()

                for cluster in clusters:
                    for domain in cluster.domains:
                        # Clean domain (remove protocols, trailing chars)
                        domain = domain.lower().strip()
                        if domain.startswith('http://'):
                            domain = domain[7:]
                        if domain.startswith('https://'):
                            domain = domain[8:]
                        domain = domain.split('/')[0].rstrip('.,;:')

                        parts = domain.split('.')

                        # Extract multiple levels of base domains
                        # For deep subdomains like "sub1.sub2.sub3.example.io" we check:
                        # - example.io (last 2)
                        # - sub3.example.io (last 3)
                        # - sub2.sub3.example.io (last 4)
                        # - sub1.sub2.sub3.example.io (last 5)
                        for i in range(2, min(len(parts) + 1, 6)):  # Check up to 5 levels
                            base = '.'.join(parts[-i:])
                            if base and '.' in base:  # Valid domain
                                domain_counts[base] += 1

                # Sort by frequency (most common first) and take top candidates
                # This ensures high-frequency wildcard zones get checked first
                sorted_domains = [d for d, count in domain_counts.most_common(100)]

                # Log what we're checking
                if HAS_FUN_DISPLAY and sorted_domains:
                    top_5 = sorted_domains[:5]
                    print(f"  {C.DIM}[i] Checking {len(sorted_domains)} candidate domains (top: {', '.join(top_5[:3])}...){C.RESET}")

                domain_list = sorted_domains

                if domain_list:
                    wildcard_suspects = quick_wildcard_check(domain_list, timeout=2.0)

                    # Filter to only confirmed wildcards
                    confirmed_wildcards = {d: v for d, v in wildcard_suspects.items()
                                          if v.get('is_wildcard', False)}

                    if confirmed_wildcards:
                        if HAS_FUN_DISPLAY:
                            print(f"  {C.YELLOW}[!]{C.RESET} {C.YELLOW}Wildcard DNS detected in {len(confirmed_wildcards)} domain(s):{C.RESET}")
                            for domain, info in list(confirmed_wildcards.items())[:5]:
                                print(f"      {C.YELLOW}- {domain}{C.RESET} (wildcard IP: {info.get('wildcard_ip', 'unknown')})")
                            if len(confirmed_wildcards) > 5:
                                print(f"      {C.DIM}... and {len(confirmed_wildcards) - 5} more{C.RESET}")
                            print(f"  {C.CYAN}[i]{C.RESET} {C.DIM}These may be false positives. Run Signal//Noise analyzer for deep dive.{C.RESET}")
                        else:
                            print(f"  [!] Wildcard DNS detected in {len(confirmed_wildcards)} domain(s)")
                    else:
                        if HAS_FUN_DISPLAY:
                            print(f"  {C.GREEN}[+]{C.RESET} No wildcard DNS patterns detected")
                        else:
                            print("  [+] No wildcard DNS patterns detected")
            except Exception as e:
                if HAS_FUN_DISPLAY:
                    print(f"  {C.DIM}[i] Wildcard check skipped: {e}{C.RESET}")

        # =====================================================================
        # STAGE 5: Hub Identification
        # =====================================================================
        spinner = None
        if HAS_FUN_DISPLAY:
            print_stage_header(5, total_stages, "Identifying Hub Domains")
            spinner = FunSpinner("Zeroing in on puppet masters", style='runner')
            spinner.start()
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n🎯 STAGE 5: Identifying Hub Domains")
            print("-" * 50)

        try:
            hubs = analyzer.identify_hubs(top_n=30)
            if spinner:
                potential_c2 = sum(1 for h in hubs if h.is_potential_c2)
                spinner.stop(f"Identified {len(hubs)} hubs ({potential_c2} potential C2)")
        except Exception:
            if spinner:
                spinner.stop("Error identifying hubs")
            raise

        # =====================================================================
        # STAGE 6: Report Generation
        # =====================================================================
        spinner = None
        if HAS_FUN_DISPLAY:
            print_stage_header(6, total_stages, "Generating Reports")
            spinner = FunSpinner("Writing analysis reports", style='moon')
            spinner.start()
        else:
            print(f"\n{random.choice(PROGRESS_MESSAGES)}")
            print("\n📝 STAGE 6: Generating Reports")
            print("-" * 50)

        try:
            generate_all_reports(
                output_dir=output_path,
                signals=signals,
                analyzer=analyzer,
                hubs=hubs,
                data_summary=data_summary,
                wildcard_suspects=wildcard_suspects if HAS_WILDCARD_ANALYZER else None
            )

            # Export graph for external visualization
            graph_path = output_path / "network.graphml"
            analyzer.export_graph(str(graph_path))

            if spinner:
                spinner.stop("Reports generated successfully")
        except Exception:
            if spinner:
                spinner.stop("Error generating reports")
            raise

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
