"""
Cyber-Forensics & Device Fingerprint Specialist Sub-Agent Tests (tests/test_cyber_agent.py)
Validates hardware device nexus forensics (Q4), bot attack periodicity (Q15),
sybil account network resolution (Q23), master agent federation, and REST API endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from src.graph.client import GraphClient
from src.agent.cyber_agent import CyberForensicsAgent, CyberForensicsAssessment
from src.agent.graph import FraudInvestigatorAgent
from src.api.main import app


class TestCyberForensicsAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Cyber Forensics Agent Test Suite ===")
        cls.client = GraphClient()
        cls.cyber_agent = CyberForensicsAgent(cls.client)
        cls.master_agent = FraudInvestigatorAgent(cls.client)
        cls.api = TestClient(app)

    def test_01_clean_case_cyber_assessment(self):
        """Validates baseline case assessment for routine device telemetry."""
        assessment = self.cyber_agent.assess_case("HHG-001")
        self.assertIsInstance(assessment, CyberForensicsAssessment)
        self.assertEqual(assessment.case_id, "HHG-001")
        self.assertIn(assessment.threat_tier, ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        self.assertIsInstance(assessment.cyber_risk_score, float)
        self.assertGreaterEqual(assessment.cyber_risk_score, 0.0)
        self.assertLessEqual(assessment.cyber_risk_score, 1.0)
        self.assertGreater(len(assessment.recommended_cyber_defenses), 0)
        self.assertIn("=== CYBER-FORENSICS & HARDWARE INTEGRITY REPORT", assessment.forensics_narrative)
        print(f"PASS: Baseline case HHG-001 evaluated with threat tier: {assessment.threat_tier}.")

    def test_02_device_pooling_and_nexus_detection(self):
        """Validates device sharing nexus detection and hardware threat scoring."""
        assessment = self.cyber_agent.assess_case("HHG-004")
        self.assertIsInstance(assessment, CyberForensicsAssessment)
        self.assertIsNotNone(assessment.device_nexus_summary)
        print(f"PASS: Case HHG-004 evaluated {len(assessment.device_nexus_summary)} hardware profiles.")

    def test_03_sybil_clusters_and_bot_periodicity(self):
        """Validates sybil analysis and bot periodicity evaluation."""
        assessment = self.cyber_agent.assess_case("HHG-004")
        self.assertIsInstance(assessment.connected_sybil_cards, list)
        self.assertIsInstance(assessment.compromised_devices, list)
        self.assertIsNotNone(assessment.bot_burst_summary)
        print("PASS: Sybil cluster and bot burst evaluation sub-dictionaries verified.")

    def test_04_forensics_narrative_formatting(self):
        """Validates structured forensics narrative formatting and defense recommendations."""
        assessment = self.cyber_agent.assess_case("HHG-004")
        self.assertIn("CASE: HHG-004", assessment.forensics_narrative)
        self.assertIn("Threat Tier:", assessment.forensics_narrative)
        self.assertIn("Recommended Defensive Controls:", assessment.forensics_narrative)
        print("PASS: Forensics narrative format and defensive recommendations verified.")

    def test_05_multi_agent_federation_integration(self):
        """Validates that FraudInvestigatorAgent seamlessly incorporates cyber forensics intelligence."""
        res = self.master_agent.investigate_case("HHG-001")
        self.assertIn("cyber_forensics", res, "Master investigation must contain cyber_forensics payload")
        cyber_data = res["cyber_forensics"]
        self.assertEqual(cyber_data["case_id"], "HHG-001")
        self.assertIn("cyber_risk_score", cyber_data)
        self.assertIn("recommended_cyber_defenses", cyber_data)
        print("PASS: Master agent investigation returned federated cyber forensics intelligence payload.")

    def test_06_rest_api_endpoints(self):
        """Validates GET and POST API endpoints for cyber forensics assessments."""
        # 1. POST /api/agents/cyber/assess
        post_req = {"case_id": "HHG-001"}
        resp_post = self.api.post("/api/agents/cyber/assess", json=post_req)
        self.assertEqual(resp_post.status_code, 200)
        data_post = resp_post.json()
        self.assertEqual(data_post["case_id"], "HHG-001")
        self.assertIn("cyber_risk_score", data_post)
        self.assertIn("threat_tier", data_post)

        # 2. GET /api/cases/HHG-001/cyber-assessment
        resp_get = self.api.get("/api/cases/HHG-001/cyber-assessment")
        self.assertEqual(resp_get.status_code, 200)
        data_get = resp_get.json()
        self.assertEqual(data_get["case_id"], "HHG-001")
        self.assertIn("forensics_narrative", data_get)
        print("PASS: CyberForensicsAgent REST API endpoints verified.")


if __name__ == "__main__":
    unittest.main()
