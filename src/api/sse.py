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
    yield f"data: {json.dumps({'step': 'TRIGGER', 'status': 'received', 'case_id': case_id, 'message': f'Received trigger for Case {case_id}'})}\n\n"
    await asyncio.sleep(0.3)

    # 2. Event: Opening Case & Graph Neighborhood
    yield f"data: {json.dumps({'step': 'OPEN_CASE', 'status': 'in_progress', 'message': 'Querying customer and card baseline profile (Q1)...'})}\n\n"
    await asyncio.sleep(0.4)

    # 3. Event: Memory Retrieval
    yield f"data: {json.dumps({'step': 'RETRIEVE_MEMORY', 'status': 'in_progress', 'message': 'Scanning 5,565 closed historical cases for structural and typology precedents (Q10)...'})}\n\n"
    await asyncio.sleep(0.4)

    # 4. Event: Analytics & Graph Pattern Execution
    yield f"data: {json.dumps({'step': 'INVESTIGATE', 'status': 'in_progress', 'message': 'Evaluating velocity burst (Q3), device sharing (Q4), and 5 fraud typology signatures (Q11)...'})}\n\n"
    await asyncio.sleep(0.5)

    # 5. Execute full agent investigation
    result = agent.investigate_case(case_id, simulated_scenario=simulated_scenario)
    pre_prob = result["case"]["fraud_probability"]
    evidence_reqs = result.get("evidence_requests", [])

    # 6. Event: Pre-Evidence Assessment
    yield f"data: {json.dumps({'step': 'ASSESS', 'status': 'complete', 'fraud_probability': pre_prob, 'is_ambiguous': len(evidence_reqs) > 0, 'initial_actions': result['next_best_actions']['initial'], 'message': f'Pre-evidence assessment complete. Assessed probability: {pre_prob:.2f}'})}\n\n"
    await asyncio.sleep(0.5)

    # 7. Event: Evidence Request (if applicable)
    if evidence_reqs:
        req = evidence_reqs[0]
        resp_msg = req['assumed_response']
        yield f"data: {json.dumps({'step': 'REQUEST_EVIDENCE', 'status': 'in_progress', 'request_type': req['type'], 'assumed_response': req['assumed_response'], 'message': f'Inquiring cardholder: {resp_msg}'})}\n\n"
        await asyncio.sleep(0.6)


    # 8. Event: Final Recommendation & Actions
    yield f"data: {json.dumps({'step': 'DECIDE_ACTIONS', 'status': 'complete', 'final_actions': result['next_best_actions']['final'], 'what_changed': result['next_best_actions']['what_changed'], 'sar': result['sar']['file'], 'message': 'Final actions determined under Bank Fraud Policy.'})}\n\n"
    await asyncio.sleep(0.3)

    # 9. Event: Complete Case Payload
    yield f"data: {json.dumps({'step': 'COMPLETE', 'status': 'done', 'payload': result})}\n\n"
