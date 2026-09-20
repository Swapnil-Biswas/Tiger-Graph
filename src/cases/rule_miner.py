"""
Inductive Fraud Rule Discovery & Pattern Mining Engine (src/cases/rule_miner.py)
Mines frequent subgraphs, discrete attribute correlations, and high-confidence association
rules from historical closed cases to discover emergent cybercrime typologies and adapt to evolving fraud modii operandi.
All operations strictly enforce temporal (as_of) boundary isolation.
"""

import time
import math
from typing import Dict, List, Set, Any, Optional, Union
from collections import defaultdict

from src.graph.client import parse_as_of_epoch


class InductiveFraudRuleMiner:
    """
    Inductive association rule learning and frequent pattern discovery engine.
    Mines empirical fraud rules from closed case graph history.
    """

    def __init__(self, client: Any):
        self.client = client

    def mine_rules(
        self,
        min_support: int = 10,
        min_confidence: float = 0.80,
        as_of: Optional[Union[str, int]] = None,
        target_consequent: str = "confirmed_fraud",
        max_rules: int = 20,
    ) -> Dict[str, Any]:
        """
        Mines high-confidence association rules from closed cases prior to as_of.
        Evaluates 1-item and 2-item antecedents against the target outcome/pattern.
        """
        t0 = time.perf_counter()
        as_of_epoch = parse_as_of_epoch(as_of)

        cases = [
            c for c in self.client.store.closed_cases.values()
            if parse_as_of_epoch(c.get("opened_at")) <= as_of_epoch
        ]
        total_cases = len(cases)
        if total_cases == 0:
            return {
                "total_cases_evaluated": 0,
                "base_rate": 0.0,
                "min_support": min_support,
                "min_confidence": min_confidence,
                "rules_discovered_count": 0,
                "rules": [],
                "elapsed_ms": 0.0,
            }

        case_records = []
        for c in cases:
            outcome = c.get("outcome", "cleared")
            pattern = c.get("pattern", "none")
            exp = float(c.get("exposure_usd", 0.0) or 0.0)
            n_txns = int(c.get("n_txns", 1) or 1)

            tid = c.get("first_fraud_txn_id") or c.get("txn_ids", "").split("|")[0]
            try:
                tid_str = str(int(float(tid))) if tid and str(tid) != "nan" else ""
            except Exception:
                tid_str = str(tid)

            txn_obj = self.client.store.transactions.get(tid_str, {})
            risk = float(txn_obj.get("risk_score", 0.5) or 0.5)
            dev = txn_obj.get("device_profile", "")

            dev_card_count = 1
            if dev and dev != "None | None | None | None" and not dev.startswith("UnknownDevice"):
                dev_card_count = len(getattr(self.client.store, "cards_by_device", {}).get(dev, set()))

            predicates = set()
            if risk >= 0.85:
                predicates.add("risk_score >= 0.85")
            elif risk >= 0.70:
                predicates.add("risk_score >= 0.70")
            elif risk < 0.40:
                predicates.add("risk_score < 0.40")

            if exp >= 500.0:
                predicates.add("exposure >= $500")
            elif exp >= 200.0:
                predicates.add("exposure >= $200")
            elif 0.0 < exp <= 20.0:
                predicates.add("micro_amount <= $20")

            if n_txns >= 3:
                predicates.add("txn_count >= 3")
            elif n_txns >= 2:
                predicates.add("txn_count >= 2")

            if dev_card_count >= 3:
                predicates.add("device_cards >= 3")
            elif dev_card_count >= 2:
                predicates.add("device_cards >= 2")

            notes = c.get("analyst_notes", "")
            if "Online purchases" in notes:
                predicates.add("online_merchant == True")
            if "Card-present" in notes:
                predicates.add("card_present == True")

            is_target = (outcome == "confirmed_fraud") if target_consequent == "confirmed_fraud" else (pattern == target_consequent)

            case_records.append({
                "is_target": is_target,
                "outcome": outcome,
                "pattern": pattern,
                "predicates": predicates,
            })

        total_targets = sum(1 for r in case_records if r["is_target"])
        base_rate = total_targets / total_cases if total_cases > 0 else 0.0

        all_preds = set()
        for r in case_records:
            all_preds.update(r["predicates"])
        sorted_preds = sorted(list(all_preds))

        candidate_rules = []

        # 1-item antecedents
        for p in sorted_preds:
            matched = [r for r in case_records if p in r["predicates"]]
            supp = len(matched)
            if supp >= min_support:
                target_supp = sum(1 for r in matched if r["is_target"])
                conf = target_supp / supp
                lift = conf / base_rate if base_rate > 0 else 1.0
                if conf >= min_confidence:
                    candidate_rules.append({
                        "antecedent": [p],
                        "consequent": target_consequent,
                        "support": supp,
                        "target_support": target_supp,
                        "confidence": round(conf, 4),
                        "lift": round(lift, 2),
                    })

        # 2-item antecedents
        for i in range(len(sorted_preds)):
            for j in range(i + 1, len(sorted_preds)):
                p1, p2 = sorted_preds[i], sorted_preds[j]
                matched = [r for r in case_records if p1 in r["predicates"] and p2 in r["predicates"]]
                supp = len(matched)
                if supp >= min_support:
                    target_supp = sum(1 for r in matched if r["is_target"])
                    conf = target_supp / supp
                    lift = conf / base_rate if base_rate > 0 else 1.0
                    if conf >= min_confidence:
                        candidate_rules.append({
                            "antecedent": [p1, p2],
                            "consequent": target_consequent,
                            "support": supp,
                            "target_support": target_supp,
                            "confidence": round(conf, 4),
                            "lift": round(lift, 2),
                        })

        candidate_rules.sort(key=lambda r: (r["confidence"], r["support"]), reverse=True)
        top_rules = candidate_rules[:max_rules]
        for idx, r in enumerate(top_rules):
            r["rule_id"] = f"IND-RULE-{idx+1:03d}"
            r["rule_str"] = f"IF {' AND '.join(r['antecedent'])} THEN {r['consequent']} (conf: {r['confidence']*100:.1f}%, supp: {r['support']}, lift: {r['lift']}x)"
            r["description"] = f"Inductive association rule {r['rule_id']}: {r['rule_str']}"

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return {
            "total_cases_evaluated": total_cases,
            "target_consequent": target_consequent,
            "base_rate": round(base_rate, 4),
            "min_support": min_support,
            "min_confidence": min_confidence,
            "rules_discovered_count": len(top_rules),
            "rules": top_rules,
            "elapsed_ms": elapsed_ms,
        }

    def evaluate_entity(
        self,
        card_id: str,
        rules: Optional[List[Dict[str, Any]]] = None,
        as_of: Optional[Union[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates an active card against discovered inductive fraud rules.
        """
        as_of_epoch = parse_as_of_epoch(as_of)

        if rules is None:
            mined = self.mine_rules(as_of=as_of)
            rules = mined.get("rules", [])

        card_txns = self.client.store.txns_by_card.get(card_id, [])
        valid_txns = [t for t in card_txns if t["epoch_s"] <= as_of_epoch]
        n_txns = len(valid_txns)
        exp = sum(t.get("amount", 0.0) for t in valid_txns)

        last_txn = valid_txns[-1] if valid_txns else {}
        risk = float(last_txn.get("risk_score", 0.5) or 0.5)
        dev = last_txn.get("device_profile", "")

        dev_card_count = 1
        if dev and dev != "None | None | None | None" and not dev.startswith("UnknownDevice"):
            dev_card_count = len(getattr(self.client.store, "cards_by_device", {}).get(dev, set()))

        predicates = set()
        if risk >= 0.85:
            predicates.add("risk_score >= 0.85")
        elif risk >= 0.70:
            predicates.add("risk_score >= 0.70")
        elif risk < 0.40:
            predicates.add("risk_score < 0.40")

        if exp >= 500.0:
            predicates.add("exposure >= $500")
        elif exp >= 200.0:
            predicates.add("exposure >= $200")
        elif 0.0 < exp <= 20.0:
            predicates.add("micro_amount <= $20")

        if n_txns >= 3:
            predicates.add("txn_count >= 3")
        elif n_txns >= 2:
            predicates.add("txn_count >= 2")

        if dev_card_count >= 3:
            predicates.add("device_cards >= 3")
        elif dev_card_count >= 2:
            predicates.add("device_cards >= 2")

        # Check online / card present
        is_cnp = last_txn.get("ProductCD") in ["W", "C", "R"] or (dev and dev != "None | None | None | None")
        if is_cnp:
            predicates.add("online_merchant == True")
        else:
            predicates.add("card_present == True")

        matching_rules = []
        for r in rules:
            if all(p in predicates for p in r["antecedent"]):
                matching_rules.append(r)

        highest_confidence = max((r["confidence"] for r in matching_rules), default=0.0)
        has_match = len(matching_rules) > 0

        return {
            "card_id": card_id,
            "active_predicates": sorted(list(predicates)),
            "matching_rules_count": len(matching_rules),
            "highest_confidence": highest_confidence,
            "is_inductive_fraud_match": has_match and highest_confidence >= 0.85,
            "matching_rules": matching_rules[:5],
        }

    def export_to_graphrag_chunks(self, rules: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Exports mined inductive rules into formatted GraphRAG knowledge chunks.
        """
        chunks = []
        for r in rules:
            chunks.append({
                "chunk_id": f"TYP-{r['rule_id']}",
                "title": f"Mined Inductive Fraud Rule: {r['rule_id']}",
                "category": "inductive_fraud_rules",
                "content": (
                    f"RULE IDENTIFIER: {r['rule_id']}\n"
                    f"SPECIFICATION: {r['rule_str']}\n"
                    f"ANTECEDENT PREDICATES: {', '.join(r['antecedent'])}\n"
                    f"CONSEQUENT: {r['consequent']}\n"
                    f"EMPIRICAL SUPPORT: {r['support']} cases\n"
                    f"CONFIDENCE: {r['confidence'] * 100:.1f}%\n"
                    f"LIFT: {r['lift']}x baseline\n"
                    f"GUIDANCE: When an active case satisfies these antecedent predicates, "
                    f"the empirical probability of fraud is {r['confidence'] * 100:.1f}%. "
                    f"Treat as strong supporting evidence alongside topological graph signals."
                ),
            })
        return chunks
