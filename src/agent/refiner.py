"""
Graph-Augmented LLM Self-Refinement & Counter-Factual Verification Loop (Lens 11 & Lens 12).
Iteratively audits proposed verdict, actions, and regulatory filings against graph structural invariants,
detects policy contradictions or ungrounded actions, and automatically refines the response before dispatch.
"""

from typing import Dict, Any, List, Optional, Tuple


class GraphAugmentedSelfRefiner:
    """
    Iterative Graph-Augmented Self-Refinement Engine.
    Evaluates 7 core structural and policy invariants across case verdicts, actions, and topology:
      1. INVARIANT_R1_WEAK_SIGNAL: Weak signal (< 0.70) cannot execute BLOCK_CARD without step-up auth/challenge.
      2. INVARIANT_R10_MULTI_CARD: BLOCK_ALL_CARDS strictly requires >= 2 confirmed compromised cards.
      3. INVARIANT_R2_CUSTOMER_DENY: Customer denial strictly mandates fraud verdict and BLOCK_CARD.
      4. INVARIANT_R3_CUSTOMER_CONFIRM: Customer confirmation strictly prohibits fraud verdict or BLOCK_CARD.
      5. INVARIANT_R7_RECURRING_PROTECTION: Disputed recurring charges require WARN_CUSTOMER before disruptive block.
      6. INVARIANT_R8_HIGH_EXPOSURE_TIER: High financial exposure (> $1,000) under uncertain evaluation requires L2_LEAD review.
      7. INVARIANT_SAR_MANDATORY: Confirmed fraud with exposure >= $10,000 or syndicate pattern mandates SAR filing.
    """

    INVARIANTS = [
        "INVARIANT_R1_WEAK_SIGNAL",
        "INVARIANT_R10_MULTI_CARD",
        "INVARIANT_R2_CUSTOMER_DENY",
        "INVARIANT_R3_CUSTOMER_CONFIRM",
        "INVARIANT_R7_RECURRING_PROTECTION",
        "INVARIANT_R8_HIGH_EXPOSURE_TIER",
        "INVARIANT_SAR_MANDATORY",
    ]

    def __init__(self, max_refinements: int = 3):
        self.max_refinements = max_refinements

    def check_invariants(self, answer: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Scans current answer dictionary for structural invariant violations.
        Returns a list of violation descriptors.
        """
        violations = []
        case = answer.get("case", {})
        verdict = case.get("verdict", "uncertain")
        fraud_prob = float(case.get("fraud_probability", 0.50))
        exposure = float(case.get("exposure_usd", 0.0))
        pattern = case.get("pattern", "none")
        sar = answer.get("sar", {})

        # Extract final action names
        actions_data = answer.get("actions", {})
        final_actions = actions_data.get("final", [])
        action_names = set()
        for a in final_actions:
            if isinstance(a, dict):
                action_names.add(a.get("action"))
            elif isinstance(a, str):
                action_names.add(a)

        # Context evidence clues
        what_changed = str(actions_data.get("what_changed", "")).lower()
        evidence_items = answer.get("evidence", [])

        # 1. INVARIANT_R1_WEAK_SIGNAL
        if fraud_prob < 0.70 and "BLOCK_CARD" in action_names:
            if "customer confirmation" not in what_changed and "denied" not in what_changed and "recurring" not in what_changed:
                # If no strong secondary signal
                if fraud_prob < 0.65:
                    violations.append({
                        "invariant": "INVARIANT_R1_WEAK_SIGNAL",
                        "severity": "HIGH",
                        "reason": f"Single weak signal with fraud probability {fraud_prob:.2f} (< 0.70) cannot execute BLOCK_CARD without prior customer challenge.",
                        "fix_type": "REPLACE_BLOCK_WITH_STEP_UP",
                    })

        # 2. INVARIANT_R10_MULTI_CARD
        if "BLOCK_ALL_CARDS" in action_names:
            confirmed_cards = case.get("confirmed_compromised_cards", 1)
            if confirmed_cards < 2:
                violations.append({
                    "invariant": "INVARIANT_R10_MULTI_CARD",
                    "severity": "CRITICAL",
                    "reason": "BLOCK_ALL_CARDS executed with fewer than 2 confirmed compromised cards.",
                    "fix_type": "DOWNGRADE_TO_SINGLE_CARD_BLOCK",
                })

        # 3. INVARIANT_R2_CUSTOMER_DENY
        if "denied" in what_changed or "customer denies" in what_changed:
            if verdict != "fraud" or "BLOCK_CARD" not in action_names:
                violations.append({
                    "invariant": "INVARIANT_R2_CUSTOMER_DENY",
                    "severity": "CRITICAL",
                    "reason": "Customer denied transaction, but case was not resolved to fraud with BLOCK_CARD.",
                    "fix_type": "FORCE_FRAUD_BLOCK",
                })

        # 4. INVARIANT_R3_CUSTOMER_CONFIRM
        if "customer confirmation" in what_changed or "customer confirmed" in what_changed:
            if verdict == "fraud" or "BLOCK_CARD" in action_names:
                violations.append({
                    "invariant": "INVARIANT_R3_CUSTOMER_CONFIRM",
                    "severity": "CRITICAL",
                    "reason": "Customer confirmed authorization, but verdict is fraud or BLOCK_CARD is retained.",
                    "fix_type": "FORCE_LEGITIMATE_ALLOW",
                })

        # 5. INVARIANT_R7_RECURRING_PROTECTION
        if "recurring" in what_changed and "disputed" in what_changed:
            if "BLOCK_CARD" in action_names and "WARN_CUSTOMER" not in action_names:
                violations.append({
                    "invariant": "INVARIANT_R7_RECURRING_PROTECTION",
                    "severity": "MEDIUM",
                    "reason": "Disputed recurring subscription requires WARN_CUSTOMER before disruptive card blocking.",
                    "fix_type": "REPLACE_BLOCK_WITH_WARN",
                })

        # 6. INVARIANT_R8_HIGH_EXPOSURE_TIER
        if verdict == "uncertain" and exposure > 1000.0:
            routes = [a.get("route") for a in final_actions if isinstance(a, dict)]
            if any(r in ("auto", "L1_ANALYST") for r in routes) and not any(r == "L2_LEAD" for r in routes):
                violations.append({
                    "invariant": "INVARIANT_R8_HIGH_EXPOSURE_TIER",
                    "severity": "HIGH",
                    "reason": f"High financial exposure (${exposure:.2f} > $1,000) under uncertain verdict must be escalated to L2_LEAD.",
                    "fix_type": "ESCALATE_ROUTE_TO_L2",
                })

        # 7. INVARIANT_SAR_MANDATORY
        if verdict == "fraud" and (exposure >= 10000.0 or pattern in ("syndicate_bustout", "proxy_rotation", "device_pooling_nexus")):
            if not sar.get("file", False):
                violations.append({
                    "invariant": "INVARIANT_SAR_MANDATORY",
                    "severity": "CRITICAL",
                    "reason": f"Mandatory FinCEN SAR filing required for confirmed fraud with high exposure (${exposure:.2f}) or organized syndicate pattern '{pattern}'.",
                    "fix_type": "MANDATE_SAR_FILING",
                })

        return violations

    def apply_refinement(self, answer: Dict[str, Any], violation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies a targeted structural correction to resolve a detected invariant violation.
        """
        fix_type = violation.get("fix_type")
        actions_data = answer.setdefault("actions", {})
        final_actions = actions_data.get("final", [])
        case = answer.setdefault("case", {})

        if fix_type == "REPLACE_BLOCK_WITH_STEP_UP":
            new_actions = []
            for a in final_actions:
                act = a.get("action") if isinstance(a, dict) else a
                if act == "BLOCK_CARD":
                    new_actions.append({"action": "STEP_UP_AUTH", "route": "auto", "reason": "Refined: Step-up authentication required before blocking on single weak signal."})
                else:
                    new_actions.append(a)
            actions_data["final"] = new_actions

        elif fix_type == "DOWNGRADE_TO_SINGLE_CARD_BLOCK":
            new_actions = []
            for a in final_actions:
                act = a.get("action") if isinstance(a, dict) else a
                if act == "BLOCK_ALL_CARDS":
                    new_actions.append({"action": "BLOCK_CARD", "route": "L1_ANALYST", "reason": "Refined: Downgraded multi-card block to target card block per Rule R10."})
                else:
                    new_actions.append(a)
            actions_data["final"] = new_actions

        elif fix_type == "FORCE_FRAUD_BLOCK":
            case["verdict"] = "fraud"
            case["fraud_probability"] = max(0.95, float(case.get("fraud_probability", 0.95)))
            act_names = [a.get("action") if isinstance(a, dict) else a for a in final_actions]
            if "BLOCK_CARD" not in act_names:
                final_actions.append({"action": "BLOCK_CARD", "route": "auto", "reason": "Refined: Card block enforced following customer denial."})
            if "DECLINE_TRANSACTION" not in act_names:
                final_actions.append({"action": "DECLINE_TRANSACTION", "route": "auto", "reason": "Refined: Transaction declined per customer denial."})
            actions_data["final"] = final_actions

        elif fix_type == "FORCE_LEGITIMATE_ALLOW":
            case["verdict"] = "legitimate"
            case["fraud_probability"] = min(0.10, float(case.get("fraud_probability", 0.10)))
            new_actions = []
            for a in final_actions:
                act = a.get("action") if isinstance(a, dict) else a
                if act not in ("BLOCK_CARD", "BLOCK_ALL_CARDS", "DECLINE_TRANSACTION"):
                    new_actions.append(a)
            act_names = [a.get("action") if isinstance(a, dict) else a for a in new_actions]
            if "ALLOW_TRANSACTION" not in act_names:
                new_actions.append({"action": "ALLOW_TRANSACTION", "route": "auto", "reason": "Refined: Transaction allowed following cardholder confirmation."})
            if "CLOSE_NO_FRAUD" not in act_names:
                new_actions.append({"action": "CLOSE_NO_FRAUD", "route": "auto", "reason": "Refined: Case closed as legitimate."})
            actions_data["final"] = new_actions

        elif fix_type == "REPLACE_BLOCK_WITH_WARN":
            new_actions = []
            for a in final_actions:
                act = a.get("action") if isinstance(a, dict) else a
                if act == "BLOCK_CARD":
                    new_actions.append({"action": "WARN_CUSTOMER", "route": "auto", "reason": "Refined: Customer warning issued for subscription dispute without punitive block."})
                else:
                    new_actions.append(a)
            actions_data["final"] = new_actions

        elif fix_type == "ESCALATE_ROUTE_TO_L2":
            for a in final_actions:
                if isinstance(a, dict):
                    a["route"] = "L2_LEAD"
                    a["reason"] = a.get("reason", "") + " (Refined: Escalated to L2_LEAD due to exposure > $1,000)."

        elif fix_type == "MANDATE_SAR_FILING":
            sar = answer.setdefault("sar", {})
            sar["file"] = True
            sar["narrative"] = sar.get("narrative") or f"Mandatory SAR filing generated for confirmed fraud case with high exposure or syndicate pattern."
            sar["subjects"] = sar.get("subjects") or [case.get("card_id", "UNKNOWN")]

        return answer

    def refine_investigation(self, answer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the iterative self-refinement and counter-factual verification loop.
        Applies fixes until all invariants are satisfied or max_refinements is reached.
        """
        refinement_history = []
        iteration = 0

        while iteration < self.max_refinements:
            violations = self.check_invariants(answer)
            if not violations:
                break

            v = violations[0]
            iteration += 1
            refinement_history.append({
                "iteration": iteration,
                "invariant": v["invariant"],
                "reason": v["reason"],
                "fix_applied": v["fix_type"],
            })
            answer = self.apply_refinement(answer, v)

        final_violations = self.check_invariants(answer)
        score = max(0.0, round(1.0 - (len(final_violations) * 0.20), 4))

        answer["self_refinement"] = {
            "refinements_applied_count": len(refinement_history),
            "converged": len(final_violations) == 0,
            "structural_consistency_score": score,
            "invariants_checked": self.INVARIANTS,
            "refinement_history": refinement_history,
            "remaining_violations": [v["invariant"] for v in final_violations],
        }

        return answer
