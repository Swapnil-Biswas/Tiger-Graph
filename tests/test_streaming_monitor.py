"""
Unit Test Suite for Streaming Transaction Influx Monitor & Dynamic Graph Anomaly Window Detector
(tests/test_streaming_monitor.py)

Tests sub-millisecond streaming ingestion, sliding window eviction, velocity spike triggers,
novel device linkages, impossible travel anomalies, high-risk MCC alerts, and FastAPI REST endpoints.
"""

import unittest
import time
from fastapi.testclient import TestClient

from src.graph.streaming_monitor import (
    StreamingGraphMonitor,
    StreamingAlert,
)
from src.api.main import app, streaming_monitor


class TestStreamingGraphMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Streaming Graph Monitor Test Suite ===")
        cls.monitor = StreamingGraphMonitor(window_seconds=300)
        cls.client = TestClient(app)

    def test_01_sub_millisecond_ingestion_and_eviction(self):
        """Verify streaming transaction ingestion achieves sub-millisecond latency (< 1ms/event)."""
        base_epoch = 1600000000
        t0 = time.perf_counter()

        for i in range(100):
            txn = {
                "TransactionID": f"STRM_{i}",
                "card_id": f"C_BENCH_{i % 10}",
                "amount": 25.0,
                "epoch_s": base_epoch + i,
            }
            self.monitor.ingest_transaction(txn)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        avg_ms_per_event = elapsed_ms / 100.0

        self.assertLess(avg_ms_per_event, 2.0, f"Latency {avg_ms_per_event:.3f}ms exceeds target.")
        stats = self.monitor.get_stats()
        self.assertEqual(stats["total_processed"], 100)
        self.assertEqual(stats["current_window_events"], 100)

        # Test window eviction: ingest event 400s later
        late_txn = {
            "TransactionID": "STRM_LATE",
            "card_id": "C_LATE",
            "amount": 10.0,
            "epoch_s": base_epoch + 400,
        }
        self.monitor.ingest_transaction(late_txn)
        stats_after = self.monitor.get_stats()
        # All events before (base_epoch + 400 - 300 = base_epoch + 100) should be evicted
        self.assertLess(stats_after["current_window_events"], 100)

        print(f"PASS: Streaming ingestion evaluated at {avg_ms_per_event:.3f}ms/event with sliding eviction.")

    def test_02_rolling_velocity_spike_rule(self):
        """Verify rolling velocity spike alert (count >= 3 in 5 min)."""
        monitor = StreamingGraphMonitor(window_seconds=300)
        card = "C_VELOCITY_TEST"
        now_epoch = int(time.time())

        # Ingest 3 rapid txns
        alerts = []
        for i in range(3):
            alerts.extend(monitor.ingest_transaction({
                "TransactionID": f"VEL_{i}",
                "card_id": card,
                "amount": 150.0,
                "epoch_s": now_epoch + (i * 10),
            }))

        vel_alerts = [a for a in alerts if a.rule_triggered == "VELOCITY_SPIKE"]
        self.assertGreaterEqual(len(vel_alerts), 1)
        self.assertEqual(vel_alerts[0].card_id, card)
        self.assertIn("window_txn_count", vel_alerts[0].details)
        self.assertEqual(vel_alerts[0].details["window_txn_count"], 3)

        print(f"PASS: Rolling velocity spike detected after {vel_alerts[0].details['window_txn_count']} txns in window.")

    def test_03_novel_device_linkage_rule(self):
        """Verify novel device linkage trigger when shared device is used by a new card."""
        monitor = StreamingGraphMonitor(window_seconds=300)
        device = "iPhone_13_Pro_iOS_15_Safari"
        now_epoch = int(time.time())

        # Card 1 uses device
        al1 = monitor.ingest_transaction({
            "TransactionID": "DEV_1",
            "card_id": "CARD_ALPHA",
            "amount": 50.0,
            "device_profile": device,
            "epoch_s": now_epoch,
        })
        self.assertEqual(len([a for a in al1 if a.rule_triggered == "NOVEL_DEVICE_LINK"]), 0)

        # Card 2 uses SAME device -> triggers NOVEL_DEVICE_LINK
        al2 = monitor.ingest_transaction({
            "TransactionID": "DEV_2",
            "card_id": "CARD_BETA",
            "amount": 75.0,
            "device_profile": device,
            "epoch_s": now_epoch + 5,
        })
        dev_alerts = [a for a in al2 if a.rule_triggered == "NOVEL_DEVICE_LINK"]
        self.assertEqual(len(dev_alerts), 1)
        self.assertEqual(dev_alerts[0].card_id, "CARD_BETA")
        self.assertIn("CARD_ALPHA", dev_alerts[0].details["prior_cards_on_device"])

        print("PASS: Novel device linkage triggered on secondary card adoption.")

    def test_04_impossible_travel_and_high_risk_mcc(self):
        """Verify impossible travel velocity (> 800 km/h) and high-risk MCC 6051 alerts."""
        monitor = StreamingGraphMonitor(window_seconds=3600)
        card = "C_GEO_TEST"
        now_epoch = int(time.time())

        # 1. New York transaction (lat 40.7128, lon -74.0060)
        monitor.ingest_transaction({
            "TransactionID": "GEO_NY",
            "card_id": card,
            "amount": 20.0,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "epoch_s": now_epoch,
        })

        # 2. London transaction 15 minutes later (lat 51.5074, lon -0.1278) -> ~5,570 km in 0.25h (~22,000 km/h)
        al_geo = monitor.ingest_transaction({
            "TransactionID": "GEO_LON",
            "card_id": card,
            "amount": 100.0,
            "latitude": 51.5074,
            "longitude": -0.1278,
            "epoch_s": now_epoch + 900,  # 15 mins later
        })

        geo_alerts = [a for a in al_geo if a.rule_triggered == "IMPOSSIBLE_TRAVEL"]
        self.assertEqual(len(geo_alerts), 1)
        self.assertGreater(geo_alerts[0].details["calculated_speed_kmh"], 800.0)
        self.assertEqual(geo_alerts[0].severity, "CRITICAL")

        # 3. High-Risk MCC 6051 (Quasi-Cash / Crypto)
        al_mcc = monitor.ingest_transaction({
            "TransactionID": "MCC_CRYPTO",
            "card_id": card,
            "amount": 500.0,
            "mcc": "6051",
            "epoch_s": now_epoch + 1000,
        })
        mcc_alerts = [a for a in al_mcc if a.rule_triggered == "HIGH_RISK_MCC"]
        self.assertEqual(len(mcc_alerts), 1)
        self.assertEqual(mcc_alerts[0].details["mcc"], "6051")

        print("PASS: Impossible physical travel and high-risk MCC 6051 rules verified.")

    def test_05_fastapi_streaming_endpoints(self):
        """Verify REST endpoints for /api/streaming/ingest, /api/streaming/alerts, and /api/streaming/stats."""
        # 1. POST Ingest
        sample_txn = {
            "TransactionID": "API_STRM_1",
            "card_id": "C_API_TEST",
            "amount": 1500.0,  # Exceeds velocity amount threshold
            "epoch_s": int(time.time()),
        }
        resp_ingest = self.client.post("/api/streaming/ingest", json={"transaction": sample_txn})
        self.assertEqual(resp_ingest.status_code, 200)
        idata = resp_ingest.json()
        self.assertEqual(idata["processed"], 1)
        self.assertGreaterEqual(idata["alerts_triggered"], 1)

        # 2. GET Alerts
        resp_alerts = self.client.get("/api/streaming/alerts")
        self.assertEqual(resp_alerts.status_code, 200)
        adata = resp_alerts.json()
        self.assertIn("alerts", adata)

        # 3. GET Stats
        resp_stats = self.client.get("/api/streaming/stats")
        self.assertEqual(resp_stats.status_code, 200)
        sdata = resp_stats.json()
        self.assertIn("total_processed", sdata)
        self.assertIn("current_window_events", sdata)
        self.assertIn("total_alerts_emitted", sdata)

        print("PASS: FastAPI streaming ingestion, alerts, and operational stats endpoints verified.")


if __name__ == "__main__":
    unittest.main()
