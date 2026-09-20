"""
Unit Tests for Temporal Recency-Weighted Case Retrieval in GraphRAG
Validates exponential decay mathematics, recency ranking order,
and strict as_of temporal isolation.
"""

import unittest
import math
from src.rag.retrieve import GraphRAGRetriever
from src.graph.client import parse_as_of_epoch


class TestTemporalRecencyRetrieval(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Temporal Recency Retrieval Test Suite ===")
        cls.retriever = GraphRAGRetriever()

    def test_recency_decay_mathematical_bounds(self):
        """Exponential decay math: e^(-ln(2) * delta / half_life)."""
        half_life = 30.0
        lam = math.log(2) / half_life

        # 0 days -> decay 1.0
        decay_0 = math.exp(-lam * 0.0)
        self.assertAlmostEqual(decay_0, 1.0, places=4)

        # 30 days (1 half life) -> decay 0.5
        decay_30 = math.exp(-lam * 30.0)
        self.assertAlmostEqual(decay_30, 0.5, places=4)

        # 60 days (2 half lives) -> decay 0.25
        decay_60 = math.exp(-lam * 60.0)
        self.assertAlmostEqual(decay_60, 0.25, places=4)

        # 90 days (3 half lives) -> decay 0.125
        decay_90 = math.exp(-lam * 90.0)
        self.assertAlmostEqual(decay_90, 0.125, places=4)

    def test_retrieval_returns_temporal_metadata_and_ranks_by_relevance(self):
        """Verify retrieved cases contain temporal metadata and are sorted descending by relevance."""
        as_of = "2016-10-01 00:00:00"
        cases = self.retriever.retrieve_similar_cases(
            query="unrecognized online transaction card not present",
            card_id="C00259-K1",
            as_of=as_of,
            top_k=5,
        )

        self.assertGreater(len(cases), 0, "No cases retrieved.")
        
        # Verify fields and descending sort
        prev_score = float("inf")
        as_of_epoch = parse_as_of_epoch(as_of)

        for c in cases:
            self.assertIn("case_id", c)
            self.assertIn("relevance_score", c)
            self.assertIn("recency_decay", c)
            self.assertIn("days_prior", c)
            self.assertIn("opened_at", c)

            # Check descending sort
            self.assertLessEqual(c["relevance_score"], prev_score)
            prev_score = c["relevance_score"]

            # Strict temporal isolation
            opened_epoch = parse_as_of_epoch(c["opened_at"])
            self.assertLessEqual(opened_epoch, as_of_epoch, f"Case {c['case_id']} leaked future data!")

    def test_strict_temporal_isolation_future_exclusion(self):
        """Cases opened after as_of must never be returned under any query."""
        early_as_of = "2016-01-01 00:00:00"  # Before any cases in historical set
        cases = self.retriever.retrieve_similar_cases(
            query="fraud compromise",
            card_id="C00259-K1",
            as_of=early_as_of,
            top_k=5,
        )
        self.assertEqual(len(cases), 0, "Expected 0 cases before 2016-01-01.")


if __name__ == "__main__":
    unittest.main()
