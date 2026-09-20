"""
Adaptive Graph Budgeter & Traversal Pruning Tests (tests/test_budgeter.py)
Validates dynamic tool budget allocation, pruning of redundant scans,
and execution efficiency across risk tiers.
"""

import unittest
from src.agent.budgeter import AdaptiveGraphBudgeter
from src.agent.graph import FraudInvestigatorAgent


class TestAdaptiveGraphBudgeter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Adaptive Graph Budgeter Test Suite ===")
        cls.agent = FraudInvestigatorAgent()

    def test_01_ambiguous_risk_allocates_exhaustive_tier(self):
        """Validates that ambiguous risk scores (0.40-0.75) receive exhaustive tool budget."""
        trigger = {"trigger_type": "risk_score", "risk_score": 0.61}
        profile = {"txn_count": 50, "total_spend": 2000.0}
        plan = AdaptiveGraphBudgeter.determine_plan(trigger, profile)

        self.assertEqual(plan["budget_tier"], "exhaustive")
        self.assertEqual(plan["max_tool_calls"], 12)
        self.assertTrue(plan["allow_deep_ring_scan"])
        self.assertTrue(plan["allow_geo_dispersion_scan"])
        self.assertTrue(plan["allow_undocumented_detector"])
        print(f"PASS: Ambiguous risk (0.61) allocated exhaustive tier: {plan['prune_rationale']}")

    def test_02_customer_report_allocates_targeted_escalation(self):
        """Validates that customer reports allocate targeted escalation tier."""
        trigger = {"trigger_type": "customer_report", "risk_score": None}
        profile = {"txn_count": 20, "total_spend": 1000.0}
        plan = AdaptiveGraphBudgeter.determine_plan(trigger, profile)

        self.assertEqual(plan["budget_tier"], "targeted_escalation")
        self.assertEqual(plan["max_tool_calls"], 8)
        self.assertTrue(plan["allow_deep_ring_scan"])
        print(f"PASS: Customer report allocated targeted escalation tier: {plan['prune_rationale']}")

    def test_03_low_risk_established_account_fast_path_clearing(self):
        """Validates that low-risk (< 0.30) established accounts get fast-path clearing with pruned scans."""
        trigger = {"trigger_type": "risk_score", "risk_score": 0.15}
        profile = {"txn_count": 45, "total_spend": 3500.0}
        plan = AdaptiveGraphBudgeter.determine_plan(trigger, profile)

        self.assertEqual(plan["budget_tier"], "fast_path_clearing")
        self.assertEqual(plan["max_tool_calls"], 5)
        self.assertFalse(plan["allow_deep_ring_scan"])
        self.assertFalse(plan["allow_geo_dispersion_scan"])
        self.assertFalse(plan["allow_undocumented_detector"])
        print(f"PASS: Low-risk routine account fast-path pruned: {plan['prune_rationale']}")

    def test_04_investigation_attaches_budget_plan(self):
        """Validates that agent.investigate_case attaches active budget_plan to investigation answer."""
        res = self.agent.investigate_case("HHG-001")
        budget = res.get("budget_plan")
        self.assertIsNotNone(budget, "budget_plan was not attached to investigation result")
        self.assertIn("budget_tier", budget)
        self.assertIn("max_tool_calls", budget)
        self.assertIn("prune_rationale", budget)
        print(f"PASS: Case HHG-001 attached budget plan ({budget['budget_tier']}, max_tools={budget['max_tool_calls']}).")


if __name__ == "__main__":
    unittest.main()
