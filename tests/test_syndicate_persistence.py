"""
Cross-Case Syndicate Nexus & Graph Persistence Tests (tests/test_syndicate_persistence.py).
Validates multi-case ring linking, aggregate exposure tracking, and cross-case graph edges.
"""

import unittest
from src.agent.graph import FraudInvestigatorAgent
from src.cases.manager import CaseManager


class TestSyndicateNexusGraphPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Syndicate Persistence Test Suite ===")
        cls.agent = FraudInvestigatorAgent()
        cls.manager = CaseManager(client=cls.agent.client)

    def test_01_syndicate_nexus_creation_and_cross_case_linking(self):
        """Validates that shared device profiles create a unified SyndicateNexus and cross-case links."""
        # Case A: Syndicate alert on HHG-004
        res_a = self.agent.investigate_case("HHG-004")
        graph_id_a = self.manager.write_case_to_graph(res_a)
        self.assertEqual(graph_id_a, "CASE-HHG-004")

        rec_a = self.manager.reconstruct_case_from_graph("HHG-004")
        nexus_id_a = rec_a.get("syndicate_nexus_id")
        self.assertIsNotNone(nexus_id_a, "SyndicateNexus was not created for HHG-004")
        self.assertTrue(nexus_id_a.startswith("NEXUS-"))

        # Inspect initial dossier
        dossier_initial = self.manager.get_syndicate_dossier(nexus_id_a)
        self.assertIsNotNone(dossier_initial)
        self.assertIn("CASE-HHG-004", dossier_initial["member_cases"])
        initial_exposure = dossier_initial["total_exposure_usd"]

        # Case B: Synthesize another case sharing the exact same device profile
        shared_dev = res_a["case"]["connected_device_profiles"][0] if res_a["case"]["connected_device_profiles"] else "DEV-SHARED-TEST"
        res_b = {
            "case_id": "SYN-TEST-002",
            "case": {
                "status": "closed",
                "verdict": "fraud",
                "fraud_probability": 0.95,
                "pattern": "undocumented",
                "pattern_description": "Organized device nexus test",
                "exposure_usd": 6500.0,
                "first_suspicious_txn_id": "9999991",
                "connected_card_ids": ["CARD-EXTRA-01", "CARD-EXTRA-02"],
                "connected_device_profiles": [shared_dev],
                "similar_prior_cases": ["CC-001"],
                "affected_txn_ids": ["9999991"],
                "evidence": [{"id": "EV-01", "source": "graph", "ref": "query:test", "claim": "shared device"}],
                "summary": "Synthesized syndicate test case",
            },
            "next_best_actions": {
                "final": [{"action": "BLOCK_ALL_CARDS", "route": "L2", "reason": "Syndicate nexus confirmed"}]
            }
        }
        graph_id_b = self.manager.write_case_to_graph(res_b)
        self.assertEqual(graph_id_b, "CASE-SYN-TEST-002")

        rec_b = self.manager.reconstruct_case_from_graph("SYN-TEST-002")
        nexus_id_b = rec_b.get("syndicate_nexus_id")
        self.assertEqual(nexus_id_a, nexus_id_b, "Cases sharing identical device did not join same SyndicateNexus")

        # Verify updated dossier aggregates exposure and members
        dossier_updated = self.manager.get_syndicate_dossier(nexus_id_a)
        self.assertIn("CASE-HHG-004", dossier_updated["member_cases"])
        self.assertIn("CASE-SYN-TEST-002", dossier_updated["member_cases"])
        self.assertGreater(dossier_updated["total_exposure_usd"], initial_exposure)
        self.assertGreaterEqual(len(dossier_updated["member_cards"]), 2)
        print(f"PASS: SyndicateNexus {nexus_id_a} aggregated 2 cases, exposure: ${dossier_updated['total_exposure_usd']:.2f}, threat: {dossier_updated['threat_level']}")

        # Verify Bidirectional Cross-Case Links
        links_a = self.manager.get_cross_case_links("HHG-004")
        links_b = self.manager.get_cross_case_links("SYN-TEST-002")
        self.assertTrue(any(l["connected_case_id"] == "CASE-SYN-TEST-002" for l in links_a))
        self.assertTrue(any(l["connected_case_id"] == "CASE-HHG-004" for l in links_b))
        print("PASS: Bidirectional cross-case edges verified between CASE-HHG-004 and CASE-SYN-TEST-002.")

    def test_02_isolated_case_has_no_spurious_cross_links(self):
        """Validates that a legitimate isolated case does not link to unrelated syndicates."""
        res_iso = {
            "case_id": "ISO-001",
            "case": {
                "status": "closed",
                "verdict": "legitimate",
                "fraud_probability": 0.05,
                "pattern": "none",
                "exposure_usd": 0.0,
                "connected_card_ids": ["CARD-CLEAN-99"],
                "connected_device_profiles": [],
                "evidence": [],
                "summary": "Clean isolated account",
            },
            "next_best_actions": {
                "final": [{"action": "CLOSE_NO_FRAUD", "route": "auto", "reason": "Legitimate"}]
            }
        }
        self.manager.write_case_to_graph(res_iso)
        links = self.manager.get_cross_case_links("ISO-001")
        self.assertEqual(len(links), 0, "Clean case unexpectedly received cross-case links")
        print("PASS: Clean isolated case has zero spurious cross-case links.")


if __name__ == "__main__":
    unittest.main()
