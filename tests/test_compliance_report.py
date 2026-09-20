"""
Unit Tests for Fine-Grained Policy Audit & Compliance Report Packager (tests/test_compliance_report.py)
Validates:
  1. Multi-jurisdiction statutory auditing (FinCEN 31 CFR 1020, UK POCA, EU 6AMLD/GDPR)
  2. Internal bank fraud policy guardrails (Rules R1 - R10, evidence gates, approval tiers)
  3. FRE 902(13)/(14) Cryptographic chain of custody & signature verification
  4. Markdown and HTML compliance certificate exports
  5. Batch compliance auditing and FastAPI REST endpoints
"""

import json
import os
import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.policy.compliance_report import ComplianceReportPackager, compliance_packager
from src.api.main import app


class TestComplianceReportPackager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api_client = TestClient(app)
        # Load sample benchmark case HHG-001
        case_file = ROOT_DIR / "cases" / "HHG-001.json"
        with open(case_file, "r", encoding="utf-8") as f:
            cls.sample_case = json.load(f)

    def test_01_compliant_case_evaluation(self):
        """Standard benchmark case HHG-001 achieves compliant status and high compliance score."""
        report = compliance_packager.evaluate_case(self.sample_case, jurisdiction="US")

        self.assertEqual(report.case_id, "HHG-001")
        self.assertEqual(report.jurisdiction, "US")
        self.assertIn(report.overall_status, ["COMPLIANT", "CONDITIONAL_COMPLIANCE"])
        self.assertGreaterEqual(report.compliance_score, 90.0)
        self.assertTrue(report.certificate_id.startswith("COMP-CERT-"))
        self.assertTrue(len(report.signature_hash) == 64)

        # Verify all 5 framework assessments are present
        expected_frameworks = [
            "BSA_FINCEN",
            "UK_POCA",
            "EU_GDPR_6AMLD",
            "INTERNAL_POLICY_R1_R10",
            "FRE_902_CHAIN_OF_CUSTODY",
        ]
        for fw in expected_frameworks:
            self.assertIn(fw, report.framework_assessments)
            fa = report.framework_assessments[fw]
            self.assertGreaterEqual(fa["score"], 80.0)
            self.assertIn(fa["status"], ["PASS", "WARN"])

    def test_02_sar_threshold_enforcement(self):
        """High-exposure ($15,000) fraud case without SAR triggers CRITICAL non-compliance."""
        high_exposure_case = {
            "case_id": "TEST-SAR-FAIL",
            "case": {
                "verdict": "fraud",
                "fraud_probability": 0.95,
                "exposure_usd": 15000.0,
                "pattern": "card_not_present_burst",
                "evidence": [{"id": "EV-01", "claim": "Confirmed card takeover with $15,000 drained."}],
            },
            "next_best_actions": ["BLOCK_CARD"],
            # No SAR provided
        }

        report = compliance_packager.evaluate_case(high_exposure_case, jurisdiction="US")
        self.assertEqual(report.overall_status, "NON_COMPLIANT")
        self.assertIn("BSA-31CFR1020-01", [c["check_id"] for c in report.checks if not c["passed"]])
        self.assertTrue(any("FinCEN Form 111" in step for step in report.remediation_steps))

        # Now attach SAR and re-evaluate -> should pass SAR check
        high_exposure_case["sar"] = {
            "narrative": "Part I: Suspect Info... Part II: Suspicious Activity...",
            "filing_ready": True,
        }
        report_repaired = compliance_packager.evaluate_case(high_exposure_case, jurisdiction="US")
        bsa_sar_check = next(c for c in report_repaired.checks if c["check_id"] == "BSA-31CFR1020-01")
        self.assertTrue(bsa_sar_check["passed"])

    def test_03_gdpr_data_minimization_detection(self):
        """Unmasked PANs and personal emails trigger GDPR Article 5 warning/remediation."""
        unminimized_case = {
            "case_id": "TEST-GDPR-FAIL",
            "case": {
                "verdict": "fraud",
                "fraud_probability": 0.88,
                "exposure_usd": 1200.0,
                "evidence": [
                    {
                        "id": "EV-01",
                        "claim": "Card 4111-2222-3333-4444 used by user.john.doe@company.org on fraudulent portal.",
                    }
                ],
            },
            "next_best_actions": ["BLOCK_CARD"],
        }

        report = compliance_packager.evaluate_case(unminimized_case, jurisdiction="EU")
        gdpr_check = next(c for c in report.checks if c["check_id"] == "EU-GDPR-01")
        self.assertFalse(gdpr_check["passed"])
        self.assertIn("unmasked PAN", gdpr_check["detail"])
        self.assertTrue(any("GDPR Article 5" in step for step in report.remediation_steps))

    def test_04_policy_rules_guardrails(self):
        """Enforces Rules R1, R8, R10, and Evidence Gate violations."""
        # Violation 1: R1 (single signal weak fraud block without verify)
        r1_case = {
            "case_id": "TEST-R1-FAIL",
            "case": {
                "verdict": "review",
                "fraud_probability": 0.35,
                "exposure_usd": 80.0,
                "risk_signals": ["single_mismatch"],
                "evidence": [{"id": "EV-01", "claim": "IP country mismatch."}],
            },
            "next_best_actions": ["BLOCK_CARD"],
        }
        r1_report = compliance_packager.evaluate_case(r1_case)
        r1_check = next(c for c in r1_report.checks if c["check_id"] == "POLICY-R1")
        self.assertFalse(r1_check["passed"])

        # Violation 2: R8 (premature closure on high exposure > $5,000)
        r8_case = {
            "case_id": "TEST-R8-FAIL",
            "case": {
                "verdict": "legitimate",
                "fraud_probability": 0.10,
                "exposure_usd": 8500.0,
                "evidence": [{"id": "EV-01", "claim": "High value wire."}],
            },
            "next_best_actions": ["CLOSE_NO_FRAUD"],
        }
        r8_report = compliance_packager.evaluate_case(r8_case)
        r8_check = next(c for c in r8_report.checks if c["check_id"] == "POLICY-R8")
        self.assertFalse(r8_check["passed"])

        # Violation 3: R10 (BLOCK_ALL_CARDS without 2 confirmed compromised cards)
        r10_case = {
            "case_id": "TEST-R10-FAIL",
            "case": {
                "verdict": "fraud",
                "fraud_probability": 0.85,
                "exposure_usd": 1200.0,
                "connected_card_ids": ["CARD-1"],  # only 1 card
                "evidence": [{"id": "EV-01", "claim": "Compromised card."}],
            },
            "next_best_actions": ["BLOCK_ALL_CARDS"],
        }
        r10_report = compliance_packager.evaluate_case(r10_case)
        r10_check = next(c for c in r10_report.checks if c["check_id"] == "POLICY-R10")
        self.assertFalse(r10_check["passed"])

    def test_05_export_markdown_and_html_certificates(self):
        """Exports publication-grade Markdown and printable HTML certificates."""
        report = compliance_packager.evaluate_case(self.sample_case, jurisdiction="US")

        # Markdown export
        md = compliance_packager.export_markdown_certificate(report)
        self.assertIn("# Statutory & Policy Compliance Audit Certificate", md)
        self.assertIn("Certificate ID:", md)
        self.assertIn("BEGIN COMPLIANCE AUDIT CERTIFICATE", md)
        self.assertIn(report.signature_hash, md)

        # HTML export
        html = compliance_packager.export_html_certificate(report)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<title>Compliance Certificate - HHG-001</title>", html)
        self.assertIn("Statutory & Policy Compliance Certificate", html)
        self.assertIn(report.certificate_id, html)
        self.assertIn("@media print", html)

    def test_06_batch_compliance_audit(self):
        """Batch compliance audit aggregates scores and metrics across multiple cases."""
        cases = [self.sample_case, dict(self.sample_case, case_id="HHG-001-COPY")]
        batch_res = compliance_packager.audit_batch(cases, jurisdiction="US")

        self.assertEqual(batch_res["total_cases_audited"], 2)
        self.assertGreaterEqual(batch_res["average_compliance_score"], 90.0)
        self.assertIn("compliance_pass_rate_percent", batch_res)
        self.assertEqual(len(batch_res["reports"]), 2)

    def test_07_api_compliance_endpoints(self):
        """FastAPI REST endpoints for compliance report and batch audit operate correctly."""
        # Test JSON format
        res_json = self.api_client.get("/api/compliance/report/HHG-001?format=json")
        self.assertEqual(res_json.status_code, 200)
        data = res_json.json()
        self.assertEqual(data["case_id"], "HHG-001")
        self.assertIn("compliance_score", data)
        self.assertIn("signature_hash", data)

        # Test Markdown format
        res_md = self.api_client.get("/api/compliance/report/HHG-001?format=markdown")
        self.assertEqual(res_md.status_code, 200)
        self.assertIn("# Statutory & Policy Compliance Audit Certificate", res_md.text)

        # Test HTML format
        res_html = self.api_client.get("/api/compliance/report/HHG-001?format=html")
        self.assertEqual(res_html.status_code, 200)
        self.assertIn("<!DOCTYPE html>", res_html.text)

        # Test Batch audit endpoint
        res_batch = self.api_client.post(
            "/api/compliance/audit-batch",
            json={"case_ids": ["HHG-001", "HHG-002"], "jurisdiction": "US"},
        )
        self.assertEqual(res_batch.status_code, 200)
        batch_data = res_batch.json()
        self.assertEqual(batch_data["total_cases_audited"], 2)
        self.assertGreaterEqual(batch_data["average_compliance_score"], 90.0)


if __name__ == "__main__":
    unittest.main()
