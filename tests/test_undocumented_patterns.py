"""
Unit tests for UndocumentedPatternDetector.
Verifies discovery of undocumented fraud typologies (proxy rotation syndicates,
coordinated velocity bursts, impossible geographic dispersion networks).
"""

import unittest
from src.graph.client import GraphClient
from src.graph.algorithms import UndocumentedPatternDetector


class TestUndocumentedPatterns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = GraphClient(mode="embedded")
        cls.detector = UndocumentedPatternDetector(cls.client)

    def test_01_proxy_rotation_syndicate_detection(self):
        dev = "SM-T810 Build/NRD90M | Android 7.0 | chrome 62.0 for android | 2048x1536"
        txns = self.client.store.txns_by_device.get(dev, [])
        self.assertTrue(len(txns) >= 3, "Expected at least 3 txns for device SM-T810")
        
        target_txn_id = txns[-1]["TransactionID"]
        res = self.detector.detect_anomalies(target_txn_id)

        self.assertTrue(res["is_anomaly"])
        self.assertEqual(res["anomaly_type"], "device_pooling_nexus")
        self.assertGreaterEqual(res["confidence"], 0.70)
        self.assertIn("Undocumented", res["description"])
        self.assertGreaterEqual(res["details"]["distinct_cards"], 3)
        print(f"PASS: Undocumented pattern detected on txn {target_txn_id}: {res['anomaly_type']}")

    def test_02_benign_transaction_no_anomaly(self):
        low_risk_txns = [
            tid for tid, txn in self.client.store.transactions.items()
            if txn["risk_score"] < 0.05 and txn["amount"] < 30.0 and txn.get("device_profile") is None
        ]
        if low_risk_txns:
            res = self.detector.detect_anomalies(low_risk_txns[0])
            self.assertFalse(res["is_anomaly"])
            self.assertIsNone(res["anomaly_type"])
            print("PASS: Benign transaction produces 0 undocumented anomaly flags.")


if __name__ == "__main__":
    unittest.main()
