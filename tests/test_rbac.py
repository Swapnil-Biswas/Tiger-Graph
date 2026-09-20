"""
Unit Test Suite for Dynamic Multi-Tenant Role-Based Access Control (RBAC)
(tests/test_rbac.py)

Tests role permission matrix, action authorization tiers, exposure thresholds,
PII masking engine (GDPR Art. 5), and FastAPI REST endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from src.auth.rbac import (
    Role,
    Permission,
    AuthUser,
    ROLE_PERMISSIONS,
    ACTION_TIERS,
    mask_pii_dict,
)
from src.api.main import app


class TestRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Multi-Tenant RBAC Test Suite ===")
        cls.client = TestClient(app)

    def test_01_role_permission_matrix(self):
        """Verify statutory role-to-permission mappings."""
        # 1. L1 Analyst
        l1 = AuthUser(user_id="user_l1", role=Role.L1_ANALYST)
        self.assertTrue(l1.has_permission(Permission.CASE_READ))
        self.assertTrue(l1.has_permission(Permission.ACTION_EXECUTE_L1))
        self.assertFalse(l1.has_permission(Permission.PII_READ_UNMASKED))
        self.assertFalse(l1.has_permission(Permission.ACTION_EXECUTE_L2))
        self.assertFalse(l1.has_permission(Permission.ACTION_EXECUTE_L3))
        self.assertFalse(l1.has_permission(Permission.POLICY_OVERRIDE))

        # 2. L2 Senior Investigator
        l2 = AuthUser(user_id="user_l2", role=Role.L2_SENIOR_INVESTIGATOR)
        self.assertTrue(l2.has_permission(Permission.PII_READ_UNMASKED))
        self.assertTrue(l2.has_permission(Permission.ACTION_EXECUTE_L1))
        self.assertTrue(l2.has_permission(Permission.ACTION_EXECUTE_L2))
        self.assertTrue(l2.has_permission(Permission.POLICY_OVERRIDE))
        self.assertFalse(l2.has_permission(Permission.ACTION_EXECUTE_L3))

        # 3. AML Compliance Officer
        aml = AuthUser(user_id="user_aml", role=Role.AML_COMPLIANCE_OFFICER)
        self.assertTrue(aml.has_permission(Permission.ACTION_EXECUTE_L3))
        self.assertTrue(aml.has_permission(Permission.REGULATORY_EXPORT))

        # 4. Auditor (Read-only, no unmasked PII, no action execution)
        auditor = AuthUser(user_id="user_auditor", role=Role.AUDITOR)
        self.assertTrue(auditor.has_permission(Permission.CASE_READ))
        self.assertTrue(auditor.has_permission(Permission.EVIDENCE_VAULT_AUDIT))
        self.assertFalse(auditor.has_permission(Permission.PII_READ_UNMASKED))
        self.assertFalse(auditor.has_permission(Permission.ACTION_EXECUTE_L1))

        print("PASS: Role-to-permission matrix strictly verified.")

    def test_02_action_authorization_tiers_and_exposure_gates(self):
        """Verify fine-grained action tier authorization and dollar exposure limits."""
        l1 = AuthUser(user_id="user_l1", role=Role.L1_ANALYST)
        l2 = AuthUser(user_id="user_l2", role=Role.L2_SENIOR_INVESTIGATOR)
        aml = AuthUser(user_id="user_aml", role=Role.AML_COMPLIANCE_OFFICER)

        # L1 can execute VERIFY_WITH_CUSTOMER under $2,500
        ok, _ = l1.can_execute_action("VERIFY_WITH_CUSTOMER", exposure_usd=100.0)
        self.assertTrue(ok)

        # L1 blocked from BLOCK_CARD (Tier 2)
        ok, reason = l1.can_execute_action("BLOCK_CARD", exposure_usd=100.0)
        self.assertFalse(ok)
        self.assertIn("lacks required permission", reason)

        # L1 blocked from exposure > $2,500
        ok, reason = l1.can_execute_action("VERIFY_WITH_CUSTOMER", exposure_usd=3000.0)
        self.assertFalse(ok)
        self.assertIn("exceeds L1 Analyst authority", reason)

        # L2 can execute BLOCK_CARD
        ok, _ = l2.can_execute_action("BLOCK_CARD", exposure_usd=1500.0)
        self.assertTrue(ok)

        # L2 blocked from BLOCK_ALL_CARDS (Tier 3)
        ok, reason = l2.can_execute_action("BLOCK_ALL_CARDS", exposure_usd=1500.0)
        self.assertFalse(ok)
        self.assertIn("lacks required permission", reason)

        # L2 blocked from exposure > $10,000
        ok, reason = l2.can_execute_action("BLOCK_CARD", exposure_usd=15000.0)
        self.assertFalse(ok)
        self.assertIn("exceeds $10,000.00 threshold", reason)

        # AML Officer can execute BLOCK_ALL_CARDS and FILE_SAR even for > $10,000
        ok, _ = aml.can_execute_action("BLOCK_ALL_CARDS", exposure_usd=25000.0)
        self.assertTrue(ok)
        ok, _ = aml.can_execute_action("FILE_SAR", exposure_usd=25000.0)
        self.assertTrue(ok)

        print("PASS: Action tiers and financial exposure authorization gates verified.")

    def test_03_pii_masking_engine(self):
        """Verify PII masking for roles without PII_READ_UNMASKED (GDPR Art. 5)."""
        sample_payload = {
            "case_id": "HHG-001",
            "card_id": "C12382-K1",
            "customer_id": "C12382",
            "p_email": "john.smith@gmail.com",
            "connected_card_ids": ["C11919-K1", "C11919-K2"],
            "financial_summary": {"exposure_usd": 1250.0},
        }

        # 1. Masked for Auditor
        auditor = AuthUser(user_id="auditor_01", role=Role.AUDITOR)
        masked = mask_pii_dict(sample_payload, auditor)

        self.assertEqual(masked["case_id"], "HHG-001")
        self.assertEqual(masked["card_id"], "C****-K1")
        self.assertEqual(masked["customer_id"], "C***82")
        self.assertEqual(masked["p_email"], "j********h@gmail.com")
        self.assertEqual(masked["connected_card_ids"], ["C****-K1", "C****-K2"])
        self.assertEqual(masked["financial_summary"]["exposure_usd"], 1250.0)

        # 2. Unmasked for L2 Senior Investigator
        l2 = AuthUser(user_id="l2_01", role=Role.L2_SENIOR_INVESTIGATOR)
        unmasked = mask_pii_dict(sample_payload, l2)

        self.assertEqual(unmasked["card_id"], "C12382-K1")
        self.assertEqual(unmasked["customer_id"], "C12382")
        self.assertEqual(unmasked["p_email"], "john.smith@gmail.com")
        self.assertEqual(unmasked["connected_card_ids"], ["C11919-K1", "C11919-K2"])

        print("PASS: PII masking engine strictly isolates sensitive fields by role.")

    def test_04_fastapi_rbac_endpoints(self):
        """Verify REST endpoints for /api/auth/me, /api/auth/roles, and /api/cases/{case_id}/actions/authorize."""
        # 1. GET /api/auth/me with custom role header
        resp = self.client.get(
            "/api/auth/me",
            headers={"X-User-Role": "AML_COMPLIANCE_OFFICER", "X-User-Id": "aml_officer_42"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["user_id"], "aml_officer_42")
        self.assertEqual(data["role"], "AML_COMPLIANCE_OFFICER")
        self.assertIn("ACTION_EXECUTE_L3", data["permissions"])

        # 2. GET /api/auth/roles
        resp_roles = self.client.get("/api/auth/roles")
        self.assertEqual(resp_roles.status_code, 200)
        roles_data = resp_roles.json()
        self.assertIn("L1_ANALYST", roles_data)
        self.assertIn("AML_COMPLIANCE_OFFICER", roles_data)
        self.assertIn("AUDITOR", roles_data)

        # 3. POST /api/cases/{case_id}/actions/authorize (Authorized)
        resp_auth = self.client.post(
            "/api/cases/HHG-001/actions/authorize",
            headers={"X-User-Role": "L2_SENIOR_INVESTIGATOR", "X-User-Id": "investigator_02"},
            json={"action_name": "BLOCK_CARD", "exposure_usd": 800.0},
        )
        self.assertEqual(resp_auth.status_code, 200)
        auth_data = resp_auth.json()
        self.assertTrue(auth_data["authorized"])

        # 4. POST /api/cases/{case_id}/actions/authorize (Unauthorized L1 for BLOCK_CARD)
        resp_unauth = self.client.post(
            "/api/cases/HHG-001/actions/authorize",
            headers={"X-User-Role": "L1_ANALYST", "X-User-Id": "junior_analyst"},
            json={"action_name": "BLOCK_CARD", "exposure_usd": 800.0},
        )
        self.assertEqual(resp_unauth.status_code, 200)
        unauth_data = resp_unauth.json()
        self.assertFalse(unauth_data["authorized"])
        self.assertIn("lacks required permission", unauth_data["reason"])

        print("PASS: FastAPI RBAC and action authorization REST endpoints verified.")

    def test_05_case_dossier_pii_masking_via_api(self):
        """Verify that GET /api/cases/{case_id} masks PII for Auditor and exposes PII for Senior Investigator."""
        # 1. Auditor request -> PII masked
        resp_auditor = self.client.get(
            "/api/cases/HHG-001",
            headers={"X-User-Role": "AUDITOR", "X-User-Id": "external_auditor"},
        )
        self.assertEqual(resp_auditor.status_code, 200)
        auditor_case = resp_auditor.json()
        c_card = auditor_case["case"].get("card_id", "")
        self.assertIn("****", c_card, "Auditor must receive masked card_id")

        # 2. Senior Investigator request -> PII unmasked
        resp_l2 = self.client.get(
            "/api/cases/HHG-001",
            headers={"X-User-Role": "L2_SENIOR_INVESTIGATOR", "X-User-Id": "senior_l2"},
        )
        self.assertEqual(resp_l2.status_code, 200)
        l2_case = resp_l2.json()
        c_card_l2 = l2_case["case"].get("card_id", "")
        self.assertEqual(c_card_l2, "C12382-K1", "Senior Investigator must receive unmasked card_id")

        print("PASS: Case dossier endpoint dynamically enforces PII masking by requester role.")


if __name__ == "__main__":
    unittest.main()
