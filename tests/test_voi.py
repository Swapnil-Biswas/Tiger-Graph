"""
Unit Tests for Evidence Value of Information (VOI) Engine
Verifies Shannon entropy calculations and cost-benefit inquiry ranking.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.voi import ValueOfInformationEngine, binary_entropy
from src.agent.state import Assessment, Hypothesis


class TestValueOfInformationEngine(unittest.TestCase):

    def test_01_entropy_properties(self):
        """Verify binary Shannon entropy boundary values."""
        self.assertAlmostEqual(binary_entropy(0.0), 0.0)
        self.assertAlmostEqual(binary_entropy(1.0), 0.0)
        self.assertAlmostEqual(binary_entropy(0.5), 1.0)
        self.assertGreater(binary_entropy(0.6), binary_entropy(0.9))
        print("PASS: Binary entropy mathematical bounds verified.")

    def test_02_inquiry_ranking(self):
        """Verify candidate inquiries are ranked by VOI score."""
        assessment = Assessment(
            risk_score=60.0,
            fraud_probability=0.60,
            confidence=0.60,
            verdict="uncertain",
            pattern="card_not_present_fraud",
            pattern_description="",
            sufficient_to_act=False,
            is_ambiguous=True,
            missing_evidence=["Cardholder validation"],
            hypotheses=[],
        )
        trigger = {"trigger_type": "risk_score", "risk_score": 0.60, "channel": "online"}
        inquiries = ValueOfInformationEngine.evaluate_inquiries(
            assessment, trigger, has_new_device=True
        )

        self.assertGreaterEqual(len(inquiries), 2)
        # Check descending order by VOI
        for i in range(len(inquiries) - 1):
            self.assertGreaterEqual(inquiries[i]["voi_score"], inquiries[i + 1]["voi_score"])

        best = ValueOfInformationEngine.select_best_inquiry(
            assessment, trigger, has_new_device=True
        )
        self.assertIsNotNone(best)
        self.assertIn(best.type, {"customer_validation", "step_up_auth", "analyst_info"})
        self.assertIn("Optimal VOI", best.reason)
        print(f"PASS: Inquiries ranked by VOI. Top inquiry: {best.type} ({best.reason})")


if __name__ == "__main__":
    unittest.main()
