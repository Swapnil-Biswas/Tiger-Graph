"""
Unit Tests for Interactive Human-in-the-Loop Analyst Override & Graph Audit Trail
Validates override execution, role-based policy gates, justification enforcement,
graph persistence, and API endpoint behavior.
"""

import unittest
from fastapi.testclient import TestClient
from src.agent.graph import FraudInvestigatorAgent
from src.cases.manager import CaseManager
from src.api.main import app, active_cases


class TestAnalystOverrideAndAuditTrail(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Analyst Override Test Suite ===")
        cls.agent = FraudInvestigatorAgent()
        cls.case_manager = CaseManager(client=cls.agent.client)
        cls.client = TestClient(app)

    def test_analyst_override_success_and_audit_trail(self):
        """Valid override must update vertex, status, and append immutable audit log."""
        case_id = "HHG-003"
        ans = self.agent.investigate_case(case_id)
        self.case_manager.write_case_to_graph(ans)

        override_rec = self.case_manager.record_analyst_override(
            case_id=case_id,
            analyst_id="ANALYST-JANE-DOE",
            analyst_role="L1_ANALYST",
            new_verdict="legitimate",
            justification="Cardholder provided notarized affidavit verifying legitimate travel transaction.",
            new_actions=[{"action": "ALLOW_TRANSACTION", "route": "auto", "reason": "Analyst verified affidavit"}],
        )

        self.assertEqual(override_rec["new_verdict"], "legitimate")
        self.assertEqual(override_rec["new_status"], "closed_legitimate")
        self.assertEqual(override_rec["previous_verdict"], "fraud")

        # Verify graph case vertex
        c_vert = self.case_manager.store.graph_cases[f"CASE-{case_id}"]
        self.assertTrue(c_vert["is_overridden"])
        self.assertEqual(c_vert["verdict"], "legitimate")
        self.assertEqual(c_vert["status"], "closed_legitimate")
        self.assertEqual(len(c_vert["audit_trail"]), 1)
        self.assertEqual(c_vert["audit_trail"][0]["analyst_id"], "ANALYST-JANE-DOE")

        # Verify edge in graph_case_edges
        edge_found = any(
            e.get("type") == "OVERRIDDEN_BY" and e.get("from_case") == f"CASE-{case_id}"
            for e in self.case_manager.store.graph_case_edges
        )
        self.assertTrue(edge_found, "OVERRIDDEN_BY edge missing from graph_case_edges.")

        # Verify reconstruction from graph
        reconstructed = self.case_manager.reconstruct_case_from_graph(case_id)
        self.assertTrue(reconstructed["is_overridden"])
        self.assertEqual(reconstructed["verdict"], "legitimate")
        self.assertEqual(len(reconstructed["audit_trail"]), 1)

    def test_high_exposure_role_permission_gate(self):
        """Overriding high exposure fraud (> $2,500) to legitimate requires L2_LEAD or higher."""
        case_id = "HHG-004"
        ans = self.agent.investigate_case(case_id)
        ans["case"]["exposure_usd"] = 5000.0  # Explicit high exposure scenario
        self.case_manager.write_case_to_graph(ans)

        # L1_ANALYST attempt must be denied by policy
        with self.assertRaises(PermissionError):
            self.case_manager.record_analyst_override(
                case_id=case_id,
                analyst_id="ANALYST-JUNIOR",
                analyst_role="L1_ANALYST",
                new_verdict="legitimate",
                justification="Attempting unauthorized clearing of large corporate fraud case.",
            )

        # L2_LEAD attempt must succeed
        ovr = self.case_manager.record_analyst_override(
            case_id=case_id,
            analyst_id="LEAD-SARAH-CONNOR",
            analyst_role="L2_LEAD",
            new_verdict="legitimate",
            justification="Special executive authorization and verified vendor billing reconciliations.",
        )
        self.assertEqual(ovr["new_verdict"], "legitimate")

    def test_justification_and_verdict_validation(self):
        """Overrides with short justification or invalid verdict must be rejected."""
        case_id = "HHG-007"
        ans = self.agent.investigate_case(case_id)
        self.case_manager.write_case_to_graph(ans)

        # Trivial justification (< 10 chars)
        with self.assertRaises(ValueError):
            self.case_manager.record_analyst_override(
                case_id=case_id,
                analyst_id="ANALYST-1",
                analyst_role="L1_ANALYST",
                new_verdict="legitimate",
                justification="too short",
            )

        # Invalid verdict
        with self.assertRaises(ValueError):
            self.case_manager.record_analyst_override(
                case_id=case_id,
                analyst_id="ANALYST-1",
                analyst_role="L1_ANALYST",
                new_verdict="maybe_fraud",
                justification="Structured justification explaining the rationale thoroughly.",
            )

    def test_api_override_and_audit_endpoints(self):
        """API endpoints /api/cases/{case_id}/override and /api/cases/{case_id}/audit function correctly."""
        case_id = "HHG-011"
        payload = {
            "analyst_id": "ANALYST-ALICE",
            "analyst_role": "L1_ANALYST",
            "new_verdict": "uncertain",
            "justification": "Escalating for secondary review with anti-money-laundering division.",
            "new_actions": [{"action": "CREATE_CASE", "route": "auto", "reason": "AML review"}],
        }

        # POST override
        resp = self.client.post(f"/api/cases/{case_id}/override", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["override"]["new_verdict"], "uncertain")

        # GET audit trail
        audit_resp = self.client.get(f"/api/cases/{case_id}/audit")
        self.assertEqual(audit_resp.status_code, 200)
        audit_data = audit_resp.json()
        self.assertGreaterEqual(len(audit_data["audit_trail"]), 1)
        self.assertEqual(audit_data["audit_trail"][-1]["analyst_id"], "ANALYST-ALICE")


if __name__ == "__main__":
    unittest.main()
