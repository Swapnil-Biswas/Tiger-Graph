"""
Multi-Agent Debate & Weighted Majority Voting Protocol Tests (tests/test_consensus.py)
Validates multi-agent deliberation, mathematical weight bounds, statutory AML vetoes,
cyber defense isolation, conflict resolution transcripts, and REST API endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from src.agent.consensus import MultiAgentConsensusEngine, FederatedConsensusDossier
from src.agent.graph import FraudInvestigatorAgent
from src.api.main import app


class TestMultiAgentConsensusEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Multi-Agent Consensus Test Suite ===")
        cls.engine = MultiAgentConsensusEngine()
        cls.agent = FraudInvestigatorAgent()
        cls.api = TestClient(app)

    def test_01_unanimous_consensus(self):
        """Validates deliberation when all agents agree on a low-risk legitimate case."""
        mock_payload = {
            "case": {
                "case_id": "TEST-001",
                "verdict": "legitimate",
                "fraud_probability": 0.05,
                "exposure_usd": 45.0,
            },
            "next_best_actions": {"final": [{"action": "ALLOW_TRANSACTION", "route": "auto"}]},
            "aml_specialist": {
                "aml_score": 0.05,
                "risk_level": "LOW",
                "mandatory_sar": False,
                "recommended_aml_actions": ["STANDARD_MONITORING"],
            },
            "cyber_forensics": {
                "cyber_risk_score": 0.05,
                "threat_tier": "LOW",
                "recommended_cyber_defenses": ["MAINTAIN_STANDARD_TELEMETRY"],
            },
        }

        dossier = self.engine.deliberate(mock_payload)
        self.assertIsInstance(dossier, FederatedConsensusDossier)
        self.assertEqual(dossier.consensus_verdict, "legitimate")
        self.assertLess(dossier.consensus_probability, 0.20)
        self.assertGreaterEqual(dossier.consensus_confidence, 0.90)
        self.assertEqual(len(dossier.conflicts_detected), 0)
        self.assertIn("ALLOW_TRANSACTION", dossier.resolved_unified_actions)
        print("PASS: Unanimous low-risk case produced legitimate consensus with high confidence.")

    def test_02_aml_statutory_veto(self):
        """Validates that AML mandatory SAR veto cannot be overridden by other agents."""
        mock_payload = {
            "case": {
                "case_id": "TEST-AML-VETO",
                "verdict": "review",
                "fraud_probability": 0.35,
                "exposure_usd": 12500.0,
            },
            "next_best_actions": {"final": [{"action": "VERIFY_WITH_CUSTOMER", "route": "L2_LEAD"}]},
            "aml_specialist": {
                "aml_score": 0.85,
                "risk_level": "CRITICAL",
                "mandatory_sar": True,
                "detected_typologies": ["AML_STRUCTURING_SMURFING"],
                "recommended_aml_actions": ["FILE_SAR_FINCEN", "FLAG_STRUCTURING_NETWORK"],
            },
            "cyber_forensics": {
                "cyber_risk_score": 0.20,
                "threat_tier": "LOW",
                "recommended_cyber_defenses": [],
            },
        }

        dossier = self.engine.deliberate(mock_payload)
        self.assertIn("FILE_SAR_FINCEN", dossier.resolved_unified_actions)
        self.assertGreater(len(dossier.mandatory_regulatory_filings), 0)
        self.assertEqual(dossier.consensus_verdict, "aml_escalation")
        self.assertIn("CONFLICT_LOW_CARD_RISK_VS_MANDATORY_AML_SAR", dossier.conflicts_detected)
        print("PASS: Statutory AML SAR veto strictly enforced with aml_escalation consensus.")

    def test_03_cyber_compromise_isolation(self):
        """Validates that hardware blacklisting is merged into actions even if fraud verdict is legitimate."""
        mock_payload = {
            "case": {
                "case_id": "TEST-CYBER-ISOLATE",
                "verdict": "legitimate",
                "fraud_probability": 0.12,
                "exposure_usd": 150.0,
            },
            "next_best_actions": {"final": [{"action": "ALLOW_TRANSACTION", "route": "auto"}]},
            "aml_specialist": {
                "aml_score": 0.05,
                "risk_level": "LOW",
                "mandatory_sar": False,
            },
            "cyber_forensics": {
                "cyber_risk_score": 0.75,
                "threat_tier": "CRITICAL",
                "recommended_cyber_defenses": ["BLACKLIST_DEVICE_HARDWARE", "STEP_UP_DEVICE_BIOMETRICS"],
            },
        }

        dossier = self.engine.deliberate(mock_payload)
        self.assertIn("BLACKLIST_DEVICE_HARDWARE", dossier.resolved_unified_actions)
        self.assertIn("STEP_UP_DEVICE_BIOMETRICS", dossier.resolved_unified_actions)
        self.assertIn("CONFLICT_FRAUD_LEGITIMATE_VS_CYBER_HARDWARE_ALERT", dossier.conflicts_detected)
        print("PASS: Cyber hardware defenses isolated compromised device despite transaction allowance.")

    def test_04_mathematical_weights_and_bounds(self):
        """Validates agent weights sum to 1.00 and consensus probability is strictly bounded."""
        mock_payload = {
            "case": {"case_id": "TEST-MATH", "verdict": "review", "fraud_probability": 0.45, "exposure_usd": 15000.0},
            "aml_specialist": {"aml_score": 0.60, "risk_level": "HIGH", "mandatory_sar": True, "detected_typologies": ["AML_STRUCTURING"]},
            "cyber_forensics": {"cyber_risk_score": 0.30, "threat_tier": "MEDIUM"},
        }
        dossier = self.engine.deliberate(mock_payload)
        w_sum = sum(dossier.agent_weights.values())
        self.assertAlmostEqual(w_sum, 1.0, places=4)
        self.assertGreaterEqual(dossier.consensus_probability, 0.0)
        self.assertLessEqual(dossier.consensus_probability, 1.0)
        print("PASS: Agent weights sum to 1.00 and consensus probability bounds verified.")

    def test_05_multi_agent_investigation_federation(self):
        """Validates that FraudInvestigatorAgent seamlessly incorporates Step 15 consensus deliberation."""
        res = self.agent.investigate_case("HHG-001")
        self.assertIn("federated_consensus", res)
        consensus = res["federated_consensus"]
        self.assertEqual(consensus["case_id"], "HHG-001")
        self.assertIn("consensus_verdict", consensus)
        self.assertIn("consensus_probability", consensus)
        self.assertIn("debate_transcript", consensus)
        self.assertGreater(len(consensus["debate_transcript"]), 0)
        print(f"PASS: Case HHG-001 deliberated with consensus verdict: {consensus['consensus_verdict']}.")

    def test_06_rest_api_endpoints(self):
        """Validates GET and POST API endpoints for consensus deliberation."""
        # 1. POST /api/agents/consensus/deliberate
        mock_payload = {
            "case": {"case_id": "HHG-001", "verdict": "legitimate", "fraud_probability": 0.10},
            "aml_specialist": {"aml_score": 0.05, "risk_level": "LOW"},
            "cyber_forensics": {"cyber_risk_score": 0.05, "threat_tier": "LOW"},
        }
        resp_post = self.api.post("/api/agents/consensus/deliberate", json={"investigation_answer": mock_payload})
        self.assertEqual(resp_post.status_code, 200)
        data_post = resp_post.json()
        self.assertEqual(data_post["case_id"], "HHG-001")
        self.assertIn("consensus_probability", data_post)

        # 2. GET /api/cases/HHG-001/consensus
        resp_get = self.api.get("/api/cases/HHG-001/consensus")
        self.assertEqual(resp_get.status_code, 200)
        data_get = resp_get.json()
        self.assertEqual(data_get["case_id"], "HHG-001")
        self.assertIn("debate_transcript", data_get)
        print("PASS: Multi-agent consensus REST API endpoints verified.")


if __name__ == "__main__":
    unittest.main()
