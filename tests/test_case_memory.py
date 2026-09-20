"""
Unit tests for Case Memory & Empirical Bayes Prior Engine (src.cases.memory).
Validates leak-free temporal boundaries ('as_of'), prior adjustments, and Bayesian smoothing.
"""

import unittest
from unittest.mock import MagicMock
from src.cases.memory import BayesianCaseMemoryPrior


class TestCaseMemoryPrior(unittest.TestCase):
    def setUp(self):
        # Create a mock graph client with controlled closed cases and device index
        self.mock_client = MagicMock()
        self.mock_store = MagicMock()
        self.mock_client.store = self.mock_store

        # Mock closed cases
        self.mock_store.closed_cases = {
            "CC-001": {
                "case_id": "CC-001",
                "card_id": "CARD-A",
                "customer_id": "CUST-1",
                "opened_at": "2016-10-01 12:00:00",
                "outcome": "confirmed_fraud",
            },
            "CC-002": {
                "case_id": "CC-002",
                "card_id": "CARD-A",
                "customer_id": "CUST-1",
                "opened_at": "2016-10-15 10:00:00",
                "outcome": "cleared",
            },
            "CC-003": {
                "case_id": "CC-003",
                "card_id": "CARD-A",
                "customer_id": "CUST-1",
                "opened_at": "2016-12-05 08:00:00",  # Future relative to Nov 1
                "outcome": "confirmed_fraud",
            },
            "CC-004": {
                "case_id": "CC-004",
                "card_id": "CARD-B",
                "customer_id": "CUST-2",
                "opened_at": "2016-09-01 09:00:00",
                "outcome": "confirmed_fraud",
            },
        }

        # Mock device sharing index
        self.mock_store.cards_by_device = {
            "DEV-SHARED-1": ["CARD-X", "CARD-B"],
            "DEV-CLEAN-1": ["CARD-A"],
        }

        self.memory_engine = BayesianCaseMemoryPrior(self.mock_client)

    def test_strict_temporal_isolation(self):
        """Validates that any closed case opened at or after 'as_of' is strictly ignored."""
        prior = self.memory_engine.compute_prior(
            card_id="CARD-A",
            customer_id="CUST-1",
            as_of="2016-11-01 00:00:00",
        )
        # CC-003 was opened on 2016-12-05, so only CC-001 and CC-002 should be matched
        self.assertEqual(prior["total_prior_cases"], 2)
        self.assertEqual(prior["confirmed_fraud_count"], 1)
        self.assertEqual(prior["cleared_count"], 1)
        self.assertNotIn("CC-003", prior["prior_cases_cited"])
        print("PASS: Temporal isolation strictly enforced: future case CC-003 excluded.")

    def test_confirmed_fraud_prior_elevates_risk(self):
        """Validates that prior confirmed fraud increases the Bayesian posterior and risk delta."""
        prior = self.memory_engine.compute_prior(
            card_id="CARD-B",
            customer_id="CUST-2",
            as_of="2016-11-01 00:00:00",
        )
        self.assertEqual(prior["total_prior_cases"], 1)
        self.assertEqual(prior["confirmed_fraud_count"], 1)
        self.assertGreater(prior["risk_delta"], 0.0)
        self.assertGreater(prior["posterior_fraud_rate"], 0.15)
        print("PASS: Prior confirmed fraud elevates Bayesian risk delta.")

    def test_cleared_precedents_dampen_risk(self):
        """Validates that cleared historical cases without fraud dampen risk points."""
        # Set up store with only cleared cases for CARD-CLEAN
        self.mock_store.closed_cases["CC-005"] = {
            "case_id": "CC-005",
            "card_id": "CARD-CLEAN",
            "customer_id": "CUST-3",
            "opened_at": "2016-08-01 12:00:00",
            "outcome": "cleared",
        }
        prior = self.memory_engine.compute_prior(
            card_id="CARD-CLEAN",
            as_of="2016-11-01 00:00:00",
        )
        self.assertEqual(prior["confirmed_fraud_count"], 0)
        self.assertEqual(prior["cleared_count"], 1)
        self.assertLess(prior["risk_delta"], 0.0)
        print("PASS: Historical cleared cases safely dampen risk points.")

    def test_shared_device_prior_fraud_flag(self):
        """Validates detection of prior confirmed fraud on a shared device profile."""
        prior = self.memory_engine.compute_prior(
            card_id="CARD-X",  # New card, but shares DEV-SHARED-1 with compromised CARD-B
            device_profile="DEV-SHARED-1",
            as_of="2016-11-01 00:00:00",
        )
        self.assertTrue(prior["device_prior_fraud"])
        self.assertGreaterEqual(prior["risk_delta"], 5.0)
        print("PASS: Shared device prior fraud correctly flagged and factored into prior.")

    def test_zero_history_baseline(self):
        """Validates that an entity with zero case history returns neutral prior."""
        prior = self.memory_engine.compute_prior(
            card_id="CARD-UNKNOWN",
            as_of="2016-11-01 00:00:00",
        )
        self.assertFalse(prior["has_history"])
        self.assertEqual(prior["total_prior_cases"], 0)
        self.assertEqual(prior["risk_delta"], 0.0)
        print("PASS: Zero history returns neutral prior without distortion.")


if __name__ == "__main__":
    unittest.main()
