"""
FastAPI Server for TigerGraph Agentic Fraud Investigator
Exposes REST and SSE endpoints for case investigations, approvals, graph exploration,
memory retrieval, mock actions, and serves the web frontend.
"""

import os
import sys
import json
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query, Body, Response
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
def get_case(case_id: str):
    """Retrieves full investigation record for a case."""
    if case_id in active_cases:
        return active_cases[case_id]
    
    # Auto-run if not yet investigated
    if case_id in agent.client.store.case_pack:
        res = agent.investigate_case(case_id)
        active_cases[case_id] = res
        case_manager.write_case_to_graph(res)
        return res
        
    raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")


@app.post("/api/investigate")
def start_investigation(req: InvestigateRequest):
    """Synchronous investigation endpoint."""
    res = agent.investigate_case(req.case_id, simulated_scenario=req.scenario)
    active_cases[req.case_id] = res
    case_manager.write_case_to_graph(res)

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


class StructuringCheckRequest(BaseModel):
    customer_id: Optional[str] = None
    device_profile: Optional[str] = None
    card_ids: Optional[List[str]] = None
    transactions: Optional[List[Dict[str, Any]]] = None
    window_hours: float = 24.0
    as_of: Optional[str] = None
    jurisdiction: str = "US"


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


# Mount UI static directory
ui_dir = os.path.join(os.path.dirname(__file__), "../../ui")
if os.path.exists(ui_dir):
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
