"""
Server-Sent Events (SSE) Streaming Engine for Investigation Progression
Streams live investigation steps, tool executions, uncertainty gauge updates,
and recommendation transitions to the UI.
"""

import json
import asyncio
from typing import AsyncGenerator, Dict, Any
from src.agent.graph import FraudInvestigatorAgent


async def stream_investigation_events(
    agent: FraudInvestigatorAgent,
    case_id: str,
    simulated_scenario: str = None,
) -> AsyncGenerator[str, None]:
    """
    Streams realistic progressive SSE events for a case investigation.
    """
    # 1. Event: Trigger Received
    yield f"data: {json.dumps({'step': 'TRIGGER', 'status': 'received', 'case_id': case_id, 'message': f'Received alert trigger for Case {case_id}'})}\n\n"
    await asyncio.sleep(0.2)

    # 2. Event: Opening Case & Graph Neighborhood
    yield f"data: {json.dumps({'step': 'OPEN_CASE', 'status': 'in_progress', 'message': 'Querying card and customer baseline profile (Q1)...'})}\n\n"
    await asyncio.sleep(0.2)

    # Execute full agent investigation
    result = agent.investigate_case(case_id, simulated_scenario=simulated_scenario)
    budget = result.get("budget_plan", {})
    critique = result.get("audit_critique", {})
    pre_prob = result["case"]["fraud_probability"]
    evidence_reqs = result.get("evidence_requests", [])

    # 3. Event: Adaptive Budget Allocation
    if budget:
        tier_str = str(budget.get("budget_tier", "")).upper()
        max_tools = budget.get("max_tool_calls", 10)
        rationale = budget.get("prune_rationale", "")
        event_data = {
            "step": "BUDGET_PLAN",
            "status": "complete",
            "tier": budget.get("budget_tier"),
            "max_tools": max_tools,
            "message": f"Adaptive Tool Budget: {tier_str} ({max_tools} tools). {rationale}",
        }
        yield f"data: {json.dumps(event_data)}\n\n"
        await asyncio.sleep(0.2)

    # 4. Event: Memory & Empirical Bayes Prior
    yield f"data: {json.dumps({'step': 'RETRIEVE_MEMORY', 'status': 'in_progress', 'message': 'Scanning 5,565 closed historical cases; conditioning empirical Bayes Beta-Binomial prior...' })}\n\n"
    await asyncio.sleep(0.3)

    # 5. Event: Graph Structural Analytics
    yield f"data: {json.dumps({'step': 'INVESTIGATE', 'status': 'in_progress', 'message': 'Executing bisect velocity (Q3), device sharing nexus (Q4), ring cycles (Q8), and geo travel anomalies (Q9)...'})}\n\n"
    await asyncio.sleep(0.3)

    # 6. Event: GraphRAG BM25 Retrieval
    yield f"data: {json.dumps({'step': 'GRAPHRAG_BM25', 'status': 'complete', 'message': 'GraphRAG BM25 retrieved applicable bank policy clauses and fraud typology signatures under character budget.'})}\n\n"
    await asyncio.sleep(0.2)

    # 7. Event: Pre-Evidence Assessment
    yield f"data: {json.dumps({'step': 'ASSESS', 'status': 'complete', 'fraud_probability': pre_prob, 'is_ambiguous': len(evidence_reqs) > 0, 'initial_actions': result['next_best_actions']['initial'], 'message': f'Pre-evidence uncertainty assessed: fraud probability {pre_prob:.2f}.'})}\n\n"
    await asyncio.sleep(0.3)

    # 8. Event: Evidence Request (if applicable)
    if evidence_reqs:
        req = evidence_reqs[0]
        resp_msg = req['assumed_response']
        yield f"data: {json.dumps({'step': 'REQUEST_EVIDENCE', 'status': 'in_progress', 'request_type': req['type'], 'assumed_response': req['assumed_response'], 'message': f'Inquiring cardholder: \"{resp_msg}\"' })}\n\n"
        await asyncio.sleep(0.4)

    # 9. Event: Final Recommendation & Actions
    yield f"data: {json.dumps({'step': 'DECIDE_ACTIONS', 'status': 'complete', 'final_actions': result['next_best_actions']['final'], 'what_changed': result['next_best_actions']['what_changed'], 'sar': result['sar']['file'], 'message': 'Final actions and tiered approval routes determined under Bank Fraud Policy.'})}\n\n"
    await asyncio.sleep(0.2)

    # 10. Event: Deterministic Self-Critique & Anti-Hallucination Audit
    if critique:
        critique_summary = critique.get("critique_summary", "")
        faithfulness = critique.get("faithfulness_score", 1.0)
        event_data = {
            "step": "SELF_CRITIQUE",
            "status": "complete",
            "faithfulness": faithfulness,
            "message": f"Audit Critique: {critique_summary} (Faithfulness: {faithfulness:.2f})",
        }
        yield f"data: {json.dumps(event_data)}\n\n"
        await asyncio.sleep(0.2)

    # 11. Event: Complete Case Payload
    yield f"data: {json.dumps({'step': 'COMPLETE', 'status': 'done', 'payload': result})}\n\n"

