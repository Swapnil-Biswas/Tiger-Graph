"""
Agent Investigation State Models (Pydantic v2)
Maintains strict schemas for evidence, findings, hypotheses, assessments,
actions, events, and case progression.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    id: str
    source: Literal["graph", "document", "customer", "external"]
    ref: str
    claim: str
    entity_ids: List[str] = Field(default_factory=list)


class Finding(BaseModel):
    id: str
    kind: str
    statement: str
    strength: Literal["weak", "moderate", "strong"]
    evidence_ids: List[str]  # Required non-empty
    policy_chunk_ids: List[str] = Field(default_factory=list)


class Hypothesis(BaseModel):
    fraud_type: str
    probability: float
    supporting: List[str] = Field(default_factory=list)
    contradicting: List[str] = Field(default_factory=list)


class Assessment(BaseModel):
    risk_score: float         # 0.0 to 100.0
    fraud_probability: float  # 0.0 to 1.0
    confidence: float         # 0.0 to 1.0
    verdict: Literal["fraud", "legitimate", "uncertain"]
    pattern: str
    pattern_description: str = ""
    sufficient_to_act: bool
    is_ambiguous: bool
    missing_evidence: List[str] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)


class ProposedAction(BaseModel):
    action: str
    route: Literal["auto", "L1", "L2"]
    reason: str
    policy_decision: Optional[Literal["allow", "needs_approval", "deny"]] = None
    approver: Optional[str] = None
    simulated: bool = True


class EvidenceRequest(BaseModel):
    type: Literal["customer_validation", "step_up_auth", "analyst_info"]
    asked_after_step: int
    assumed_response: str
    reason: str = ""


class NextBestActionsBundle(BaseModel):
    initial: List[ProposedAction] = Field(default_factory=list)
    final: List[ProposedAction] = Field(default_factory=list)
    what_changed: str = "nothing"


class CaseSARRecord(BaseModel):
    file: bool = False
    reason: str = ""
    narrative: str = ""
    subjects: List[str] = Field(default_factory=list)
    total_amount_usd: float = 0.0
    activity_dates: List[str] = Field(default_factory=list)


class CaseInvestigationRecord(BaseModel):
    status: Literal["open", "closed_fraud", "closed_legitimate", "escalated"]
    verdict: Literal["fraud", "legitimate", "uncertain"]
    fraud_probability: float
    pattern: str
    pattern_description: str = ""
    affected_txn_ids: List[str] = Field(default_factory=list)
    first_suspicious_txn_id: str = ""
    connected_card_ids: List[str] = Field(default_factory=list)
    connected_device_profiles: List[str] = Field(default_factory=list)
    exposure_usd: float = 0.0
    evidence: List[EvidenceItem] = Field(default_factory=list)
    similar_prior_cases: List[str] = Field(default_factory=list)
    summary: str
    written_to_graph: bool = True
    graph_case_id: str = ""


class InvestigationState(BaseModel):
    case_id: str
    trigger: Dict[str, Any]
    opened_at: str
    as_of: str
    loop_count: int = 0
    max_loops: int = 3
    stop_reason: str = ""
    tool_calls: int = 0
    tokens: int = 0
    latency_s: float = 0.0

    # Dynamic state
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    assessment: Optional[Assessment] = None
    pre_evidence_assessment: Optional[Assessment] = None
    initial_actions: List[ProposedAction] = Field(default_factory=list)
    final_actions: List[ProposedAction] = Field(default_factory=list)
    evidence_requests: List[EvidenceRequest] = Field(default_factory=list)
    what_changed: str = "nothing"
    sar: Optional[CaseSARRecord] = None
    summary_text: str = ""
    events: List[Dict[str, Any]] = Field(default_factory=list)
