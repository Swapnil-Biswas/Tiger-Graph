"""
Streaming Graph Edge Decay & Memory Management Engine (Q24).
Implements continuous exponential temporal decay with priority-boosting for fraud seeds
and bounded-degree top-K pruning to maintain bounded graph memory and sub-millisecond
traversal latencies in high-throughput financial transaction streams.
"""

import math
import time
from typing import Dict, Any, List, Optional, Tuple, Union, Set
from collections import defaultdict


class ExponentialTemporalDecay:
    """
    Temporal Graph Edge Decay & Priority-Preserving Pruning Engine.
    Computes continuous exponential edge decay:
      w(e) = min(1.0, alpha(e) * 2^(-Delta_t / tau))
    where tau is the half-life duration (e.g. 30 days) and alpha(e) boosts high-priority
    edges (fraud seeds, syndicates, high-risk alerts).
    """

    def __init__(
        self,
        half_life_days: float = 30.0,
        min_retention_weight: float = 0.05,
        max_degree_per_node: int = 50,
        client=None,
    ):
        self.half_life_days = max(0.1, float(half_life_days))
        self.half_life_seconds = self.half_life_days * 86400.0
        self.min_retention_weight = float(min_retention_weight)
        self.max_degree_per_node = int(max_degree_per_node)
        self.client = client

    @staticmethod
    def get_importance_multiplier(
        edge_type: str = "TRANSACTION",
        is_fraud: bool = False,
        risk_score: float = 0.0,
    ) -> float:
        """Computes priority multiplier alpha(e) based on edge criticality."""
        if is_fraud:
            return 4.0
        if edge_type in ("COLLUSIVE_MERCHANT_LINK", "RESOLVED_IDENTITY_LINK", "SYNDICATE_LINK"):
            return 3.0
        if risk_score >= 0.70:
            return 2.0
        if risk_score >= 0.40:
            return 1.5
        return 1.0

    def calculate_edge_weight(
        self,
        epoch_s: int,
        as_of_epoch: int,
        edge_type: str = "TRANSACTION",
        is_fraud: bool = False,
        risk_score: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Calculates continuous exponential decay weight for an edge as of as_of_epoch.
        Strictly enforces temporal isolation (future edges have weight 0.0).
        """
        if epoch_s > as_of_epoch:
            return {
                "epoch_s": epoch_s,
                "as_of_epoch": as_of_epoch,
                "delta_seconds": 0,
                "decay_factor": 0.0,
                "importance_multiplier": 0.0,
                "effective_weight": 0.0,
                "retained": False,
                "prune_reason": "FUTURE_TRANSACTION_TEMPORAL_ISOLATION",
            }

        delta_s = max(0, as_of_epoch - epoch_s)
        half_lives = delta_s / self.half_life_seconds
        decay_factor = 2.0 ** (-half_lives)
        alpha = self.get_importance_multiplier(edge_type=edge_type, is_fraud=is_fraud, risk_score=risk_score)
        eff_weight = min(1.0, round(alpha * decay_factor, 6))

        # Fraud edges are immune to dropping below min_weight
        retained = is_fraud or (eff_weight >= self.min_retention_weight)
        reason = "KEPT" if retained else "EXPIRED_BELOW_MIN_WEIGHT"

        return {
            "epoch_s": epoch_s,
            "as_of_epoch": as_of_epoch,
            "delta_seconds": delta_s,
            "half_lives_elapsed": round(half_lives, 4),
            "decay_factor": round(decay_factor, 6),
            "importance_multiplier": alpha,
            "effective_weight": eff_weight,
            "retained": retained,
            "is_fraud_immune": is_fraud,
            "prune_reason": reason,
        }

    def prune_incident_edges(
        self,
        edges: List[Dict[str, Any]],
        as_of_epoch: int,
        max_degree: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Filters and prunes incident edges by temporal validity, decay weight,
        and bounded top-K degree while strictly preserving confirmed fraud seeds.
        """
        limit = max_degree or self.max_degree_per_node
        scored = []
        pruned_future = 0
        pruned_decayed = 0
        fraud_seeds_count = 0

        for e in edges:
            ep = e.get("epoch_s", 0)
            is_f = bool(e.get("is_fraud", False))
            if is_f:
                fraud_seeds_count += 1
            risk = float(e.get("risk_score", 0.0))
            etype = str(e.get("edge_type", "TRANSACTION"))

            calc = self.calculate_edge_weight(
                epoch_s=ep,
                as_of_epoch=as_of_epoch,
                edge_type=etype,
                is_fraud=is_f,
                risk_score=risk,
            )

            if calc["prune_reason"] == "FUTURE_TRANSACTION_TEMPORAL_ISOLATION":
                pruned_future += 1
                continue

            if not calc["retained"]:
                pruned_decayed += 1
                continue

            scored.append((calc["effective_weight"], is_f, e, calc))

        # Sort: fraud seeds first, then highest effective weight
        scored.sort(key=lambda x: (1 if x[1] else 0, x[0]), reverse=True)

        retained_edges = [item[2] for item in scored[:limit]]
        pruned_degree = max(0, len(scored) - limit)

        stats = {
            "edges_evaluated": len(edges),
            "edges_retained": len(retained_edges),
            "edges_pruned_total": pruned_future + pruned_decayed + pruned_degree,
            "pruned_future_count": pruned_future,
            "pruned_decayed_count": pruned_decayed,
            "pruned_degree_overflow_count": pruned_degree,
            "fraud_seeds_preserved": sum(1 for e in retained_edges if e.get("is_fraud", False)),
            "compression_ratio": round(len(retained_edges) / max(1, len(edges)), 4),
        }

        return retained_edges, stats

    def prune_card_subgraph(
        self,
        card_id: str,
        as_of: Optional[Union[str, int]] = None,
        max_degree: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Applies exponential decay and bounded-degree pruning to transactions for card_id.
        """
        from src.graph.client import parse_as_of_epoch
        as_of_epoch = parse_as_of_epoch(as_of)

        txns = []
        if self.client and hasattr(self.client, "store"):
            txns = self.client.store.txns_by_card.get(card_id, [])

        retained, stats = self.prune_incident_edges(txns, as_of_epoch=as_of_epoch, max_degree=max_degree)

        return {
            "card_id": card_id,
            "as_of": as_of,
            "as_of_epoch": as_of_epoch,
            "half_life_days": self.half_life_days,
            "max_degree_limit": max_degree or self.max_degree_per_node,
            "stats": stats,
            "retained_transactions_count": len(retained),
            "retained_transactions": retained,
        }

    def simulate_streaming_pruning(
        self,
        as_of: Optional[Union[str, int]] = None,
        sample_size: int = 50,
        max_degree: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Simulates streaming graph edge pruning over active cards in GraphStore
        and reports aggregate memory reduction and latency metrics.
        """
        t0 = time.perf_counter()
        from src.graph.client import parse_as_of_epoch
        as_of_epoch = parse_as_of_epoch(as_of)

        total_eval = 0
        total_retained = 0
        total_pruned = 0
        fraud_preserved = 0

        cards_sampled = 0
        if self.client and hasattr(self.client, "store"):
            sample_cards = list(self.client.store.txns_by_card.keys())[:sample_size]
            for cid in sample_cards:
                res = self.prune_card_subgraph(cid, as_of=as_of, max_degree=max_degree)
                st = res["stats"]
                total_eval += st["edges_evaluated"]
                total_retained += st["edges_retained"]
                total_pruned += st["edges_pruned_total"]
                fraud_preserved += st["fraud_seeds_preserved"]
                cards_sampled += 1

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        compression = round(total_retained / max(1, total_eval), 4)

        return {
            "as_of": as_of,
            "half_life_days": self.half_life_days,
            "min_retention_weight": self.min_retention_weight,
            "max_degree_limit": max_degree or self.max_degree_per_node,
            "cards_sampled": cards_sampled,
            "total_edges_evaluated": total_eval,
            "total_edges_retained": total_retained,
            "total_edges_pruned": total_pruned,
            "fraud_seeds_preserved": fraud_preserved,
            "graph_compression_ratio": compression,
            "memory_reduction_pct": round((1.0 - compression) * 100.0, 2),
            "elapsed_ms": elapsed_ms,
            "avg_latency_us_per_node": round((elapsed_ms * 1000.0) / max(1, cards_sampled), 2),
        }
