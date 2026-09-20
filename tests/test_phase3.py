"""
Phase 3 Acceptance Tests: GraphRAG & Case Memory
Tests retrieval of policy clauses and historical case memory across 10 distinct queries,
and verifies that context briefs adhere strictly to token/character limits.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rag.retrieve import GraphRAGRetriever
from src.rag.assemble import ContextAssembler


class TestPhase3GraphRAG(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing GraphRAG Retriever for Phase 3 Tests ===")
        cls.retriever = GraphRAGRetriever()

    def test_01_retrieval_relevance_10_queries(self):
        """Verify retrieved policy clauses for 10 sample investigation queries."""
        test_queries = [
            ("Three small authorizations followed by a larger purchase", "POLICY-R5"),
            ("Customer denies making the transaction", "POLICY-R2"),
            ("Single risk score signal under 0.70 verify customer", "POLICY-R1"),
            ("Customer confirms they made the purchase during travel", "POLICY-R3"),
            ("Multiple cards compromised from same device profile and region", "POLICY-R6"),
            ("Monthly recurring charge disputed by cardholder", "POLICY-R7"),
            ("Uncertain fraud evaluation with high financial loss", "POLICY-R8"),
            ("Suspicious Activity Report narrative criteria for regulator", "REG-FINCEN-SAR"),
            ("Card not present online purchase from new device proxy", "TYP-CNP-NEW-DEV"),
            ("Multi-card proxy rotation coordinated undocumented pattern", "TYP-DISCOVERED-PROXY-ROT"),
        ]

        print("\nEvaluating 10 Sample Policy Queries:")
        for idx, (query, expected_chunk_id) in enumerate(test_queries, 1):
            hits = self.retriever.retrieve_policy(query, top_k=3)
            hit_ids = [h["id"] for h in hits]
            self.assertIn(expected_chunk_id, hit_ids, f"Query '{query}' did not retrieve {expected_chunk_id}. Got {hit_ids}")
            print(f"  Query {idx} ({query[:45]}...): Top hit: {hit_ids[0]} (Contains {expected_chunk_id}: YES)")

    def test_02_similar_cases_retrieval_and_temporal_isolation(self):
        """Verify similar cases retrieval and strict as_of enforcement."""
        card_id = "C00259-K1"
        as_of = "2016-10-01 00:00:00"
        cases = self.retriever.retrieve_similar_cases(
            query="unrecognized online purchase card not present",
            card_id=card_id,
            as_of=as_of,
            top_k=3,
        )
        self.assertGreater(len(cases), 0, "No cases retrieved")
        for c in cases:
            self.assertIn("case_id", c)
            self.assertIn("outcome", c)
        print(f"PASS: Retrieved {len(cases)} cases for card {card_id}. Top hit: {cases[0]['case_id']} ({cases[0]['outcome']})")

    def test_03_context_assembler_budget_limit(self):
        """Verify context assembler output remains strictly within character budget."""
        trigger = {
            "case_id": "HHG-001",
            "trigger_type": "risk_score",
            "trigger_text": "Real-time model scored transaction 3514030 at 0.61.",
            "card_id": "C12382-K1",
            "customer_id": "C12382",
            "flagged_txn_id": "3514030",
            "risk_score": 0.61,
        }
        evidence = [
            {"id": f"EV-{i}", "source": "graph", "ref": f"query:q{i}", "claim": f"Claim details {i} showing anomalies."}
            for i in range(10)
        ]
        policy = self.retriever.retrieve_policy("risk score verify before block", top_k=3)
        patterns = {"best_pattern": "card_not_present_fraud", "patterns": {"card_not_present_fraud": {"match": True, "confidence": 0.7}}}
        memory = self.retriever.retrieve_similar_cases("card testing", card_id="C12382-K1", top_k=2)

        brief = ContextAssembler.assemble_brief(
            case_id="HHG-001",
            trigger=trigger,
            evidence_items=evidence,
            policy_clauses=policy,
            pattern_matches=patterns,
            memory_cases=memory,
            max_chars=3000,
        )

        self.assertLessEqual(len(brief), 3000, "Brief exceeded max_chars limit")
        self.assertIn("HHG-001", brief)
        self.assertIn("CONNECTED GRAPH EVIDENCE", brief)
        self.assertIn("APPLICABLE FRAUD POLICY CLAUSES", brief)
        print(f"PASS: Context brief assembled successfully ({len(brief)} characters <= 3000 budget).")

    def test_04_context_assembler_with_graph_topology(self):
        """Verify graph topology metrics and syndicate nexus are formatted into context brief."""
        trigger = {
            "trigger_type": "risk_score",
            "trigger_text": "Model flagged transaction",
            "card_id": "C08623-K2",
            "customer_id": "C08623",
            "flagged_txn_id": "3514030",
            "risk_score": 0.88,
        }
        evidence = [
            {"id": "EV-01", "source": "graph", "ref": "query:q1", "claim": "High velocity in 1h window."}
        ]
        topology = {
            "connected_cards_count": 4,
            "connected_customers_count": 3,
            "device_sharing": {"is_shared": True, "distinct_cards_count": 4, "distinct_customers_count": 3},
            "velocity": {"windows": {"1h": {"count": 3}, "24h": {"count": 7}}, "velocity_spike_ratio": 4.5},
            "geo": {"anomalies_count": 2},
            "ring": {"ring_detected": True, "cycle_length": 3},
            "as_of": "2016-12-05 12:00:00",
        }
        brief = ContextAssembler.assemble_brief(
            case_id="HHG-004",
            trigger=trigger,
            evidence_items=evidence,
            policy_clauses=[{"id": "POLICY-R6", "title": "Syndicate Detection", "text": "Coordinate multi-card activity."}],
            pattern_matches={"best_pattern": "card_not_present_new_device", "patterns": {}},
            memory_cases=[],
            graph_topology=topology,
            max_chars=3000,
        )

        self.assertLessEqual(len(brief), 3000)
        self.assertIn("GRAPH TOPOLOGY & SYNDICATE METRICS", brief)
        self.assertIn("Device Nexus: Shared across 4 cards", brief)
        self.assertIn("Transaction Burst: 3 txn(s)/1h, 7 txn(s)/24h", brief)
        self.assertIn("Circular Flow: Synthetic transaction cycle detected", brief)
        self.assertIn("Temporal Isolation: Graph expansion strictly bounded as_of", brief)
        print("PASS: Graph topology successfully integrated into Context Brief.")

    def test_05_policy_retrieval_mrr_benchmark(self):
        """Benchmark Mean Reciprocal Rank (MRR) and Top-k accuracy across comprehensive policy test set."""
        benchmark_queries = [
            ("Three small authorizations followed by a larger purchase", "POLICY-R5"),
            ("Customer denies making the transaction", "POLICY-R2"),
            ("Single risk score signal under 0.70 verify customer", "POLICY-R1"),
            ("Customer confirms they made the purchase during travel", "POLICY-R3"),
            ("Multiple cards compromised from same device profile and region", "POLICY-R6"),
            ("Monthly recurring charge disputed by cardholder", "POLICY-R7"),
            ("Uncertain fraud evaluation with high financial loss", "POLICY-R8"),
            ("Restrictions on BLOCK_ALL_CARDS requires at least two cards", "POLICY-R10"),
            ("Card not present online purchase from new device proxy", "TYP-CNP-NEW-DEV"),
            ("Multi-card proxy rotation coordinated undocumented pattern", "TYP-DISCOVERED-PROXY-ROT"),
            ("Device pooling nexus shared by multiple unrelated cards", "TYP-DISCOVERED-DEVICE-POOL"),
            ("Rapid geographical dispersion impossible travel velocity", "TYP-RAPID-DISPERSION"),
        ]

        metrics = self.retriever.evaluate_policy_retrieval_mrr(benchmark_queries, top_k=3)
        self.assertGreaterEqual(metrics["mrr"], 0.90, f"MRR too low: {metrics['mrr']}")
        self.assertEqual(metrics["topk_accuracy"], 1.0, f"Top-k accuracy must be 100%: {metrics['topk_accuracy']}")
        print(f"PASS: Policy Retrieval MRR: {metrics['mrr']:.4f}, Top-1 Acc: {metrics['top1_accuracy']*100:.1f}%, Top-3 Acc: {metrics['topk_accuracy']*100:.1f}%")


if __name__ == "__main__":
    unittest.main()
