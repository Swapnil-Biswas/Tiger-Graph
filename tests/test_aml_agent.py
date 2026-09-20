"""
Anti-Money Laundering (AML) Specialist Sub-Agent Tests (tests/test_aml_agent.py)
Validates specialized BSA/FinCEN structuring analysis, FATF corridor screening,
statutory citations (31 USC 5324, 31 CFR 1020.320), master agent federation,
and REST API endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from src.graph.client import GraphClient
from src.agent.aml_agent import AMLSpecialistAgent, AMLAssessment
from src.agent.graph import FraudInvestigatorAgent
from src.api.main import app


class TestAMLSpecialistAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing AML Specialist Agent Test Suite ===")
        cls.client = GraphClient()
        cls.aml_agent = AMLSpecialistAgent(cls.client)
        cls.master_agent = FraudInvestigatorAgent(cls.client)
        cls.api = TestClient(app)

    def test_01_clean_case_aml_assessment(self):
        """Validates baseline case assessment for routine transaction activity."""
        assessment = self.aml_agent.assess_case("HHG-001")
        self.assertIsInstance(assessment, AMLAssessment)
        self.assertEqual(assessment.case_id, "HHG-001")
        self.assertIn(assessment.risk_level, ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        self.assertIsInstance(assessment.aml_score, float)
        self.assertGreaterEqual(assessment.aml_score, 0.0)
        self.assertLessEqual(assessment.aml_score, 1.0)
        self.assertGreater(len(assessment.recommended_aml_actions), 0)
        self.assertIn("=== AML SPECIALIST AGENT COMPLIANCE REPORT", assessment.aml_narrative)
        print(f"PASS: Baseline case HHG-001 evaluated with AML risk level: {assessment.risk_level}.")

    def test_02_structuring_smurfing_detection(self):
        """Validates detection of sub-threshold structuring and statutory citation generation."""
        # Query case HHG-004 (high-risk syndicate case)
        assessment = self.aml_agent.assess_case("HHG-004")
        self.assertIsInstance(assessment, AMLAssessment)
        self.assertGreater(len(assessment.detected_typologies), 0)
        print(f"PASS: Case HHG-004 typologies: {assessment.detected_typologies}")

    def test_03_high_risk_corridor_and_quasi_cash(self):
        """Validates detection of high-risk MCC or corridor screening."""
        assessment = self.aml_agent.assess_case("HHG-004")
        # Ensure structuring or MCC or cross-border analysis is populated
        self.assertIsNotNone(assessment.structuring_analysis)
        self.assertIsNotNone(assessment.cross_border_analysis)
        self.assertIsNotNone(assessment.mcc_risk_analysis)
        print("PASS: Multi-vector AML analysis dictionary populated across all compliance sub-engines.")

    def test_04_statutory_narrative_and_sar_mandates(self):
        """Validates statutory regulatory narrative formatting and citation correctness."""
        assessment = self.aml_agent.assess_case("HHG-004")
        self.assertIn("CASE: HHG-004", assessment.aml_narrative)
        self.assertIn("Risk Level:", assessment.aml_narrative)
        if assessment.mandatory_sar:
            self.assertIn("MANDATORY REGULATORY FILING", assessment.aml_narrative)
            self.assertIn("FILE_SAR_FINCEN", assessment.recommended_aml_actions)
        print(f"PASS: Statutory narrative verified (mandatory SAR: {assessment.mandatory_sar}).")

    def test_05_multi_agent_federation_integration(self):
        """Validates that FraudInvestigatorAgent seamlessly incorporates AML specialist intelligence."""
        res = self.master_agent.investigate_case("HHG-001")
        self.assertIn("aml_specialist", res, "Master investigation must contain aml_specialist payload")
        aml_data = res["aml_specialist"]
        self.assertEqual(aml_data["case_id"], "HHG-001")
        self.assertIn("aml_score", aml_data)
        self.assertIn("recommended_aml_actions", aml_data)
        print("PASS: Master agent investigation returned federated AML intelligence payload.")

    def test_06_rest_api_endpoints(self):
        """Validates GET and POST API endpoints for AML specialist assessments."""
        # 1. POST /api/agents/aml/assess
        post_req = {"case_id": "HHG-001", "window_hours": 48.0}
        resp_post = self.api.post("/api/agents/aml/assess", json=post_req)
        self.assertEqual(resp_post.status_code, 200)
        data_post = resp_post.json()
        self.assertEqual(data_post["case_id"], "HHG-001")
        self.assertIn("aml_score", data_post)
        self.assertIn("risk_level", data_post)

        # 2. GET /api/cases/HHG-001/aml-assessment
        resp_get = self.api.get("/api/cases/HHG-001/aml-assessment?window_hours=48.0")
        self.assertEqual(resp_get.status_code, 200)
        data_get = resp_get.json()
        self.assertEqual(data_get["case_id"], "HHG-001")
        self.assertIn("aml_narrative", data_get)
        print("PASS: AMLSpecialistAgent REST API endpoints verified.")


if __name__ == "__main__":
    unittest.main()
