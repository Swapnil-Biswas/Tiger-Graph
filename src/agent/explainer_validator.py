"""
Anti-Hallucination Explainer & Citation Validator
Enforces strict citation integrity:
1. Every claim must cite evidence IDs or policy IDs that exist in the active investigation state.
2. Strips or rejects any findings or narrative citing non-existent or fabricated IDs.
"""

import re
from typing import List, Dict, Any, Tuple


class CitationValidator:

    @staticmethod
    def validate_citations(
        statement: str,
        valid_evidence_ids: List[str],
        valid_policy_ids: List[str],
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Extracts cited IDs (e.g. EV-01, POLICY-R1, REG-FINCEN-SAR) and validates against active state.
        Returns: (is_valid, valid_citations_found, fabricated_citations_found)
        """
        # Find citations in brackets or tokens
        potential_ev_citations = re.findall(r"\b(EV-\d+)\b", statement)
        potential_policy_citations = re.findall(r"\b(POLICY-[A-Z0-9\-]+|REG-[A-Z0-9\-]+|TYP-[A-Z0-9\-]+)\b", statement)

        valid_ev_set = set(valid_evidence_ids)
        valid_pol_set = set(valid_policy_ids)

        valid_found = []
        fabricated_found = []

        for cid in potential_ev_citations:
            if cid in valid_ev_set:
                valid_found.append(cid)
            else:
                fabricated_found.append(cid)

        for pid in potential_policy_citations:
            if pid in valid_pol_set:
                valid_found.append(pid)
            else:
                fabricated_found.append(pid)

        is_valid = len(fabricated_found) == 0
        return is_valid, valid_found, fabricated_found

    @staticmethod
    def sanitize_explanation(
        explanation_text: str,
        valid_evidence_ids: List[str],
        valid_policy_ids: List[str],
    ) -> str:
        """
        Strips or flags any fabricated ID from explanation text.
        """
        is_valid, valid_found, fabricated_found = CitationValidator.validate_citations(
            explanation_text, valid_evidence_ids, valid_policy_ids
        )
        sanitized = explanation_text
        for fab_id in fabricated_found:
            sanitized = sanitized.replace(fab_id, "[INVALID_CITATION_REMOVED]")
        return sanitized


class AuditTrailSelfCritiqueVerifier:
    """
    Deterministic self-critique engine verifying narrative faithfulness,
    evidence traceability, entity cross-referencing, and anti-hallucination guarantees.
    """

    @classmethod
    def audit_case(
        cls,
        case_summary: str,
        case_dict: Dict[str, Any],
        active_evidence_items: List[Dict[str, Any]],
        valid_policy_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Conducts a deterministic self-critique pass over narrative, cross-referencing:
        1. Valid evidence IDs (EV-xx)
        2. Valid policy references (POLICY-xx)
        3. Grounded entity mentions (cards, customers, transactions)
        """
        if valid_policy_ids is None:
            valid_policy_ids = [
                "POLICY-R1", "POLICY-R2", "POLICY-R3", "POLICY-R4", "POLICY-R5",
                "POLICY-R6", "POLICY-R7", "POLICY-R8", "POLICY-R9", "POLICY-R10",
                "POLICY-APPROVALS", "POLICY-EVIDENCE-GATE", "REG-FINCEN-SAR",
                "TYP-CARD-TESTING", "TYP-CNP-NEW-DEV", "TYP-RAPID-DISPERSION",
                "TYP-GEO-IMPOSSIBLE", "TYP-DISCOVERED-PROXY-ROT", "TYP-DISCOVERED-DEVICE-POOL"
            ]

        valid_ev_ids = [ev.get("id") or ev.get("local_id") for ev in active_evidence_items if ev.get("id") or ev.get("local_id")]

        # 1. Citation check
        is_cit_valid, valid_citations, fabricated_citations = CitationValidator.validate_citations(
            case_summary, valid_ev_ids, valid_policy_ids
        )

        # 2. Entity Grounding Set
        grounded_cards = set(case_dict.get("connected_card_ids", []))
        if case_dict.get("card_id"):
            grounded_cards.add(str(case_dict["card_id"]))

        grounded_txns = set(str(t) for t in case_dict.get("affected_txn_ids", []))
        if case_dict.get("first_suspicious_txn_id"):
            grounded_txns.add(str(case_dict["first_suspicious_txn_id"]))

        # Include entities from evidence items
        for ev in active_evidence_items:
            for ent in ev.get("entity_ids", []):
                ent_s = str(ent).strip()
                if "-K" in ent_s:
                    grounded_cards.add(ent_s)
                elif ent_s.isdigit() and len(ent_s) >= 6:
                    grounded_txns.add(ent_s)

        # 3. Entity Extraction from summary
        mentioned_cards = re.findall(r"\b(C\d{3,6}-K\d+)\b", case_summary)
        mentioned_txns = re.findall(r"\b(\d{7})\b", case_summary)

        unverified_entities = []
        for c in mentioned_cards:
            if c not in grounded_cards:
                unverified_entities.append(f"Unverified Card: {c}")

        for t in mentioned_txns:
            if t not in grounded_txns:
                unverified_entities.append(f"Unverified Transaction: {t}")

        # 4. Faithfulness Score Computation
        penalties = len(fabricated_citations) * 0.25 + len(unverified_entities) * 0.15
        faithfulness_score = round(max(0.0, 1.0 - penalties), 2)
        passed = (len(fabricated_citations) == 0 and len(unverified_entities) == 0)

        critique_summary = (
            "PASS: All citations and entity mentions 100% grounded in verified evidence."
            if passed
            else f"FAIL: Detected {len(fabricated_citations)} fabricated citation(s) and {len(unverified_entities)} ungrounded entity mention(s)."
        )

        return {
            "passed": passed,
            "faithfulness_score": faithfulness_score,
            "valid_citations_count": len(valid_citations),
            "fabricated_citations": fabricated_citations,
            "unverified_entities": unverified_entities,
            "grounded_entities_count": len(grounded_cards) + len(grounded_txns),
            "critique_summary": critique_summary,
        }
