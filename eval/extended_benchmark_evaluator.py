#!/usr/bin/env python3
"""
TigerGraph Agentic Fraud Investigator - Extended Benchmark Evaluator
====================================================================
Evaluates the 50-case extended synthetic benchmark suite against schema
conformance, regulatory validity, and policy metrics.

Usage:
    python eval/extended_benchmark_evaluator.py [--cases-dir eval/extended_cases] [--json]
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from eval.validate_answers import validate_single_answer


class ExtendedBenchmarkEvaluator:
    """Evaluates extended high-stress cases for schema and policy compliance."""

    def __init__(self, cases_dir: Path):
        self.cases_dir = cases_dir.resolve()

    def evaluate_all(self) -> Dict[str, Any]:
        """Validate all cases in directory and aggregate metrics."""
        case_files = sorted(self.cases_dir.glob("EXT-*.json"))
        total = len(case_files)
        if total == 0:
            return {"total_cases": 0, "status": "NO_CASES"}

        passed_count = 0
        fraud_count = 0
        legit_count = 0
        sar_count = 0
        total_exposure = 0.0
        case_results = []

        for cf in case_files:
            case_id = cf.stem
            try:
                data = json.loads(cf.read_text(encoding="utf-8"))
                errors = validate_single_answer(data, case_id)
                is_valid = len(errors) == 0
                if is_valid:
                    passed_count += 1

                c = data.get("case", {})
                verdict = c.get("verdict", "unknown")
                if verdict == "fraud":
                    fraud_count += 1
                elif verdict == "legitimate":
                    legit_count += 1

                exp = c.get("exposure_usd", 0.0)
                total_exposure += exp

                if data.get("sar", {}).get("file", False):
                    sar_count += 1

                case_results.append({
                    "case_id": case_id,
                    "valid": is_valid,
                    "errors": errors,
                    "verdict": verdict,
                    "exposure_usd": exp,
                    "pattern": c.get("pattern", "unknown"),
                })
            except Exception as e:
                case_results.append({
                    "case_id": case_id,
                    "valid": False,
                    "errors": [f"Exception: {e}"],
                    "verdict": "error",
                    "exposure_usd": 0.0,
                    "pattern": "error",
                })

        pass_rate = round((passed_count / total) * 100.0, 2)
        all_passed = passed_count == total

        return {
            "status": "PASS" if all_passed else "FAIL",
            "total_cases": total,
            "passed_cases": passed_count,
            "failed_cases": total - passed_count,
            "pass_rate_pct": pass_rate,
            "fraud_cases": fraud_count,
            "legitimate_cases": legit_count,
            "sar_filings_triggered": sar_count,
            "total_exposure_usd": round(total_exposure, 2),
            "case_results": case_results,
        }


def print_report(results: Dict[str, Any]) -> None:
    """Print human-readable evaluation summary."""
    print("\n" + "=" * 70)
    print("  TIGERGRAPH EXTENDED BENCHMARK EVALUATOR (50-CASE HIGH-STRESS SUITE)")
    print("=" * 70)
    print(f"Total Cases Evaluated   : {results['total_cases']}")
    print(f"Schema Validation Passed: {results['passed_cases']}/{results['total_cases']} ({results['pass_rate_pct']}%)")
    print(f"Fraud / Legitimate Ratio: {results['fraud_cases']} / {results['legitimate_cases']}")
    print(f"Total Fraud Exposure    : ${results['total_exposure_usd']:,.2f} USD")
    print(f"SAR Filings Triggered   : {results['sar_filings_triggered']}")
    print("-" * 70)
    print(f"OVERALL STATUS          : [{results['status']}]")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Evaluate extended benchmark cases")
    parser.add_argument("--cases-dir", default="eval/extended_cases", help="Directory of extended cases")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    cases_path = ROOT_DIR / args.cases_dir
    evaluator = ExtendedBenchmarkEvaluator(cases_path)
    results = evaluator.evaluate_all()

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    sys.exit(0 if results["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
