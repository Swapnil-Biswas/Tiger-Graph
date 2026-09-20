"""
Unit Tests for Grafana SLA Dashboard and Prometheus Alerting Rules (tests/test_grafana_dashboard.py)
"""

import os
import json
import unittest
import yaml


class TestGrafanaAndAlerting(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.dash_path = os.path.join(self.repo_root, "deploy", "grafana", "fraud_sla_dashboard.json")
        self.alerts_path = os.path.join(self.repo_root, "deploy", "grafana", "alerts.yml")

    def test_01_grafana_dashboard_structure(self):
        """Verify Grafana dashboard JSON schema, UID, refresh rate, and panels."""
        self.assertTrue(os.path.exists(self.dash_path), "fraud_sla_dashboard.json must exist")
        with open(self.dash_path, "r", encoding="utf-8") as f:
            dash = json.load(f)

        self.assertEqual(dash.get("uid"), "tigergraph-fraud-sla")
        self.assertIn("TigerGraph", dash.get("title", ""))
        self.assertEqual(dash.get("refresh"), "5s")
        self.assertIn("panels", dash)

        panels = dash["panels"]
        self.assertTrue(len(panels) >= 8, f"Dashboard must contain at least 8 panels, found {len(panels)}")

        panel_titles = [p.get("title", "") for p in panels]
        self.assertTrue(any("SLA Status" in t for t in panel_titles))
        self.assertTrue(any("Latency SLA Percentiles" in t for t in panel_titles))
        self.assertTrue(any("Streaming Transaction Throughput" in t for t in panel_titles))
        self.assertTrue(any("Streaming Anomaly Alerts" in t for t in panel_titles))
        self.assertTrue(any("Graph Store Indexed Entities" in t for t in panel_titles))

    def test_02_grafana_prometheus_expressions(self):
        """Verify that panels query official Prometheus metrics exposed by the agent."""
        with open(self.dash_path, "r", encoding="utf-8") as f:
            dash = json.load(f)

        all_exprs = []
        for p in dash["panels"]:
            for target in p.get("targets", []):
                if "expr" in target:
                    all_exprs.append(target["expr"])

        expr_str = " ".join(all_exprs)
        self.assertIn("investigation_latency_seconds", expr_str)
        self.assertIn("streaming_transactions_ingested_total", expr_str)
        self.assertIn("streaming_alerts_emitted_total", expr_str)
        self.assertIn("policy_actions_authorized_total", expr_str)
        self.assertIn("graph_indexed_entities", expr_str)

    def test_03_prometheus_alerting_rules(self):
        """Verify Alertmanager rules file syntax, alert triggers, severity labels, and annotations."""
        self.assertTrue(os.path.exists(self.alerts_path), "alerts.yml must exist")
        with open(self.alerts_path, "r", encoding="utf-8") as f:
            alerts_data = yaml.safe_load(f)

        self.assertIn("groups", alerts_data)
        groups = alerts_data["groups"]
        self.assertTrue(len(groups) >= 1)

        group = groups[0]
        self.assertEqual(group["name"], "tigergraph_fraud_sla_alerts")
        rules = group.get("rules", [])
        self.assertTrue(len(rules) >= 4)

        alert_names = [r.get("alert") for r in rules]
        self.assertIn("FraudInvestigationSLAViolation", alert_names)
        self.assertIn("HighSeverityStreamingAnomalySurge", alert_names)
        self.assertIn("StreamingVelocitySpikeBurst", alert_names)
        self.assertIn("GraphEntityCapacityWarning", alert_names)

        for r in rules:
            self.assertIn("expr", r)
            self.assertIn("for", r)
            self.assertIn("labels", r)
            self.assertIn("severity", r["labels"])
            self.assertIn("annotations", r)
            self.assertIn("summary", r["annotations"])


if __name__ == "__main__":
    unittest.main()
