import unittest
from fastapi.testclient import TestClient
from src.graph.client import GraphClient
from src.graph.decay import ExponentialTemporalDecay
from src.api.main import app, agent


class TestGraphDecay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = agent.client
        cls.decay_engine = ExponentialTemporalDecay(half_life_days=30.0, client=cls.client)
        cls.api_client = TestClient(app)

    def test_exponential_decay_halflife_mathematics(self):
        """Exponential decay must halve weight every half-life period exactly."""
        now = 100_000_000
        tau_seconds = 30 * 86400  # 30 days = 2,592,000s

        # At Delta t = 0
        w0 = self.decay_engine.calculate_edge_weight(epoch_s=now, as_of_epoch=now)
        self.assertAlmostEqual(w0["effective_weight"], 1.0, places=4)
        self.assertTrue(w0["retained"])

        # At Delta t = 1 half-life
        w1 = self.decay_engine.calculate_edge_weight(epoch_s=now - tau_seconds, as_of_epoch=now)
        self.assertAlmostEqual(w1["decay_factor"], 0.50, places=3)
        self.assertAlmostEqual(w1["effective_weight"], 0.50, places=3)

        # At Delta t = 2 half-lives
        w2 = self.decay_engine.calculate_edge_weight(epoch_s=now - (2 * tau_seconds), as_of_epoch=now)
        self.assertAlmostEqual(w2["decay_factor"], 0.25, places=3)
        self.assertAlmostEqual(w2["effective_weight"], 0.25, places=3)

    def test_priority_boosting_and_fraud_preservation(self):
        """Confirmed fraud transactions must receive 4.0x priority multiplier and fraud immunity."""
        now = 100_000_000
        tau_seconds = 30 * 86400
        old_epoch = now - (5 * tau_seconds)  # 150 days old

        # Normal transaction: 2^-5 = 0.03125 (< 0.05 min weight -> pruned)
        normal = self.decay_engine.calculate_edge_weight(epoch_s=old_epoch, as_of_epoch=now, is_fraud=False)
        self.assertFalse(normal["retained"])
        self.assertEqual(normal["prune_reason"], "EXPIRED_BELOW_MIN_WEIGHT")

        # Fraud transaction: boosted by 4.0x and immune to deletion
        fraud = self.decay_engine.calculate_edge_weight(epoch_s=old_epoch, as_of_epoch=now, is_fraud=True)
        self.assertTrue(fraud["retained"])
        self.assertTrue(fraud["is_fraud_immune"])
        self.assertGreater(fraud["effective_weight"], normal["effective_weight"])

    def test_syndicate_and_high_risk_priority_boost(self):
        """Syndicate links (3.0x) and high-risk alerts (2.0x) must decay slower than routine retail."""
        now = 100_000_000
        tau_seconds = 30 * 86400
        epoch_2_half_lives = now - (2 * tau_seconds)

        routine = self.decay_engine.calculate_edge_weight(epoch_s=epoch_2_half_lives, as_of_epoch=now, risk_score=0.1)
        high_risk = self.decay_engine.calculate_edge_weight(epoch_s=epoch_2_half_lives, as_of_epoch=now, risk_score=0.85)
        syndicate = self.decay_engine.calculate_edge_weight(
            epoch_s=epoch_2_half_lives, as_of_epoch=now, edge_type="COLLUSIVE_MERCHANT_LINK"
        )

        self.assertAlmostEqual(routine["effective_weight"], 0.25, places=2)
        self.assertAlmostEqual(high_risk["effective_weight"], 0.50, places=2)
        self.assertAlmostEqual(syndicate["effective_weight"], 0.75, places=2)

    def test_bounded_degree_top_k_pruning(self):
        """High-degree node must be pruned to max_degree while preserving fraud seeds at top priority."""
        as_of = 500_000
        edges = []
        # 30 routine transactions
        for i in range(30):
            edges.append({
                "txn_id": f"TX_{i}",
                "epoch_s": as_of - (i * 1000),
                "is_fraud": False,
                "risk_score": 0.1,
            })
        # 2 old confirmed fraud transactions
        edges.append({
            "txn_id": "TX_FRAUD_OLD_1",
            "epoch_s": as_of - 10_000_000,
            "is_fraud": True,
            "risk_score": 0.99,
        })
        edges.append({
            "txn_id": "TX_FRAUD_OLD_2",
            "epoch_s": as_of - 12_000_000,
            "is_fraud": True,
            "risk_score": 0.99,
        })

        retained, stats = self.decay_engine.prune_incident_edges(edges, as_of_epoch=as_of, max_degree=10)
        self.assertEqual(len(retained), 10)
        self.assertEqual(stats["edges_retained"], 10)
        self.assertEqual(stats["fraud_seeds_preserved"], 2)
        # Fraud seeds must be among the retained items
        retained_ids = [e["txn_id"] for e in retained]
        self.assertIn("TX_FRAUD_OLD_1", retained_ids)
        self.assertIn("TX_FRAUD_OLD_2", retained_ids)

    def test_temporal_isolation_future_transactions(self):
        """Transactions occurring after as_of must receive weight 0.0 and be pruned."""
        as_of = 100_000
        future_txn = self.decay_engine.calculate_edge_weight(epoch_s=150_000, as_of_epoch=as_of)
        self.assertEqual(future_txn["effective_weight"], 0.0)
        self.assertFalse(future_txn["retained"])
        self.assertEqual(future_txn["prune_reason"], "FUTURE_TRANSACTION_TEMPORAL_ISOLATION")

    def test_streaming_prune_simulation_and_api(self):
        """Simulation over store cards and REST API endpoints must execute successfully."""
        sim = self.decay_engine.simulate_streaming_pruning(sample_size=20, max_degree=25)
        self.assertGreater(sim["cards_sampled"], 0)
        self.assertGreater(sim["total_edges_evaluated"], 0)
        self.assertGreaterEqual(sim["memory_reduction_pct"], 0.0)

        # 1. API: /api/graph/edge-decay
        decay_resp = self.api_client.post(
            "/api/graph/edge-decay",
            json={"epoch_s": 10000, "as_of": "50000", "is_fraud": True},
        )
        self.assertEqual(decay_resp.status_code, 200)
        d_data = decay_resp.json()
        self.assertTrue(d_data["retained"])
        self.assertTrue(d_data["is_fraud_immune"])

        # 2. API: /api/graph/streaming-prune
        prune_resp = self.api_client.post(
            "/api/graph/streaming-prune",
            json={"sample_size": 10, "max_degree": 20},
        )
        self.assertEqual(prune_resp.status_code, 200)
        p_data = prune_resp.json()
        self.assertIn("memory_reduction_pct", p_data)
        self.assertIn("graph_compression_ratio", p_data)


if __name__ == "__main__":
    unittest.main()
