import unittest
from fastapi.testclient import TestClient
from src.agent.refiner import GraphAugmentedSelfRefiner
from src.api.main import app, agent


class TestGraphAugmentedSelfRefiner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refiner = GraphAugmentedSelfRefiner(max_refinements=3)
        cls.api_client = TestClient(app)

    def test_consistent_investigation_no_refinements(self):
        """A structurally sound case answer should require 0 refinements and achieve consistency score 1.0."""
        valid_answer = {
            "case": {
                "verdict": "legitimate",
                "fraud_probability": 0.08,
                "exposure_usd": 120.0,
                "pattern": "none",
            },
            "actions": {
                "final": [
                    {"action": "ALLOW_TRANSACTION", "route": "auto", "reason": "Authorized charge."},
                    {"action": "CLOSE_NO_FRAUD", "route": "auto", "reason": "No anomaly detected."},
                ],
                "what_changed": "customer confirmed transaction",
            },
            "sar": {"file": False},
        }

        refined = self.refiner.refine_investigation(valid_answer)
        ref_meta = refined["self_refinement"]
        self.assertEqual(ref_meta["refinements_applied_count"], 0)
        self.assertTrue(ref_meta["converged"])
        self.assertEqual(ref_meta["structural_consistency_score"], 1.0)
        self.assertEqual(len(ref_meta["remaining_violations"]), 0)

    def test_refine_weak_signal_punitive_block(self):
        """Single weak signal (prob < 0.70) cannot execute BLOCK_CARD; refiner must replace with STEP_UP_AUTH."""
        premature_block_answer = {
            "case": {
                "verdict": "uncertain",
                "fraud_probability": 0.55,
                "exposure_usd": 250.0,
                "pattern": "none",
            },
            "actions": {
                "final": [
                    {"action": "BLOCK_CARD", "route": "auto", "reason": "Weak signal block attempt."},
                ],
                "what_changed": "",
            },
            "sar": {"file": False},
        }

        refined = self.refiner.refine_investigation(premature_block_answer)
        ref_meta = refined["self_refinement"]
        self.assertEqual(ref_meta["refinements_applied_count"], 1)
        self.assertTrue(ref_meta["converged"])
        actions = [a["action"] for a in refined["actions"]["final"]]
        self.assertNotIn("BLOCK_CARD", actions)
        self.assertIn("STEP_UP_AUTH", actions)

    def test_refine_unauthorized_multi_card_block(self):
        """BLOCK_ALL_CARDS on a single card case must be downgraded to BLOCK_CARD per Rule R10."""
        overreaching_answer = {
            "case": {
                "verdict": "fraud",
                "fraud_probability": 0.95,
                "exposure_usd": 800.0,
                "confirmed_compromised_cards": 1,
            },
            "actions": {
                "final": [
                    {"action": "BLOCK_ALL_CARDS", "route": "auto", "reason": "Excessive multi-card block."},
                ],
                "what_changed": "customer denied transaction",
            },
            "sar": {"file": False},
        }

        refined = self.refiner.refine_investigation(overreaching_answer)
        ref_meta = refined["self_refinement"]
        self.assertEqual(ref_meta["refinements_applied_count"], 1)
        actions = [a["action"] for a in refined["actions"]["final"]]
        self.assertNotIn("BLOCK_ALL_CARDS", actions)
        self.assertIn("BLOCK_CARD", actions)

    def test_refine_customer_denial_contradiction(self):
        """Customer denial of transaction strictly mandates fraud verdict and BLOCK_CARD."""
        contradictory_answer = {
            "case": {
                "verdict": "uncertain",
                "fraud_probability": 0.60,
                "exposure_usd": 500.0,
            },
            "actions": {
                "final": [
                    {"action": "MONITOR_CARD", "route": "auto", "reason": "Under-reaction to denial."},
                ],
                "what_changed": "customer denied transaction",
            },
            "sar": {"file": False},
        }

        refined = self.refiner.refine_investigation(contradictory_answer)
        self.assertEqual(refined["case"]["verdict"], "fraud")
        self.assertGreaterEqual(refined["case"]["fraud_probability"], 0.95)
        actions = [a["action"] for a in refined["actions"]["final"]]
        self.assertIn("BLOCK_CARD", actions)
        self.assertIn("DECLINE_TRANSACTION", actions)

    def test_refine_recurring_subscription_protection(self):
        """Disputed recurring charge requires WARN_CUSTOMER before punitive card block."""
        disputed_sub_answer = {
            "case": {
                "verdict": "uncertain",
                "fraud_probability": 0.40,
                "exposure_usd": 29.99,
            },
            "actions": {
                "final": [
                    {"action": "BLOCK_CARD", "route": "auto", "reason": "Disruptive block on subscription."},
                ],
                "what_changed": "recurring subscription disputed by customer",
            },
            "sar": {"file": False},
        }

        refined = self.refiner.refine_investigation(disputed_sub_answer)
        actions = [a["action"] for a in refined["actions"]["final"]]
        self.assertNotIn("BLOCK_CARD", actions)
        self.assertIn("WARN_CUSTOMER", actions)

    def test_refine_high_exposure_uncertain_escalation(self):
        """High financial exposure (> $1,000) under uncertain evaluation requires L2_LEAD escalation."""
        high_exposure_answer = {
            "case": {
                "verdict": "uncertain",
                "fraud_probability": 0.50,
                "exposure_usd": 3500.0,
            },
            "actions": {
                "final": [
                    {"action": "CREATE_CASE", "route": "auto", "reason": "Standard case creation."},
                ],
                "what_changed": "cardholder inquiry pending",
            },
            "sar": {"file": False},
        }

        refined = self.refiner.refine_investigation(high_exposure_answer)
        routes = [a["route"] for a in refined["actions"]["final"]]
        self.assertIn("L2_LEAD", routes)

    def test_rest_api_endpoint_self_refine(self):
        """POST /api/agent/self-refine must execute successfully and return refined structure."""
        req_payload = {
            "answer": {
                "case": {"verdict": "legitimate", "fraud_probability": 0.10, "exposure_usd": 50.0},
                "actions": {
                    "final": [{"action": "ALLOW_TRANSACTION", "route": "auto"}],
                    "what_changed": "customer confirmed transaction",
                },
                "sar": {"file": False},
            },
            "max_refinements": 3,
        }

        resp = self.api_client.post("/api/agent/self-refine", json=req_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("self_refinement", data)
        self.assertEqual(data["self_refinement"]["structural_consistency_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
