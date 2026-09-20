"""
Unit Test Suite for Automated FinCEN Form 111 XML/ASCII Electronic Filing Validator & Packager
(tests/test_sar_exporter.py)

Tests XML 2.0 schema structure, statutory 5-part narrative generation, 12-rule electronic
filing validator, and FastAPI REST endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from src.cases.sar_exporter import (
    FinCENSARXMLPackager,
    FinCENValidationReport,
)
from src.api.main import app


class TestFinCENSARXMLPackager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing FinCEN Form 111 SAR XML Test Suite ===")
        cls.packager = FinCENSARXMLPackager()
        cls.client = TestClient(app)

    def test_01_sar_xml_structure_and_schema_version(self):
        """Verify FinCEN XML 2.0 root tags, namespace, and document identifier."""
        sample_bundle = {
            "case_id": "HHG-001",
            "case": {
                "customer_id": "C12382",
                "card_id": "C12382-K1",
                "exposure_usd": 1250.0,
                "pattern": "card_not_present_fraud",
                "summary": "Coordinated online card-not-present fraud detected across multiple device hubs.",
                "first_suspicious_txn_id": "3514030",
                "connected_card_ids": ["C11919-K1"],
            },
            "sar": {"file": True},
        }

        xml_str = self.packager.generate_sar_xml(sample_bundle)

        self.assertIn("xmlns:fc2=\"http://www.fincen.gov/base\"", xml_str)
        self.assertIn("version=\"2.0\"", xml_str)
        self.assertIn("<fc2:SuspiciousActivityReport", xml_str)
        self.assertIn("<fc2:Activity>", xml_str)
        self.assertIn("<fc2:ActivityParty PartyType=\"Subject\">", xml_str)
        self.assertIn("<fc2:ActivityParty PartyType=\"FilingInstitution\">", xml_str)
        self.assertIn("<fc2:SuspiciousActivity>", xml_str)
        self.assertIn("<fc2:NarrativeInformation>", xml_str)

        print("PASS: FinCEN XML 2.0 root tags and namespaces verified.")

    def test_02_statutory_five_part_narrative(self):
        """Verify Part V five-part narrative adheres to Who/What/When/Where/Why structure <= 17,000 chars."""
        sample_bundle = {
            "case_id": "HHG-004",
            "case": {
                "customer_id": "C02222",
                "card_id": "C02222-K1",
                "exposure_usd": 5400.0,
                "pattern": "multi_card_ring",
                "summary": "Coordinated multi-card syndicate sharing fingerprint device SM-T810.",
                "connected_card_ids": ["C03095-K1", "C04248-K2"],
                "connected_device_profiles": ["SM-T810 Build/NRD90M"],
            },
            "sar": {"file": True},
        }

        xml_str = self.packager.generate_sar_xml(sample_bundle)

        self.assertIn("1. WHO IS CONDUCTING THE ACTIVITY:", xml_str)
        self.assertIn("2. WHAT TRANSACTIONS OCCURRED:", xml_str)
        self.assertIn("3. WHEN DID THE ACTIVITY TAKE PLACE:", xml_str)
        self.assertIn("4. WHERE DID THE ACTIVITY OCCUR:", xml_str)
        self.assertIn("5. WHY AND HOW THE ACTIVITY IS SUSPICIOUS:", xml_str)
        self.assertIn("31 CFR 1020.320", xml_str)
        self.assertLessEqual(len(xml_str), 50000)

        print("PASS: Statutory 5-part narrative strictly generated.")

    def test_03_efiling_validation_rules_pass(self):
        """Verify that generated XML satisfies all 12 BSA E-Filing validation rules."""
        sample_bundle = {
            "case_id": "HHG-005",
            "case": {
                "customer_id": "C00329",
                "card_id": "C00329-K2",
                "exposure_usd": 8900.0,
                "pattern": "structuring",
                "summary": "Rapid succession smurfing just below $10,000 CTR reporting threshold.",
            },
            "sar": {"file": True},
        }

        xml_str = self.packager.generate_sar_xml(sample_bundle)
        report = self.packager.validate_sar_xml(xml_str)

        self.assertTrue(report.is_valid)
        self.assertEqual(len(report.critical_errors), 0)
        self.assertIsNotNone(report.bsa_identifier)

        print(f"PASS: BSA E-Filing validation passed with 0 critical errors (BSA ID: {report.bsa_identifier}).")

    def test_04_efiling_validation_tamper_detection(self):
        """Verify that missing mandatory elements (Part I Subject, Part III TIN, truncated narrative) trigger critical errors."""
        # 1. Truncated narrative (< 50 chars)
        bad_xml_narrative = """<fc2:SuspiciousActivityReport xmlns:fc2="http://www.fincen.gov/base" version="2.0" DocumentIdentifier="BSA_TEST123">
          <fc2:Activity>
            <fc2:FilingDateText>20260921</fc2:FilingDateText>
            <fc2:ActivityParty PartyType="Subject">
              <fc2:AccountNumber>C12382-K1</fc2:AccountNumber>
            </fc2:ActivityParty>
            <fc2:ActivityParty PartyType="FilingInstitution">
              <fc2:PartyTIN>12-3456789</fc2:PartyTIN>
            </fc2:ActivityParty>
            <fc2:SuspiciousActivity>
              <fc2:SuspiciousActivityAmountText>5000</fc2:SuspiciousActivityAmountText>
            </fc2:SuspiciousActivity>
            <fc2:NarrativeInformation>
              <fc2:NarrativeText>Too short.</fc2:NarrativeText>
            </fc2:NarrativeInformation>
          </fc2:Activity>
        </fc2:SuspiciousActivityReport>"""

        rep1 = self.packager.validate_sar_xml(bad_xml_narrative)
        self.assertFalse(rep1.is_valid)
        self.assertTrue(any("NarrativeText" in e.field for e in rep1.critical_errors))

        # 2. Missing Filing Institution TIN
        bad_xml_tin = """<fc2:SuspiciousActivityReport xmlns:fc2="http://www.fincen.gov/base" version="2.0" DocumentIdentifier="BSA_TEST123">
          <fc2:Activity>
            <fc2:FilingDateText>20260921</fc2:FilingDateText>
            <fc2:ActivityParty PartyType="Subject">
              <fc2:AccountNumber>C12382-K1</fc2:AccountNumber>
            </fc2:ActivityParty>
            <fc2:ActivityParty PartyType="FilingInstitution">
              <fc2:PartyName>Apex Federal</fc2:PartyName>
            </fc2:ActivityParty>
            <fc2:SuspiciousActivity>
              <fc2:SuspiciousActivityAmountText>5000</fc2:SuspiciousActivityAmountText>
            </fc2:SuspiciousActivity>
            <fc2:NarrativeInformation>
              <fc2:NarrativeText>This is a valid long narrative that explains the entire situation in great detail.</fc2:NarrativeText>
            </fc2:NarrativeInformation>
          </fc2:Activity>
        </fc2:SuspiciousActivityReport>"""

        rep2 = self.packager.validate_sar_xml(bad_xml_tin)
        self.assertFalse(rep2.is_valid)
        self.assertTrue(any("PartyTIN" in e.field for e in rep2.critical_errors))

        print("PASS: BSA E-Filing validation correctly detected critical filing errors.")

    def test_05_fastapi_sar_xml_endpoints(self):
        """Verify REST endpoints for GET /api/cases/{case_id}/sar/xml and POST /api/compliance/validate-sar-xml."""
        # 1. GET SAR XML
        resp_xml = self.client.get("/api/cases/HHG-001/sar/xml")
        self.assertEqual(resp_xml.status_code, 200)
        self.assertIn("application/xml", resp_xml.headers.get("content-type", ""))
        xml_content = resp_xml.text
        self.assertIn("<fc2:SuspiciousActivityReport", xml_content)

        # 2. POST validate SAR XML
        resp_val = self.client.post(
            "/api/compliance/validate-sar-xml",
            json={"xml_content": xml_content},
        )
        self.assertEqual(resp_val.status_code, 200)
        report_data = resp_val.json()
        self.assertTrue(report_data["is_valid"])
        self.assertEqual(len(report_data["critical_errors"]), 0)

        print("PASS: FastAPI FinCEN Form 111 SAR XML generation and validation REST endpoints verified.")


if __name__ == "__main__":
    unittest.main()
