"""
Unit test for Agent Run-to-Run Consistency and Determinism.
Verifies that multiple repeated runs of ambiguous and complex syndicate cases
yield identical recommendations, actions, and risk probabilities (0% variance).
"""

import unittest
from eval.benchmark_consistency import run_consistency_evaluation


class TestBenchmarkConsistency(unittest.TestCase):
    def test_agent_run_to_run_consistency(self):
        # Test on key representative cases: HHG-001 (Ambiguous), HHG-004 (Syndicate), HHG-007 (Subscription), HHG-011 (Card Testing)
        test_cases = ["HHG-001", "HHG-004", "HHG-007", "HHG-011"]
        res = run_consistency_evaluation(num_runs=3, cases=test_cases)

        self.assertEqual(res["recommendation_variance_pct"], 0.0, f"Expected 0% variance, got {res['recommendation_variance_pct']}%")
        self.assertEqual(res["verdict_concordance_pct"], 100.0)
        self.assertEqual(res["pattern_concordance_pct"], 100.0)
        self.assertEqual(res["action_concordance_pct"], 100.0)
        self.assertLess(res["mean_prob_variance"], 1e-6)


if __name__ == "__main__":
    unittest.main()
