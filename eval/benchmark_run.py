"""
Benchmark 20-Case Run Orchestrator
Executes autonomous fraud investigations across all 20 benchmark cases (HHG-001 to HHG-020),
persists state to TigerGraph, and outputs strictly compliant JSON answer files to cases/.
"""

import os
import sys
import json
import time
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.graph import FraudInvestigatorAgent
from src.cases.manager import CaseManager


def run_all_benchmarks(output_dir: str = "cases") -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    print(f"============================================================")
    print(f" TIGERGRAPH AGENTIC FRAUD INVESTIGATOR: BENCHMARK RUN")
    print(f" Target: 20 Cases (HHG-001 -> HHG-020)")
    print(f" Output Directory: {output_dir}")
    print(f"============================================================\n")

    agent = FraudInvestigatorAgent()
    case_mgr = CaseManager(client=agent.client)

    results = []
    overall_start = time.time()

    for i in range(1, 21):
        case_id = f"HHG-{i:03d}"
        print(f"Investigating {case_id}...", end="", flush=True)
        t0 = time.time()
        
        answer = agent.investigate_case(case_id)
        case_mgr.write_case_to_graph(answer)
        
        out_path = os.path.join(output_dir, f"{case_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(answer, f, indent=2)
            
        elapsed = time.time() - t0
        case_obj = answer["case"]
        sar_obj = answer["sar"]
        actions = answer["next_best_actions"]["final"]
        
        print(f" Done ({elapsed:.2f}s) | Verdict: {case_obj['verdict'].upper()} | Pattern: {case_obj['pattern']} | SAR: {sar_obj['file']}")
        
        results.append({
            "case_id": case_id,
            "verdict": case_obj["verdict"],
            "prob": round(case_obj["fraud_probability"], 3),
            "pattern": case_obj["pattern"],
            "exposure": case_obj["exposure_usd"],
            "sar": sar_obj["file"],
            "num_actions": len(actions),
            "latency_s": answer["latency_s"],
        })

    total_time = time.time() - overall_start
    print(f"\n============================================================")
    print(f" BENCHMARK RUN COMPLETED in {total_time:.2f}s")
    print(f"============================================================\n")
    
    print(f"| Case ID | Verdict | Prob | Pattern | Exposure ($) | SAR | Actions | Latency |")
    print(f"|---|---|---|---|---|---|---|---|")
    for r in results:
        sar_str = "YES" if r["sar"] else "NO"
        print(f"| {r['case_id']} | {r['verdict'].upper()} | {r['prob']:.2f} | {r['pattern']} | ${r['exposure']:,.2f} | {sar_str} | {r['num_actions']} | {r['latency_s']:.2f}s |")

    return results


if __name__ == "__main__":
    run_all_benchmarks()
