import unittest
from fastapi.testclient import TestClient
from src.policy.jurisdiction import HighRiskMCCRiskEngine, JurisdictionComplianceRouter
from src.graph.client import GraphClient
from src.api.main import app


class TestHighRiskMCC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = GraphClient()
        cls.api_client = TestClient(app)

    def test_routine_retail_mcc_baseline(self):
        """Routine retail purchases should yield 1.0x multiplier and no mandatory actions."""
        retail_txns = [
            {"txn_id": "T1", "amount": 65.0, "mcc": "5411", "channel": "in_person", "epoch_s": 1000},
            {"txn_id": "T2", "amount": 120.0, "mcc": "5311", "channel": "in_person", "epoch_s": 1050},
        ]
        res = HighRiskMCCRiskEngine.evaluate_mcc_risk(
            card_id="card_retail_1",
            transactions=retail_txns,
            as_of=1200,
        )
        self.assertEqual(res["high_risk_mcc_count"], 0)
        self.assertEqual(res["high_risk_exposure_usd"], 0.0)
        self.assertEqual(res["max_risk_multiplier"], 1.0)
        self.assertEqual(res["effective_velocity_multiplier"], 1.0)
        self.assertFalse(res["enhanced_due_diligence_required"])
        self.assertEqual(len(res["mandatory_actions"]), 0)

    def test_crypto_quasi_cash_mcc_6051(self):
        """Cryptocurrency / Quasi-cash purchases should trigger RESTRICT_QUASI_CASH and 2.0x multiplier."""
        crypto_txns = [
            {"txn_id": "T1", "amount": 800.0, "mcc": "6051", "channel": "online", "epoch_s": 1000},
        ]
        res = HighRiskMCCRiskEngine.evaluate_mcc_risk(
            card_id="card_crypto_1",
            transactions=crypto_txns,
            as_of=1200,
        )
        self.assertEqual(res["high_risk_mcc_count"], 1)
        self.assertIn("6051", res["high_risk_mccs_detected"])
        self.assertEqual(res["max_risk_multiplier"], 2.0)
        self.assertIn("RESTRICT_QUASI_CASH", res["mandatory_actions"])

    def test_gambling_rapid_velocity_compounding(self):
        """Rapid bursts of gambling/betting (MCC 7995) should compound the velocity multiplier to 3.75x."""
        gambling_txns = [
            {"txn_id": "T1", "amount": 300.0, "mcc": "7995", "channel": "online", "epoch_s": 1000},
            {"txn_id": "T2", "amount": 500.0, "mcc": "7995", "channel": "online", "epoch_s": 1020},
            {"txn_id": "T3", "amount": 700.0, "mcc": "7995", "channel": "online", "epoch_s": 1040},
        ]
        res = HighRiskMCCRiskEngine.evaluate_mcc_risk(
            card_id="card_gambling_1",
            transactions=gambling_txns,
            as_of=1100,
        )
        self.assertEqual(res["high_risk_mcc_count"], 3)
        self.assertEqual(res["max_risk_multiplier"], 2.5)
        # Compounded: 2.5 * 1.5 = 3.75
        self.assertEqual(res["effective_velocity_multiplier"], 3.75)
        self.assertIn("STEP_UP_AUTH", res["mandatory_actions"])

    def test_cumulative_exposure_threshold_sar(self):
        """High cumulative quasi-cash exposure (>= $2,000) should trigger EDD and SAR filing."""
        large_crypto = [
            {"txn_id": "T1", "amount": 1200.0, "mcc": "6051", "channel": "online", "epoch_s": 1000},
            {"txn_id": "T2", "amount": 1500.0, "mcc": "6051", "channel": "online", "epoch_s": 1050},
        ]
        res = HighRiskMCCRiskEngine.evaluate_mcc_risk(
            card_id="card_sar_crypto_1",
            transactions=large_crypto,
            as_of=1200,
        )
        self.assertTrue(res["enhanced_due_diligence_required"])
        self.assertIn("ENHANCED_DUE_DILIGENCE", res["mandatory_actions"])
        self.assertIn("FILE_SAR_HIGH_RISK_MCC", res["mandatory_actions"])

    def test_jurisdiction_dispatch_bundle_integration(self):
        """JurisdictionComplianceRouter.generate_dispatch_bundle should embed mcc_risk_analysis."""
        mock_case_answer = {
            "case_id": "CASE-MCC-TEST-001",
            "case": {
                "card_id": "card_mcc_bundle_test",
                "verdict": "uncertain",
                "exposure_usd": 3000.0,
                "pattern": "none",
                "transactions": [
                    {"txn_id": "TXN_CRYPTO_1", "amount": 2500.0, "mcc": "6051", "epoch_s": 2000},
                ],
            },
            "sar": {"narrative": "High-risk crypto outflow", "subjects": ["card_mcc_bundle_test"]},
        }
        bundle = JurisdictionComplianceRouter.generate_dispatch_bundle(
            case_answer=mock_case_answer,
            client=self.client,
        )
        self.assertIn("mcc_risk_analysis", bundle)
        mcc_analysis = bundle["mcc_risk_analysis"]
        self.assertIsNotNone(mcc_analysis)
        self.assertIn("6051", mcc_analysis["high_risk_mccs_detected"])
        self.assertTrue(bundle["obligations"]["must_file"])
        self.assertIn("FILE_SAR_HIGH_RISK_MCC", bundle["obligations"]["mandatory_actions"])

    def test_api_endpoints_mcc(self):
        """Tests GET /api/cases/{case_id}/mcc-risk and POST /api/regulatory/mcc-check."""
        # 1. GET endpoint for benchmark case
        resp_get = self.api_client.get("/api/cases/HHG-001/mcc-risk")
        self.assertEqual(resp_get.status_code, 200)
        data_get = resp_get.json()
        self.assertIn("case_id", data_get)
        self.assertIn("mcc_risk_analysis", data_get)
        self.assertIn("effective_velocity_multiplier", data_get["mcc_risk_analysis"])

        # 2. POST on-demand check endpoint
        payload = {
            "card_id": "CUST_TEST_MCC",
            "transactions": [
                {"txn_id": "T1", "amount": 2500.0, "mcc": "4829", "epoch_s": 1000},
            ],
            "as_of": "1200",
            "window_hours": 48.0,
        }
        resp_post = self.api_client.post("/api/regulatory/mcc-check", json=payload)
        self.assertEqual(resp_post.status_code, 200)
        data_post = resp_post.json()
        self.assertEqual(data_post["card_id"], "CUST_TEST_MCC")
        self.assertIn("4829", data_post["high_risk_mccs_detected"])
        self.assertIn("RESTRICT_OUTBOUND_WIRES", data_post["mandatory_actions"])


if __name__ == "__main__":
    unittest.main()
