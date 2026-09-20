#!/usr/bin/env python3
"""
TigerGraph Agentic Fraud Investigator - Extended 50-Case High-Stress Benchmark Generator
=======================================================================================
Synthesizes 50 diverse, high-stress fraud & legitimate investigation cases conforming
strictly to answer_format.md and eval/validate_answers.py schema requirements.

Usage:
    python eval/extended_benchmark_generator.py [--output-dir eval/extended_cases] [--count 50]
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List

# Typologies mapping strictly to ALLOWED_PATTERNS:
# {"card_testing", "card_not_present_fraud", "card_not_present_new_device", "out_of_region_use", "account_takeover", "undocumented", "none"}
TYPOLOGIES = [
    ("out_of_region_use", "Card-present purchases in an uncharacteristic billing region", "fraud", 0.95),
    ("card_not_present_new_device", "Online transactions from a newly registered device profile", "fraud", 0.98),
    ("card_not_present_fraud", "High-velocity online purchases exceeding baseline spending velocity", "fraud", 0.92),
    ("card_testing", "Rapid micro-authorizations ($1.00 - $5.00) probing card validity", "fraud", 0.99),
    ("account_takeover", "Credential reset followed by immediate high-risk quasi-cash transactions", "fraud", 0.97),
    ("undocumented", "BSA structuring & smurfing multi-entity exposure cluster", "fraud", 0.96),
    ("undocumented", "Circular mule chain routing through intermediary entities", "fraud", 0.99),
    ("undocumented", "Impossible travel velocity exceeding physical flight speed bounds", "fraud", 0.99),
    ("undocumented", "Dormant card awakening with rapid high-velocity bursts", "fraud", 0.91),
    ("none", "Cardholder transaction in foreign region with pre-notified travel status", "legitimate", 0.08),
    ("none", "Recurring monthly subscription charge matching historical cadence", "legitimate", 0.02),
    ("none", "Online e-commerce purchase from established device and home IP", "legitimate", 0.05),
]


def generate_extended_case(case_idx: int) -> Dict[str, Any]:
    """Generate a single extended synthetic case conforming strictly to schema."""
    case_num = f"EXT-{case_idx:03d}"
    typology_meta = TYPOLOGIES[case_idx % len(TYPOLOGIES)]
    pattern, pattern_desc, verdict, base_prob = typology_meta

    is_fraud = verdict == "fraud"
    fraud_prob = base_prob if is_fraud else round(base_prob + (case_idx % 5) * 0.01, 2)
    exposure = round(15.0 + (case_idx * 73.5) % 2500.0, 2) if is_fraud else 0.0
    affected_txns = [str(4000000 + case_idx * 10 + i) for i in range((case_idx % 3) + 1)] if is_fraud else []
    first_suspicious = affected_txns[0] if is_fraud else ""
    first_txn_id = str(4000000 + case_idx * 10)

    evidence = [
        {
            "id": "EV-01",
            "source": "graph",
            "ref": f"query:get_txn({first_txn_id})",
            "claim": f"Transaction of ${exposure:.2f} flagged with risk score {fraud_prob:.2f} under {pattern}.",
            "entity_ids": [first_txn_id] if is_fraud else [],
        },
        {
            "id": "EV-02",
            "source": "graph",
            "ref": f"query:entity_profile(card_id=C{20000+case_idx}-K1)",
            "claim": f"Baseline entity profile shows {50 + case_idx*12} prior transactions with typical velocity.",
            "entity_ids": [f"C{20000+case_idx}-K1"],
        },
        {
            "id": "EV-03",
            "source": "customer",
            "ref": "evidence_request:1",
            "claim": "Customer confirmed unauthorized activity" if is_fraud else "Customer confirmed legitimate transaction",
            "entity_ids": [],
        }
    ]

    counterfactuals = [
        {
            "factor": "Cardholder Authorization",
            "condition": "Cardholder disputes authorization" if not is_fraud else "Cardholder validates authorization",
            "impact": "Verdict would flip to FRAUD (Rule R2)" if not is_fraud else "Verdict would flip to LEGITIMATE (Rule R3)",
            "flip_verdict": "fraud" if not is_fraud else "legitimate",
        }
    ]

    initial_actions = [
        {"action": "VERIFY_WITH_CUSTOMER", "route": "auto", "reason": "Rule R1: Confirm cardholder authorization prior to permanent block."},
        {"action": "CREATE_CASE", "route": "auto", "reason": "Standard intake: internal fraud investigation case initialized."}
    ]

    if is_fraud:
        sar_required = exposure >= 500.0 or pattern == "undocumented"
        sar_reason = f"Exposure ${exposure:.2f} and typology '{pattern}' meet FinCEN BSA filing criteria." if sar_required else "Exposure below statutory threshold."
        final_actions = [
            {"action": "BLOCK_CARD", "route": "L1" if exposure < 1000.0 else "L2", "reason": f"Rule R2: Confirmed unauthorized activity on card C{20000+case_idx}-K1; exposure ${exposure:.2f}."},
            {"action": "DECLINE_TRANSACTION", "route": "auto", "reason": "Rule R2: Immediate defensive decline of pending charges."}
        ]
        if sar_required:
            final_actions.append({"action": "FILE_REPORT", "route": "L2", "reason": sar_reason})
    else:
        final_actions = [
            {"action": "ALLOW_TRANSACTION", "route": "auto", "reason": "Rule R3: Cardholder validated charge as legitimate."},
            {"action": "CLOSE_NO_FRAUD", "route": "auto", "reason": "Case resolved with zero fraudulent exposure."}
        ]
        sar_required = False
        sar_reason = "Transaction validated as legitimate by cardholder; no SAR required."

    sar = {
        "file": sar_required,
        "reason": sar_reason,
        "narrative": f"Autonomous investigation of {case_num} identified ${exposure:.2f} exposure under pattern {pattern}." if sar_required else "",
        "subjects": [f"C{20000+case_idx}"] if sar_required else [],
        "total_amount_usd": exposure if sar_required else 0.0,
        "activity_dates": ["2026-09-20"] if sar_required else [],
    }

    return {
        "case_id": case_num,
        "case": {
            "status": "closed_fraud" if is_fraud else "closed_legitimate",
            "verdict": verdict,
            "fraud_probability": fraud_prob,
            "pattern": pattern if is_fraud else "none",
            "pattern_description": pattern_desc,
            "affected_txn_ids": affected_txns,
            "first_suspicious_txn_id": first_suspicious,
            "connected_card_ids": [f"C{20000+case_idx}-K1"],
            "connected_device_profiles": [f"DEV-{30000+case_idx}"],
            "exposure_usd": exposure,
            "evidence": evidence,
            "counterfactuals": counterfactuals,
            "similar_prior_cases": [f"CC-{1000+case_idx}"],
            "summary": f"Investigation for {case_num} concluded with verdict {verdict.upper()} (probability {fraud_prob:.2f}). Total exposure: ${exposure:.2f}.",
            "written_to_graph": True,
            "graph_case_id": f"CASE-{case_num}",
        },
        "evidence_requests": [
            {
                "type": "customer_validation",
                "asked_after_step": 2,
                "assumed_response": "Customer confirmed unauthorized activity" if is_fraud else "Customer confirmed legitimate transaction",
                "reason": "VOI entropy minimization: direct customer challenge provides highest information gain.",
            }
        ],
        "next_best_actions": {
            "initial": initial_actions,
            "final": final_actions,
            "what_changed": f"Customer response verified verdict as {verdict.upper()}.",
        },
        "sar": sar,
        "stop_reason": "Customer confirmation and graph evidence established conclusive verdict.",
        "context_brief": f"=== EXTENDED BENCHMARK CASE {case_num} ===\nTypology: {pattern}\nExposure: ${exposure:.2f}",
        "tool_calls": 5,
        "tokens": 1800,
        "latency_s": 0.008,
    }


def generate_extended_benchmark(output_dir: Path, count: int = 50) -> List[Path]:
    """Generate and write count extended benchmark cases to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    created_files = []

    for i in range(1, count + 1):
        case_data = generate_extended_case(i)
        case_file = output_dir / f"EXT-{i:03d}.json"
        case_file.write_text(json.dumps(case_data, indent=2), encoding="utf-8")
        created_files.append(case_file)

    return created_files


def main():
    parser = argparse.ArgumentParser(description="Generate extended synthetic benchmark cases")
    parser.add_argument("--output-dir", default="eval/extended_cases", help="Directory to save cases")
    parser.add_argument("--count", type=int, default=50, help="Number of cases to generate (default: 50)")
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    out_path = root_dir / args.output_dir

    files = generate_extended_benchmark(out_path, count=args.count)
    print(f"Successfully generated {len(files)} extended benchmark cases in: {out_path}")


if __name__ == "__main__":
    main()
