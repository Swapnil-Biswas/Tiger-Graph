"""
Phase 5 Acceptance Tests: Case Persistence & Citation Validation
Tests that:
1. An investigation case is 100% reconstructable from graph vertices and edges alone.
2. The explanation validator strictly rejects fabricated citation IDs.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.graph import FraudInvestigatorAgent
from src.cases.manager import CaseManager
from src.agent.explainer_validator import CitationValidator


class TestPhase5CasePersistenceAndValidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing TestPhase5CasePersistenceAndValidation ===")
        cls.agent = FraudInvestigatorAgent()
        cls.manager = CaseManager(client=cls.agent.client)

    def test_01_case_reconstructable_from_graph_alone(self):
        """Verify case is completely persisted and reconstructable from graph vertices."""
        # 1. Run investigation for HHG-002
        case_result = self.agent.investigate_case("HHG-002")
        
        # 2. Persist to graph
        graph_id = self.manager.write_case_to_graph(case_result)
        self.assertEqual(graph_id, "CASE-HHG-002")
        print(f"PASS: Case HHG-002 persisted to graph as vertex '{graph_id}'")

        # 3. Reconstruct from graph
        reconstructed = self.manager.reconstruct_case_from_graph("HHG-002")
        
        self.assertEqual(reconstructed["case_id"], "HHG-002")
        self.assertEqual(reconstructed["verdict"], case_result["case"]["verdict"])
        self.assertEqual(reconstructed["pattern"], case_result["case"]["pattern"])
        self.assertEqual(reconstructed["exposure_usd"], case_result["case"]["exposure_usd"])
        self.assertEqual(len(reconstructed["evidence"]), len(case_result["case"]["evidence"]))
        self.assertEqual(len(reconstructed["actions"]), len(case_result["next_best_actions"]["final"]))
        print(f"PASS: Case HHG-002 100% reconstructed from graph alone ({len(reconstructed['evidence'])} evidence items, {len(reconstructed['actions'])} actions).")

    def test_02_explanation_validator_rejects_fabricated_ids(self):
        """Verify that explanation validator detects and strips fabricated evidence IDs."""
        valid_ev_ids = ["EV-01", "EV-02", "EV-03"]
        valid_policy_ids = ["POLICY-R1", "POLICY-R5"]

        # Valid text
        valid_text = "Based on EV-01 and EV-02 under POLICY-R1, verify customer before blocking."
        is_valid, valid_found, fab_found = CitationValidator.validate_citations(
            valid_text, valid_ev_ids, valid_policy_ids
        )
        self.assertTrue(is_valid)
        self.assertEqual(len(fab_found), 0)
        self.assertEqual(set(valid_found), {"EV-01", "EV-02", "POLICY-R1"})
        print("PASS: Legitimate citations accepted.")

        # Fabricated text
        fake_text = "Based on EV-01 and fabricated EV-99 under fake POLICY-FABRICATED, block card."
        is_valid2, valid_found2, fab_found2 = CitationValidator.validate_citations(
            fake_text, valid_ev_ids, valid_policy_ids
        )
        self.assertFalse(is_valid2, "Validator failed to flag fabricated citations")
        self.assertIn("EV-99", fab_found2)
        self.assertIn("POLICY-FABRICATED", fab_found2)
        print(f"PASS: Fabricated citations flagged: {fab_found2}")

        # Sanitize text
        sanitized = CitationValidator.sanitize_explanation(fake_text, valid_ev_ids, valid_policy_ids)
        self.assertNotIn("EV-99", sanitized)
        self.assertNotIn("POLICY-FABRICATED", sanitized)
        self.assertIn("[INVALID_CITATION_REMOVED]", sanitized)
        print(f"PASS: Sanitized output safely removed fabricated citations.")


if __name__ == "__main__":
    unittest.main()
