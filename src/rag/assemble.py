"""
Context Assembler Module (GraphRAG)
Synthesizes connected graph facts, graph topology metrics, applicable policy clauses,
pattern criteria, and memory precedents into a compact, structured brief capped by token budget.
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
        graph_topology: Optional[Dict[str, Any]] = None,
        max_chars: int = 3000,
    ) -> str:
        """
        Builds a structured, token-capped investigation brief integrating graph topology,
        evidence citations, typologies, policies, and prior case memory.
        """
        lines = []
        lines.append(f"=== INVESTIGATION CONTEXT BRIEF: CASE {case_id} ===")
        lines.append(f"TRIGGER: {trigger.get('trigger_type')} | Subject: Card {trigger.get('card_id')}, Customer {trigger.get('customer_id')}")
        lines.append(f"Trigger Text: {trigger.get('trigger_text')}")
        lines.append(f"Flagged Transaction: {trigger.get('flagged_txn_id')} (Risk Score: {trigger.get('risk_score', 'N/A')})\n")

        # 1. Graph Topology & Syndicate Nexus
        if graph_topology:
            lines.append("--- GRAPH TOPOLOGY & SYNDICATE METRICS ---")
            cards_cnt = graph_topology.get("connected_cards_count", 1)
            cust_cnt = graph_topology.get("connected_customers_count", 1)
            lines.append(f"- Subgraph Scope: {cards_cnt} card(s), {cust_cnt} customer(s)")
            
            dev_sharing = graph_topology.get("device_sharing", {})
            if dev_sharing.get("is_shared"):
                lines.append(f"- Device Nexus: Shared across {dev_sharing.get('distinct_cards_count', 0)} cards / {dev_sharing.get('distinct_customers_count', 0)} customers (Blast Radius: HIGH)")
            
            vel = graph_topology.get("velocity", {})
            if vel:
                w1 = vel.get("windows", {}).get("1h", {}).get("count", 0)
                w24 = vel.get("windows", {}).get("24h", {}).get("count", 0)
                spike = vel.get("velocity_spike_ratio", 1.0)
                lines.append(f"- Transaction Burst: {w1} txn(s)/1h, {w24} txn(s)/24h (Spike Ratio: {spike})")
            
            geo = graph_topology.get("geo", {})
            if geo and geo.get("anomalies_count", 0) > 0:
                lines.append(f"- Geo Impossible Travel: {geo['anomalies_count']} rapid inter-regional event(s) detected")

            ring = graph_topology.get("ring", {})
            if ring and ring.get("ring_detected"):
                lines.append(f"- Circular Flow: Synthetic transaction cycle detected (Length: {ring.get('cycle_length')})")
            
            if "as_of" in graph_topology:
                lines.append(f"- Temporal Isolation: Graph expansion strictly bounded as_of {graph_topology['as_of']}\n")

        # 2. Connected Graph Facts with Evidence IDs
        lines.append("--- CONNECTED GRAPH EVIDENCE ---")
        for ev in evidence_items[:6]:
            lines.append(f"[{ev['id']}] ({ev['source']}/{ev['ref']}): {ev['claim']}")

        # 3. Pattern Match Signatures
        lines.append("\n--- GRAPH PATTERN EVALUATION ---")
        best_pat = pattern_matches.get("best_pattern", "none")
        lines.append(f"Top Matching Typology: {best_pat}")
        for pat_name, pat_info in list(pattern_matches.get("patterns", {}).items())[:4]:
            match_status = "MATCH" if pat_info.get("match") else "NO_MATCH"
            lines.append(f"- {pat_name}: {match_status} (conf: {pat_info.get('confidence')})")

        # 4. Applicable Bank Fraud Policy Clauses
        lines.append("\n--- APPLICABLE FRAUD POLICY CLAUSES ---")
        for p in policy_clauses[:3]:
            text_snip = p.get('text', '')
            if len(text_snip) > 120:
                text_snip = text_snip[:120] + "..."
            lines.append(f"[{p['id']}] {p.get('title')}: {text_snip}")

        # 5. Memory Precedents
        lines.append("\n--- SIMILAR HISTORICAL CASES (CASE MEMORY) ---")
        if not memory_cases:
            lines.append("No directly matching historical cases found.")
        else:
            for mc in memory_cases[:2]:
                lines.append(f"[{mc['case_id']}] ({mc.get('match_type')}): outcome={mc.get('outcome')}, pattern={mc.get('pattern')}, exposure=${mc.get('exposure_usd')}")
                notes = mc.get('analyst_notes', '')
                if len(notes) > 90:
                    notes = notes[:90] + "..."
                lines.append(f"   Notes: {notes}")

        brief = "\n".join(lines)
        if len(brief) > max_chars:
            brief = brief[:max_chars - 35] + "\n... [Context truncated to budget]"
        return brief
