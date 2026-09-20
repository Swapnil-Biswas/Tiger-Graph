"""
Anti-Money Laundering (AML) Specialist Agent (src/agent/aml_agent.py)
Autonomous specialized domain agent for Bank Secrecy Act (BSA), FinCEN, FATF, and AML compliance.
Analyzes cross-entity structuring, sub-threshold smurfing, correspondent banking transit corridors,
sanctioned jurisdictions, and high-risk MCC quasi-cash conversion.
Generates structured regulatory citations (31 CFR 1020.320, 31 USC 5324) and enriched SAR narratives.
"""

from typing import Dict, List, Set, Any, Optional, Union
from dataclasses import dataclass, field, asdict

from src.graph.client import GraphClient, parse_as_of_epoch


@dataclass
class AMLAssessment:
    """
    Structured AML assessment and regulatory compliance output.
    """
    case_id: str
    is_aml_flagged: bool
    risk_level: str                          # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    aml_score: float                         # 0.00 to 1.00
    detected_typologies: List[str] = field(default_factory=list)
    structuring_analysis: Dict[str, Any] = field(default_factory=dict)
    cross_border_analysis: Dict[str, Any] = field(default_factory=dict)
    mcc_risk_analysis: Dict[str, Any] = field(default_factory=dict)
    total_aml_exposure_usd: float = 0.0
    mandatory_sar: bool = False
    sar_jurisdiction: str = "US_FINCEN"
    regulatory_citations: List[str] = field(default_factory=list)
    recommended_aml_actions: List[str] = field(default_factory=list)
    aml_narrative: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AMLSpecialistAgent:
    """
    Specialized agent dedicated to anti-money laundering, counter-terrorist financing,
    and regulatory structuring detection.
    """

    FATF_SANCTIONED_CORRIDORS = {"IRN", "PRK", "MMR", "SYR", "RUS"}
    BSA_CTR_THRESHOLD_USD = 10000.0

    def __init__(self, client: Optional[GraphClient] = None):
        self.client = client or GraphClient(mode="embedded")

    def assess_case(
        self,
        case_id: str,
        as_of: Optional[Union[str, int]] = None,
        window_hours: float = 48.0,
    ) -> AMLAssessment:
        """
        Executes comprehensive multi-vector AML analysis for a given case incident.
        """
        as_of_epoch = parse_as_of_epoch(as_of)

        # 1. Resolve seed card and customer
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

        # 2. Run Q16 Structuring Detection
        structuring_res = {}
        if card_id:
            try:
                structuring_res = self.client.detect_structuring(card_id, as_of=as_of_epoch, window_hours=window_hours)
            except Exception:
                structuring_res = {}

        # 3. Run Q20 Cross-Border AML & Correspondent Banking
        cross_border_res = {}
        if card_id:
            try:
                cross_border_res = self.client.detect_cross_border_aml(card_id, as_of=as_of_epoch, window_hours=window_hours)
            except Exception:
                cross_border_res = {}

        # 4. Run Q21 High-Risk MCC Classification
        mcc_res = {}
        if card_id:
            try:
                mcc_res = self.client.detect_high_risk_mcc(card_id, as_of=as_of_epoch, window_hours=window_hours)
            except Exception:
                mcc_res = {}

        # 5. Synthesize Typologies & Scores
        typologies: List[str] = []
        citations: List[str] = []
        aml_actions: List[str] = []

        is_structuring = structuring_res.get("is_structuring", False)
        structuring_indicators = structuring_res.get("structuring_indicators", [])
        structuring_exposure = float(structuring_res.get("total_exposure_usd", 0.0))

        if is_structuring or len(structuring_indicators) > 0:
            typologies.append("AML_STRUCTURING_SMURFING")
            citations.append("31 USC 5324(a) (Structuring transactions to evade reporting requirement)")
            citations.append("31 CFR 1010.311 (Currency Transaction Reports - CTR)")
            aml_actions.append("FILE_SAR_FINCEN")
            aml_actions.append("FLAG_STRUCTURING_NETWORK")

        cross_txns = int(cross_border_res.get("cross_border_txns_count", 0))
        is_layering = cross_border_res.get("is_layering_bundling_detected", False)
        high_risk_corridor = cross_border_res.get("has_fatf_high_risk_corridor", False)
        if cross_txns > 0 or is_layering or high_risk_corridor:
            typologies.append("AML_HIGH_RISK_CORRESPONDENT_CORRIDOR")
            citations.append("FATF Recommendation 16 (Wire Transfers & Originator Information)")
            citations.append("31 CFR 1020.320 (Reports of suspicious transactions by national banks)")
            if "FILE_SAR_FINCEN" not in aml_actions:
                aml_actions.append("FILE_SAR_FINCEN")
            aml_actions.append("RESTRICT_INTERNATIONAL_WIRE")

        mccs_detected = mcc_res.get("high_risk_mccs_detected", [])
        mcc_exposure = float(mcc_res.get("high_risk_exposure_usd", 0.0))
        if mccs_detected:
            typologies.append(f"AML_QUASI_CASH_CONCENTRATION_{'_'.join(mccs_detected)}")
            citations.append("FinCEN Advisory FIN-2019-A003 (Convertible Virtual Currencies & Quasi-Cash)")
            aml_actions.append("RESTRICT_QUASI_CASH")

        # Total Exposure
        total_exposure = max(
            structuring_exposure,
            mcc_exposure,
            float(cross_border_res.get("cross_border_exposure_usd", 0.0)),
            float(case_obj.get("total_exposure", 0.0)),
        )

        # Mandatory SAR filing check
        mandatory_sar = False
        if is_structuring or high_risk_corridor or total_exposure >= self.BSA_CTR_THRESHOLD_USD:
            mandatory_sar = True
            if "FILE_SAR_FINCEN" not in aml_actions:
                aml_actions.append("FILE_SAR_FINCEN")

        # Calculate AML Score
        score = 0.0
        if is_structuring or len(structuring_indicators) > 0:
            score += 0.45
        if high_risk_corridor:
            score += 0.35
        elif cross_txns > 0 or is_layering:
            score += 0.15
        if mccs_detected:
            score += 0.20
        if total_exposure >= self.BSA_CTR_THRESHOLD_USD:
            score += 0.25

        score = round(min(1.0, score), 4)

        if score >= 0.70:
            risk_level = "CRITICAL"
        elif score >= 0.45:
            risk_level = "HIGH"
        elif score >= 0.20:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        is_flagged = (score >= 0.20 or len(typologies) > 0)

        # Default actions if clean
        if not aml_actions:
            aml_actions.append("STANDARD_MONITORING")

        # Generate Regulatory Narrative
        narrative_parts = [
            f"=== AML SPECIALIST AGENT COMPLIANCE REPORT (CASE: {case_id}) ===",
            f"Risk Level: {risk_level} (AML Score: {score:.2f}) | Total Exposure: ${total_exposure:,.2f}",
        ]
        if typologies:
            narrative_parts.append(f"Identified Typologies: {', '.join(typologies)}")
        if citations:
            narrative_parts.append(f"Applicable Statutory Citations: {'; '.join(citations)}")
        if mandatory_sar:
            narrative_parts.append(
                "MANDATORY REGULATORY FILING: Form 111 FinCEN SAR filing strictly mandated under 31 CFR 1020.320."
            )
        else:
            narrative_parts.append("Filing Determination: Routine AML activity below mandatory reporting thresholds.")

        aml_narrative = "\n".join(narrative_parts)

        return AMLAssessment(
            case_id=case_id,
            is_aml_flagged=is_flagged,
            risk_level=risk_level,
            aml_score=score,
            detected_typologies=typologies,
            structuring_analysis=structuring_res,
            cross_border_analysis=cross_border_res,
            mcc_risk_analysis=mcc_res,
            total_aml_exposure_usd=total_exposure,
            mandatory_sar=mandatory_sar,
            sar_jurisdiction="US_FINCEN",
            regulatory_citations=citations,
            recommended_aml_actions=aml_actions,
            aml_narrative=aml_narrative,
        )
