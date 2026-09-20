"""
Parallelized Asynchronous Graph Traversal Engine
Executes independent topological traversals, velocity checks, pattern matches,
and memory priors concurrently across thread worker pools, accelerating investigation throughput.
"""

import time
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


class ConcurrentGraphTraverser:
    """
    Orchestrates concurrent execution of read-only graph algorithms and queries.
    """

    @classmethod
    def gather_graph_evidence(
        cls,
        client: Any,
        memory_prior_engine: Any,
        undocumented_detector: Any,
        card_id: str,
        customer_id: Optional[str],
        flagged_txn: Optional[str],
        dev_profile: Optional[str],
        as_of: Optional[str],
        budget_plan: Dict[str, Any],
        max_workers: int = 6,
    ) -> Dict[str, Any]:
        """
        Executes all independent graph queries concurrently using a thread worker pool.
        """
        t_start = time.perf_counter()

        def _get_profile():
            return "profile", client.entity_profile(card_id, "card")

        def _get_context():
            return "context", (client.txn_context(flagged_txn) if flagged_txn else {})

        def _get_velocity():
            return "velocity", client.velocity(card_id, as_of=as_of)

        def _get_new_entity():
            return "new_entity", (client.new_entity_check(flagged_txn, as_of=as_of) if flagged_txn else {})

        def _get_device_sharing():
            if dev_profile and dev_profile != "None | None | None | None":
                return "device_sharing", client.device_sharing(dev_profile, as_of=as_of)
            return "device_sharing", {}

        def _get_pattern_match():
            if flagged_txn:
                return "pattern_match", client.pattern_match(flagged_txn, as_of=as_of)
            return "pattern_match", {"best_pattern": "none", "patterns": {}}

        def _get_similar_cases():
            return "similar_cases", client.similar_cases(card_id, customer_id=customer_id, as_of=as_of)

        def _get_memory_prior():
            return "memory_prior", memory_prior_engine.compute_prior(
                card_id=card_id,
                customer_id=customer_id,
                device_profile=dev_profile,
                as_of=as_of,
            )

        def _get_ring():
            if budget_plan.get("allow_deep_ring_scan", True):
                return "ring", client.ring_detection(card_id, as_of=as_of)
            return "ring", {"ring_detected": False}

        def _get_geo():
            if budget_plan.get("allow_geo_dispersion_scan", True):
                return "geo", client.geo_impossible(card_id, as_of=as_of)
            return "geo", {"anomalies_count": 0, "has_geo_anomaly": False}

        def _get_undocumented():
            if flagged_txn and budget_plan.get("allow_undocumented_detector", True):
                return "undocumented_anomaly", undocumented_detector.detect_anomalies(flagged_txn, as_of=as_of)
            return "undocumented_anomaly", {}

        def _get_community():
            if budget_plan.get("allow_community_detection", True):
                return "community", client.detect_community(card_id, as_of=as_of)
            return "community", {"is_dense_fraud_cluster": False, "community_size": 1}

        def _get_burst_cluster():
            if flagged_txn and budget_plan.get("allow_burst_cluster_scan", True):
                return "burst_cluster", client.detect_burst_cluster(flagged_txn, as_of=as_of)
            return "burst_cluster", {"is_coordinated_burst": False, "burst_card_count": 0}

        def _get_structuring():
            if budget_plan.get("allow_structuring_scan", True):
                return "structuring", client.detect_structuring(customer_id=customer_id, device_profile=dev_profile, card_ids=[card_id], as_of=as_of)
            return "structuring", {"is_structuring": False, "mandatory_filings": []}

        def _get_contagion():
            if budget_plan.get("allow_contagion_scan", True):
                return "contagion", client.calculate_fraud_contagion(card_id, as_of=as_of)
            return "contagion", {"target_contagion_score": 0.0, "contagion_risk_level": "none"}

        def _get_syndicate_merchants():
            if budget_plan.get("allow_deep_ring_scan", True) and hasattr(client, "expand_syndicate_for_card"):
                return "syndicate_merchants", client.expand_syndicate_for_card(card_id, as_of=as_of)
            return "syndicate_merchants", {"shared_merchants_count": 0, "collusive_merchants": []}

        tasks = [
            _get_profile,
            _get_context,
            _get_velocity,
            _get_new_entity,
            _get_device_sharing,
            _get_pattern_match,
            _get_similar_cases,
            _get_memory_prior,
            _get_ring,
            _get_geo,
            _get_undocumented,
            _get_community,
            _get_burst_cluster,
            _get_structuring,
            _get_contagion,
            _get_syndicate_merchants,
        ]

        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fn) for fn in tasks]
            for future in as_completed(futures):
                key, val = future.result()
                results[key] = val

        results["budget_plan"] = budget_plan
        results["traversal_time_ms"] = round((time.perf_counter() - t_start) * 1000.0, 2)

        return results
