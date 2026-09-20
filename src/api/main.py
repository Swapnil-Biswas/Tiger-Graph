"""
FastAPI Server for TigerGraph Agentic Fraud Investigator
Exposes REST and SSE endpoints for case investigations, approvals, graph exploration,
memory retrieval, mock actions, and serves the web frontend.
"""

import os
import sys
import json
import time
import uuid
from typing import Dict, Any, Optional, List, Union
from fastapi import FastAPI, HTTPException, Query, Body, Response, Depends
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.agent.graph import FraudInvestigatorAgent
from src.cases.manager import CaseManager
from src.api.sse import stream_investigation_events


app = FastAPI(
    title="TigerGraph Agentic Fraud Investigator API",
    version="1.0.0",
    description="Agentic Fraud Investigation & Next-Best-Action System (HHGOA)",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent and case manager instances
agent = FraudInvestigatorAgent()
case_manager = CaseManager(client=agent.client)

# Asynchronous Investigation Task Queue
from src.agent.queue import InvestigationTaskQueue
task_queue = InvestigationTaskQueue(max_workers=2, agent=agent)

# Graph Scenario Simulator
from src.graph.simulation import GraphScenarioSimulator
simulator = GraphScenarioSimulator(agent=agent)

# Temporal Graph Playback Engine
from src.graph.playback import TemporalGraphPlaybackEngine
playback_engine = TemporalGraphPlaybackEngine(client=agent.client)

# Compliance Evidence Packager
from src.cases.evidence_bundle import ComplianceEvidencePackager
evidence_packager = ComplianceEvidencePackager()

# Syndicate Cluster & LOD Engine
from src.graph.cluster_renderer import SyndicateClusterEngine
cluster_engine = SyndicateClusterEngine(store=agent.client.store)

# Multi-Tenant Role-Based Access Control (RBAC)
from src.auth.rbac import (
    Role,
    Permission,
    AuthUser,
    get_current_user,
    require_permission,
    mask_pii_dict,
    ROLE_PERMISSIONS,
)

# FinCEN Form 111 XML Packager
from src.cases.sar_exporter import FinCENSARXMLPackager
sar_packager = FinCENSARXMLPackager()

# Streaming Transaction Monitor
from src.graph.streaming_monitor import StreamingGraphMonitor, StreamingAlert
streaming_monitor = StreamingGraphMonitor()

# Enterprise Prometheus & SLA Telemetry
from src.api.telemetry import telemetry
telemetry.set_gauge("graph_indexed_entities", len(agent.client.store.transactions), {"type": "transactions"})
telemetry.set_gauge("graph_indexed_entities", len(agent.client.store.cards), {"type": "cards"})
telemetry.set_gauge("graph_indexed_entities", len(agent.client.store.customers), {"type": "customers"})
telemetry.set_gauge("graph_indexed_entities", len(agent.client.store.closed_cases), {"type": "cases"})

# Enterprise Webhook Dispatcher
from src.api.webhooks import webhook_dispatcher

# In-memory store for active cases & approvals
active_cases: Dict[str, Dict[str, Any]] = {}
pending_approvals: Dict[str, Dict[str, Any]] = {}


class InvestigateRequest(BaseModel):
    case_id: str
    scenario: Optional[str] = None


class ApprovalDecision(BaseModel):
    action_id: str
    decision: str  # "approved" | "rejected"
    notes: Optional[str] = ""


class CaseOverrideRequest(BaseModel):
    analyst_id: str
    analyst_role: Optional[str] = "L1_ANALYST"  # "L1_ANALYST" | "L2_LEAD" | "COMPLIANCE_OFFICER"
    new_verdict: str  # "fraud" | "legitimate" | "uncertain"
    justification: str
    new_actions: Optional[list] = None


class StructuringCheckRequest(BaseModel):
    customer_id: Optional[str] = None
    device_profile: Optional[str] = None
    card_ids: Optional[List[str]] = None
    transactions: Optional[List[Dict[str, Any]]] = None
    window_hours: float = 24.0
    as_of: Optional[str] = None
    jurisdiction: str = "US"


class ContagionCheckRequest(BaseModel):
    seed_id: str
    entity_type: str = "card"
    as_of: Optional[str] = None
    restart_prob: float = 0.15
    custom_fraud_seeds: Optional[List[str]] = None


class PoolEmbeddingRequest(BaseModel):
    seed_id: str
    entity_type: str = "card"
    as_of: Optional[str] = None
    k_hops: int = 2
    max_nodes: int = 50
    decay_lambda: float = 0.05


class MineRulesRequest(BaseModel):
    min_support: int = 10
    min_confidence: float = 0.80
    as_of: Optional[str] = None
    target_consequent: str = "confirmed_fraud"
    max_rules: int = 20


class EvaluateRulesRequest(BaseModel):
    card_id: str
    as_of: Optional[str] = None


class CrossBorderCheckRequest(BaseModel):
    card_id: str
    transactions: Optional[List[Dict[str, Any]]] = None
    as_of: Optional[str] = None
    window_hours: float = 48.0


class MCCCheckRequest(BaseModel):
    card_id: str
    transactions: Optional[List[Dict[str, Any]]] = None
    as_of: Optional[str] = None
    window_hours: float = 48.0


class MotifsCheckRequest(BaseModel):
    seed_id: str
    entity_type: str = "card"
    as_of: Optional[str] = None
    window_hours: float = 72.0


class EntityLinkageRequest(BaseModel):
    profile_a: Dict[str, Any]
    profile_b: Dict[str, Any]


class SybilCheckRequest(BaseModel):
    card_id: str
    as_of: Optional[str] = None


class EdgeDecayRequest(BaseModel):
    epoch_s: int
    as_of: Optional[str] = None
    edge_type: str = "TRANSACTION"
    is_fraud: bool = False
    risk_score: float = 0.0
    half_life_days: float = 30.0


class StreamingPruneRequest(BaseModel):
    as_of: Optional[str] = None
    sample_size: int = 50
    half_life_days: float = 30.0
    max_degree: int = 50


class RefineInvestigationRequest(BaseModel):
    answer: Dict[str, Any]
    max_refinements: int = 3


class TripletExportRequest(BaseModel):
    case_id: str
    max_hops: int = 2
    max_triplets: int = 150
    as_of: Optional[str] = None
    format: str = "bundle"


class ActiveLearningMineRequest(BaseModel):
    target_size: int = 20
    strategy: str = "hybrid_balanced"
    as_of: Optional[str] = None
    max_scan: int = 2000
    max_per_card: int = 2
    max_per_merchant: int = 3


class AMLAssessmentRequest(BaseModel):
    case_id: str
    as_of: Optional[str] = None
    window_hours: float = 48.0


class CyberAssessmentRequest(BaseModel):
    case_id: str
    as_of: Optional[str] = None


class ConsensusDeliberateRequest(BaseModel):
    investigation_answer: Dict[str, Any]


class EnqueueTaskRequest(BaseModel):
    task_type: str = "CASE_INVESTIGATION"
    payload: Dict[str, Any]
    priority: str = "NORMAL"
    idempotency_key: Optional[str] = None
    max_retries: int = 3
    backoff_factor: float = 0.05


class MemorySearchRequest(BaseModel):
    card_id: Optional[str] = None
    customer_id: Optional[str] = None
    device_profile: Optional[str] = None
    domain_filter: str = "ALL"  # "ALL", "FRAUD", "AML", "CYBER"
    as_of: Optional[str] = None
    top_k: int = 5
    query_vector: Optional[List[float]] = None


class RunSimulationRequest(BaseModel):
    case_id: str
    amount_multiplier: float = 1.0
    override_amount: Optional[float] = None
    inject_transactions: List[Dict[str, Any]] = []
    unlink_devices: List[str] = []
    unlink_ip_addresses: List[str] = []
    override_mcc: Optional[str] = None
    simulated_customer_response: Optional[str] = None
    notes: Optional[str] = ""


class ActionAuthorizeRequest(BaseModel):
    action_name: str
    exposure_usd: Optional[float] = 0.0


StructuringCheckRequest.model_rebuild()
ContagionCheckRequest.model_rebuild()
PoolEmbeddingRequest.model_rebuild()
MineRulesRequest.model_rebuild()
EvaluateRulesRequest.model_rebuild()
CrossBorderCheckRequest.model_rebuild()
MCCCheckRequest.model_rebuild()
MotifsCheckRequest.model_rebuild()
EntityLinkageRequest.model_rebuild()
SybilCheckRequest.model_rebuild()
EdgeDecayRequest.model_rebuild()
StreamingPruneRequest.model_rebuild()
RefineInvestigationRequest.model_rebuild()
TripletExportRequest.model_rebuild()
ActiveLearningMineRequest.model_rebuild()
AMLAssessmentRequest.model_rebuild()
CyberAssessmentRequest.model_rebuild()
ConsensusDeliberateRequest.model_rebuild()
EnqueueTaskRequest.model_rebuild()
MemorySearchRequest.model_rebuild()
RunSimulationRequest.model_rebuild()
ActionAuthorizeRequest.model_rebuild()


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "transactions_indexed": len(agent.client.store.transactions),
        "cards_indexed": len(agent.client.store.cards),
        "closed_cases_indexed": len(agent.client.store.closed_cases),
        "benchmark_cases_indexed": len(agent.client.store.case_pack),
    }


@app.get("/api/cases")
def get_all_cases():
    """Returns all benchmark and investigated cases for the Case Board."""
    cases_list = []
    # Benchmark cases
    import pandas as pd
    for cid, c_data in agent.client.store.case_pack.items():
        inv = active_cases.get(cid)
        raw_score = c_data.get("risk_score")
        score_val = float(raw_score) if (raw_score is not None and pd.notna(raw_score) and str(raw_score).strip() != "") else None
        cases_list.append({
            "case_id": cid,
            "opened_at": str(c_data.get("opened_at", "")),
            "trigger_type": str(c_data.get("trigger_type", "")),
            "trigger_text": str(c_data.get("trigger_text", "")),
            "card_id": str(c_data.get("card_id", "")),
            "customer_id": str(c_data.get("customer_id", "")),
            "risk_score": score_val,
            "status": inv["case"]["status"] if inv else "NEW",
            "verdict": inv["case"]["verdict"] if inv else "pending",
            "fraud_probability": inv["case"]["fraud_probability"] if inv else None,
            "is_investigated": inv is not None,
        })

    return {"cases": cases_list}


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, user: AuthUser = Depends(get_current_user)):
    """Retrieves full investigation record for a case, with role-based PII masking."""
    import copy
    if case_id in active_cases:
        res = active_cases[case_id]
    elif case_id in agent.client.store.case_pack:
        res = agent.investigate_case(case_id)
        active_cases[case_id] = res
        case_manager.write_case_to_graph(res)
    else:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    res_copy = copy.deepcopy(res)
    pack_item = agent.client.store.case_pack.get(case_id, {})
    if "card_id" not in res_copy.get("case", {}) and pack_item.get("card_id"):
        res_copy.setdefault("case", {})["card_id"] = pack_item["card_id"]
    if "customer_id" not in res_copy.get("case", {}) and pack_item.get("customer_id"):
        res_copy.setdefault("case", {})["customer_id"] = pack_item["customer_id"]

    return mask_pii_dict(res_copy, user)


@app.post("/api/investigate")
def start_investigation(req: InvestigateRequest):
    """Synchronous investigation endpoint."""
    t0 = time.perf_counter()
    res = agent.investigate_case(req.case_id, simulated_scenario=req.scenario)
    elapsed = time.perf_counter() - t0
    active_cases[req.case_id] = res
    case_manager.write_case_to_graph(res)

    telemetry.inc_counter("fraud_investigations_total", 1.0, {"verdict": res["case"]["verdict"], "status": "completed"})
    telemetry.observe_histogram("investigation_latency_seconds", elapsed)

    # Queue any gated L1 / L2 approvals
    for act in res["next_best_actions"]["final"]:
        if act["route"] in ["L1", "L2"]:
            appr_id = f"{req.case_id}-{act['action']}"
            pending_approvals[appr_id] = {
                "approval_id": appr_id,
                "case_id": req.case_id,
                "action": act["action"],
                "route": act["route"],
                "reason": act["reason"],
                "exposure_usd": res["case"]["exposure_usd"],
                "status": "pending",
            }
            if act["route"] == "L2":
                webhook_dispatcher.dispatch_event(
                    "CASE_ESCALATION_L2",
                    {
                        "case_id": req.case_id,
                        "action": act["action"],
                        "route": act["route"],
                        "exposure_usd": res["case"]["exposure_usd"],
                        "verdict": res["case"]["verdict"],
                    },
                )

    if res.get("sar", {}).get("file"):
        webhook_dispatcher.dispatch_event(
            "SAR_FILING_REQUIRED",
            {
                "case_id": req.case_id,
                "exposure_usd": res["case"]["exposure_usd"],
                "verdict": res["case"]["verdict"],
                "sar_file": res["sar"]["file"],
                "subjects": res["sar"].get("subjects", []),
            },
        )

    return {"case_id": req.case_id, "status": "complete", "result": res}


@app.get("/api/cases/{case_id}/stream")
def stream_investigation(case_id: str, scenario: Optional[str] = None):
    """Server-Sent Events streaming of investigation progression."""
    return StreamingResponse(
        stream_investigation_events(agent, case_id, simulated_scenario=scenario),
        media_type="text/event-stream",
    )


@app.get("/api/cases/{case_id}/graph")
def get_case_subgraph(case_id: str):
    """Returns Cytoscape.js compatible JSON subgraph."""
    return agent.client.get_case_subgraph(case_id)


@app.get("/api/approvals")
def get_approvals():
    """Returns queue of actions requiring L1/L2 analyst approval."""
    return {"approvals": list(pending_approvals.values())}


@app.post("/api/approvals/{approval_id}")
def process_approval(approval_id: str, decision: ApprovalDecision):
    """Analyst approval / rejection of gated action."""
    if approval_id not in pending_approvals:
        raise HTTPException(status_code=404, detail="Approval not found.")
    
    pending_approvals[approval_id]["status"] = decision.decision
    pending_approvals[approval_id]["notes"] = decision.notes
    return {"status": "success", "approval": pending_approvals[approval_id]}


@app.post("/api/cases/{case_id}/override")
def override_case_verdict(case_id: str, req: CaseOverrideRequest):
    """
    Human analyst override endpoint.
    Allows fraud analysts to override an agent verdict with structured justification,
    policy role validation, and immutable graph audit logging.
    """
    # Ensure case is loaded in graph/active_cases
    if case_id not in active_cases and f"CASE-{case_id}" not in case_manager.store.graph_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    try:
        override_rec = case_manager.record_analyst_override(
            case_id=case_id,
            analyst_id=req.analyst_id,
            analyst_role=req.analyst_role,
            new_verdict=req.new_verdict,
            justification=req.justification,
            new_actions=req.new_actions,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except (ValueError, KeyError) as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    # Synchronize active_cases cache if present
    if case_id in active_cases:
        active_cases[case_id]["case"]["verdict"] = req.new_verdict
        active_cases[case_id]["case"]["status"] = override_rec["new_status"]
        active_cases[case_id]["case"]["is_overridden"] = True
        active_cases[case_id]["case"]["latest_override"] = override_rec
        if req.new_actions:
            active_cases[case_id]["next_best_actions"]["final"] = req.new_actions

    return {
        "status": "success",
        "case_id": case_id,
        "override": override_rec,
        "case": active_cases.get(case_id) or case_manager.reconstruct_case_from_graph(case_id),
    }


@app.get("/api/cases/{case_id}/audit")
def get_case_audit_trail(case_id: str):
    """Retrieves immutable audit trail and analyst overrides for a case."""
    audit_trail = case_manager.get_case_audit_trail(case_id)
    return {"case_id": case_id, "audit_trail": audit_trail}


@app.get("/api/cases/{case_id}/regulatory")
def get_regulatory_dispatch(case_id: str, jurisdiction: Optional[str] = None):
    """Retrieves multi-jurisdiction regulatory filing package and GDPR certifications."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_data = active_cases[case_id]
    from src.policy.jurisdiction import JurisdictionComplianceRouter
    bundle = JurisdictionComplianceRouter.generate_dispatch_bundle(
        case_answer=case_data,
        override_jurisdiction=jurisdiction,
        client=agent.client,
    )
    return bundle


@app.get("/api/cases/{case_id}/structuring")
def get_case_structuring(case_id: str, window_hours: float = 24.0, jurisdiction: str = "US"):
    """Evaluates BSA/POCA/6AMLD regulatory structuring alerts and multi-entity exposure rollup."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_data = active_cases[case_id]
    from src.policy.jurisdiction import RegulatoryStructuringDetector
    connected_cards = case_data.get("case", {}).get("connected_card_ids", [])
    analysis = RegulatoryStructuringDetector.detect_structuring(
        card_ids=connected_cards if connected_cards else None,
        window_hours=window_hours,
        jurisdiction=jurisdiction,
        client=agent.client,
    )
    return {"case_id": case_id, "structuring_analysis": analysis}


@app.post("/api/regulatory/structuring-check")
def run_structuring_check(req: StructuringCheckRequest):
    """On-demand regulatory structuring & multi-entity exposure rollup."""
    from src.policy.jurisdiction import RegulatoryStructuringDetector
    return RegulatoryStructuringDetector.detect_structuring(
        customer_id=req.customer_id,
        device_profile=req.device_profile,
        card_ids=req.card_ids,
        transactions=req.transactions,
        window_hours=req.window_hours,
        as_of=req.as_of,
        jurisdiction=req.jurisdiction,
        client=agent.client,
    )


@app.get("/api/cases/{case_id}/cross-border-aml")
def get_case_cross_border_aml(case_id: str, window_hours: float = 48.0):
    """Evaluates cross-border AML transaction bundling, correspondent banking risk, and FATF corridor exposure."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_data = active_cases[case_id]
    card_id = case_data.get("case", {}).get("card_id")
    as_of = case_data.get("case", {}).get("as_of")
    analysis = agent.client.detect_cross_border_aml(
        card_id=card_id,
        transactions=case_data.get("case", {}).get("transactions"),
        as_of=as_of,
        window_hours=window_hours,
    )
    return {"case_id": case_id, "cross_border_aml_analysis": analysis}


@app.post("/api/regulatory/cross-border-check")
def run_cross_border_check(req: CrossBorderCheckRequest):
    """On-demand cross-border AML and correspondent banking risk evaluation."""
    return agent.client.detect_cross_border_aml(
        card_id=req.card_id,
        transactions=req.transactions,
        as_of=req.as_of,
        window_hours=req.window_hours,
    )


@app.get("/api/syndicates/{nexus_id}/merchants")
def get_syndicate_merchants(nexus_id: str, as_of: Optional[str] = None):
    """Retrieves multi-case shared merchant and proxy hub expansion for a syndicate nexus."""
    if not hasattr(agent.client.store, "graph_syndicates") or nexus_id not in agent.client.store.graph_syndicates:
        raise HTTPException(status_code=404, detail=f"Syndicate nexus {nexus_id} not found.")
    
    return case_manager.expand_syndicate_merchants(nexus_id=nexus_id, as_of=as_of)


@app.get("/api/cases/{case_id}/mcc-risk")
def get_case_mcc_risk(case_id: str, window_hours: float = 48.0):
    """Evaluates high-risk Merchant Category Code (MCC) exposure and adaptive velocity multipliers."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_data = active_cases[case_id]
    card_id = case_data.get("case", {}).get("card_id")
    as_of = case_data.get("case", {}).get("as_of")
    analysis = agent.client.detect_high_risk_mcc(
        card_id=card_id,
        transactions=case_data.get("case", {}).get("transactions"),
        as_of=as_of,
        window_hours=window_hours,
    )
    return {"case_id": case_id, "mcc_risk_analysis": analysis}


@app.post("/api/regulatory/mcc-check")
def run_mcc_check(req: MCCCheckRequest):
    """On-demand high-risk MCC and adaptive velocity multiplier evaluation."""
    return agent.client.detect_high_risk_mcc(
        card_id=req.card_id,
        transactions=req.transactions,
        as_of=req.as_of,
        window_hours=req.window_hours,
    )


@app.get("/api/cases/{case_id}/contagion")
def get_case_contagion(case_id: str, restart_prob: float = 0.15):
    """Calculates Personalized PageRank fraud contagion score from confirmed fraud seeds."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_data = active_cases[case_id]
    card_id = case_data.get("case", {}).get("card_id")
    as_of = case_data.get("case", {}).get("as_of")
    contagion = agent.client.calculate_fraud_contagion(
        seed_id=card_id,
        entity_type="card",
        as_of=as_of,
        restart_prob=restart_prob,
    )
    return {"case_id": case_id, "contagion": contagion}


@app.post("/api/graph/contagion-check")
def run_contagion_check(req: ContagionCheckRequest):
    """On-demand Personalized PageRank fraud contagion calculation."""
    return agent.client.calculate_fraud_contagion(
        seed_id=req.seed_id,
        entity_type=req.entity_type,
        as_of=req.as_of,
        restart_prob=req.restart_prob,
        custom_fraud_seeds=req.custom_fraud_seeds,
    )


@app.get("/api/cases/{case_id}/embedding")
def get_case_embedding(case_id: str, k_hops: int = 2, decay_lambda: float = 0.05):
    """Extracts and pools temporal graph attention embeddings for a case."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_data = active_cases[case_id]
    card_id = case_data.get("case", {}).get("card_id")
    as_of = case_data.get("case", {}).get("as_of")
    embedding = agent.client.pool_graph_embedding(
        seed_id=card_id,
        entity_type="card",
        as_of=as_of,
        k_hops=k_hops,
        decay_lambda=decay_lambda,
    )
    return {"case_id": case_id, "embedding": embedding}


@app.post("/api/graph/pool-embedding")
def run_pool_embedding(req: PoolEmbeddingRequest):
    """On-demand temporal graph attention subgraph pooling."""
    return agent.client.pool_graph_embedding(
        seed_id=req.seed_id,
        entity_type=req.entity_type,
        as_of=req.as_of,
        k_hops=req.k_hops,
        max_nodes=req.max_nodes,
        decay_lambda=req.decay_lambda,
    )


@app.get("/api/cases/{case_id}/motifs")
def get_case_motifs(case_id: str, window_hours: float = 72.0):
    """Mines topological transaction subgraph motifs for a case."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_data = active_cases[case_id]
    card_id = case_data.get("case", {}).get("card_id")
    as_of = case_data.get("case", {}).get("as_of")
    motifs = agent.client.mine_subgraph_motifs(
        seed_id=card_id,
        entity_type="card",
        as_of=as_of,
        window_hours=window_hours,
    )
    return {"case_id": case_id, "motifs": motifs}


@app.post("/api/graph/motifs-check")
def run_motifs_check(req: MotifsCheckRequest):
    """On-demand temporal transaction subgraph motif mining."""
    return agent.client.mine_subgraph_motifs(
        seed_id=req.seed_id,
        entity_type=req.entity_type,
        as_of=req.as_of,
        window_hours=req.window_hours,
    )


@app.post("/api/graph/entity-linkage")
def run_entity_linkage(req: EntityLinkageRequest):
    """Calculates Fellegi-Sunter probabilistic match probability between two entity profiles."""
    return agent.client.resolve_entity_linkage(req.profile_a, req.profile_b)


@app.get("/api/devices/{device_key:path}/resolved")
def get_resolved_device_nexus(device_key: str, as_of: Optional[str] = None, similarity_threshold: float = 0.75):
    """Resolves fuzzy near-duplicate device profiles across the graph."""
    return agent.client.resolve_device_nexus(
        device_key=device_key,
        as_of=as_of,
        similarity_threshold=similarity_threshold,
    )


@app.get("/api/cases/{case_id}/sybils")
def get_case_sybils(case_id: str):
    """Discovers probabilistic sybil identities and synthetic cards for a case."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_data = active_cases[case_id]
    card_id = case_data.get("case", {}).get("card_id")
    as_of = case_data.get("case", {}).get("as_of")
    return agent.client.resolve_cardholder_sybils(card_id=card_id, as_of=as_of)


@app.post("/api/graph/sybil-check")
def run_sybil_check(req: SybilCheckRequest):
    """On-demand cardholder sybil identity discovery."""
    return agent.client.resolve_cardholder_sybils(card_id=req.card_id, as_of=req.as_of)


@app.post("/api/graph/edge-decay")
def run_edge_decay_check(req: EdgeDecayRequest):
    """Calculates continuous exponential temporal decay weight for an edge."""
    return agent.client.calculate_edge_decay(
        epoch_s=req.epoch_s,
        as_of=req.as_of,
        edge_type=req.edge_type,
        is_fraud=req.is_fraud,
        risk_score=req.risk_score,
        half_life_days=req.half_life_days,
    )


@app.post("/api/graph/streaming-prune")
def run_streaming_prune(req: StreamingPruneRequest):
    """Simulates streaming graph pruning across active cards and measures memory reduction."""
    return agent.client.prune_streaming_graph(
        as_of=req.as_of,
        sample_size=req.sample_size,
        half_life_days=req.half_life_days,
        max_degree=req.max_degree,
    )


@app.get("/api/cards/{card_id}/pruned")
def get_card_pruned_edges(card_id: str, as_of: Optional[str] = None, half_life_days: float = 30.0, max_degree: int = 50):
    """Applies exponential temporal decay and bounded top-K degree pruning to card transactions."""
    return agent.client.prune_card_edges(
        card_id=card_id,
        as_of=as_of,
        half_life_days=half_life_days,
        max_degree=max_degree,
    )


@app.post("/api/agent/self-refine")
def run_self_refine(req: RefineInvestigationRequest):
    """Executes graph-augmented self-refinement and counterfactual verification loop on an investigation answer."""
    from src.agent.refiner import GraphAugmentedSelfRefiner
    refiner = GraphAugmentedSelfRefiner(max_refinements=req.max_refinements)
    return refiner.refine_investigation(req.answer)


@app.get("/api/cases/{case_id}/triplets")
def get_case_triplets(
    case_id: str,
    format: str = "bundle",
    max_hops: int = 2,
    max_triplets: int = 150,
    as_of: Optional[str] = None,
):
    """Q25: Extracts semantic knowledge graph triplets and exports in TigerGraph GSQL, Neo4j Cypher, or RDF formats."""
    return agent.client.export_knowledge_triplets(
        case_id=case_id,
        max_hops=max_hops,
        max_triplets=max_triplets,
        as_of=as_of,
        format=format,
    )


@app.post("/api/graph/triplets/export")
def post_triplets_export(req: TripletExportRequest):
    """Q25: Dynamic knowledge graph triplet export endpoint."""
    return agent.client.export_knowledge_triplets(
        case_id=req.case_id,
        max_hops=req.max_hops,
        max_triplets=req.max_triplets,
        as_of=req.as_of,
        format=req.format,
    )


@app.post("/api/ml/active-learning/mine")
def post_active_learning_mine(req: ActiveLearningMineRequest):
    """Q26: Mines informative and hard-negative transaction candidates for continuous model retraining."""
    return agent.client.select_active_learning_samples(
        target_size=req.target_size,
        strategy=req.strategy,
        as_of=req.as_of,
        max_scan=req.max_scan,
        max_per_card=req.max_per_card,
        max_per_merchant=req.max_per_merchant,
    )


@app.get("/api/ml/active-learning/candidates")
def get_active_learning_candidates(
    target_size: int = 20,
    strategy: str = "hybrid_balanced",
    as_of: Optional[str] = None,
    max_scan: int = 2000,
):
    """Q26: Retrieves informative candidates for continuous retraining."""
    return agent.client.select_active_learning_samples(
        target_size=target_size,
        strategy=strategy,
        as_of=as_of,
        max_scan=max_scan,
    )


@app.post("/api/agents/aml/assess")
def post_aml_assess(req: AMLAssessmentRequest):
    """Executes specialized domain assessment by the AMLSpecialistAgent."""
    from src.agent.aml_agent import AMLSpecialistAgent
    aml_agent = AMLSpecialistAgent(client=agent.client)
    res = aml_agent.assess_case(case_id=req.case_id, as_of=req.as_of, window_hours=req.window_hours)
    return res.to_dict()


@app.get("/api/cases/{case_id}/aml-assessment")
def get_case_aml_assessment(case_id: str, as_of: Optional[str] = None, window_hours: float = 48.0):
    """Retrieves specialized domain assessment by the AMLSpecialistAgent for a case."""
    from src.agent.aml_agent import AMLSpecialistAgent
    aml_agent = AMLSpecialistAgent(client=agent.client)
    res = aml_agent.assess_case(case_id=case_id, as_of=as_of, window_hours=window_hours)
    return res.to_dict()


@app.post("/api/agents/cyber/assess")
def post_cyber_assess(req: CyberAssessmentRequest):
    """Executes specialized cyber-forensics assessment by the CyberForensicsAgent."""
    from src.agent.cyber_agent import CyberForensicsAgent
    cyber_agent = CyberForensicsAgent(client=agent.client)
    res = cyber_agent.assess_case(case_id=req.case_id, as_of=req.as_of)
    return res.to_dict()


@app.get("/api/cases/{case_id}/cyber-assessment")
def get_case_cyber_assessment(case_id: str, as_of: Optional[str] = None):
    """Retrieves specialized cyber-forensics assessment by the CyberForensicsAgent for a case."""
    from src.agent.cyber_agent import CyberForensicsAgent
    cyber_agent = CyberForensicsAgent(client=agent.client)
    res = cyber_agent.assess_case(case_id=case_id, as_of=as_of)
    return res.to_dict()


@app.post("/api/agents/consensus/deliberate")
def post_consensus_deliberate(req: ConsensusDeliberateRequest):
    """Deliberates multi-agent weighted consensus over an investigation answer payload."""
    from src.agent.consensus import MultiAgentConsensusEngine
    engine = MultiAgentConsensusEngine()
    res = engine.deliberate(req.investigation_answer)
    return res.to_dict()


@app.get("/api/cases/{case_id}/consensus")
def get_case_consensus(case_id: str, as_of: Optional[str] = None):
    """Executes full multi-agent investigation and retrieves federated consensus dossier."""
    answer = agent.investigate_case(case_id)
    return answer.get("federated_consensus", {})


@app.post("/api/queue/tasks")
def post_enqueue_task(req: EnqueueTaskRequest):
    """Submits an asynchronous investigation/screening task with idempotency deduplication."""
    task, is_dedup = task_queue.submit_task(
        task_type=req.task_type,
        payload=req.payload,
        priority=req.priority,
        idempotency_key=req.idempotency_key,
        max_retries=req.max_retries,
        backoff_factor=req.backoff_factor,
    )
    return {
        "task": task.to_dict(),
        "is_deduplicated": is_dedup,
    }


@app.get("/api/queue/tasks/{task_id}")
def get_queued_task(task_id: str):
    """Retrieves current execution status, progress, timing, and result for a queued task."""
    task = task_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return task.to_dict()


@app.post("/api/queue/tasks/{task_id}/cancel")
def cancel_queued_task(task_id: str):
    """Cancels a pending or running task in the investigation queue."""
    ok = task_queue.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Task '{task_id}' could not be cancelled or was not found.")
    task = task_queue.get_task(task_id)
    return {"status": "cancelled", "task": task.to_dict() if task else None}


@app.get("/api/queue/stats")
def get_queue_stats():
    """Returns queue depth, worker concurrency, throughput, and DLQ statistics."""
    return task_queue.get_stats()


@app.get("/api/queue/dlq")
def get_queue_dlq():
    """Retrieves all failed tasks in the Dead Letter Queue for auditing."""
    tasks = task_queue.get_dead_letter_tasks()
    return {"count": len(tasks), "dead_letter_tasks": [t.to_dict() for t in tasks]}


@app.post("/api/queue/dlq/{task_id}/retry")
def retry_dlq_task(task_id: str):
    """Retries a failed task from the Dead Letter Queue."""
    task = task_queue.retry_dlq_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found in DLQ.")
    return {"status": "requeued", "task": task.to_dict()}







@app.get("/api/rules/mined")
def get_mined_rules(
    min_support: int = 10,
    min_confidence: float = 0.80,
    as_of: Optional[str] = None,
    target_consequent: str = "confirmed_fraud",
    max_rules: int = 20,
):
    """Mines inductive association rules from historical closed cases."""
    return agent.client.mine_inductive_rules(
        min_support=min_support,
        min_confidence=min_confidence,
        as_of=as_of,
        target_consequent=target_consequent,
        max_rules=max_rules,
    )


@app.post("/api/rules/evaluate")
def run_evaluate_rules(req: EvaluateRulesRequest):
    """Evaluates an active card against mined inductive rules."""
    return agent.client.evaluate_inductive_rules(
        card_id=req.card_id,
        as_of=req.as_of,
    )


@app.get("/api/cases/{case_id}/dossier")
def get_case_dossier(case_id: str):
    """Generates and returns self-contained interactive HTML incident dossier."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    from src.cases.dossier_exporter import IncidentDossierExporter
    html_report = IncidentDossierExporter.export_html_dossier(active_cases[case_id])
    return Response(content=html_report, media_type="text/html")


@app.get("/api/memory/similar")
def get_similar_cases(card_id: str, customer_id: Optional[str] = None):
    """Retrieves similar cases from graph memory."""
    return agent.retriever.retrieve_similar_cases(
        query=f"card {card_id} unauthorized fraud",
        card_id=card_id,
        customer_id=customer_id,
        top_k=5,
    )


@app.post("/api/memory/episodes/search")
def search_memory_episodes(req: MemorySearchRequest):
    """Searches federated episodic memory across Fraud, AML, and Cyber sub-agent domains."""
    return agent.memory_bus.query_cross_agent_precedents(
        query_vector=req.query_vector,
        card_id=req.card_id,
        customer_id=req.customer_id,
        device_profile=req.device_profile,
        domain_filter=req.domain_filter,
        as_of=req.as_of,
        top_k=req.top_k,
    )


@app.get("/api/memory/episodes/{case_id}")
def get_memory_episode(case_id: str):
    """Retrieves committed federated multi-agent episode for a specific case."""
    ep = agent.memory_bus.get_episode(case_id)
    if not ep:
        # If not already committed, run investigation to generate and commit episode
        if case_id in agent.client.store.case_pack or case_id in agent.client.store.closed_cases:
            ans = agent.investigate_case(case_id)
            active_cases[case_id] = ans
            ep = agent.memory_bus.get_episode(case_id)
    if not ep:
        raise HTTPException(status_code=404, detail=f"Episode for case '{case_id}' not found.")
    return ep.to_dict()


@app.get("/api/memory/blackboard/{case_id}")
def get_case_blackboard(case_id: str):
    """Retrieves real-time working memory blackboard observations for an active investigation."""
    obs_list = agent.memory_bus.get_blackboard(case_id)
    return {
        "case_id": case_id,
        "observation_count": len(obs_list),
        "observations": [o.to_dict() for o in obs_list],
    }


@app.get("/api/memory/cross-domain-prior")
def get_cross_domain_prior(
    card_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    device_profile: Optional[str] = None,
    as_of: Optional[str] = None,
):
    """Calculates unified multi-domain empirical risk prior combining Fraud, AML, and Cyber precedents."""
    return agent.memory_bus.get_cross_domain_prior(
        card_id=card_id,
        customer_id=customer_id,
        device_profile=device_profile,
        as_of=as_of,
    )


@app.post("/api/simulation/run")
def run_scenario_simulation(req: RunSimulationRequest):
    """Executes counterfactual what-if simulation comparing baseline vs perturbed graph state."""
    from src.graph.simulation import ScenarioPerturbation
    perturbation = ScenarioPerturbation(
        case_id=req.case_id,
        amount_multiplier=req.amount_multiplier,
        override_amount=req.override_amount,
        inject_transactions=req.inject_transactions,
        unlink_devices=req.unlink_devices,
        unlink_ip_addresses=req.unlink_ip_addresses,
        override_mcc=req.override_mcc,
        simulated_customer_response=req.simulated_customer_response,
        notes=req.notes or "",
    )
    report = simulator.simulate_scenario(perturbation)
    return report.to_dict()


@app.get("/api/simulation/templates")
def get_simulation_templates():
    """Retrieves pre-configured counterfactual scenario templates."""
    return simulator.list_templates()


@app.post("/api/simulation/templates/{template_id}/apply")
def apply_simulation_template(template_id: str, case_id: str = Query(...)):
    """Applies a preset scenario template to a case and returns delta report."""
    try:
        report = simulator.apply_template(case_id=case_id, template_id=template_id)
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/graph/playback/{case_id}")
def get_graph_playback(case_id: str, max_frames: int = 50):
    """Generates an interactive chronological step-by-step graph evolution timeline."""
    try:
        timeline = playback_engine.generate_case_playback(case_id=case_id, max_frames=max_frames)
        return timeline.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/playback/{case_id}/frame/{frame_idx}")
def get_graph_playback_frame(case_id: str, frame_idx: int):
    """Retrieves a single frame state and active subgraph from the playback timeline."""
    timeline = playback_engine.generate_case_playback(case_id=case_id)
    if frame_idx < 0 or frame_idx >= len(timeline.frames):
        raise HTTPException(status_code=404, detail=f"Frame {frame_idx} out of range [0, {len(timeline.frames)-1}]")
    return timeline.frames[frame_idx].to_dict()


@app.get("/api/cases/{case_id}/evidence-bundle")
def get_case_evidence_bundle(case_id: str):
    """Generates an immutable, cryptographically certified compliance evidence bundle with Merkle root and digital signature."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            cfile = os.path.join("cases", f"{case_id}.json")
            if os.path.exists(cfile):
                with open(cfile, "r", encoding="utf-8") as f:
                    active_cases[case_id] = json.load(f)
            else:
                raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_ans = active_cases[case_id]
    bundle = evidence_packager.build_evidence_bundle(case_ans)
    return bundle.to_dict()


@app.get("/api/cases/{case_id}/evidence-manifest")
def get_case_evidence_manifest(case_id: str):
    """Retrieves a regulatory submission manifest listing Merkle root and item hashes."""
    if case_id not in active_cases:
        if case_id in agent.client.store.case_pack:
            res = agent.investigate_case(case_id)
            active_cases[case_id] = res
            case_manager.write_case_to_graph(res)
        else:
            cfile = os.path.join("cases", f"{case_id}.json")
            if os.path.exists(cfile):
                with open(cfile, "r", encoding="utf-8") as f:
                    active_cases[case_id] = json.load(f)
            else:
                raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case_ans = active_cases[case_id]
    bundle = evidence_packager.build_evidence_bundle(case_ans)
    return bundle.export_manifest()


@app.post("/api/compliance/verify-evidence-bundle")
def verify_evidence_bundle_endpoint(bundle: Dict[str, Any]):
    """Performs full cryptographic audit on an uploaded evidence bundle to detect bit-flips or tampering."""
    report = evidence_packager.verify_bundle(bundle)
    return report


@app.get("/api/graph/syndicates/macro-topology")
def get_syndicates_macro_topology():
    """Retrieves high-level macro network topology across all syndicate nexuses."""
    return cluster_engine.extract_macro_topology()


@app.get("/api/graph/clusters/{case_id}/lod")
def get_case_lod_clusters(case_id: str):
    """Retrieves multi-scale Level-of-Detail (LOD 0, 1, 2) graph views with WebGL vertex buffers."""
    lod_views = cluster_engine.generate_case_lod_views(case_id)
    return {k: v.to_dict() for k, v in lod_views.items()}


@app.get("/api/auth/me")
def get_auth_me(user: AuthUser = Depends(get_current_user)):
    """Returns current authenticated user, assigned role, permissions, and tenant."""
    return {
        "user_id": user.user_id,
        "role": user.role.value,
        "department": user.department,
        "tenant_id": user.tenant_id,
        "permissions": sorted([p.value for p in user.permissions]),
    }


@app.get("/api/auth/roles")
def get_auth_roles():
    """Returns the matrix of system roles and their assigned permissions."""
    return {
        role.value: sorted([p.value for p in perms])
        for role, perms in ROLE_PERMISSIONS.items()
    }


@app.post("/api/cases/{case_id}/actions/authorize")
def authorize_case_action(
    case_id: str,
    req: ActionAuthorizeRequest,
    user: AuthUser = Depends(get_current_user),
):
    """Checks whether the authenticated user has authority to execute a specific action on a case."""
    authorized, reason = user.can_execute_action(req.action_name, req.exposure_usd or 0.0)
    if authorized:
        telemetry.inc_counter(
            "policy_actions_authorized_total",
            1.0,
            {"action": req.action_name, "role": user.role.value},
        )
    return {
        "case_id": case_id,
        "action_name": req.action_name,
        "user_id": user.user_id,
        "role": user.role.value,
        "authorized": authorized,
        "reason": reason,
    }


class ValidateSARXMLRequest(BaseModel):
    xml_content: str


ValidateSARXMLRequest.model_rebuild()


@app.get("/api/cases/{case_id}/sar/xml")
def get_case_sar_xml(case_id: str, user: AuthUser = Depends(get_current_user)):
    """Exports official FinCEN Form 111 XML 2.0 electronic filing document."""
    if case_id in active_cases:
        res = active_cases[case_id]
    elif case_id in agent.client.store.case_pack:
        res = agent.investigate_case(case_id)
        active_cases[case_id] = res
        case_manager.write_case_to_graph(res)
    else:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    res_masked = mask_pii_dict(res, user)
    xml_str = sar_packager.generate_sar_xml(res_masked)
    return Response(content=xml_str, media_type="application/xml")


@app.post("/api/compliance/validate-sar-xml")
def validate_sar_xml_endpoint(req: ValidateSARXMLRequest):
    """Validates an uploaded FinCEN SAR XML document against 12 mandatory BSA E-Filing criteria."""
    report = sar_packager.validate_sar_xml(req.xml_content)
    return report.to_dict()


class StreamingIngestRequest(BaseModel):
    transaction: Optional[Dict[str, Any]] = None
    transactions: Optional[List[Dict[str, Any]]] = None


StreamingIngestRequest.model_rebuild()


@app.post("/api/streaming/ingest")
def ingest_streaming_transaction(req: StreamingIngestRequest):
    """Ingests live streaming transactions and returns any triggered anomaly alerts."""
    t0 = time.perf_counter()
    txns = req.transactions or ([req.transaction] if req.transaction else [])
    alerts = []
    for t in txns:
        al = streaming_monitor.ingest_transaction(t)
        alerts.extend(al)
    elapsed = time.perf_counter() - t0
    telemetry.inc_counter("streaming_transactions_ingested_total", float(len(txns)))
    telemetry.observe_histogram("streaming_ingest_latency_seconds", elapsed, buckets=telemetry.STREAMING_BUCKETS)
    if alerts:
        for a in alerts:
            telemetry.inc_counter("streaming_alerts_emitted_total", 1.0, {"rule": a.rule_triggered, "severity": a.severity})
            if a.severity == "CRITICAL":
                webhook_dispatcher.dispatch_event(
                    "STREAMING_CRITICAL_ANOMALY",
                    {
                        "alert_id": a.alert_id,
                        "card_id": a.card_id,
                        "rule": a.rule_triggered,
                        "severity": a.severity,
                        "details": a.details,
                        "timestamp": a.timestamp,
                    },
                )
    return {
        "processed": len(txns),
        "alerts_triggered": len(alerts),
        "alerts": [a.to_dict() for a in alerts],
    }


@app.get("/api/streaming/alerts")
def get_streaming_alerts(severity: Optional[str] = None, limit: int = 50):
    """Retrieves active streaming alerts filtered by optional severity."""
    return {"alerts": streaming_monitor.get_alerts(severity=severity, limit=limit)}


@app.get("/api/streaming/stats")
def get_streaming_stats():
    """Returns sliding window operational metrics."""
    return streaming_monitor.get_stats()


@app.get("/metrics")
def get_prometheus_metrics():
    """Prometheus/OpenMetrics exposition endpoint for Grafana/Prometheus scraper."""
    return Response(
        content=telemetry.generate_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/api/telemetry/dashboard")
def get_telemetry_dashboard():
    """Returns operational SLA telemetry metrics and health status."""
    return telemetry.get_dashboard_summary()


class WebhookSubscriptionRequest(BaseModel):
    url: str
    secret: str
    events: Optional[List[str]] = None
    enabled: bool = True


WebhookSubscriptionRequest.model_rebuild()


class WebhookTestRequest(BaseModel):
    event_type: str = "TEST_INCIDENT_EVENT"
    payload: Optional[Dict[str, Any]] = None


WebhookTestRequest.model_rebuild()


@app.post("/api/webhooks/subscriptions")
def register_webhook_subscription(req: WebhookSubscriptionRequest):
    """Registers a webhook endpoint to receive real-time fraud incident notifications."""
    sub = webhook_dispatcher.register_subscription(
        url=req.url,
        secret=req.secret,
        events=req.events,
        enabled=req.enabled,
    )
    return {"status": "success", "subscription": sub.to_dict()}


@app.get("/api/webhooks/subscriptions")
def get_webhook_subscriptions():
    """Lists all active webhook subscriptions."""
    return {"subscriptions": [s.to_dict() for s in webhook_dispatcher.get_subscriptions()]}


@app.delete("/api/webhooks/subscriptions/{sub_id}")
def delete_webhook_subscription(sub_id: str):
    """Removes a registered webhook subscription."""
    deleted = webhook_dispatcher.delete_subscription(sub_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Subscription {sub_id} not found.")
    return {"status": "success", "deleted_id": sub_id}


@app.post("/api/webhooks/test")
def test_webhook_dispatch(req: WebhookTestRequest):
    """Triggers a simulated webhook delivery for testing external integrations."""
    sample_payload = req.payload or {
        "incident_id": f"INC-{uuid.uuid4().hex[:8].upper()}",
        "severity": "CRITICAL",
        "description": "Simulated fraud syndicate alert for webhook validation",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    deliveries = webhook_dispatcher.dispatch_event(req.event_type, sample_payload, send_http=False)
    return {
        "status": "dispatched",
        "event_type": req.event_type,
        "deliveries_count": len(deliveries),
        "deliveries": [d.to_dict() for d in deliveries],
    }


@app.get("/api/webhooks/deliveries")
def get_webhook_deliveries(limit: int = 50):
    """Returns recent webhook delivery audit history."""
    return {"deliveries": webhook_dispatcher.get_delivery_log(limit=limit)}


@app.post("/api/benchmark/run")
def run_benchmark():
    """Runs all 20 benchmark cases and outputs answer files to cases/."""
    os.makedirs("cases", exist_ok=True)
    results = {}
    for i in range(1, 21):
        cid = f"HHG-{i:03d}"
        ans = agent.investigate_case(cid)
        active_cases[cid] = ans
        case_manager.write_case_to_graph(ans)
        
        # Save to cases/<case_id>.json
        out_file = os.path.join("cases", f"{cid}.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(ans, f, indent=2)
        results[cid] = {"verdict": ans["case"]["verdict"], "pattern": ans["case"]["pattern"], "sar": ans["sar"]["file"]}

    return {"status": "complete", "total_evaluated": 20, "benchmark_results": results}


@app.get("/api/export/{case_id}")
def export_case(case_id: str):
    """Exports case answer JSON."""
    file_path = os.path.join("cases", f"{case_id}.json")
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/json", filename=f"{case_id}.json")
    if case_id in active_cases:
        return JSONResponse(active_cases[case_id])
    raise HTTPException(status_code=404, detail="Answer file not found.")


# Cryptographic Audit Ledger
from src.policy.audit_ledger import get_audit_ledger
audit_ledger = get_audit_ledger()

@app.get("/api/audit/ledger")
def get_audit_entries(limit: int = Query(default=100, ge=1, le=1000)):
    """Retrieve the latest cryptographically signed audit ledger entries."""
    entries = audit_ledger.get_entries(limit=limit)
    return {"entries": entries, "count": len(entries)}

@app.get("/api/audit/verify")
def verify_audit_ledger():
    """Verify cryptographic hash chain integrity and HMAC-SHA256 signatures."""
    ok, msg = audit_ledger.verify_chain()
    return {"verified": ok, "message": msg}


# Mount UI static directory
ui_dir = os.path.join(os.path.dirname(__file__), "../../ui")
if os.path.exists(ui_dir):
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
