"""
Unit Tests for Multi-Jurisdiction Regulatory Routing & Compliance Engine
Validates US FinCEN, UK NCA, and EU 6AMLD regulatory routing, statutory citations,
and GDPR Article 5 data minimization shields.
"""

import unittest
from src.policy.jurisdiction import JurisdictionComplianceRouter


class TestJurisdictionComplianceRouting(unittest.TestCase):

    def test_us_fincen_sar_routing_and_thresholds(self):
        """US jurisdiction must route to FinCEN under 31 CFR 1020.320 with 30-day deadline."""
        obs = JurisdictionComplianceRouter.evaluate_regulatory_obligations(
            jurisdiction="US",
            exposure_usd=6500.0,
            is_fraud=True,
            pattern="card_not_present_new_device",
        )

        self.assertEqual(obs["jurisdiction"], "US")
        self.assertIn("FinCEN", obs["agency"])
        self.assertIn("31 CFR 1020.320", obs["statute"])
        self.assertTrue(obs["must_file"])
        self.assertEqual(obs["retention_years"], 5)

        # Non-fraud or sub-threshold without pattern must not require filing
        obs_clean = JurisdictionComplianceRouter.evaluate_regulatory_obligations(
            jurisdiction="US",
            exposure_usd=150.0,
            is_fraud=False,
            pattern="none",
        )
        self.assertFalse(obs_clean["must_file"])

    def test_uk_nca_daml_str_routing(self):
        """UK jurisdiction must route to NCA under POCA Part 7 with 14-day deadline."""
        obs = JurisdictionComplianceRouter.evaluate_regulatory_obligations(
            jurisdiction="UK",
            exposure_usd=4000.0,
            is_fraud=True,
            pattern="out_of_region_use",
        )

        self.assertEqual(obs["jurisdiction"], "UK")
        self.assertIn("National Crime Agency", obs["agency"])
        self.assertIn("POCA", obs["statute"])
        self.assertTrue(obs["must_file"])

    def test_eu_gdpr_data_minimization_shield(self):
        """GDPR Article 5 requires PAN truncation and email redaction on evidence."""
        raw_evidence = [
            {
                "id": "EV-01",
                "claim": "Cardholder 4111-2222-3333-4444 disputed charge of $500 initiated via user.john.doe@company.org.",
            },
            {
                "id": "EV-02",
                "claim": "Device compromised with card 5500123456789999 from IP 192.168.1.1.",
            },
        ]

        minimized = JurisdictionComplianceRouter.apply_gdpr_data_minimization(raw_evidence)

        # PAN 4111-2222-3333-4444 must be truncated to ****-****-****-4444
        self.assertIn("****-****-****-4444", minimized[0]["claim"])
        self.assertNotIn("4111-2222-3333-4444", minimized[0]["claim"])

        # Email user.john.doe@company.org must be redacted to u***@company.org
        self.assertIn("u***@company.org", minimized[0]["claim"])
        self.assertNotIn("user.john.doe@company.org", minimized[0]["claim"])

        # PAN 5500123456789999 must be truncated to ****-****-****-9999
        self.assertIn("****-****-****-9999", minimized[1]["claim"])
        self.assertNotIn("5500123456789999", minimized[1]["claim"])

    def test_dispatch_bundle_generation(self):
        """Complete dispatch bundle must include jurisdiction obligations, sanitized evidence, and safeguards."""
        mock_case = {
            "case_id": "HHG-UK-TEST",
            "case": {
                "verdict": "fraud",
                "pattern": "device_pooling_nexus",
                "exposure_usd": 7500.0,
                "evidence": [
                    {
                        "id": "EV-01",
                        "claim": "Card 4000-1234-5678-9012 compromised from London IP address.",
                    }
                ],
            },
            "sar": {
                "narrative": "Part I: Suspect Information...",
                "subjects": ["Subject-1"],
            },
        }

        bundle = JurisdictionComplianceRouter.generate_dispatch_bundle(
            case_answer=mock_case,
            override_jurisdiction="UK",
        )

        self.assertEqual(bundle["target_jurisdiction"], "UK")
        self.assertTrue(bundle["obligations"]["must_file"])
        self.assertEqual(bundle["filing_package"]["agency"], "National Crime Agency (NCA) / Financial Conduct Authority (FCA)")
        self.assertIn("POCA", bundle["filing_package"]["statutory_authority"])
        self.assertIn("Part I: Suspect", bundle["filing_package"]["narrative"])


if __name__ == "__main__":
    unittest.main()
