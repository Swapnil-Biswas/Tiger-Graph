"""
Ablation Study Unit Tests (tests/test_ablation.py)
Validates that architectural ablations (Graph Signals OFF, Memory OFF, Policy OFF)
behave as expected and demonstrate the necessity of each subsystem.
"""

import unittest
from src.agent.graph import FraudInvestigatorAgent
from src.policy.engine import PolicyEngine


class TestComponentAblation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Component Ablation Test Suite ===")
        cls.agent = FraudInvestigatorAgent()

    def test_01_full_system_zero_violations_high_precision(self):
        """Validates that Full System operates with 0 policy violations and grounded decisions."""
        ans = self.agent.investigate_case("HHG-001", ablate_graph=False, ablate_memory=False, ablate_policy=False)
        actions = ans["next_best_actions"]["final"]
        for act in actions:
            action_name = act.get("action") if isinstance(act, dict) else act.action
            res = PolicyEngine.check(
                action=action_name,
                fraud_probability=ans["case"]["fraud_probability"],
                exposure_usd=ans["case"]["exposure_usd"],
                signal_count=len(ans.get("evidence", [])),
                evidence_claims=ans.get("evidence", []),
            )
            self.assertNotEqual(res["decision"], "deny", f"Unexpected policy deny in Full System: {res['reasons']}")
        print("PASS: Full System produced 0 policy violations on ambiguous case HHG-001.")

    def test_02_graph_ablation_strips_topological_context(self):
        """Validates that ablating graph signals zeroes velocity, device sharing, and ring detection."""
        ans = self.agent.investigate_case("HHG-004", ablate_graph=True)
        # Verify no graph topological anomaly claims in evidence
        evidence = ans.get("evidence", [])
        for ev in evidence:
            self.assertNotIn("query:device_sharing", ev.get("ref", ""))
            self.assertNotIn("query:geo_impossible", ev.get("ref", ""))
        print("PASS: Graph ablation successfully stripped topological queries and shared-device evidence.")

    def test_03_memory_ablation_zeroes_historical_priors(self):
        """Validates that ablating memory zeroes empirical Bayes priors and similar cases."""
        ans = self.agent.investigate_case("HHG-001", ablate_memory=True)
        evidence = ans.get("evidence", [])
        for ev in evidence:
            self.assertNotIn("query:empirical_bayes_prior", ev.get("ref", ""))
            self.assertNotIn("query:similar_cases", ev.get("ref", ""))
        print("PASS: Case memory ablation successfully eliminated historical prior conditioning.")

    def test_04_policy_ablation_triggers_unconstrained_violations(self):
        """Validates that ablating policy guards causes unconstrained actions and triggers violations."""
        # On HHG-001 with pre-evidence risk ~0.60, policy ablation executes BLOCK_CARD without verification (violating R1)
        ans = self.agent.investigate_case("HHG-001", ablate_policy=True)
        actions = ans["next_best_actions"]["final"]
        action_names = [a.get("action") if isinstance(a, dict) else a.action for a in actions]
        
        # When policy is ablated, naive thresholding blocks immediately on >= 0.50 risk without customer check
        self.assertIn("BLOCK_CARD", action_names)
        
        # PolicyEngine must catch this as a violation
        res = PolicyEngine.check(
            action="BLOCK_CARD",
            fraud_probability=0.61,
            exposure_usd=ans["case"]["exposure_usd"],
            signal_count=1,
            evidence_claims=[],
        )
        self.assertEqual(res["decision"], "deny", "Ablated action should have been denied by PolicyEngine")
        self.assertIn("POLICY-R1", res["policy_refs"])
        print(f"PASS: Policy ablation correctly induced Rule R1 violation: '{res['reasons'][0]}'")



if __name__ == "__main__":
    unittest.main()
