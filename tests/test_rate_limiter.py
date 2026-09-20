"""
Unit tests for Dynamic Rate Limiter, Token Bucket, and DoS Interception Filter
"""

import sys
import time
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.api.rate_limiter import (
    TokenBucket,
    DynamicRateLimiter,
    RateLimitMiddleware,
    rate_limiter,
)
from src.api.main import app


class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = DynamicRateLimiter(
            default_capacity=5,
            default_refill_rate=10.0,
            quarantine_threshold=3,
            quarantine_duration=1.0,
        )

    def test_token_bucket_consume_and_refill(self):
        bucket = TokenBucket(capacity=10, refill_rate=100.0)
        allowed, retry_after, rem = bucket.consume(cost=4)
        self.assertTrue(allowed)
        self.assertEqual(rem, 6)
        self.assertEqual(retry_after, 0.0)

        # Consume remaining
        allowed, retry_after, rem = bucket.consume(cost=6)
        self.assertTrue(allowed)
        self.assertEqual(rem, 0)

        # Over-consume
        allowed, retry_after, rem = bucket.consume(cost=5)
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0.0)

        # Refill after short sleep
        time.sleep(0.06)
        allowed, _, rem = bucket.consume(cost=2)
        self.assertTrue(allowed)

    def test_dynamic_rate_limiter_tiers(self):
        self.assertEqual(self.limiter.get_tier_for_path("/api/investigate"), "critical")
        self.assertEqual(self.limiter.get_tier_for_path("/api/benchmark/run"), "critical")
        self.assertEqual(self.limiter.get_tier_for_path("/graphql"), "critical")
        self.assertEqual(self.limiter.get_tier_for_path("/api/cases/HHG-001"), "standard")
        self.assertEqual(self.limiter.get_tier_for_path("/metrics"), "relaxed")
        self.assertEqual(self.limiter.get_tier_for_path("/health"), "relaxed")

    def test_client_quarantine(self):
        client = "test_abuser"
        # Exhaust capacity
        for _ in range(5):
            self.limiter.check_limit(client, "/api/cases")

        # Trigger violations
        for _ in range(3):
            allowed, retry_after, _, _ = self.limiter.check_limit(client, "/api/cases")
            self.assertFalse(allowed)

        # Should now be quarantined
        stats = self.limiter.get_stats()
        self.assertIn(client, stats["quarantined_ids"])
        self.assertEqual(stats["quarantined_clients"], 1)

        # Further requests rejected immediately
        allowed, retry_after, rem, limit = self.limiter.check_limit(client, "/api/cases")
        self.assertFalse(allowed)
        self.assertEqual(limit, 0)

    def test_client_reset(self):
        client = "test_reset_client"
        for _ in range(6):
            self.limiter.check_limit(client, "/api/cases")

        self.limiter.reset_client(client)
        stats = self.limiter.get_stats()
        self.assertNotIn(client, stats["quarantined_ids"])

        # Allowed again
        allowed, _, rem, _ = self.limiter.check_limit(client, "/api/cases")
        self.assertTrue(allowed)

    def test_whitelist_bypass(self):
        client = "vip_service"
        self.limiter.whitelist.add(client)

        for _ in range(20):
            allowed, _, rem, limit = self.limiter.check_limit(client, "/api/investigate")
            self.assertTrue(allowed)
            self.assertEqual(rem, 9999)

    def test_fastapi_rate_limiter_endpoints(self):
        client = TestClient(app)
        # Stats endpoint
        resp = client.get("/api/security/ratelimit/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("active_clients", data)
        self.assertIn("quarantined_clients", data)

        # Reset endpoint
        resp_reset = client.post("/api/security/ratelimit/reset")
        self.assertEqual(resp_reset.status_code, 200)
        self.assertEqual(resp_reset.json()["status"], "all_reset")

    def test_rate_limit_middleware_interception(self):
        # Create minimal FastAPI app with middleware
        test_app = FastAPI()
        strict_limiter = DynamicRateLimiter(
            default_capacity=2,
            default_refill_rate=0.01,
            quarantine_threshold=5,
        )
        test_app.add_middleware(RateLimitMiddleware, limiter=strict_limiter)

        @test_app.get("/test")
        def dummy():
            return {"status": "ok"}

        t_client = TestClient(test_app)

        # First 2 requests succeed
        r1 = t_client.get("/test")
        self.assertEqual(r1.status_code, 200)
        self.assertIn("X-RateLimit-Limit", r1.headers)

        r2 = t_client.get("/test")
        self.assertEqual(r2.status_code, 200)

        # 3rd request gets 429 Too Many Requests
        r3 = t_client.get("/test")
        self.assertEqual(r3.status_code, 429)
        self.assertIn("Retry-After", r3.headers)
        self.assertEqual(r3.json()["error"], "Too Many Requests")


if __name__ == "__main__":
    unittest.main()
