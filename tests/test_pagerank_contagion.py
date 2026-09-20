"""
Unit Tests for Personalized PageRank Fraud Contagion Engine (tests/test_pagerank_contagion.py)
Validates Random Walk with Restart (RWR) contagion calculation, seed diffusion,
mathematical convergence, temporal isolation, and API endpoints.
"""

import unittest
import time
from fastapi.testclient import TestClient
from src.graph.client import GraphClient
from src.graph.algorithms import FraudContagionPageRank
from src.api.main import app


class TestFraudContagionPageRank(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Fraud Contagion PageRank Test Suite ===")
        cls.client = GraphClient(mode="embedded")
        cls.rwr = FraudContagionPageRank(cls.client)
        cls.api_client = TestClient(app)

    def test_01_isolated_entity_zero_contagion(self):
        """Routine clean card with no fraud precedents has 0.0 contagion score."""
        card_id = "C06743-K1"
        res = self.rwr.calculate_contagion(card_id, as_of="2017-01-01 00:00:00")

        self.assertEqual(res["target_id"], card_id)
        self.assertEqual(res["mode"], "target_centrality")
        self.assertEqual(res["target_contagion_score"], 0.0)
        self.assertEqual(res["contagion_risk_level"], "none")
        self.assertEqual(len(res["fraud_seeds"]), 0)
        self.assertGreater(res["target_centrality_score"], 0.0)
        print(f"PASS: Isolated entity verified: contagion={res['target_contagion_score']}, centrality={res['target_centrality_score']}.")

    def test_02_syndicate_contagion_propagation(self):
        """Entity connected to confirmed fraud precedents receives elevated contagion."""
        card_id = "C00259-K1"
        res = self.rwr.calculate_contagion(card_id, as_of="2017-06-01 00:00:00")

        self.assertEqual(res["mode"], "contagion_from_fraud_seeds")
        self.assertGreater(len(res["fraud_seeds"]), 0, "Must detect confirmed fraud seeds")
        self.assertGreaterEqual(res["target_contagion_score"], 0.15, "Target contagion should be critical (>= 0.15)")
        self.assertIn(res["contagion_risk_level"], ["critical", "high"])
        self.assertGreater(len(res["top_nodes_by_contagion"]), 0)
        print(f"PASS: Syndicate contagion verified: score={res['target_contagion_score']:.4f}, threat={res['contagion_risk_level']}, seeds={len(res['fraud_seeds'])}.")

    def test_03_custom_fraud_seeds_propagation(self):
        """Custom fraud seeds correctly diffuse contagion to target entity."""
        card_id = "C00259-K1"
        res = self.rwr.calculate_contagion(
            card_id,
            as_of="2017-06-01 00:00:00",
            custom_fraud_seeds=["CARD:C00259-K1"],
        )

        self.assertEqual(res["mode"], "contagion_from_fraud_seeds")
        self.assertIn("CARD:C00259-K1", res["fraud_seeds"])
        self.assertGreater(res["target_contagion_score"], 0.10)
        print(f"PASS: Custom fraud seeds verified: seeds={res['fraud_seeds']}, score={res['target_contagion_score']:.4f}.")

    def test_04_mathematical_properties_convergence(self):
        """PageRank distribution must sum to approximately 1.0 across the subgraph."""
        card_id = "C12382-K1"
        res = self.rwr.calculate_contagion(card_id, as_of="2017-06-01 00:00:00")

        total_prob = sum(n["score"] for n in res["top_nodes_by_contagion"])
        self.assertGreater(total_prob, 0.50, "Top nodes should capture majority of mass")
        self.assertLessEqual(total_prob, 1.05, "Probability mass cannot exceed 1.0 + epsilon")
        self.assertLessEqual(res["iterations_to_convergence"], 30)
        self.assertEqual(res["restart_probability"], 0.15)
        print(f"PASS: Mathematical properties verified: sum={total_prob:.4f}, iters={res['iterations_to_convergence']}.")

    def test_05_temporal_isolation_enforcement(self):
        """Strict as_of cutoff prevents future fraud seeds from diffusing into historical contagion."""
        card_id = "C00259-K1"
        # Prior to any transactions or cases
        early_res = self.rwr.calculate_contagion(card_id, as_of="2015-01-01 00:00:00")
        self.assertEqual(early_res["mode"], "target_centrality")
        self.assertEqual(early_res["target_contagion_score"], 0.0)
        self.assertEqual(early_res["contagion_risk_level"], "none")
        self.assertEqual(len(early_res["fraud_seeds"]), 0)

        # Later after fraud cases exist
        later_res = self.rwr.calculate_contagion(card_id, as_of="2017-06-01 00:00:00")
        self.assertEqual(later_res["mode"], "contagion_from_fraud_seeds")
        self.assertGreater(later_res["target_contagion_score"], 0.0)
        print(f"PASS: Temporal isolation verified (2015 contagion: {early_res['target_contagion_score']} vs 2017: {later_res['target_contagion_score']}).")

    def test_06_execution_latency_sub_15ms(self):
        """PageRank calculation executes under 15ms."""
        card_id = "C12382-K1"
        t0 = time.perf_counter()
        res = self.rwr.calculate_contagion(card_id, as_of="2017-06-01 00:00:00")
        latency_ms = (time.perf_counter() - t0) * 1000.0

        self.assertLess(latency_ms, 15.0, f"Latency {latency_ms:.2f}ms exceeds 15ms threshold")
        print(f"PASS: PageRank execution latency: {latency_ms:.2f}ms (reported: {res['elapsed_ms']}ms).")

    def test_07_api_endpoint_integration(self):
        """API endpoints GET /api/cases/{id}/contagion and POST /api/graph/contagion-check operate correctly."""
        # Test GET /api/cases/HHG-001/contagion
        resp = self.api_client.get("/api/cases/HHG-001/contagion")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("contagion", data)
        self.assertEqual(data["case_id"], "HHG-001")

        # Test POST /api/graph/contagion-check
        post_resp = self.api_client.post(
            "/api/graph/contagion-check",
            json={"seed_id": "C00259-K1", "entity_type": "card", "as_of": "2017-06-01 00:00:00"},
        )
        self.assertEqual(post_resp.status_code, 200)
        post_data = post_resp.json()
        self.assertEqual(post_data["target_id"], "C00259-K1")
        self.assertIn("target_contagion_score", post_data)
        print("PASS: API endpoints verified successfully.")
