"""
Unit Tests for Inductive Fraud Rule Discovery (tests/test_rule_discovery.py)
Validates frequent itemset mining over 5,565 closed cases, confidence & lift bounds,
temporal boundary isolation, card evaluation, GraphRAG chunk export, and API endpoints.
"""

import unittest
import time
from fastapi.testclient import TestClient
from src.graph.client import GraphClient
from src.cases.rule_miner import InductiveFraudRuleMiner
from src.api.main import app


class TestInductiveRuleDiscovery(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Inductive Fraud Rule Discovery Test Suite ===")
        cls.client = GraphClient(mode="embedded")
        cls.miner = InductiveFraudRuleMiner(cls.client)
        cls.api_client = TestClient(app)

    def test_01_mine_rules_discovery(self):
        """Rule miner discovers high-confidence association rules from closed cases."""
        res = self.miner.mine_rules(min_support=15, min_confidence=0.85, max_rules=15)

        self.assertGreater(res["total_cases_evaluated"], 5000)
        self.assertGreater(res["rules_discovered_count"], 0)
        self.assertGreaterEqual(len(res["rules"]), 5)

        first_rule = res["rules"][0]
        self.assertIn("rule_id", first_rule)
        self.assertIn("rule_str", first_rule)
        self.assertGreaterEqual(first_rule["confidence"], 0.85)
        self.assertGreaterEqual(first_rule["support"], 15)
        print(f"PASS: Mined {res['rules_discovered_count']} rules in {res['elapsed_ms']}ms. Top rule: {first_rule['rule_str']}.")

    def test_02_confidence_and_lift_thresholds(self):
        """All discovered rules strictly respect confidence >= 0.80 and support >= 10."""
        res = self.miner.mine_rules(min_support=10, min_confidence=0.80, max_rules=20)

        for r in res["rules"]:
            self.assertGreaterEqual(r["confidence"], 0.80, f"Rule {r['rule_id']} confidence below 0.80")
            self.assertGreaterEqual(r["support"], 10, f"Rule {r['rule_id']} support below 10")
            self.assertGreater(r["lift"], 0.90, f"Rule {r['rule_id']} lift below 0.90")
        print("PASS: Confidence, support, and lift thresholds validated across all mined rules.")

    def test_03_temporal_isolation_enforcement(self):
        """Early as_of boundary yields 0 rules; later as_of discovers rules without data leakage."""
        # Prior to dataset timeline
        early_res = self.miner.mine_rules(as_of="2015-01-01 00:00:00")
        self.assertEqual(early_res["total_cases_evaluated"], 0)
        self.assertEqual(early_res["rules_discovered_count"], 0)

        # Later timeline
        later_res = self.miner.mine_rules(as_of="2017-06-01 00:00:00", min_support=15, min_confidence=0.85)
        self.assertGreater(later_res["total_cases_evaluated"], 1000)
        self.assertGreater(later_res["rules_discovered_count"], 0)
        print(f"PASS: Temporal isolation verified (2015 cases: {early_res['total_cases_evaluated']} vs 2017: {later_res['total_cases_evaluated']}).")

    def test_04_card_evaluation_against_mined_rules(self):
        """Active card with high-risk signals matches mined inductive rules."""
        card_id = "C00259-K1"
        eval_res = self.miner.evaluate_entity(card_id, as_of="2017-06-01 00:00:00")

        self.assertEqual(eval_res["card_id"], card_id)
        self.assertGreater(len(eval_res["active_predicates"]), 0)
        self.assertTrue(eval_res["is_inductive_fraud_match"])
        self.assertGreaterEqual(eval_res["highest_confidence"], 0.85)
        print(f"PASS: Card evaluation matched {eval_res['matching_rules_count']} rule(s) (highest conf: {eval_res['highest_confidence']*100:.1f}%).")

    def test_05_graphrag_chunks_export(self):
        """Mined rules export to valid GraphRAG knowledge chunks."""
        res = self.miner.mine_rules(min_support=20, min_confidence=0.90, max_rules=5)
        chunks = self.miner.export_to_graphrag_chunks(res["rules"])

        self.assertEqual(len(chunks), len(res["rules"]))
        for ch in chunks:
            self.assertTrue(ch["chunk_id"].startswith("TYP-IND-RULE-"))
            self.assertIn("RULE IDENTIFIER:", ch["content"])
            self.assertIn("CONFIDENCE:", ch["content"])
            self.assertEqual(ch["category"], "inductive_fraud_rules")
        print(f"PASS: Exported {len(chunks)} GraphRAG chunks successfully.")

    def test_06_api_endpoints_integration(self):
        """API endpoints GET /api/rules/mined and POST /api/rules/evaluate operate correctly."""
        # Test GET /api/rules/mined
        resp = self.api_client.get("/api/rules/mined?min_support=20&min_confidence=0.85&max_rules=5")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("rules", data)
        self.assertGreater(data["rules_discovered_count"], 0)

        # Test POST /api/rules/evaluate
        post_resp = self.api_client.post(
            "/api/rules/evaluate",
            json={"card_id": "C00259-K1", "as_of": "2017-06-01 00:00:00"},
        )
        self.assertEqual(post_resp.status_code, 200)
        post_data = post_resp.json()
        self.assertEqual(post_data["card_id"], "C00259-K1")
        self.assertIn("is_inductive_fraud_match", post_data)
        print("PASS: Rule discovery API endpoints verified successfully.")
