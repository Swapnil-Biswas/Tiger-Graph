"""
Unit tests for Webhook Dead-Letter Queue (DLQ) and Exponential Backoff Retry Engine
"""

import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.api.webhook_dlq import WebhookDeadLetterQueue, DLQMessage, webhook_dlq
from src.api.webhooks import EnterpriseWebhookDispatcher
from src.api.main import app


class TestWebhookDLQ(unittest.TestCase):
    def setUp(self):
        self.dlq = WebhookDeadLetterQueue(default_max_attempts=3, base_delay=0.1, max_delay=10.0)
        self.client = TestClient(app)

    def test_enqueue_message(self):
        msg = self.dlq.enqueue(
            subscription_id="SUB-001",
            url="https://example.com/webhook",
            secret="test_secret_key",
            event_type="SAR_FILING_REQUIRED",
            payload={"case_id": "HHG-001", "exposure": 77.07},
            initial_error="Connection timeout",
        )
        self.assertTrue(msg.message_id.startswith("DLQ-"))
        self.assertEqual(msg.status, "PENDING")
        self.assertEqual(msg.attempts, 1)
        self.assertEqual(msg.last_error, "Connection timeout")
        self.assertGreater(msg.next_retry_time, 0.0)

    def test_backoff_calculation(self):
        # attempts: 1 -> base * 2^0 = 1.0
        # attempts: 2 -> base * 2^1 = 2.0
        # attempts: 3 -> base * 2^2 = 4.0
        # capped by max_delay
        self.assertEqual(self.dlq.calculate_backoff(1, base_delay=1.0, max_delay=10.0), 1.0)
        self.assertEqual(self.dlq.calculate_backoff(2, base_delay=1.0, max_delay=10.0), 2.0)
        self.assertEqual(self.dlq.calculate_backoff(3, base_delay=1.0, max_delay=10.0), 4.0)
        self.assertEqual(self.dlq.calculate_backoff(10, base_delay=1.0, max_delay=10.0), 10.0)

    def test_successful_retry(self):
        msg = self.dlq.enqueue("SUB-002", "https://api.test/hook", "sec", "TEST_EVENT", {"k": "v"})
        ok = self.dlq.retry_message(msg.message_id, send_fn=lambda m: True)
        self.assertTrue(ok)
        self.assertEqual(msg.status, "DELIVERED")
        self.assertIsNone(msg.last_error)

    def test_exhaustion_to_dead_letter(self):
        msg = self.dlq.enqueue("SUB-003", "https://api.test/fail", "sec", "FAIL_EVENT", {}, max_attempts=2)
        # 1st attempt was enqueue (attempts=1). Retry fails -> attempts=2 >= max_attempts -> DEAD_LETTER
        ok = self.dlq.retry_message(msg.message_id, send_fn=lambda m: False)
        self.assertFalse(ok)
        self.assertEqual(msg.status, "DEAD_LETTER")
        self.assertEqual(msg.attempts, 2)

    def test_manual_requeue_and_purge(self):
        msg = self.dlq.enqueue("SUB-004", "https://api.test/rq", "sec", "RQ_EVENT", {}, max_attempts=2)
        self.dlq.retry_message(msg.message_id, send_fn=lambda m: False)
        self.assertEqual(msg.status, "DEAD_LETTER")

        # Requeue
        rq_ok = self.dlq.requeue_message(msg.message_id)
        self.assertTrue(rq_ok)
        self.assertEqual(msg.status, "PENDING")
        self.assertEqual(msg.attempts, 0)

        # Purge
        purged = self.dlq.purge(status="PENDING")
        self.assertEqual(purged, 1)
        self.assertEqual(len(self.dlq.get_messages()), 0)

    def test_automatic_dlq_enqueue_on_dispatch_failure(self):
        dispatcher = EnterpriseWebhookDispatcher()
        # Register invalid URL that fails HTTP
        dispatcher.register_subscription(
            url="http://127.0.0.1:59999/nonexistent-webhook-endpoint",
            secret="sec123",
            events=["CRITICAL_ALERT"],
        )
        deliveries = dispatcher.dispatch_event("CRITICAL_ALERT", {"alert": "burst"}, send_http=True)
        self.assertEqual(len(deliveries), 1)
        self.assertFalse(deliveries[0].success)

        # Check that it was enqueued in global webhook_dlq
        msgs = webhook_dlq.get_messages()
        self.assertGreaterEqual(len(msgs), 1)
        latest = msgs[-1]
        self.assertEqual(latest["event_type"], "CRITICAL_ALERT")

    def test_fastapi_dlq_endpoints(self):
        # Stats
        resp_stats = self.client.get("/api/webhooks/dlq/stats")
        self.assertEqual(resp_stats.status_code, 200)
        self.assertIn("total", resp_stats.json())

        # List
        resp_list = self.client.get("/api/webhooks/dlq")
        self.assertEqual(resp_list.status_code, 200)
        self.assertIn("messages", resp_list.json())

        # Retry all
        resp_retry = self.client.post("/api/webhooks/dlq/retry?force=true")
        self.assertEqual(resp_retry.status_code, 200)
        self.assertEqual(resp_retry.json()["status"], "retried")

        # Purge
        resp_purge = self.client.post("/api/webhooks/dlq/purge")
        self.assertEqual(resp_purge.status_code, 200)
        self.assertEqual(resp_purge.json()["status"], "purged")


if __name__ == "__main__":
    unittest.main()
