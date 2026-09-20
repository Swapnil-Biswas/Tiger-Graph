"""
Unit tests for Executive Case Summary Briefing Exporter (Markdown & Printable HTML)
"""

import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.cases.briefing_exporter import ExecutiveBriefingExporter
from src.api.main import app


class TestBriefingExporter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = ExecutiveBriefingExporter(cases_dir=str(ROOT_DIR / "cases"))
        cls.client = TestClient(app)

    def test_markdown_briefing_fraud_case(self):
        md = self.exporter.export_markdown_briefing("HHG-006")
        self.assertIn("# EXECUTIVE FRAUD INCIDENT BRIEFING: HHG-006", md)
        self.assertIn("**Investigative Verdict** | **`FRAUD`**", md)
        self.assertIn("Multi-Hop Graph Evidence Findings", md)
        self.assertIn("Next-Best-Action Policy & Guardrail Enforcement", md)
        self.assertIn("Counterfactual Decision Sensitivity", md)
        self.assertIn("FinCEN Regulatory SAR Narrative", md)
        self.assertIn("REQUIRED (31 CFR 1020.320)", md)
        self.assertIn("[OFFICIAL BRIEFING CERTIFICATION]", md)

    def test_markdown_briefing_legitimate_case(self):
        md = self.exporter.export_markdown_briefing("HHG-002")
        self.assertIn("# EXECUTIVE FRAUD INCIDENT BRIEFING: HHG-002", md)
        self.assertIn("**Investigative Verdict** | **`LEGITIMATE`**", md)
        self.assertIn("SAR filing was **NOT required**", md)

    def test_html_briefing_structure(self):
        html = self.exporter.export_html_briefing("HHG-001")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<title>Executive Briefing: HHG-001</title>", html)
        self.assertIn("@media print", html)
        self.assertIn("window.print()", html)
        self.assertIn("RESTRICTED // BSA-AML", html)
        self.assertIn("Gross Exposure", html)
        self.assertIn("Verified Multi-Hop Graph Evidence", html)
        self.assertIn("Federal Rules of Evidence 902(13) & 902(14)", html)

    def test_case_not_found_exception(self):
        with self.assertRaises(FileNotFoundError):
            self.exporter.export_markdown_briefing("NON-EXISTENT-CASE")

    def test_api_endpoints_markdown_and_html(self):
        # Markdown endpoint
        resp_md = self.client.get("/api/cases/HHG-001/briefing/markdown")
        self.assertEqual(resp_md.status_code, 200)
        self.assertIn("text/markdown", resp_md.headers["content-type"])
        self.assertIn("EXECUTIVE FRAUD INCIDENT BRIEFING: HHG-001", resp_md.text)

        # HTML endpoint
        resp_html = self.client.get("/api/cases/HHG-001/briefing/html")
        self.assertEqual(resp_html.status_code, 200)
        self.assertIn("text/html", resp_html.headers["content-type"])
        self.assertIn("Executive Briefing: HHG-001", resp_html.text)

    def test_api_case_not_found_404(self):
        resp = self.client.get("/api/cases/NON-EXISTENT-CASE/briefing/markdown")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
