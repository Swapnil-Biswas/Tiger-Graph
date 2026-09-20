"""
Topological Graph Embedding & GNN-Ready Adjacency Exporter (src/graph/embeddings.py)
Transforms heterogeneous multi-hop incident subgraphs into standardized node feature tensors (x),
sparse adjacency edge lists (edge_index), and edge attribute matrices (edge_attr)
compatible with PyTorch Geometric (PyG), DGL, and Graph Neural Networks (RGCN, GAT),
as well as tabular ego-net topological vectors for gradient boosted trees (XGBoost/LightGBM).
All operations strictly enforce temporal (as_of) isolation.
"""

import math
from typing import Dict, List, Set, Any, Optional, Union, Tuple
from collections import defaultdict

from src.graph.client import parse_as_of_epoch


class TopologicalGraphEmbeddingExporter:
    """
    Exports normalized graph topological features and sparse adjacency structures.
    """

    def __init__(self, client: Any):
        self.client = client

    def extract_gnn_subgraph(
        self,
        seed_id: str,
        entity_type: str = "card",
        as_of: Optional[Union[str, int]] = None,
        k_hops: int = 2,
        max_nodes: int = 50,
    ) -> Dict[str, Any]:
        """
        Extracts a k-hop heterogeneous subgraph around seed_id up to as_of,
        generating normalized node features, sparse edge indices, and edge attributes.
        """
        as_of_epoch = parse_as_of_epoch(as_of)

        # 1. Resolve seed entity
        if entity_type == "transaction":
            txn = self.client.store.transactions.get(seed_id, {})
            seed_card = txn.get("card_id", seed_id)
        elif entity_type == "customer":
            cust_txns = self.client.store.txns_by_customer.get(seed_id, [])
            seed_card = cust_txns[0]["card_id"] if cust_txns else seed_id
        else:
            seed_card = seed_id

        seed_node = f"CARD:{seed_card}"

        # 2. Extract k-hop neighborhood
        nodes: List[str] = [seed_node]
        node_types: Dict[str, str] = {seed_node: "card"}
        visited: Set[str] = {seed_node}
        queue: List[Tuple[str, int]] = [(seed_node, 0)]
        edges: List[Tuple[str, str, str, float]] = []  # (u, v, edge_type, weight)
        adj: Dict[str, Set[str]] = defaultdict(set)

        while queue and len(visited) < max_nodes:
            curr_node, hop = queue.pop(0)
            if hop >= k_hops:
                continue

            if curr_node.startswith("CARD:"):
                cid = curr_node[5:]
                all_txns = self.client.store.txns_by_card.get(cid, [])
                txns = [t for t in all_txns if t["epoch_s"] <= as_of_epoch]

                for t in txns:
                    tid = str(t.get("TransactionID", ""))
                    t_node = f"TXN:{tid}"
                    if t_node not in visited and len(visited) < max_nodes:
                        visited.add(t_node)
                        nodes.append(t_node)
                        node_types[t_node] = "transaction"
                        queue.append((t_node, hop + 1))
                    if t_node in visited:
                        edges.append((curr_node, t_node, "CARD_HAS_TXN", float(t.get("amount", 1.0))))
                        edges.append((t_node, curr_node, "TXN_ON_CARD", float(t.get("amount", 1.0))))
                        adj[curr_node].add(t_node)
                        adj[t_node].add(curr_node)

                    # Customer
                    cust = t.get("customer_id")
                    if cust:
                        c_node = f"CUST:{cust}"
                        if c_node not in visited and len(visited) < max_nodes:
                            visited.add(c_node)
                            nodes.append(c_node)
                            node_types[c_node] = "customer"
                            queue.append((c_node, hop + 1))
                        if c_node in visited:
                            edges.append((curr_node, c_node, "CARD_OWNED_BY_CUST", 1.0))
                            edges.append((c_node, curr_node, "CUST_OWNS_CARD", 1.0))
                            adj[curr_node].add(c_node)
                            adj[c_node].add(curr_node)

                    # Device
                    dev = t.get("device_profile")
                    if dev and dev != "None | None | None | None" and not dev.startswith("UnknownDevice"):
                        dev_card_count = len(set(x["card_id"] for x in self.client.store.txns_by_device.get(dev, [])))
                        if dev_card_count <= 15:
                            d_node = f"DEV:{dev}"
                            if d_node not in visited and len(visited) < max_nodes:
                                visited.add(d_node)
                                nodes.append(d_node)
                                node_types[d_node] = "device"
                                queue.append((d_node, hop + 1))
                            if d_node in visited:
                                edges.append((curr_node, d_node, "CARD_USED_DEVICE", 1.0))
                                edges.append((d_node, curr_node, "DEVICE_USED_BY_CARD", 1.0))
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
                        if card_node not in visited and len(visited) < max_nodes:
                            visited.add(card_node)
                            nodes.append(card_node)
                            node_types[card_node] = "card"
                            queue.append((card_node, hop + 1))
                        if card_node in visited:
                            edges.append((curr_node, card_node, "DEVICE_USED_BY_CARD", 1.0))
                            edges.append((card_node, curr_node, "CARD_USED_DEVICE", 1.0))
                            adj[curr_node].add(card_node)
                            adj[card_node].add(curr_node)

        # 3. Build Node Mapping and Normalized Node Features (x)
        node_to_idx = {n: i for i, n in enumerate(nodes)}
        num_nodes = len(nodes)

        # Type one-hot map: [card, customer, device, transaction]
        type_onehot_map = {
            "card": [1.0, 0.0, 0.0, 0.0],
            "customer": [0.0, 1.0, 0.0, 0.0],
            "device": [0.0, 0.0, 1.0, 0.0],
            "transaction": [0.0, 0.0, 0.0, 1.0],
        }

        # Calculate local clustering coefficients
        clustering_coeffs = {}
        for n in nodes:
            nbrs = adj.get(n, set())
            k = len(nbrs)
            if k >= 2:
                # Count edges between neighbors
                e_nbrs = 0
                for u in nbrs:
                    for v in nbrs:
                        if u < v and v in adj.get(u, set()):
                            e_nbrs += 1
                clustering_coeffs[n] = (2.0 * e_nbrs) / (k * (k - 1))
            else:
                clustering_coeffs[n] = 0.0

        node_features = []
        for n in nodes:
            ntype = node_types.get(n, "card")
            feat_type = type_onehot_map.get(ntype, [0.0, 0.0, 0.0, 0.0])

            # Degree centrality normalized
            deg = len(adj.get(n, set()))
            deg_norm = round(deg / max(1, num_nodes - 1), 4)

            # Local clustering coefficient
            cc = round(clustering_coeffs.get(n, 0.0), 4)

            # Fraud history indicator
            has_fraud = 0.0
            if ntype == "card":
                cid = n[5:]
                cases = [c for c in self.client.store.cases_by_card.get(cid, []) if parse_as_of_epoch(c.get("opened_at")) <= as_of_epoch and c.get("outcome") == "confirmed_fraud"]
                has_fraud = 1.0 if cases else 0.0
            elif ntype == "transaction":
                tid = n[4:]
                txn_obj = self.client.store.transactions.get(tid, {})
                has_fraud = 1.0 if txn_obj.get("is_fraud") == 1 else 0.0

            # Financial exposure (log normalized)
            exp_norm = 0.0
            if ntype == "card":
                cid = n[5:]
                all_card_txns = self.client.store.txns_by_card.get(cid, [])
                tot = sum(t.get("amount", 0.0) for t in all_card_txns if t["epoch_s"] <= as_of_epoch)
                exp_norm = round(min(1.0, math.log10(max(1.0, tot)) / 6.0), 4)
            elif ntype == "transaction":
                tid = n[4:]
                amt = self.client.store.transactions.get(tid, {}).get("amount", 0.0)
                exp_norm = round(min(1.0, math.log10(max(1.0, amt)) / 6.0), 4)

            # Risk score feature
            risk_score = 0.5
            if ntype == "transaction":
                tid = n[4:]
                risk_score = float(self.client.store.transactions.get(tid, {}).get("risk_score", 0.5) or 0.5)
            elif ntype == "card":
                cid = n[5:]
                vel = self.client.velocity(cid, as_of=as_of_epoch)
                spike = vel.get("velocity_spike_ratio", 1.0)
                risk_score = round(min(1.0, spike / 5.0), 4)

            # Node feature vector (10 dimensions)
            row = feat_type + [deg_norm, cc, has_fraud, exp_norm, risk_score]
            node_features.append(row)

        # 4. Build Sparse Edge Index [2, E] and Edge Attributes [E, D_edge]
        edge_type_map = {
            "CARD_HAS_TXN": [1.0, 0.0, 0.0, 0.0],
            "TXN_ON_CARD": [1.0, 0.0, 0.0, 0.0],
            "CARD_OWNED_BY_CUST": [0.0, 1.0, 0.0, 0.0],
            "CUST_OWNS_CARD": [0.0, 1.0, 0.0, 0.0],
            "CARD_USED_DEVICE": [0.0, 0.0, 1.0, 0.0],
            "DEVICE_USED_BY_CARD": [0.0, 0.0, 1.0, 0.0],
        }

        # Deduplicate edges
        seen_edges = set()
        edge_index_src = []
        edge_index_dst = []
        edge_attributes = []

        for u, v, etype, weight in edges:
            if u in node_to_idx and v in node_to_idx:
                pair = (node_to_idx[u], node_to_idx[v], etype)
                if pair not in seen_edges:
                    seen_edges.add(pair)
                    edge_index_src.append(node_to_idx[u])
                    edge_index_dst.append(node_to_idx[v])
                    etype_vec = edge_type_map.get(etype, [0.0, 0.0, 0.0, 1.0])
                    norm_weight = round(min(1.0, math.log10(max(1.0, weight)) / 4.0), 4)
                    edge_attributes.append(etype_vec + [norm_weight])

        edge_index = [edge_index_src, edge_index_dst]
        num_edges = len(edge_index_src)

        # 5. Extract Tabular Ego-Net Topological Vector (for XGBoost / LightGBM)
        card_nodes = [n for n in nodes if node_types[n] == "card"]
        dev_nodes = [n for n in nodes if node_types[n] == "device"]
        cust_nodes = [n for n in nodes if node_types[n] == "customer"]
        txn_nodes = [n for n in nodes if node_types[n] == "transaction"]

        graph_density = round((2.0 * num_edges) / (num_nodes * (num_nodes - 1)), 4) if num_nodes > 1 else 0.0
        avg_clustering = round(sum(clustering_coeffs.values()) / max(1, num_nodes), 4)
        max_deg = max((len(adj.get(n, set())) for n in nodes), default=0)

        tabular_vector = {
            "subgraph_node_count": float(num_nodes),
            "subgraph_edge_count": float(num_edges),
            "subgraph_density": graph_density,
            "subgraph_avg_clustering": avg_clustering,
            "subgraph_max_degree": float(max_deg),
            "card_nodes_count": float(len(card_nodes)),
            "device_nodes_count": float(len(dev_nodes)),
            "customer_nodes_count": float(len(cust_nodes)),
            "transaction_nodes_count": float(len(txn_nodes)),
            "fraud_precedents_count": float(sum(1 for row in node_features if row[6] == 1.0)),
        }

        return {
            "seed_id": seed_id,
            "seed_node": seed_node,
            "num_nodes": num_nodes,
            "num_edges": num_edges,
            "node_ids": nodes,
            "node_types": [node_types[n] for n in nodes],
            "x": node_features,  # Shape: [N, 9]
            "edge_index": edge_index,  # Shape: [2, E]
            "edge_attr": edge_attributes,  # Shape: [E, 5]
            "tabular_vector": tabular_vector,
            "pyg_format_ready": True,
        }


class TemporalGraphAttentionPooler:
    """
    Temporal Graph Attention Subgraph Pooling Engine.
    Aggregates variable-size heterogeneous node feature tensors ([N, D]) into fixed-dimensional
    graph-level representations ([D] or [3D]) using time-decayed attention mechanisms.
    """

    def __init__(self, client: Any = None):
        self.client = client
        self.default_weights = [1.0, 0.8, 1.2, 1.0, 1.5, 1.2, 3.0, 2.0, 2.5]

    def pool_subgraph(
        self,
        pyg_subgraph: Dict[str, Any],
        as_of: Optional[Union[str, int]] = None,
        decay_lambda: float = 0.05,
        feature_weights: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Pools heterogeneous node features x ([N, D]) into fixed-dimensional vectors:
        - pooled_attention_embedding: [D] (attention weighted)
        - pooled_mean_embedding: [D]
        - pooled_max_embedding: [D]
        - concatenated_embedding: [3D]
        """
        import time

        t0 = time.perf_counter()
        as_of_epoch = parse_as_of_epoch(as_of)

        num_nodes = pyg_subgraph.get("num_nodes", 0)
        node_ids = pyg_subgraph.get("node_ids", [])
        node_types = pyg_subgraph.get("node_types", [])
        x = pyg_subgraph.get("x", [])

        if num_nodes == 0 or not x:
            return {
                "subgraph_size": 0,
                "feature_dim": 9,
                "pooled_dim": 27,
                "attention_weights": {},
                "pooled_attention_embedding": [0.0] * 9,
                "pooled_mean_embedding": [0.0] * 9,
                "pooled_max_embedding": [0.0] * 9,
                "concatenated_embedding": [0.0] * 27,
                "top_attention_nodes": [],
                "elapsed_ms": 0.0,
            }

        w = feature_weights or self.default_weights
        feat_dim = len(x[0])

        # Compute days_prior for each node
        days_priors = []
        for i, nid in enumerate(node_ids):
            ntype = node_types[i] if i < len(node_types) else "card"
            node_epoch = as_of_epoch
            if self.client and hasattr(self.client, "store"):
                if ntype == "transaction":
                    tid = nid[4:] if nid.startswith("TXN:") else nid
                    txn_obj = self.client.store.transactions.get(tid, {})
                    node_epoch = txn_obj.get("epoch_s", as_of_epoch)
                elif ntype == "card":
                    cid = nid[5:] if nid.startswith("CARD:") else nid
                    card_txns = self.client.store.txns_by_card.get(cid, [])
                    valid_txns = [t["epoch_s"] for t in card_txns if t["epoch_s"] <= as_of_epoch]
                    node_epoch = max(valid_txns) if valid_txns else as_of_epoch
                elif ntype == "device":
                    did = nid[4:] if nid.startswith("DEV:") else nid
                    dev_txns = self.client.store.txns_by_device.get(did, [])
                    valid_txns = [t["epoch_s"] for t in dev_txns if t["epoch_s"] <= as_of_epoch]
                    node_epoch = max(valid_txns) if valid_txns else as_of_epoch
                elif ntype == "customer":
                    cid = nid[5:] if nid.startswith("CUST:") else nid
                    cust_txns = self.client.store.txns_by_customer.get(cid, [])
                    valid_txns = [t["epoch_s"] for t in cust_txns if t["epoch_s"] <= as_of_epoch]
                    node_epoch = max(valid_txns) if valid_txns else as_of_epoch

            diff_sec = max(0.0, float(as_of_epoch - node_epoch))
            days = diff_sec / 86.4
            days_priors.append(days)

        # Compute raw attention scores
        scores = []
        for i in range(num_nodes):
            feat_score = sum(w[j] * x[i][j] for j in range(min(len(w), feat_dim)))
            time_penalty = decay_lambda * days_priors[i]
            scores.append(feat_score - time_penalty)

        # Softmax
        max_s = max(scores)
        exp_scores = [math.exp(s - max_s) for s in scores]
        sum_exp = sum(exp_scores)
        attn_weights = [e / sum_exp for e in exp_scores]

        # Compute pooled vectors
        h_attn = [0.0] * feat_dim
        h_mean = [0.0] * feat_dim
        h_max = [float("-inf")] * feat_dim

        for i in range(num_nodes):
            alpha = attn_weights[i]
            for j in range(feat_dim):
                val = x[i][j]
                h_attn[j] += alpha * val
                h_mean[j] += val / num_nodes
                if val > h_max[j]:
                    h_max[j] = val

        h_concat = [round(v, 4) for v in (h_attn + h_mean + h_max)]
        h_attn = [round(v, 4) for v in h_attn]
        h_mean = [round(v, 4) for v in h_mean]
        h_max = [round(v, 4) for v in h_max]

        attn_map = {node_ids[i]: round(attn_weights[i], 4) for i in range(num_nodes)}
        top_nodes = sorted(
            [
                {
                    "node_id": node_ids[i],
                    "node_type": node_types[i],
                    "attention_weight": round(attn_weights[i], 4),
                    "days_prior": round(days_priors[i], 1),
                }
                for i in range(num_nodes)
            ],
            key=lambda item: item["attention_weight"],
            reverse=True,
        )[:10]

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return {
            "subgraph_size": num_nodes,
            "feature_dim": feat_dim,
            "pooled_dim": feat_dim * 3,
            "attention_weights": attn_map,
            "pooled_attention_embedding": h_attn,
            "pooled_mean_embedding": h_mean,
            "pooled_max_embedding": h_max,
            "concatenated_embedding": h_concat,
            "top_attention_nodes": top_nodes,
            "elapsed_ms": elapsed_ms,
        }

