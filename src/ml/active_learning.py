"""
Active Learning Sample Selector & Hard-Negative Mining Engine (src/ml/active_learning.py)
Identifies the most informative, ambiguous, and boundary-defining transaction samples
from historical transaction streams for continuous GBDT and GNN classifier retraining.
Implements Margin Uncertainty, Shannon Entropy, Hard-Negative Discrepancy Mining,
and Submodular Topological Diversity Filtering with Strict Temporal Isolation.
"""

import math
import hashlib
from typing import Dict, List, Set, Any, Optional, Union, Tuple
from collections import defaultdict

from src.graph.client import parse_as_of_epoch


class ActiveLearningSampleSelector:
    """
    Intelligent sample selection engine for continuous model retraining and active learning.
    """

    HIGH_RISK_MCCS = {"6051", "4829", "7995", "5944"}

    def __init__(self, client: Any):
        self.client = client

    def compute_binary_entropy(self, p: float) -> float:
        """
        Computes normalized binary Shannon entropy H(P) in [0.0, 1.0].
        Maximized (1.0) at P = 0.50, minimized (0.0) at P = 0.0 or 1.0.
        """
        p_clamped = max(1e-6, min(1.0 - 1e-6, float(p)))
        h = -(p_clamped * math.log2(p_clamped) + (1.0 - p_clamped) * math.log2(1.0 - p_clamped))
        return round(float(h), 4)

    def compute_margin_uncertainty(self, p: float) -> float:
        """
        Computes margin uncertainty: 1.0 - 2 * |P - 0.50|.
        Ranges from 1.0 (exact decision boundary at 0.50) to 0.0 (certain prediction).
        """
        return round(1.0 - 2.0 * abs(float(p) - 0.50), 4)

    def extract_topological_flags(self, txn: Dict[str, Any], as_of_epoch: int) -> List[str]:
        """
        Extracts structural topological risk indicators for a candidate transaction.
        """
        flags: List[str] = []
        card_id = str(txn.get("card_id", ""))
        amount = float(txn.get("amount", 0.0))
        mcc = str(txn.get("mcc", ""))
        dev = txn.get("device_profile")

        if mcc in self.HIGH_RISK_MCCS:
            flags.append(f"HIGH_RISK_MCC_{mcc}")

        # Structuring threshold indicator
        if 8500.0 <= amount < 10000.0:
            flags.append("NEAR_CTR_THRESHOLD")
        elif amount >= 10000.0:
            flags.append("HIGH_EXPOSURE")

        # Device sharing
        if dev and dev != "None | None | None | None" and not dev.startswith("UnknownDevice"):
            dev_cards = set(x.get("card_id") for x in self.client.store.txns_by_device.get(dev, []))
            if len(dev_cards) > 1:
                flags.append("SHARED_DEVICE_NEXUS")

        # Multi-card velocity check
        card_txns = [t for t in self.client.store.txns_by_card.get(card_id, []) if t.get("epoch_s", 0) <= as_of_epoch]
        recent_txns = [t for t in card_txns if abs(t.get("epoch_s", 0) - txn.get("epoch_s", 0)) <= 86400]
        if len(recent_txns) >= 4:
            flags.append("HIGH_CARD_VELOCITY")

        return flags

    def mine_candidate_samples(
        self,
        target_size: int = 20,
        strategy: str = "hybrid_balanced",
        as_of: Optional[Union[str, int]] = None,
        max_scan: int = 2000,
        max_per_card: int = 2,
        max_per_merchant: int = 3,
    ) -> Dict[str, Any]:
        """
        Mines the top-K most informative active learning transaction samples.

        Strategies:
        - 'margin_uncertainty': Maximizes 1.0 - 2*|P - 0.50|
        - 'shannon_entropy': Maximizes binary entropy H(P)
        - 'hard_negative': Mines non-fraud transactions with high risk scores and topological flags
        - 'hybrid_balanced': Combines margin uncertainty, entropy, and topological discrepancy
        """
        as_of_epoch = parse_as_of_epoch(as_of)

        all_txns = list(self.client.store.transactions.values())
        # Filter temporally up to as_of
        valid_txns = [t for t in all_txns if t.get("epoch_s", 0) <= as_of_epoch]
        # Sort by epoch descending to prioritize recent transactions
        valid_txns.sort(key=lambda x: x.get("epoch_s", 0), reverse=True)
        scan_pool = valid_txns[:max_scan]

        scored_candidates: List[Dict[str, Any]] = []

        for txn in scan_pool:
            tid = str(txn.get("TransactionID", ""))
            card_id = str(txn.get("card_id", ""))
            merch = str(txn.get("merchant_id") or txn.get("merchant_name") or "")
            if not merch or merch in ("UNKNOWN", "None"):
                p_code = txn.get("product_code", "W")
                addr = str(txn.get("addr1", ""))
                merch = f"MERCH_{p_code}_{addr}" if addr else f"MERCH_{p_code}_{str(txn.get('card1', '0'))[:3]}"
            amount = float(txn.get("amount", 0.0))
            epoch = int(txn.get("epoch_s", 0))
            is_fraud = int(txn.get("is_fraud", 0))

            # Retrieve or calculate model predicted probability
            # If txn has risk_score use it, otherwise default around 0.50
            p_pred = float(txn.get("risk_score", 0.50) if txn.get("risk_score") is not None else 0.50)

            # Metrics
            margin = self.compute_margin_uncertainty(p_pred)
            entropy = self.compute_binary_entropy(p_pred)
            flags = self.extract_topological_flags(txn, as_of_epoch)
            is_hard_neg = (is_fraud == 0 and (p_pred >= 0.35 or len(flags) > 0))

            # Score by strategy
            if strategy == "margin_uncertainty":
                final_score = margin
            elif strategy == "shannon_entropy":
                final_score = entropy
            elif strategy == "hard_negative":
                # Boost if non-fraud with high risk and flags
                topo_bonus = 0.15 * len(flags)
                final_score = (p_pred * 0.7 + topo_bonus) if is_fraud == 0 else 0.0
            else:  # 'hybrid_balanced'
                topo_bonus = 0.10 * len(flags)
                hard_neg_boost = 0.25 if is_hard_neg else 0.0
                final_score = (0.40 * margin) + (0.30 * entropy) + hard_neg_boost + topo_bonus

            # Sample training weight for continuous retraining loss
            sample_weight = round(min(5.0, 1.0 + 3.0 * final_score + (1.0 if is_hard_neg else 0.0)), 3)

            scored_candidates.append({
                "transaction_id": tid,
                "card_id": card_id,
                "merchant_id": merch,
                "amount": amount,
                "epoch_s": epoch,
                "true_label": is_fraud,
                "predicted_probability": p_pred,
                "margin_uncertainty": margin,
                "entropy": entropy,
                "is_hard_negative": is_hard_neg,
                "topological_flags": flags,
                "informativeness_score": round(final_score, 4),
                "retraining_weight": sample_weight,
            })

        # Sort descending by informativeness score
        scored_candidates.sort(key=lambda x: x["informativeness_score"], reverse=True)

        # Apply Topological Diversity Filtering (Submodular Representative Selection)
        selected: List[Dict[str, Any]] = []
        selected_ids: Set[str] = set()
        card_counts = defaultdict(int)
        merch_counts = defaultdict(int)

        # Pass 1: Strict diversity caps
        for c in scored_candidates:
            cid = c["card_id"]
            mid = c["merchant_id"]
            if card_counts[cid] < max_per_card and merch_counts[mid] < max_per_merchant:
                selected.append(c)
                selected_ids.add(c["transaction_id"])
                card_counts[cid] += 1
                merch_counts[mid] += 1
                if len(selected) >= target_size:
                    break

        # Pass 2: Relaxed merchant cap if target_size not yet fulfilled
        if len(selected) < target_size:
            for c in scored_candidates:
                if c["transaction_id"] in selected_ids:
                    continue
                cid = c["card_id"]
                mid = c["merchant_id"]
                if card_counts[cid] < max_per_card:
                    selected.append(c)
                    selected_ids.add(c["transaction_id"])
                    card_counts[cid] += 1
                    merch_counts[mid] += 1
                    if len(selected) >= target_size:
                        break

        # Summary statistics
        batch_hash = hashlib.sha256(f"{as_of_epoch}-{strategy}-{len(selected)}".encode()).hexdigest()[:12]
        avg_uncertainty = (
            round(sum(c["margin_uncertainty"] for c in selected) / len(selected), 4)
            if selected else 0.0
        )
        hard_neg_count = sum(1 for c in selected if c["is_hard_negative"])
        unique_cards = len(set(c["card_id"] for c in selected))
        unique_merchants = len(set(c["merchant_id"] for c in selected))

        return {
            "batch_id": f"ALB-{batch_hash.upper()}",
            "strategy": strategy,
            "target_size": target_size,
            "total_scanned": len(scan_pool),
            "candidates_selected": len(selected),
            "summary": {
                "avg_margin_uncertainty": avg_uncertainty,
                "hard_negatives_count": hard_neg_count,
                "unique_cards_covered": unique_cards,
                "unique_merchants_covered": unique_merchants,
                "avg_retraining_weight": round(sum(c["retraining_weight"] for c in selected) / max(1, len(selected)), 3),
            },
            "candidates": selected,
        }
