import unittest
from fastapi.testclient import TestClient
from src.graph.client import GraphClient
from src.graph.algorithms import TemporalSubgraphMotifMiner
from src.api.main import app, agent, case_manager


class TestGraphMotifs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = agent.client
        cls.miner = TemporalSubgraphMotifMiner(cls.client)
        cls.api_client = TestClient(app)

    def test_isolated_card_no_motifs(self):
        """Isolated card with 1-2 transactions at a single merchant should have 0 motifs."""
        card_id = "card_isolated_motif_001"
        self.client.store.txns_by_card[card_id] = [
            {"transaction_id": "tx_iso_1", "card_id": card_id, "merchant": "M_GROCERY", "amount": 25.0, "epoch_s": 10000},
            {"transaction_id": "tx_iso_2", "card_id": card_id, "merchant": "M_GROCERY", "amount": 30.0, "epoch_s": 25000},
        ]
        res = self.miner.mine_motifs(seed_id=card_id, entity_type="card", as_of=30000, window_hours=72.0)
        self.assertEqual(res["total_motifs_count"], 0)
        self.assertEqual(res["anomaly_score"], 0.0)
        self.assertEqual(res["threat_level"], "none")
        self.assertEqual(res["dominant_motif"], "none")

    def test_fan_out_star_motif(self):
        """Card dispersing transactions to >= 4 distinct merchants within the window triggers fan_out_star."""
        card_id = "card_fan_out_002"
        self.client.store.txns_by_card[card_id] = [
            {"transaction_id": "tx_fo_1", "card_id": card_id, "merchant": "M_ELECTRO", "amount": 100.0, "epoch_s": 10000},
            {"transaction_id": "tx_fo_2", "card_id": card_id, "merchant": "M_LUXURY", "amount": 250.0, "epoch_s": 12000},
            {"transaction_id": "tx_fo_3", "card_id": card_id, "merchant": "M_CRYPTO", "amount": 400.0, "epoch_s": 14000},
            {"transaction_id": "tx_fo_4", "card_id": card_id, "merchant": "M_GAS", "amount": 50.0, "epoch_s": 16000},
        ]
        res = self.miner.mine_motifs(seed_id=card_id, entity_type="card", as_of=20000, window_hours=72.0)
        self.assertGreaterEqual(res["motif_counts"]["fan_out_star"], 1)
        self.assertEqual(res["dominant_motif"], "fan_out_star")
        self.assertGreaterEqual(res["anomaly_score"], 0.20)
        star = res["motifs"]["fan_out_star"][0]
        self.assertEqual(star["card_id"], card_id)
        self.assertGreaterEqual(star["merchant_count"], 4)

    def test_fan_in_hub_motif(self):
        """Single merchant receiving transactions from >= 3 distinct cards in local subgraph triggers fan_in_hub."""
        target_card = "card_hub_target_003"
        peer_card_1 = "card_hub_peer_003a"
        peer_card_2 = "card_hub_peer_003b"
        device_id = "dev_shared_hub_003"

        # Link cards to device
        self.client.store.devices_by_card[target_card].add(device_id)
        self.client.store.devices_by_card[peer_card_1].add(device_id)
        self.client.store.devices_by_card[peer_card_2].add(device_id)
        self.client.store.cards_by_device[device_id].update([target_card, peer_card_1, peer_card_2])

        # All 3 cards funnel into M_LIQUIDATE
        self.client.store.txns_by_card[target_card] = [
            {"transaction_id": "tx_hub_1", "card_id": target_card, "merchant": "M_LIQUIDATE", "amount": 500.0, "epoch_s": 10000}
        ]
        self.client.store.txns_by_card[peer_card_1] = [
            {"transaction_id": "tx_hub_2", "card_id": peer_card_1, "merchant": "M_LIQUIDATE", "amount": 750.0, "epoch_s": 10500}
        ]
        self.client.store.txns_by_card[peer_card_2] = [
            {"transaction_id": "tx_hub_3", "card_id": peer_card_2, "merchant": "M_LIQUIDATE", "amount": 900.0, "epoch_s": 11000}
        ]

        res = self.miner.mine_motifs(seed_id=target_card, entity_type="card", as_of=15000, window_hours=72.0)
        self.assertGreaterEqual(res["motif_counts"]["fan_in_hub"], 1)
        hub = res["motifs"]["fan_in_hub"][0]
        self.assertEqual(hub["merchant_id"], "M_LIQUIDATE")
        self.assertEqual(hub["card_count"], 3)
        self.assertIn(target_card, hub["cards"])

    def test_bipartite_mesh_motif(self):
        """Two cards sharing >= 2 merchants within the window triggers bipartite_mesh."""
        c1 = "card_mesh_004a"
        c2 = "card_mesh_004b"
        dev = "dev_mesh_004"

        self.client.store.devices_by_card[c1].add(dev)
        self.client.store.devices_by_card[c2].add(dev)
        self.client.store.cards_by_device[dev].update([c1, c2])

        # Both transacting at M_TEST_1 and M_TEST_2
        self.client.store.txns_by_card[c1] = [
            {"transaction_id": "tx_m_1", "card_id": c1, "merchant": "M_TEST_1", "amount": 10.0, "epoch_s": 10000},
            {"transaction_id": "tx_m_2", "card_id": c1, "merchant": "M_TEST_2", "amount": 15.0, "epoch_s": 10200},
        ]
        self.client.store.txns_by_card[c2] = [
            {"transaction_id": "tx_m_3", "card_id": c2, "merchant": "M_TEST_1", "amount": 12.0, "epoch_s": 10400},
            {"transaction_id": "tx_m_4", "card_id": c2, "merchant": "M_TEST_2", "amount": 18.0, "epoch_s": 10600},
        ]

        res = self.miner.mine_motifs(seed_id=c1, entity_type="card", as_of=15000, window_hours=72.0)
        self.assertGreaterEqual(res["motif_counts"]["bipartite_mesh"], 1)
        mesh = res["motifs"]["bipartite_mesh"][0]
        self.assertEqual(mesh["merchant_count"], 2)
        self.assertIn("M_TEST_1", mesh["shared_merchants"])
        self.assertIn("M_TEST_2", mesh["shared_merchants"])

    def test_temporal_chain_and_sharing_triangle(self):
        """Rapid consecutive transactions (<= 7200s) trigger temporal_chain, and device-sharing merchant overlap triggers sharing_triangle."""
        c1 = "card_tc_005a"
        c2 = "card_tc_005b"
        dev = "dev_tc_005"

        self.client.store.devices_by_card[c1].add(dev)
        self.client.store.devices_by_card[c2].add(dev)
        self.client.store.cards_by_device[dev].update([c1, c2])

        # Rapid chain of 3 transactions on c1
        self.client.store.txns_by_card[c1] = [
            {"transaction_id": "tx_tc_1", "card_id": c1, "merchant": "M_SHARED_TRI", "amount": 50.0, "epoch_s": 1000},
            {"transaction_id": "tx_tc_2", "card_id": c1, "merchant": "M_SHARED_TRI", "amount": 60.0, "epoch_s": 2000},
            {"transaction_id": "tx_tc_3", "card_id": c1, "merchant": "M_SHARED_TRI", "amount": 70.0, "epoch_s": 3000},
        ]
        # c2 also transacting at M_SHARED_TRI
        self.client.store.txns_by_card[c2] = [
            {"transaction_id": "tx_tc_4", "card_id": c2, "merchant": "M_SHARED_TRI", "amount": 80.0, "epoch_s": 4000},
        ]

        res = self.miner.mine_motifs(seed_id=c1, entity_type="card", as_of=5000, window_hours=72.0)
        self.assertGreaterEqual(res["motif_counts"]["temporal_chain"], 1)
        self.assertGreaterEqual(res["motif_counts"]["sharing_triangle"], 1)
        chain = res["motifs"]["temporal_chain"][0]
        self.assertEqual(chain["chain_length"], 3)
        tri = res["motifs"]["sharing_triangle"][0]
        self.assertEqual(tri["device_id"], dev)
        self.assertEqual(tri["merchant_id"], "M_SHARED_TRI")

    def test_temporal_isolation_and_api(self):
        """Future transactions must be isolated, and REST API endpoints must return valid responses."""
        card_id = "card_api_motif_006"
        self.client.store.txns_by_card[card_id] = [
            {"transaction_id": "tx_iso_past", "card_id": card_id, "merchant": "M_PAST", "amount": 10.0, "epoch_s": 1000},
            # Future transactions that should NOT be visible at as_of=2000
            {"transaction_id": "tx_iso_future1", "card_id": card_id, "merchant": "M_FUT1", "amount": 20.0, "epoch_s": 5000},
            {"transaction_id": "tx_iso_future2", "card_id": card_id, "merchant": "M_FUT2", "amount": 30.0, "epoch_s": 6000},
            {"transaction_id": "tx_iso_future3", "card_id": card_id, "merchant": "M_FUT3", "amount": 40.0, "epoch_s": 7000},
            {"transaction_id": "tx_iso_future4", "card_id": card_id, "merchant": "M_FUT4", "amount": 50.0, "epoch_s": 8000},
        ]

        # Prior to epoch 2000, only 1 transaction exists -> 0 motifs
        res_past = self.miner.mine_motifs(seed_id=card_id, entity_type="card", as_of=2000, window_hours=72.0)
        self.assertEqual(res_past["total_motifs_count"], 0)

        # Direct API test
        resp = self.api_client.post(
            "/api/graph/motifs-check",
            json={"seed_id": card_id, "entity_type": "card", "as_of": "2000", "window_hours": 72.0},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["seed_id"], card_id)
        self.assertEqual(data["total_motifs_count"], 0)
        self.assertEqual(data["threat_level"], "none")


if __name__ == "__main__":
    unittest.main()
