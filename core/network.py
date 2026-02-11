#!/usr/bin/env python3
"""
network.py - Network Analysis and Clustering for Sock Puppet Detection

Builds a domain connection graph from signals and performs:
- Community detection (identify clusters)
- Hub identification (find potential C2/controllers)
- Connection strength analysis
"""

import networkx as nx
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from .signals import Signal, SignalTier

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class DomainConnection:
    """Represents a connection between two domains"""
    domain1: str
    domain2: str
    smoking_guns: List[Signal] = field(default_factory=list)
    strong_signals: List[Signal] = field(default_factory=list)
    weak_signals: List[Signal] = field(default_factory=list)

    @property
    def confidence(self) -> str:
        """Get connection confidence level"""
        if self.smoking_guns:
            return "CONFIRMED"
        elif len(self.strong_signals) >= 2:
            return "LIKELY"
        elif self.strong_signals:
            return "POSSIBLE"
        else:
            return "WEAK"

    @property
    def total_signals(self) -> int:
        return len(self.smoking_guns) + len(self.strong_signals) + len(self.weak_signals)

    @property
    def evidence_summary(self) -> str:
        """Get a summary of the evidence"""
        parts = []
        if self.smoking_guns:
            types = set(s.signal_type for s in self.smoking_guns)
            parts.append(f"🔴 {len(self.smoking_guns)} smoking gun(s): {', '.join(types)}")
        if self.strong_signals:
            types = set(s.signal_type for s in self.strong_signals)
            parts.append(f"🟡 {len(self.strong_signals)} strong signal(s): {', '.join(types)}")
        return "; ".join(parts) if parts else "Weak signals only"


@dataclass
class DomainCluster:
    """Represents a cluster of connected domains"""
    cluster_id: int
    domains: Set[str] = field(default_factory=set)
    connections: List[DomainConnection] = field(default_factory=list)
    hub_domain: Optional[str] = None

    @property
    def size(self) -> int:
        return len(self.domains)

    @property
    def confidence(self) -> str:
        """Overall cluster confidence"""
        confirmed = any(c.confidence == "CONFIRMED" for c in self.connections)
        likely = sum(1 for c in self.connections if c.confidence == "LIKELY")

        if confirmed:
            return "HIGH"
        elif likely >= 2:
            return "MEDIUM"
        else:
            return "LOW"

    @property
    def smoking_gun_count(self) -> int:
        return sum(len(c.smoking_guns) for c in self.connections)


@dataclass
class HubAnalysis:
    """Analysis of a potential hub/controller domain"""
    domain: str
    connection_count: int
    confirmed_connections: int
    likely_connections: int
    betweenness_centrality: float
    pagerank: float
    is_potential_c2: bool
    connected_domains: List[str] = field(default_factory=list)


# =============================================================================
# NETWORK BUILDER
# =============================================================================

class NetworkAnalyzer:
    """Build and analyze domain connection network"""

    def __init__(self):
        self.graph = nx.Graph()
        self.connections: Dict[Tuple[str, str], DomainConnection] = {}
        self.clusters: List[DomainCluster] = []

    def build_network(self, signals: Dict[str, Signal], show_progress: bool = True):
        """
        Build network from extracted signals.

        Each shared signal creates edges between all domains that share it.
        """
        # Optional tqdm import with fallback
        try:
            from tqdm import tqdm
        except ImportError:
            def tqdm(iterable, **kwargs):
                return iterable

        print("\n🕸️ Building domain connection network...")

        # First, create all connections from signals
        connection_signals = defaultdict(lambda: {'smoking': [], 'strong': [], 'weak': []})

        signal_list = list(signals.values())
        iterator = tqdm(signal_list, desc="  Processing signals", ncols=80) if show_progress else signal_list

        for signal in iterator:
            domains = list(signal.domains)

            # Create edges between all pairs of domains sharing this signal
            for i, d1 in enumerate(domains):
                for d2 in domains[i + 1:]:
                    # Normalize edge key (alphabetical order)
                    edge_key = tuple(sorted([d1, d2]))

                    if signal.tier == SignalTier.SMOKING_GUN:
                        connection_signals[edge_key]['smoking'].append(signal)
                    elif signal.tier == SignalTier.STRONG:
                        connection_signals[edge_key]['strong'].append(signal)
                    else:
                        connection_signals[edge_key]['weak'].append(signal)

        # Create DomainConnection objects and add to graph
        for (d1, d2), sig_data in connection_signals.items():
            conn = DomainConnection(
                domain1=d1,
                domain2=d2,
                smoking_guns=sig_data['smoking'],
                strong_signals=sig_data['strong'],
                weak_signals=sig_data['weak']
            )
            self.connections[(d1, d2)] = conn

            # Add edge to graph with weight based on confidence
            weight = len(sig_data['smoking']) * 10 + len(sig_data['strong']) * 3 + len(sig_data['weak'])
            self.graph.add_edge(d1, d2, weight=weight, connection=conn)

        # Summary
        confirmed = sum(1 for c in self.connections.values() if c.confidence == "CONFIRMED")
        likely = sum(1 for c in self.connections.values() if c.confidence == "LIKELY")

        print(f"\n✓ Network built: {self.graph.number_of_nodes()} domains, {self.graph.number_of_edges()} connections")
        print(f"  🔴 {confirmed} CONFIRMED connections (smoking gun evidence)")
        print(f"  🟡 {likely} LIKELY connections (multiple strong signals)")

    def detect_clusters(self, min_size: int = 2) -> List[DomainCluster]:
        """
        Detect clusters of connected domains using community detection.
        """
        print("\n🔍 Detecting domain clusters...")

        if self.graph.number_of_nodes() == 0:
            print("  No nodes in graph")
            return []

        # Try Louvain first (best for weighted graphs, finds more granular clusters)
        try:
            import community as community_louvain
            partition = community_louvain.best_partition(self.graph, weight='weight')
            print("  Using Louvain community detection (recommended)")
        except ImportError:
            # Fall back to label propagation - WARNING: produces fewer, larger clusters
            print("  ⚠ python-louvain not installed, using label propagation (may find fewer clusters)")
            print("  💡 Install for better results: pip install python-louvain")
            communities = list(nx.algorithms.community.label_propagation_communities(self.graph))
            partition = {}
            for i, comm in enumerate(communities):
                for node in comm:
                    partition[node] = i

        # Group domains by community
        community_domains = defaultdict(set)
        for domain, comm_id in partition.items():
            community_domains[comm_id].add(domain)

        # Create cluster objects
        self.clusters = []
        for cluster_id, domains in community_domains.items():
            if len(domains) < min_size:
                continue

            # Get all connections within this cluster
            cluster_connections = []
            for (d1, d2), conn in self.connections.items():
                if d1 in domains and d2 in domains:
                    cluster_connections.append(conn)

            # Find hub (highest degree within cluster)
            subgraph = self.graph.subgraph(domains)
            if subgraph.number_of_nodes() > 0:
                hub = max(subgraph.nodes(), key=lambda n: subgraph.degree(n, weight='weight'))
            else:
                hub = list(domains)[0]

            cluster = DomainCluster(
                cluster_id=cluster_id,
                domains=domains,
                connections=cluster_connections,
                hub_domain=hub
            )
            self.clusters.append(cluster)

        # Sort by confidence and size
        self.clusters.sort(key=lambda c: (
            0 if c.confidence == "HIGH" else 1 if c.confidence == "MEDIUM" else 2,
            -c.size
        ))

        # Summary
        high_conf = sum(1 for c in self.clusters if c.confidence == "HIGH")
        med_conf = sum(1 for c in self.clusters if c.confidence == "MEDIUM")

        print(f"✓ Found {len(self.clusters)} clusters:")
        print(f"  🔴 {high_conf} HIGH confidence clusters")
        print(f"  🟡 {med_conf} MEDIUM confidence clusters")

        return self.clusters

    def identify_hubs(self, top_n: int = 20) -> List[HubAnalysis]:
        """
        Identify potential hub/C2 domains based on network centrality.
        """
        print("\n🎯 Identifying potential hub domains...")

        if self.graph.number_of_nodes() == 0:
            return []

        # Calculate centrality measures
        betweenness = nx.betweenness_centrality(self.graph, weight='weight')

        # PageRank requires scipy - fall back to degree centrality if not available
        try:
            pagerank = nx.pagerank(self.graph, weight='weight')
        except (ImportError, ModuleNotFoundError, Exception):
            # scipy not installed or other error - use degree centrality as fallback
            print("  ⚠ scipy not installed, using degree centrality instead of PageRank")
            print("  💡 Install scipy for better results: pip install scipy")
            degree = dict(self.graph.degree(weight='weight'))
            # Avoid division by zero: ensure max_degree is at least 1
            max_degree = max(degree.values()) if degree else 1
            if max_degree == 0:
                max_degree = 1
            pagerank = {node: deg / max_degree for node, deg in degree.items()}

        hubs = []
        for domain in self.graph.nodes():
            # Count connection types
            confirmed = 0
            likely = 0
            neighbors = list(self.graph.neighbors(domain))

            for neighbor in neighbors:
                edge_key = tuple(sorted([domain, neighbor]))
                conn = self.connections.get(edge_key)
                if conn:
                    if conn.confidence == "CONFIRMED":
                        confirmed += 1
                    elif conn.confidence == "LIKELY":
                        likely += 1

            # Determine if potential C2
            is_c2 = (
                confirmed >= 3 or
                (confirmed >= 1 and likely >= 3) or
                (betweenness.get(domain, 0) > 0.1 and len(neighbors) >= 5)
            )

            hub = HubAnalysis(
                domain=domain,
                connection_count=len(neighbors),
                confirmed_connections=confirmed,
                likely_connections=likely,
                betweenness_centrality=betweenness.get(domain, 0),
                pagerank=pagerank.get(domain, 0),
                is_potential_c2=is_c2,
                connected_domains=neighbors
            )
            hubs.append(hub)

        # Sort by potential C2 status and connection count
        hubs.sort(key=lambda h: (
            0 if h.is_potential_c2 else 1,
            -h.confirmed_connections,
            -h.connection_count
        ))

        potential_c2 = sum(1 for h in hubs if h.is_potential_c2)
        print(f"✓ Found {potential_c2} potential hub/C2 domains")

        return hubs[:top_n]

    def get_confirmed_connections(self) -> List[DomainConnection]:
        """Get all confirmed (smoking gun) connections"""
        return [c for c in self.connections.values() if c.confidence == "CONFIRMED"]

    def get_likely_connections(self) -> List[DomainConnection]:
        """Get all likely connections"""
        return [c for c in self.connections.values() if c.confidence == "LIKELY"]

    def get_connection(self, domain1: str, domain2: str) -> Optional[DomainConnection]:
        """Get connection between two specific domains"""
        key = tuple(sorted([domain1, domain2]))
        return self.connections.get(key)

    def get_domain_connections(self, domain: str) -> List[DomainConnection]:
        """Get all connections for a specific domain"""
        result = []
        for (d1, d2), conn in self.connections.items():
            if d1 == domain or d2 == domain:
                result.append(conn)
        return result

    def export_graph(self, filepath: str):
        """Export graph to GraphML format for visualization in other tools"""
        # Create a copy of the graph with only serializable attributes
        export_graph = nx.Graph()

        # Add nodes
        for node in self.graph.nodes():
            export_graph.add_node(node)

        # Add edges with only weight attribute (not the DomainConnection object)
        for u, v, data in self.graph.edges(data=True):
            conn = data.get('connection')
            if conn:
                export_graph.add_edge(
                    u, v,
                    weight=data.get('weight', 1),
                    confidence=conn.confidence,
                    smoking_guns=len(conn.smoking_guns),
                    strong_signals=len(conn.strong_signals)
                )
            else:
                export_graph.add_edge(u, v, weight=data.get('weight', 1))

        nx.write_graphml(export_graph, filepath)
        print(f"✓ Graph exported to {filepath}")


def summarize_network(analyzer: NetworkAnalyzer) -> Dict:
    """Create a summary of the network analysis"""
    return {
        'total_domains': analyzer.graph.number_of_nodes(),
        'total_connections': analyzer.graph.number_of_edges(),
        'confirmed_connections': len(analyzer.get_confirmed_connections()),
        'likely_connections': len(analyzer.get_likely_connections()),
        'clusters': len(analyzer.clusters),
        'high_confidence_clusters': sum(1 for c in analyzer.clusters if c.confidence == "HIGH"),
        'medium_confidence_clusters': sum(1 for c in analyzer.clusters if c.confidence == "MEDIUM"),
    }
