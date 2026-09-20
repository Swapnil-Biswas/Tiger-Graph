"""
Unit Tests for Self-Contained Interactive HTML Incident Dossier Exporter
Validates HTML structure, Cytoscape graph embedding, section completeness,
file export, and API endpoint delivery.
"""

import os
import unittest
from fastapi.testclient import TestClient
from src.agent.graph import FraudInvestigatorAgent
from src.cases.dossier_exporter import IncidentDossierExporter
from src.api.main import app


class TestIncidentDossierExporter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Incident Dossier Exporter Test Suite ===")
        cls.agent = FraudInvestigatorAgent()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "client"):
            cls.client.close()

    def test_html_dossier_structure_and_sections(self):
        """Dossier must be valid HTML containing all 8 critical operational sections."""
        ans = self.agent.investigate_case("HHG-004")
        html_str = IncidentDossierExporter.export_html_dossier(ans)

        # Structural HTML assertions
        self.assertIn("<!DOCTYPE html>", html_str)
        self.assertIn("<title>Incident Dossier — HHG-004</title>", html_str)
        self.assertIn("cytoscape.min.js", html_str)
        self.assertIn("id=\"cy-container\"", html_str)

        # Section assertions
        self.assertIn("1. Autonomous Investigation Narrative", html_str)
        self.assertIn("2. Incident Graph Topology", html_str)
        self.assertIn("3. Grounding Evidence & Citations", html_str)
        self.assertIn("4. Counterfactual Decision Boundary & Sensitivity Sliders", html_str)
        self.assertIn("5. Next-Best-Action Decisions & Policy Routing", html_str)
        self.assertIn("6. Regulatory Filing", html_str)
        self.assertIn("Deterministic Audit Trail Certified", html_str)

        # Content assertions
        self.assertIn("FRAUD", html_str)
        self.assertIn("Card Not Present New Device", html_str)
        self.assertIn("EXPOSURE", html_str)

    def test_dossier_file_persistence(self):
        """Exporting to a file path must persist valid HTML on disk."""
        ans = self.agent.investigate_case("HHG-001")
        sample_path = "docs/sample_incident_dossier.html"
        
        IncidentDossierExporter.export_html_dossier(ans, output_path=sample_path)
        self.assertTrue(os.path.exists(sample_path), "Dossier HTML file not saved.")
        self.assertGreater(os.path.getsize(sample_path), 2000, "Dossier file abnormally small.")

    def test_api_dossier_endpoint(self):
        """API endpoint GET /api/cases/{case_id}/dossier must return 200 text/html."""
        resp = self.client.get("/api/cases/HHG-004/dossier")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers["content-type"])
        self.assertIn("TigerGraph Incident Dossier", resp.text)

    def test_decision_boundary_and_sliders_visualization(self):
        """Dossier must render interactive decision boundary gauge and counterfactual sliders."""
        ans = self.agent.investigate_case("HHG-001")
        html_str = IncidentDossierExporter.export_html_dossier(ans)

        # Decision boundary gauge assertions
        self.assertIn("4. Counterfactual Decision Boundary & Sensitivity Sliders", html_str)
        self.assertIn("id=\"sim-marker\"", html_str)
        self.assertIn("id=\"sim-prob-val\"", html_str)
        self.assertIn("id=\"sim-verdict-badge\"", html_str)
        self.assertIn("linear-gradient(90deg, #10b981 0%, #f59e0b 50%, #ef4444 100%)", html_str)

        # Interactive slider assertions
        self.assertIn("id=\"slider-cust\"", html_str)
        self.assertIn("id=\"slider-dev\"", html_str)
        self.assertIn("id=\"slider-geo\"", html_str)
        self.assertIn("id=\"slider-vel\"", html_str)
        self.assertIn("updateSimulation()", html_str)
        self.assertIn("Interactive Sensitivity Simulator", html_str)


if __name__ == "__main__":
    unittest.main()
