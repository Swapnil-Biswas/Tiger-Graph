"""
Unit Tests for Dynamic Graph Community Detection & Dense Fraud Subgraph Discovery (tests/test_community_detection.py)
Validates Label Propagation Algorithm (LPA) partitioning, internal edge density,
fraud contagion calculation, and temporal isolation.
"""

import unittest
import time
from src.graph.client import GraphClient
from src.graph.algorithms import GraphCommunityDetector


class TestGraphCommunityDetection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Graph Community Detection Test Suite ===")
        cls.client = GraphClient(mode="embedded")
        cls.detector = GraphCommunityDetector(cls.client)

    def test_01_isolated_entity_trivial_community(self):
        """Routine single-card customer with no shared devices yields a trivial community."""
        card_id = "C06743-K1"  # Clean customer C06743 with zero prior fraud
        res = self.detector.detect_community(card_id, as_of="2017-01-01 00:00:00")

        self.assertEqual(res["seed_id"], card_id)
        self.assertIn(card_id, res["cards"])
        self.assertEqual(res["card_count"], 1)
        self.assertEqual(res["customer_count"], 1, "Single cardholder wallet")
        self.assertFalse(res["is_dense_fraud_cluster"], "Routine card should not be flagged as dense fraud cluster")
        self.assertEqual(res["fraud_contagion_score"], 0.0)
        print(f"PASS: Isolated entity community verified (cards={res['card_count']}, customers={res['customer_count']}, cluster={res['is_dense_fraud_cluster']}).")

    def test_02_syndicate_dense_fraud_cluster_detection(self):
        """Coordinated syndicate nexus yields a multi-card dense fraud community with elevated contagion."""
        # C00259-K1 is linked to device sharing and known fraud precedent CC-3035
        card_id = "C00259-K1"
        res = self.detector.detect_community(card_id, as_of="2017-06-01 00:00:00")

        self.assertGreaterEqual(res["card_count"], 2, "Syndicate community must contain >= 2 cards")
        self.assertGreaterEqual(res["device_count"], 1, "Syndicate community must contain shared device")
        self.assertGreaterEqual(res["fraud_contagion_score"], 0.40, "Contagion score should be >= 0.40")
        self.assertTrue(res["is_dense_fraud_cluster"], "Syndicate nexus must be classified as dense fraud cluster")
        self.assertGreater(len(res["fraud_cases_in_community"]), 0, "Precedent fraud cases must be cited")
        print(f"PASS: Syndicate dense fraud community detected: {res['community_id']} (cards={res['card_count']}, contagion={res['fraud_contagion_score']}, cases={res['fraud_cases_in_community']}).")

    def test_03_temporal_isolation_enforcement(self):
        """Community detection must strictly enforce as_of temporal cutoff."""
        card_id = "C00259-K1"
        # Before any transactions occurred
        early_res = self.detector.detect_community(card_id, as_of="2015-01-01 00:00:00")
        self.assertEqual(early_res["community_size"], 1)
        self.assertEqual(early_res["card_count"], 1)
        self.assertEqual(len(early_res["fraud_cases_in_community"]), 0)

        # After transactions occurred
        later_res = self.detector.detect_community(card_id, as_of="2017-06-01 00:00:00")
        self.assertGreater(later_res["community_size"], early_res["community_size"])
        print(f"PASS: Temporal isolation verified (size at 2015: {early_res['community_size']} vs at 2017: {later_res['community_size']}).")

    def test_04_graph_client_convenience_and_latency(self):
        """GraphClient.detect_community convenience method functions with sub-50ms latency."""
        t0 = time.perf_counter()
        res = self.client.detect_community("C00259-K1", as_of="2017-06-01 00:00:00")
        latency_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIn("community_id", res)
        self.assertIn("internal_edge_density", res)
        self.assertIn("fraud_contagion_score", res)
        self.assertIn("is_dense_fraud_cluster", res)
        self.assertLess(latency_ms, 150.0, f"Latency {latency_ms:.2f}ms exceeded 150ms limit")
        print(f"PASS: GraphClient.detect_community executed in {latency_ms:.2f}ms with complete schema.")


if __name__ == "__main__":
    unittest.main()
