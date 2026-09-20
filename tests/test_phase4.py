"""
Phase 4 Acceptance Tests: Agent Core & Policy Enforcement
Tests end-to-end investigation progression on an ambiguous case, verifying recommendation evolution
(pre vs post evidence), policy route enforcement, and prevention of unauthorized actions.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.graph import FraudInvestigatorAgent
from src.policy.engine import PolicyEngine


class TestPhase4AgentCore(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing FraudInvestigatorAgent for Phase 4 Tests ===")
        cls.agent = FraudInvestigatorAgent()

    def test_01_ambiguous_case_recommendation_change(self):
        """
        Verify that an ambiguous case (HHG-001) produces differing pre_evidence and post_evidence
        recommendations when customer verification is simulated.
        """
        res = self.agent.investigate_case("HHG-001", simulated_scenario="recognizes")
        
        # 1. Evidence request was made
        self.assertGreater(len(res["evidence_requests"]), 0, "No evidence requested for ambiguous case")
        print(f"PASS: Evidence requested: {res['evidence_requests'][0]['type']}")

        # 2. Recommendations evolved
        initial_actions = [a["action"] for a in res["next_best_actions"]["initial"]]
        final_actions = [a["action"] for a in res["next_best_actions"]["final"]]
        what_changed = res["next_best_actions"]["what_changed"]

        print(f"PASS: Initial actions: {initial_actions}")
        print(f"PASS: Final actions: {final_actions}")
        print(f"PASS: What changed: {what_changed}")

        self.assertIn("VERIFY_WITH_CUSTOMER", initial_actions, "Initial did not contain VERIFY_WITH_CUSTOMER")
        self.assertIn("CLOSE_NO_FRAUD", final_actions, "Final did not contain CLOSE_NO_FRAUD after customer recognized")
        self.assertNotEqual(initial_actions, final_actions, "Initial and final actions should differ")
        self.assertNotEqual(what_changed, "nothing", "what_changed should explain the difference")

    def test_02_unauthorized_actions_blocked_by_policy(self):
        """Verify that unauthorized actions are blocked (deny) by the PolicyEngine."""
        # 1. Rule R1: Attempting to BLOCK_CARD on single signal under 0.70
        check_r1 = PolicyEngine.check(
            action="BLOCK_CARD",
            fraud_probability=0.55,
            exposure_usd=100.0,
            signal_count=1,
            evidence_claims=[],
        )
        self.assertEqual(check_r1["decision"], "deny", "Policy did not block single signal block")
        self.assertIn("POLICY-R1", check_r1["policy_refs"])
        print(f"PASS: Rule R1 blocked unauthorized card block: {check_r1['reasons'][0]}")

        # 2. Rule R10: Attempting to BLOCK_ALL_CARDS when only 1 card is compromised
        check_r10 = PolicyEngine.check(
            action="BLOCK_ALL_CARDS",
            fraud_probability=0.90,
            exposure_usd=2000.0,
            signal_count=3,
            evidence_claims=[],
            confirmed_compromised_cards=1,
        )
        self.assertEqual(check_r10["decision"], "deny", "Policy did not block premature BLOCK_ALL_CARDS")
        self.assertIn("POLICY-R10", check_r10["policy_refs"])
        print(f"PASS: Rule R10 blocked unauthorized BLOCK_ALL_CARDS: {check_r10['reasons'][0]}")

    def test_03_approval_routes_enforced(self):
        """Verify approval routes (auto, L1, L2) are correctly assigned."""
        # DECLINE_TRANSACTION -> L1
        self.assertEqual(PolicyEngine.get_approval_route("DECLINE_TRANSACTION"), "L1")
        # BLOCK_CARD <= 2500 -> L1
        self.assertEqual(PolicyEngine.get_approval_route("BLOCK_CARD", exposure_usd=500.0), "L1")
        # BLOCK_CARD > 2500 -> L2
        self.assertEqual(PolicyEngine.get_approval_route("BLOCK_CARD", exposure_usd=3500.0), "L2")
        # FILE_REPORT -> L2
        self.assertEqual(PolicyEngine.get_approval_route("FILE_REPORT"), "L2")
        # ALLOW_TRANSACTION -> auto
        self.assertEqual(PolicyEngine.get_approval_route("ALLOW_TRANSACTION"), "auto")
        print("PASS: Approval routes auto, L1, L2 accurately assigned across exposure tiers.")


if __name__ == "__main__":
    unittest.main()
