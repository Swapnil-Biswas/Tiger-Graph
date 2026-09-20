"""
Unit Test Suite for Real-Time Web UI Streaming Live Monitor & Dynamic Alert Feed
(tests/test_ui_streaming.py)

Tests static frontend assets, DOM elements, script bindings, and streaming dashboard integration.
"""

import unittest
from fastapi.testclient import TestClient

from src.api.main import app


class TestUIStreaming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Web UI Streaming Live Monitor Test Suite ===")
        cls.client = TestClient(app)

    def test_01_static_assets_delivery(self):
        """Verify delivery of HTML, JS, and CSS static frontend assets."""
        resp_html = self.client.get("/")
        self.assertEqual(resp_html.status_code, 200)

        resp_js = self.client.get("/app.js")
        self.assertEqual(resp_js.status_code, 200)

        resp_css = self.client.get("/style.css")
        self.assertEqual(resp_css.status_code, 200)

        print("PASS: Static frontend assets delivered successfully.")

    def test_02_required_streaming_dom_elements(self):
        """Verify presence of streaming tab, ticker metrics, simulation buttons, and alert feed in index.html."""
        resp_html = self.client.get("/")
        html = resp_html.text

        # 1. Navigation Tab
        self.assertIn('id="tab-streaming"', html)
        self.assertIn('id="badge-streaming-alerts"', html)

        # 2. Tab View Section
        self.assertIn('id="view-streaming"', html)

        # 3. Operational Metrics Ticker
        self.assertIn('id="streaming-stat-total"', html)
        self.assertIn('id="streaming-stat-window"', html)
        self.assertIn('id="streaming-stat-cards"', html)
        self.assertIn('id="streaming-stat-alerts"', html)
        self.assertIn('id="streaming-stat-critical"', html)

        # 4. Simulation Buttons
        self.assertIn('id="btn-sim-velocity"', html)
        self.assertIn('id="btn-sim-device"', html)
        self.assertIn('id="btn-sim-travel"', html)
        self.assertIn('id="btn-sim-mcc"', html)

        # 5. Alert Feed Container
        self.assertIn('id="streaming-alerts-feed"', html)
        self.assertIn('id="select-alert-severity"', html)

        print("PASS: All required streaming DOM elements present in index.html.")

    def test_03_app_js_streaming_bindings(self):
        """Verify app.js contains streaming controller functions and simulation handlers."""
        resp_js = self.client.get("/app.js")
        js = resp_js.text

        self.assertIn("loadStreamingDashboard", js)
        self.assertIn("loadStreamingStats", js)
        self.assertIn("loadStreamingAlerts", js)
        self.assertIn("setupStreamingListeners", js)
        self.assertIn("postStreamingTransactions", js)
        self.assertIn("dispatchStreamingAction", js)
        self.assertIn("/api/streaming/stats", js)
        self.assertIn("/api/streaming/alerts", js)
        self.assertIn("/api/streaming/ingest", js)

        print("PASS: JavaScript streaming controller bindings verified in app.js.")

    def test_04_style_css_streaming_classes(self):
        """Verify style.css contains streaming grid, ticker, simulation buttons, and alert card styling."""
        resp_css = self.client.get("/style.css")
        css = resp_css.text

        self.assertIn(".streaming-ticker-grid", css)
        self.assertIn(".ticker-card", css)
        self.assertIn(".sim-buttons-grid", css)
        self.assertIn(".sim-btn", css)
        self.assertIn(".streaming-alerts-feed", css)
        self.assertIn(".streaming-alert-card", css)
        self.assertIn(".streaming-alert-card.critical", css)
        self.assertIn(".alert-rule-badge", css)

        print("PASS: CSS styling for streaming dashboard verified in style.css.")

    def test_05_api_streaming_contract_compatibility(self):
        """Verify that the API streaming contracts expected by app.js are functional."""
        # 1. Stats contract
        resp_stats = self.client.get("/api/streaming/stats")
        self.assertEqual(resp_stats.status_code, 200)
        sdata = resp_stats.json()
        self.assertIn("total_processed", sdata)
        self.assertIn("current_window_events", sdata)

        # 2. Ingest contract
        sample_txns = [
            {"TransactionID": "UI_TEST_1", "card_id": "C_UI_TEST", "amount": 100.0, "epoch_s": 1600000000},
            {"TransactionID": "UI_TEST_2", "card_id": "C_UI_TEST", "amount": 200.0, "epoch_s": 1600000005},
        ]
        resp_ingest = self.client.post("/api/streaming/ingest", json={"transactions": sample_txns})
        self.assertEqual(resp_ingest.status_code, 200)
        idata = resp_ingest.json()
        self.assertEqual(idata["processed"], 2)

        # 3. Alerts contract
        resp_alerts = self.client.get("/api/streaming/alerts")
        self.assertEqual(resp_alerts.status_code, 200)
        adata = resp_alerts.json()
        self.assertIn("alerts", adata)

        print("PASS: API streaming endpoints fully compatible with frontend controller.")


if __name__ == "__main__":
    unittest.main()
