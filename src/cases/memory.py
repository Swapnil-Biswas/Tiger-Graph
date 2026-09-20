"""
Case Memory & Dynamic Bayesian Prior Adjustment Engine
Retrieves historical closed-case precedents strictly respecting temporal 'as_of' boundaries
and computes empirical Bayesian prior adjustments to calibrate agent uncertainty.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class BayesianCaseMemoryPrior:
    def __init__(self, client):
        self.client = client
        self.store = client.store

    def compute_prior(
        self,
        card_id: str,
        customer_id: Optional[str] = None,
        device_profile: Optional[str] = None,
        as_of: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes leak-free empirical Bayesian fraud prior from closed case memory.
        All query logic strictly enforces opened_at < as_of.
        """
        if not as_of:
            as_of = "9999-12-31 23:59:59"

        # 1. Historical Cases for Card & Customer
        historical_cases = []
        for cid, c in self.store.closed_cases.items():
            c_opened = str(c.get("opened_at", ""))
            # Strict temporal isolation check: must precede as_of
            if c_opened >= str(as_of):
                continue

            matches_card = card_id and c.get("card_id") == card_id
            matches_cust = customer_id and c.get("customer_id") == customer_id
            if matches_card or matches_cust:
                historical_cases.append(c)

        # 2. Historical Cases for Shared Device Profile
        device_prior_fraud = False
        if device_profile and device_profile != "None | None | None | None":
            dev_cards = set(self.store.cards_by_device.get(device_profile, []))
            for cid, c in self.store.closed_cases.items():
                c_opened = str(c.get("opened_at", ""))
                if c_opened < str(as_of) and c.get("card_id") in dev_cards:
                    if c.get("outcome") == "confirmed_fraud":
                        device_prior_fraud = True
                        break

        total_cases = len(historical_cases)
        confirmed_count = sum(1 for c in historical_cases if c.get("outcome") == "confirmed_fraud")
        cleared_count = sum(1 for c in historical_cases if c.get("outcome") == "cleared")

        # 3. Empirical Bayes Prior Smoothing (Beta-Binomial with alpha=1, beta=10 base rate)
        alpha_prior = 1.0
        beta_prior = 10.0
        base_rate = alpha_prior / (alpha_prior + beta_prior)
        posterior_prob = (confirmed_count + alpha_prior) / (total_cases + alpha_prior + beta_prior)

        # Calibrated risk delta adjustment
        risk_delta = 0.0
        if device_prior_fraud:
            risk_delta += 6.0
        if confirmed_count > 0:
            risk_delta += (posterior_prob - base_rate) * 20.0
        elif cleared_count > 0 and not device_prior_fraud:
            risk_delta -= min(10.0, cleared_count * 2.5)

        risk_delta = round(max(-10.0, min(12.0, risk_delta)), 1)

        return {
            "has_history": total_cases > 0 or device_prior_fraud,
            "total_prior_cases": total_cases,
            "confirmed_fraud_count": confirmed_count,
            "cleared_count": cleared_count,
            "device_prior_fraud": device_prior_fraud,
            "posterior_fraud_rate": round(posterior_prob, 3),
            "risk_delta": risk_delta,
            "prior_cases_cited": [c["case_id"] for c in historical_cases[:3]],
        }
