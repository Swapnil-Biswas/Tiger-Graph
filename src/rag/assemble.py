"""
Context Assembler Module (GraphRAG)
Synthesizes connected graph facts, applicable policy clauses, pattern criteria,
and memory precedents into a compact, structured brief capped by token budget.
"""

from typing import Dict, List, Any, Optional


class ContextAssembler:
    @staticmethod
    def assemble_brief(
        case_id: str,
        trigger: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
        policy_clauses: List[Dict[str, Any]],
        pattern_matches: Dict[str, Any],
        memory_cases: List[Dict[str, Any]],
        max_chars: int = 4000,
    ) -> str:
        """
        Builds a structured, token-capped investigation brief.
        """
        lines = []
        lines.append(f"=== INVESTIGATION CONTEXT BRIEF: CASE {case_id} ===")
        lines.append(f"TRIGGER: {trigger.get('trigger_type')} | Subject: Card {trigger.get('card_id')}, Customer {trigger.get('customer_id')}")
        lines.append(f"Trigger Text: {trigger.get('trigger_text')}")
        lines.append(f"Flagged Transaction: {trigger.get('flagged_txn_id')} (Risk Score: {trigger.get('risk_score', 'N/A')})\n")

        # 1. Connected Graph Facts with Evidence IDs
        lines.append("--- CONNECTED GRAPH EVIDENCE ---")
        for ev in evidence_items[:8]:
            lines.append(f"[{ev['id']}] ({ev['source']}/{ev['ref']}): {ev['claim']}")

        # 2. Pattern Match Signatures
        lines.append("\n--- GRAPH PATTERN EVALUATION ---")
        best_pat = pattern_matches.get("best_pattern", "none")
        lines.append(f"Top Matching Typology: {best_pat}")
        for pat_name, pat_info in pattern_matches.get("patterns", {}).items():
            match_status = "MATCH" if pat_info.get("match") else "NO_MATCH"
            lines.append(f"- {pat_name}: {match_status} (conf: {pat_info.get('confidence')})")

        # 3. Applicable Bank Fraud Policy Clauses
        lines.append("\n--- APPLICABLE FRAUD POLICY CLAUSES ---")
        for p in policy_clauses[:4]:
            lines.append(f"[{p['id']}] {p['title']}: {p['text']}")

        # 4. Memory Precedents
        lines.append("\n--- SIMILAR HISTORICAL CASES (CASE MEMORY) ---")
        if not memory_cases:
            lines.append("No directly matching historical cases found.")
        else:
            for mc in memory_cases[:3]:
                lines.append(f"[{mc['case_id']}] ({mc.get('match_type')}): outcome={mc.get('outcome')}, pattern={mc.get('pattern')}, exposure=${mc.get('exposure_usd')}")
                notes = mc.get('analyst_notes', '')
                if len(notes) > 120:
                    notes = notes[:120] + "..."
                lines.append(f"   Notes: {notes}")

        brief = "\n".join(lines)
        if len(brief) > max_chars:
            brief = brief[:max_chars - 30] + "\n... [Context truncated to budget]"
        return brief
