"""
Entity Resolution Module
Constructs consistent DeviceProfile composite keys, resolves customer cards,
and normalizes graph vertex IDs.
"""

import math
from typing import Dict, Tuple, Optional, Any, List, Set, Union
from collections import defaultdict
import pandas as pd


def build_device_profile_key(
    device_info: str = "",
    os: str = "",
    browser: str = "",
    screen: str = "",
) -> str:
    """
    Constructs the canonical composite device profile key:
    'DeviceInfo | OS | browser | screen'
    matching the format in README_dataset.md.
    """
    parts = [
        str(device_info).strip() if pd.notna(device_info) and str(device_info).strip() else "UnknownDevice",
        str(os).strip() if pd.notna(os) and str(os).strip() else "UnknownOS",
        str(browser).strip() if pd.notna(browser) and str(browser).strip() else "UnknownBrowser",
        str(screen).strip() if pd.notna(screen) and str(screen).strip() else "UnknownScreen",
    ]
    return " | ".join(parts)


class CardEntityResolver:
    """
    Resolves card_id for transactions using known mappings from closed_cases_history
    and case_pack, falling back to customer card-attribute clustering.
    """

    def __init__(self):
        self.txn_to_card: Dict[str, str] = {}
        self.cust_card_signatures: Dict[str, Dict[Tuple, str]] = {}
        self.cust_default_card: Dict[str, str] = {}

    def train_from_history(self, closed_cases: list[dict], case_pack: list[dict], transactions_sample: list[dict]):
        """
        Seeds card signatures from ground truth cases.
        """
        # Map known transaction IDs directly
        for c in closed_cases:
            card_id = c.get("card_id")
            if not card_id:
                continue
            txns = str(c.get("txn_ids", "")).split("|")
            for t in txns:
                t = t.strip()
                if t:
                    self.txn_to_card[t] = card_id

        for c in case_pack:
            card_id = c.get("card_id")
            flagged = str(c.get("flagged_txn_id", "")).strip()
            if card_id and flagged:
                self.txn_to_card[flagged] = card_id

        # Associate customer card attributes
        for r in transactions_sample:
            tid = str(r.get("TransactionID", "")).strip()
            cid = str(r.get("customer_id", "")).strip()
            if not cid:
                continue

            card_tuple = (
                str(r.get("card1", "")).strip(),
                str(r.get("card2", "")).strip(),
                str(r.get("card3", "")).strip(),
                str(r.get("card4", "")).strip(),
                str(r.get("card5", "")).strip(),
                str(r.get("card6", "")).strip(),
            )

            if cid not in self.cust_card_signatures:
                self.cust_card_signatures[cid] = {}

            if tid in self.txn_to_card:
                assigned_card = self.txn_to_card[tid]
                self.cust_card_signatures[cid][card_tuple] = assigned_card
                if cid not in self.cust_default_card:
                    self.cust_default_card[cid] = assigned_card

    def resolve_card_id(self, txn_id: str, customer_id: str, card_attrs: Tuple[str, ...]) -> str:
        """
        Returns the resolved card_id (e.g. 'C00259-K1').
        """
        tid = str(txn_id).strip()
        if tid in self.txn_to_card:
            return self.txn_to_card[tid]

        cid = str(customer_id).strip()
        if cid in self.cust_card_signatures:
            sig_map = self.cust_card_signatures[cid]
            if card_attrs in sig_map:
                return sig_map[card_attrs]
            # Match on card1
            c1 = card_attrs[0] if len(card_attrs) > 0 else ""
            for sig, card_id in sig_map.items():
                if sig[0] == c1:
                    return card_id

        if cid in self.cust_default_card:
            return self.cust_default_card[cid]

        # Default standard format
        return f"{cid}-K1"


def jaro_similarity(s1: str, s2: str) -> float:
    s1 = str(s1 or "").strip().lower()
    s2 = str(s2 or "").strip().lower()
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j]:
                continue
            if s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    t = transpositions // 2
    return (matches / len1 + matches / len2 + (matches - t) / matches) / 3.0


def jaro_winkler_similarity(s1: str, s2: str, prefix_weight: float = 0.1) -> float:
    j_sim = jaro_similarity(s1, s2)
    s1_l = str(s1 or "").strip().lower()
    s2_l = str(s2 or "").strip().lower()
    prefix_len = 0
    for c1, c2 in zip(s1_l[:4], s2_l[:4]):
        if c1 == c2:
            prefix_len += 1
        else:
            break
    return round(j_sim + prefix_len * prefix_weight * (1.0 - j_sim), 4)


def parse_device_profile_key(key: str) -> dict:
    parts = [p.strip() for p in str(key or "").split("|")]
    return {
        "device_info": parts[0] if len(parts) > 0 and parts[0] != "UnknownDevice" else "",
        "os": parts[1] if len(parts) > 1 and parts[1] != "UnknownOS" else "",
        "browser": parts[2] if len(parts) > 2 and parts[2] != "UnknownBrowser" else "",
        "screen": parts[3] if len(parts) > 3 and parts[3] != "UnknownScreen" else "",
    }


class ProbabilisticEntityResolver:
    """
    Probabilistic Record Linkage & Noisy Profile Disambiguation Engine (Q23).
    Implements Fellegi-Sunter log-likelihood linkage and Jaro-Winkler string similarity
    across heterogeneous attributes (device model, browser, OS, screen, email prefix/domain,
    IP subnet, billing address) with candidate blocking for sub-millisecond execution.
    """

    FELLEGI_SUNTER_PARAMS = {
        "device_model": {"m": 0.95, "u": 0.03, "threshold": 0.85},
        "os_platform": {"m": 0.90, "u": 0.10, "threshold": 0.85},
        "browser": {"m": 0.88, "u": 0.08, "threshold": 0.80},
        "screen_res": {"m": 0.85, "u": 0.12, "threshold": 1.0},
        "email_domain": {"m": 0.80, "u": 0.25, "threshold": 1.0},
        "email_prefix": {"m": 0.96, "u": 0.005, "threshold": 0.85},
        "ip_subnet": {"m": 0.90, "u": 0.02, "threshold": 1.0},
        "billing_addr": {"m": 0.92, "u": 0.03, "threshold": 1.0},
    }

    def __init__(self, client=None):
        self.client = client
        # Precomputed Fellegi-Sunter weights
        self.weights = {}
        for attr, p in self.FELLEGI_SUNTER_PARAMS.items():
            m, u = p["m"], p["u"]
            w_agree = math.log2(m / u)
            w_disagree = math.log2((1.0 - m) / (1.0 - u))
            self.weights[attr] = {
                "agree": w_agree,
                "disagree": w_disagree,
                "threshold": p["threshold"],
            }

        # Lazy blocking index for device profiles
        self._device_index_built = False
        self._device_prefix_index: Dict[str, Set[str]] = defaultdict(set)
        self._screen_index: Dict[str, Set[str]] = defaultdict(set)

    def _ensure_device_index(self):
        if self._device_index_built or not self.client or not hasattr(self.client, "store"):
            return
        for dev_key in self.client.store.device_profiles.keys():
            parsed = parse_device_profile_key(dev_key)
            d_info = parsed.get("device_info", "")
            if d_info:
                prefix = d_info.split()[0].lower() if d_info.split() else d_info.lower()
                self._device_prefix_index[prefix].add(dev_key)
            screen = parsed.get("screen", "")
            if screen:
                self._screen_index[screen].add(dev_key)
        self._device_index_built = True

    def compare_profiles(self, profile_a: dict, profile_b: dict) -> dict:
        """
        Compares two entity profiles using Fellegi-Sunter log-likelihood weights
        and Jaro-Winkler similarity.
        """
        breakdown = {}
        composite_weight = 0.0
        compared_count = 0

        # Mapping of input keys to attribute categories
        attr_mapping = [
            ("device_model", ["device_model", "device_info", "device", "DeviceInfo"]),
            ("os_platform", ["os_platform", "os", "id_30"]),
            ("browser", ["browser", "id_31"]),
            ("screen_res", ["screen_res", "screen", "id_33"]),
            ("email_domain", ["email_domain", "P_emaildomain", "R_emaildomain"]),
            ("email_prefix", ["email_prefix", "email", "handle"]),
            ("ip_subnet", ["ip_subnet", "ip", "subnet"]),
            ("billing_addr", ["billing_addr", "addr1", "address"]),
        ]

        for attr, keys in attr_mapping:
            val_a = None
            for k in keys:
                if k in profile_a and profile_a[k] is not None and str(profile_a[k]).strip() != "":
                    val_a = str(profile_a[k]).strip()
                    break

            val_b = None
            for k in keys:
                if k in profile_b and profile_b[k] is not None and str(profile_b[k]).strip() != "":
                    val_b = str(profile_b[k]).strip()
                    break

            if val_a is None or val_b is None:
                continue

            param = self.weights[attr]
            w_agree = param["agree"]
            w_disagree = param["disagree"]
            threshold = param["threshold"]

            if threshold >= 1.0:
                # Exact categorical match
                sim = 1.0 if val_a.lower() == val_b.lower() else 0.0
                gamma = 1.0 if sim == 1.0 else 0.0
            else:
                sim = jaro_winkler_similarity(val_a, val_b)
                lower_bound = max(0.60, threshold - 0.15)
                if sim >= threshold:
                    gamma = 1.0
                elif sim <= lower_bound:
                    gamma = 0.0
                else:
                    gamma = (sim - lower_bound) / (threshold - lower_bound)

            contrib = gamma * w_agree + (1.0 - gamma) * w_disagree
            composite_weight += contrib
            compared_count += 1

            breakdown[attr] = {
                "val_a": val_a,
                "val_b": val_b,
                "similarity": round(sim, 4),
                "gamma": round(gamma, 4),
                "contribution_weight": round(contrib, 4),
            }

        # Compute posterior match probability via sigmoid of log-likelihood ratio
        match_prob = round(1.0 / (1.0 + 2.0 ** (-composite_weight)), 4)

        if match_prob >= 0.85:
            verdict = "CONFIRMED_MATCH"
            link_type = "RESOLVED_IDENTITY_LINK"
            action = "MERGE_ENTITY_CLUSTER"
        elif match_prob >= 0.65:
            verdict = "PROBABLE_SYBIL"
            link_type = "SUSPECTED_SYBIL_LINK"
            action = "STEP_UP_AUTH_AND_EDD"
        else:
            verdict = "DISTINCT"
            link_type = "NONE"
            action = "MAINTAIN_SEPARATION"

        return {
            "match_probability": match_prob,
            "composite_weight": round(composite_weight, 4),
            "attributes_compared": compared_count,
            "attribute_breakdown": breakdown,
            "verdict": verdict,
            "link_type": link_type,
            "recommended_action": action,
        }

    def resolve_device_nexus(
        self,
        device_key: str,
        as_of: Optional[Union[str, int]] = None,
        similarity_threshold: float = 0.75,
        max_candidates: int = 50,
    ) -> dict:
        """
        Resolves fuzzy near-duplicate device profiles across the graph using candidate blocking.
        """
        from src.graph.client import parse_as_of_epoch
        as_of_epoch = parse_as_of_epoch(as_of)
        self._ensure_device_index()

        src_parsed = parse_device_profile_key(device_key)
        d_info = src_parsed.get("device_info", "")
        prefix = d_info.split()[0].lower() if d_info.split() else d_info.lower()
        screen = src_parsed.get("screen", "")

        # Candidate blocking: prioritize candidates sharing device prefix, then screen
        prefix_candidates = set()
        if prefix and prefix in self._device_prefix_index:
            prefix_candidates.update(self._device_prefix_index[prefix])

        screen_candidates = set()
        if screen and screen in self._screen_index:
            screen_candidates.update(self._screen_index[screen])

        if not prefix_candidates and not screen_candidates and self.client and hasattr(self.client, "store"):
            ordered_candidates = list(self.client.store.device_profiles.keys())
        else:
            ordered_candidates = list(prefix_candidates) + list(screen_candidates - prefix_candidates)

        # Exclude self
        ordered_candidates = [c for c in ordered_candidates if c != device_key]

        resolved_links = []
        sybil_cards = set()

        for cand_key in ordered_candidates[:max_candidates]:
            cand_parsed = parse_device_profile_key(cand_key)
            comp = self.compare_profiles(src_parsed, cand_parsed)
            if comp["match_probability"] >= similarity_threshold:
                # Find cards linked to candidate device
                cand_cards = set()
                if self.client and hasattr(self.client, "store"):
                    for c in self.client.store.cards_by_device.get(cand_key, set()):
                        # Check temporal activity
                        txns = self.client.store.txns_by_card.get(c, [])
                        if any(t.get("epoch_s", 0) <= as_of_epoch for t in txns) or not txns:
                            cand_cards.add(c)
                sybil_cards.update(cand_cards)
                resolved_links.append({
                    "target_device": cand_key,
                    "match_probability": comp["match_probability"],
                    "link_type": comp["link_type"],
                    "verdict": comp["verdict"],
                    "linked_cards": sorted(list(cand_cards)),
                    "recommended_action": comp["recommended_action"],
                })

        resolved_links.sort(key=lambda x: x["match_probability"], reverse=True)
        sybil_risk_score = min(1.0, round(0.35 * len(resolved_links) + 0.20 * len(sybil_cards), 4))

        return {
            "source_device": device_key,
            "as_of": as_of,
            "similarity_threshold": similarity_threshold,
            "candidates_evaluated": len(ordered_candidates),
            "resolved_links_count": len(resolved_links),
            "resolved_links": resolved_links,
            "sybil_cards_count": len(sybil_cards),
            "sybil_cards": sorted(list(sybil_cards)),
            "sybil_risk_score": sybil_risk_score,
            "threat_level": "critical" if sybil_risk_score >= 0.70 else "high" if sybil_risk_score >= 0.40 else "elevated" if sybil_risk_score >= 0.20 else "low" if sybil_risk_score > 0.0 else "none",
        }

    def resolve_cardholder_sybils(
        self,
        card_id: str,
        as_of: Optional[Union[str, int]] = None,
    ) -> dict:
        """
        Discovers hidden sybil and synthetic identity cards linked to card_id via
        probabilistic device and profile linkage.
        """
        card_devices = set()
        if self.client and hasattr(self.client, "store"):
            card_devices = self.client.store.devices_by_card.get(card_id, set())

        all_sybil_cards = set()
        matched_devices = []

        for dev in sorted(list(card_devices)):
            res = self.resolve_device_nexus(dev, as_of=as_of, similarity_threshold=0.75)
            for link in res["resolved_links"]:
                matched_devices.append(link)
                for c in link["linked_cards"]:
                    if c != card_id:
                        all_sybil_cards.add(c)

        sybil_risk = min(1.0, round(0.35 * len(matched_devices) + 0.20 * len(all_sybil_cards), 4))
        threat = "critical" if sybil_risk >= 0.70 else "high" if sybil_risk >= 0.40 else "elevated" if sybil_risk >= 0.20 else "low" if sybil_risk > 0.0 else "none"

        return {
            "card_id": card_id,
            "as_of": as_of,
            "primary_devices_count": len(card_devices),
            "resolved_sybil_devices_count": len(matched_devices),
            "sybil_cards_count": len(all_sybil_cards),
            "sybil_cards": sorted(list(all_sybil_cards)),
            "sybil_risk_score": sybil_risk,
            "threat_level": threat,
            "recommended_action": "ENHANCED_DUE_DILIGENCE_AND_SYBIL_HOLD" if sybil_risk >= 0.40 else "STANDARD_MONITORING",
        }
