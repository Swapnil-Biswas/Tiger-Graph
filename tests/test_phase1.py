"""
Phase 1 Acceptance Tests
Validates graph foundation, row counts, entity resolution, and baseline queries Q1 - Q4.
"""

import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph.client import GraphClient
from src.graph.ingest import GraphStore


class TestPhase1GraphFoundation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing GraphClient for Phase 1 Tests ===")
        cls.client = GraphClient(mode="embedded")
        cls.store = cls.client.store

    def test_01_row_counts_match_source(self):
        """Verify row counts match source datasets."""
        self.assertEqual(len(self.store.transactions), 590742, "Transaction count mismatch")
        self.assertEqual(len(self.store.closed_cases), 5565, "Closed cases count mismatch")
        self.assertEqual(len(self.store.case_pack), 20, "Benchmark cases count mismatch")
        self.assertGreater(len(self.store.cards), 10000, "Cards count lower than expected")
        self.assertGreater(len(self.store.customers), 10000, "Customers count lower than expected")
        print(f"PASS: 590,742 transactions, 5,565 closed cases, 20 benchmark cases verified.")

    def test_02_entity_profile_q1(self):
        """Verify Q1 entity_profile on 5 hand-checked benchmark entities."""
        test_entities = [
            ("C12382-K1", "card"),
            ("C11891-K1", "card"),
            ("C08623-K2", "card"),
            ("C12382", "customer"),
            ("C11891", "customer"),
        ]

        for entity_id, entity_type in test_entities:
            profile = self.client.entity_profile(entity_id, entity_type=entity_type)
            self.assertEqual(profile["entity_id"], entity_id)
            self.assertEqual(profile["entity_type"], entity_type)
            self.assertGreater(profile["txn_count"], 0, f"No transactions found for {entity_id}")
            self.assertGreater(profile["total_spend"], 0.0)
            self.assertIn("median_amount", profile)
            print(f"PASS: Q1 for {entity_type} {entity_id}: txns={profile['txn_count']}, spend=${profile['total_spend']}, median=${profile['median_amount']}")

    def test_03_txn_context_q2(self):
        """Verify Q2 txn_context returns temporal neighborhood and z-score."""
        flagged_txn = "3514030"  # from HHG-001
        ctx = self.client.txn_context(flagged_txn, window_hours=48)
        self.assertEqual(ctx["txn_id"], flagged_txn)
        self.assertIn("prior_count", ctx)
        self.assertIn("amount_z_score", ctx)
        print(f"PASS: Q2 for txn {flagged_txn}: prior_count={ctx['prior_count']}, z_score={ctx['amount_z_score']}")

    def test_04_velocity_q3(self):
        """Verify Q3 velocity burst windows."""
        card_id = "C12382-K1"
        vel = self.client.velocity(card_id, as_of="2016-12-05 01:55:28")
        self.assertIn("5m", vel["windows"])
        self.assertIn("1h", vel["windows"])
        self.assertIn("24h", vel["windows"])
        self.assertIn("7d", vel["windows"])
        print(f"PASS: Q3 for card {card_id}: 1h={vel['windows']['1h']['count']} txns, 24h={vel['windows']['24h']['count']} txns")

    def test_05_device_sharing_q4(self):
        """Verify Q4 device sharing linkage."""
        # Find a device with transactions
        sample_dev = list(self.store.cards_by_device.keys())[0]
        sharing = self.client.device_sharing(sample_dev)
        self.assertIn("distinct_cards_count", sharing)
        self.assertIn("distinct_customers_count", sharing)
        print(f"PASS: Q4 for device '{sample_dev[:40]}...': cards={sharing['distinct_cards_count']}, customers={sharing['distinct_customers_count']}")

    def test_06_subgraph_cytoscape(self):
        """Verify Cytoscape subgraph extraction."""
        subgraph = self.client.get_case_subgraph("HHG-001")
        self.assertGreater(len(subgraph["nodes"]), 0)
        self.assertGreater(len(subgraph["edges"]), 0)
        print(f"PASS: Subgraph for HHG-001 has {len(subgraph['nodes'])} nodes, {len(subgraph['edges'])} edges.")


if __name__ == "__main__":
    unittest.main()
