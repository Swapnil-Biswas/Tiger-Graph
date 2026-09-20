"""
Counterfactual Scenario Playground & Policy Simulation Engine (src/graph/simulation.py)
Allows fraud analysts, compliance officers, and automated policy tuners to simulate
"what-if" topological perturbations (amount scaling, transaction injection, device
unlinking, high-risk MCC reclassification, customer challenge responses) and evaluate
the exact causal impact across Fraud, AML, Cyber, and next-best-action decision boundaries.
"""

import time
import copy
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union, Tuple


@dataclass
class ScenarioPerturbation:
    """
    Specification of synthetic or counterfactual perturbations applied to an investigation.
    """
    case_id: str
    amount_multiplier: float = 1.0
    override_amount: Optional[float] = None
    inject_transactions: List[Dict[str, Any]] = field(default_factory=list)
    unlink_devices: List[str] = field(default_factory=list)
    unlink_ip_addresses: List[str] = field(default_factory=list)
    override_mcc: Optional[str] = None
    simulated_customer_response: Optional[str] = None  # "CONFIRM_LEGITIMATE", "CONFIRM_FRAUD", "NO_RESPONSE", "STEP_UP_FAILED"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioSimulationReport:
    """
    Comprehensive counterfactual simulation report contrasting baseline vs. perturbed state.
    """
    simulation_id: str
    case_id: str
    timestamp: float
    perturbation: Dict[str, Any]
    baseline: Dict[str, Any]
    simulated: Dict[str, Any]
    delta: Dict[str, Any]
    causal_drivers: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


SIMULATION_TEMPLATES = {
    "BELOW_BSA_THRESHOLD": {
        "template_id": "BELOW_BSA_THRESHOLD",
        "name": "Below BSA Structuring Threshold ($10,000)",
        "description": "Reduces cumulative transaction exposure to $8,500, evaluating whether mandatory FinCEN SAR filing drops.",
        "params": {"override_amount": 8500.0, "notes": "Simulated spend strictly under 31 USC 5324(a) $10,000 reporting threshold."},
    },
    "DEVICE_UNLINKING": {
        "template_id": "DEVICE_UNLINKING",
        "name": "Isolate & Unlink Suspicious Hardware Profile",
        "description": "Simulates severing all shared device edges, testing if syndicate hardware clustering de-escalates.",
        "params": {"unlink_devices": ["ALL_SHARED"], "notes": "Simulated hardware sanitization eliminating device sharing nexus."},
    },
    "VELOCITY_SURGE": {
        "template_id": "VELOCITY_SURGE",
        "name": "High-Frequency Automated Bot Velocity Burst",
        "description": "Injects 8 rapid-fire micro-transactions within a 3-minute window to test cyber burst anomaly detection.",
        "params": {
            "inject_transactions": [
                {"TransactionAmt": 15.0, "time_offset_s": i * 20} for i in range(8)
            ],
            "notes": "Simulated bot dictionary testing burst attack.",
        },
    },
    "HIGH_RISK_MCC_6051": {
        "template_id": "HIGH_RISK_MCC_6051",
        "name": "Quasi-Cash / Crypto Exchange MCC Pivot",
        "description": "Reclassifies merchant to quasi-cash MCC 6051 (crypto/wire), testing AML velocity and SAR multipliers.",
        "params": {"override_mcc": "6051", "notes": "Simulated high-risk quasi-cash merchant category."},
    },
    "CUSTOMER_CONFIRMED_LEGITIMATE": {
        "template_id": "CUSTOMER_CONFIRMED_LEGITIMATE",
        "name": "Cardholder Positive Authorization Confirmation",
        "description": "Simulates customer confirming transaction validity via two-factor mobile challenge flow.",
        "params": {"simulated_customer_response": "CONFIRM_LEGITIMATE", "notes": "Simulated positive two-factor verification response."},
    },
    "CUSTOMER_CONFIRMED_FRAUD": {
        "template_id": "CUSTOMER_CONFIRMED_FRAUD",
        "name": "Cardholder Stolen Credential / Fraud Confirmation",
        "description": "Simulates customer reporting card stolen or transaction unrecognized.",
        "params": {"simulated_customer_response": "CONFIRM_FRAUD", "notes": "Simulated negative cardholder dispute response."},
    },
}


class GraphScenarioSimulator:
    """
    Counterfactual scenario simulation engine executing topological and behavioral
    perturbations over the agentic investigation pipeline.
    """

    def __init__(self, agent: Optional[Any] = None):
        self.agent = agent

    def list_templates(self) -> List[Dict[str, Any]]:
        """Returns catalog of available simulation scenario templates."""
        return list(SIMULATION_TEMPLATES.values())

    def simulate_scenario(self, perturbation: ScenarioPerturbation) -> ScenarioSimulationReport:
        """
        Executes a counterfactual simulation comparing baseline investigation against perturbed graph state.
        """
        if not self.agent:
            from src.agent.graph import FraudInvestigatorAgent
            self.agent = FraudInvestigatorAgent()

        case_id = perturbation.case_id

        # 1. Baseline Investigation
        baseline_answer = self.agent.investigate_case(case_id)
        base_case = baseline_answer.get("case", {})
        base_aml = baseline_answer.get("aml_specialist", {})
        base_cyber = baseline_answer.get("cyber_forensics", {})
        base_actions = [
            a.get("action", a) if isinstance(a, dict) else a
            for a in baseline_answer.get("next_best_actions", {}).get("final", [])
        ]
        base_consensus = baseline_answer.get("federated_consensus", {})

        baseline_summary = {
            "fraud_probability": float(base_case.get("fraud_probability", 0.50)),
            "verdict": str(base_case.get("verdict", "review")),
            "exposure_usd": float(base_case.get("exposure_usd", 0.0)),
            "aml_score": float(base_aml.get("aml_score", 0.0)),
            "aml_risk_level": str(base_aml.get("risk_level", "LOW")),
            "mandatory_sar": bool(base_aml.get("mandatory_sar", False) or baseline_answer.get("sar", {}).get("file", False)),
            "cyber_risk_score": float(base_cyber.get("cyber_risk_score", 0.0)),
            "cyber_threat_tier": str(base_cyber.get("threat_tier", "LOW")),
            "consensus_verdict": str(base_consensus.get("consensus_verdict", base_case.get("verdict", "review"))),
            "consensus_probability": float(base_consensus.get("consensus_probability", base_case.get("fraud_probability", 0.50))),
            "actions": base_actions,
        }

        # 2. Compute Simulated Counterfactual State
        sim_case = copy.deepcopy(base_case)
        sim_aml = copy.deepcopy(base_aml)
        sim_cyber = copy.deepcopy(base_cyber)
        sim_actions = list(base_actions)
        causal_drivers = []

        # A. Amount Perturbation
        sim_exposure = baseline_summary["exposure_usd"]
        if perturbation.override_amount is not None:
            sim_exposure = float(perturbation.override_amount)
            causal_drivers.append(f"Transaction exposure manually overridden to ${sim_exposure:,.2f}")
        elif perturbation.amount_multiplier != 1.0:
            sim_exposure = round(sim_exposure * perturbation.amount_multiplier, 2)
            causal_drivers.append(f"Exposure scaled by multiplier {perturbation.amount_multiplier:.2f}x to ${sim_exposure:,.2f}")

        # B. AML Structuring Impact
        sim_mandatory_sar = baseline_summary["mandatory_sar"]
        sim_aml_score = baseline_summary["aml_score"]
        sim_aml_risk = baseline_summary["aml_risk_level"]

        if sim_exposure < 10000.0 and baseline_summary["exposure_usd"] >= 10000.0:
            sim_mandatory_sar = False
            sim_aml_score = max(0.10, sim_aml_score - 0.45)
            sim_aml_risk = "LOW" if sim_aml_score < 0.35 else "MEDIUM"
            if "FILE_SAR_FINCEN" in sim_actions:
                sim_actions.remove("FILE_SAR_FINCEN")
            causal_drivers.append("Exposure dropped below $10,000 BSA threshold: Mandatory FinCEN SAR filing eliminated.")
        elif sim_exposure >= 10000.0 and baseline_summary["exposure_usd"] < 10000.0:
            sim_mandatory_sar = True
            sim_aml_score = min(1.0, sim_aml_score + 0.50)
            sim_aml_risk = "HIGH"
            if "FILE_SAR_FINCEN" not in sim_actions:
                sim_actions.append("FILE_SAR_FINCEN")
            causal_drivers.append("Exposure exceeded $10,000 BSA threshold: Mandatory FinCEN SAR filing triggered.")

        # C. High-Risk MCC Reclassification
        if perturbation.override_mcc:
            mcc = str(perturbation.override_mcc)
            causal_drivers.append(f"Merchant MCC reclassified to {mcc}")
            if mcc in ["6051", "6011", "7995", "4829"]:
                sim_aml_score = min(1.0, sim_aml_score + 0.30)
                sim_aml_risk = "HIGH" if sim_aml_score > 0.65 else "MEDIUM"
                if "STEP_UP_AUTH" not in sim_actions and "ALLOW_TRANSACTION" in sim_actions:
                    sim_actions.remove("ALLOW_TRANSACTION")
                    sim_actions.append("STEP_UP_AUTH")
                causal_drivers.append("High-risk quasi-cash MCC detected: Adaptive velocity and step-up auth triggered.")

        # D. Device Unlinking
        sim_cyber_threat = baseline_summary["cyber_threat_tier"]
        sim_cyber_score = baseline_summary["cyber_risk_score"]
        if perturbation.unlink_devices:
            sim_cyber_score = max(0.05, sim_cyber_score - 0.55)
            sim_cyber_threat = "LOW"
            sim_actions = [a for a in sim_actions if a != "ISOLATE_HARDWARE_FINGERPRINT"]
            causal_drivers.append(f"Unlinked devices {perturbation.unlink_devices}: Device sharing nexus dissolved, cyber threat tier downgraded to LOW.")

        # E. Injected Transactions (Bot Velocity Burst)
        if perturbation.inject_transactions:
            injected_count = len(perturbation.inject_transactions)
            sim_cyber_score = min(1.0, sim_cyber_score + 0.60)
            sim_cyber_threat = "CRITICAL"
            if "BLOCK_CARD" not in sim_actions:
                sim_actions.append("BLOCK_CARD")
            if "ISOLATE_HARDWARE_FINGERPRINT" not in sim_actions:
                sim_actions.append("ISOLATE_HARDWARE_FINGERPRINT")
            if "ALLOW_TRANSACTION" in sim_actions:
                sim_actions.remove("ALLOW_TRANSACTION")
            causal_drivers.append(f"Injected {injected_count} rapid transactions: Automated bot velocity burst threshold triggered.")

        # F. Customer Challenge Response
        sim_fraud_prob = baseline_summary["fraud_probability"]
        sim_verdict = baseline_summary["verdict"]

        if perturbation.simulated_customer_response == "CONFIRM_LEGITIMATE":
            sim_fraud_prob = min(0.12, sim_fraud_prob * 0.15)
            sim_verdict = "legitimate"
            sim_actions = ["ALLOW_TRANSACTION", "CLOSE_NO_FRAUD"]
            causal_drivers.append("Cardholder confirmed valid transaction authorization: Fraud probability collapsed to ≤ 0.12.")
        elif perturbation.simulated_customer_response == "CONFIRM_FRAUD":
            sim_fraud_prob = max(0.95, sim_fraud_prob * 1.25)
            sim_verdict = "fraud"
            sim_actions = ["BLOCK_CARD", "DECLINE_TRANSACTION", "CREATE_CASE"]
            causal_drivers.append("Cardholder reported unauthorized fraud/credential theft: Case escalated to confirmed fraud.")
        elif perturbation.simulated_customer_response == "STEP_UP_FAILED":
            sim_fraud_prob = max(0.85, sim_fraud_prob + 0.30)
            sim_verdict = "fraud"
            sim_actions = ["BLOCK_CARD", "DECLINE_TRANSACTION", "CREATE_CASE"]
            causal_drivers.append("Cardholder two-factor step-up authentication failed: High risk of account takeover.")
        elif perturbation.simulated_customer_response == "NO_RESPONSE":
            sim_actions = ["DECLINE_TRANSACTION", "MONITOR_CARD"]
            causal_drivers.append("Cardholder did not respond to challenge: Provisional transaction decline enforced.")

        # Re-derive consensus probability & verdict
        sim_consensus_prob = round(float(sim_fraud_prob * 0.50 + sim_aml_score * 0.30 + sim_cyber_score * 0.20), 4)
        if sim_mandatory_sar:
            sim_consensus_verdict = "aml_escalation"
        elif sim_consensus_prob >= 0.70:
            sim_consensus_verdict = "fraud"
        elif sim_consensus_prob <= 0.30:
            sim_consensus_verdict = "legitimate"
        else:
            sim_consensus_verdict = "review"

        simulated_summary = {
            "fraud_probability": round(float(sim_fraud_prob), 4),
            "verdict": sim_verdict,
            "exposure_usd": sim_exposure,
            "aml_score": round(float(sim_aml_score), 4),
            "aml_risk_level": sim_aml_risk,
            "mandatory_sar": sim_mandatory_sar,
            "cyber_risk_score": round(float(sim_cyber_score), 4),
            "cyber_threat_tier": sim_cyber_threat,
            "consensus_verdict": sim_consensus_verdict,
            "consensus_probability": sim_consensus_prob,
            "actions": sorted(list(set(sim_actions))),
        }

        # 3. Delta Computation
        actions_added = [a for a in simulated_summary["actions"] if a not in baseline_summary["actions"]]
        actions_removed = [a for a in baseline_summary["actions"] if a not in simulated_summary["actions"]]
        actions_retained = [a for a in simulated_summary["actions"] if a in baseline_summary["actions"]]

        delta = {
            "fraud_probability_delta": round(simulated_summary["fraud_probability"] - baseline_summary["fraud_probability"], 4),
            "aml_score_delta": round(simulated_summary["aml_score"] - baseline_summary["aml_score"], 4),
            "cyber_risk_score_delta": round(simulated_summary["cyber_risk_score"] - baseline_summary["cyber_risk_score"], 4),
            "verdict_flipped": simulated_summary["verdict"] != baseline_summary["verdict"],
            "sar_status_flipped": simulated_summary["mandatory_sar"] != baseline_summary["mandatory_sar"],
            "threat_tier_flipped": simulated_summary["cyber_threat_tier"] != baseline_summary["cyber_threat_tier"],
            "consensus_verdict_flipped": simulated_summary["consensus_verdict"] != baseline_summary["consensus_verdict"],
            "actions_added": actions_added,
            "actions_removed": actions_removed,
            "actions_retained": actions_retained,
            "financial_exposure_delta_usd": round(simulated_summary["exposure_usd"] - baseline_summary["exposure_usd"], 2),
        }

        return ScenarioSimulationReport(
            simulation_id=f"SIM-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}",
            case_id=case_id,
            timestamp=time.time(),
            perturbation=perturbation.to_dict(),
            baseline=baseline_summary,
            simulated=simulated_summary,
            delta=delta,
            causal_drivers=causal_drivers or ["Default simulation pass: no impactful perturbations."],
        )

    def apply_template(self, case_id: str, template_id: str) -> ScenarioSimulationReport:
        """Applies a pre-configured template perturbation to a case."""
        template = SIMULATION_TEMPLATES.get(template_id)
        if not template:
            raise ValueError(f"Unknown simulation template '{template_id}'. Available: {list(SIMULATION_TEMPLATES.keys())}")

        params = copy.deepcopy(template.get("params", {}))
        perturbation = ScenarioPerturbation(
            case_id=case_id,
            override_amount=params.get("override_amount"),
            amount_multiplier=params.get("amount_multiplier", 1.0),
            unlink_devices=params.get("unlink_devices", []),
            inject_transactions=params.get("inject_transactions", []),
            override_mcc=params.get("override_mcc"),
            simulated_customer_response=params.get("simulated_customer_response"),
            notes=params.get("notes", ""),
        )
        return self.simulate_scenario(perturbation)
