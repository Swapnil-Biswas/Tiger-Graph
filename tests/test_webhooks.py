"""
Unit and Integration Tests for Enterprise Webhook Dispatcher & Incident Bridge
(tests/test_webhooks.py)
"""

import unittest
import time
from fastapi.testclient import TestClient
from src.api.webhooks import EnterpriseWebhookDispatcher, webhook_dispatcher
from src.api.main import app


class TestWebhooks(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.dispatcher = EnterpriseWebhookDispatcher()

    def test_01_signature_generation_and_verification(self):
        """Verify HMAC-SHA256 signature generation, validation, and anti-tamper security."""
        secret = "super_secret_webhook_key_2026"
        payload = b'{"alert":"CRITICAL_FRAUD","amount":15000.0}'
        ts = int(time.time())

        # 1. Valid signature
        header = self.dispatcher.sign_payload(secret, payload, timestamp=ts)
        self.assertTrue(self.dispatcher.verify_signature(secret, payload, header))

        # 2. Tampered payload
        tampered_payload = b'{"alert":"CRITICAL_FRAUD","amount":15.0}'
        self.assertFalse(self.dispatcher.verify_signature(secret, tampered_payload, header))

        # 3. Wrong secret
        self.assertFalse(self.dispatcher.verify_signature("wrong_secret", payload, header))

        # 4. Expired timestamp (> 300s tolerance)
        old_header = self.dispatcher.sign_payload(secret, payload, timestamp=ts - 600)
        self.assertFalse(self.dispatcher.verify_signature(secret, payload, old_header, tolerance_seconds=300))

    def test_02_subscription_lifecycle_and_filtering(self):
        """Verify subscription registration, event filtering, and secret masking."""
        sub1 = self.dispatcher.register_subscription(
            url="https://hooks.slack.com/services/T00/B00/X00",
            secret="slack_secret_key",
            events=["STREAMING_CRITICAL_ANOMALY"],
        )
        sub2 = self.dispatcher.register_subscription(
            url="https://events.pagerduty.com/v2/enqueue",
            secret="pd_secret_key",
            events=["SAR_FILING_REQUIRED"],
        )
        sub_all = self.dispatcher.register_subscription(
            url="https://soc.enterprise.bank/webhooks/fraud",
            secret="soc_secret_key",
            events=["*"],
        )

        self.assertEqual(len(self.dispatcher.get_subscriptions()), 3)

        # Verify secret masking
        sub_dict = sub1.to_dict()
        self.assertNotIn("secret", sub_dict)
        self.assertIn("secret_masked", sub_dict)
        self.assertTrue(sub_dict["secret_masked"].endswith("...."))

        # Dispatch STREAMING_CRITICAL_ANOMALY
        deliv1 = self.dispatcher.dispatch_event(
            "STREAMING_CRITICAL_ANOMALY",
            {"card_id": "C12345-K1", "rule": "IMPOSSIBLE_TRAVEL"},
        )
        # Should deliver to sub1 and sub_all (2 deliveries)
        self.assertEqual(len(deliv1), 2)
        sub_ids = [d.subscription_id for d in deliv1]
        self.assertIn(sub1.subscription_id, sub_ids)
        self.assertIn(sub_all.subscription_id, sub_ids)
        self.assertNotIn(sub2.subscription_id, sub_ids)

        # Dispatch SAR_FILING_REQUIRED
        deliv2 = self.dispatcher.dispatch_event(
            "SAR_FILING_REQUIRED",
            {"case_id": "HHG-004", "exposure_usd": 12500.0},
        )
        # Should deliver to sub2 and sub_all (2 deliveries)
        self.assertEqual(len(deliv2), 2)
        sub_ids2 = [d.subscription_id for d in deliv2]
        self.assertIn(sub2.subscription_id, sub_ids2)
        self.assertIn(sub_all.subscription_id, sub_ids2)

        # Deletion
        self.assertTrue(self.dispatcher.delete_subscription(sub1.subscription_id))
        self.assertEqual(len(self.dispatcher.get_subscriptions()), 2)

    def test_03_fastapi_webhook_endpoints(self):
        """Verify REST endpoints for webhook subscriptions, test dispatches, and delivery logs."""
        # 1. Register subscription
        req_body = {
            "url": "https://api.pagerduty.com/webhook",
            "secret": "test_api_secret_key",
            "events": ["STREAMING_CRITICAL_ANOMALY", "SAR_FILING_REQUIRED"],
            "enabled": True,
        }
        resp = self.client.post("/api/webhooks/subscriptions", json=req_body)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        sub_id = data["subscription"]["subscription_id"]

        # 2. List subscriptions
        resp_list = self.client.get("/api/webhooks/subscriptions")
        self.assertEqual(resp_list.status_code, 200)
        subs = resp_list.json()["subscriptions"]
        self.assertTrue(any(s["subscription_id"] == sub_id for s in subs))

        # 3. Test dispatch
        test_payload = {
            "event_type": "STREAMING_CRITICAL_ANOMALY",
            "payload": {"incident": "TEST_SYNDICATE_SPIKE", "severity": "CRITICAL"},
        }
        resp_test = self.client.post("/api/webhooks/test", json=test_payload)
        self.assertEqual(resp_test.status_code, 200)
        test_res = resp_test.json()
        self.assertEqual(test_res["status"], "dispatched")
        self.assertTrue(test_res["deliveries_count"] >= 1)

        # 4. Get delivery logs
        resp_logs = self.client.get("/api/webhooks/deliveries")
        self.assertEqual(resp_logs.status_code, 200)
        logs = resp_logs.json()["deliveries"]
        self.assertTrue(len(logs) >= 1)
        self.assertEqual(logs[0]["event_type"], "STREAMING_CRITICAL_ANOMALY")

        # 5. Delete subscription
        resp_del = self.client.delete(f"/api/webhooks/subscriptions/{sub_id}")
        self.assertEqual(resp_del.status_code, 200)
        self.assertEqual(resp_del.json()["deleted_id"], sub_id)

    def test_04_pipeline_critical_streaming_webhook_dispatch(self):
        """Verify that streaming transactions triggering CRITICAL alerts automatically dispatch webhooks."""
        # Register test subscription in global dispatcher
        sub = webhook_dispatcher.register_subscription(
            url="https://hooks.slack.com/test",
            secret="slack_global_test",
            events=["STREAMING_CRITICAL_ANOMALY"],
        )

        # Ingest impossible travel transaction pair (NY -> London in 10 seconds)
        txn1 = {
            "transaction_id": "TXN-GEO-001",
            "card_id": "CARD-GEO-TEST",
            "amount": 100.0,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "epoch_s": 1700000000,
        }
        txn2 = {
            "transaction_id": "TXN-GEO-002",
            "card_id": "CARD-GEO-TEST",
            "amount": 500.0,
            "latitude": 51.5074,
            "longitude": -0.1278,
            "epoch_s": 1700000010,
        }

        self.client.post("/api/streaming/ingest", json={"transaction": txn1})
        resp2 = self.client.post("/api/streaming/ingest", json={"transaction": txn2})
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()["alerts_triggered"] >= 1)

        # Check delivery log
        logs = webhook_dispatcher.get_delivery_log(limit=10)
        critical_logs = [l for l in logs if l["event_type"] == "STREAMING_CRITICAL_ANOMALY"]
        self.assertTrue(len(critical_logs) >= 1)
        self.assertEqual(critical_logs[0]["payload"]["card_id"], "CARD-GEO-TEST")
        self.assertEqual(critical_logs[0]["payload"]["rule"], "IMPOSSIBLE_TRAVEL")

        # Cleanup
        webhook_dispatcher.delete_subscription(sub.subscription_id)


if __name__ == "__main__":
    unittest.main()
