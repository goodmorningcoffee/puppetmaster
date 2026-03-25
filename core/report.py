#!/usr/bin/env python3
"""
report.py - Report Generation for Sock Puppet Detection

Generates:
- executive_summary.md - Main findings (start here!)
- smoking_guns.csv - Definitive connections
- clusters.csv - Domain groupings
- hub_analysis.csv - Potential C2 domains
- all_connections.csv - Complete edge list
"""

import os
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from .signals import Signal, SignalTier, summarize_signals
from .network import NetworkAnalyzer, DomainConnection, DomainCluster, HubAnalysis, summarize_network


def sanitize_csv_value(value):
    """
    Sanitize a value for safe CSV output to prevent CSV injection attacks.

    CSV injection occurs when a cell value starts with =, +, -, @, or tab/carriage return,
    which can be interpreted as formulas by spreadsheet applications.

    Args:
        value: The value to sanitize

    Returns:
        Sanitized string safe for CSV export
    """
    if value is None:
        return ""

    value = str(value)

    # Characters that can trigger formula interpretation in spreadsheets
    dangerous_chars = ('=', '+', '-', '@', '\t', '\r', '\n')

    # Check if value starts with dangerous character (even after leading whitespace)
    # This catches " =formula" attacks while preserving intentional leading spaces
    stripped = value.lstrip()
    if stripped and stripped[0] in dangerous_chars:
        return "'" + value

    return value


# =============================================================================
# EXECUTIVE SUMMARY GENERATOR
# =============================================================================

def generate_executive_summary(
    output_dir: Path,
    signals: Dict,
    analyzer: NetworkAnalyzer,
    hubs: List[HubAnalysis],
    data_summary: Dict,
    wildcard_suspects: Dict = None
) -> str:
    """Generate the executive summary markdown file"""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    network_summary = summarize_network(analyzer)
    signal_summary = summarize_signals(signals)

    # Get top findings
    confirmed_connections = analyzer.get_confirmed_connections()
    confirmed_connections.sort(key=lambda c: len(c.smoking_guns), reverse=True)

    high_conf_clusters = [c for c in analyzer.clusters if c.confidence == "HIGH"]
    potential_c2s = [h for h in hubs if h.is_potential_c2]

    md = f"""# 🎭 PUPPETMASTER Executive Summary

**Analysis Date:** {timestamp}
**Tool Version:** 1.0

---

## 🎯 Key Findings at a Glance

| Metric | Count |
|--------|-------|
| Domains Analyzed | {data_summary.get('domains', 0)} |
| Total Data Rows | {data_summary.get('total_rows', 0):,} |
| **Confirmed Connections** | **{network_summary['confirmed_connections']}** 🔴 |
| Likely Connections | {network_summary['likely_connections']} 🟡 |
| Domain Clusters | {network_summary['clusters']} |
| Potential Hub/C2 Domains | {len(potential_c2s)} |

---

## 🔴 SMOKING GUN EVIDENCE

These connections are **definitively proven** by shared unique identifiers.
One matching signal = same operator.

"""

    if confirmed_connections:
        md += "| Domain 1 | Domain 2 | Evidence Type | Shared Value |\n"
        md += "|----------|----------|---------------|---------------|\n"

        for conn in confirmed_connections[:15]:
            for sg in conn.smoking_guns[:2]:  # Show up to 2 smoking guns per connection
                value = sg.value[:40] + "..." if len(sg.value) > 40 else sg.value
                md += f"| {conn.domain1} | {conn.domain2} | {sg.signal_type} | `{value}` |\n"

        if len(confirmed_connections) > 15:
            md += f"\n*...and {len(confirmed_connections) - 15} more confirmed connections. See `smoking_guns.csv` for complete list.*\n"
    else:
        md += "*No smoking gun evidence found. This could mean:*\n"
        md += "- *Domains are not connected*\n"
        md += "- *Operators are using different tracking/analytics per domain*\n"
        md += "- *SpiderFoot didn't capture the connecting signals*\n"

    md += f"""

---

## 🏷️ High-Confidence Clusters

These domain groups are likely controlled by the same entity.

"""

    if high_conf_clusters:
        for i, cluster in enumerate(high_conf_clusters[:5], 1):
            domains_list = ", ".join(sorted(cluster.domains)[:10])
            if len(cluster.domains) > 10:
                domains_list += f", ... (+{len(cluster.domains) - 10} more)"

            md += f"""### Cluster {i}: {cluster.size} domains
**Hub Domain:** `{cluster.hub_domain}`
**Smoking Guns:** {cluster.smoking_gun_count}
**Domains:** {domains_list}

"""
    else:
        md += "*No high-confidence clusters detected.*\n"

    md += f"""

---

## 🎮 Potential Hub/Controller Domains

These domains have high connectivity and may be central to the network.

"""

    if potential_c2s:
        md += "| Domain | Connections | Confirmed | Likely | Centrality |\n"
        md += "|--------|-------------|-----------|--------|------------|\n"

        for hub in potential_c2s[:10]:
            md += f"| {hub.domain} | {hub.connection_count} | {hub.confirmed_connections} | {hub.likely_connections} | {hub.betweenness_centrality:.3f} |\n"
    else:
        md += "*No obvious hub domains detected.*\n"

    # Add wildcard DNS suspects section if available
    if wildcard_suspects:
        confirmed_wildcards = {d: v for d, v in wildcard_suspects.items()
                              if v.get('is_wildcard', False)}

        if confirmed_wildcards:
            md += f"""

---

## ⚠️ Potential Wildcard DNS False Positives

The following domains show wildcard DNS patterns and may inflate enumerated subdomain counts.
Subdomains from these domains should be treated with caution.

| Domain | Wildcard IP | Confidence |
|--------|-------------|------------|
"""
            for domain, info in list(confirmed_wildcards.items())[:15]:
                wildcard_ip = info.get('wildcard_ip', 'unknown')
                confidence = info.get('confidence', 'unknown')
                md += f"| {domain} | {wildcard_ip} | {confidence} |\n"

            if len(confirmed_wildcards) > 15:
                md += f"\n*...and {len(confirmed_wildcards) - 15} more wildcard domains.*\n"

            md += """
**Recommendation:** Run `python3 wildcardDNS_analyzer.py --domain <domain> --full` for deep analysis.

"""

    md += f"""

---

## 📊 Signal Summary

| Signal Type | Tier | Occurrences |
|-------------|------|-------------|
"""

    for signal_type, count in sorted(signal_summary['by_type'].items(), key=lambda x: -x[1])[:15]:
        # Determine tier
        tier = "🔴 Smoking Gun" if signal_type in ['google_analytics', 'adsense', 'email', 'ssl_fingerprint', 'google_site_verification', 'atlassian_verification', 'facebook_pixel'] else "🟡 Strong"
        md += f"| {signal_type} | {tier} | {count} |\n"

    md += f"""

---

## 📁 Output Files

- `executive_summary.md` - This file
- `smoking_guns.csv` - All definitive connections with evidence
- `clusters.csv` - Domain cluster assignments
- `hub_analysis.csv` - Hub/C2 domain analysis
- `all_connections.csv` - Complete connection list
- `signals.csv` - All extracted signals

---

## 🔍 Methodology

This analysis uses a **binary signal classification** approach:

1. **Smoking Guns** 🔴 - Unique identifiers that definitively prove common ownership:
   - Google Analytics IDs (UA-XXXXX, G-XXXXX)
   - AdSense Publisher IDs (pub-XXXXX)
   - Unique email addresses
   - SSL certificate fingerprints
   - Google Site Verification tokens

2. **Strong Signals** 🟡 - Indicators that suggest connection when multiple match:
   - WHOIS registrant information
   - Phone numbers
   - Custom nameservers
   - Cryptocurrency addresses

3. **Weak/Noise** - Filtered out (shared CDN, hosting, generic patterns)

**Key Insight:** A single shared Google Analytics ID is stronger evidence than
10 shared hosting providers.

---

## ⚠️ Limitations

- Analysis is only as good as SpiderFoot's data collection
- Privacy-protected WHOIS data limits registrant matching
- Common shared services (Cloudflare, AWS) are filtered as noise
- False positives possible if unrelated sites use same web dev agency

---

*Generated by PUPPETMASTER - SpiderFoot Sock Puppet Detector*
*"Finding the strings that connect the puppets"*
"""

    # Write the file
    output_path = output_dir / "executive_summary.md"
    if output_path.exists():
        print(f"  Note: Overwriting {output_path.name}")
    output_path.write_text(md)
    print(f"✓ Executive summary: {output_path}")

    return md


# =============================================================================
# CSV EXPORTERS
# =============================================================================

def export_smoking_guns(output_dir: Path, analyzer: NetworkAnalyzer):
    """Export all smoking gun connections to CSV"""
    filepath = output_dir / "smoking_guns.csv"
    if filepath.exists():
        print(f"  Note: Overwriting {filepath.name}")

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow([
            'Domain 1', 'Domain 2', 'Signal Type', 'Signal Value',
            'Description', 'Source Module'
        ])

        for conn in analyzer.get_confirmed_connections():
            for sg in conn.smoking_guns:
                # Sanitize values to prevent CSV injection attacks
                writer.writerow([
                    sanitize_csv_value(conn.domain1),
                    sanitize_csv_value(conn.domain2),
                    sanitize_csv_value(sg.signal_type),
                    sanitize_csv_value(sg.value),
                    sanitize_csv_value(sg.description),
                    sanitize_csv_value(sg.source_module)
                ])

    print(f"✓ Smoking guns CSV: {filepath}")


def export_clusters(output_dir: Path, clusters: List[DomainCluster]):
    """Export cluster analysis to CSV"""
    filepath = output_dir / "clusters.csv"
    if filepath.exists():
        print(f"  Note: Overwriting {filepath.name}")

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow([
            'Cluster ID', 'Confidence', 'Size', 'Hub Domain',
            'Smoking Gun Count', 'Domains'
        ])

        for cluster in clusters:
            # Sanitize values to prevent CSV injection attacks
            writer.writerow([
                sanitize_csv_value(cluster.cluster_id),
                sanitize_csv_value(cluster.confidence),
                cluster.size,
                sanitize_csv_value(cluster.hub_domain),
                cluster.smoking_gun_count,
                sanitize_csv_value("; ".join(sorted(cluster.domains)))
            ])

    print(f"✓ Clusters CSV: {filepath}")


def export_hubs(output_dir: Path, hubs: List[HubAnalysis]):
    """Export hub analysis to CSV"""
    filepath = output_dir / "hub_analysis.csv"
    if filepath.exists():
        print(f"  Note: Overwriting {filepath.name}")

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow([
            'Domain', 'Is Potential C2', 'Total Connections',
            'Confirmed Connections', 'Likely Connections',
            'Betweenness Centrality', 'PageRank', 'Connected Domains'
        ])

        for hub in hubs:
            # Sanitize values to prevent CSV injection attacks
            writer.writerow([
                sanitize_csv_value(hub.domain),
                hub.is_potential_c2,
                hub.connection_count,
                hub.confirmed_connections,
                hub.likely_connections,
                f"{hub.betweenness_centrality:.6f}",
                f"{hub.pagerank:.6f}",
                sanitize_csv_value("; ".join(hub.connected_domains[:20]))
            ])

    print(f"✓ Hub analysis CSV: {filepath}")


def export_all_connections(output_dir: Path, analyzer: NetworkAnalyzer):
    """Export all connections to CSV"""
    filepath = output_dir / "all_connections.csv"
    if filepath.exists():
        print(f"  Note: Overwriting {filepath.name}")

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow([
            'Domain 1', 'Domain 2', 'Confidence', 'Total Signals',
            'Smoking Guns', 'Strong Signals', 'Evidence Summary'
        ])

        # Sort by confidence
        connections = sorted(
            analyzer.connections.values(),
            key=lambda c: (
                0 if c.confidence == "CONFIRMED" else
                1 if c.confidence == "LIKELY" else
                2 if c.confidence == "POSSIBLE" else 3,
                -c.total_signals
            )
        )

        for conn in connections:
            # Sanitize values to prevent CSV injection attacks
            writer.writerow([
                sanitize_csv_value(conn.domain1),
                sanitize_csv_value(conn.domain2),
                sanitize_csv_value(conn.confidence),
                conn.total_signals,
                len(conn.smoking_guns),
                len(conn.strong_signals),
                sanitize_csv_value(conn.evidence_summary)
            ])

    print(f"✓ All connections CSV: {filepath}")


def export_signals(output_dir: Path, signals: Dict):
    """Export all signals to CSV"""
    filepath = output_dir / "signals.csv"
    if filepath.exists():
        print(f"  Note: Overwriting {filepath.name}")

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow([
            'Signal Type', 'Tier', 'Value', 'Domain Count',
            'Domains', 'Description'
        ])

        # Sort by tier and domain count
        sorted_signals = sorted(
            signals.values(),
            key=lambda s: (
                0 if s.tier == SignalTier.SMOKING_GUN else 1,
                -len(s.domains)
            )
        )

        for signal in sorted_signals:
            # Sanitize values to prevent CSV injection attacks
            writer.writerow([
                sanitize_csv_value(signal.signal_type),
                sanitize_csv_value(signal.tier.value),
                sanitize_csv_value(signal.value[:200] + ("..." if len(signal.value) > 200 else "")),
                len(signal.domains),
                sanitize_csv_value("; ".join(sorted(signal.domains)[:20])),
                sanitize_csv_value(signal.description)
            ])

    print(f"✓ Signals CSV: {filepath}")


# =============================================================================
# MAIN REPORT GENERATOR
# =============================================================================

def generate_all_reports(
    output_dir: Path,
    signals: Dict,
    analyzer: NetworkAnalyzer,
    hubs: List[HubAnalysis],
    data_summary: Dict,
    wildcard_suspects: Dict = None
):
    """Generate all reports and exports"""
    print("\n📝 Generating reports...")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate executive summary (with wildcard suspects if available)
    generate_executive_summary(output_dir, signals, analyzer, hubs, data_summary, wildcard_suspects)

    # Export CSVs
    export_smoking_guns(output_dir, analyzer)
    export_clusters(output_dir, analyzer.clusters)
    export_hubs(output_dir, hubs)
    export_all_connections(output_dir, analyzer)
    export_signals(output_dir, signals)

    print(f"\n✓ All reports saved to: {output_dir}")
