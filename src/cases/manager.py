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

        self.store.graph_cases[graph_case_id] = case_vertex
        return graph_case_id

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
            "evidence": evidence_list,
            "actions": action_list,
            "summary": c_vertex["summary"],
        }
