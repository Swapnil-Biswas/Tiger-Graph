"""
Unit tests for SARNarrativeGenerator.
Verifies compliance with FinCEN narrative structure, Section 3a criteria,
and strict answer_format.md validation rules.
"""

import unittest
from src.cases.sar_generator import SARNarrativeGenerator


class TestSARNarrativeGenerator(unittest.TestCase):
    def test_01_sar_filing_structured_narrative(self):
        trigger = {
            "trigger_type": "risk_score",
            "trigger_text": "Model scored transaction at 0.95",
            "card_id": "C08623-K2",
            "customer_id": "C08623",
            "flagged_txn_id": "3514030",
            "device_profile": "SM-T810 | Android 7.0",
        }
        graph_evidence = {
            "device_sharing": {"is_shared": True, "distinct_cards_count": 4, "distinct_customers_count": 3, "cards": ["C08623-K2", "C12382-K1"]},
            "velocity": {"windows": {"1h": {"count": 2}, "24h": {"count": 5}}, "velocity_spike_ratio": 3.2},
            "new_entity": {"proxy_flag": True},
            "geo": {"anomalies_count": 1},
        }

        sar = SARNarrativeGenerator.generate_sar(
            case_id="HHG-004",
            verdict="fraud",
            pattern="card_not_present_new_device",
            exposure_usd=128.33,
            trigger_data=trigger,
            graph_evidence=graph_evidence,
            evidence_requests=[],
            as_of="2016-12-05 14:30:00",
            file_sar=True,
        )

        self.assertTrue(sar["file"])
        self.assertGreater(sar["total_amount_usd"], 0)
        self.assertGreater(len(sar["activity_dates"]), 0)
        self.assertIn("C08623", sar["subjects"])
        self.assertIn("C08623-K2", sar["subjects"])
        self.assertIn("C12382-K1", sar["subjects"])
        
        narrative = sar["narrative"]
        self.assertIn("PART I: SUBJECT INFORMATION", narrative)
        self.assertIn("PART II: SUSPICIOUS ACTIVITY SUMMARY", narrative)
        self.assertIn("PART III: CHRONOLOGY & TYPOLOGY PATTERN MECHANICS", narrative)
        self.assertIn("PART IV: INVESTIGATIVE FINDINGS", narrative)
        self.assertIn("PART V: ACTIONS TAKEN & RECOMMENDED DISPOSITION", narrative)
        print("PASS: FinCEN SAR narrative correctly structured across all 5 regulatory parts.")

    def test_02_sar_no_filing_for_cleared_case(self):
        sar = SARNarrativeGenerator.generate_sar(
            case_id="HHG-002",
            verdict="legitimate",
            pattern="none",
            exposure_usd=0.0,
            trigger_data={"card_id": "C12345-K1", "customer_id": "C12345"},
            graph_evidence={},
            evidence_requests=[],
            as_of="2016-12-01 10:00:00",
            file_sar=False,
        )

        self.assertFalse(sar["file"])
        self.assertEqual(sar["narrative"], "")
        self.assertEqual(sar["subjects"], [])
        self.assertEqual(sar["total_amount_usd"], 0.0)
        print("PASS: Non-filing SAR safely returns empty narrative and subjects.")


if __name__ == "__main__":
    unittest.main()
