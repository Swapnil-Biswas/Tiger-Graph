"""
Unit Test Suite for Automated Compliance Evidence Packager & Cryptographic Chain-of-Custody
(tests/test_evidence_bundle.py)

Tests bundle generation across 16 evidence categories, Merkle tree construction,
HMAC-SHA256 signature sealing, tamper detection on bit-flips/content modifications,
chain of custody logging, and FastAPI REST endpoints.
"""

import json
import unittest
from fastapi.testclient import TestClient

from src.cases.evidence_bundle import (
    ComplianceEvidencePackager,
    EvidenceBundle,
    compute_sha256,
    compute_merkle_root,
    canonical_json,
    DEFAULT_SIGNING_KEY,
)
from src.agent.graph import FraudInvestigatorAgent
from src.api.main import app


class TestComplianceEvidenceBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Compliance Evidence Packager Test Suite ===")
        cls.agent = FraudInvestigatorAgent()
        cls.packager = ComplianceEvidencePackager()
        cls.api_client = TestClient(app)

        # Generate a baseline case investigation
        cls.case_ans = cls.agent.investigate_case("HHG-001")

    def test_01_complete_evidence_bundle_generation(self):
        """Verify generation of certified evidence bundle with all 16 evidence categories."""
        bundle = self.packager.build_evidence_bundle(self.case_ans)

        self.assertIsNotNone(bundle.bundle_id)
        self.assertTrue(bundle.bundle_id.startswith("BUNDLE-HHG-001-"))
        self.assertEqual(bundle.case_id, "HHG-001")
        self.assertEqual(len(bundle.items), 16)

        categories = [item.category for item in bundle.items]
        expected_categories = [
            "CASE_METADATA",
            "GRAPH_TRAVERSAL",
            "VECTOR_SEARCH",
            "GRAPH_MOTIFS",
            "RECORD_LINKAGE",
            "RULE_MINING",
            "CROSS_BORDER_AML",
            "MCC_ANALYSIS",
            "CONTAGION_SCORING",
            "GRAPH_EMBEDDINGS",
            "ACTIVE_LEARNING",
            "SUBAGENT_ASSESSMENT",
            "SUBAGENT_ASSESSMENT",
            "CONSENSUS_DELIBERATION",
            "EPISODIC_MEMORY",
            "REGULATORY_SAR",
        ]
        self.assertEqual(categories, expected_categories)

        # Validate hashes and signatures
        for item in bundle.items:
            self.assertEqual(len(item.sha256_hash), 64)
            self.assertEqual(item.sha256_hash, compute_sha256(item.content))

        self.assertEqual(len(bundle.merkle_root), 64)
        self.assertEqual(len(bundle.signature), 64)
        self.assertGreaterEqual(len(bundle.chain_of_custody), 3)
        print("PASS: Certified evidence bundle generated with all 16 categories.")

    def test_02_merkle_tree_mathematical_integrity(self):
        """Verify Merkle tree construction, single leaf, odd duplication, and avalanche effect."""
        # 1. Empty tree
        self.assertEqual(len(compute_merkle_root([])), 64)

        # 2. Single leaf
        leaf1 = compute_sha256("leaf_1")
        self.assertEqual(compute_merkle_root([leaf1]), leaf1)

        # 3. Two leaves
        leaf2 = compute_sha256("leaf_2")
        root2 = compute_merkle_root([leaf1, leaf2])
        self.assertEqual(len(root2), 64)

        # 4. Odd leaves (duplicate last)
        leaf3 = compute_sha256("leaf_3")
        root3 = compute_merkle_root([leaf1, leaf2, leaf3])
        self.assertEqual(len(root3), 64)

        # 5. Avalanche effect: changing one byte in any leaf alters root completely
        leaf1_tampered = compute_sha256("leaf_1_tampered")
        root3_tampered = compute_merkle_root([leaf1_tampered, leaf2, leaf3])
        self.assertNotEqual(root3, root3_tampered)
        print("PASS: Merkle tree construction and cryptographic avalanche effect verified.")

    def test_03_cryptographic_verification_clean_bundle(self):
        """Verify clean evidence bundle passes full cryptographic verification."""
        bundle = self.packager.build_evidence_bundle(self.case_ans)
        audit = self.packager.verify_bundle(bundle)

        self.assertTrue(audit["is_valid"])
        self.assertFalse(audit["tamper_detected"])
        self.assertEqual(audit["total_items"], 16)
        self.assertEqual(audit["items_verified"], 16)
        self.assertEqual(len(audit["corrupted_items"]), 0)
        self.assertTrue(audit["merkle_root_valid"])
        self.assertTrue(audit["signature_valid"])
        self.assertEqual(audit["legal_admissibility"], "FEDERAL_RULES_OF_EVIDENCE_RULE_902_CERTIFIED")
        print("PASS: Clean bundle passes full cryptographic audit & FRE 902 certification.")

    def test_04_tamper_detection_content_modification(self):
        """Verify bit-flip or content alteration in any evidence item is immediately detected."""
        bundle = self.packager.build_evidence_bundle(self.case_ans)
        bundle_dict = bundle.to_dict()

        # Maliciously alter case metadata (e.g. forge exposure_usd from 2700 to 100)
        bundle_dict["items"][0]["content"]["exposure_usd"] = 100.0

        audit = self.packager.verify_bundle(bundle_dict)
        self.assertFalse(audit["is_valid"])
        self.assertTrue(audit["tamper_detected"])
        self.assertEqual(len(audit["corrupted_items"]), 1)
        self.assertEqual(audit["corrupted_items"][0]["item_id"], bundle_dict["items"][0]["item_id"])
        self.assertFalse(audit["merkle_root_valid"])
        self.assertFalse(audit["signature_valid"])
        self.assertEqual(audit["legal_admissibility"], "FAILED_INTEGRITY_CHECK")
        print("PASS: Item content tampering detected with exact corrupted item pinpointed.")

    def test_05_tamper_detection_signature_spoofing(self):
        """Verify forged digital signatures or wrong keys fail verification."""
        bundle = self.packager.build_evidence_bundle(self.case_ans)
        bundle_dict = bundle.to_dict()

        # Forge signature
        bundle_dict["signature"] = "0" * 64
        audit = self.packager.verify_bundle(bundle_dict)
        self.assertFalse(audit["is_valid"])
        self.assertFalse(audit["signature_valid"])

        # Verify with wrong key
        wrong_key = b"MALICIOUS_COUNTERFEIT_KEY_666"
        audit_wrong = self.packager.verify_bundle(bundle, signing_key=wrong_key)
        self.assertFalse(audit_wrong["is_valid"])
        self.assertFalse(audit_wrong["signature_valid"])
        print("PASS: Forged signatures and unauthorized signing keys successfully rejected.")

    def test_06_chain_of_custody_and_manifest(self):
        """Verify chain-of-custody transfer tracking and manifest export."""
        bundle = self.packager.build_evidence_bundle(self.case_ans)
        initial_events = len(bundle.chain_of_custody)

        # Append custody transfer event
        evt = self.packager.append_custody_event(
            bundle=bundle,
            action="REGULATORY_SUBMISSION_FINCEN",
            actor="COMPLIANCE_OFFICER_J_DOE",
            system_component="BSA_E_FILING_SECURE_GATEWAY",
            verification_status="SUBMITTED_ACKNOWLEDGED",
            notes="Submitted to FinCEN BSA filing system reference #BSN-9821038",
        )
        self.assertEqual(len(bundle.chain_of_custody), initial_events + 1)
        self.assertEqual(evt.action, "REGULATORY_SUBMISSION_FINCEN")
        self.assertEqual(evt.verification_status, "SUBMITTED_ACKNOWLEDGED")

        # Export manifest
        manifest = bundle.export_manifest()
        self.assertEqual(manifest["case_id"], "HHG-001")
        self.assertEqual(manifest["merkle_root"], bundle.merkle_root)
        self.assertEqual(len(manifest["evidence_items_manifest"]), 16)
        print("PASS: Chain-of-custody logging and regulatory manifest verified.")

    def test_07_fastapi_evidence_bundle_endpoints(self):
        """Verify REST API endpoints for evidence bundle generation, manifest, and verification."""
        # 1. GET /api/cases/{case_id}/evidence-bundle
        resp_bundle = self.api_client.get("/api/cases/HHG-001/evidence-bundle")
        self.assertEqual(resp_bundle.status_code, 200)
        bundle_data = resp_bundle.json()
        self.assertIn("bundle_id", bundle_data)
        self.assertIn("merkle_root", bundle_data)
        self.assertEqual(bundle_data["item_count"], 16)

        # 2. GET /api/cases/{case_id}/evidence-manifest
        resp_manifest = self.api_client.get("/api/cases/HHG-001/evidence-manifest")
        self.assertEqual(resp_manifest.status_code, 200)
        manifest_data = resp_manifest.json()
        self.assertIn("evidence_items_manifest", manifest_data)
        self.assertEqual(len(manifest_data["evidence_items_manifest"]), 16)

        # 3. POST /api/compliance/verify-evidence-bundle (Clean)
        resp_verify = self.api_client.post("/api/compliance/verify-evidence-bundle", json=bundle_data)
        self.assertEqual(resp_verify.status_code, 200)
        audit = resp_verify.json()
        self.assertTrue(audit["is_valid"])
        self.assertFalse(audit["tamper_detected"])

        # 4. POST /api/compliance/verify-evidence-bundle (Tampered)
        tampered_bundle = dict(bundle_data)
        tampered_bundle["items"] = list(bundle_data["items"])
        tampered_bundle["items"][0]["sha256_hash"] = "f" * 64

        resp_tampered = self.api_client.post("/api/compliance/verify-evidence-bundle", json=tampered_bundle)
        self.assertEqual(resp_tampered.status_code, 200)
        tamper_audit = resp_tampered.json()
        self.assertFalse(tamper_audit["is_valid"])
        self.assertTrue(tamper_audit["tamper_detected"])
        print("PASS: FastAPI compliance evidence bundle and cryptographic audit endpoints verified.")


if __name__ == "__main__":
    unittest.main()
