"""
Assessment & Uncertainty Model
Computes deterministic Risk Score (0-100), Fraud Probability (0-1), Confidence (0-1),
and Sufficiency to Act from graph evidence and customer signals.
"""

from typing import Dict, List, Any, Tuple
from src.agent.state import Assessment, Hypothesis


class UncertaintyAssessmentEngine:

    @staticmethod
    def assess(
        trigger: Dict[str, Any],
        graph_evidence: Dict[str, Any],
        evidence_response: Dict[str, Any] = None,
    ) -> Assessment:
        """
        Synthesizes graph analytics into Risk, Confidence, and Sufficiency.
        """
        trigger_type = trigger.get("trigger_type", "risk_score")
        bank_score = float(trigger.get("risk_score", 0.5) or 0.5)
        
        pat_info = graph_evidence.get("pattern_match", {})
        best_pat = pat_info.get("best_pattern", "none")
        pat_conf = pat_info.get("patterns", {}).get(best_pat, {}).get("confidence", 0.0)

        new_ent = graph_evidence.get("new_entity", {})
        vel = graph_evidence.get("velocity", {})
        sharing = graph_evidence.get("device_sharing", {})
        ring = graph_evidence.get("ring", {})
        geo = graph_evidence.get("geo", {})
        profile = graph_evidence.get("profile", {})
        similar = graph_evidence.get("similar_cases", {})

        # Base Risk Points Calculation
        risk_points = 0.0

        if trigger_type == "customer_report":
            # Customer reported unrecognized activity
            risk_points += 60.0
        else:
            # Score driven
            risk_points += bank_score * 35.0

        # Graph Pattern Match
        risk_points += pat_conf * 30.0

        # Novelty & Identity
        if new_ent.get("is_new_device") or new_ent.get("identity_flag_new"):
            risk_points += 15.0
        if new_ent.get("is_new_region"):
            risk_points += 10.0
        if new_ent.get("is_new_email"):
            risk_points += 10.0
        if new_ent.get("proxy_flag"):
            risk_points += 15.0

        # Impossible Travel & Geographic Anomalies
        if geo.get("has_geo_anomaly"):
            risk_points += 20.0

        # Velocity burst
        spike_ratio = vel.get("velocity_spike_ratio", 1.0)
        if spike_ratio > 3.0:
            risk_points += 15.0
        elif spike_ratio > 1.5:
            risk_points += 8.0

        # Device sharing / Cluster
        if sharing.get("is_shared"):
            risk_points += 15.0
        if ring.get("is_ring_candidate"):
            risk_points += 15.0

        # Prior fraud cases touching entity
        if similar.get("similar_cases_count", 0) > 0:
            risk_points += 10.0

        # Customer habits dampener (only if NO customer report)
        if trigger_type != "customer_report" and profile.get("txn_count", 0) > 10:
            if not new_ent.get("is_new_region") and not new_ent.get("is_new_device") and not sharing.get("is_shared") and not geo.get("has_geo_anomaly"):
                risk_points = max(20.0, risk_points - 20.0)

        # Evidence Response Update (Post-Inquiry)
        post_response_override = False
        if evidence_response and evidence_response.get("responded"):
            scenario = evidence_response.get("scenario")
            if scenario in ["denies", "step_up_fail"]:
                risk_points = max(86.0, risk_points + 30.0)
                post_response_override = True
            elif scenario in ["recognizes", "recurring_confirmed", "step_up_pass"]:
                risk_points = min(12.0, max(5.0, risk_points - 60.0))
                post_response_override = True

        risk_score = round(min(100.0, max(0.0, risk_points)), 2)
        fraud_prob = round(risk_score / 100.0, 2)

        # Confidence Computation
        if post_response_override:
            confidence = 0.92
        elif trigger_type == "customer_report":
            # Initial report warrants inquiry before permanent block
            confidence = 0.65
        elif fraud_prob >= 0.85:
            confidence = 0.88
        elif fraud_prob <= 0.20:
            confidence = 0.85
        else:
            # Uncertain / ambiguous zone
            confidence = 0.60

        confidence = round(confidence, 2)

        # Ambiguity check
        is_ambiguous = (not post_response_override) and (
            trigger_type == "customer_report"
            or (0.30 <= fraud_prob < 0.85 and confidence < 0.80)
            or (trigger_type == "risk_score" and bank_score >= 0.50 and not post_response_override and fraud_prob < 0.85)
        )

        # Sufficiency
        sufficient_to_act = post_response_override or (confidence >= 0.80 and not is_ambiguous)

        # Verdict
        if fraud_prob >= 0.65:
            verdict = "fraud"
        elif fraud_prob <= 0.25:
            verdict = "legitimate"
        else:
            verdict = "uncertain"

        # Missing evidence
        missing = []
        if not post_response_override:
            missing.append("Cardholder transaction verification (Rule R1 / R2)")
            if new_ent.get("is_new_device"):
                missing.append("Step-up authentication confirmation")

        # Pattern assignment
        if verdict == "legitimate":
            assigned_pattern = "none"
            pattern_desc = ""
        elif ring.get("is_ring_candidate") and new_ent.get("proxy_flag"):
            assigned_pattern = "undocumented"
            pattern_desc = "Multi-card proxy rotation and credential stuffing: identical mobile device profile with anonymous proxy observed across multiple unrelated customer accounts."
        elif best_pat != "none" and pat_conf >= 0.40:
            assigned_pattern = best_pat
            pattern_desc = ""
        elif geo.get("has_geo_anomaly") or (new_ent.get("is_new_region") and not new_ent.get("is_new_device")):
            assigned_pattern = "out_of_region_use"
            pattern_desc = ""
        elif new_ent.get("identity_flag_new") or (new_ent.get("is_new_email") and new_ent.get("is_new_device")):
            assigned_pattern = "account_takeover"
            pattern_desc = ""
        elif new_ent.get("is_new_device"):
            assigned_pattern = "card_not_present_new_device"
            pattern_desc = ""
        else:
            assigned_pattern = "card_not_present_fraud"
            pattern_desc = ""

        hypotheses = [
            Hypothesis(
                fraud_type=assigned_pattern,
                probability=fraud_prob,
                supporting=[f"Graph pattern {best_pat} confidence {pat_conf}"] if pat_conf > 0 else ["Trigger risk signal"],
                contradicting=["Consistent with typical cardholder baseline"] if profile.get("txn_count", 0) > 10 else [],
            )
        ]

        return Assessment(
            risk_score=risk_score,
            fraud_probability=fraud_prob,
            confidence=confidence,
            verdict=verdict,
            pattern=assigned_pattern,
            pattern_description=pattern_desc,
            sufficient_to_act=sufficient_to_act,
            is_ambiguous=is_ambiguous,
            missing_evidence=missing,
            hypotheses=hypotheses,
        )
