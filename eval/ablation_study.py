"""
Architectural Component Ablation Study (eval/ablation_study.py)
Evaluates the impact of core agentic subsystems on historical backtest cases:
1. Full System (Graph + Memory + Policy)
2. Graph Signals OFF (No topological traversals, velocity, or device sharing)
3. Case Memory OFF (No empirical Bayes prior adjustment, historical precedents zeroed)
4. Policy Rules OFF (No Rule R1/R4/R5/R7/R10 guards, pure raw thresholding)
"""

import os
import sys
import time
from typing import Dict, Any, List
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.graph import FraudInvestigatorAgent
from src.policy.engine import PolicyEngine


def run_ablation_study(sample_size: int = 100, random_seed: int = 42) -> Dict[str, Any]:
    print("============================================================")
    print(" TIGERGRAPH AGENTIC FRAUD INVESTIGATOR: ABLATION STUDY")
    print(f" Sample Size: {sample_size} cases (stratified from closed cases history)")
    print("============================================================\n")

    agent = FraudInvestigatorAgent()
    df_closed = pd.read_csv("data/closed_cases_history.csv")

    df_fraud = df_closed[df_closed["outcome"] == "confirmed_fraud"]
    df_cleared = df_closed[df_closed["outcome"] == "cleared"]

    n_fraud = int(sample_size * 0.838)
    n_cleared = sample_size - n_fraud

    sample_fraud = df_fraud.sample(n=n_fraud, random_state=random_seed)
    sample_cleared = df_cleared.sample(n=n_cleared, random_state=random_seed)
    sample_df = pd.concat([sample_fraud, sample_cleared]).sample(frac=1.0, random_state=random_seed).reset_index(drop=True)

    conditions = [
        {"name": "Full System (Baseline)", "kwargs": {}},
        {"name": "Graph Signals OFF", "kwargs": {"ablate_graph": True}},
        {"name": "Case Memory OFF", "kwargs": {"ablate_memory": True}},
        {"name": "Policy Rules OFF", "kwargs": {"ablate_policy": True}},
    ]

    report = {}

    for cond in conditions:
        name = cond["name"]
        kwargs = cond["kwargs"]
        print(f"--- Running Condition: {name} ---")

        tp, fp, tn, fn = 0, 0, 0, 0
        sar_matches = 0
        policy_violations = 0
        latencies = []

        for idx, row in sample_df.iterrows():
            case_id = str(row["case_id"])
            true_outcome = str(row["outcome"])
            true_is_fraud = (true_outcome == "confirmed_fraud")
            true_sar = (str(row.get("report_filed", "")).strip().lower() in ["yes", "true", "1"])

            t0 = time.time()
            try:
                ans = agent.investigate_case(case_id, **kwargs)
                pred_verdict = ans["case"]["verdict"]
                pred_sar = ans["sar"]["file"]
                actions = ans["next_best_actions"]["final"]
                exposure = ans["case"]["exposure_usd"]
            except Exception as e:
                print(f"Error on case {case_id}: {e}")
                continue

            lat = time.time() - t0
            latencies.append(lat)

            pred_is_fraud = (pred_verdict == "fraud")

            if true_is_fraud and pred_is_fraud:
                tp += 1
            elif not true_is_fraud and pred_is_fraud:
                fp += 1
            elif not true_is_fraud and not pred_is_fraud:
                tn += 1
            elif true_is_fraud and not pred_is_fraud:
                fn += 1

            if pred_sar == true_sar:
                sar_matches += 1

            # Check for policy violations
            for act in actions:
                action_type = act.get("action") if isinstance(act, dict) else act.action
                check_res = PolicyEngine.check(
                    action=action_type,
                    fraud_probability=ans["case"]["fraud_probability"],
                    exposure_usd=exposure,
                    signal_count=len(ans.get("evidence", [])),
                    evidence_claims=ans.get("evidence", []),
                )
                if check_res["decision"] == "deny":
                    policy_violations += 1

        total = tp + fp + tn + fn
        precision = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        fpr = (fp / (fp + tn)) * 100.0 if (fp + tn) > 0 else 0.0
        sar_acc = (sar_matches / total) * 100.0 if total > 0 else 0.0
        avg_lat = (sum(latencies) / len(latencies)) * 1000.0 if latencies else 0.0

        report[name] = {
            "precision": round(precision, 2),
            "recall": round(recall, 2),
            "f1": round(f1, 2),
            "fpr": round(fpr, 2),
            "sar_accuracy": round(sar_acc, 2),
            "policy_violations": policy_violations,
            "avg_latency_ms": round(avg_lat, 2),
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
        }

        print(f"  Precision: {precision:.1f}%, Recall: {recall:.1f}%, F1: {f1:.1f}%, FPR: {fpr:.1f}%, Violations: {policy_violations}\n")

    # Print summary scoreboard
    print("==========================================================================================")
    print(" ABLATION STUDY SCOREBOARD")
    print("==========================================================================================")
    print(f"| Condition | Precision | Recall | F1-Score | FPR | Violations | Latency (ms) |")
    print(f"|---|---|---|---|---|---|---|")
    for name, m in report.items():
        print(f"| {name} | {m['precision']:.1f}% | {m['recall']:.1f}% | {m['f1']:.1f}% | {m['fpr']:.1f}% | {m['policy_violations']} | {m['avg_latency_ms']:.1f} ms |")
    print("==========================================================================================\n")

    return report


if __name__ == "__main__":
    run_ablation_study(sample_size=100)
