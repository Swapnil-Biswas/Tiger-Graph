"""
Unit Tests for Interactive Web UI Executive Briefing & GraphQL Tabs (tests/test_ui_briefing_graphql.py)
Validates:
  1. Presence and integrity of new navigation tabs (tab-briefing, tab-graphql) in ui/index.html
  2. Element IDs, containers, and iframe bindings in view-briefing and view-graphql
  3. Frontend application logic in ui/app.js (briefing, diff, GraphQL runner)
  4. Backend API endpoint responsiveness for all backing services
"""

import re
import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.api.main import app


class TestUIBriefingGraphQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.html_path = ROOT_DIR / "ui" / "index.html"
        cls.js_path = ROOT_DIR / "ui" / "app.js"
        cls.html_content = cls.html_path.read_text(encoding="utf-8")
        cls.js_content = cls.js_path.read_text(encoding="utf-8")

    def test_01_navigation_tab_buttons(self):
        """Navigation bar contains buttons for Executive Briefing and GraphQL Explorer tabs."""
        self.assertIn('id="tab-briefing"', self.html_content)
        self.assertIn('data-tab="briefing"', self.html_content)
        self.assertIn('id="tab-graphql"', self.html_content)
        self.assertIn('data-tab="graphql"', self.html_content)

    def test_02_briefing_view_structure(self):
        """Briefing view contains selector, action buttons, compliance scorecards, and iframe/markdown display."""
        self.assertIn('id="view-briefing"', self.html_content)
        self.assertIn('id="select-briefing-case"', self.html_content)
        self.assertIn('id="select-briefing-mode"', self.html_content)
        self.assertIn('id="btn-load-briefing"', self.html_content)
        self.assertIn('id="btn-print-briefing"', self.html_content)
        self.assertIn('id="briefing-compliance-badge"', self.html_content)
        self.assertIn('id="briefing-stat-fincen"', self.html_content)
        self.assertIn('id="briefing-stat-poca"', self.html_content)
        self.assertIn('id="briefing-stat-gdpr"', self.html_content)
        self.assertIn('id="briefing-stat-policy"', self.html_content)
        self.assertIn('id="briefing-stat-fre902"', self.html_content)
        self.assertIn('id="briefing-iframe"', self.html_content)
        self.assertIn('id="briefing-markdown-pre"', self.html_content)

    def test_03_graphql_diff_view_structure(self):
        """GraphQL view contains graph diff inspector and interactive query runner elements."""
        self.assertIn('id="view-graphql"', self.html_content)
        self.assertIn('id="diff-risk-badge"', self.html_content)
        self.assertIn('id="select-diff-case"', self.html_content)
        self.assertIn('id="btn-run-diff"', self.html_content)
        self.assertIn('id="diff-stat-nodes-added"', self.html_content)
        self.assertIn('id="diff-stat-edges-added"', self.html_content)
        self.assertIn('id="diff-stat-classification"', self.html_content)
        self.assertIn('id="select-graphql-preset"', self.html_content)
        self.assertIn('id="btn-execute-graphql"', self.html_content)
        self.assertIn('id="graphql-query-input"', self.html_content)
        self.assertIn('id="graphql-response-output"', self.html_content)

    def test_04_js_logic_functions(self):
        """app.js implements all required briefing, diff, and GraphQL runner functions."""
        self.assertIn("function loadExecutiveBriefing", self.js_content)
        self.assertIn("function printExecutiveBriefing", self.js_content)
        self.assertIn("function runGraphTemporalDiff", self.js_content)
        self.assertIn("function initGraphQLRunner", self.js_content)
        self.assertIn("function executeGraphQLQuery", self.js_content)
        self.assertIn("GRAPHQL_PRESETS", self.js_content)
        self.assertIn("CaseOverview", self.js_content)
        self.assertIn("RecentFraudCases", self.js_content)

    def test_05_backend_briefing_and_compliance_apis(self):
        """Backend APIs supporting the briefing UI return valid responses."""
        # 1. HTML briefing
        res_html = self.client.get("/api/cases/HHG-001/briefing/html")
        self.assertEqual(res_html.status_code, 200)
        self.assertIn("<!DOCTYPE html>", res_html.text)

        # 2. Markdown briefing
        res_md = self.client.get("/api/cases/HHG-001/briefing/markdown")
        self.assertEqual(res_md.status_code, 200)
        self.assertIn("# EXECUTIVE FRAUD INCIDENT BRIEFING", res_md.text)

        # 3. Compliance HTML certificate
        res_comp = self.client.get("/api/compliance/report/HHG-001?format=html")
        self.assertEqual(res_comp.status_code, 200)
        self.assertIn("Compliance Certificate", res_comp.text)

    def test_06_backend_diff_and_graphql_apis(self):
        """Backend APIs supporting the diff & GraphQL UI return valid responses."""
        # 1. Graph diff endpoint
        res_diff = self.client.get("/api/cases/HHG-001/graph-diff")
        self.assertEqual(res_diff.status_code, 200)
        diff_data = res_diff.json()
        self.assertIn("risk_shift", diff_data)
        self.assertIn("delta_node_count", diff_data)

        # 2. GraphQL query endpoint
        query = 'query { case(caseId: "HHG-001") { case_id verdict fraud_probability } }'
        res_gql = self.client.post("/graphql", json={"query": query})
        self.assertEqual(res_gql.status_code, 200)
        gql_data = res_gql.json()
        self.assertIn("data", gql_data)
        self.assertEqual(gql_data["data"]["case"]["case_id"], "HHG-001")


if __name__ == "__main__":
    unittest.main()
