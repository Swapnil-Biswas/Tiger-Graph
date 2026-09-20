"""
Unit Tests for Parallelized Asynchronous Graph Traversal Engine
Validates thread safety, multi-query result identity, and concurrent performance.
"""

import unittest
from concurrent.futures import ThreadPoolExecutor
from src.agent.graph import FraudInvestigatorAgent
from src.graph.traverser import ConcurrentGraphTraverser
from src.agent.budgeter import AdaptiveGraphBudgeter


class TestAsyncGraphTraversal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Async Graph Traversal Test Suite ===")
        cls.agent = FraudInvestigatorAgent()

    def test_concurrency_accuracy_identity(self):
        """Concurrent graph traversal must produce 100% identical results to sequential execution."""
        card_id = "C00259-K1"
        flagged_txn = "3000001"
        as_of = "2016-10-01 00:00:00"
        budget_plan = {
            "allow_deep_ring_scan": True,
            "allow_geo_dispersion_scan": True,
            "allow_undocumented_detector": True,
        }

        # 1. Concurrent Execution
        concurrent_res = ConcurrentGraphTraverser.gather_graph_evidence(
            client=self.agent.client,
            memory_prior_engine=self.agent.memory_prior_engine,
            undocumented_detector=self.agent.undocumented_detector,
            card_id=card_id,
            customer_id=None,
            flagged_txn=flagged_txn,
            dev_profile=None,
            as_of=as_of,
            budget_plan=budget_plan,
            max_workers=6,
        )

        # 2. Sequential Execution
        seq_profile = self.agent.client.entity_profile(card_id, "card")
        seq_vel = self.agent.client.velocity(card_id, as_of=as_of)
        seq_ring = self.agent.client.ring_detection(card_id, as_of=as_of)
        seq_geo = self.agent.client.geo_impossible(card_id, as_of=as_of)

        # Identity checks
        self.assertEqual(concurrent_res["profile"]["txn_count"], seq_profile["txn_count"])
        self.assertEqual(concurrent_res["velocity"]["windows"]["24h"]["count"], seq_vel["windows"]["24h"]["count"])
        self.assertEqual(concurrent_res["ring"].get("is_ring_candidate"), seq_ring.get("is_ring_candidate"))
        self.assertEqual(concurrent_res["geo"]["has_geo_anomaly"], seq_geo["has_geo_anomaly"])
        self.assertGreater(concurrent_res["traversal_time_ms"], 0.0)

    def test_thread_safety_multi_case_stress(self):
        """Concurrently investigating multiple distinct cases must not cause race conditions."""
        cases = ["HHG-001", "HHG-002", "HHG-003", "HHG-004", "HHG-007", "HHG-011"]

        def _run_case(cid):
            return self.agent.investigate_case(cid)

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(_run_case, cases))

        self.assertEqual(len(results), len(cases))
        for res in results:
            self.assertIn("case", res)
            self.assertIn("verdict", res["case"])
            self.assertIn("fraud_probability", res["case"])


if __name__ == "__main__":
    unittest.main()
