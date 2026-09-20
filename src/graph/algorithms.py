"""
Graph Analytics & Undocumented Pattern Discovery Engine
Implements graph anomaly detection algorithms (Louvain-inspired community clustering,
proxy rotation syndicate detection, and cross-card device nexus expansion)
to uncover organized financial crime patterns beyond the 5 documented typologies.
"""

import math
from typing import Dict, Any, List, Optional, Set, Union, Tuple
from collections import defaultdict, Counter


class GraphCommunityDetector:
    """
    Dynamic Graph Community Detection & Dense Fraud Subgraph Discovery.
    Uses multi-hop ego-network extraction and deterministic Label Propagation Algorithm (LPA)
    to discover cohesive clusters of cards, devices, and customers, computing internal edge density,
    inter-entity connectivity, and community-level fraud contagion risk.
    """

    def __init__(self, client):
        self.client = client

    def detect_community(
        self,
        seed_id: str,
        entity_type: str = "card",
        as_of: Optional[Union[str, int]] = None,
        max_hops: int = 2,
        max_nodes: int = 60,
    ) -> Dict[str, Any]:
        """
        Extracts the multi-hop ego-network around seed_id up to as_of,
        partitions the local graph via deterministic Label Propagation,
        and evaluates density, modularity, and fraud contagion.
        """
        from src.graph.client import parse_as_of_epoch
        as_of_epoch = parse_as_of_epoch(as_of)

        # 1. Resolve seed entity node
        if entity_type == "card":
            seed_card = seed_id
        elif entity_type == "customer":
            cust_txns = self.client.store.txns_by_customer.get(seed_id, [])
            seed_card = cust_txns[0]["card_id"] if cust_txns else seed_id
        elif entity_type == "transaction":
            txn = self.client.store.transactions.get(seed_id, {})
            seed_card = txn.get("card_id", seed_id)
        else:
            seed_card = seed_id

        seed_node = f"CARD:{seed_card}"

        # 2. Extract Multi-Hop Ego-Network
        adj: Dict[str, Set[str]] = defaultdict(set)
        node_types: Dict[str, str] = {seed_node: "card"}
        visited: Set[str] = {seed_node}
        queue: List[Tuple[str, int]] = [(seed_node, 0)]

        while queue and len(visited) < max_nodes:
            curr_node, hop = queue.pop(0)
            if hop >= max_hops:
                continue

            if curr_node.startswith("CARD:"):
                cid = curr_node[5:]
                all_txns = self.client.store.txns_by_card.get(cid, [])
                txns = [t for t in all_txns if t["epoch_s"] <= as_of_epoch]
                for t in txns:
                    # Customer edge
                    cust = t.get("customer_id")
                    if cust:
                        c_node = f"CUST:{cust}"
                        node_types[c_node] = "customer"
                        if c_node not in visited:
                            if len(visited) < max_nodes:
                                visited.add(c_node)
                                queue.append((c_node, hop + 1))
                                adj[curr_node].add(c_node)
                                adj[c_node].add(curr_node)
                        else:
                            adj[curr_node].add(c_node)
                            adj[c_node].add(curr_node)

                    # Device edge - exclude placeholders and generic browser hubs (> 15 cards)
                    dev = t.get("device_profile")
                    if dev and dev != "None | None | None | None" and not dev.startswith("UnknownDevice"):
                        dev_card_count = len(set(x["card_id"] for x in self.client.store.txns_by_device.get(dev, [])))
                        if dev_card_count <= 15:
                            d_node = f"DEV:{dev}"
                            node_types[d_node] = "device"
                            if d_node not in visited:
                                if len(visited) < max_nodes:
                                    visited.add(d_node)
                                    queue.append((d_node, hop + 1))
                                    adj[curr_node].add(d_node)
                                    adj[d_node].add(curr_node)
                            else:
                                adj[curr_node].add(d_node)
                                adj[d_node].add(curr_node)

            elif curr_node.startswith("DEV:"):
                dev_id = curr_node[4:]
                all_dev_txns = self.client.store.txns_by_device.get(dev_id, [])
                dev_txns = [t for t in all_dev_txns if t["epoch_s"] <= as_of_epoch]
                for t in dev_txns:
                    other_card = t.get("card_id")
                    if other_card:
                        card_node = f"CARD:{other_card}"
                        node_types[card_node] = "card"
                        if card_node not in visited:
                            if len(visited) < max_nodes:
                                visited.add(card_node)
                                queue.append((card_node, hop + 1))
                                adj[curr_node].add(card_node)
                                adj[card_node].add(curr_node)
                        else:
                            adj[curr_node].add(card_node)
                            adj[card_node].add(curr_node)

            elif curr_node.startswith("CUST:"):
                cust_id = curr_node[5:]
                all_cust_txns = self.client.store.txns_by_customer.get(cust_id, [])
                for t in all_cust_txns:
                    if t["epoch_s"] <= as_of_epoch:
                        c = t.get("card_id")
                        if c:
                            card_node = f"CARD:{c}"
                            node_types[card_node] = "card"
                            if card_node not in visited:
                                if len(visited) < max_nodes:
                                    visited.add(card_node)
                                    queue.append((card_node, hop + 1))
                                    adj[curr_node].add(card_node)
                                    adj[card_node].add(curr_node)
                            else:
                                adj[curr_node].add(card_node)
                                adj[card_node].add(curr_node)

        # 3. Deterministic Label Propagation Algorithm (LPA)
        nodes_list = sorted(list(visited))
        labels = {v: v for v in nodes_list}

        if len(nodes_list) > 1:
            for _ in range(10):
                changed = False
                for v in nodes_list:
                    neighbors = [nbr for nbr in adj.get(v, set()) if nbr in labels]
                    if not neighbors:
                        continue
                    counts = Counter(labels[nbr] for nbr in neighbors)
                    max_c = max(counts.values())
                    best_candidates = [lbl for lbl, c in counts.items() if c == max_c]
                    best_label = min(best_candidates)  # Deterministic tie-breaking
                    if labels[v] != best_label:
                        labels[v] = best_label
                        changed = True
                if not changed:
                    break

        # 4. Extract Seed Community
        seed_label = labels.get(seed_node, seed_node)
        comm_nodes = [v for v in nodes_list if labels.get(v) == seed_label]
        comm_set = set(comm_nodes)

        cards = sorted([v[5:] for v in comm_nodes if v.startswith("CARD:")])
        devices = sorted([v[4:] for v in comm_nodes if v.startswith("DEV:")])
        customers = sorted([v[5:] for v in comm_nodes if v.startswith("CUST:")])

        # 5. Internal Edges and Density
        internal_edges = 0
        for u in comm_nodes:
            for w in adj.get(u, set()):
                if w in comm_set and u < w:
                    internal_edges += 1

        comm_size = len(comm_nodes)
        if comm_size > 1:
            possible_edges = (comm_size * (comm_size - 1)) / 2.0
            density = round(internal_edges / possible_edges, 3)
        else:
            density = 0.0

        # 6. Fraud Contagion Evaluation
        fraud_cases = []
        for c in cards:
            for case_obj in self.client.store.cases_by_card.get(c, []):
                if parse_as_of_epoch(case_obj.get("opened_at")) <= as_of_epoch:
                    if case_obj.get("outcome") == "confirmed_fraud":
                        fraud_cases.append(case_obj["case_id"])

        total_txns = 0
        fraud_txns = 0
        for c in cards:
            for t in self.client.store.txns_by_card.get(c, []):
                if t["epoch_s"] <= as_of_epoch:
                    total_txns += 1
                    if t.get("is_fraud") == 1:
                        fraud_txns += 1

        fraud_txn_rate = (fraud_txns / total_txns) if total_txns > 0 else 0.0
        unique_fraud_cases = sorted(list(set(fraud_cases)))

        if len(unique_fraud_cases) > 0:
            contagion = min(1.0, 0.45 + (0.15 * len(unique_fraud_cases)) + (0.20 * fraud_txn_rate))
        elif fraud_txn_rate > 0.05:
            contagion = min(1.0, 0.30 + (0.50 * fraud_txn_rate))
        else:
            contagion = 0.0

        fraud_contagion_score = round(contagion, 3)

        # 7. Dense Fraud Cluster Classification
        is_dense_fraud_cluster = (
            len(cards) >= 2
            and (len(devices) >= 1 or density >= 0.25)
            and (fraud_contagion_score >= 0.40 or len(unique_fraud_cases) >= 1)
        )

        clean_comm_id = f"COMM-{seed_label.replace(':', '_').replace('|', '_').replace(' ', '_')[:30]}"

        description = (
            f"Dense fraud community {clean_comm_id} detected with {len(cards)} cards, "
            f"{len(devices)} devices, internal density {density}, and contagion score {fraud_contagion_score}."
            if is_dense_fraud_cluster else
            f"Routine community of size {comm_size} ({len(cards)} card(s), {len(devices)} device(s))."
        )

        return {
            "seed_id": seed_id,
            "seed_node": seed_node,
            "community_id": clean_comm_id,
            "community_size": comm_size,
            "card_count": len(cards),
            "device_count": len(devices),
            "customer_count": len(customers),
            "cards": cards,
            "devices": devices[:10],
            "customers": customers[:10],
            "internal_edges_count": internal_edges,
            "internal_edge_density": density,
            "fraud_contagion_score": fraud_contagion_score,
            "fraud_cases_in_community": unique_fraud_cases,
            "is_dense_fraud_cluster": is_dense_fraud_cluster,
            "description": description,
        }


class UndocumentedPatternDetector:
    def __init__(self, client):
        self.client = client

    def detect_anomalies(self, txn_id: str, as_of: Optional[str] = None) -> Dict[str, Any]:
        """
        Evaluates transactional and graph topological anomalies to identify
        undocumented organized fraud patterns.
        """
        txn = self.client.store.transactions.get(txn_id)
        if not txn:
            return {"is_anomaly": False, "anomaly_type": None, "confidence": 0.0, "description": "", "details": {}}

        card_id = txn["card_id"]
        dev_profile = txn.get("device_profile", "")
        as_of_epoch = txn["epoch_s"]

        # 1. Device Sharing & Multi-Card Proxy Rotation Nexus
        sharing = {}
        if dev_profile and dev_profile != "None | None | None | None":
            sharing = self.client.device_sharing(dev_profile, as_of=as_of_epoch)

        new_ent = self.client.new_entity_check(txn_id, as_of=as_of_epoch)
        vel = self.client.velocity(card_id, as_of=as_of_epoch)
        geo = self.client.geo_impossible(card_id, as_of=as_of_epoch)

        distinct_cards = sharing.get("distinct_cards_count", 1)
        distinct_custs = sharing.get("distinct_customers_count", 1)
        is_proxy = bool(new_ent.get("proxy_flag"))

        # Anomaly Signature A: Multi-Card Proxy Rotation Syndicate
        if distinct_cards >= 2 and is_proxy:
            confidence = min(0.95, 0.70 + (distinct_cards * 0.05))
            return {
                "is_anomaly": True,
                "anomaly_type": "proxy_rotation_syndicate",
                "confidence": round(confidence, 2),
                "description": (
                    f"Undocumented Syndicate Pattern: Coordinated multi-card exploitation via anonymous proxy rotation. "
                    f"Device profile '{dev_profile[:30]}...' compromised {distinct_cards} cards across {distinct_custs} accounts."
                ),
                "details": {
                    "distinct_cards": distinct_cards,
                    "distinct_customers": distinct_custs,
                    "proxy_detected": True,
                    "cards_involved": sharing.get("cards", [])[:5],
                }
            }

        # Anomaly Signature B: Multi-Card Device Pooling Nexus
        # A single device operating 3+ distinct payment cards without household overlap
        if distinct_cards >= 3 and distinct_custs >= 3:
            confidence = min(0.92, 0.65 + (distinct_cards * 0.05))
            return {
                "is_anomaly": True,
                "anomaly_type": "device_pooling_nexus",
                "confidence": round(confidence, 2),
                "description": (
                    f"Undocumented Anomaly: Unregulated multi-card device pooling nexus. "
                    f"Hardware fingerprint linked to {distinct_cards} independent card accounts across {distinct_custs} cardholders."
                ),
                "details": {
                    "distinct_cards": distinct_cards,
                    "distinct_customers": distinct_custs,
                    "cards_involved": sharing.get("cards", [])[:5],
                }
            }

        # Anomaly Signature C: Coordinated Velocity Burst Across Accounts
        if distinct_cards >= 2 and vel.get("velocity_spike_ratio", 1.0) >= 3.0:
            return {
                "is_anomaly": True,
                "anomaly_type": "coordinated_burst_nexus",
                "confidence": 0.85,
                "description": (
                    f"Undocumented Anomaly: Synchronized high-velocity burst across multi-account device nexus. "
                    f"Spike ratio {vel.get('velocity_spike_ratio')} observed across {distinct_cards} linked cards."
                ),
                "details": {
                    "distinct_cards": distinct_cards,
                    "velocity_spike_ratio": vel.get("velocity_spike_ratio"),
                    "windows": vel.get("windows"),
                }
            }

        # Anomaly Signature D: Impossible Geo-Dispersion Network
        if geo.get("anomalies_count", 0) >= 2:
            return {
                "is_anomaly": True,
                "anomaly_type": "impossible_geo_dispersion",
                "confidence": 0.80,
                "description": (
                    f"Undocumented Anomaly: Rapid multi-regional dispersion indicating distributed physical skimming or counterfeit relay. "
                    f"{geo.get('anomalies_count')} impossible velocity hops observed across non-contiguous billing regions."
                ),
                "details": {
                    "hop_count": geo.get("anomalies_count"),
                }
            }

        return {
            "is_anomaly": False,
            "anomaly_type": None,
            "confidence": 0.0,
            "description": "",
            "details": {}
        }


class MultiCardBurstClusterDetector:
    """
    Multi-Card Temporal Velocity Burst & Coordinated Testing Detector.
    Identifies distributed card testing, bot attacks, and synchronized cash-outs
    across distinct payment cards sharing hardware fingerprints or merchant channels
    within narrow temporal windows (e.g. 1h to 24h).
    """

    def __init__(self, client):
        self.client = client

    def detect_burst_cluster(
        self,
        txn_id: str,
        window_hours: float = 24.0,
        as_of: Optional[Union[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes the temporal neighborhood around txn_id for coordinated multi-card bursts.
        """
        from src.graph.client import parse_as_of_epoch
        txn = self.client.store.transactions.get(str(txn_id))
        if not txn:
            return {
                "txn_id": str(txn_id),
                "is_coordinated_burst": False,
                "burst_card_count": 0,
                "burst_txn_count": 0,
                "confidence": 0.0,
                "threat_level": "low",
                "description": f"Transaction {txn_id} not found.",
            }

        t_epoch = txn["epoch_s"]
        card_id = txn["card_id"]
        dev_profile = txn.get("device_profile", "")

        as_of_epoch = parse_as_of_epoch(as_of) if as_of is not None else t_epoch
        cutoff_epoch = min(t_epoch, as_of_epoch)
        window_kilosec = max(1, int(window_hours * 3.6))

        # Collect candidate transactions within window
        candidates = []
        if dev_profile and dev_profile != "None | None | None | None" and not dev_profile.startswith("UnknownDevice"):
            all_dev_txns = self.client.store.txns_by_device.get(dev_profile, [])
            for t in all_dev_txns:
                if (cutoff_epoch - window_kilosec) <= t["epoch_s"] <= cutoff_epoch:
                    candidates.append(t)
        else:
            # Fallback to card transactions in window
            all_card_txns = self.client.store.txns_by_card.get(card_id, [])
            for t in all_card_txns:
                if (cutoff_epoch - window_kilosec) <= t["epoch_s"] <= cutoff_epoch:
                    candidates.append(t)

        # Deduplicate
        seen_tids = set()
        cluster_txns = []
        for t in candidates:
            tid = str(t["TransactionID"])
            if tid not in seen_tids:
                seen_tids.add(tid)
                cluster_txns.append(t)

        cluster_txns.sort(key=lambda x: x["epoch_s"])

        distinct_cards = sorted(list(set(t["card_id"] for t in cluster_txns)))
        distinct_customers = sorted(list(set(t["customer_id"] for t in cluster_txns)))
        txn_count = len(cluster_txns)
        card_count = len(distinct_cards)
        customer_count = len(distinct_customers)
        total_exposure = round(sum(t.get("amount", 0.0) for t in cluster_txns), 2)

        micro_deposits = [t for t in cluster_txns if float(t.get("amount", 0.0)) <= 5.0]
        micro_deposit_ratio = round(len(micro_deposits) / txn_count, 3) if txn_count > 0 else 0.0

        # Calculate inter-arrival intervals
        inter_arrivals_sec = []
        for i in range(1, len(cluster_txns)):
            diff_sec = (cluster_txns[i]["epoch_s"] - cluster_txns[i - 1]["epoch_s"]) * 1000
            inter_arrivals_sec.append(diff_sec)

        if len(inter_arrivals_sec) >= 2:
            mean_interval = sum(inter_arrivals_sec) / len(inter_arrivals_sec)
            variance = sum((x - mean_interval) ** 2 for x in inter_arrivals_sec) / len(inter_arrivals_sec)
            std_interval = round(math.sqrt(variance), 1)
        else:
            mean_interval = 0.0
            std_interval = 0.0

        is_bot_pattern = (txn_count >= 3 and 0.0 < std_interval <= 120.0)

        is_coordinated_burst = (
            (card_count >= 2 and txn_count >= 3 and window_hours <= 24.0)
            or (card_count >= 3 and txn_count >= 3)
            or (txn_count >= 4 and micro_deposit_ratio >= 0.50)
        )

        if is_coordinated_burst:
            confidence = min(0.98, 0.70 + (0.05 * card_count) + (0.10 * micro_deposit_ratio))
            threat = "critical" if card_count >= 3 else ("high" if card_count >= 2 else "medium")
        else:
            confidence = 0.0
            threat = "low"

        description = (
            f"Coordinated multi-card velocity burst detected: {card_count} distinct cards executed {txn_count} transactions "
            f"within {window_hours}h window (exposure: ${total_exposure:.2f}, micro-deposit ratio: {micro_deposit_ratio:.2f}, "
            f"bot interval std: {std_interval}s)."
            if is_coordinated_burst else
            f"Routine activity: {txn_count} transaction(s) across {card_count} card(s) in {window_hours}h window."
        )

        return {
            "txn_id": str(txn_id),
            "seed_card_id": card_id,
            "window_hours": window_hours,
            "is_coordinated_burst": is_coordinated_burst,
            "burst_card_count": card_count,
            "burst_customer_count": customer_count,
            "burst_txn_count": txn_count,
            "total_exposure_usd": total_exposure,
            "micro_deposit_ratio": micro_deposit_ratio,
            "is_bot_periodicity": is_bot_pattern,
            "inter_arrival_mean_sec": round(mean_interval, 1),
            "inter_arrival_std_sec": std_interval,
            "threat_level": threat,
            "confidence": round(confidence, 2),
            "cards_involved": distinct_cards[:10],
            "txn_ids": [t["TransactionID"] for t in cluster_txns][:15],
            "description": description,
        }


class FraudContagionPageRank:
    """
    Personalized PageRank / Random Walk with Restart (RWR) Engine for Fraud Contagion.
    Calculates continuous structural contagion distributions from confirmed fraud seeds
    across heterogeneous multi-hop financial subgraphs.
    """

    def __init__(self, client):
        self.client = client

    def calculate_contagion(
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
    ) -> Dict[str, Any]:
        """
        Calculates Personalized PageRank from confirmed fraud seeds in the local ego-network.
        Returns continuous contagion score, risk classification, and top contagion nodes.
        """
        import time
        from src.graph.client import parse_as_of_epoch

        t0 = time.perf_counter()
        as_of_epoch = parse_as_of_epoch(as_of)

        if entity_type == "card":
            target_card = seed_id
        elif entity_type == "customer":
            cust_txns = self.client.store.txns_by_customer.get(seed_id, [])
            target_card = cust_txns[0]["card_id"] if cust_txns else seed_id
        elif entity_type == "transaction":
            txn = self.client.store.transactions.get(seed_id, {})
            target_card = txn.get("card_id", seed_id)
        else:
            target_card = seed_id

        target_node = f"CARD:{target_card}"

        adj: Dict[str, Set[str]] = defaultdict(set)
        node_types: Dict[str, str] = {target_node: "card"}
        visited: Set[str] = {target_node}
        queue: List[Tuple[str, int]] = [(target_node, 0)]

        # Multi-hop ego-net extraction with temporal bounds
        while queue and len(visited) < max_nodes:
            curr_node, hops = queue.pop(0)
            if hops >= max_hops:
                continue

            ntype, nid = curr_node.split(":", 1)

            if ntype == "CARD":
                # Connect to customer
                cust_id = self.client.store.cards.get(nid, {}).get("customer_id")
                if cust_id:
                    cnode = f"CUST:{cust_id}"
                    adj[curr_node].add(cnode)
                    adj[cnode].add(curr_node)
                    if cnode not in visited and len(visited) < max_nodes:
                        visited.add(cnode)
                        node_types[cnode] = "customer"
                        queue.append((cnode, hops + 1))

                # Connect to transactions & devices
                card_txns = self.client.store.txns_by_card.get(nid, [])
                recent_txns = [t for t in card_txns if t["epoch_s"] <= as_of_epoch][-10:]
                for t in recent_txns:
                    dev = t.get("device_profile")
                    if dev and dev != "None | None | None | None" and not dev.startswith("UnknownDevice"):
                        dnode = f"DEV:{dev[:35]}"
                        adj[curr_node].add(dnode)
                        adj[dnode].add(curr_node)
                        if dnode not in visited and len(visited) < max_nodes:
                            visited.add(dnode)
                            node_types[dnode] = "device"
                            queue.append((dnode, hops + 1))

                # Connect to closed cases
                cases = self.client.store.cases_by_card.get(nid, [])
                for c in cases:
                    if parse_as_of_epoch(c.get("opened_at")) <= as_of_epoch:
                        casenode = f"CASE:{c['case_id']}"
                        adj[curr_node].add(casenode)
                        adj[casenode].add(curr_node)
                        if casenode not in visited and len(visited) < max_nodes:
                            visited.add(casenode)
                            node_types[casenode] = "case"
                            queue.append((casenode, hops + 1))

            elif ntype == "DEV":
                dev_key = nid
                all_cards = set()
                for d_full, cards in getattr(self.client.store, "cards_by_device", {}).items():
                    if d_full.startswith(dev_key):
                        all_cards.update(cards)
                if len(all_cards) <= 15:
                    for c_id in list(all_cards)[:6]:
                        cnode = f"CARD:{c_id}"
                        adj[curr_node].add(cnode)
                        adj[cnode].add(curr_node)
                        if cnode not in visited and len(visited) < max_nodes:
                            visited.add(cnode)
                            node_types[cnode] = "card"
                            queue.append((cnode, hops + 1))

            elif ntype == "CUST":
                cust_txns = self.client.store.txns_by_customer.get(nid, [])
                cust_cards = set(t["card_id"] for t in cust_txns if t["epoch_s"] <= as_of_epoch)
                for c_id in list(cust_cards)[:5]:
                    cnode = f"CARD:{c_id}"
                    adj[curr_node].add(cnode)
                    adj[cnode].add(curr_node)
                    if cnode not in visited and len(visited) < max_nodes:
                        visited.add(cnode)
                        node_types[cnode] = "card"
                        queue.append((cnode, hops + 1))

        # Identify fraud seeds
        fraud_seeds = set()
        if custom_fraud_seeds:
            for s in custom_fraud_seeds:
                s_node = s if ":" in s else f"CARD:{s}"
                if s_node in visited:
                    fraud_seeds.add(s_node)
        else:
            for node in visited:
                ntype, nid = node.split(":", 1)
                if ntype == "CASE":
                    c_obj = self.client.store.closed_cases.get(nid, {})
                    if c_obj.get("outcome") == "confirmed_fraud":
                        fraud_seeds.add(node)
                elif ntype == "CARD":
                    cases = self.client.store.cases_by_card.get(nid, [])
                    if any(c.get("outcome") == "confirmed_fraud" and parse_as_of_epoch(c.get("opened_at")) <= as_of_epoch for c in cases):
                        fraud_seeds.add(node)

        node_list = sorted(list(visited))
        node_idx = {n: i for i, n in enumerate(node_list)}
        N = len(node_list)

        p0 = [0.0] * N
        if fraud_seeds:
            mode = "contagion_from_fraud_seeds"
            seed_weight = 1.0 / len(fraud_seeds)
            for s in fraud_seeds:
                p0[node_idx[s]] = seed_weight
        else:
            mode = "target_centrality"
            p0[node_idx[target_node]] = 1.0

        # Power iteration
        r = list(p0)
        n_iter = 0
        for it in range(max_iter):
            n_iter += 1
            r_next = [0.0] * N
            for u in node_list:
                u_idx = node_idx[u]
                r_u = r[u_idx]
                if r_u <= 0.0:
                    continue
                nbrs = adj.get(u, set())
                if nbrs:
                    share = (1.0 - restart_prob) * r_u / len(nbrs)
                    for v in nbrs:
                        r_next[node_idx[v]] += share
                else:
                    for i in range(N):
                        r_next[i] += (1.0 - restart_prob) * r_u / N

            for i in range(N):
                r_next[i] += restart_prob * p0[i]

            diff = sum(abs(r_next[i] - r[i]) for i in range(N))
            r = r_next
            if diff < tol:
                break

        target_score = round(r[node_idx[target_node]], 4)

        if mode == "contagion_from_fraud_seeds":
            if target_score >= 0.15:
                threat = "critical"
            elif target_score >= 0.08:
                threat = "high"
            elif target_score >= 0.03:
                threat = "elevated"
            else:
                threat = "low"
            contagion_score = target_score
            description = (
                f"Personalized PageRank contagion: Target {seed_id} received {target_score:.4f} "
                f"contagion probability from {len(fraud_seeds)} confirmed fraud seed(s) in its local subgraph "
                f"(threat level: {threat})."
            )
        else:
            threat = "none"
            contagion_score = 0.0
            description = (
                f"Personalized PageRank centrality: Target {seed_id} has 0 confirmed fraud seeds in its local subgraph "
                f"(contagion: 0.0, local structural centrality: {target_score:.4f})."
            )

        top_nodes = sorted(
            [{"id": n, "type": node_types.get(n, "unknown"), "score": round(r[node_idx[n]], 4)} for n in node_list],
            key=lambda x: x["score"],
            reverse=True,
        )[:10]

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return {
            "target_id": seed_id,
            "target_node": target_node,
            "subgraph_size": N,
            "edge_count": sum(len(adj[n]) for n in node_list) // 2,
            "fraud_seeds": sorted(list(fraud_seeds)),
            "mode": mode,
            "target_contagion_score": contagion_score,
            "target_centrality_score": target_score,
            "contagion_risk_level": threat,
            "top_nodes_by_contagion": top_nodes,
            "iterations_to_convergence": n_iter,
            "restart_probability": restart_prob,
            "elapsed_ms": elapsed_ms,
            "description": description,
        }

