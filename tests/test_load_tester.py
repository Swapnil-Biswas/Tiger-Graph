"""
Unit tests for Automated End-to-End Stress & Concurrent Load Testing Harness
"""

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from eval.load_tester import LoadTestHarness


class TestLoadTester(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = LoadTestHarness()

    def test_load_test_execution(self):
        results = self.harness.run_load_test(total_requests=10, concurrency=2)
        self.assertEqual(results["total_requests"], 10)
        self.assertEqual(results["concurrency"], 2)
        self.assertEqual(results["success_count"], 10)
        self.assertEqual(results["success_rate_percent"], 100.0)
        self.assertGreater(results["throughput_rps"], 0.0)
        self.assertEqual(results["error_count"], 0)

    def test_percentile_calculations(self):
        results = self.harness.run_load_test(total_requests=15, concurrency=3)
        lat = results["latency_ms"]
        self.assertGreaterEqual(lat["min"], 0.0)
        self.assertGreaterEqual(lat["p50"], lat["min"])
        self.assertGreaterEqual(lat["p90"], lat["p50"])
        self.assertGreaterEqual(lat["p95"], lat["p90"])
        self.assertGreaterEqual(lat["p99"], lat["p95"])
        self.assertGreaterEqual(lat["max"], lat["p99"])

    def test_format_report_ascii(self):
        results = self.harness.run_load_test(total_requests=6, concurrency=2)
        report = self.harness.format_report(results)
        self.assertIn("TIGERGRAPH AGENTIC FRAUD INVESTIGATOR: CONCURRENT LOAD TEST REPORT", report)
        self.assertIn("Throughput (RPS)", report)
        self.assertIn("Latency Distribution (ms)", report)
        self.assertIn("Status Codes", report)

    def test_custom_endpoints(self):
        endpoints = ["/api/cases/HHG-001", "/api/security/ratelimit/stats"]
        results = self.harness.run_load_test(endpoints=endpoints, total_requests=8, concurrency=2)
        self.assertEqual(results["total_requests"], 8)
        self.assertEqual(results["success_count"], 8)

    def test_error_capture(self):
        endpoints = ["/api/cases/NON-EXISTENT-CASE-12345"]
        results = self.harness.run_load_test(endpoints=endpoints, total_requests=4, concurrency=2)
        self.assertEqual(results["total_requests"], 4)
        self.assertEqual(results["status_code_distribution"].get(404, 0), 4)


if __name__ == "__main__":
    unittest.main()
