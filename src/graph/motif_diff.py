"""
Graph Temporal Motif and Topology Diff Comparator for TigerGraph Agentic Platform
Compares temporal snapshots of ego-networks (t1 vs t2), detecting structural deltas,
emerging motifs (stars, cycles, bridges), and topological risk shifts.
"""

import time
from typing import Dict, Any, List, Set, Tuple, Optional
from dataclasses import dataclass, field, asdict
import networkx as nx


@dataclass
class TopologyDiffResult:
    entity_id: str
    t1: float
    t2: float
    nodes_added: List[str]
    nodes_removed: List[str]
    edges_added: List[Tuple[str, str]]
    edges_removed: List[Tuple[str, str]]
    delta_node_count: int
    delta_edge_count: int
    delta_density: float
    motif_deltas: Dict[str, int]
    risk_shift: str  # STABLE, STRUCTURAL_EXPLOSION, RING_FORMATION, BRIDGE_CREATION
    narrative: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["edges_added"] = [f"{u}->{v}" for u, v in self.edges_added]
        d["edges_removed"] = [f"{u}->{v}" for u, v in self.edges_removed]
        return d


class GraphTopologyDiffComparator:
    """Computes topological differences and motif shifts between two graph states."""

    @staticmethod
    def extract_motifs(G: nx.Graph) -> Dict[str, int]:
        """Extracts counts of fundamental structural motifs."""
        motifs = {
            "stars": 0,
            "triangles": 0,
            "cycles": 0,
            "bridges": 0,
        }
        if len(G) == 0:
            return motifs

        # Triangles
        try:
            tri_dict = nx.triangles(G.to_undirected() if G.is_directed() else G)
            motifs["triangles"] = sum(tri_dict.values()) // 3
        except Exception:
            pass

        # Stars (nodes with degree >= 3)
        for _, deg in G.degree():
            if deg >= 3:
                motifs["stars"] += 1

        # Bridges (cut edges)
        try:
            undirected = G.to_undirected() if G.is_directed() else G
            motifs["bridges"] = len(list(nx.bridges(undirected)))
        except Exception:
            pass

        # Simple cycles (DFS on small subgraphs)
        if G.is_directed():
            try:
                cycles = list(nx.simple_cycles(G))
                motifs["cycles"] = len(cycles)
            except Exception:
                pass
        else:
            try:
                cycle_basis = nx.cycle_basis(G)
                motifs["cycles"] = len(cycle_basis)
            except Exception:
                pass

        return motifs

    def compare_graphs(
        self,
        entity_id: str,
        G1: nx.Graph,
        G2: nx.Graph,
        t1: float = 0.0,
        t2: float = 0.0,
    ) -> TopologyDiffResult:
        """
        Computes detailed topological and motif differences between G1 and G2.
        """
        nodes1 = set(G1.nodes())
        nodes2 = set(G2.nodes())
        nodes_added = sorted(list(nodes2 - nodes1))
        nodes_removed = sorted(list(nodes1 - nodes2))

        def _get_edges(G: nx.Graph) -> Set[Tuple[str, str]]:
            return set((str(u), str(v)) for u, v in G.edges())

        edges1 = _get_edges(G1)
        edges2 = _get_edges(G2)
        edges_added = sorted(list(edges2 - edges1))
        edges_removed = sorted(list(edges1 - edges2))

        # Densities
        d1 = nx.density(G1) if len(G1) > 1 else 0.0
        d2 = nx.density(G2) if len(G2) > 1 else 0.0
        delta_density = round(d2 - d1, 4)

        # Motifs
        m1 = self.extract_motifs(G1)
        m2 = self.extract_motifs(G2)
        motif_deltas = {k: m2[k] - m1[k] for k in m1}

        # Risk Shift Classification
        delta_nodes = len(nodes_added) - len(nodes_removed)
        delta_edges = len(edges_added) - len(edges_removed)

        if motif_deltas.get("cycles", 0) > 0 or motif_deltas.get("triangles", 0) > 0:
            risk_shift = "RING_FORMATION"
            narrative = f"Detected emergence of {motif_deltas.get('cycles', 0)} new cycle(s) and {motif_deltas.get('triangles', 0)} triangle(s), indicating potential circular routing."
        elif delta_nodes >= 5 or delta_edges >= 10:
            risk_shift = "STRUCTURAL_EXPLOSION"
            narrative = f"Rapid topological expansion observed: +{len(nodes_added)} nodes, +{len(edges_added)} edges."
        elif motif_deltas.get("bridges", 0) > 0:
            risk_shift = "BRIDGE_CREATION"
            narrative = f"Detected {motif_deltas.get('bridges', 0)} new bridge connection(s) linking previously isolated components."
        else:
            risk_shift = "STABLE"
            narrative = "Topology remained stable between snapshots with minimal structural variance."

        return TopologyDiffResult(
            entity_id=entity_id,
            t1=t1,
            t2=t2,
            nodes_added=nodes_added,
            nodes_removed=nodes_removed,
            edges_added=edges_added,
            edges_removed=edges_removed,
            delta_node_count=delta_nodes,
            delta_edge_count=delta_edges,
            delta_density=delta_density,
            motif_deltas=motif_deltas,
            risk_shift=risk_shift,
            narrative=narrative,
        )

    def compare_temporal_snapshots(
        self,
        store: Any,
        entity_id: str,
        t1: float,
        t2: float,
        hops: int = 2,
    ) -> TopologyDiffResult:
        """
        Builds ego-networks from GraphStore at t1 and t2, then computes the diff.
        """
        G1 = self._build_ego_at_time(store, entity_id, t1, hops)
        G2 = self._build_ego_at_time(store, entity_id, t2, hops)
        return self.compare_graphs(entity_id, G1, G2, t1=t1, t2=t2)

    def _build_ego_at_time(self, store: Any, entity_id: str, t: float, hops: int = 2) -> nx.Graph:
        """Constructs an in-memory ego network of all nodes and transactions with timestamp <= t."""
        G = nx.Graph()
        if not hasattr(store, "transactions"):
            return G

        G.add_node(entity_id)
        visited = {entity_id}
        current_layer = {entity_id}

        for _ in range(hops):
            next_layer = set()
            for node in current_layer:
                # Find connected transactions where timestamp <= t
                for tx_id, tx in store.transactions.items():
                    ts = getattr(tx, "timestamp", 0.0)
                    if ts > t:
                        continue
                    cid = getattr(tx, "card_id", "")
                    did = getattr(tx, "device_id", "")
                    mid = getattr(tx, "merchant_id", "")

                    if node in (tx_id, cid, did, mid):
                        for neighbor in (tx_id, cid, did, mid):
                            if neighbor:
                                G.add_node(neighbor)
                                G.add_edge(node, neighbor)
                                if neighbor not in visited:
                                    visited.add(neighbor)
                                    next_layer.add(neighbor)
            current_layer = next_layer

        return G


# Global singleton instance
motif_comparator = GraphTopologyDiffComparator()
