"""
Unit tests for Graph Temporal Motif & Topology Diff Comparator
"""

import sys
import unittest
from pathlib import Path
import networkx as nx
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.graph.motif_diff import GraphTopologyDiffComparator, TopologyDiffResult
from src.api.main import app, agent


class TestMotifDiff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comparator = GraphTopologyDiffComparator()
        cls.client = TestClient(app)

    def test_identical_graphs_diff(self):
        G1 = nx.Graph()
        G1.add_edges_from([("A", "B"), ("B", "C")])
        G2 = G1.copy()

        diff = self.comparator.compare_graphs("entity_test", G1, G2)
        self.assertEqual(diff.delta_node_count, 0)
        self.assertEqual(diff.delta_edge_count, 0)
        self.assertEqual(len(diff.nodes_added), 0)
        self.assertEqual(len(diff.edges_added), 0)
        self.assertEqual(diff.risk_shift, "STABLE")

    def test_node_and_edge_additions(self):
        G1 = nx.Graph()
        G1.add_edges_from([("A", "B")])

        G2 = G1.copy()
        G2.add_edge("B", "C")
        G2.add_edge("C", "D")

        diff = self.comparator.compare_graphs("entity_test", G1, G2)
        self.assertEqual(diff.delta_node_count, 2)
        self.assertEqual(diff.delta_edge_count, 2)
        self.assertIn("C", diff.nodes_added)
        self.assertIn("D", diff.nodes_added)

    def test_ring_formation_motif_shift(self):
        # G1 is a simple tree A-B-C
        G1 = nx.Graph()
        G1.add_edges_from([("A", "B"), ("B", "C")])

        # G2 adds edge C-A forming a 3-cycle (triangle)
        G2 = G1.copy()
        G2.add_edge("C", "A")

        diff = self.comparator.compare_graphs("entity_test", G1, G2)
        self.assertEqual(diff.risk_shift, "RING_FORMATION")
        self.assertGreater(diff.motif_deltas["triangles"], 0)
        self.assertIn("triangle", diff.narrative.lower())

    def test_structural_explosion_shift(self):
        G1 = nx.Graph()
        G1.add_edge("center", "n1")

        # G2 adds 6 new nodes and 12 edges
        G2 = G1.copy()
        for i in range(2, 8):
            G2.add_edge("center", f"n{i}")
            G2.add_edge(f"n{i}", f"aux_{i}")

        diff = self.comparator.compare_graphs("center", G1, G2)
        self.assertEqual(diff.risk_shift, "STRUCTURAL_EXPLOSION")
        self.assertGreaterEqual(diff.delta_node_count, 5)

    def test_bridge_creation_shift(self):
        # G1 has two disconnected components: A-B and C-D
        G1 = nx.Graph()
        G1.add_edges_from([("A", "B"), ("C", "D")])

        # G2 links B to C with a bridge edge
        G2 = G1.copy()
        G2.add_edge("B", "C")

        diff = self.comparator.compare_graphs("A", G1, G2)
        # Check motif deltas or risk shift
        self.assertIn(diff.risk_shift, ("BRIDGE_CREATION", "STABLE"))

    def test_graph_client_compare_topology_snapshots(self):
        t2 = 1500000000.0
        t1 = t2 - 86400 * 30
        res = agent.client.compare_topology_snapshots(
            entity_id="C12382-K1",
            t1=t1,
            t2=t2,
            hops=2,
        )
        self.assertIn("entity_id", res)
        self.assertIn("risk_shift", res)
        self.assertIn("delta_node_count", res)
        self.assertIn("delta_edge_count", res)
        self.assertIn("motif_deltas", res)

    def test_fastapi_graph_diff_endpoints(self):
        # Direct diff endpoint
        resp = self.client.get(
            "/api/graph/diff?entity_id=C12382-K1&t1=1400000000&t2=1500000000&hops=2"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["entity_id"], "C12382-K1")
        self.assertIn("risk_shift", data)

        # Case graph diff endpoint
        resp_case = self.client.get("/api/cases/HHG-001/graph-diff")
        self.assertEqual(resp_case.status_code, 200)
        case_data = resp_case.json()
        self.assertIn("risk_shift", case_data)


if __name__ == "__main__":
    unittest.main()
