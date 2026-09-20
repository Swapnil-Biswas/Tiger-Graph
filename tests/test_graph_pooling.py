"""
Unit Tests for Temporal Graph Attention Subgraph Pooling (tests/test_graph_pooling.py)
Validates fixed-dimensional embedding generation (9D / 27D), softmax attention properties,
temporal recency decay, fraud precedent boosting, and API endpoints.
"""

import unittest
import time
from fastapi.testclient import TestClient
from src.graph.client import GraphClient
from src.graph.embeddings import TopologicalGraphEmbeddingExporter, TemporalGraphAttentionPooler
from src.api.main import app


class TestTemporalGraphPooling(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Temporal Graph Pooling Test Suite ===")
        cls.client = GraphClient(mode="embedded")
        cls.exporter = TopologicalGraphEmbeddingExporter(cls.client)
        cls.pooler = TemporalGraphAttentionPooler(cls.client)
        cls.api_client = TestClient(app)

    def test_01_feature_dimensions_concordance(self):
        """Pooled embedding vectors strictly conform to 9D and 27D shapes."""
        card_id = "C00259-K1"
        pyg_data = self.exporter.extract_gnn_subgraph(card_id, as_of="2017-06-01 00:00:00")
        res = self.pooler.pool_subgraph(pyg_data, as_of="2017-06-01 00:00:00")

        self.assertEqual(res["feature_dim"], 9)
        self.assertEqual(res["pooled_dim"], 27)
        self.assertEqual(len(res["pooled_attention_embedding"]), 9)
        self.assertEqual(len(res["pooled_mean_embedding"]), 9)
        self.assertEqual(len(res["pooled_max_embedding"]), 9)
        self.assertEqual(len(res["concatenated_embedding"]), 27)
        self.assertGreater(res["subgraph_size"], 0)
        print(f"PASS: Dimensions validated: feat_dim={res['feature_dim']}, pooled_dim={res['pooled_dim']}, N={res['subgraph_size']}.")

    def test_02_attention_weights_softmax_property(self):
        """Attention weights across all subgraph nodes sum to approximately 1.0."""
        card_id = "C12382-K1"
        pyg_data = self.exporter.extract_gnn_subgraph(card_id, as_of="2017-06-01 00:00:00")
        res = self.pooler.pool_subgraph(pyg_data, as_of="2017-06-01 00:00:00")

        weights = list(res["attention_weights"].values())
        total_weight = sum(weights)
        self.assertAlmostEqual(total_weight, 1.0, places=3, msg="Softmax attention weights must sum to 1.0")
        self.assertTrue(all(0.0 <= w <= 1.0 for w in weights))
        print(f"PASS: Softmax property verified: sum(alpha)={total_weight:.4f}, min={min(weights):.4f}, max={max(weights):.4f}.")

    def test_03_temporal_recency_decay_effect(self):
        """Increasing decay_lambda concentrates attention onto more recent nodes."""
        card_id = "C00259-K1"
        pyg_data = self.exporter.extract_gnn_subgraph(card_id, as_of="2017-06-01 00:00:00")

        # Zero decay (pure feature attention)
        res_no_decay = self.pooler.pool_subgraph(pyg_data, as_of="2017-06-01 00:00:00", decay_lambda=0.0)
        # Strong decay (favors recent nodes)
        res_decay = self.pooler.pool_subgraph(pyg_data, as_of="2017-06-01 00:00:00", decay_lambda=0.15)

        self.assertNotEqual(res_no_decay["pooled_attention_embedding"], res_decay["pooled_attention_embedding"])
        print("PASS: Temporal recency decay altered attention distribution as expected.")

    def test_04_fraud_precedent_attention_boost(self):
        """Confirmed fraud precedent nodes receive high attention weights."""
        card_id = "C00259-K1"
        pyg_data = self.exporter.extract_gnn_subgraph(card_id, as_of="2017-06-01 00:00:00")
        res = self.pooler.pool_subgraph(pyg_data, as_of="2017-06-01 00:00:00")

        top_node = res["top_attention_nodes"][0]
        self.assertEqual(top_node["node_id"], f"CARD:{card_id}")
        self.assertGreater(top_node["attention_weight"], 0.50)
        print(f"PASS: Top attention node correctly identified: {top_node['node_id']} (weight: {top_node['attention_weight']}).")

    def test_05_execution_latency_sub_5ms(self):
        """Graph attention pooling executes in under 5ms."""
        card_id = "C12382-K1"
        pyg_data = self.exporter.extract_gnn_subgraph(card_id, as_of="2017-06-01 00:00:00")

        t0 = time.perf_counter()
        res = self.pooler.pool_subgraph(pyg_data, as_of="2017-06-01 00:00:00")
        latency_ms = (time.perf_counter() - t0) * 1000.0

        self.assertLess(latency_ms, 5.0, f"Latency {latency_ms:.2f}ms exceeds 5ms threshold")
        print(f"PASS: Pooling execution latency: {latency_ms:.2f}ms (reported: {res['elapsed_ms']}ms).")

    def test_06_api_endpoints_integration(self):
        """API endpoints GET /api/cases/{id}/embedding and POST /api/graph/pool-embedding operate correctly."""
        # Test GET /api/cases/HHG-001/embedding
        resp = self.api_client.get("/api/cases/HHG-001/embedding")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("embedding", data)
        self.assertEqual(data["case_id"], "HHG-001")
        self.assertEqual(data["embedding"]["pooled_dim"], 27)

        # Test POST /api/graph/pool-embedding
        post_resp = self.api_client.post(
            "/api/graph/pool-embedding",
            json={"seed_id": "C00259-K1", "entity_type": "card", "as_of": "2017-06-01 00:00:00"},
        )
        self.assertEqual(post_resp.status_code, 200)
        post_data = post_resp.json()
        self.assertEqual(post_data["feature_dim"], 9)
        self.assertEqual(post_data["pooled_dim"], 27)
        print("PASS: Embedding pooling API endpoints verified successfully.")
