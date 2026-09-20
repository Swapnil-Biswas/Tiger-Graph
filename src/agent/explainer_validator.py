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
