"""
Graph-Native Counterfactual Explainer
Generates deterministic counterfactual conditions answering:
"What minimum changes in graph topology or customer verification would flip this decision?"
Dramatically enhances regulatory transparency, auditability, and analyst trust.
"""

from typing import Dict, Any, List


class CounterfactualExplainer:
    """
    Generates actionable, topologically grounded counterfactual statements
    explaining decision sensitivity and boundaries.
    """

    @staticmethod
    def generate_counterfactuals(
        verdict: str,
        fraud_probability: float,
        pattern: str,
        graph_evidence: Dict[str, Any],
        trigger: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Computes counterfactual inversion requirements.
        Returns a list of structured counterfactual conditions.
        """
        counterfactuals = []
        new_ent = graph_evidence.get("new_entity", {})
        geo = graph_evidence.get("geo", {})
        sharing = graph_evidence.get("device_sharing", {})
        profile = graph_evidence.get("profile", {})
        vel = graph_evidence.get("velocity", {})

        typical_regions = profile.get("typical_regions", [])
        typical_regions_str = ", ".join(str(r) for r in typical_regions[:2]) if typical_regions else "home region"

        if verdict == "fraud":
            # Target: What would turn verdict into legitimate or uncertain?
            # 1. Customer Verification Counterfactual
            counterfactuals.append({
                "factor": "Cardholder Confirmation",
                "condition": "Customer confirms authorization during SMS or mobile push challenge",
                "impact": "Fraud probability would reduce from {prob:.2f} to ≤ 0.10, flipping verdict to LEGITIMATE (Rule R3).".format(prob=fraud_probability),
                "flip_verdict": "legitimate",
            })

            # 2. Device Familiarity Counterfactual
            if new_ent.get("is_new_device"):
                counterfactuals.append({
                    "factor": "Device Fingerprint Baseline",
                    "condition": "Device had ≥2 prior authorized transactions in cardholder history",
                    "impact": "Eliminates new-device risk penalty (-15.0 pts), preventing automated card block.",
                    "flip_verdict": "uncertain",
                })

            # 3. Geographical Origin Counterfactual
            if geo.get("has_geo_anomaly") or new_ent.get("is_new_region"):
                counterfactuals.append({
                    "factor": "Billing Region Proximity",
                    "condition": f"Transaction billing region aligned with baseline regions ({typical_regions_str})",
                    "impact": "Eliminates geographic distance anomaly penalty (-20.0 pts) and impossible travel flag.",
                    "flip_verdict": "uncertain",
                })

            # 4. Device Sharing / Ring Counterfactual
            if sharing.get("is_shared"):
                distinct_cards = sharing.get("distinct_cards_count", 2)
                counterfactuals.append({
                    "factor": "Device Exclusivity",
                    "condition": "Device profile observed solely on this customer account",
                    "impact": f"Removes syndicate sharing flag ({distinct_cards} linked cards), downgrading from SAR requirement.",
                    "flip_verdict": "fraud (lower tier)",
                })

        elif verdict == "legitimate":
            # Target: What would turn verdict into fraud?
            counterfactuals.append({
                "factor": "Unrecognized Device / Proxy",
                "condition": "Transaction executed from anonymous VPN proxy or unknown mobile OS",
                "impact": "Would trigger Rule R1 step-up authentication challenge and elevate risk points by +30.0.",
                "flip_verdict": "uncertain",
            })
            counterfactuals.append({
                "factor": "Cross-Card Cluster Sharing",
                "condition": "Device or billing IP detected across ≥ 2 other compromised accounts",
                "impact": "Would trigger Rule R6 syndicate ring alert, escalating to immediate card hold.",
                "flip_verdict": "fraud",
            })

        else:
            # Uncertain verdict: What would settle it?
            counterfactuals.append({
                "factor": "Cardholder Response Settle",
                "condition": "Cardholder replies to validation SMS (Confirm vs Deny)",
                "impact": "Unambiguously resolves case to LEGITIMATE (if confirm) or CONFIRMED FRAUD (if deny).",
                "flip_verdict": "legitimate / fraud",
            })

        return counterfactuals

    @staticmethod
    def format_counterfactual_summary(counterfactuals: List[Dict[str, Any]]) -> str:
        """Formats counterfactual conditions into an analyst-readable string."""
        if not counterfactuals:
            return ""
        lines = ["Decision Sensitivity (Counterfactual Boundaries):"]
        for idx, cf in enumerate(counterfactuals, 1):
            lines.append(f"  {idx}. [{cf['factor']}]: {cf['condition']} -> {cf['impact']}")
        return "\n".join(lines)
