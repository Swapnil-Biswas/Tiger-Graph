"""
Unit Test Suite for Counterfactual Scenario Playground & Policy Simulation Engine (tests/test_graph_simulation.py)
Tests what-if topological perturbations, template applications, causal driver reporting,
exposure scaling, device unlinking, velocity burst injection, customer challenge flips,
and REST API endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from src.graph.simulation import (
    GraphScenarioSimulator,
    ScenarioPerturbation,
    SIMULATION_TEMPLATES,
)
from src.agent.graph import FraudInvestigatorAgent
from src.api.main import app


class TestGraphScenarioSimulator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Graph Scenario Simulator Test Suite ===")
        cls.agent = FraudInvestigatorAgent()
        cls.simulator = GraphScenarioSimulator(agent=cls.agent)

    def test_list_templates(self):
        """Verify simulation scenario templates are registered and cataloged."""
        templates = self.simulator.list_templates()
        self.assertEqual(len(templates), 6)
        template_ids = {t["template_id"] for t in templates}
        self.assertIn("BELOW_BSA_THRESHOLD", template_ids)
        self.assertIn("DEVICE_UNLINKING", template_ids)
        self.assertIn("VELOCITY_SURGE", template_ids)
        self.assertIn("HIGH_RISK_MCC_6051", template_ids)
        self.assertIn("CUSTOMER_CONFIRMED_LEGITIMATE", template_ids)
        self.assertIn("CUSTOMER_CONFIRMED_FRAUD", template_ids)
        print("PASS: Simulation templates catalog verified.")

    def test_customer_confirmation_flip(self):
        """Verify customer confirmation collapses fraud probability and flips verdict to legitimate."""
        report = self.simulator.apply_template(case_id="HHG-001", template_id="CUSTOMER_CONFIRMED_LEGITIMATE")

        self.assertLessEqual(report.simulated["fraud_probability"], 0.12)
        self.assertEqual(report.simulated["verdict"], "legitimate")
        self.assertIn("ALLOW_TRANSACTION", report.simulated["actions"])
        self.assertIn("CLOSE_NO_FRAUD", report.simulated["actions"])
        self.assertTrue(report.delta["verdict_flipped"])
        self.assertGreater(len(report.causal_drivers), 0)
        print("PASS: Customer positive authorization counterfactual flip verified.")

    def test_customer_confirmed_fraud(self):
        """Verify cardholder fraud report escalates probability to near 1.0 and blocks card."""
        report = self.simulator.apply_template(case_id="HHG-001", template_id="CUSTOMER_CONFIRMED_FRAUD")

        self.assertGreaterEqual(report.simulated["fraud_probability"], 0.95)
        self.assertEqual(report.simulated["verdict"], "fraud")
        self.assertIn("BLOCK_CARD", report.simulated["actions"])
        self.assertIn("DECLINE_TRANSACTION", report.simulated["actions"])
        print("PASS: Cardholder confirmed fraud dispute escalation verified.")

    def test_device_unlinking_simulation(self):
        """Verify unlinking shared devices reduces cyber risk score and threat tier."""
        report = self.simulator.apply_template(case_id="HHG-001", template_id="DEVICE_UNLINKING")

        self.assertEqual(report.simulated["cyber_threat_tier"], "LOW")
        self.assertLessEqual(report.simulated["cyber_risk_score"], 0.50)
        self.assertIn("unlink", report.causal_drivers[0].lower())
        print("PASS: Device unlinking and hardware threat de-escalation verified.")

    def test_velocity_surge_bot_burst(self):
        """Verify injected rapid-fire transactions escalate cyber threat tier to CRITICAL."""
        report = self.simulator.apply_template(case_id="HHG-001", template_id="VELOCITY_SURGE")

        self.assertEqual(report.simulated["cyber_threat_tier"], "CRITICAL")
        self.assertGreaterEqual(report.simulated["cyber_risk_score"], 0.60)
        self.assertIn("BLOCK_CARD", report.simulated["actions"])
        self.assertTrue(any("bot velocity burst" in d.lower() for d in report.causal_drivers))
        print("PASS: Velocity surge and bot burst anomaly simulation verified.")

    def test_high_risk_mcc_pivot(self):
        """Verify merchant MCC reclassification to 6051 increases AML score and triggers step-up auth."""
        report = self.simulator.apply_template(case_id="HHG-001", template_id="HIGH_RISK_MCC_6051")

        self.assertGreater(report.simulated["aml_score"], report.baseline["aml_score"])
        self.assertTrue(any("quasi-cash" in d.lower() for d in report.causal_drivers))
        print("PASS: High-risk quasi-cash MCC pivot simulation verified.")

    def test_custom_perturbation_and_fastapi_endpoints(self):
        """Verify custom perturbation spec execution and FastAPI simulation endpoints."""
        client = TestClient(app)

        # 1. Get templates
        resp_t = client.get("/api/simulation/templates")
        self.assertEqual(resp_t.status_code, 200)
        self.assertEqual(len(resp_t.json()), 6)

        # 2. Apply template via endpoint
        resp_apply = client.post("/api/simulation/templates/CUSTOMER_CONFIRMED_LEGITIMATE/apply?case_id=HHG-001")
        self.assertEqual(resp_apply.status_code, 200)
        data = resp_apply.json()
        self.assertEqual(data["case_id"], "HHG-001")
        self.assertEqual(data["simulated"]["verdict"], "legitimate")

        # 3. Custom simulation run
        resp_custom = client.post(
            "/api/simulation/run",
            json={
                "case_id": "HHG-001",
                "override_amount": 15000.0,
                "override_mcc": "6051",
                "notes": "Custom high-exposure quasi-cash test",
            },
        )
        self.assertEqual(resp_custom.status_code, 200)
        res_data = resp_custom.json()
        self.assertEqual(res_data["simulated"]["exposure_usd"], 15000.0)
        self.assertTrue(res_data["simulated"]["mandatory_sar"])
        print("PASS: Custom perturbation and FastAPI simulation endpoints verified.")


if __name__ == "__main__":
    unittest.main()
