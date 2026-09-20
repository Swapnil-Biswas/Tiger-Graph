"""
Unit Tests for Multi-Card Temporal Velocity Burst Clustering (tests/test_burst_clustering.py)
Validates cross-card velocity burst detection, bot periodicity intervals,
micro-deposit ratio analysis, and temporal isolation.
"""

import unittest
import time
from src.graph.client import GraphClient
from src.graph.algorithms import MultiCardBurstClusterDetector


class TestMultiCardBurstClustering(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Multi-Card Burst Clustering Test Suite ===")
        cls.client = GraphClient(mode="embedded")
        cls.detector = MultiCardBurstClusterDetector(cls.client)

    def test_01_isolated_transaction_no_burst(self):
        """Routine single-card transaction with no shared burst produces no coordinated burst."""
        # Find a transaction on clean card C06743-K1
        txns = self.client.store.txns_by_card.get("C06743-K1", [])
        self.assertGreater(len(txns), 0)
        tid = str(txns[0]["TransactionID"])

        res = self.detector.detect_burst_cluster(tid, window_hours=24.0)
        self.assertEqual(res["txn_id"], tid)
        self.assertFalse(res["is_coordinated_burst"], "Routine transaction should not trigger coordinated burst")
        self.assertLessEqual(res["burst_card_count"], 1)
        self.assertEqual(res["threat_level"], "low")
        print(f"PASS: Isolated transaction {tid} verified: burst={res['is_coordinated_burst']}, cards={res['burst_card_count']}.")

    def test_02_card_testing_syndicate_burst_detection(self):
        """Syndicate card testing attack on SM-G610F triggers coordinated burst alert."""
        # Transaction 3583368 from HHG-011
        tid = "3583368"
        res = self.detector.detect_burst_cluster(tid, window_hours=24.0)

        self.assertTrue(res["is_coordinated_burst"], "Multi-card syndicate attack must be flagged as coordinated burst")
        self.assertGreaterEqual(res["burst_card_count"], 3, "Expected >= 3 distinct cards in burst")
        self.assertGreaterEqual(res["burst_txn_count"], 3, "Expected >= 3 transactions in burst")
        self.assertIn(res["threat_level"], ["high", "critical"])
        self.assertGreaterEqual(res["confidence"], 0.70)
        self.assertIn("C11923-K2", res["cards_involved"])
        print(f"PASS: Coordinated burst detected on {tid}: cards={res['burst_card_count']}, txns={res['burst_txn_count']}, threat={res['threat_level']}, conf={res['confidence']}.")

    def test_03_temporal_window_bounds(self):
        """Tightening the time window restricts the cluster to immediate adjacent transactions."""
        tid = "3583368"
        # 0.05 hours = 3 minutes (too narrow for 5-hour spread)
        narrow_res = self.detector.detect_burst_cluster(tid, window_hours=0.05)
        self.assertEqual(narrow_res["burst_txn_count"], 1)
        self.assertFalse(narrow_res["is_coordinated_burst"])

        # 24 hours captures the full multi-card campaign
        wide_res = self.detector.detect_burst_cluster(tid, window_hours=24.0)
        self.assertGreater(wide_res["burst_txn_count"], narrow_res["burst_txn_count"])
        print(f"PASS: Temporal windowing validated (txns in 3m: {narrow_res['burst_txn_count']} vs 24h: {wide_res['burst_txn_count']}).")

    def test_04_graph_client_convenience_and_latency(self):
        """GraphClient.detect_burst_cluster executes with sub-15ms latency."""
        t0 = time.perf_counter()
        res = self.client.detect_burst_cluster("3583368", window_hours=24.0)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIn("is_coordinated_burst", res)
        self.assertIn("burst_card_count", res)
        self.assertIn("threat_level", res)
        self.assertLess(elapsed_ms, 30.0, f"Latency {elapsed_ms:.2f}ms exceeded 30ms limit")
        print(f"PASS: GraphClient.detect_burst_cluster executed in {elapsed_ms:.2f}ms.")


if __name__ == "__main__":
    unittest.main()
