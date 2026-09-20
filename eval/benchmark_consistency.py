"""
Benchmark Self-Consistency Evaluation
Executes autonomous fraud investigations across all 20 benchmark cases (HHG-001 to HHG-020)
over 3 independent runs to evaluate recommendation variance, pattern stability, and determinism.
Target: 0.00% recommendation variance (100% deterministic reproducibility).
"""

import os
import sys
import json
import time
from typing import Dict, Any, List
import statistics

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.graph import FraudInvestigatorAgent


def run_consistency_evaluation(num_runs: int = 3, cases: List[str] = None) -> Dict[str, Any]:
    if cases is None:
        cases = [f"HHG-{i:03d}" for i in range(1, 21)]

    print("=" * 70)
    print(f" BENCHMARK SELF-CONSISTENCY EVALUATION ({num_runs} INDEPENDENT RUNS)")
    print(f" Cases ({len(cases)}): {cases[0]} ... {cases[-1]}")
    print("=" * 70)

    # Store results: case_id -> list of run summaries
    case_runs: Dict[str, List[Dict[str, Any]]] = {c: [] for c in cases}

    for run_idx in range(1, num_runs + 1):
        print(f"\n--- Starting Run {run_idx}/{num_runs} ---")
        agent = FraudInvestigatorAgent()
        
        t0 = time.time()
        for case_id in cases:
            ans = agent.investigate_case(case_id)
            case_obj = ans["case"]
            sar_obj = ans["sar"]
            final_actions = [a["action"] for a in ans["next_best_actions"]["final"]]
            pre_actions = [a["action"] for a in ans["next_best_actions"].get("pre_evidence", [])]
            ev_req = ans["next_best_actions"].get("evidence_request", {}).get("inquiry_type")

            case_runs[case_id].append({
                "run": run_idx,
                "verdict": case_obj["verdict"],
                "prob": round(float(case_obj["fraud_probability"]), 4),
                "pattern": case_obj["pattern"],
                "pre_actions": pre_actions,
                "evidence_request": ev_req,
                "final_actions": final_actions,
                "sar_file": sar_obj["file"]
            })
        print(f"Run {run_idx} finished in {time.time() - t0:.2f}s")

    # Analyze concordance and variance
    total_cases = len(cases)
    verdict_concordant = 0
    pattern_concordant = 0
    actions_concordant = 0
    sar_concordant = 0
    prob_variances = []

    print("\n" + "=" * 70)
    print(" CONSISTENCY SCOREBOARD")
    print("=" * 70)
    print(f"| Case ID | Verdicts | Prob Range | Patterns | Actions Match | SAR Match |")
    print(f"|---|---|---|---|---|---|")

    case_stability = {}

    for case_id in cases:
        runs = case_runs[case_id]
        verdicts = set(r["verdict"] for r in runs)
        patterns = set(r["pattern"] for r in runs)
        sars = set(r["sar_file"] for r in runs)
        action_tuples = set(tuple(r["final_actions"]) for r in runs)
        probs = [r["prob"] for r in runs]
        
        prob_range = max(probs) - min(probs)
        prob_var = statistics.variance(probs) if len(probs) > 1 else 0.0
        prob_variances.append(prob_var)

        v_match = len(verdicts) == 1
        p_match = len(patterns) == 1
        a_match = len(action_tuples) == 1
        s_match = len(sars) == 1

        if v_match:
            verdict_concordant += 1
        if p_match:
            pattern_concordant += 1
        if a_match:
            actions_concordant += 1
        if s_match:
            sar_concordant += 1

        case_stability[case_id] = {
            "verdict_stable": v_match,
            "pattern_stable": p_match,
            "actions_stable": a_match,
            "sar_stable": s_match,
            "prob_variance": prob_var,
            "sample_actions": runs[0]["final_actions"]
        }

        print(f"| {case_id} | {'/'.join(verdicts)} | {min(probs):.3f} - {max(probs):.3f} | {list(patterns)[0] if p_match else 'DIVERGENT'} | {'YES' if a_match else 'NO'} | {'YES' if s_match else 'NO'} |")

    recommendation_variance_rate = ((total_cases - actions_concordant) / total_cases) * 100.0
    mean_prob_variance = statistics.mean(prob_variances)

    print("\n" + "=" * 70)
    print(" SUMMARY METRICS")
    print("=" * 70)
    print(f"Total Cases Evaluated:       {total_cases}")
    print(f"Runs per Case:               {num_runs}")
    print(f"Verdict Concordance:         {verdict_concordant}/{total_cases} ({(verdict_concordant/total_cases)*100:.1f}%)")
    print(f"Pattern Concordance:         {pattern_concordant}/{total_cases} ({(pattern_concordant/total_cases)*100:.1f}%)")
    print(f"Action/Recommendation Match: {actions_concordant}/{total_cases} ({(actions_concordant/total_cases)*100:.1f}%)")
    print(f"SAR Decision Concordance:    {sar_concordant}/{total_cases} ({(sar_concordant/total_cases)*100:.1f}%)")
    print(f"Recommendation Variance:     {recommendation_variance_rate:.2f}% (Target: 0.00%)")
    print(f"Mean Probability Variance:   {mean_prob_variance:.6f}")
    print("=" * 70)

    return {
        "total_cases": total_cases,
        "num_runs": num_runs,
        "verdict_concordance_pct": (verdict_concordant / total_cases) * 100.0,
        "pattern_concordance_pct": (pattern_concordant / total_cases) * 100.0,
        "action_concordance_pct": (actions_concordant / total_cases) * 100.0,
        "recommendation_variance_pct": recommendation_variance_rate,
        "mean_prob_variance": mean_prob_variance,
        "case_stability": case_stability
    }


if __name__ == "__main__":
    results = run_consistency_evaluation()
    if results["recommendation_variance_pct"] > 0.0:
        print("\nFAILURE: Recommendation variance detected!")
        sys.exit(1)
    else:
        print("\nSUCCESS: 100% Deterministic Reproducibility across all benchmark cases.")
        sys.exit(0)
