"""
Audit Trail Self-Critique & Hallucination Verifier Tests (tests/test_audit_self_critique.py).
Validates deterministic self-critique pass, citation grounding, and entity hallucination defenses.
"""

import unittest
from src.agent.graph import FraudInvestigatorAgent
from src.agent.explainer_validator import AuditTrailSelfCritiqueVerifier, CitationValidator


class TestAuditTrailSelfCritique(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Audit Trail Self-Critique Test Suite ===")
        cls.agent = FraudInvestigatorAgent()

    def test_01_grounded_investigation_passes_audit(self):
        """Validates that real investigation output achieves 100% faithfulness score and 0 hallucinations."""
        res = self.agent.investigate_case("HHG-001")
        audit = res.get("audit_critique")
        self.assertIsNotNone(audit, "audit_critique was not attached to investigation result")

        self.assertTrue(audit["passed"], f"Audit failed unexpectedly: {audit['critique_summary']}")
        self.assertEqual(audit["faithfulness_score"], 1.00)
        self.assertEqual(len(audit["fabricated_citations"]), 0)
        self.assertEqual(len(audit["unverified_entities"]), 0)
        print("PASS: HHG-001 investigation achieved 100% audit faithfulness score (1.00) and 0 ungrounded claims.")

    def test_02_hallucinated_citations_caught_and_penalized(self):
        """Validates that injected fake citation tokens (EV-999, POLICY-FAKE) are detected and penalized."""
        fake_summary = "Based on EV-999 and POLICY-FAKE under EV-01, the card was blocked."
        evidence_items = [{"id": "EV-01", "claim": "valid", "entity_ids": ["3514030"]}]
        case_dict = {"card_id": "C12382-K1", "affected_txn_ids": ["3514030"]}

        audit = AuditTrailSelfCritiqueVerifier.audit_case(
            case_summary=fake_summary,
            case_dict=case_dict,
            active_evidence_items=evidence_items,
        )

        self.assertFalse(audit["passed"])
        self.assertIn("EV-999", audit["fabricated_citations"])
        self.assertIn("POLICY-FAKE", audit["fabricated_citations"])
        self.assertLess(audit["faithfulness_score"], 1.00)
        print(f"PASS: Injected fake citations correctly penalized: faithfulness score dropped to {audit['faithfulness_score']:.2f}")

    def test_03_ungrounded_entity_mentions_caught(self):
        """Validates that fabricated transaction IDs or card numbers in narrative are flagged."""
        hallucinated_summary = "Alert on C12382-K1 with ungrounded card C99999-K9 and fake txn 9999999."
        evidence_items = [{"id": "EV-01", "claim": "valid", "entity_ids": ["C12382-K1"]}]
        case_dict = {"card_id": "C12382-K1", "connected_card_ids": ["C12382-K1"], "affected_txn_ids": []}

        audit = AuditTrailSelfCritiqueVerifier.audit_case(
            case_summary=hallucinated_summary,
            case_dict=case_dict,
            active_evidence_items=evidence_items,
        )

        self.assertFalse(audit["passed"])
        self.assertTrue(any("C99999-K9" in e for e in audit["unverified_entities"]))
        self.assertTrue(any("9999999" in e for e in audit["unverified_entities"]))
        print(f"PASS: Hallucinated entity mentions successfully flagged: {audit['unverified_entities']}")

    def test_04_automatic_sanitization_removes_hallucinations(self):
        """Validates that sanitize_explanation scrubs fabricated citations cleanly."""
        text = "Under POLICY-R1 and fake EV-777, block card."
        sanitized = CitationValidator.sanitize_explanation(text, valid_evidence_ids=["EV-01"], valid_policy_ids=["POLICY-R1"])
        self.assertNotIn("EV-777", sanitized)
        self.assertIn("[INVALID_CITATION_REMOVED]", sanitized)
        self.assertIn("POLICY-R1", sanitized)
        print("PASS: Automated sanitization stripped fabricated tokens cleanly.")


if __name__ == "__main__":
    unittest.main()
