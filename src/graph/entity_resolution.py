"""
Entity Resolution Module
Constructs consistent DeviceProfile composite keys, resolves customer cards,
and normalizes graph vertex IDs.
"""

from typing import Dict, Tuple, Optional, Any
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
