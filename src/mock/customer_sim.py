"""
Customer & Analyst Interaction Simulator
Provides deterministic simulation of customer validation and step-up auth inquiries.
"""

from typing import Dict, Any, Optional


class CustomerSimulator:
    """
    Simulates cardholder or analyst responses for benchmark evaluation and testing.
    """

    RESPONSES = {
        ("customer_validation", "denies"): "Customer states they did not make these purchases and still has the card",
        ("customer_validation", "recognizes"): "Customer confirms they made this purchase while traveling and still has possession of the card",
        ("customer_validation", "recurring_confirmed"): "Customer confirms this is their monthly recurring subscription service",
        ("customer_validation", "no_response"): "No reply received from cardholder within 24 hours of notification",
        ("step_up_auth", "step_up_pass"): "Cardholder successfully completed one-time passcode SMS challenge",
        ("step_up_auth", "step_up_fail"): "Step-up authentication challenge failed after multiple expired attempts",
        ("analyst_info", "confirmed"): "Senior analyst confirms compromised credential batch matches current device signature",
    }

    @classmethod
    def simulate_response(
        cls,
        request_type: str = "customer_validation",
        scenario: str = "denies",
    ) -> Dict[str, Any]:
        key = (request_type, scenario)
        response_text = cls.RESPONSES.get(key, f"Cardholder provided response for {request_type} under scenario {scenario}")
        return {
            "type": request_type,
            "scenario": scenario,
            "assumed_response": response_text,
            "responded": scenario != "no_response",
        }
