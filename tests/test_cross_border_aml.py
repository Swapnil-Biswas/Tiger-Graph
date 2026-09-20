import unittest
from fastapi.testclient import TestClient
from src.policy.jurisdiction import CrossBorderAMLRiskDetector, JurisdictionComplianceRouter
from src.graph.client import GraphClient
from src.api.main import app


class TestCrossBorderAML(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = GraphClient()
        cls.api_client = TestClient(app)

    def test_domestic_baseline(self):
        """Routine domestic transactions should evaluate to low risk with no mandatory actions."""
        domestic_txns = [
            {"txn_id": "T1", "amount": 120.0, "addr1": "CA", "addr2": "87.0", "epoch_s": 1000},
            {"txn_id": "T2", "amount": 85.0, "addr1": "CA", "addr2": "87.0", "epoch_s": 1050},
            {"txn_id": "T3", "amount": 210.0, "addr1": "CA", "addr2": "US", "epoch_s": 1100},
        ]
        res = CrossBorderAMLRiskDetector.evaluate_cross_border_risk(
            card_id="card_domestic_1",
            transactions=domestic_txns,
            as_of=1200,
        )
        self.assertEqual(res["cross_border_txns_count"], 0)
        self.assertEqual(res["cross_border_exposure_usd"], 0.0)
        self.assertFalse(res["has_fatf_high_risk_corridor"])
        self.assertFalse(res["has_fatf_grey_list_corridor"])
        self.assertFalse(res["enhanced_due_diligence_required"])
        self.assertEqual(res["aml_threat_level"], "low")
        self.assertEqual(len(res["mandatory_actions"]), 0)

    def test_fatf_high_risk_corridor(self):
        """High-risk FATF corridor transactions should mandate EDD and SAR filing if threshold exceeded."""
        fatf_txns = [
            {"txn_id": "T1", "amount": 3500.0, "addr1": "999", "addr2": "RU", "jurisdiction": "RU", "epoch_s": 1000},
            {"txn_id": "T2", "amount": 400.0, "addr1": "CA", "addr2": "87.0", "epoch_s": 1050},
        ]
        res = CrossBorderAMLRiskDetector.evaluate_cross_border_risk(
            card_id="card_fatf_1",
            transactions=fatf_txns,
            as_of=1200,
        )
        self.assertTrue(res["has_fatf_high_risk_corridor"])
        self.assertTrue(res["enhanced_due_diligence_required"])
        self.assertIn("ENHANCED_DUE_DILIGENCE", res["mandatory_actions"])
        self.assertIn("FILE_SAR_CROSS_BORDER_AML", res["mandatory_actions"])
        self.assertGreaterEqual(res["aml_risk_score"], 0.70)
        self.assertEqual(res["aml_threat_level"], "critical")

    def test_rapid_layering_bundling(self):
        """Multi-region cross-border dispersion should trigger layering/bundling actions."""
        layering_txns = [
            {"txn_id": "T1", "amount": 1500.0, "addr1": "REG_A", "addr2": "AE", "is_cross_border": True, "epoch_s": 1000},
            {"txn_id": "T2", "amount": 1800.0, "addr1": "REG_B", "addr2": "CY", "is_cross_border": True, "epoch_s": 1020},
            {"txn_id": "T3", "amount": 2000.0, "addr1": "REG_C", "addr2": "PA", "is_cross_border": True, "epoch_s": 1040},
        ]
        res = CrossBorderAMLRiskDetector.evaluate_cross_border_risk(
            card_id="card_layer_1",
            transactions=layering_txns,
            as_of=1100,
        )
        self.assertTrue(res["is_layering_bundling_detected"])
        self.assertIn("BLOCK_CORRESPONDENT_PATH", res["mandatory_actions"])
        self.assertIn("RESTRICT_OUTBOUND_WIRES", res["mandatory_actions"])
        self.assertIn("FILE_SAR_CROSS_BORDER_AML", res["mandatory_actions"])
        self.assertGreaterEqual(res["cross_border_exposure_usd"], 5000.0)

    def test_jurisdiction_dispatch_bundle_integration(self):
        """JurisdictionComplianceRouter.generate_dispatch_bundle should embed cross-border AML analysis."""
        mock_case_answer = {
            "case_id": "CASE-TEST-001",
            "case": {
                "card_id": "card_aml_test",
                "verdict": "uncertain",
                "exposure_usd": 1200.0,
                "pattern": "none",
                "transactions": [
                    {"txn_id": "TXN_CB_1", "amount": 6000.0, "addr1": "999", "addr2": "IR", "epoch_s": 2000},
                ],
            },
            "sar": {"narrative": "Suspicious flow to sanctioned territory", "subjects": ["card_aml_test"]},
        }
        bundle = JurisdictionComplianceRouter.generate_dispatch_bundle(
            case_answer=mock_case_answer,
            client=self.client,
        )
        self.assertIn("cross_border_aml_analysis", bundle)
        cb_analysis = bundle["cross_border_aml_analysis"]
        self.assertIsNotNone(cb_analysis)
        self.assertTrue(cb_analysis["has_fatf_high_risk_corridor"])
        # Should force must_file to True even if initial verdict was uncertain
        self.assertTrue(bundle["obligations"]["must_file"])
        self.assertIn("FILE_SAR_CROSS_BORDER_AML", bundle["obligations"]["mandatory_actions"])

    def test_temporal_window_isolation(self):
        """Transactions occurring after as_of must be strictly isolated and ignored."""
        txns = [
            {"txn_id": "T_PAST", "amount": 100.0, "addr1": "CA", "addr2": "87.0", "epoch_s": 1000},
            {"txn_id": "T_FUTURE", "amount": 99999.0, "addr1": "999", "addr2": "KP", "epoch_s": 5000},
        ]
        res = CrossBorderAMLRiskDetector.evaluate_cross_border_risk(
            card_id="card_temp_1",
            transactions=txns,
            as_of=1500,
            window_hours=48.0,
        )
        self.assertEqual(res["total_transactions_evaluated"], 1)
        self.assertEqual(res["cross_border_exposure_usd"], 0.0)
        self.assertFalse(res["has_fatf_high_risk_corridor"])

    def test_api_endpoints(self):
        """Tests GET /api/cases/{case_id}/cross-border-aml and POST /api/regulatory/cross-border-check."""
        # 1. GET endpoint for benchmark case
        resp_get = self.api_client.get("/api/cases/HHG-001/cross-border-aml")
        self.assertEqual(resp_get.status_code, 200)
        data_get = resp_get.json()
        self.assertIn("case_id", data_get)
        self.assertIn("cross_border_aml_analysis", data_get)
        self.assertIn("aml_risk_score", data_get["cross_border_aml_analysis"])

        # 2. POST on-demand check endpoint
        payload = {
            "card_id": "CUST_TEST_CB",
            "transactions": [
                {"txn_id": "T1", "amount": 4200.0, "addr1": "999", "addr2": "RU", "epoch_s": 1000},
            ],
            "as_of": "1200",
            "window_hours": 48.0,
        }
        resp_post = self.api_client.post("/api/regulatory/cross-border-check", json=payload)
        self.assertEqual(resp_post.status_code, 200)
        data_post = resp_post.json()
        self.assertEqual(data_post["card_id"], "CUST_TEST_CB")
        self.assertTrue(data_post["has_fatf_high_risk_corridor"])
        self.assertIn("ENHANCED_DUE_DILIGENCE", data_post["mandatory_actions"])


if __name__ == "__main__":
    unittest.main()
