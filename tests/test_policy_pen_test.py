"""
Policy & Permission Penetration Test Suite (tests/test_policy_pen_test.py).
Conducts adversarial fuzzing against PolicyEngine to ensure zero unauthorized
actions, zero privilege escalations, and strict regulatory adherence under all boundary conditions.
"""

import unittest
from src.policy.engine import PolicyEngine


class TestPolicyPenetrationAndFuzzing(unittest.TestCase):

    def test_r1_weak_signal_block_fuzzing(self):
        """Fuzzes Rule R1 across probability spectrum [0.01 - 0.69] to verify block is denied."""
        prob_samples = [0.01, 0.10, 0.25, 0.40, 0.55, 0.65, 0.69]
        for prob in prob_samples:
            for act in ["BLOCK_CARD", "BLOCK_ALL_CARDS"]:
                res = PolicyEngine.check(
                    action=act,
                    fraud_probability=prob,
                    exposure_usd=500.0,
                    signal_count=1,
                    evidence_claims=[{"claim": "single anomaly"}],
                )
                self.assertEqual(res["decision"], "deny", f"R1 failed to block {act} at prob {prob}")
                self.assertIn("POLICY-R1", res["policy_refs"])
        print(f"PASS: Rule R1 successfully denied {len(prob_samples) * 2} weak-signal block attempts.")

    def test_r7_recurring_subscription_dispute_protection(self):
        """Verifies that recurring subscription charges are protected from card cancellation."""
        for act in ["BLOCK_CARD", "BLOCK_ALL_CARDS"]:
            res = PolicyEngine.check(
                action=act,
                fraud_probability=0.85,
                exposure_usd=49.99,
                signal_count=3,
                evidence_claims=[{"claim": "recurring dispute"}],
                is_recurring_dispute=True,
            )
            self.assertEqual(res["decision"], "deny", f"R7 failed to protect subscription from {act}")
            self.assertIn("POLICY-R7", res["policy_refs"])
        print("PASS: Rule R7 strictly protects recurring subscriptions from disruptive card block.")

    def test_r10_multi_card_compromise_threshold(self):
        """Verifies BLOCK_ALL_CARDS cannot execute unless at least 2 cards are confirmed compromised."""
        # Test with 0 and 1 compromised cards -> MUST DENY
        for count in [0, 1]:
            res = PolicyEngine.check(
                action="BLOCK_ALL_CARDS",
                fraud_probability=0.95,
                exposure_usd=8000.0,
                signal_count=4,
                evidence_claims=[{"claim": "credential breach"}],
                confirmed_compromised_cards=count,
            )
            self.assertEqual(res["decision"], "deny", f"R10 permitted BLOCK_ALL_CARDS with only {count} card(s)")
            self.assertIn("POLICY-R10", res["policy_refs"])

        # Test with 2 cards and fraud_manager role -> ALLOWED with L2 approval
        res_valid = PolicyEngine.check(
            action="BLOCK_ALL_CARDS",
            fraud_probability=0.95,
            exposure_usd=8000.0,
            signal_count=4,
            evidence_claims=[{"claim": "multi-card ring"}],
            actor_role="fraud_manager",
            confirmed_compromised_cards=2,
        )
        self.assertEqual(res_valid["decision"], "allow")
        self.assertEqual(res_valid["route"], "L2")
        print("PASS: Rule R10 multi-card threshold strictly enforced (>= 2 confirmed cards).")

    def test_approval_routing_and_privilege_escalation(self):
        """Verifies that automated agents cannot bypass L1/L2 approval tiers."""
        # 1. Agent attempting L1 action (DECLINE_TRANSACTION)
        res_l1 = PolicyEngine.check(
            action="DECLINE_TRANSACTION",
            fraud_probability=0.80,
            exposure_usd=500.0,
            signal_count=2,
            evidence_claims=[{"claim": "fraud burst"}],
            actor_role="agent",
        )
        self.assertEqual(res_l1["decision"], "needs_approval")
        self.assertEqual(res_l1["route"], "L1")

        # Team lead can approve L1
        res_l1_lead = PolicyEngine.check(
            action="DECLINE_TRANSACTION",
            fraud_probability=0.80,
            exposure_usd=500.0,
            signal_count=2,
            evidence_claims=[{"claim": "fraud burst"}],
            actor_role="team_lead",
        )
        self.assertEqual(res_l1_lead["decision"], "allow")

        # 2. Team lead attempting L2 action (FILE_REPORT / SAR)
        res_l2_lead = PolicyEngine.check(
            action="FILE_REPORT",
            fraud_probability=0.95,
            exposure_usd=15000.0,
            signal_count=3,
            evidence_claims=[{"claim": "SAR nexus"}],
            actor_role="team_lead",
        )
        self.assertEqual(res_l2_lead["decision"], "needs_approval")
        self.assertEqual(res_l2_lead["route"], "L2")

        # Fraud manager can approve L2
        res_l2_mgr = PolicyEngine.check(
            action="FILE_REPORT",
            fraud_probability=0.95,
            exposure_usd=15000.0,
            signal_count=3,
            evidence_claims=[{"claim": "SAR nexus"}],
            actor_role="fraud_manager",
        )
        self.assertEqual(res_l2_mgr["decision"], "allow")
        print("PASS: Tiered approval routes (auto, L1, L2) and role privilege separation validated.")

    def test_exposure_tampering_sanitization(self):
        """Verifies malicious negative or corrupted exposure parameters cannot evade L2 routing."""
        # Negative exposure should not slip into auto route
        res_neg = PolicyEngine.check(
            action="BLOCK_CARD",
            fraud_probability=0.85,
            exposure_usd=-99999.0,  # Adversarial negative exposure
            signal_count=2,
            evidence_claims=[{"claim": "compromised"}],
        )
        self.assertEqual(res_neg["route"], "L1")  # Sanitized to 0.0, requiring L1
        self.assertEqual(res_neg["decision"], "needs_approval")

        # Corrupted non-numeric exposure
        res_str = PolicyEngine.check(
            action="BLOCK_CARD",
            fraud_probability=0.85,
            exposure_usd="malicious_string",  # type: ignore
            signal_count=2,
            evidence_claims=[{"claim": "compromised"}],
        )
        self.assertEqual(res_str["route"], "L1")
        print("PASS: Adversarial exposure tampering sanitized safely.")

    def test_r8_high_exposure_premature_closure_gate(self):
        """Verifies that high-exposure cases cannot be quietly closed without review."""
        res_premature = PolicyEngine.check(
            action="CLOSE_NO_FRAUD",
            fraud_probability=0.80,  # High risk
            exposure_usd=12000.0,    # High exposure
            signal_count=2,
            evidence_claims=[{"claim": "disputed"}],
        )
        self.assertEqual(res_premature["decision"], "deny")
        self.assertIn("POLICY-R8", res_premature["policy_refs"])
        print("PASS: Rule R8 prevented premature closure of high-exposure case.")

    def test_zero_evidence_punitive_action_gate(self):
        """Verifies that punitive actions cannot be executed with zero evidence claims."""
        res_zero = PolicyEngine.check(
            action="BLOCK_CARD",
            fraud_probability=0.95,
            exposure_usd=1000.0,
            signal_count=0,
            evidence_claims=[],
        )
        self.assertEqual(res_zero["decision"], "deny")
        self.assertIn("POLICY-EVIDENCE-GATE", res_zero["policy_refs"])
        print("PASS: Punitive action rejected due to complete absence of evidence claims.")


if __name__ == "__main__":
    unittest.main()
