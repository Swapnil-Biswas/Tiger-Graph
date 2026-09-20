"""
Evidence Value-of-Information (VOI) Engine
Computes the expected information gain (entropy reduction) per unit cost across
candidate investigative inquiries, mathematically optimizing agent inquiry selection.
"""

import math
from typing import Dict, Any, List, Optional
from src.agent.state import Assessment, EvidenceRequest


def binary_entropy(p: float) -> float:
    """Computes binary Shannon entropy in bits for probability p in [0, 1]."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return - (p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


class ValueOfInformationEngine:
    """
    Ranks candidate investigative inquiries by Expected Information Gain per Cost (VOI).
    """

    # Estimated operational & customer friction costs (in USD)
    INQUIRY_COSTS = {
        "customer_validation": 0.05,  # SMS notification & minor customer friction
        "step_up_auth": 0.10,         # Step-up 2FA challenge & friction
        "analyst_info": 2.50,         # Human analyst queue & labor cost
    }

    @classmethod
    def evaluate_inquiries(
        cls,
        current_assessment: Assessment,
        trigger: Dict[str, Any],
        has_new_device: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Evaluates candidate inquiries and computes their Expected Value of Information.
        """
        p_prior = max(0.01, min(0.99, current_assessment.fraud_probability))
        h_prior = binary_entropy(p_prior)

        candidates = []

        # Candidate 1: Customer Validation (SMS outreach)
        # Expected outcomes:
        # P(confirm | legitimate) ~ 0.85, P(deny | fraud) ~ 0.90
        p_deny = p_prior * 0.90 + (1.0 - p_prior) * 0.10
        p_recognize = 1.0 - p_deny
        # Posterior if deny: ~0.98, Posterior if recognize: ~0.05
        h_post_deny = binary_entropy(0.98)
        h_post_rec = binary_entropy(0.05)
        expected_h_post_cust = (p_deny * h_post_deny) + (p_recognize * h_post_rec)
        delta_h_cust = max(0.0, h_prior - expected_h_post_cust)
        cost_cust = cls.INQUIRY_COSTS["customer_validation"]
        voi_cust = delta_h_cust / cost_cust

        candidates.append({
            "type": "customer_validation",
            "delta_entropy_bits": round(delta_h_cust, 3),
            "cost_usd": cost_cust,
            "voi_score": round(voi_cust, 2),
            "reason": "Cardholder inquiry has high expected entropy reduction (-{:.2f} bits) at low cost.".format(delta_h_cust),
            "recommended": True,
        })

        # Candidate 2: Step-Up Authentication (if online transaction / new device)
        if has_new_device or trigger.get("channel") == "online":
            p_fail = p_prior * 0.80 + (1.0 - p_prior) * 0.05
            p_pass = 1.0 - p_fail
            h_post_fail = binary_entropy(0.95)
            h_post_pass = binary_entropy(0.10)
            expected_h_post_step = (p_fail * h_post_fail) + (p_pass * h_post_pass)
            delta_h_step = max(0.0, h_prior - expected_h_post_step)
            cost_step = cls.INQUIRY_COSTS["step_up_auth"]
            voi_step = delta_h_step / cost_step

            candidates.append({
                "type": "step_up_auth",
                "delta_entropy_bits": round(delta_h_step, 3),
                "cost_usd": cost_step,
                "voi_score": round(voi_step, 2),
                "reason": "Step-up challenge provides cryptographic authentication with delta H = {:.2f} bits.".format(delta_h_step),
                "recommended": False,
            })

        # Candidate 3: Senior Analyst Review (high cost, high certainty)
        cost_analyst = cls.INQUIRY_COSTS["analyst_info"]
        delta_h_analyst = h_prior  # human analyst resolves ambiguity completely
        voi_analyst = delta_h_analyst / cost_analyst
        candidates.append({
            "type": "analyst_info",
            "delta_entropy_bits": round(delta_h_analyst, 3),
            "cost_usd": cost_analyst,
            "voi_score": round(voi_analyst, 2),
            "reason": "Manual analyst escalation offers complete uncertainty resolution but high operational cost.",
            "recommended": False,
        })

        # Sort candidates descending by VOI score
        candidates.sort(key=lambda c: c["voi_score"], reverse=True)
        # Mark highest VOI candidate as recommended
        for idx, c in enumerate(candidates):
            c["recommended"] = (idx == 0)

        return candidates

    @classmethod
    def select_best_inquiry(
        cls,
        current_assessment: Assessment,
        trigger: Dict[str, Any],
        has_new_device: bool = False,
    ) -> Optional[EvidenceRequest]:
        """
        Returns the optimal EvidenceRequest based on VOI ranking.
        """
        if current_assessment.sufficient_to_act and not current_assessment.is_ambiguous:
            return None

        candidates = cls.evaluate_inquiries(
            current_assessment, trigger, has_new_device=has_new_device
        )
        best = candidates[0]

        return EvidenceRequest(
            type=best["type"],
            asked_after_step=3,
            assumed_response="Customer states they did not make these purchases and still has the card",
            reason=f"Optimal VOI ({best['voi_score']} bits/$): {best['reason']}",
        )
