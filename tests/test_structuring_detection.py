"""
Unit Tests for Regulatory Structuring Alerts & Dynamic Multi-Entity Exposure Rollup
Validates BSA 31 CFR 1010.314/1020.320, UK POCA, and EU 6AMLD structuring evasion detection,
multi-card smurfing, and CTR/SAR filing requirements.
"""

import unittest
from datetime import datetime, timezone, timedelta
from src.graph.client import GraphClient
from src.policy.jurisdiction import RegulatoryStructuringDetector, JurisdictionComplianceRouter


class TestRegulatoryStructuringDetection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = GraphClient(mode="embedded")

    def test_01_us_bsa_ctr_threshold_and_multi_card_dispersion(self):
        """Validates that cumulative exposure >= $10,000 across multiple cards triggers CTR and multi-card dispersion."""
        now = datetime.now(timezone.utc)
        t1 = (now - timedelta(hours=5)).isoformat()
        t2 = (now - timedelta(hours=3)).isoformat()
        t3 = (now - timedelta(hours=1)).isoformat()

        mock_txns = [
            {"txn_id": "TX-001", "amount": 4500.0, "card_id": "CARD-A", "ts": t1, "device_profile": "DEV-1"},
            {"txn_id": "TX-002", "amount": 3200.0, "card_id": "CARD-B", "ts": t2, "device_profile": "DEV-1"},
            {"txn_id": "TX-003", "amount": 3100.0, "card_id": "CARD-C", "ts": t3, "device_profile": "DEV-1"},
        ]

        res = RegulatoryStructuringDetector.detect_structuring(
            transactions=mock_txns,
            window_hours=24.0,
            jurisdiction="US",
        )

        self.assertEqual(res["jurisdiction"], "US")
        self.assertEqual(res["total_exposure_usd"], 10800.0)
        self.assertEqual(res["card_count"], 3)
        self.assertTrue(res["is_structuring"])
        self.assertIn("CTR_THRESHOLD_EXCEEDED", res["structuring_indicators"])
        self.assertIn("MULTI_CARD_DISPERSION", res["structuring_indicators"])
        self.assertIn("FILE_CTR", res["mandatory_filings"])
        self.assertIn("FILE_SAR_STRUCTURING", res["mandatory_filings"])
        self.assertIn("31 CFR 1010.311", res["narrative_summary"])
        self.assertIn("31 CFR 1010.314", res["narrative_summary"])

    def test_02_sub_threshold_concentration_classic_smurfing(self):
        """Validates that multiple transactions in the $8,000-$9,999.99 band trigger structuring evasion."""
        now = datetime.now(timezone.utc)
        mock_txns = [
            {"txn_id": "TX-101", "amount": 9500.0, "card_id": "CARD-A", "ts": (now - timedelta(hours=10)).isoformat()},
            {"txn_id": "TX-102", "amount": 9200.0, "card_id": "CARD-A", "ts": (now - timedelta(hours=2)).isoformat()},
        ]

        res = RegulatoryStructuringDetector.detect_structuring(
            transactions=mock_txns,
            window_hours=24.0,
            jurisdiction="US",
        )

        self.assertTrue(res["is_structuring"])
        self.assertIn("SUB_THRESHOLD_CONCENTRATION", res["structuring_indicators"])
        self.assertIn("FILE_SAR_STRUCTURING", res["mandatory_filings"])
        self.assertIn("Sub-threshold structuring detected", res["narrative_summary"])

    def test_03_uk_and_eu_jurisdiction_thresholds(self):
        """Validates jurisdiction-tailored thresholds for UK (£2,500 / $3,000) and EU (€2,000 / $2,500)."""
        now = datetime.now(timezone.utc)
        # UK: 2 transactions of $2,600 in $2,400-$2,999.99 band
        uk_txns = [
            {"txn_id": "TX-UK-1", "amount": 2600.0, "card_id": "CARD-UK-1", "ts": (now - timedelta(hours=4)).isoformat()},
            {"txn_id": "TX-UK-2", "amount": 2700.0, "card_id": "CARD-UK-2", "ts": (now - timedelta(hours=1)).isoformat()},
        ]
        uk_res = RegulatoryStructuringDetector.detect_structuring(
            transactions=uk_txns,
            window_hours=24.0,
            jurisdiction="UK",
        )
        self.assertTrue(uk_res["is_structuring"])
        self.assertIn("SUB_THRESHOLD_CONCENTRATION", uk_res["structuring_indicators"])
        self.assertIn("CTR_THRESHOLD_EXCEEDED", uk_res["structuring_indicators"])
        self.assertIn("POCA", uk_res["narrative_summary"])

        # EU: 1 transaction of $2,800 exceeds $2,500 CTR threshold
        eu_txns = [
            {"txn_id": "TX-EU-1", "amount": 2800.0, "card_id": "CARD-EU-1", "ts": now.isoformat()},
        ]
        eu_res = RegulatoryStructuringDetector.detect_structuring(
            transactions=eu_txns,
            window_hours=24.0,
            jurisdiction="EU",
        )
        self.assertIn("CTR_THRESHOLD_EXCEEDED", eu_res["structuring_indicators"])
        self.assertIn("6AMLD", eu_res["narrative_summary"])

    def test_04_rapid_velocity_and_round_sum_indicators(self):
        """Validates detection of rapid burst transactions and round sum concentrations."""
        now = datetime.now(timezone.utc)
        burst_txns = [
            {"txn_id": "B-1", "amount": 2500.0, "card_id": "CARD-1", "ts": (now - timedelta(hours=2)).isoformat()},
            {"txn_id": "B-2", "amount": 2500.0, "card_id": "CARD-2", "ts": (now - timedelta(hours=1)).isoformat()},
            {"txn_id": "B-3", "amount": 2500.0, "card_id": "CARD-3", "ts": now.isoformat()},
        ]

        res = RegulatoryStructuringDetector.detect_structuring(
            transactions=burst_txns,
            window_hours=24.0,
            jurisdiction="US",
        )

        self.assertIn("RAPID_DISPERSED_VELOCITY", res["structuring_indicators"])
        self.assertIn("ROUND_SUM_CONCENTRATION", res["structuring_indicators"])
        self.assertIn("FILE_SAR_STRUCTURING", res["mandatory_filings"])

    def test_05_dispatch_bundle_integration(self):
        """Validates that generate_dispatch_bundle attaches structuring analysis and merges mandatory filings."""
        mock_case = {
            "case_id": "HHG-STRUCT-001",
            "case": {
                "verdict": "legitimate",  # Even if initial verdict is legitimate, structuring enforces filing
                "pattern": "none",
                "exposure_usd": 1500.0,
                "connected_card_ids": ["CARD-X", "CARD-Y"],
                "evidence": [],
            },
            "sar": {"narrative": "Test narrative", "subjects": []},
        }

        # Mock client transactions or pass directly
        bundle = JurisdictionComplianceRouter.generate_dispatch_bundle(
            case_answer=mock_case,
            override_jurisdiction="US",
            client=self.client,
        )

        self.assertIn("structuring_analysis", bundle)
        self.assertIn("obligations", bundle)

    def test_06_graph_client_q16_method(self):
        """Validates that GraphClient exposes detect_structuring (Q16)."""
        now = datetime.now(timezone.utc)
        sample_txns = [
            {"txn_id": "TX-Q16-1", "amount": 500.0, "card_id": "C-1", "ts": now.isoformat()},
        ]
        res = self.client.detect_structuring(transactions=sample_txns, jurisdiction="US")
        self.assertEqual(res["total_exposure_usd"], 500.0)
        self.assertFalse(res["is_structuring"])
        self.assertEqual(res["mandatory_filings"], [])


if __name__ == "__main__":
    unittest.main()
