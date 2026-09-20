"""
Unit & Integration Tests for Enterprise Prometheus Telemetry and SLA Dashboard (tests/test_telemetry.py)
"""

import unittest
from fastapi.testclient import TestClient
from src.api.telemetry import EnterpriseTelemetryRegistry, telemetry
from src.api.main import app


class TestEnterpriseTelemetry(unittest.TestCase):
    def setUp(self):
        self.reg = EnterpriseTelemetryRegistry()
        self.client = TestClient(app)

    def test_counter_increments(self):
        self.reg.inc_counter("test_counter", 1.0)
        self.reg.inc_counter("test_counter", 2.5)
        self.reg.inc_counter("test_counter_labeled", 1.0, {"env": "prod", "service": "fraud"})
        
        metrics = self.reg.generate_prometheus_metrics()
        self.assertIn("test_counter 3.5", metrics)
        self.assertIn('test_counter_labeled{env="prod",service="fraud"} 1.0', metrics)

    def test_gauge_setting(self):
        self.reg.set_gauge("active_workers", 8.0)
        self.reg.set_gauge("memory_usage_mb", 512.4, {"node": "worker-1"})
        
        metrics = self.reg.generate_prometheus_metrics()
        self.assertIn("active_workers 8.0", metrics)
        self.assertIn('memory_usage_mb{node="worker-1"} 512.4', metrics)

    def test_histogram_observation(self):
        buckets = (0.01, 0.05, 0.1, float("inf"))
        self.reg.observe_histogram("req_latency", 0.005, buckets=buckets)
        self.reg.observe_histogram("req_latency", 0.03, buckets=buckets)
        self.reg.observe_histogram("req_latency", 0.08, buckets=buckets)
        self.reg.observe_histogram("req_latency", 0.25, buckets=buckets)

        metrics = self.reg.generate_prometheus_metrics()
        self.assertIn('req_latency_bucket{le="0.01"} 1', metrics)
        self.assertIn('req_latency_bucket{le="0.05"} 2', metrics)
        self.assertIn('req_latency_bucket{le="0.1"} 3', metrics)
        self.assertIn('req_latency_bucket{le="+Inf"} 4', metrics)
        self.assertIn("req_latency_count 4", metrics)

    def test_dashboard_summary(self):
        self.reg.inc_counter("fraud_investigations_total", 10.0)
        self.reg.inc_counter("streaming_transactions_ingested_total", 500.0)
        self.reg.inc_counter("streaming_alerts_emitted_total", 3.0)
        self.reg.observe_histogram("investigation_latency_seconds", 0.020)
        self.reg.observe_histogram("investigation_latency_seconds", 0.030)

        summary = self.reg.get_dashboard_summary()
        self.assertEqual(summary["status"], "HEALTHY")
        self.assertEqual(summary["total_investigations"], 10)
        self.assertEqual(summary["total_streaming_txns"], 500)
        self.assertEqual(summary["total_streaming_alerts"], 3)
        self.assertTrue(summary["sla_compliant"])
        self.assertAlmostEqual(summary["current_avg_latency_ms"], 25.0, delta=1.0)

    def test_fastapi_metrics_and_dashboard_endpoints(self):
        # 1. Test /metrics endpoint
        resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/plain", resp.headers["content-type"])
        body = resp.text
        self.assertIn("# HELP fraud_investigations_total", body)
        self.assertIn("# TYPE fraud_investigations_total counter", body)
        self.assertIn("graph_indexed_entities", body)

        # 2. Test /api/telemetry/dashboard endpoint
        dash_resp = self.client.get("/api/telemetry/dashboard")
        self.assertEqual(dash_resp.status_code, 200)
        data = dash_resp.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertIn("sla_compliant", data)
        self.assertIn("active_gauges", data)

    def test_api_pipeline_telemetry_integration(self):
        # 1. Ingest streaming transaction
        txn_payload = {
            "transaction": {
                "transaction_id": "TX-TELEM-001",
                "card_id": "CUST-TELEM-CARD",
                "customer_id": "CUST-TELEM",
                "amount": 9500.0,
                "timestamp": "2026-09-20T12:00:00Z",
                "merchant_category": "crypto",
            }
        }
        ingest_resp = self.client.post("/api/streaming/ingest", json=txn_payload)
        self.assertEqual(ingest_resp.status_code, 200)

        # 2. Authorize action
        auth_resp = self.client.post(
            "/api/cases/HHG-001/actions/authorize",
            headers={"X-User-Id": "USR-L2-01", "X-User-Role": "L2_SENIOR_INVESTIGATOR"},
            json={"action_name": "BLOCK_CARD", "exposure_usd": 1500.0},
        )
        self.assertEqual(auth_resp.status_code, 200)
        self.assertTrue(auth_resp.json()["authorized"])

        # 3. Check /metrics reflecting increments
        metrics_resp = self.client.get("/metrics")
        self.assertEqual(metrics_resp.status_code, 200)
        self.assertIn("streaming_transactions_ingested_total", metrics_resp.text)
        self.assertIn("policy_actions_authorized_total", metrics_resp.text)


if __name__ == "__main__":
    unittest.main()
