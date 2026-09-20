"""
Graph Ingestion & In-Memory Indexed Store
Loads transactions, identity records, closed cases, and case pack into an
indexed graph representation supporting high-speed GSQL analytics (Q1-Q12)
with zero network latency and strict temporal (as_of) isolation.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import time
import pickle
import pandas as pd
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Set, Any, Optional

from src.graph.entity_resolution import build_device_profile_key, CardEntityResolver



class GraphStore:
    def __init__(self):
        # Core entities
        self.transactions: Dict[str, dict] = {}
        self.cards: Dict[str, dict] = {}
        self.customers: Dict[str, dict] = {}
        self.device_profiles: Dict[str, dict] = {}
        self.closed_cases: Dict[str, dict] = {}
        self.case_pack: Dict[str, dict] = {}

        # Graph indices (sorted by timestamp/epoch_s for temporal filtering)
        self.txns_by_card: Dict[str, List[dict]] = defaultdict(list)
        self.txns_by_customer: Dict[str, List[dict]] = defaultdict(list)
        self.txns_by_device: Dict[str, List[dict]] = defaultdict(list)
        self.cards_by_device: Dict[str, Set[str]] = defaultdict(set)
        self.devices_by_card: Dict[str, Set[str]] = defaultdict(set)
        self.cards_by_region: Dict[str, Set[str]] = defaultdict(set)
        self.regions_by_card: Dict[str, Set[str]] = defaultdict(set)
        
        # Memory & case indices
        self.cases_by_card: Dict[str, List[dict]] = defaultdict(list)
        self.cases_by_customer: Dict[str, List[dict]] = defaultdict(list)
        self.cases_by_device: Dict[str, List[dict]] = defaultdict(list)

        self.initialized = False

    def build_from_csv(
        self,
        transactions_path: str = "data/transactions.csv",
        identity_path: str = "data/identity.csv",
        closed_cases_path: str = "data/closed_cases_history.csv",
        case_pack_path: str = "data/case_pack.csv",
    ):
        print("Starting GraphStore ingestion...")
        t_start = time.time()

        # 1. Load Closed Cases
        print(f"Loading closed cases from {closed_cases_path}...")
        df_closed = pd.read_csv(closed_cases_path)
        closed_records = df_closed.to_dict(orient="records")
        for r in closed_records:
            cid = str(r["case_id"]).strip()
            self.closed_cases[cid] = r
            card_id = str(r["card_id"]).strip() if pd.notna(r.get("card_id")) else ""
            cust_id = str(r["customer_id"]).strip() if pd.notna(r.get("customer_id")) else ""
            if card_id:
                self.cases_by_card[card_id].append(r)
            if cust_id:
                self.cases_by_customer[cust_id].append(r)

        # 2. Load Case Pack
        print(f"Loading benchmark case pack from {case_pack_path}...")
        df_pack = pd.read_csv(case_pack_path)
        pack_records = df_pack.to_dict(orient="records")
        for r in pack_records:
            cid = str(r["case_id"]).strip()
            self.case_pack[cid] = r

        # 3. Load Identity records
        print(f"Loading identity records from {identity_path}...")
        df_id = pd.read_csv(identity_path)
        id_map: Dict[str, dict] = {}
        for r in df_id.to_dict(orient="records"):
            tid = str(r["TransactionID"]).strip()
            dev_profile = build_device_profile_key(
                device_info=r.get("DeviceInfo", ""),
                os=r.get("id_30", ""),
                browser=r.get("id_31", ""),
                screen=r.get("id_33", ""),
            )
            id_map[tid] = {
                "device_profile": dev_profile,
                "device_type": str(r.get("DeviceType", "")).strip(),
                "id_15": str(r.get("id_15", "")).strip(),
                "id_23": str(r.get("id_23", "")).strip(),
            }
            if dev_profile not in self.device_profiles:
                self.device_profiles[dev_profile] = {
                    "id": dev_profile,
                    "device_info": str(r.get("DeviceInfo", "")).strip(),
                    "device_type": str(r.get("DeviceType", "")).strip(),
                    "os": str(r.get("id_30", "")).strip(),
                    "browser": str(r.get("id_31", "")).strip(),
                    "screen": str(r.get("id_33", "")).strip(),
                    "proxy_status": str(r.get("id_23", "")).strip(),
                }

        # 4. Initialize Card Entity Resolver
        resolver = CardEntityResolver()

        # 5. Load Transactions
        print(f"Loading transactions from {transactions_path}...")
        cols = [
            "TransactionID", "TransactionDT", "TransactionAmt", "ProductCD",
            "card1", "card2", "card3", "card4", "card5", "card6",
            "addr1", "addr2", "P_emaildomain", "R_emaildomain",
            "customer_id", "ts", "channel", "risk_score"
        ]
        df_txns = pd.read_csv(transactions_path, usecols=cols)
        
        # Convert timestamps to epoch seconds for fast comparison
        df_txns["epoch_s"] = pd.to_datetime(df_txns["ts"]).astype("int64") // 10**9
        
        # Train card resolver with sample
        print("Training card entity resolver...")
        sample_txns = df_txns.head(50000).to_dict(orient="records")
        resolver.train_from_history(closed_records, pack_records, sample_txns)

        # Ingest transactions
        print("Building graph indices over transactions...")
        records = df_txns.to_dict(orient="records")
        for r in records:
            tid = str(r["TransactionID"]).strip()
            cust_id = str(r["customer_id"]).strip()
            
            card_attrs = (
                str(r.get("card1", "")).strip(),
                str(r.get("card2", "")).strip(),
                str(r.get("card3", "")).strip(),
                str(r.get("card4", "")).strip(),
                str(r.get("card5", "")).strip(),
                str(r.get("card6", "")).strip(),
            )
            card_id = resolver.resolve_card_id(tid, cust_id, card_attrs)

            id_info = id_map.get(tid, {})
            dev_profile = id_info.get("device_profile", "None | None | None | None")
            
            addr1 = str(r.get("addr1", "")).strip() if pd.notna(r.get("addr1")) else ""
            addr2 = str(r.get("addr2", "")).strip() if pd.notna(r.get("addr2")) else ""
            p_email = str(r.get("P_emaildomain", "")).strip() if pd.notna(r.get("P_emaildomain")) else ""
            r_email = str(r.get("R_emaildomain", "")).strip() if pd.notna(r.get("R_emaildomain")) else ""
            amount = float(r["TransactionAmt"]) if pd.notna(r.get("TransactionAmt")) else 0.0
            risk_score = float(r["risk_score"]) if pd.notna(r.get("risk_score")) else 0.0

            txn_obj = {
                "TransactionID": tid,
                "customer_id": cust_id,
                "card_id": card_id,
                "amount": amount,
                "ts": str(r["ts"]).strip(),
                "epoch_s": int(r["epoch_s"]),
                "product_code": str(r.get("ProductCD", "")).strip(),
                "channel": str(r.get("channel", "")).strip(),
                "risk_score": risk_score,
                "addr1": addr1,
                "addr2": addr2,
                "p_email": p_email,
                "r_email": r_email,
                "device_profile": dev_profile,
                "device_type": id_info.get("device_type", ""),
                "id_15": id_info.get("id_15", ""),
                "id_23": id_info.get("id_23", ""),
                "card_network": str(r.get("card4", "")).strip(),
                "card_type": str(r.get("card6", "")).strip(),
                "card1": str(r.get("card1", "")).strip(),
            }

            self.transactions[tid] = txn_obj
            self.txns_by_card[card_id].append(txn_obj)
            self.txns_by_customer[cust_id].append(txn_obj)
            
            if dev_profile and dev_profile != "None | None | None | None":
                self.txns_by_device[dev_profile].append(txn_obj)
                self.cards_by_device[dev_profile].add(card_id)
                self.devices_by_card[card_id].add(dev_profile)

            if addr1:
                self.cards_by_region[addr1].add(card_id)
                self.regions_by_card[card_id].add(addr1)

            if card_id not in self.cards:
                self.cards[card_id] = {
                    "card_id": card_id,
                    "customer_id": cust_id,
                    "card_network": txn_obj["card_network"],
                    "card_type": txn_obj["card_type"],
                    "card1": txn_obj["card1"],
                }

            if cust_id not in self.customers:
                self.customers[cust_id] = {
                    "customer_id": cust_id,
                }

        # Index closed cases by device profiles
        for cid, case_data in self.closed_cases.items():
            txns = str(case_data.get("txn_ids", "")).split("|")
            for t in txns:
                t = t.strip()
                if t in self.transactions:
                    dev = self.transactions[t]["device_profile"]
                    if dev and dev != "None | None | None | None":
                        self.cases_by_device[dev].append(case_data)

        # Sort all lists by epoch_s for fast temporal slicing
        print("Sorting temporal transaction indices...")
        for card_id in self.txns_by_card:
            self.txns_by_card[card_id].sort(key=lambda x: x["epoch_s"])
        for cust_id in self.txns_by_customer:
            self.txns_by_customer[cust_id].sort(key=lambda x: x["epoch_s"])
        for dev_profile in self.txns_by_device:
            self.txns_by_device[dev_profile].sort(key=lambda x: x["epoch_s"])

        self.initialized = True
        print(f"GraphStore initialized successfully in {time.time() - t_start:.2f}s!")
        print(f"Loaded {len(self.transactions)} transactions, {len(self.cards)} cards, {len(self.customers)} customers, {len(self.device_profiles)} device profiles.")

    def save_cache(self, cache_path: str = "data/graph_cache.pkl"):
        print(f"Saving GraphStore cache to {cache_path}...")
        with open(cache_path, "wb") as f:
            pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"GraphStore cache saved ({os.path.getsize(cache_path) / (1024*1024):.1f} MB).")

    @classmethod
    def load_cache_or_build(cls, cache_path: str = "data/graph_cache.pkl") -> "GraphStore":
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            print(f"Loading GraphStore from cache: {cache_path}...")
            t0 = time.time()
            try:
                class CustomUnpickler(pickle.Unpickler):
                    def find_class(self, module, name):
                        if module == "__main__" and name == "GraphStore":
                            return GraphStore
                        if module == "__main__" and name == "CardEntityResolver":
                            return CardEntityResolver
                        return super().find_class(module, name)

                with open(cache_path, "rb") as f:
                    store = CustomUnpickler(f).load()
                print(f"GraphStore loaded from cache in {time.time() - t0:.2f}s!")
                return store
            except Exception as e:
                print(f"Cache load error ({e}). Rebuilding store from CSV...")
                store = cls()
                store.build_from_csv()
                store.save_cache(cache_path)
                return store
        else:
            store = cls()
            store.build_from_csv()
            store.save_cache(cache_path)
            return store



if __name__ == "__main__":
    store = GraphStore.load_cache_or_build()
