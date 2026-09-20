"""
Next-Best-Action Decision Engine
Determines policy-compliant recommended actions both before (initial) and after (final)
evidence collection, enforcing approval routing (auto, L1, L2) and Rule R1 - R10 citations.
"""

from typing import List, Dict, Any, Optional
from src.agent.state import Assessment, ProposedAction, EvidenceRequest
from src.policy.engine import PolicyEngine


class NextBestActionPlanner:

    @staticmethod
    def plan_initial_actions(
        assessment: Assessment,
        trigger: Dict[str, Any],
        exposure_usd: float,
        is_shared_device: bool = False,
    ) -> List[ProposedAction]:
        actions = []
        prob = assessment.fraud_probability
        pattern = assessment.pattern

        # Scenario 1: Ambiguous / Low Confidence on Single Signal (Rule R1)
        if assessment.is_ambiguous or (prob < 0.70 and not assessment.sufficient_to_act):
            actions.append(ProposedAction(
                action="VERIFY_WITH_CUSTOMER",
                route="auto",
                reason="R1: Assessed fraud probability is below 0.70 on weak/single signal; confirm with cardholder before any blocking action.",
            ))
            if prob >= 0.30:
                actions.append(ProposedAction(
                    action="CREATE_CASE",
                    route="auto",
                    reason="Section 3a: Internal fraud case created pending customer verification.",
                ))
            return actions

        # Scenario 2: Card Testing Detected (Rule R5)
        if pattern == "card_testing":
            actions.append(ProposedAction(
                action="DECLINE_TRANSACTION",
                route="L1",
                reason="R5: Card testing sequence observed with rapid micro-authorizations.",
            ))
            actions.append(ProposedAction(
                action="STEP_UP_AUTH",
                route="auto",
                reason="R5: Require step-up authentication challenge before further activity.",
            ))
            return actions

        # Scenario 3: High Risk Confirmed Fraud (Rule R2, R6)
        if prob >= 0.70:
            route_block = PolicyEngine.get_approval_route("BLOCK_CARD", exposure_usd)
            actions.append(ProposedAction(
                action="BLOCK_CARD",
                route=route_block,
                reason=f"R2: High probability unauthorized activity ({prob:.2f}); exposure ${exposure_usd:.2f}.",
            ))
            actions.append(ProposedAction(
                action="CREATE_CASE",
                route="auto",
                reason="Section 3a: Formal fraud case opened with evidence attached.",
            ))
            if exposure_usd > 1000.0 or is_shared_device or pattern == "undocumented":
                actions.append(ProposedAction(
                    action="FILE_REPORT",
                    route="L2",
                    reason=f"Section 3a & R2: Regulatory SAR required (exposure ${exposure_usd:.2f} > $1,000 or shared device origin).",
                ))
            if is_shared_device:
                actions.append(ProposedAction(
                    action="MONITOR_CONNECTED_CARDS",
                    route="auto",
                    reason="R6: Compromised device profile shared with other cards.",
                ))
            return actions

        # Scenario 4: Legitimate / False Alarm
        actions.append(ProposedAction(
            action="ALLOW_TRANSACTION",
            route="auto",
            reason="Activity consistent with customer normal spending habits.",
        ))
        actions.append(ProposedAction(
            action="CLOSE_NO_FRAUD",
            route="auto",
            reason="R3: Alert cleared as legitimate activity.",
        ))
        return actions

    @staticmethod
    def plan_evidence_request(assessment: Assessment, trigger: Dict[str, Any]) -> Optional[EvidenceRequest]:
        if assessment.sufficient_to_act and not assessment.is_ambiguous:
            return None

        # Determine best inquiry
        if trigger.get("trigger_type") == "customer_report":
            # Customer already initiated, ask for validation of specific cards
            return EvidenceRequest(
                type="customer_validation",
                asked_after_step=3,
                assumed_response="Customer states they did not make these purchases and still has the card",
                reason="R1: Cardholder inquiry to verify transaction legitimacy.",
            )
        else:
            return EvidenceRequest(
                type="customer_validation",
                asked_after_step=3,
                assumed_response="Customer states they did not make these purchases and still has the card",
                reason="R1: Ambiguous risk score requires cardholder validation before permanent card block.",
            )

    @staticmethod
    def plan_final_actions(
        initial_actions: List[ProposedAction],
        post_assessment: Assessment,
        trigger: Dict[str, Any],
        exposure_usd: float,
        evidence_response: Optional[Dict[str, Any]] = None,
        is_shared_device: bool = False,
    ) -> Tuple[List[ProposedAction], str]:
        if not evidence_response:
            return initial_actions, "nothing"

        scenario = evidence_response.get("scenario", "")
        post_prob = post_assessment.fraud_probability
        final_actions = []

        # 1. Customer Denies
        if scenario == "denies":
            route_block = PolicyEngine.get_approval_route("BLOCK_CARD", exposure_usd)
            final_actions.append(ProposedAction(
                action="BLOCK_CARD",
                route=route_block,
                reason=f"R2: Customer confirmed unauthorized activity; exposure ${exposure_usd:.2f}.",
            ))
            final_actions.append(ProposedAction(
                action="CREATE_CASE",
                route="auto",
                reason="R2: Formal internal fraud case created.",
            ))
            if exposure_usd > 1000.0 or is_shared_device:
                final_actions.append(ProposedAction(
                    action="FILE_REPORT",
                    route="L2",
                    reason=f"R2 & Section 3a: SAR required (exposure ${exposure_usd:.2f} or shared origin).",
                ))
            if is_shared_device:
                final_actions.append(ProposedAction(
                    action="MONITOR_CONNECTED_CARDS",
                    route="auto",
                    reason="R6: Shared device profile also observed on connected cards.",
                ))
            what_changed = f"Customer denial raised fraud probability to {post_prob:.2f}, confirming immediate card block and case escalation."

        # 2. Step-Up Authentication Failed (Rule R5)
        elif scenario == "step_up_fail":
            route_block = PolicyEngine.get_approval_route("BLOCK_CARD", exposure_usd)
            final_actions.append(ProposedAction(
                action="BLOCK_CARD",
                route=route_block,
                reason=f"R5: Step-up authentication failed; defensive block executed on exposure ${exposure_usd:.2f}.",
            ))
            final_actions.append(ProposedAction(
                action="DECLINE_TRANSACTION",
                route="L1",
                reason="R5: Decline transaction following failed identity challenge.",
            ))
            final_actions.append(ProposedAction(
                action="CREATE_CASE",
                route="auto",
                reason="Section 3a: Internal fraud case opened following authentication failure.",
            ))
            if exposure_usd > 1000.0 or is_shared_device:
                final_actions.append(ProposedAction(
                    action="FILE_REPORT",
                    route="L2",
                    reason=f"Section 3a & R5: Regulatory SAR required for high exposure failed challenge.",
                ))
            what_changed = f"Step-up authentication challenge failed, raising fraud probability to {post_prob:.2f} and triggering immediate card block and transaction decline under Rule R5."

        # 3. Disputed Recurring / Legitimate Subscription (Rule R7)
        elif scenario == "recurring_confirmed":
            final_actions.append(ProposedAction(
                action="CREATE_CASE",
                route="auto",
                reason="R7: Case logged for recurring subscription dispute record.",
            ))
            final_actions.append(ProposedAction(
                action="WARN_CUSTOMER",
                route="auto",
                reason="R7: Inform cardholder of active recurring billing subscription details.",
            ))
            final_actions.append(ProposedAction(
                action="ALLOW_TRANSACTION",
                route="auto",
                reason="R7: Transaction permitted as recognized subscription.",
            ))
            what_changed = "Cardholder identified transaction as recognized recurring charge. Avoided card block and issued customer subscription advisory under Rule R7."

        # 4. Customer Confirms / Recognized / Step-Up Pass (Rule R3)
        elif scenario in ["recognizes", "step_up_pass"]:
            final_actions.append(ProposedAction(
                action="ALLOW_TRANSACTION",
                route="auto",
                reason="R3: Customer confirmed transaction as authorized.",
            ))
            final_actions.append(ProposedAction(
                action="CLOSE_NO_FRAUD",
                route="auto",
                reason="R3: Verification confirmed false alarm; alert closed without fraud.",
            ))
            what_changed = f"Customer confirmation reduced fraud probability to {post_prob:.2f}, resolving the alert as legitimate and clearing the case."

        # 5. No Reply within 24h (Rule R4)
        else:
            final_actions.append(ProposedAction(
                action="DECLINE_TRANSACTION",
                route="L1",
                reason="R4: No cardholder response within 24 hours; decline pending transaction.",
            ))
            final_actions.append(ProposedAction(
                action="MONITOR_CARD",
                route="auto",
                reason="R4: Elevate card monitoring sensitivity for 72 hours.",
            ))
            if exposure_usd > 500.0:
                final_actions.append(ProposedAction(
                    action="ESCALATE_TO_ANALYST",
                    route="auto",
                    reason="R4 & R8: Unresolved case with exposure exceeding $500.",
                ))
            what_changed = "No customer reply within 24 hours triggered defensive transaction decline and elevated card monitoring under Rule R4."

        return final_actions, what_changed
