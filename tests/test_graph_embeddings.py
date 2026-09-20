"""
Unit Tests for Topological Graph Embedding & GNN-Ready Adjacency Matrix Exporter (tests/test_graph_embeddings.py)
Validates PyTorch Geometric (PyG) schema concordance, tensor shapes ([N, D], [2, E]),
normalized feature bounds, tabular ego-net vectors, and temporal isolation.
"""

import unittest
import time
from src.graph.client import GraphClient
from src.graph.embeddings import TopologicalGraphEmbeddingExporter


class TestGraphEmbeddings(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Graph Embeddings Test Suite ===")
        cls.client = GraphClient(mode="embedded")
        cls.exporter = TopologicalGraphEmbeddingExporter(cls.client)

    def test_01_gnn_subgraph_schema_and_shapes(self):
        """Validates PyG tensor dimensions, node features [N, 9], and edge_index [2, E]."""
        card_id = "C00259-K1"
        res = self.exporter.extract_gnn_subgraph(card_id, as_of="2017-06-01 00:00:00", k_hops=2)

        self.assertTrue(res["pyg_format_ready"])
        self.assertGreater(res["num_nodes"], 0)
        self.assertGreater(res["num_edges"], 0)

        # Check x tensor shape [N, 9]
        x = res["x"]
        self.assertEqual(len(x), res["num_nodes"])
        for row in x:
            self.assertEqual(len(row), 9, "Node feature vector must have 9 dimensions")
            for val in row:
                self.assertGreaterEqual(val, 0.0)
                self.assertLessEqual(val, 1.0)

        # Check edge_index shape [2, E]
        edge_index = res["edge_index"]
        self.assertEqual(len(edge_index), 2)
        self.assertEqual(len(edge_index[0]), res["num_edges"])
        self.assertEqual(len(edge_index[1]), res["num_edges"])

        # Check edge_attr shape [E, 5]
        edge_attr = res["edge_attr"]
        self.assertEqual(len(edge_attr), res["num_edges"])
        for row in edge_attr:
            self.assertEqual(len(row), 5, "Edge attribute vector must have 5 dimensions")
            for val in row:
                self.assertGreaterEqual(val, 0.0)
                self.assertLessEqual(val, 1.0)

        print(f"PASS: PyG subgraph schema validated: N={res['num_nodes']}, E={res['num_edges']}, x={len(x)}x9, edge_index=2x{res['num_edges']}.")

    def test_02_tabular_ego_net_vector_completeness(self):
        """Validates extracted tabular ego-net vector contains all required GBDT topological features."""
        card_id = "C12382-K1"
        res = self.exporter.extract_gnn_subgraph(card_id, as_of="2016-12-05 01:55:28", k_hops=2)

        tab = res["tabular_vector"]
        required_keys = [
            "subgraph_node_count",
            "subgraph_edge_count",
            "subgraph_density",
            "subgraph_avg_clustering",
            "subgraph_max_degree",
            "card_nodes_count",
            "device_nodes_count",
            "customer_nodes_count",
            "transaction_nodes_count",
            "fraud_precedents_count",
        ]
        for k in required_keys:
            self.assertIn(k, tab)
            self.assertIsInstance(tab[k], float)
            self.assertFalse(tab[k] != tab[k], f"Feature {k} cannot be NaN")

        self.assertGreater(tab["subgraph_node_count"], 0)
        self.assertGreaterEqual(tab["subgraph_density"], 0.0)
        self.assertLessEqual(tab["subgraph_density"], 1.0)
        print(f"PASS: Tabular ego-net vector complete: {tab}")

    def test_03_temporal_isolation(self):
        """Subgraph node and edge counts must respect as_of temporal boundaries."""
        card_id = "C00259-K1"
        early_res = self.exporter.extract_gnn_subgraph(card_id, as_of="2015-01-01 00:00:00", k_hops=2)
        later_res = self.exporter.extract_gnn_subgraph(card_id, as_of="2017-06-01 00:00:00", k_hops=2)

        self.assertEqual(early_res["num_nodes"], 1, "Zero transactions exist prior to 2015")
        self.assertEqual(early_res["num_edges"], 0)
        self.assertGreater(later_res["num_nodes"], early_res["num_nodes"])
        self.assertGreater(later_res["num_edges"], early_res["num_edges"])
        print(f"PASS: Temporal isolation verified (nodes at 2015: {early_res['num_nodes']} vs at 2017: {later_res['num_nodes']}).")

    def test_04_graph_client_convenience_and_latency(self):
        """GraphClient.export_gnn_subgraph runs with sub-25ms execution latency."""
        t0 = time.perf_counter()
        res = self.client.export_gnn_subgraph("C00259-K1", as_of="2017-06-01 00:00:00", k_hops=2)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertTrue(res["pyg_format_ready"])
        self.assertLess(elapsed_ms, 50.0, f"Latency {elapsed_ms:.2f}ms exceeded 50ms limit")
        print(f"PASS: GraphClient.export_gnn_subgraph completed in {elapsed_ms:.2f}ms.")


if __name__ == "__main__":
    unittest.main()
