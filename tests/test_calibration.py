"""
Unit Tests for Uncertainty Calibration & Reliability Curve Engine
Validates mathematical correctness of ECE, MCE, and Brier score computations
and evaluates agent probability calibration against PRD Section 11 thresholds.
"""

import unittest
import numpy as np
from eval.calibration_curve import compute_calibration_metrics
from src.agent.graph import FraudInvestigatorAgent


class TestUncertaintyCalibration(unittest.TestCase):

    def test_perfect_calibration_zeros_error(self):
        """Identical probability predictions and binary labels should produce 0.0 error."""
        preds = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        labels = [0, 0, 0, 1, 1, 1]
        metrics = compute_calibration_metrics(preds, labels, n_bins=10)

        self.assertEqual(metrics["ece"], 0.0)
        self.assertEqual(metrics["mce"], 0.0)
        self.assertEqual(metrics["brier_score"], 0.0)
        self.assertEqual(metrics["n_samples"], 6)

    def test_known_miscalibration_exact_math(self):
        """A known overconfident prediction should match analytical ECE/MCE/Brier values."""
        # 10 samples all predicted 0.80, but all true 0
        preds = [0.80] * 10
        labels = [0] * 10
        metrics = compute_calibration_metrics(preds, labels, n_bins=10)

        # In bin [0.8, 0.9), mean_pred = 0.80, empirical_rate = 0.0 -> gap = 0.80
        self.assertAlmostEqual(metrics["ece"], 0.80, places=3)
        self.assertAlmostEqual(metrics["mce"], 0.80, places=3)
        # Brier = (0.8 - 0)^2 = 0.64
        self.assertAlmostEqual(metrics["brier_score"], 0.64, places=3)

    def test_empty_and_single_bin_robustness(self):
        """Empty samples and sparse bins must not cause ZeroDivisionError or NaNs."""
        empty_res = compute_calibration_metrics([], [])
        self.assertEqual(empty_res["n_samples"], 0)
        self.assertEqual(empty_res["ece"], 0.0)
        self.assertEqual(empty_res["brier_score"], 0.0)

        # Single sample
        single_res = compute_calibration_metrics([0.05], [0])
        self.assertEqual(single_res["n_samples"], 1)
        self.assertAlmostEqual(single_res["ece"], 0.05, places=3)
        self.assertAlmostEqual(single_res["brier_score"], 0.0025, places=4)

    def test_benchmark_cases_agent_calibration(self):
        """
        Evaluates the agent's probability calibration across benchmark cases,
        verifying compliance with PRD Section 11 thresholds:
        - ECE < 0.08
        - MCE < 0.15
        - Brier score < 0.12
        """
        agent = FraudInvestigatorAgent()
        benchmark_cases = [
            ("HHG-001", 1),  # confirmed fraud
            ("HHG-002", 0),  # legitimate clearing
            ("HHG-003", 1),  # confirmed fraud
            ("HHG-004", 1),  # confirmed fraud
            ("HHG-007", 1),  # confirmed fraud
            ("HHG-011", 1),  # confirmed fraud
            ("HHG-012", 0),  # legitimate clearing
        ]

        preds = []
        labels = []

        for case_id, true_label in benchmark_cases:
            ans = agent.investigate_case(case_id)
            pred_prob = float(ans["case"]["fraud_probability"])
            preds.append(pred_prob)
            labels.append(true_label)

        metrics = compute_calibration_metrics(preds, labels, n_bins=10)

        # Verify PRD Section 11 criteria
        self.assertLess(
            metrics["ece"],
            0.08,
            f"ECE {metrics['ece']} exceeded PRD Section 11 threshold of 0.08",
        )
        self.assertLess(
            metrics["mce"],
            0.15,
            f"MCE {metrics['mce']} exceeded PRD Section 11 threshold of 0.15",
        )
        self.assertLess(
            metrics["brier_score"],
            0.12,
            f"Brier score {metrics['brier_score']} exceeded PRD Section 11 threshold of 0.12",
        )


if __name__ == "__main__":
    unittest.main()
