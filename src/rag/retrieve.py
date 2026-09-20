"""
GraphRAG Retrieval Engine
Combines semantic vector search over policy/typology chunks and historical closed cases
with graph structural traversals (connected devices, shared customers, cluster rings).
"""

import os
import sys
from typing import List, Dict, Any, Optional, Tuple

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.rag.chunk import PolicyChunker
from src.rag.embed import LocalSemanticIndex
from src.graph.client import GraphClient, parse_as_of_epoch


class GraphRAGRetriever:
    def __init__(self, client: Optional[GraphClient] = None):
        self.client = client or GraphClient(mode="embedded")
        self.store = self.client.store

        # 1. Initialize Policy Index
        self.policy_index = LocalSemanticIndex()
        policy_chunks = PolicyChunker.get_policy_chunks()
        self.policy_index.add_documents(policy_chunks, text_field="text", id_field="id")

        # 2. Initialize Case Memory Index
        self.case_index = LocalSemanticIndex()
        case_docs = []
        for cid, case_data in self.store.closed_cases.items():
            notes = str(case_data.get("analyst_notes", "")).strip()
            pattern = str(case_data.get("pattern", "")).strip()
            outcome = str(case_data.get("outcome", "")).strip()
            card = str(case_data.get("card_id", "")).strip()
            opened = str(case_data.get("opened_at", "")).strip()
            exposure = str(case_data.get("exposure_usd", "0"))

            case_docs.append({
                "id": cid,
                "text": f"Case {cid} on card {card}: {outcome} {pattern}. {notes}",
                "pattern": pattern,
                "outcome": outcome,
                "card_id": card,
                "opened_at": opened,
                "exposure_usd": float(exposure) if exposure.replace('.', '', 1).isdigit() else 0.0,
                "analyst_notes": notes,
                "keywords": [pattern, outcome, card],
            })
        self.case_index.add_documents(case_docs, text_field="text", id_field="id")

    def retrieve_policy(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieves top-k applicable policy clauses based on case facts / hypotheses."""
        results = self.policy_index.search(query, top_k=top_k)
        return [doc for doc, score in results]

    def retrieve_similar_cases(
        self,
        query: str,
        card_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        as_of: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Combines semantic similarity over case summaries with structural graph lookups.
        Enforces as_of temporal isolation: never returns cases opened after as_of.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        hits = {}

        # 1. Structural graph hits (Q10)
        if card_id:
            struct_res = self.client.similar_cases(card_id, customer_id=customer_id, as_of=as_of)
            for m in struct_res.get("similar_cases", []):
                cid = m["case_id"]
                hits[cid] = {
                    "case_id": cid,
                    "match_type": f"structural_{m['match_type']}",
                    "outcome": m.get("outcome"),
                    "pattern": m.get("pattern"),
                    "exposure_usd": m.get("exposure_usd", 0.0),
                    "analyst_notes": m.get("analyst_notes", ""),
                }

        # 2. Semantic search hits
        semantic_hits = self.case_index.search(query, top_k=top_k * 2)
        for doc, score in semantic_hits:
            cid = doc["id"]
            if parse_as_of_epoch(doc.get("opened_at")) <= as_of_epoch:
                if cid not in hits:
                    hits[cid] = {
                        "case_id": cid,
                        "match_type": "semantic_similarity",
                        "outcome": doc.get("outcome"),
                        "pattern": doc.get("pattern"),
                        "exposure_usd": doc.get("exposure_usd", 0.0),
                        "analyst_notes": doc.get("analyst_notes", ""),
                    }

        return list(hits.values())[:top_k]

    def evaluate_policy_retrieval_mrr(
        self,
        test_queries: List[Tuple[str, str]],
        top_k: int = 3,
    ) -> Dict[str, float]:
        """
        Evaluates retrieval quality across test query/expected-chunk-ID pairs.
        Returns:
            mrr: Mean Reciprocal Rank (1.0 = perfect top-1 ranking)
            top1_accuracy: Fraction of queries where expected chunk is rank 1
            topk_accuracy: Fraction of queries where expected chunk is in top-k
        """
        total = len(test_queries)
        if total == 0:
            return {"mrr": 0.0, "top1_accuracy": 0.0, "topk_accuracy": 0.0}

        reciprocal_ranks = []
        top1_hits = 0
        topk_hits = 0

        for query, expected_id in test_queries:
            hits = self.retrieve_policy(query, top_k=top_k)
            hit_ids = [h.get("id") for h in hits]

            if expected_id in hit_ids:
                rank = hit_ids.index(expected_id) + 1
                reciprocal_ranks.append(1.0 / rank)
                topk_hits += 1
                if rank == 1:
                    top1_hits += 1
            else:
                reciprocal_ranks.append(0.0)

        mrr = sum(reciprocal_ranks) / total
        top1_acc = top1_hits / total
        topk_acc = topk_hits / total

        return {
            "mrr": round(mrr, 4),
            "top1_accuracy": round(top1_acc, 4),
            "topk_accuracy": round(topk_acc, 4),
        }

