"""
Unit Tests for Graph-Native Counterfactual Explainer
Verifies counterfactual inversion generation across fraud, legitimate, and uncertain verdicts.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.counterfactual import CounterfactualExplainer


class TestCounterfactualExplainer(unittest.TestCase):

    def test_01_fraud_counterfactuals(self):
        """Verify that fraud cases generate actionable inversion conditions."""
        graph_evidence = {
            "new_entity": {"is_new_device": True, "is_new_region": True},
            "geo": {"has_geo_anomaly": True},
            "device_sharing": {"is_shared": True, "distinct_cards_count": 3},
            "profile": {"typical_regions": ["299.0", "444.0"]},
        }
        cfs = CounterfactualExplainer.generate_counterfactuals(
            verdict="fraud",
            fraud_probability=0.95,
            pattern="card_not_present_new_device",
            graph_evidence=graph_evidence,
        )
        self.assertGreater(len(cfs), 2, "Expected at least 3 counterfactuals for multi-anomaly fraud")
        factors = [c["factor"] for c in cfs]
        self.assertIn("Cardholder Confirmation", factors)
        self.assertIn("Device Fingerprint Baseline", factors)
        self.assertIn("Billing Region Proximity", factors)
        self.assertIn("Device Exclusivity", factors)

        summary_text = CounterfactualExplainer.format_counterfactual_summary(cfs)
        self.assertIn("Decision Sensitivity", summary_text)
        print("PASS: Fraud counterfactual inversions generated and formatted.")

    def test_02_legitimate_counterfactuals(self):
        """Verify that legitimate cases generate sensitivity conditions."""
        graph_evidence = {"new_entity": {}, "geo": {}, "profile": {}}
        cfs = CounterfactualExplainer.generate_counterfactuals(
            verdict="legitimate",
            fraud_probability=0.05,
            pattern="none",
            graph_evidence=graph_evidence,
        )
        self.assertGreaterEqual(len(cfs), 1)
        self.assertEqual(cfs[0]["flip_verdict"], "uncertain")
        print("PASS: Legitimate sensitivity conditions generated.")


if __name__ == "__main__":
    unittest.main()
