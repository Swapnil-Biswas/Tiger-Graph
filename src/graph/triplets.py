"""
Dynamic Knowledge Graph Triplet & Enterprise Graph Synchronizer (src/graph/triplets.py)
Extracts typed semantic knowledge graph triplets (Subject, Predicate, Object) with
temporal weights, schema attributes, and case provenance tracking.
Enables lossless external synchronization to enterprise TigerGraph clusters (GSQL DML),
Neo4j graph databases (Cypher MERGE), and semantic ontologies (W3C RDF N-Triples, JSON-LD).
"""

import json
import re
from typing import Dict, List, Set, Any, Optional, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from src.graph.client import parse_as_of_epoch


@dataclass
class KnowledgeTriplet:
    """
    Canonical semantic knowledge graph triplet representation.
    """
    subject: str                  # e.g., "CARD-10001" or "CUST-99"
    subject_type: str             # "Customer", "Card", "Transaction", "Device", "Merchant", "SyndicateNexus", "Case"
    predicate: str                # "OWNS_CARD", "HAS_TRANSACTION", "TRANS_AT", "USED_DEVICE", "IN_SYNDICATE", etc.
    object: str                   # e.g., "TXN-3044562"
    object_type: str              # "Transaction", "Device", ...
    properties: Dict[str, Any] = field(default_factory=dict)
    temporal_epoch: Optional[int] = None
    provenance_case: Optional[str] = None
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class KnowledgeGraphTripletExporter:
    """
    Extracts multi-hop incident subgraphs and converts them into standardized
    knowledge graph triplets and multi-dialect enterprise graph DML scripts.
    """

    def __init__(self, client: Any):
        self.client = client

    def extract_case_triplets(
        self,
        case_id: str,
        max_hops: int = 2,
        max_triplets: int = 150,
        as_of: Optional[Union[str, int]] = None,
    ) -> List[KnowledgeTriplet]:
        """
        Extracts semantic knowledge graph triplets for a case incident up to as_of.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        triplets: List[KnowledgeTriplet] = []
        seen_triplet_keys: Set[str] = set()

        # 1. Resolve case metadata from pack or store
        pack = getattr(self.client.store, "case_pack", {})
        closed = getattr(self.client.store, "closed_cases", {})
        case_obj = pack.get(case_id) or closed.get(case_id) or {}

        card_id = str(case_obj.get("card_id", ""))
        cust_id = str(case_obj.get("customer_id", ""))
        flagged_txn = str(case_obj.get("flagged_transaction_id", ""))

        if not card_id and flagged_txn:
            txn_meta = self.client.store.transactions.get(flagged_txn, {})
            card_id = str(txn_meta.get("card_id", ""))
            if not cust_id:
                cust_id = str(txn_meta.get("customer_id", ""))

        # Case vertex & edges
        case_node = f"CASE-{case_id}" if not case_id.startswith("CASE-") else case_id
        if card_id:
            card_node = f"CARD-{card_id}" if not card_id.startswith("CARD-") else card_id
            t = KnowledgeTriplet(
                subject=case_node,
                subject_type="Case",
                predicate="INVESTIGATES_CARD",
                object=card_node,
                object_type="Card",
                properties={"case_id": case_id, "priority": case_obj.get("priority", "HIGH")},
                temporal_epoch=as_of_epoch,
                provenance_case=case_id,
            )
            key = f"{t.subject}|{t.predicate}|{t.object}"
            seen_triplet_keys.add(key)
            triplets.append(t)

        if flagged_txn:
            txn_node = f"TXN-{flagged_txn}" if not flagged_txn.startswith("TXN-") else flagged_txn
            t = KnowledgeTriplet(
                subject=case_node,
                subject_type="Case",
                predicate="FLAGGED_TRANSACTION",
                object=txn_node,
                object_type="Transaction",
                properties={"case_id": case_id, "reason": case_obj.get("trigger_reason", "Suspicious Activity")},
                temporal_epoch=as_of_epoch,
                provenance_case=case_id,
            )
            key = f"{t.subject}|{t.predicate}|{t.object}"
            seen_triplet_keys.add(key)
            triplets.append(t)

        # 2. Extract card neighborhood
        if card_id:
            card_triplets = self.extract_card_triplets(
                card_id=card_id,
                max_hops=max_hops,
                max_triplets=max_triplets - len(triplets),
                as_of=as_of_epoch,
                provenance_case=case_id,
            )
            for ct in card_triplets:
                k = f"{ct.subject}|{ct.predicate}|{ct.object}"
                if k not in seen_triplet_keys:
                    seen_triplet_keys.add(k)
                    triplets.append(ct)
                    if len(triplets) >= max_triplets:
                        break

        # 3. Connect SyndicateNexus if active
        if hasattr(self.client.store, "graph_syndicates"):
            for nexus_id, nexus in self.client.store.graph_syndicates.items():
                member_cards = nexus.get("member_cards", set())
                member_cases = nexus.get("cases", set())
                if card_id in member_cards or case_id in member_cases:
                    nexus_node = f"NEXUS-{nexus_id}" if not str(nexus_id).startswith("NEXUS-") else str(nexus_id)
                    card_node = f"CARD-{card_id}" if not card_id.startswith("CARD-") else card_id
                    t = KnowledgeTriplet(
                        subject=card_node,
                        subject_type="Card",
                        predicate="IN_SYNDICATE",
                        object=nexus_node,
                        object_type="SyndicateNexus",
                        properties={
                            "exposure": float(nexus.get("total_exposure", 0.0)),
                            "threat_level": nexus.get("threat_level", "HIGH"),
                        },
                        temporal_epoch=as_of_epoch,
                        provenance_case=case_id,
                    )
                    k = f"{t.subject}|{t.predicate}|{t.object}"
                    if k not in seen_triplet_keys:
                        seen_triplet_keys.add(k)
                        triplets.append(t)

        return triplets

    def extract_card_triplets(
        self,
        card_id: str,
        max_hops: int = 2,
        max_triplets: int = 150,
        as_of: Optional[Union[str, int]] = None,
        provenance_case: Optional[str] = None,
    ) -> List[KnowledgeTriplet]:
        """
        Extracts multi-hop semantic triplets centered around a payment card.
        """
        as_of_epoch = parse_as_of_epoch(as_of)
        triplets: List[KnowledgeTriplet] = []
        seen_keys: Set[str] = set()

        card_node = f"CARD-{card_id}" if not card_id.startswith("CARD-") else card_id

        # 1. Transactions on Card
        all_txns = self.client.store.txns_by_card.get(card_id, [])
        txns = [t for t in all_txns if t.get("epoch_s", 0) <= as_of_epoch]
        txns.sort(key=lambda x: x.get("epoch_s", 0), reverse=True)
        txns = txns[:30]  # Limit recent transactions for bounded export

        cust_id = None

        for t in txns:
            tid = str(t.get("TransactionID", ""))
            txn_node = f"TXN-{tid}" if not tid.startswith("TXN-") else tid
            amount = float(t.get("amount", 0.0))
            epoch = int(t.get("epoch_s", 0))
            is_fraud = int(t.get("is_fraud", 0))

            # Edge: Card -> HAS_TRANSACTION -> Transaction
            trip1 = KnowledgeTriplet(
                subject=card_node,
                subject_type="Card",
                predicate="HAS_TRANSACTION",
                object=txn_node,
                object_type="Transaction",
                properties={"amount": amount, "epoch_s": epoch, "is_fraud": is_fraud},
                temporal_epoch=epoch,
                provenance_case=provenance_case,
                weight=amount,
            )
            k1 = f"{trip1.subject}|{trip1.predicate}|{trip1.object}"
            if k1 not in seen_keys:
                seen_keys.add(k1)
                triplets.append(trip1)

            # Edge: Transaction -> TRANS_AT -> Merchant
            merch = t.get("merchant_id") or t.get("merchant_name")
            if merch:
                merch_node = f"MERCH-{merch}" if not str(merch).startswith("MERCH-") else str(merch)
                trip2 = KnowledgeTriplet(
                    subject=txn_node,
                    subject_type="Transaction",
                    predicate="TRANS_AT",
                    object=merch_node,
                    object_type="Merchant",
                    properties={"amount": amount, "mcc": str(t.get("mcc", "5311"))},
                    temporal_epoch=epoch,
                    provenance_case=provenance_case,
                    weight=amount,
                )
                k2 = f"{trip2.subject}|{trip2.predicate}|{trip2.object}"
                if k2 not in seen_keys:
                    seen_keys.add(k2)
                    triplets.append(trip2)

            # Edge: Transaction -> USED_DEVICE -> Device
            dev = t.get("device_profile")
            if dev and dev != "None | None | None | None" and not dev.startswith("UnknownDevice"):
                # Clean device node ID
                dev_clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(dev))[:40]
                dev_node = f"DEV-{dev_clean}"
                trip3 = KnowledgeTriplet(
                    subject=txn_node,
                    subject_type="Transaction",
                    predicate="USED_DEVICE",
                    object=dev_node,
                    object_type="Device",
                    properties={"device_raw": str(dev)},
                    temporal_epoch=epoch,
                    provenance_case=provenance_case,
                )
                k3 = f"{trip3.subject}|{trip3.predicate}|{trip3.object}"
                if k3 not in seen_keys:
                    seen_keys.add(k3)
                    triplets.append(trip3)

            if not cust_id and t.get("customer_id"):
                cust_id = str(t.get("customer_id"))

            if len(triplets) >= max_triplets:
                break

        # Edge: Customer -> OWNS_CARD -> Card
        if cust_id:
            cust_node = f"CUST-{cust_id}" if not cust_id.startswith("CUST-") else cust_id
            trip_cust = KnowledgeTriplet(
                subject=cust_node,
                subject_type="Customer",
                predicate="OWNS_CARD",
                object=card_node,
                object_type="Card",
                properties={"card_id": card_id, "customer_id": cust_id},
                temporal_epoch=as_of_epoch,
                provenance_case=provenance_case,
            )
            k_cust = f"{trip_cust.subject}|{trip_cust.predicate}|{trip_cust.object}"
            if k_cust not in seen_keys:
                seen_keys.add(k_cust)
                triplets.append(trip_cust)

        return triplets

    # =========================================================================
    # Serialization Dialects (TigerGraph GSQL, Neo4j Cypher, RDF, JSON-LD)
    # =========================================================================

    def to_tigergraph_gsql(self, triplets: List[KnowledgeTriplet], graph_name: str = "FraudGraph") -> str:
        """
        Generates TigerGraph GSQL DML statements (USE GRAPH, vertex INSERT, edge INSERT).
        """
        lines = [
            f"// ========================================================",
            f"// TigerGraph GSQL DML Synchronization Script",
            f"// Target Graph: {graph_name} | Generated Triplets: {len(triplets)}",
            f"// ========================================================",
            f"USE GRAPH {graph_name}",
            "",
            "// --- VERTICES ---",
        ]

        inserted_vertices: Set[str] = set()

        def escape_val(v: Any) -> str:
            if isinstance(v, (int, float)):
                return str(v)
            val_str = str(v).replace('"', '\\"')
            return f'"{val_str}"'

        for t in triplets:
            if t.subject not in inserted_vertices:
                inserted_vertices.add(t.subject)
                lines.append(f'INSERT INTO {t.subject_type} (PRIMARY_ID) VALUES ({escape_val(t.subject)});')
            if t.object not in inserted_vertices:
                inserted_vertices.add(t.object)
                lines.append(f'INSERT INTO {t.object_type} (PRIMARY_ID) VALUES ({escape_val(t.object)});')

        lines.append("")
        lines.append("// --- EDGES ---")

        for t in triplets:
            edge_type = t.predicate
            # Format properties
            prop_keys = []
            prop_vals = []
            for pk, pv in t.properties.items():
                if isinstance(pv, (int, float, str)):
                    prop_keys.append(pk)
                    prop_vals.append(escape_val(pv))

            if prop_keys:
                keys_str = f"FROM, TO, {', '.join(prop_keys)}"
                vals_str = f"{escape_val(t.subject)}, {escape_val(t.object)}, {', '.join(prop_vals)}"
            else:
                keys_str = "FROM, TO"
                vals_str = f"{escape_val(t.subject)}, {escape_val(t.object)}"

            lines.append(f"INSERT INTO {edge_type} ({keys_str}) VALUES ({vals_str});")

        return "\n".join(lines)

    def to_neo4j_cypher(self, triplets: List[KnowledgeTriplet]) -> str:
        """
        Generates idempotent Neo4j Cypher statements using MERGE clauses.
        """
        lines = [
            "// ========================================================",
            f"// Neo4j Cypher Idempotent Synchronization Script ({len(triplets)} Triplets)",
            "// ========================================================",
        ]

        merged_nodes: Set[str] = set()

        for t in triplets:
            if t.subject not in merged_nodes:
                merged_nodes.add(t.subject)
                lines.append(f'MERGE (s:{t.subject_type} {{id: "{t.subject}"}});')
            if t.object not in merged_nodes:
                merged_nodes.add(t.object)
                lines.append(f'MERGE (o:{t.object_type} {{id: "{t.object}"}});')

            props_list = []
            for k, v in t.properties.items():
                if isinstance(v, (int, float)):
                    props_list.append(f"{k}: {v}")
                elif isinstance(v, str):
                    val_str = v.replace('"', '\\"')
                    props_list.append(f'{k}: "{val_str}"')

            prop_str = f" {{{', '.join(props_list)}}}" if props_list else ""

            lines.append(
                f'MATCH (s:{t.subject_type} {{id: "{t.subject}"}}), (o:{t.object_type} {{id: "{t.object}"}}) '
                f'MERGE (s)-[r:{t.predicate}{prop_str}]->(o);'
            )

        return "\n".join(lines)

    def to_rdf_ntriples(
        self,
        triplets: List[KnowledgeTriplet],
        base_uri: str = "https://fraud.tigergraph.bank/entity/",
        ontology_uri: str = "https://fraud.tigergraph.bank/ontology#",
    ) -> str:
        """
        Generates standard W3C RDF N-Triples (<subject> <predicate> <object> .).
        """
        lines = []

        def clean_uri(ident: str, type_str: str) -> str:
            clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(ident))
            return f"<{base_uri}{type_str.lower()}/{clean}>"

        for t in triplets:
            s_uri = clean_uri(t.subject, t.subject_type)
            p_uri = f"<{ontology_uri}{t.predicate}>"
            o_uri = clean_uri(t.object, t.object_type)
            lines.append(f"{s_uri} {p_uri} {o_uri} .")

        return "\n".join(lines)

    def to_jsonld(
        self,
        triplets: List[KnowledgeTriplet],
        base_uri: str = "https://fraud.tigergraph.bank/entity/",
        ontology_uri: str = "https://fraud.tigergraph.bank/ontology#",
    ) -> Dict[str, Any]:
        """
        Generates standard W3C JSON-LD graph with context mappings.
        """
        context = {
            "@vocab": ontology_uri,
            "entity": base_uri,
            "id": "@id",
            "type": "@type",
        }

        graph_nodes: Dict[str, Dict[str, Any]] = {}

        for t in triplets:
            s_id = f"{base_uri}{t.subject_type.lower()}/{t.subject}"
            o_id = f"{base_uri}{t.object_type.lower()}/{t.object}"

            if s_id not in graph_nodes:
                graph_nodes[s_id] = {
                    "@id": s_id,
                    "@type": t.subject_type,
                    "name": t.subject,
                }

            if o_id not in graph_nodes:
                graph_nodes[o_id] = {
                    "@id": o_id,
                    "@type": t.object_type,
                    "name": t.object,
                }

            # Add relation on subject
            pred_key = t.predicate
            if pred_key not in graph_nodes[s_id]:
                graph_nodes[s_id][pred_key] = []
            elif not isinstance(graph_nodes[s_id][pred_key], list):
                graph_nodes[s_id][pred_key] = [graph_nodes[s_id][pred_key]]

            rel_target = {"@id": o_id}
            if t.properties:
                rel_target["properties"] = t.properties
            graph_nodes[s_id][pred_key].append(rel_target)

        return {
            "@context": context,
            "@graph": list(graph_nodes.values()),
        }

    def export_export_bundle(
        self,
        case_id: str,
        max_hops: int = 2,
        max_triplets: int = 150,
        as_of: Optional[Union[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Returns a comprehensive synchronization bundle in all enterprise dialects.
        """
        triplets = self.extract_case_triplets(
            case_id=case_id,
            max_hops=max_hops,
            max_triplets=max_triplets,
            as_of=as_of,
        )

        unique_subjects = set(t.subject for t in triplets)
        unique_objects = set(t.object for t in triplets)
        all_nodes = unique_subjects | unique_objects

        pred_counts = defaultdict(int)
        for t in triplets:
            pred_counts[t.predicate] += 1

        return {
            "case_id": case_id,
            "total_triplets": len(triplets),
            "total_entities": len(all_nodes),
            "predicate_counts": dict(pred_counts),
            "triplets": [t.to_dict() for t in triplets],
            "gsql": self.to_tigergraph_gsql(triplets),
            "cypher": self.to_neo4j_cypher(triplets),
            "rdf_ntriples": self.to_rdf_ntriples(triplets),
            "jsonld": self.to_jsonld(triplets),
        }
