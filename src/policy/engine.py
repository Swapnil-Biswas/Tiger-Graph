"""
Policy and Permissions Engine
Deterministic policy verification for proposed fraud investigation actions.
Enforces rules R1 - R10, approval routing (auto, L1, L2), and action gates.
No LLM inside the decision loop.
"""

from typing import Dict, List, Any, Optional


class PolicyEngine:
    """
    Deterministic rule engine enforcing bank fraud policy.
    """

    @staticmethod
    def get_approval_route(action: str, exposure_usd: float = 0.0) -> str:
        """
        Determines the exact approval route per Section 2 of Fraud Policy:
        - auto: agent may act alone
        - L1: team lead must approve
        - L2: fraud manager must approve
        """
        action = action.upper().strip()
        if action == "DECLINE_TRANSACTION":
            return "L1"
        if action == "BLOCK_CARD":
            return "L1" if exposure_usd <= 2500.0 else "L2"
        if action in ["BLOCK_ALL_CARDS", "FILE_REPORT"]:
            return "L2"
        return "auto"

    @staticmethod
    def check(
        action: str,
        fraud_probability: float,
        exposure_usd: float,
        signal_count: int,
        evidence_claims: List[Dict[str, Any]],
        actor_role: str = "agent",
        confirmed_compromised_cards: int = 1,
        is_recurring_dispute: bool = False,
    ) -> Dict[str, Any]:
        """
        Validates action proposal against policy rules R1 - R10.
        Returns: {decision: 'allow' | 'needs_approval' | 'deny', route: 'auto' | 'L1' | 'L2', approver: str, reasons: list[str], policy_refs: list[str]}
        """
        action = action.upper().strip()
        route = PolicyEngine.get_approval_route(action, exposure_usd)
        reasons = []
        policy_refs = []

        # R1 Check: Weak / Single Signal Verify Before Block
        if action in ["BLOCK_CARD", "BLOCK_ALL_CARDS"]:
            if signal_count <= 1 and fraud_probability < 0.70:
                return {
                    "decision": "deny",
                    "route": route,
                    "approver": "None",
                    "reasons": ["Rule R1 Violation: Single signal with fraud probability < 0.70 requires VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block."],
                    "policy_refs": ["POLICY-R1"],
                }

        # R7 Check: Disputed recurring charge cannot be blocked immediately
        if is_recurring_dispute and action in ["BLOCK_CARD", "BLOCK_ALL_CARDS"]:
            return {
                "decision": "deny",
                "route": route,
                "approver": "None",
                "reasons": ["Rule R7 Violation: Charge matches cardholder's recurring history. Recommend VERIFY_WITH_CUSTOMER and WARN_CUSTOMER; do not block."],
                "policy_refs": ["POLICY-R7"],
            }

        # R10 Check: BLOCK_ALL_CARDS constraint
        if action == "BLOCK_ALL_CARDS":
            if confirmed_compromised_cards < 2:
                return {
                    "decision": "deny",
                    "route": route,
                    "approver": "None",
                    "reasons": ["Rule R10 Violation: BLOCK_ALL_CARDS requires at least two confirmed compromised cards or confirmed credential theft."],
                    "policy_refs": ["POLICY-R10"],
                }

        # Route Enforcement
        if route == "auto":
            return {
                "decision": "allow",
                "route": "auto",
                "approver": "AutomatedAgent",
                "reasons": ["Action permitted under automated agent delegation."],
                "policy_refs": ["POLICY-APPROVALS"],
            }
        elif route == "L1":
            approver = "Fraud Team Lead"
            decision = "allow" if actor_role in ["team_lead", "fraud_manager"] else "needs_approval"
            reasons.append(f"Requires approval from {approver} (exposure ${exposure_usd:.2f} <= $2,500).")
            policy_refs.append("POLICY-APPROVALS")
            return {
                "decision": decision,
                "route": "L1",
                "approver": approver,
                "reasons": reasons,
                "policy_refs": policy_refs,
            }
        else: # L2
            approver = "Fraud Manager"
            decision = "allow" if actor_role == "fraud_manager" else "needs_approval"
            reasons.append(f"Requires senior approval from {approver} (L2 threshold met).")
            policy_refs.append("POLICY-APPROVALS")
            return {
                "decision": decision,
                "route": "L2",
                "approver": approver,
                "reasons": reasons,
                "policy_refs": policy_refs,
            }
