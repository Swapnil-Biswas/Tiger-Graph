import unittest
from fastapi.testclient import TestClient
from src.cases.manager import CaseManager
from src.graph.client import GraphClient
from src.api.main import app, case_manager


class TestSyndicateMerchantExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case_manager = case_manager
        cls.client = case_manager.client
        cls.api_client = TestClient(app)

    def setUp(self):
        # Create mock cards and transactions in store
        self.card_a = "CARD_SYN_A"
        self.card_b = "CARD_SYN_B"
        self.card_c = "CARD_SYN_C"

        self.client.store.txns_by_card[self.card_a] = [
            {"TransactionID": "TXN_A1", "card_id": self.card_a, "amount": 1200.0, "risk_score": 0.85, "merchant_id": "MERCH_COLLUSIVE_1", "channel": "online", "epoch_s": 1000},
            {"TransactionID": "TXN_A2", "card_id": self.card_a, "amount": 1500.0, "risk_score": 0.75, "merchant_id": "MERCH_COLLUSIVE_2", "channel": "online", "epoch_s": 1050},
            {"TransactionID": "TXN_A3", "card_id": self.card_a, "amount": 80.0, "risk_score": 0.10, "merchant_id": "MERCH_NORMAL_A", "channel": "in_person", "epoch_s": 1100},
        ]
        self.client.store.txns_by_card[self.card_b] = [
            {"TransactionID": "TXN_B1", "card_id": self.card_b, "amount": 2200.0, "risk_score": 0.90, "merchant_id": "MERCH_COLLUSIVE_1", "channel": "online", "epoch_s": 1020},
            {"TransactionID": "TXN_B2", "card_id": self.card_b, "amount": 1800.0, "risk_score": 0.80, "merchant_id": "MERCH_COLLUSIVE_2", "channel": "online", "epoch_s": 1060},
            {"TransactionID": "TXN_B3", "card_id": self.card_b, "amount": 5000.0, "risk_score": 0.95, "merchant_id": "MERCH_FUTURE", "channel": "online", "epoch_s": 5000},
        ]
        self.client.store.txns_by_card[self.card_c] = [
            {"TransactionID": "TXN_C1", "card_id": self.card_c, "amount": 50.0, "risk_score": 0.05, "merchant_id": "MERCH_NORMAL_C", "channel": "in_person", "epoch_s": 1010},
        ]

    def test_multi_card_shared_merchant_collusion(self):
        """Syndicate with 2+ cards transacting at shared high-risk merchants should detect collusion."""
        nexus_id = self.case_manager.register_syndicate_nexus(
            nexus_type="multi_card_ring",
            primary_entity="DEVICE_SHARED_XYZ",
            member_case_id="CASE-SYN-TEST-001",
            card_ids=[self.card_a, self.card_b],
            exposure_usd=6700.0,
        )

        expansion = self.case_manager.expand_syndicate_merchants(nexus_id, as_of=2000)
        self.assertEqual(expansion["nexus_id"], nexus_id)
        self.assertGreaterEqual(expansion["shared_merchants_count"], 2)
        self.assertGreater(expansion["collusion_risk_score"], 0.50)
        self.assertGreater(expansion["collusive_exposure_usd"], 4000.0)

        # Check top collusive merchant details
        top_merch = expansion["collusive_merchants"][0]
        self.assertIn("MERCH_COLLUSIVE", top_merch["merchant_id"])
        self.assertEqual(top_merch["card_count"], 2)
        self.assertIn("MULTI_CARD_SHARED_MERCHANT", top_merch["collusion_indicators"])

    def test_single_card_isolated_no_collusion(self):
        """Nexus with a single card should report zero shared merchants and zero collusion risk."""
        nexus_id = self.case_manager.register_syndicate_nexus(
            nexus_type="isolated_card",
            primary_entity="DEVICE_ISOLATED_999",
            member_case_id="CASE-ISOLATED-001",
            card_ids=[self.card_c],
            exposure_usd=50.0,
        )

        expansion = self.case_manager.expand_syndicate_merchants(nexus_id, as_of=2000)
        self.assertEqual(expansion["shared_merchants_count"], 0)
        self.assertEqual(expansion["collusion_risk_score"], 0.0)
        self.assertEqual(len(expansion["collusive_merchants"]), 0)

    def test_collusive_merchant_graph_edges(self):
        """Expanding syndicate merchants should establish COLLUSIVE_MERCHANT_LINK edges in graph."""
        nexus_id = self.case_manager.register_syndicate_nexus(
            nexus_type="multi_card_ring",
            primary_entity="DEVICE_SHARED_EDGES",
            member_case_id="CASE-EDGE-TEST-001",
            card_ids=[self.card_a, self.card_b],
            exposure_usd=6700.0,
        )

        self.case_manager.expand_syndicate_merchants(nexus_id, as_of=2000)

        # Check graph_case_edges for COLLUSIVE_MERCHANT_LINK
        merch_edges = [
            e for e in self.client.store.graph_case_edges
            if e.get("type") == "COLLUSIVE_MERCHANT_LINK" and e.get("via_nexus") == nexus_id
        ]
        self.assertGreaterEqual(len(merch_edges), 1)
        first_edge = merch_edges[0]
        self.assertEqual(first_edge["from_case"], "CASE-EDGE-TEST-001")
        self.assertIn("MERCH_COLLUSIVE", first_edge["to_merchant"])

    def test_temporal_isolation_as_of(self):
        """Transactions occurring after as_of (e.g., TXN_B3 at epoch 5000) must be strictly isolated."""
        nexus_id = self.case_manager.register_syndicate_nexus(
            nexus_type="multi_card_ring",
            primary_entity="DEVICE_TEMP_ISOLATION",
            member_case_id="CASE-TEMP-TEST-001",
            card_ids=[self.card_a, self.card_b],
            exposure_usd=6700.0,
        )

        # Evaluate as of epoch 2000 (before epoch 5000)
        expansion_past = self.case_manager.expand_syndicate_merchants(nexus_id, as_of=2000)
        merch_ids_past = [m["merchant_id"] for m in expansion_past["collusive_merchants"]]
        self.assertNotIn("MERCH_FUTURE", merch_ids_past)

    def test_case_reconstruction_with_syndicate_collusion(self):
        """Reconstructing a case from graph should include syndicate collusion risk and merchants."""
        answer_bundle = {
            "case_id": "TEST-RECON-SYN-001",
            "case": {
                "status": "closed_fraud",
                "verdict": "fraud",
                "fraud_probability": 0.95,
                "pattern": "ring",
                "exposure_usd": 6700.0,
                "summary": "Multi-card syndicate nexus",
                "connected_card_ids": [self.card_a, self.card_b],
                "connected_device_profiles": ["DEVICE_RECON_PROFILE"],
                "evidence": [{"id": "EV-01", "source": "graph", "ref": "query:ring", "claim": "Shared ring"}],
            },
            "next_best_actions": {
                "final": [{"action": "BLOCK_ALL_CARDS", "route": "L2_LEAD", "reason": "Syndicate"}]
            },
        }
        graph_case_id = self.case_manager.write_case_to_graph(answer_bundle)
        nexus_id = self.client.store.graph_cases[graph_case_id].get("syndicate_nexus_id")
        self.assertIsNotNone(nexus_id)

        # Expand merchants
        self.case_manager.expand_syndicate_merchants(nexus_id, as_of=2000)

        # Reconstruct case
        recon = self.case_manager.reconstruct_case_from_graph("TEST-RECON-SYN-001")
        self.assertIn("syndicate_collusion_risk", recon)
        self.assertIn("collusive_merchants", recon)
        self.assertGreater(recon["syndicate_collusion_risk"], 0.0)

    def test_api_endpoint_syndicate_merchants(self):
        """GET /api/syndicates/{nexus_id}/merchants should return valid merchant expansion JSON."""
        nexus_id = self.case_manager.register_syndicate_nexus(
            nexus_type="multi_card_ring",
            primary_entity="DEVICE_API_TEST",
            member_case_id="CASE-API-TEST-001",
            card_ids=[self.card_a, self.card_b],
            exposure_usd=6700.0,
        )

        resp = self.api_client.get(f"/api/syndicates/{nexus_id}/merchants?as_of=2000")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["nexus_id"], nexus_id)
        self.assertIn("shared_merchants_count", data)
        self.assertIn("collusive_merchants", data)
        self.assertGreater(data["collusion_risk_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
