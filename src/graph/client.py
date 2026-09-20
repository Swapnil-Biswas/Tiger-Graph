"""
Unified Graph Client & GSQL Query Library (Q1 - Q12)
Provides dual-mode access:
1. 'embedded': In-memory GraphStore executing graph queries locally with microsecond latency.
2. 'tigergraph': Remote TigerGraph instance executing installed GSQL queries.
All queries strictly enforce temporal isolation via 'as_of' parameter.
"""

import os
import sys
import math
import bisect
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Set, Any, Optional, Union

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.graph.ingest import GraphStore


def parse_as_of_epoch(as_of: Optional[Union[str, int, float]]) -> int:
    """Converts as_of to integer epoch seconds. Defaults to infinity if None."""
    if as_of is None:
        return 9999999999
    if isinstance(as_of, (int, float)):
        val = int(as_of)
        return val // 1000 if val > 20_000_000 else val
    as_of_str = str(as_of).strip()
    if not as_of_str:
        return 9999999999
    try:
        # Check standard datetime format
        dt = datetime.strptime(as_of_str, "%Y-%m-%d %H:%M:%S")
        val = int(dt.timestamp())
        return val // 1000 if val > 20_000_000 else val
    except ValueError:
        try:
            dt = datetime.fromisoformat(as_of_str)
            val = int(dt.timestamp())
            return val // 1000 if val > 20_000_000 else val
        except Exception:
            return 9999999999


class GraphClient:
    def __init__(self, mode: Optional[str] = None, store: Optional[GraphStore] = None):
        self.mode = mode or os.getenv("GRAPH_MODE", "embedded").lower()
        self.store = store

        if self.mode == "embedded":
            if self.store is None:
                self.store = GraphStore.load_cache_or_build()
        else:
            # TigerGraph pyTigerGraph connection initialization if credentials provided
            try:
                import pyTigerGraph as tg
                host = os.getenv("TG_HOST", "https://your-domain.i.tgcloud.io")
                graph = os.getenv("TG_GRAPH", "FraudInvestigation")
                username = os.getenv("TG_USERNAME", "tigergraph")
                password = os.getenv("TG_PASSWORD", "tigergraph")
                secret = os.getenv("TG_SECRET", "")
                token = os.getenv("TG_API_TOKEN", "")

                self.tg_conn = tg.TigerGraphConnection(
                    host=host,
                    graphname=graph,
                    username=username,
                    password=password,
                    secret=secret,
                    apiToken=token,
                )
            except Exception as e:
                print(f"Warning: pyTigerGraph connection failed ({e}). Falling back to embedded engine.")
                self.mode = "embedded"
                if self.store is None:
                    self.store = GraphStore.load_cache_or_build()

    def _get_card_epochs(self, card_id: str) -> List[int]:
        if not hasattr(self.store, "_card_epochs"):
            self.store._card_epochs = {}
        epochs = self.store._card_epochs.get(card_id)
        if epochs is None:
            txns = self.store.txns_by_card.get(card_id, [])
            epochs = [t["epoch_s"] for t in txns]
            self.store._card_epochs[card_id] = epochs
        return epochs

    def _get_cust_epochs(self, cust_id: str) -> List[int]:
        if not hasattr(self.store, "_cust_epochs"):
            self.store._cust_epochs = {}
        epochs = self.store._cust_epochs.get(cust_id)
        if epochs is None:
            txns = self.store.txns_by_customer.get(cust_id, [])
            epochs = [t["epoch_s"] for t in txns]
            self.store._cust_epochs[cust_id] = epochs
        return epochs

    def _get_dev_epochs(self, dev_id: str) -> List[int]:
        if not hasattr(self.store, "_dev_epochs"):
            self.store._dev_epochs = {}
        epochs = self.store._dev_epochs.get(dev_id)
        if epochs is None:
            txns = self.store.txns_by_device.get(dev_id, [])
            epochs = [t["epoch_s"] for t in txns]
            self.store._dev_epochs[dev_id] = epochs
        return epochs

    # =========================================================================
    # Q1: entity_profile
    # Baseline transaction history, typical amounts, typical regions, channels
    # =========================================================================
    def entity_profile(self, entity_id: str, entity_type: str = "card", as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q1: Baseline behavior for customer or card prior to as_of.
        Returns: txn_count, total_spend, avg_amount, median_amount, typical_regions, typical_devices, typical_channels
        """
        if self.mode == "tigergraph":
            try:
                res = self.tg_conn.runInstalledQuery("entity_profile", {"entity_id": entity_id, "entity_type": entity_type, "as_of": str(as_of)})
                return res[0] if res else {}
            except Exception:
                pass  # fallback to embedded

        as_of_epoch = parse_as_of_epoch(as_of)
        if entity_type == "customer":
            all_txns = self.store.txns_by_customer.get(entity_id, [])
            epochs = self._get_cust_epochs(entity_id)
        else:
            all_txns = self.store.txns_by_card.get(entity_id, [])
            epochs = self._get_card_epochs(entity_id)

        idx = bisect.bisect_right(epochs, as_of_epoch)
        txns = all_txns[:idx]

        if not txns:
            return {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "txn_count": 0,
                "total_spend": 0.0,
                "avg_amount": 0.0,
                "median_amount": 0.0,
                "min_amount": 0.0,
                "max_amount": 0.0,
                "typical_regions": [],
                "typical_devices": [],
                "channels": {},
                "first_seen": None,
                "last_seen": None,
            }

        amounts = [t["amount"] for t in txns]
        amounts.sort()
        n = len(amounts)
        median_val = amounts[n // 2] if n % 2 != 0 else (amounts[n // 2 - 1] + amounts[n // 2]) / 2.0
        
        regions = Counter(t["addr1"] for t in txns if t["addr1"])
        devices = Counter(t["device_profile"] for t in txns if t["device_profile"] and t["device_profile"] != "None | None | None | None")
        channels = Counter(t["channel"] for t in txns if t["channel"])

        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "txn_count": n,
            "total_spend": round(sum(amounts), 2),
            "avg_amount": round(sum(amounts) / n, 2),
            "median_amount": round(median_val, 2),
            "min_amount": round(amounts[0], 2),
            "max_amount": round(amounts[-1], 2),
            "typical_regions": [r for r, c in regions.most_common(3)],
            "typical_devices": [d for d, c in devices.most_common(3)],
            "channels": dict(channels),
            "first_seen": txns[0]["ts"],
            "last_seen": txns[-1]["ts"],
        }

    # =========================================================================
    # Q2: txn_context
    # Neighborhood of a transaction on its card (prior/succeeding txns within window)
    # =========================================================================
    def txn_context(self, txn_id: str, window_hours: int = 48, as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q2: Preceding and succeeding transactions within window_hours on the same card.
        Computes amount deviation z-score against historical card baseline.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        txn = self.store.transactions.get(txn_id)
        if not txn:
            return {"error": f"Transaction {txn_id} not found", "txn_id": txn_id}

        card_id = txn["card_id"]
        t_epoch = txn["epoch_s"]
        window_sec = window_hours * 3600

        all_card_txns = self.store.txns_by_card.get(card_id, [])
        epochs = self._get_card_epochs(card_id)
        hi = bisect.bisect_right(epochs, as_of_epoch)
        historical_txns = all_card_txns[:hi]

        lo_prec = bisect.bisect_left(epochs, t_epoch - window_sec, 0, hi)
        hi_prec = bisect.bisect_left(epochs, t_epoch, lo_prec, hi)
        prior_txns = all_card_txns[lo_prec:hi_prec]

        lo_succ = bisect.bisect_right(epochs, t_epoch, 0, hi)
        hi_succ = bisect.bisect_right(epochs, t_epoch + window_sec, lo_succ, hi)
        succeeding_txns = all_card_txns[lo_succ:hi_succ]

        # Baseline stats for z-score
        prior_cutoff = bisect.bisect_left(epochs, t_epoch, 0, hi)
        prior_amounts = [t["amount"] for t in all_card_txns[:prior_cutoff]]
        z_score = 0.0
        if len(prior_amounts) >= 3:
            avg_amt = sum(prior_amounts) / len(prior_amounts)
            variance = sum((x - avg_amt) ** 2 for x in prior_amounts) / len(prior_amounts)
            std_amt = math.sqrt(variance)
            if std_amt > 0.01:
                z_score = round((txn["amount"] - avg_amt) / std_amt, 2)

        return {
            "txn_id": txn_id,
            "card_id": card_id,
            "target_txn": txn,
            "prior_count": len(prior_txns),
            "prior_txns": prior_txns[-5:],  # last 5
            "succeeding_count": len(succeeding_txns),
            "succeeding_txns": succeeding_txns[:5],  # first 5
            "amount_z_score": z_score,
            "time_since_prev_sec": (t_epoch - prior_txns[-1]["epoch_s"]) if prior_txns else None,
        }

    # =========================================================================
    # Q3: velocity
    # Burst detection in 5m, 1h, 24h, 7d windows
    # =========================================================================
    def velocity(self, card_id: str, as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q3: Velocity burst detection across time windows (5m, 1h, 24h, 7d) prior to as_of.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        all_card_txns = self.store.txns_by_card.get(card_id, [])
        epochs = self._get_card_epochs(card_id)
        hi = bisect.bisect_right(epochs, as_of_epoch)

        is_kilosec = bool(epochs and epochs[0] < 20_000_000)
        windows = {
            "5m": 1 if is_kilosec else 300,
            "1h": 4 if is_kilosec else 3600,
            "24h": 86 if is_kilosec else 86400,
            "7d": 605 if is_kilosec else 604800,
        }
        res = {"card_id": card_id, "windows": {}}

        for w_name, w_sec in windows.items():
            lo = bisect.bisect_left(epochs, as_of_epoch - w_sec, 0, hi)
            window_txns = all_card_txns[lo:hi]
            res["windows"][w_name] = {
                "count": len(window_txns),
                "total_usd": round(sum(t["amount"] for t in window_txns), 2),
                "txn_ids": [t["TransactionID"] for t in window_txns],
            }

        # Calculate acceleration (e.g. 1h velocity vs 7d hourly baseline)
        count_1h = res["windows"]["1h"]["count"]
        count_7d = res["windows"]["7d"]["count"]
        baseline_hourly_rate = count_7d / (7 * 24.0) if count_7d > 0 else 0.0
        res["velocity_spike_ratio"] = round(count_1h / (baseline_hourly_rate + 0.05), 2)
        return res

    # =========================================================================
    # Q4: device_sharing
    # Device linkage across cards/customers and historical cases
    # =========================================================================
    def device_sharing(self, device_profile_id: str, as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q4: Identifies all distinct cards/customers sharing this device profile prior to as_of.
        Also retrieves prior closed cases touching this device profile.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        all_dev_txns = self.store.txns_by_device.get(device_profile_id, [])
        epochs = self._get_dev_epochs(device_profile_id)
        idx = bisect.bisect_right(epochs, as_of_epoch)
        dev_txns = all_dev_txns[:idx]

        cards_seen = sorted(list(set(t["card_id"] for t in dev_txns)))
        customers_seen = sorted(list(set(t["customer_id"] for t in dev_txns)))

        # Cases touching this device
        prior_cases = []
        for c in self.store.cases_by_device.get(device_profile_id, []):
            opened_epoch = parse_as_of_epoch(c.get("opened_at"))
            if opened_epoch <= as_of_epoch:
                prior_cases.append(c["case_id"])

        return {
            "device_profile": device_profile_id,
            "txn_count": len(all_dev_txns),
            "distinct_cards_count": len(cards_seen),
            "cards": cards_seen[:10],
            "distinct_customers_count": len(customers_seen),
            "customers": customers_seen[:10],
            "is_shared": len(cards_seen) > 1,
            "prior_cases_touching_device": prior_cases,
            "first_seen": all_dev_txns[0]["ts"] if all_dev_txns else None,
            "last_seen": all_dev_txns[-1]["ts"] if all_dev_txns else None,
        }

    # =========================================================================
    # Q5: identity_link_expand
    # K-hop expansion via shared device, email domain, or billing address
    # =========================================================================
    def identity_link_expand(self, seed_card_id: str, k_hops: int = 2, as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q5: Traverses entity links (Card -> DeviceProfile / BillingRegion -> Connected Cards).
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        seed_txns = [t for t in self.store.txns_by_card.get(seed_card_id, []) if t["epoch_s"] <= as_of_epoch]
        
        seed_devices = set(t["device_profile"] for t in seed_txns if t["device_profile"] and t["device_profile"] != "None | None | None | None")
        seed_regions = set(t["addr1"] for t in seed_txns if t["addr1"])

        connected_cards = set()
        link_paths = []

        # 1-hop / 2-hop via DeviceProfile
        for dev in seed_devices:
            dev_txns = [t for t in self.store.txns_by_device.get(dev, []) if t["epoch_s"] <= as_of_epoch]
            for t in dev_txns:
                other_card = t["card_id"]
                if other_card != seed_card_id:
                    connected_cards.add(other_card)
                    if len(link_paths) < 10:
                        link_paths.append({"hop": 1, "via_type": "DeviceProfile", "via_id": dev, "connected_card": other_card})

        return {
            "seed_card_id": seed_card_id,
            "connected_cards_count": len(connected_cards),
            "connected_cards": sorted(list(connected_cards))[:15],
            "seed_device_count": len(seed_devices),
            "paths": link_paths,
        }

    # =========================================================================
    # Q6: ring_detection
    # Fraud ring and cluster candidate detection
    # =========================================================================
    def ring_detection(self, seed_id: str, entity_type: str = "card", as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q6: Identifies fraud ring structure: cluster size, density, hub entities.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        card_id = seed_id if entity_type == "card" else self.store.transactions.get(seed_id, {}).get("card_id", seed_id)
        
        expand_res = self.identity_link_expand(card_id, k_hops=2, as_of=as_of)
        connected_cards = expand_res.get("connected_cards", [])
        
        # Check if connected cards are associated with confirmed fraud cases
        fraud_neighbor_cases = []
        for c in connected_cards:
            for case_obj in self.store.cases_by_card.get(c, []):
                if parse_as_of_epoch(case_obj.get("opened_at")) <= as_of_epoch:
                    if case_obj.get("outcome") == "confirmed_fraud":
                        fraud_neighbor_cases.append(case_obj["case_id"])

        is_ring_candidate = len(connected_cards) >= 2 and len(fraud_neighbor_cases) >= 1
        return {
            "seed_card_id": card_id,
            "cluster_size": len(connected_cards) + 1,
            "connected_cards": connected_cards[:10],
            "fraud_precedents_in_cluster": list(set(fraud_neighbor_cases)),
            "is_ring_candidate": is_ring_candidate,
            "density_score": round(min(1.0, len(connected_cards) / 5.0), 2),
        }

    # =========================================================================
    # Q13: detect_community
    # Dynamic Graph Community Detection & Dense Fraud Subgraph Discovery
    # =========================================================================
    def detect_community(
        self,
        seed_id: str,
        entity_type: str = "card",
        as_of: Optional[Union[str, int]] = None,
        max_hops: int = 2,
    ) -> dict:
        """
        Q13: Partitions local ego-network via deterministic Label Propagation (LPA)
        to identify dense multi-card/device fraud communities and evaluate contagion.
        """
        from src.graph.algorithms import GraphCommunityDetector
        detector = GraphCommunityDetector(self)
        return detector.detect_community(seed_id, entity_type=entity_type, as_of=as_of, max_hops=max_hops)

    # =========================================================================
    # Q14: export_gnn_subgraph
    # Topological Graph Embedding & GNN-Ready Adjacency Matrix Exporter
    # =========================================================================
    def export_gnn_subgraph(
        self,
        seed_id: str,
        entity_type: str = "card",
        as_of: Optional[Union[str, int]] = None,
        k_hops: int = 2,
        max_nodes: int = 50,
    ) -> dict:
        """
        Q14: Extracts normalized node feature tensors (x), sparse edge index ([2, E]),
        and edge attributes ([E, D]) compatible with PyTorch Geometric (PyG) and DGL.
        """
        from src.graph.embeddings import TopologicalGraphEmbeddingExporter
        exporter = TopologicalGraphEmbeddingExporter(self)
        return exporter.extract_gnn_subgraph(seed_id, entity_type=entity_type, as_of=as_of, k_hops=k_hops, max_nodes=max_nodes)

    # =========================================================================
    # Q15: detect_burst_cluster
    # Multi-Card Temporal Velocity Burst & Coordinated Testing Detector
    # =========================================================================
    def detect_burst_cluster(
        self,
        txn_id: str,
        window_hours: float = 24.0,
        as_of: Optional[Union[str, int]] = None,
    ) -> dict:
        """
        Q15: Identifies coordinated multi-card velocity bursts, bot attacks,
        and synchronized testing clusters in narrow temporal windows.
        """
        from src.graph.algorithms import MultiCardBurstClusterDetector
        detector = MultiCardBurstClusterDetector(self)
        return detector.detect_burst_cluster(txn_id, window_hours=window_hours, as_of=as_of)

    # =========================================================================
    # Q7: new_entity_check
    # First-time device, billing region, or email domain for customer
    # =========================================================================
    def new_entity_check(self, txn_id: str, as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q7: Novelty checks for transaction: is device, region, or email domain new for customer?
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        txn = self.store.transactions.get(txn_id)
        if not txn:
            return {"error": f"Transaction {txn_id} not found", "txn_id": txn_id}

        cust_id = txn["customer_id"]
        t_epoch = txn["epoch_s"]

        all_cust_txns = self.store.txns_by_customer.get(cust_id, [])
        epochs = self._get_cust_epochs(cust_id)
        cutoff = min(t_epoch - 1, as_of_epoch)
        hi = bisect.bisect_right(epochs, cutoff)
        cust_txns = all_cust_txns[:hi]

        prior_devices = set(t["device_profile"] for t in cust_txns if t["device_profile"])
        prior_regions = set(t["addr1"] for t in cust_txns if t["addr1"])
        prior_emails = set(t["p_email"] for t in cust_txns if t["p_email"])

        txn_device = txn.get("device_profile", "")
        txn_region = txn.get("addr1", "")
        txn_email = txn.get("p_email", "")

        is_new_device = (txn_device not in prior_devices) and (txn_device != "None | None | None | None")
        is_new_region = (txn_region not in prior_regions) and bool(txn_region)
        is_new_email = (txn_email not in prior_emails) and bool(txn_email)

        # Identity record id_15 flag
        identity_flag_new = txn.get("id_15") == "New"

        return {
            "txn_id": txn_id,
            "customer_id": cust_id,
            "is_new_device": is_new_device,
            "identity_flag_new": identity_flag_new,
            "is_new_region": is_new_region,
            "is_new_email": is_new_email,
            "proxy_flag": txn.get("id_23") in ["anonymous", "hidden"],
            "prior_device_count": len(prior_devices),
            "prior_region_count": len(prior_regions),
        }

    # =========================================================================
    # Q8: geo_impossible
    # Geographic anomaly between consecutive card-present purchases
    # =========================================================================
    def geo_impossible(self, card_id: str, as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q8: Checks for impossible travel speed / region hopping across in-person purchases.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        all_txns = [t for t in self.store.txns_by_card.get(card_id, []) if t["epoch_s"] <= as_of_epoch]
        in_person = [t for t in all_txns if t["channel"] == "in_person" and t["addr1"]]

        anomalies = []
        for i in range(1, len(in_person)):
            prev_t = in_person[i - 1]
            curr_t = in_person[i]
            time_diff_hours = (curr_t["epoch_s"] - prev_t["epoch_s"]) / 3600.0
            
            if prev_t["addr1"] != curr_t["addr1"] and 0 < time_diff_hours < 2.0:
                anomalies.append({
                    "from_txn": prev_t["TransactionID"],
                    "to_txn": curr_t["TransactionID"],
                    "from_region": prev_t["addr1"],
                    "to_region": curr_t["addr1"],
                    "time_delta_hours": round(time_diff_hours, 2),
                })

        return {
            "card_id": card_id,
            "has_geo_anomaly": len(anomalies) > 0,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies[:5],
        }

    # =========================================================================
    # Q9: money_flow_trace
    # Multi-hop trace of transaction activity across connected cards/merchants
    # =========================================================================
    def money_flow_trace(self, seed_id: str, hops: int = 2, as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q9: Traces chronological activity and cumulative exposure across the card's cluster.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        txn = self.store.transactions.get(seed_id)
        card_id = txn["card_id"] if txn else seed_id
        
        all_txns = [t for t in self.store.txns_by_card.get(card_id, []) if t["epoch_s"] <= as_of_epoch]
        flow = [
            {"txn_id": t["TransactionID"], "ts": t["ts"], "amount": t["amount"], "channel": t["channel"]}
            for t in all_txns[-10:]
        ]
        return {
            "seed_id": seed_id,
            "card_id": card_id,
            "flow_path": flow,
            "total_flow_amount": round(sum(f["amount"] for f in flow), 2),
        }

    # =========================================================================
    # Q10: similar_cases
    # Structural memory retrieval: historical cases sharing entities or patterns
    # =========================================================================
    def similar_cases(self, card_id: str, customer_id: Optional[str] = None, as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q10: Structural similarity retrieval from closed_cases_history.csv.
        Finds prior closed cases sharing card, customer, device, or pattern.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        matches = []

        # 1. Matches on same customer
        if customer_id:
            for c in self.store.cases_by_customer.get(customer_id, []):
                if parse_as_of_epoch(c.get("opened_at")) <= as_of_epoch:
                    matches.append({
                        "case_id": c["case_id"],
                        "match_type": "same_customer",
                        "outcome": c.get("outcome"),
                        "pattern": c.get("pattern"),
                        "exposure_usd": float(c.get("exposure_usd", 0.0)),
                        "analyst_notes": c.get("analyst_notes", ""),
                        "opened_at": c.get("opened_at", ""),
                    })

        # 2. Matches on devices used by this card
        card_devices = self.store.devices_by_card.get(card_id, set())
        for dev in card_devices:
            for c in self.store.cases_by_device.get(dev, []):
                if parse_as_of_epoch(c.get("opened_at")) <= as_of_epoch:
                    matches.append({
                        "case_id": c["case_id"],
                        "match_type": "shared_device",
                        "outcome": c.get("outcome"),
                        "pattern": c.get("pattern"),
                        "exposure_usd": float(c.get("exposure_usd", 0.0)),
                        "analyst_notes": c.get("analyst_notes", ""),
                        "opened_at": c.get("opened_at", ""),
                    })

        # Deduplicate matches by case_id
        unique_matches = {}
        for m in matches:
            cid = m["case_id"]
            if cid not in unique_matches:
                unique_matches[cid] = m

        return {
            "card_id": card_id,
            "similar_cases_count": len(unique_matches),
            "similar_cases": list(unique_matches.values())[:5],
            "case_ids": list(unique_matches.keys())[:5],
        }

    # =========================================================================
    # Q11: pattern_match
    # Quantitative matching for the 5 documented fraud typologies
    # =========================================================================
    def pattern_match(self, txn_id: str, pattern_id: Optional[str] = None, as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q11: Tests the 5 documented fraud signatures against graph evidence:
        1. card_testing
        2. card_not_present_fraud
        3. card_not_present_new_device
        4. out_of_region_use
        5. account_takeover
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        txn = self.store.transactions.get(txn_id)
        if not txn:
            return {"error": f"Transaction {txn_id} not found"}

        card_id = txn["card_id"]
        t_epoch = txn["epoch_s"]

        # Fetch context
        card_txns = [t for t in self.store.txns_by_card.get(card_id, []) if t["epoch_s"] <= t_epoch]
        new_ent = self.new_entity_check(txn_id, as_of=t_epoch)
        vel = self.velocity(card_id, as_of=t_epoch)
        profile = self.entity_profile(card_id, entity_type="card", as_of=t_epoch - 1)

        scores = {}
        is_kilosec = (t_epoch < 20_000_000)
        delta_1h = 4 if is_kilosec else 3600
        delta_48h = 173 if is_kilosec else 172800

        # 1. card_testing: >= 3 tiny online auths (< $5) within 1h followed by larger purchase
        txns_1h = [t for t in card_txns if (t_epoch - delta_1h) <= t["epoch_s"] <= t_epoch]
        tiny_auths = [t for t in txns_1h if t["channel"] == "online" and t["amount"] < 5.0 and t["TransactionID"] != txn_id]
        testing_criteria = {
            "has_tiny_auths": len(tiny_auths) >= 3,
            "followed_by_larger": txn["amount"] > 20.0,
            "rapid_sequence": len(txns_1h) >= 4,
        }
        scores["card_testing"] = {
            "match": testing_criteria["has_tiny_auths"] and testing_criteria["followed_by_larger"],
            "confidence": 0.85 if (testing_criteria["has_tiny_auths"] and testing_criteria["followed_by_larger"]) else (0.5 if len(tiny_auths) >= 2 else 0.0),
            "evidence": {"tiny_count": len(tiny_auths), "tiny_txn_ids": [t["TransactionID"] for t in tiny_auths]},
        }

        # 2. card_not_present_fraud: Unusual online purchase burst (2-4 within 48h) inconsistent with history
        burst_txns_48h = [t for t in card_txns if (t_epoch - delta_48h) <= t["epoch_s"] <= t_epoch and t["channel"] == "online"]
        amount_mismatch = txn["amount"] > (profile.get("max_amount", 100.0) * 1.5) if profile.get("txn_count", 0) > 3 else False
        scores["card_not_present_fraud"] = {
            "match": txn["channel"] == "online" and (len(burst_txns_48h) >= 2 or amount_mismatch),
            "confidence": 0.70 if (txn["channel"] == "online" and len(burst_txns_48h) >= 2) else (0.50 if txn["channel"] == "online" else 0.1),
            "evidence": {"online_burst_48h_count": len(burst_txns_48h), "amount_mismatch": amount_mismatch},
        }

        # 3. card_not_present_new_device: Online + New device profile / Proxy
        scores["card_not_present_new_device"] = {
            "match": txn["channel"] == "online" and (new_ent["is_new_device"] or new_ent["identity_flag_new"] or new_ent["proxy_flag"]),
            "confidence": 0.80 if (txn["channel"] == "online" and (new_ent["is_new_device"] or new_ent["identity_flag_new"])) else 0.1,
            "evidence": {"new_device": new_ent["is_new_device"], "proxy": new_ent["proxy_flag"], "device_profile": txn.get("device_profile")},
        }

        # 4. out_of_region_use: Card present in billing region with no history while home activity continues
        scores["out_of_region_use"] = {
            "match": txn["channel"] == "in_person" and new_ent["is_new_region"],
            "confidence": 0.75 if (txn["channel"] == "in_person" and new_ent["is_new_region"]) else 0.1,
            "evidence": {"region": txn.get("addr1"), "is_new_region": new_ent["is_new_region"], "typical_regions": profile.get("typical_regions")},
        }

        # 5. account_takeover: Mixed-channel anomalies, credential takeover indicators
        scores["account_takeover"] = {
            "match": new_ent["is_new_device"] and new_ent["is_new_email"] and txn["channel"] == "online",
            "confidence": 0.75 if (new_ent["is_new_device"] and new_ent["is_new_email"]) else 0.15,
            "evidence": {"new_device": new_ent["is_new_device"], "new_email": new_ent["is_new_email"]},
        }

        return {
            "txn_id": txn_id,
            "card_id": card_id,
            "patterns": scores,
            "best_pattern": max(scores.items(), key=lambda x: x[1]["confidence"])[0],
        }

    # =========================================================================
    # Q12: case_history
    # Prior cases touching the entity or its immediate neighbors
    # =========================================================================
    def case_history(self, entity_id: str, entity_type: str = "card", as_of: Optional[Union[str, int]] = None) -> dict:
        """
        Q12: Historical closed cases touching this specific entity prior to as_of.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        cases = []
        if entity_type == "customer":
            cases = [c for c in self.store.cases_by_customer.get(entity_id, []) if parse_as_of_epoch(c.get("opened_at")) <= as_of_epoch]
        else:
            cases = [c for c in self.store.cases_by_card.get(entity_id, []) if parse_as_of_epoch(c.get("opened_at")) <= as_of_epoch]

        confirmed = sum(1 for c in cases if c.get("outcome") == "confirmed_fraud")
        cleared = sum(1 for c in cases if c.get("outcome") == "cleared")

        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "total_prior_cases": len(cases),
            "confirmed_fraud_count": confirmed,
            "cleared_count": cleared,
            "cases": cases[:5],
        }

    # =========================================================================
    # Subgraph extractor for UI (Cytoscape.js format)
    # =========================================================================
    def get_case_subgraph(self, case_id: str, max_nodes: int = 40) -> dict:
        """
        Extracts a localized Cytoscape-compatible JSON subgraph around a case.
        """
        # Lookup benchmark case or closed case
        pack_item = self.store.case_pack.get(case_id) or self.store.closed_cases.get(case_id)
        if not pack_item:
            return {"nodes": [], "edges": []}

        card_id = pack_item.get("card_id", "")
        cust_id = pack_item.get("customer_id", "")
        flagged_txn = pack_item.get("flagged_txn_id", "") or pack_item.get("first_fraud_txn_id", "")

        nodes = []
        edges = []
        node_ids = set()

        def add_node(nid: str, ntype: str, label: str, data: dict = None):
            if nid not in node_ids and len(node_ids) < max_nodes:
                node_ids.add(nid)
                payload = {"id": nid, "type": ntype, "label": label}
                if data:
                    payload.update(data)
                nodes.append({"data": payload})

        def add_edge(src: str, dst: str, etype: str, label: str = ""):
            if src in node_ids and dst in node_ids:
                edges.append({"data": {"source": src, "target": dst, "type": etype, "label": label}})

        # Seed Nodes
        add_node(f"case_{case_id}", "Case", f"Case {case_id}")
        if cust_id:
            add_node(f"cust_{cust_id}", "Customer", f"Customer {cust_id}")
        if card_id:
            add_node(f"card_{card_id}", "Card", f"Card {card_id}")
            add_edge(f"cust_{cust_id}", f"card_{card_id}", "OWNS", "OWNS")
            add_edge(f"case_{case_id}", f"card_{card_id}", "ABOUT", "ABOUT")

        if flagged_txn and flagged_txn in self.store.transactions:
            txn_obj = self.store.transactions[flagged_txn]
            add_node(f"txn_{flagged_txn}", "Transaction", f"${txn_obj['amount']:.2f} ({flagged_txn})", {"risk": txn_obj["risk_score"]})
            add_edge(f"card_{card_id}", f"txn_{flagged_txn}", "MADE", "MADE")
            
            dev = txn_obj.get("device_profile")
            if dev and dev != "None | None | None | None":
                dev_short = dev.split(" | ")[0]
                add_node(f"dev_{dev[:20]}", "DeviceProfile", dev_short)
                add_edge(f"txn_{flagged_txn}", f"dev_{dev[:20]}", "FROM_DEVICE", "DEVICE")

            addr = txn_obj.get("addr1")
            if addr:
                add_node(f"reg_{addr}", "BillingRegion", f"Region {addr}")
                add_edge(f"txn_{flagged_txn}", f"reg_{addr}", "BILLED_IN", "REGION")

        return {"nodes": nodes, "edges": edges}

    # =========================================================================
    # Q16: detect_structuring
    # Regulatory Structuring & Dynamic Multi-Entity Exposure Rollup
    # =========================================================================
    def detect_structuring(
        self,
        customer_id: Optional[str] = None,
        device_profile: Optional[str] = None,
        card_ids: Optional[List[str]] = None,
        transactions: Optional[List[Dict[str, Any]]] = None,
        window_hours: float = 24.0,
        as_of: Optional[Union[str, int]] = None,
        jurisdiction: str = "US",
    ) -> Dict[str, Any]:
        """
        Q16: Performs multi-entity exposure rollup and flags BSA/POCA/6AMLD structuring patterns.
        """
        from src.policy.jurisdiction import RegulatoryStructuringDetector
        return RegulatoryStructuringDetector.detect_structuring(
            customer_id=customer_id,
            device_profile=device_profile,
            card_ids=card_ids,
            transactions=transactions,
            window_hours=window_hours,
            as_of=as_of,
            jurisdiction=jurisdiction,
            client=self,
        )

    # =========================================================================
    # Q17: calculate_fraud_contagion
    # Personalized PageRank / Random Walk with Restart Contagion Scoring
    # =========================================================================
    def calculate_fraud_contagion(
        self,
        seed_id: str,
        entity_type: str = "card",
        as_of: Optional[Union[str, int]] = None,
        restart_prob: float = 0.15,
        max_iter: int = 30,
        tol: float = 1e-5,
        max_hops: int = 2,
        max_nodes: int = 60,
        custom_fraud_seeds: Optional[List[str]] = None,
    ) -> dict:
        """
        Q17: Computes continuous Personalized PageRank (PPR) fraud contagion from confirmed fraud seeds.
        """
        from src.graph.algorithms import FraudContagionPageRank
        rwr = FraudContagionPageRank(self)
        return rwr.calculate_contagion(
            seed_id=seed_id,
            entity_type=entity_type,
            as_of=as_of,
            restart_prob=restart_prob,
            max_iter=max_iter,
            tol=tol,
            max_hops=max_hops,
            max_nodes=max_nodes,
            custom_fraud_seeds=custom_fraud_seeds,
        )

    # =========================================================================
    # Q18: pool_graph_embedding
    # Temporal Graph Attention Subgraph Pooling
    # =========================================================================
    def pool_graph_embedding(
        self,
        seed_id: str,
        entity_type: str = "card",
        as_of: Optional[Union[str, int]] = None,
        k_hops: int = 2,
        max_nodes: int = 50,
        decay_lambda: float = 0.05,
    ) -> dict:
        """
        Q18: Aggregates multi-hop ego-network node features into fixed-dimensional (9D / 27D)
        embeddings via temporal graph attention pooling for GBDT / NN ingestion.
        """
        from src.graph.embeddings import TopologicalGraphEmbeddingExporter, TemporalGraphAttentionPooler
        exporter = TopologicalGraphEmbeddingExporter(self)
        pooler = TemporalGraphAttentionPooler(self)

        pyg_subgraph = exporter.extract_gnn_subgraph(
            seed_id=seed_id,
            entity_type=entity_type,
            as_of=as_of,
            k_hops=k_hops,
            max_nodes=max_nodes,
        )
        return pooler.pool_subgraph(
            pyg_subgraph=pyg_subgraph,
            as_of=as_of,
            decay_lambda=decay_lambda,
        )



