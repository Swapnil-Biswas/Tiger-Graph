"""
Active Learning Sample Selector & Hard-Negative Mining Tests (tests/test_active_learning.py)
Validates margin uncertainty mathematics, Shannon entropy symmetry, hard-negative mining,
submodular topological diversity caps, continuous retraining weights, temporal isolation,
and REST API endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from src.graph.client import GraphClient
from src.ml.active_learning import ActiveLearningSampleSelector
from src.api.main import app


class TestActiveLearningSampleSelector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Active Learning Test Suite ===")
        cls.client = GraphClient()
        cls.selector = ActiveLearningSampleSelector(cls.client)
        cls.api = TestClient(app)

    def test_01_margin_uncertainty_mathematical_bounds(self):
        """Validates margin uncertainty boundary conditions and scaling."""
        self.assertEqual(self.selector.compute_margin_uncertainty(0.50), 1.0)
        self.assertEqual(self.selector.compute_margin_uncertainty(0.00), 0.0)
        self.assertEqual(self.selector.compute_margin_uncertainty(1.00), 0.0)
        self.assertEqual(self.selector.compute_margin_uncertainty(0.40), 0.8)
        self.assertEqual(self.selector.compute_margin_uncertainty(0.60), 0.8)
        print("PASS: Margin uncertainty mathematical properties and symmetry verified.")

    def test_02_shannon_entropy_mathematical_bounds(self):
        """Validates normalized binary Shannon entropy bounds and symmetry."""
        self.assertEqual(self.selector.compute_binary_entropy(0.50), 1.0)
        self.assertAlmostEqual(self.selector.compute_binary_entropy(0.00), 0.0, places=3)
        self.assertAlmostEqual(self.selector.compute_binary_entropy(1.00), 0.0, places=3)
        h_03 = self.selector.compute_binary_entropy(0.30)
        h_07 = self.selector.compute_binary_entropy(0.70)
        self.assertEqual(h_03, h_07, "Entropy must be symmetric around 0.50")
        print("PASS: Binary Shannon entropy bounds and symmetry verified.")

    def test_03_hard_negative_filtering(self):
        """Validates that hard-negative mining prioritizes non-fraud transactions with high risk."""
        res = self.selector.mine_candidate_samples(target_size=15, strategy="hard_negative", max_scan=500)
        self.assertGreater(len(res["candidates"]), 0)
        for c in res["candidates"]:
            # Hard negatives are non-fraud samples
            self.assertEqual(c["true_label"], 0, "Hard negative must be non-fraud ground truth")
            self.assertGreaterEqual(c["informativeness_score"], 0.0)
        self.assertGreater(res["summary"]["hard_negatives_count"], 0)
        print(f"PASS: Mined {len(res['candidates'])} hard negatives with {res['summary']['hard_negatives_count']} high-risk flags.")

    def test_04_hybrid_balanced_scoring_and_weights(self):
        """Validates hybrid balanced scoring and sample retraining weight assignments."""
        res = self.selector.mine_candidate_samples(target_size=20, strategy="hybrid_balanced", max_scan=500)
        self.assertEqual(len(res["candidates"]), 20)
        for c in res["candidates"]:
            weight = c["retraining_weight"]
            self.assertGreaterEqual(weight, 1.0)
            self.assertLessEqual(weight, 5.0)
        self.assertGreater(res["summary"]["avg_retraining_weight"], 1.0)
        print(f"PASS: Hybrid balanced batch generated with avg retraining weight {res['summary']['avg_retraining_weight']:.2f}.")

    def test_05_submodular_topological_diversity(self):
        """Validates that card and merchant caps prevent cluster concentration."""
        res = self.selector.mine_candidate_samples(
            target_size=25,
            strategy="hybrid_balanced",
            max_scan=1000,
            max_per_card=2,
            max_per_merchant=3,
        )
        card_counts = {}
        merch_counts = {}
        for c in res["candidates"]:
            cid = c["card_id"]
            mid = c["merchant_id"]
            card_counts[cid] = card_counts.get(cid, 0) + 1
            merch_counts[mid] = merch_counts.get(mid, 0) + 1

        for cid, count in card_counts.items():
            self.assertLessEqual(count, 2, f"Card {cid} exceeded max_per_card cap")
        for mid, count in merch_counts.items():
            self.assertLessEqual(count, 3, f"Merchant {mid} exceeded max_per_merchant cap")

        self.assertGreaterEqual(res["summary"]["unique_cards_covered"], 10)
        print(f"PASS: Topological diversity verified across {res['summary']['unique_cards_covered']} unique cards.")

    def test_06_temporal_isolation_as_of(self):
        """Validates strict temporal isolation: no candidate may exceed as_of timestamp."""
        cutoff_epoch = 1000000  # Early epoch
        res = self.selector.mine_candidate_samples(target_size=10, as_of=cutoff_epoch)
        for c in res["candidates"]:
            self.assertLessEqual(c["epoch_s"], cutoff_epoch)
        print("PASS: Temporal isolation verified across candidate pool.")

    def test_07_rest_api_endpoints(self):
        """Validates GET and POST active learning API endpoints."""
        # 1. POST /api/ml/active-learning/mine
        post_req = {
            "target_size": 10,
            "strategy": "margin_uncertainty",
            "max_scan": 300,
            "max_per_card": 2,
        }
        resp_post = self.api.post("/api/ml/active-learning/mine", json=post_req)
        self.assertEqual(resp_post.status_code, 200)
        data_post = resp_post.json()
        self.assertEqual(data_post["strategy"], "margin_uncertainty")
        self.assertEqual(len(data_post["candidates"]), 10)

        # 2. GET /api/ml/active-learning/candidates
        resp_get = self.api.get("/api/ml/active-learning/candidates?target_size=5&strategy=hybrid_balanced&max_scan=200")
        self.assertEqual(resp_get.status_code, 200)
        data_get = resp_get.json()
        self.assertEqual(len(data_get["candidates"]), 5)
        print("PASS: REST API endpoints verified for active learning mining.")


if __name__ == "__main__":
    unittest.main()
