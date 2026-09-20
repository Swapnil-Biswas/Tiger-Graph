"""
Multi-Agent Debate & Weighted Majority Voting Consensus Protocol (src/agent/consensus.py)
Coordinates deliberation among specialized domain agents:
1. FraudInvestigatorAgent (Transaction & cardholder behavioral patterns)
2. AMLSpecialistAgent (BSA structuring, FATF corridors, statutory SAR filings)
3. CyberForensicsAgent (Hardware pooling, bot bursts, sybil networks)
Resolves signal conflicts, enforces regulatory statutory vetoes, and synthesizes unified action plans.
"""

from typing import Dict, List, Set, Any, Optional, Union, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class FederatedConsensusDossier:
    """
    Unified multi-agent consensus verdict, probability, and coordinated action plan.
    """
    case_id: str
    consensus_verdict: str                  # "fraud", "legitimate", "review", "aml_escalation"
    consensus_probability: float            # 0.00 to 1.00
    consensus_confidence: float             # 0.00 to 1.00 (agreement concordance)
    agent_weights: Dict[str, float] = field(default_factory=dict)
    agent_votes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    conflicts_detected: List[str] = field(default_factory=list)
    debate_transcript: List[str] = field(default_factory=list)
    resolved_unified_actions: List[str] = field(default_factory=list)
    mandatory_regulatory_filings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultiAgentConsensusEngine:
    """
    Autonomous multi-agent consensus engine executing weighted deliberation and statutory vetoes.
    """

    def deliberate(self, investigation_answer: Dict[str, Any]) -> FederatedConsensusDossier:
        """
        Executes multi-agent consensus debate over the completed master investigation payload.
        """
        case_dict = investigation_answer.get("case", {})
        case_id = str(case_dict.get("case_id", investigation_answer.get("case_id", "UNKNOWN")))

        # 1. Extract Agent Votes
        # Fraud Agent
        fraud_prob = float(case_dict.get("fraud_probability", 0.50))
        fraud_verdict = str(case_dict.get("verdict", "review"))
        final_actions = [
            a.get("action", a) if isinstance(a, dict) else a
            for a in investigation_answer.get("next_best_actions", {}).get("final", [])
        ]

        # AML Agent
        aml_data = investigation_answer.get("aml_specialist", {})
        aml_score = float(aml_data.get("aml_score", 0.0))
        aml_tier = aml_data.get("risk_level", "LOW")
        aml_sar = aml_data.get("mandatory_sar", False)
        aml_actions = aml_data.get("recommended_aml_actions", [])

        # Cyber Agent
        cyber_data = investigation_answer.get("cyber_forensics", {})
        cyber_score = float(cyber_data.get("cyber_risk_score", 0.0))
        cyber_tier = cyber_data.get("threat_tier", "LOW")
        cyber_actions = cyber_data.get("recommended_cyber_defenses", [])

        # 2. Dynamic Domain Weighting
        exposure = float(case_dict.get("exposure_usd", 0.0))
        has_structuring = any("STRUCTURING" in t for t in aml_data.get("detected_typologies", []))
        has_bot_burst = any("BOT" in a for a in cyber_data.get("detected_anomalies", []))

        if has_structuring or exposure >= 10000.0:
            # AML-dominant scenario
            w_aml = 0.45
            w_fraud = 0.35
            w_cyber = 0.20
        elif has_bot_burst:
            # Cyber-dominant scenario
            w_cyber = 0.45
            w_fraud = 0.35
            w_aml = 0.20
        else:
            # Standard balanced scenario
            w_fraud = 0.50
            w_aml = 0.25
            w_cyber = 0.25

        # 3. Compute Federated Consensus Probability
        consensus_prob = round(
            (w_fraud * fraud_prob) + (w_aml * aml_score) + (w_cyber * cyber_score),
            4
        )

        # 4. Measure Concordance / Confidence
        # Disagreement variance
        scores = [fraud_prob, aml_score, cyber_score]
        mean_score = sum(scores) / 3.0
        variance = sum((s - mean_score) ** 2 for s in scores) / 3.0
        # Confidence is high when variance is low (unanimous agreement)
        confidence = round(max(0.20, min(1.0, 1.0 - (2.5 * variance))), 4)

        # 5. Detect Signal Conflicts
        conflicts: List[str] = []
        transcript: List[str] = []

        transcript.append(f"[DELIBERATION ROUND 1] Initial Votes:")
        transcript.append(f" - Fraud Agent: P={fraud_prob:.2f} (Verdict: {fraud_verdict})")
        transcript.append(f" - AML Agent: S={aml_score:.2f} (Tier: {aml_tier}, Mandatory SAR: {aml_sar})")
        transcript.append(f" - Cyber Agent: S={cyber_score:.2f} (Tier: {cyber_tier})")

        # Conflict 1: Fraud says legitimate, but Cyber flags High/Critical
        if fraud_verdict == "legitimate" and cyber_tier in ("HIGH", "CRITICAL"):
            conflicts.append("CONFLICT_FRAUD_LEGITIMATE_VS_CYBER_HARDWARE_ALERT")
            transcript.append(
                "[DEBATE] Cyber Agent notes hardware compromise/bot testing, but customer confirmed legitimate usage."
            )

        # Conflict 2: Fraud says review/low, but AML mandates SAR
        if fraud_prob < 0.50 and aml_sar:
            conflicts.append("CONFLICT_LOW_CARD_RISK_VS_MANDATORY_AML_SAR")
            transcript.append(
                "[DEBATE] AML Agent enforces statutory SAR mandate (31 CFR 1020.320) despite routine card telemetry."
            )

        # 6. Consensus Verdict Determination
        if aml_sar or (has_structuring and aml_score >= 0.40):
            consensus_verdict = "aml_escalation" if fraud_verdict != "fraud" else "fraud"
        elif consensus_prob >= 0.70:
            consensus_verdict = "fraud"
        elif consensus_prob <= 0.30:
            consensus_verdict = "legitimate"
        else:
            consensus_verdict = "review"

        transcript.append(f"[DELIBERATION ROUND 2] Consensus Verdict: {consensus_verdict.upper()} (P={consensus_prob:.2f})")

        # 7. Action Resolution & Statutory Vetoes
        unified_actions: Set[str] = set(final_actions)
        regulatory_filings: List[str] = []

        # STATUTORY VETO: If AML agent mandates SAR, it CANNOT be omitted
        if aml_sar:
            unified_actions.add("FILE_SAR_FINCEN")
            regulatory_filings.append("FINCEN_SAR_FORM_111 (Mandatory Under 31 CFR 1020.320)")

        # CYBER ISOLATION: Add hardware defenses if cyber tier is elevated
        if cyber_tier in ("HIGH", "CRITICAL"):
            for d in cyber_actions:
                if d != "MAINTAIN_STANDARD_TELEMETRY":
                    unified_actions.add(d)

        sorted_actions = sorted(list(unified_actions))

        return FederatedConsensusDossier(
            case_id=case_id,
            consensus_verdict=consensus_verdict,
            consensus_probability=consensus_prob,
            consensus_confidence=confidence,
            agent_weights={"fraud": w_fraud, "aml": w_aml, "cyber": w_cyber},
            agent_votes={
                "fraud_agent": {"verdict": fraud_verdict, "probability": fraud_prob, "actions": final_actions},
                "aml_agent": {"risk_tier": aml_tier, "aml_score": aml_score, "mandatory_sar": aml_sar},
                "cyber_agent": {"threat_tier": cyber_tier, "cyber_score": cyber_score, "actions": cyber_actions},
            },
            conflicts_detected=conflicts,
            debate_transcript=transcript,
            resolved_unified_actions=sorted_actions,
            mandatory_regulatory_filings=regulatory_filings,
        )
