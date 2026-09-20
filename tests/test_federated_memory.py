"""
Unit Test Suite for Cross-Agent Distributed Episodic & Semantic Memory Bus (tests/test_federated_memory.py)
Tests multi-agent episode ingestion, working memory blackboard publishing,
strict temporal isolation, vector similarity ranking, domain filtering,
cross-domain empirical priors, master agent integration, and FastAPI endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from src.cases.federated_memory import (
    FederatedMemoryBus,
    FederatedEpisode,
    AgentObservation,
)
from src.agent.graph import FraudInvestigatorAgent
from src.api.main import app


class TestFederatedMemoryBus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Federated Memory Bus Test Suite ===")
        cls.agent = FraudInvestigatorAgent()
        cls.bus = cls.agent.memory_bus

    def test_bootstrapping_and_episode_commit(self):
        """Verify memory bus bootstraps closed cases and commits new multi-agent episodes."""
        self.assertGreater(len(self.bus._episodes), 0)

        mock_answer = {
            "case": {
                "case_id": "TEST-EP-001",
                "card_id": "card_test_99",
                "customer_id": "cust_test_99",
                "opened_at": "2024-03-20 12:00:00",
                "exposure_usd": 12500.0,
                "verdict": "fraud",
                "fraud_probability": 0.88,
                "pattern": "structuring_burst",
                "connected_card_ids": ["card_test_99", "card_test_98"],
            },
            "aml_specialist": {
                "risk_level": "HIGH",
                "aml_score": 0.85,
                "mandatory_sar": True,
                "detected_typologies": ["STRUCTURING_BSA_THRESHOLD"],
            },
            "cyber_forensics": {
                "threat_tier": "CRITICAL",
                "cyber_risk_score": 0.79,
                "detected_anomalies": ["BOT_VELOCITY_BURST"],
            },
            "federated_consensus": {
                "consensus_verdict": "aml_escalation",
                "consensus_probability": 0.85,
                "consensus_confidence": 0.94,
            },
            "next_best_actions": {
                "final": ["FILE_SAR_FINCEN", "BLOCK_CARD", "ISOLATE_HARDWARE_FINGERPRINT"],
            },
            "sar": {"file": True},
        }

        ep = self.bus.commit_episode(mock_answer)
        self.assertEqual(ep.case_id, "TEST-EP-001")
        self.assertEqual(ep.aml_risk_level, "HIGH")
        self.assertEqual(ep.cyber_threat_tier, "CRITICAL")
        self.assertEqual(ep.consensus_verdict, "aml_escalation")
        self.assertTrue(ep.mandatory_sar)
        self.assertEqual(len(ep.feature_vector), 8)

        # Retrieve
        fetched = self.bus.get_episode("TEST-EP-001")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.episode_id, ep.episode_id)
        print("PASS: Bootstrapping and multi-agent episode commit verified.")

    def test_working_memory_blackboard(self):
        """Verify sub-agents publish and subscribe to the working memory blackboard."""
        case_id = "CASE-BB-TEST"

        obs1 = self.bus.publish_observation(
            case_id=case_id,
            source_agent="fraud_investigator",
            observation_type="HIGH_VELOCITY",
            severity="WARNING",
            summary="Card velocity exceeds 99th percentile.",
            data={"velocity_1h": 8},
        )
        obs2 = self.bus.publish_observation(
            case_id=case_id,
            source_agent="aml_specialist",
            observation_type="STRUCTURING_SIGNAL",
            severity="CRITICAL",
            summary="Cumulative transfers total $14,200 under 24h.",
            data={"exposure": 14200.0},
        )
        obs3 = self.bus.publish_observation(
            case_id=case_id,
            source_agent="cyber_forensics",
            observation_type="DEVICE_FINGERPRINT_BURST",
            severity="WARNING",
            summary="Device shared across 3 distinct cardholders.",
            data={"card_count": 3},
        )

        board = self.bus.get_blackboard(case_id)
        self.assertEqual(len(board), 3)
        self.assertEqual(board[0].source_agent, "fraud_investigator")
        self.assertEqual(board[1].source_agent, "aml_specialist")
        self.assertEqual(board[2].source_agent, "cyber_forensics")

        # Cleanup
        self.bus.clear_blackboard(case_id)
        self.assertEqual(len(self.bus.get_blackboard(case_id)), 0)
        print("PASS: Working memory blackboard publish, query, and clear verified.")

    def test_temporal_isolation_boundary(self):
        """Verify no episode on or after as_of boundary is visible in precedent retrieval."""
        as_of_cutoff = "2024-02-01 00:00:00"
        precedents = self.bus.query_cross_agent_precedents(
            as_of=as_of_cutoff,
            top_k=20,
        )

        for p in precedents:
            self.assertLess(str(p["timestamp"]), as_of_cutoff)
        print("PASS: Strict temporal isolation boundary enforced on precedent search.")

    def test_semantic_vector_similarity_and_domain_filtering(self):
        """Verify vector cosine search and domain-specific precedent filtering."""
        # Query for AML-specific precedents
        aml_precedents = self.bus.query_cross_agent_precedents(
            query_vector=[0.9, 1.0, 0.9, 0.2, 1.0, 0.4, 1.0, 0.0],
            domain_filter="AML",
            top_k=5,
        )
        self.assertGreater(len(aml_precedents), 0)
        for p in aml_precedents:
            self.assertTrue(p["aml_risk_level"] in ["MEDIUM", "HIGH"] or p["mandatory_sar"])

        # Query for Cyber-specific precedents
        cyber_precedents = self.bus.query_cross_agent_precedents(
            query_vector=[0.8, 0.3, 0.2, 0.9, 0.0, 0.6, 0.0, 1.0],
            domain_filter="CYBER",
            top_k=5,
        )
        self.assertGreater(len(cyber_precedents), 0)
        for p in cyber_precedents:
            self.assertIn(p["cyber_threat_tier"], ["ELEVATED", "CRITICAL"])
        print("PASS: Semantic vector similarity and domain-specific filtering verified.")

    def test_cross_domain_prior_calculation(self):
        """Verify multi-domain empirical risk prior calculation."""
        # Sample card with history in closed cases
        sample_card = next(
            (c.get("card_id") for c in self.bus.client.store.closed_cases.values() if c.get("card_id")),
            None,
        )
        self.assertIsNotNone(sample_card)

        prior = self.bus.get_cross_domain_prior(card_id=sample_card)
        self.assertIn("has_federated_history", prior)
        self.assertIn("composite_prior_risk_delta", prior)
        self.assertIn("cited_episode_ids", prior)
        self.assertTrue(-10.0 <= prior["composite_prior_risk_delta"] <= 15.0)
        print("PASS: Cross-domain multi-agent risk prior calculation verified.")

    def test_master_agent_investigation_integration(self):
        """Verify end-to-end investigation populates blackboard, commits episode, and attaches citations."""
        ans = self.agent.investigate_case("HHG-001")

        # Step 16 checks
        self.assertIn("working_memory_blackboard", ans)
        self.assertGreater(len(ans["working_memory_blackboard"]), 0)

        self.assertIn("federated_memory_episode", ans)
        ep = ans["federated_memory_episode"]
        self.assertEqual(ep["case_id"], "HHG-001")
        self.assertEqual(len(ep["feature_vector"]), 8)

        self.assertIn("cross_agent_precedents", ans)
        self.assertIsInstance(ans["cross_agent_precedents"], list)
        print("PASS: Master agent investigation Step 16 federated memory integration verified.")

    def test_fastapi_memory_endpoints(self):
        """Verify REST API endpoints for episode search, episode detail, blackboard, and prior."""
        client = TestClient(app)

        # 1. Search precedents
        resp_search = client.post(
            "/api/memory/episodes/search",
            json={
                "domain_filter": "ALL",
                "top_k": 3,
            },
        )
        self.assertEqual(resp_search.status_code, 200)
        self.assertIsInstance(resp_search.json(), list)

        # 2. Get Episode
        resp_ep = client.get("/api/memory/episodes/HHG-001")
        self.assertEqual(resp_ep.status_code, 200)
        self.assertEqual(resp_ep.json()["case_id"], "HHG-001")

        # 3. Get Blackboard
        resp_bb = client.get("/api/memory/blackboard/HHG-001")
        self.assertEqual(resp_bb.status_code, 200)
        self.assertEqual(resp_bb.json()["case_id"], "HHG-001")

        # 4. Get Cross Domain Prior
        resp_prior = client.get("/api/memory/cross-domain-prior?card_id=card_test_99")
        self.assertEqual(resp_prior.status_code, 200)
        self.assertIn("composite_prior_risk_delta", resp_prior.json())
        print("PASS: FastAPI federated memory REST endpoints verified.")


if __name__ == "__main__":
    unittest.main()
