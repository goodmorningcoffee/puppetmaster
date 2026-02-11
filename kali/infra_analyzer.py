"""
Infrastructure Correlation Analyzer (k5)

Analyzes infrastructure patterns across multiple domains to detect
hidden connections indicating common ownership/operation.

This module correlates data from ALL Kali tools to find:
- Shared IPs/ASNs
- Shared nameservers
- Shared SSL certificates
- Shared tech stacks
- Shared emails/contacts
- Shared metadata patterns
"""

import os
import json
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Callable, Tuple
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from .modes import ScanMode, get_mode_config
from .registry import get_registry
from .aggregator import DiscoveryAggregator, AggregatedResult


# =============================================================================
# CORRELATION SIGNAL DEFINITIONS
# =============================================================================

CORRELATION_SIGNALS = {
    # IP-based correlations
    "shared_ip": {
        "description": "Multiple domains resolve to same IP address",
        "weight": 0.9,
        "source_fields": ["ips"],
    },
    "shared_ip_range": {
        "description": "Multiple domains in same /24 subnet",
        "weight": 0.6,
        "source_fields": ["ips"],
    },

    # DNS correlations
    "shared_nameserver": {
        "description": "Multiple domains use same NS records",
        "weight": 0.7,
        "source_fields": ["dns_records"],
    },
    "shared_mx": {
        "description": "Multiple domains use same mail server",
        "weight": 0.8,
        "source_fields": ["dns_records"],
    },

    # SSL correlations
    "shared_ssl_fingerprint": {
        "description": "Multiple domains use exact same SSL certificate",
        "weight": 1.0,  # Very strong signal
        "source_fields": ["ssl_info"],
    },
    "shared_ssl_issuer": {
        "description": "Multiple domains have certs from same issuer",
        "weight": 0.3,
        "source_fields": ["ssl_info"],
    },
    "shared_ssl_org": {
        "description": "Multiple domains have same org in certificate",
        "weight": 0.85,
        "source_fields": ["ssl_info"],
    },

    # Technology correlations
    "shared_tech_stack": {
        "description": "Identical CMS/framework/version combination",
        "weight": 0.5,
        "source_fields": ["technologies"],
    },
    "shared_server_signature": {
        "description": "Identical web server version/config",
        "weight": 0.4,
        "source_fields": ["technologies", "headers"],
    },

    # Contact correlations
    "shared_email": {
        "description": "Same contact email across domains",
        "weight": 0.95,
        "source_fields": ["emails"],
    },
    "shared_email_domain": {
        "description": "Emails from same custom domain",
        "weight": 0.7,
        "source_fields": ["emails"],
    },

    # Metadata correlations (from documents)
    "shared_author": {
        "description": "Same document author in metadata",
        "weight": 0.9,
        "source_fields": ["metadata"],
    },
    "shared_creator_tool": {
        "description": "Same document creation software",
        "weight": 0.3,
        "source_fields": ["metadata"],
    },

    # Social correlations
    "shared_social_username": {
        "description": "Same username on social platforms",
        "weight": 0.95,
        "source_fields": ["metadata"],
    },
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DomainInfrastructure:
    """Infrastructure data for a single domain"""
    domain: str
    scan_timestamp: str

    # Core data
    ips: Set[str] = field(default_factory=set)
    nameservers: Set[str] = field(default_factory=set)
    mx_servers: Set[str] = field(default_factory=set)
    emails: Set[str] = field(default_factory=set)

    # SSL info
    ssl_fingerprint: Optional[str] = None
    ssl_issuer: Optional[str] = None
    ssl_org: Optional[str] = None
    ssl_san: Set[str] = field(default_factory=set)

    # Tech stack
    technologies: Set[str] = field(default_factory=set)
    server_signature: Optional[str] = None
    waf: Optional[str] = None

    # Metadata
    document_authors: Set[str] = field(default_factory=set)
    creator_tools: Set[str] = field(default_factory=set)
    social_profiles: List[Dict] = field(default_factory=list)

    # Raw tool results for debugging
    raw_results: Dict[str, AggregatedResult] = field(default_factory=dict)


@dataclass
class InfraCorrelation:
    """A correlation found between domains"""
    signal_type: str
    description: str
    weight: float
    domains: Set[str]
    shared_value: str
    details: Dict = field(default_factory=dict)


@dataclass
class InfraAnalysisResult:
    """Complete analysis result"""
    timestamp: str
    mode: ScanMode
    domains_analyzed: List[str]

    # Per-domain infrastructure
    domain_infra: Dict[str, DomainInfrastructure] = field(default_factory=dict)

    # Correlations found
    correlations: List[InfraCorrelation] = field(default_factory=list)

    # Statistics
    domains_scanned: int = 0
    domains_failed: int = 0
    total_correlations: int = 0
    errors: List[str] = field(default_factory=list)

    def get_correlation_score(self, domain1: str, domain2: str) -> float:
        """Calculate correlation score between two domains"""
        score = 0.0
        for corr in self.correlations:
            if domain1 in corr.domains and domain2 in corr.domains:
                score += corr.weight
        return score

    def get_domain_clusters(self, min_score: float = 0.5) -> List[Set[str]]:
        """Group domains into clusters by correlation"""
        clusters = []
        domains = set(self.domains_analyzed)

        while domains:
            domain = domains.pop()
            cluster = {domain}

            # Find all domains correlated to this one
            for other in list(domains):
                if self.get_correlation_score(domain, other) >= min_score:
                    cluster.add(other)
                    domains.discard(other)

            clusters.append(cluster)

        return [c for c in clusters if len(c) > 1]


# =============================================================================
# INFRASTRUCTURE ANALYZER
# =============================================================================

class InfrastructureAnalyzer:
    """
    Main analyzer class that orchestrates infrastructure correlation.

    Usage:
        analyzer = InfrastructureAnalyzer(mode=ScanMode.STANDARD)
        result = analyzer.analyze(['domain1.com', 'domain2.com', 'domain3.com'])
        analyzer.save_reports(result, './output/')
    """

    def __init__(self, mode: ScanMode = ScanMode.STANDARD,
                 progress_callback: Optional[Callable] = None):
        """
        Initialize the analyzer.

        Args:
            mode: Scan mode to use for Kali tools
            progress_callback: Optional callback(domain, status, message)
        """
        self.mode = mode
        self.progress_callback = progress_callback
        self.registry = get_registry()

    def _report_progress(self, domain: str, status: str, message: str = ""):
        """Report progress to callback"""
        if self.progress_callback:
            self.progress_callback(domain, status, message)

    def _extract_infrastructure(self, domain: str, agg_result: AggregatedResult) -> DomainInfrastructure:
        """
        Extract infrastructure data from aggregated tool results.

        Args:
            domain: The domain that was scanned
            agg_result: Aggregated results from all tools

        Returns:
            DomainInfrastructure with extracted data
        """
        infra = DomainInfrastructure(
            domain=domain,
            scan_timestamp=agg_result.timestamp
        )

        # IPs from any tool
        infra.ips = agg_result.ips.copy()

        # Emails from any tool
        infra.emails = agg_result.emails.copy()

        # Process each tool's specific output
        for tool_name, tool_result in agg_result.tool_results.items():
            # DNS records (from dnsrecon, dnsenum, fierce)
            dns_records = getattr(tool_result, 'dns_records', {})
            if dns_records:
                infra.nameservers.update(dns_records.get('NS', []))
                infra.mx_servers.update(dns_records.get('MX', []))

            # SSL info (from sslscan)
            ssl_info = tool_result.metadata.get('ssl_info', {})
            if ssl_info:
                infra.ssl_fingerprint = ssl_info.get('fingerprint')
                infra.ssl_issuer = ssl_info.get('issuer')
                infra.ssl_org = ssl_info.get('organization')
                san = ssl_info.get('san', [])
                if san:
                    infra.ssl_san.update(san)

            # Technologies (from whatweb, wafw00f)
            techs = getattr(tool_result, 'technologies', [])
            if techs:
                infra.technologies.update(techs)

            # WAF detection
            waf = tool_result.metadata.get('waf')
            if waf:
                infra.waf = waf

            # Server signature from headers
            headers = tool_result.metadata.get('headers', {})
            if headers:
                server = headers.get('Server', headers.get('server'))
                if server:
                    infra.server_signature = server

            # Document metadata (from exiftool, metagoofil)
            doc_meta = tool_result.metadata.get('documents', [])
            for doc in doc_meta:
                if 'author' in doc:
                    infra.document_authors.add(doc['author'])
                if 'creator' in doc:
                    infra.creator_tools.add(doc['creator'])

            # Social profiles (from sherlock)
            social = tool_result.metadata.get('social_profiles', [])
            if social:
                infra.social_profiles.extend(social)

        return infra

    def _find_correlations(self, domain_infra: Dict[str, DomainInfrastructure]) -> List[InfraCorrelation]:
        """
        Find correlations across all domains.

        Args:
            domain_infra: Dict of domain -> DomainInfrastructure

        Returns:
            List of InfraCorrelation objects
        """
        correlations = []
        domains = list(domain_infra.keys())

        # Build reverse indexes: value -> set of domains
        ip_index = defaultdict(set)
        ns_index = defaultdict(set)
        mx_index = defaultdict(set)
        email_index = defaultdict(set)
        ssl_fp_index = defaultdict(set)
        ssl_org_index = defaultdict(set)
        tech_index = defaultdict(set)
        server_index = defaultdict(set)
        author_index = defaultdict(set)
        email_domain_index = defaultdict(set)

        for domain, infra in domain_infra.items():
            for ip in infra.ips:
                ip_index[ip].add(domain)

            for ns in infra.nameservers:
                ns_index[ns].add(domain)

            for mx in infra.mx_servers:
                mx_index[mx].add(domain)

            for email in infra.emails:
                email_index[email].add(domain)
                # Also index by email domain
                if '@' in email:
                    email_dom = email.split('@')[1]
                    email_domain_index[email_dom].add(domain)

            if infra.ssl_fingerprint:
                ssl_fp_index[infra.ssl_fingerprint].add(domain)

            if infra.ssl_org:
                ssl_org_index[infra.ssl_org].add(domain)

            # Index by tech stack combo
            if infra.technologies:
                tech_combo = "|".join(sorted(infra.technologies))
                tech_index[tech_combo].add(domain)

            if infra.server_signature:
                server_index[infra.server_signature].add(domain)

            for author in infra.document_authors:
                author_index[author].add(domain)

        # Generate correlations from indexes
        def add_correlations(index, signal_type, desc_prefix):
            signal = CORRELATION_SIGNALS.get(signal_type, {})
            for value, domain_set in index.items():
                if len(domain_set) > 1:
                    correlations.append(InfraCorrelation(
                        signal_type=signal_type,
                        description=f"{desc_prefix}: {value}",
                        weight=signal.get('weight', 0.5),
                        domains=domain_set.copy(),
                        shared_value=value
                    ))

        add_correlations(ip_index, "shared_ip", "Shared IP")
        add_correlations(ns_index, "shared_nameserver", "Shared NS")
        add_correlations(mx_index, "shared_mx", "Shared MX")
        add_correlations(email_index, "shared_email", "Shared email")
        add_correlations(email_domain_index, "shared_email_domain", "Shared email domain")
        add_correlations(ssl_fp_index, "shared_ssl_fingerprint", "Shared SSL cert")
        add_correlations(ssl_org_index, "shared_ssl_org", "Shared SSL org")
        add_correlations(tech_index, "shared_tech_stack", "Shared tech stack")
        add_correlations(server_index, "shared_server_signature", "Shared server")
        add_correlations(author_index, "shared_author", "Shared document author")

        # Check for shared IP ranges (/24)
        ip_ranges = defaultdict(set)
        for domain, infra in domain_infra.items():
            for ip in infra.ips:
                try:
                    parts = ip.split('.')
                    if len(parts) == 4:
                        range_24 = '.'.join(parts[:3]) + '.0/24'
                        ip_ranges[range_24].add(domain)
                except Exception:
                    pass

        for range_val, domain_set in ip_ranges.items():
            if len(domain_set) > 1:
                correlations.append(InfraCorrelation(
                    signal_type="shared_ip_range",
                    description=f"Same /24 subnet: {range_val}",
                    weight=CORRELATION_SIGNALS["shared_ip_range"]["weight"],
                    domains=domain_set.copy(),
                    shared_value=range_val
                ))

        return correlations

    def analyze(self, domains: List[str], parallel: int = 3) -> InfraAnalysisResult:
        """
        Analyze infrastructure for a list of domains.

        Args:
            domains: List of domains to analyze
            parallel: Number of parallel domain scans

        Returns:
            InfraAnalysisResult with all findings
        """
        result = InfraAnalysisResult(
            timestamp=datetime.now().isoformat(),
            mode=self.mode,
            domains_analyzed=domains.copy()
        )

        self._report_progress("analyzer", "starting",
                              f"Analyzing {len(domains)} domains in {self.mode.value} mode")

        # Scan each domain
        for domain in domains:
            self._report_progress(domain, "scanning", "Running Kali tools...")

            try:
                aggregator = DiscoveryAggregator(
                    mode=self.mode,
                    parallel=True,
                    max_workers=3,
                    progress_callback=None  # Disable nested progress
                )

                agg_result = aggregator.run(domain)
                result.domains_scanned += 1

                # Extract infrastructure
                infra = self._extract_infrastructure(domain, agg_result)
                result.domain_infra[domain] = infra

                self._report_progress(domain, "complete",
                                      f"IPs: {len(infra.ips)}, Emails: {len(infra.emails)}")

            except Exception as e:
                result.domains_failed += 1
                result.errors.append(f"{domain}: {str(e)}")
                self._report_progress(domain, "error", str(e))

        # Find correlations
        self._report_progress("analyzer", "correlating", "Finding infrastructure connections...")
        result.correlations = self._find_correlations(result.domain_infra)
        result.total_correlations = len(result.correlations)

        self._report_progress("analyzer", "complete",
                              f"Found {result.total_correlations} correlations")

        return result

    def save_reports(self, result: InfraAnalysisResult, output_dir: str) -> Dict[str, str]:
        """
        Save analysis reports to output directory.

        Args:
            result: Analysis results
            output_dir: Output directory path

        Returns:
            Dict of report_name -> file_path
        """
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        files = {}

        # Executive summary (markdown)
        summary_path = os.path.join(output_dir, f'infra_summary_{timestamp}.md')
        self._write_summary(result, summary_path)
        files['summary'] = summary_path

        # Correlations CSV
        corr_path = os.path.join(output_dir, f'correlations_{timestamp}.csv')
        self._write_correlations_csv(result, corr_path)
        files['correlations'] = corr_path

        # Full infrastructure JSON
        json_path = os.path.join(output_dir, f'infrastructure_{timestamp}.json')
        self._write_json(result, json_path)
        files['full_data'] = json_path

        return files

    def _write_summary(self, result: InfraAnalysisResult, path: str):
        """Write executive summary markdown"""
        clusters = result.get_domain_clusters(min_score=0.5)

        with open(path, 'w') as f:
            f.write("# Infrastructure Correlation Analysis\n\n")
            f.write(f"**Generated:** {result.timestamp}\n")
            f.write(f"**Mode:** {result.mode.value}\n")
            f.write(f"**Domains Analyzed:** {result.domains_scanned}\n\n")

            f.write("## Executive Summary\n\n")
            f.write(f"- **Total Correlations Found:** {result.total_correlations}\n")
            f.write(f"- **Domain Clusters:** {len(clusters)}\n")
            f.write(f"- **Scan Failures:** {result.domains_failed}\n\n")

            if clusters:
                f.write("## Domain Clusters\n\n")
                f.write("Domains that share significant infrastructure:\n\n")
                for i, cluster in enumerate(clusters, 1):
                    f.write(f"### Cluster {i}\n")
                    for domain in sorted(cluster):
                        f.write(f"- {domain}\n")
                    f.write("\n")

            f.write("## Correlations by Type\n\n")

            # Group correlations by type
            by_type = defaultdict(list)
            for corr in result.correlations:
                by_type[corr.signal_type].append(corr)

            for signal_type, corrs in sorted(by_type.items(), key=lambda x: -len(x[1])):
                signal_info = CORRELATION_SIGNALS.get(signal_type, {})
                f.write(f"### {signal_type} ({len(corrs)} found)\n")
                f.write(f"*{signal_info.get('description', '')}*\n\n")

                for corr in corrs[:10]:  # Limit to 10 per type
                    f.write(f"- **{corr.shared_value}**: {', '.join(sorted(corr.domains))}\n")

                if len(corrs) > 10:
                    f.write(f"\n*...and {len(corrs) - 10} more*\n")
                f.write("\n")

            if result.errors:
                f.write("## Errors\n\n")
                for error in result.errors:
                    f.write(f"- {error}\n")

    def _write_correlations_csv(self, result: InfraAnalysisResult, path: str):
        """Write correlations to CSV"""
        with open(path, 'w') as f:
            f.write("signal_type,weight,shared_value,domains,description\n")
            for corr in result.correlations:
                domains_str = "|".join(sorted(corr.domains))
                f.write(f'"{corr.signal_type}",{corr.weight},"{corr.shared_value}","{domains_str}","{corr.description}"\n')

    def _write_json(self, result: InfraAnalysisResult, path: str):
        """Write full data to JSON"""
        data = {
            'timestamp': result.timestamp,
            'mode': result.mode.value,
            'domains_analyzed': result.domains_analyzed,
            'domains_scanned': result.domains_scanned,
            'domains_failed': result.domains_failed,
            'total_correlations': result.total_correlations,
            'errors': result.errors,
            'domain_infrastructure': {},
            'correlations': []
        }

        # Convert infrastructure to serializable format
        for domain, infra in result.domain_infra.items():
            data['domain_infrastructure'][domain] = {
                'domain': infra.domain,
                'scan_timestamp': infra.scan_timestamp,
                'ips': list(infra.ips),
                'nameservers': list(infra.nameservers),
                'mx_servers': list(infra.mx_servers),
                'emails': list(infra.emails),
                'ssl_fingerprint': infra.ssl_fingerprint,
                'ssl_issuer': infra.ssl_issuer,
                'ssl_org': infra.ssl_org,
                'ssl_san': list(infra.ssl_san),
                'technologies': list(infra.technologies),
                'server_signature': infra.server_signature,
                'waf': infra.waf,
                'document_authors': list(infra.document_authors),
                'creator_tools': list(infra.creator_tools),
                'social_profiles': infra.social_profiles
            }

        # Convert correlations
        for corr in result.correlations:
            data['correlations'].append({
                'signal_type': corr.signal_type,
                'weight': corr.weight,
                'shared_value': corr.shared_value,
                'domains': list(corr.domains),
                'description': corr.description
            })

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def run_infra_analysis(domains: List[str], mode: ScanMode = ScanMode.STANDARD,
                       output_dir: str = None,
                       progress_callback: Callable = None) -> InfraAnalysisResult:
    """
    Convenience function to run infrastructure analysis.

    Args:
        domains: List of domains to analyze
        mode: Scan mode
        output_dir: Optional output directory for reports
        progress_callback: Optional progress callback

    Returns:
        InfraAnalysisResult
    """
    analyzer = InfrastructureAnalyzer(
        mode=mode,
        progress_callback=progress_callback
    )

    result = analyzer.analyze(domains)

    if output_dir:
        analyzer.save_reports(result, output_dir)

    return result


# Quick test
if __name__ == '__main__':
    def print_progress(domain, status, message):
        print(f"[{status.upper():10}] {domain}: {message}")

    print("Infrastructure Analyzer Test")
    print("=" * 50)

    # Just show what would be analyzed
    test_domains = ['example.com', 'test.com']
    print(f"\nWould analyze: {test_domains}")
    print(f"Mode: {ScanMode.STANDARD.value}")

    analyzer = InfrastructureAnalyzer(mode=ScanMode.STANDARD)
    print(f"\nCorrelation signals tracked: {len(CORRELATION_SIGNALS)}")
    for signal, info in CORRELATION_SIGNALS.items():
        print(f"  - {signal}: weight={info['weight']}")
