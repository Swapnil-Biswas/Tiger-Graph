"""
Case Management & Graph Persistence
Handles persisting cases, findings, evidence, and actions to the graph,
and reconstructing full case records directly from graph vertices and edges.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from src.graph.client import GraphClient


class CaseManager:
    def __init__(self, client: Optional[GraphClient] = None):
        self.client = client or GraphClient(mode="embedded")
        self.store = self.client.store
        
        # Dedicated graph tables for investigation entities
        if not hasattr(self.store, "graph_cases"):
            self.store.graph_cases = {}
            self.store.graph_findings = {}
            self.store.graph_evidence = {}
            self.store.graph_actions = {}
            self.store.graph_syndicates = {}
            self.store.graph_case_edges = []

    def write_case_to_graph(self, answer_bundle: Dict[str, Any]) -> str:
        """
        Writes the case, evidence, findings, and actions into graph vertices and edges.
        Returns the created graph_case_id.
        """
        case_id = answer_bundle["case_id"]
        c_data = answer_bundle["case"]
        graph_case_id = f"CASE-{case_id}"

        # 1. Create Case Vertex
        case_vertex = {
            "id": graph_case_id,
            "case_id": case_id,
            "status": c_data["status"],
            "verdict": c_data["verdict"],
            "fraud_probability": c_data["fraud_probability"],
            "pattern": c_data["pattern"],
            "pattern_description": c_data.get("pattern_description", ""),
            "exposure_usd": c_data["exposure_usd"],
            "first_suspicious_txn_id": c_data.get("first_suspicious_txn_id", ""),
            "summary": c_data["summary"],
            "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "evidence_ids": [],
            "action_ids": [],
            "finding_ids": [],
            "connected_cards": c_data.get("connected_card_ids", []),
            "similar_cases": c_data.get("similar_prior_cases", []),
            "affected_txns": c_data.get("affected_txn_ids", []),
        }

        # 2. Store Evidence Vertices
        for ev in c_data.get("evidence", []):
            ev_id = f"{graph_case_id}-{ev['id']}"
            self.store.graph_evidence[ev_id] = {
                "id": ev_id,
                "local_id": ev["id"],
                "source": ev["source"],
                "ref": ev["ref"],
                "claim": ev["claim"],
                "entity_ids": ev.get("entity_ids", []),
                "case_id": graph_case_id,
            }
            case_vertex["evidence_ids"].append(ev_id)

        # 3. Store Action Vertices
        final_actions = answer_bundle.get("next_best_actions", {}).get("final", [])
        for idx, act in enumerate(final_actions, 1):
            act_id = f"{graph_case_id}-ACT-{idx:02d}"
            self.store.graph_actions[act_id] = {
                "id": act_id,
                "action": act["action"],
                "route": act["route"],
                "reason": act["reason"],
                "case_id": graph_case_id,
            }
            case_vertex["action_ids"].append(act_id)

        # 4. Check for Syndicate Nexus (shared device profiles or multi-card rings)
        syndicate_id = None
        dev_profiles = c_data.get("connected_device_profiles", [])
        connected_cards = c_data.get("connected_card_ids", [])
        if dev_profiles or len(connected_cards) >= 2 or c_data.get("pattern") in ["undocumented", "ring"]:
            primary_ent = dev_profiles[0] if dev_profiles else (connected_cards[0] if connected_cards else case_id)
            n_type = "device_pooling_nexus" if dev_profiles else "multi_card_ring"
            syndicate_id = self.register_syndicate_nexus(
                nexus_type=n_type,
                primary_entity=primary_ent,
                member_case_id=graph_case_id,
                card_ids=connected_cards,
                exposure_usd=c_data.get("exposure_usd", 0.0),
            )
        case_vertex["syndicate_nexus_id"] = syndicate_id

        self.store.graph_cases[graph_case_id] = case_vertex
        return graph_case_id

    def register_syndicate_nexus(
        self,
        nexus_type: str,
        primary_entity: str,
        member_case_id: str,
        card_ids: List[str],
        exposure_usd: float,
    ) -> str:
        """
        Creates or updates a SyndicateNexus vertex in the graph, linking member cases and cards.
        """
        import hashlib
        ent_hash = hashlib.md5(primary_entity.encode("utf-8")).hexdigest()[:8]
        nexus_id = f"NEXUS-{ent_hash.upper()}"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        if nexus_id in self.store.graph_syndicates:
            nexus = self.store.graph_syndicates[nexus_id]
            if member_case_id not in nexus["member_cases"]:
                nexus["member_cases"].append(member_case_id)
            for cid in card_ids:
                if cid not in nexus["member_cards"]:
                    nexus["member_cards"].append(cid)
            nexus["total_exposure_usd"] = round(nexus["total_exposure_usd"] + exposure_usd, 2)
            nexus["last_detected_at"] = now_str
            nexus["threat_level"] = "critical" if (nexus["total_exposure_usd"] > 10000.0 or len(nexus["member_cards"]) >= 3) else "high"
        else:
            nexus = {
                "id": nexus_id,
                "nexus_type": nexus_type,
                "primary_entity": primary_entity,
                "member_cases": [member_case_id],
                "member_cards": list(set(card_ids)),
                "total_exposure_usd": round(exposure_usd, 2),
                "threat_level": "critical" if (exposure_usd > 10000.0 or len(card_ids) >= 3) else "high",
                "first_detected_at": now_str,
                "last_detected_at": now_str,
            }
            self.store.graph_syndicates[nexus_id] = nexus

        # Establish cross-case linking edges with existing cases in this nexus
        for other_case in nexus["member_cases"]:
            if other_case != member_case_id:
                edge = {
                    "from_case": member_case_id,
                    "to_case": other_case,
                    "type": "CROSS_CASE_LINK",
                    "via_nexus": nexus_id,
                    "established_at": now_str,
                }
                self.store.graph_case_edges.append(edge)

        return nexus_id

    def get_syndicate_dossier(self, nexus_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves comprehensive multi-case syndicate profile from graph.
        """
        return self.store.graph_syndicates.get(nexus_id)

    def get_cross_case_links(self, case_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all cross-case edges connecting this case to other investigations in the graph.
        """
        c_id = f"CASE-{case_id}" if not case_id.startswith("CASE-") else case_id
        links = []
        for edge in getattr(self.store, "graph_case_edges", []):
            if edge.get("type") == "CROSS_CASE_LINK":
                if edge.get("from_case") == c_id or edge.get("to_case") == c_id:
                    other = edge["to_case"] if edge["from_case"] == c_id else edge["from_case"]
                    links.append({
                        "connected_case_id": other,
                        "via_nexus": edge.get("via_nexus"),
                        "established_at": edge.get("established_at"),
                    })
        return links

    def reconstruct_case_from_graph(self, case_id: str) -> Dict[str, Any]:
        """
        Reconstructs the full investigation case record solely from graph vertices.
        """
        graph_case_id = f"CASE-{case_id}" if not case_id.startswith("CASE-") else case_id
        c_vertex = self.store.graph_cases.get(graph_case_id)
        if not c_vertex:
            raise KeyError(f"Case vertex {graph_case_id} not found in graph.")

        # Reconstruct evidence
        evidence_list = []
        for ev_id in c_vertex.get("evidence_ids", []):
            ev_obj = self.store.graph_evidence.get(ev_id)
            if ev_obj:
                evidence_list.append({
                    "id": ev_obj["local_id"],
                    "source": ev_obj["source"],
                    "ref": ev_obj["ref"],
                    "claim": ev_obj["claim"],
                    "entity_ids": ev_obj["entity_ids"],
                })

        # Reconstruct actions
        action_list = []
        for act_id in c_vertex.get("action_ids", []):
            act_obj = self.store.graph_actions.get(act_id)
            if act_obj:
                action_list.append({
                    "action": act_obj["action"],
                    "route": act_obj["route"],
                    "reason": act_obj["reason"],
                })

        return {
            "graph_case_id": graph_case_id,
            "case_id": c_vertex["case_id"],
            "status": c_vertex["status"],
            "verdict": c_vertex["verdict"],
            "fraud_probability": c_vertex["fraud_probability"],
            "pattern": c_vertex["pattern"],
            "pattern_description": c_vertex["pattern_description"],
            "exposure_usd": c_vertex["exposure_usd"],
            "first_suspicious_txn_id": c_vertex["first_suspicious_txn_id"],
            "connected_card_ids": c_vertex["connected_cards"],
            "similar_prior_cases": c_vertex["similar_cases"],
            "affected_txn_ids": c_vertex["affected_txns"],
            "syndicate_nexus_id": c_vertex.get("syndicate_nexus_id"),
            "cross_case_links": self.get_cross_case_links(graph_case_id),
            "evidence": evidence_list,
            "actions": action_list,
            "summary": c_vertex["summary"],
            "is_overridden": c_vertex.get("is_overridden", False),
            "audit_trail": c_vertex.get("audit_trail", []),
        }

    def record_analyst_override(
        self,
        case_id: str,
        analyst_id: str,
        analyst_role: str,
        new_verdict: str,
        justification: str,
        new_actions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Records a human analyst override with structured justification, policy validation,
        and immutable audit trail appending to the graph case.
        """
        if not justification or len(justification.strip()) < 10:
            raise ValueError("Analyst override requires a structured justification of at least 10 characters.")

        valid_verdicts = ["fraud", "legitimate", "uncertain"]
        if new_verdict not in valid_verdicts:
            raise ValueError(f"Invalid verdict '{new_verdict}'. Must be one of {valid_verdicts}.")

        graph_case_id = f"CASE-{case_id}" if not case_id.startswith("CASE-") else case_id
        c_vertex = self.store.graph_cases.get(graph_case_id)
        if not c_vertex:
            raise KeyError(f"Case vertex {graph_case_id} not found in graph.")

        exposure_usd = float(c_vertex.get("exposure_usd", 0.0))
        role = analyst_role.upper().strip()

        # Policy Gate on Overrides:
        # Overriding a fraud verdict to legitimate on high exposure (> $2,500) requires L2_LEAD or COMPLIANCE_OFFICER
        if c_vertex["verdict"] == "fraud" and new_verdict == "legitimate" and exposure_usd > 2500.0:
            if role not in ["L2_LEAD", "COMPLIANCE_OFFICER", "FRAUD_MANAGER"]:
                raise PermissionError(
                    f"Overriding high-exposure (${exposure_usd:.2f}) fraud to legitimate requires L2_LEAD or COMPLIANCE_OFFICER role."
                )

        import hashlib
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        override_hash = hashlib.md5(f"{graph_case_id}:{analyst_id}:{now_str}".encode("utf-8")).hexdigest()[:8]
        override_id = f"OVR-{override_hash.upper()}"

        prev_verdict = c_vertex["verdict"]
        prev_status = c_vertex["status"]

        # Determine new status
        if new_verdict == "fraud":
            new_status = "closed_fraud"
        elif new_verdict == "legitimate":
            new_status = "closed_legitimate"
        else:
            new_status = "escalated"

        override_record = {
            "override_id": override_id,
            "case_id": graph_case_id,
            "analyst_id": analyst_id,
            "analyst_role": role,
            "previous_verdict": prev_verdict,
            "previous_status": prev_status,
            "new_verdict": new_verdict,
            "new_status": new_status,
            "justification": justification.strip(),
            "timestamp": now_str,
            "new_actions": new_actions or [],
        }

        # Update case vertex
        c_vertex["verdict"] = new_verdict
        c_vertex["status"] = new_status
        c_vertex["is_overridden"] = True
        c_vertex["latest_override"] = override_record

        if "audit_trail" not in c_vertex:
            c_vertex["audit_trail"] = []
        c_vertex["audit_trail"].append(override_record)

        # Store in graph_overrides
        if not hasattr(self.store, "graph_overrides"):
            self.store.graph_overrides = {}
        self.store.graph_overrides[override_id] = override_record

        # Store edge in graph_case_edges
        edge = {
            "from_case": graph_case_id,
            "to_override": override_id,
            "type": "OVERRIDDEN_BY",
            "analyst_id": analyst_id,
            "timestamp": now_str,
        }
        self.store.graph_case_edges.append(edge)

        return override_record

    def get_case_audit_trail(self, case_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the immutable audit trail for a case from graph vertices.
        """
        graph_case_id = f"CASE-{case_id}" if not case_id.startswith("CASE-") else case_id
        c_vertex = self.store.graph_cases.get(graph_case_id)
        if not c_vertex:
            return []
        return c_vertex.get("audit_trail", [])
