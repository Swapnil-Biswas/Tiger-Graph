#!/usr/bin/env python3
"""
TigerGraph Agentic Fraud Investigator - Terminal CLI Investigator & Live Dashboard
==================================================================================
Interactive command-line interface for fraud analysts and operations teams.
Supports case dossier inspection, benchmark analytics, and real-time streaming feeds.

Usage:
    python src/cli/investigate_cli.py --list
    python src/cli/investigate_cli.py --case HHG-001 [--json]
    python src/cli/investigate_cli.py --benchmark [--json]
    python src/cli/investigate_cli.py --stream [--duration 5]
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# Color formatting
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _safe_str(val: Any) -> str:
    """Sanitize strings for Windows cp1252 terminal compatibility."""
    if val is None:
        return ""
    s = str(val)
    # Replace common unicode math/arrow characters with ASCII equivalents
    return (
        s.replace("\u2264", "<=")
        .replace("\u2265", ">=")
        .replace("\u2192", "->")
        .replace("\u2022", "*")
        .replace("\u2014", "--")
    )


class FraudInvestigationCLI:
    """Terminal investigator and analytics dashboard."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            self.root_dir = Path(__file__).resolve().parent.parent.parent
        else:
            self.root_dir = Path(root_dir).resolve()
        self.cases_dir = self.root_dir / "cases"

    def list_cases(self) -> List[Dict[str, Any]]:
        """List all benchmark cases with key summary fields."""
        cases = []
        if not self.cases_dir.is_dir():
            return cases

        case_files = sorted(self.cases_dir.glob("HHG-*.json"))
        for cf in case_files:
            try:
                data = json.loads(cf.read_text(encoding="utf-8"))
                c = data.get("case", {})
                cases.append({
                    "case_id": data.get("case_id", cf.stem),
                    "verdict": c.get("verdict", "unknown").upper(),
                    "fraud_probability": c.get("fraud_probability", 0.0),
                    "pattern": c.get("pattern", "unknown"),
                    "exposure_usd": c.get("exposure_usd", 0.0),
                    "sar_required": data.get("sar", {}).get("file", False),
                    "status": c.get("status", "unknown"),
                })
            except Exception:
                continue
        return cases

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Load and return full case data."""
        # Normalize case_id: accept '001', 'HHG-001', 'hhg-001'
        norm_id = case_id.upper()
        if not norm_id.startswith("HHG-"):
            norm_id = f"HHG-{norm_id.zfill(3)}"

        case_file = self.cases_dir / f"{norm_id}.json"
        if not case_file.is_file():
            return None

        try:
            return json.loads(case_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def get_benchmark_analytics(self) -> Dict[str, Any]:
        """Aggregate summary statistics across all benchmark cases."""
        cases = self.list_cases()
        total_cases = len(cases)
        if total_cases == 0:
            return {"total_cases": 0}

        verdicts = {}
        patterns = {}
        total_exposure = 0.0
        sar_count = 0
        prob_sum = 0.0

        for c in cases:
            v = c["verdict"]
            verdicts[v] = verdicts.get(v, 0) + 1
            p = c["pattern"]
            patterns[p] = patterns.get(p, 0) + 1
            total_exposure += c["exposure_usd"]
            if c["sar_required"]:
                sar_count += 1
            prob_sum += c["fraud_probability"]

        return {
            "total_cases": total_cases,
            "verdict_distribution": verdicts,
            "pattern_distribution": patterns,
            "total_exposure_usd": round(total_exposure, 2),
            "sar_filing_count": sar_count,
            "sar_filing_rate": round(sar_count / total_cases, 4),
            "average_fraud_probability": round(prob_sum / total_cases, 4),
        }

    def print_case_list(self) -> None:
        """Render formatted case listing table."""
        cases = self.list_cases()
        print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
        print(f"{BOLD}{CYAN}  TIGERGRAPH AGENTIC FRAUD INVESTIGATOR - BENCHMARK CASES ({len(cases)}){RESET}")
        print(f"{BOLD}{CYAN}{'='*80}{RESET}")
        header = f"{'Case ID':<10} | {'Verdict':<12} | {'Prob':<6} | {'Exposure ($)':<14} | {'SAR':<5} | {'Pattern':<25}"
        print(f"{BOLD}{header}{RESET}")
        print(f"{'-'*10}-+-{'-'*12}-+-{'-'*6}-+-{'-'*14}-+-{'-'*5}-+-{'-'*25}")

        for c in cases:
            v_color = RED if c["verdict"] == "FRAUD" else (GREEN if c["verdict"] == "LEGITIMATE" else YELLOW)
            sar_str = f"{RED}YES{RESET}" if c["sar_required"] else f"{DIM}NO{RESET} "
            exp_str = f"${c['exposure_usd']:>11.2f}"
            prob_str = f"{c['fraud_probability']:>4.2f}"
            print(f"{BOLD}{c['case_id']:<10}{RESET} | {v_color}{c['verdict']:<12}{RESET} | {prob_str} | {exp_str} | {sar_str} | {c['pattern']:<25}")

        print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")

    def print_case_dossier(self, data: Dict[str, Any]) -> None:
        """Render detailed case investigation dossier."""
        case_id = data.get("case_id", "UNKNOWN")
        c = data.get("case", {})
        actions = data.get("next_best_actions", {})
        sar = data.get("sar", {})

        verdict = c.get("verdict", "unknown").upper()
        v_color = RED if verdict == "FRAUD" else (GREEN if verdict == "LEGITIMATE" else YELLOW)
        prob = c.get("fraud_probability", 0.0)
        exp = c.get("exposure_usd", 0.0)

        print(f"\n{BOLD}{CYAN}{'='*75}{RESET}")
        print(f"{BOLD}{CYAN}  INVESTIGATION DOSSIER: {case_id}{RESET}")
        print(f"{BOLD}{CYAN}{'='*75}{RESET}")

        print(f"{BOLD}Verdict           :{RESET} {v_color}{verdict}{RESET} (Fraud Probability: {prob:.2f})")
        print(f"{BOLD}Typology Pattern  :{RESET} {c.get('pattern', 'unknown')}")
        print(f"{BOLD}Total Exposure    :{RESET} ${exp:,.2f} USD")
        print(f"{BOLD}Affected Txns     :{RESET} {c.get('affected_txn_ids', [])}")
        print(f"{BOLD}Status            :{RESET} {c.get('status', 'unknown')}")

        # Evidence
        evidence = c.get("evidence", [])
        print(f"\n{BOLD}--- Key Graph & Sensor Evidence ({len(evidence)}) ---{RESET}")
        for ev in evidence:
            ev_id = ev.get("id", "EV")
            src = ev.get("source", "graph")
            claim = _safe_str(ev.get("claim", ""))
            print(f"  [{BOLD}{ev_id}{RESET}] ({src}): {claim}")

        # Next Best Actions
        initial_acts = actions.get("initial", [])
        final_acts = actions.get("final", [])
        print(f"\n{BOLD}--- Next Best Actions & Routing ---{RESET}")
        if initial_acts:
            print(f"  {DIM}Initial Actions:{RESET}")
            for a in initial_acts:
                reason = _safe_str(a.get('reason', ''))
                print(f"    - {BOLD}{a.get('action')}{RESET} [{a.get('route')}]: {reason}")
        if final_acts:
            print(f"  {BOLD}Final Actions:{RESET}")
            for a in final_acts:
                route_col = RED if a.get('route') == 'L2' else (YELLOW if a.get('route') == 'L1' else GREEN)
                reason = _safe_str(a.get('reason', ''))
                print(f"    - {BOLD}{a.get('action')}{RESET} [{route_col}{a.get('route')}{RESET}]: {reason}")
        if actions.get("what_changed"):
            print(f"  {DIM}What Changed:{RESET} {_safe_str(actions.get('what_changed'))}")

        # SAR
        print(f"\n{BOLD}--- Regulatory SAR Compliance ---{RESET}")
        if sar.get("file"):
            print(f"  {RED}[SAR REQUIRED]{RESET} Reason: {_safe_str(sar.get('reason'))}")
            print(f"  Total SAR Exposure: ${sar.get('total_amount_usd', 0.0):,.2f}")
        else:
            print(f"  {GREEN}[NO SAR]{RESET} Reason: {_safe_str(sar.get('reason'))}")

        # Counterfactuals
        cfs = c.get("counterfactuals", [])
        if cfs:
            print(f"\n{BOLD}--- Decision Sensitivity (Counterfactuals) ---{RESET}")
            for cf in cfs:
                factor = _safe_str(cf.get('factor', ''))
                condition = _safe_str(cf.get('condition', ''))
                impact = _safe_str(cf.get('impact', ''))
                print(f"  * {BOLD}{factor}{RESET}: {condition}")
                print(f"    -> Impact: {impact}")

        print(f"{BOLD}{CYAN}{'='*75}{RESET}\n")

    def print_benchmark_summary(self, analytics: Dict[str, Any]) -> None:
        """Render benchmark analytics summary."""
        print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
        print(f"{BOLD}{CYAN}  TIGERGRAPH FRAUD INVESTIGATOR: BENCHMARK ANALYTICS{RESET}")
        print(f"{BOLD}{CYAN}{'='*65}{RESET}")
        print(f"Total Evaluated Cases   : {analytics['total_cases']}")
        print(f"Total Fraud Exposure    : ${analytics['total_exposure_usd']:,.2f} USD")
        print(f"Average Fraud Prob      : {analytics['average_fraud_probability']:.4f}")
        print(f"SAR Filings Triggered   : {analytics['sar_filing_count']} ({analytics['sar_filing_rate']*100:.1f}%)")
        print(f"\n{BOLD}Verdict Breakdown:{RESET}")
        for v, count in analytics["verdict_distribution"].items():
            print(f"  - {v:<12}: {count:>2} cases ({count/analytics['total_cases']*100:.1f}%)")
        print(f"\n{BOLD}Typology Breakdown:{RESET}")
        for p, count in analytics["pattern_distribution"].items():
            print(f"  - {p:<25}: {count:>2} cases")
        print(f"{BOLD}{CYAN}{'='*65}{RESET}\n")

    def run_streaming_feed(self, duration_seconds: int = 5, interval_seconds: float = 0.5) -> None:
        """Render live streaming transaction feed in terminal."""
        print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
        print(f"{BOLD}{CYAN}  LIVE STREAMING TRANSACTION INFLUX MONITOR ({duration_seconds}s){RESET}")
        print(f"{BOLD}{CYAN}{'='*70}{RESET}")
        print(f"{'Time':<10} | {'Card ID':<12} | {'Amount ($)':<12} | {'MCC':<6} | {'Risk':<6} | {'Status':<15}")
        print(f"{'-'*10}-+-{'-'*12}-+-{'-'*12}-+-{'-'*6}-+-{'-'*6}-+-{'-'*15}")

        mock_events = [
            ("12:00:01", "C10042-K1", 45.20, 5411, 0.08, f"{GREEN}[NORMAL]{RESET}"),
            ("12:00:02", "C10042-K1", 850.00, 6051, 0.88, f"{RED}[HIGH_RISK_MCC]{RESET}"),
            ("12:00:03", "C11919-K2", 12.50, 5812, 0.04, f"{GREEN}[NORMAL]{RESET}"),
            ("12:00:04", "C11919-K2", 345.00, 4829, 0.74, f"{YELLOW}[VELOCITY_SPIKE]{RESET}"),
            ("12:00:05", "C13881-K1", 99.99, 5311, 0.12, f"{GREEN}[NORMAL]{RESET}"),
            ("12:00:06", "C14201-K3", 1450.00, 6051, 0.94, f"{RED}[CRITICAL_ANOMALY]{RESET}"),
        ]

        start_time = time.time()
        idx = 0
        while (time.time() - start_time) < duration_seconds and idx < len(mock_events):
            evt = mock_events[idx % len(mock_events)]
            t_str, card, amt, mcc, risk, stat = evt
            print(f"{t_str:<10} | {card:<12} | ${amt:>10.2f} | {mcc:<6} | {risk:<6.2f} | {stat}")
            sys.stdout.flush()
            time.sleep(interval_seconds)
            idx += 1

        print(f"{BOLD}{CYAN}{'-'*70}{RESET}")
        print(f"{BOLD}{GREEN}  Streaming window closed cleanly. Influx rate: normal.{RESET}")
        print(f"{BOLD}{CYAN}{'='*70}{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="TigerGraph Agentic Fraud Investigator CLI")
    parser.add_argument("--list", action="store_true", help="List all benchmark cases")
    parser.add_argument("--case", type=str, help="Inspect detailed dossier for a case ID (e.g. HHG-001)")
    parser.add_argument("--benchmark", action="store_true", help="Display aggregate benchmark analytics")
    parser.add_argument("--stream", action="store_true", help="Run live streaming monitor")
    parser.add_argument("--duration", type=int, default=5, help="Duration for stream monitor in seconds")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args = parser.parse_args()

    cli = FraudInvestigationCLI()

    if args.list:
        cases = cli.list_cases()
        if args.json:
            print(json.dumps(cases, indent=2))
        else:
            cli.print_case_list()

    elif args.case:
        data = cli.get_case(args.case)
        if not data:
            print(f"Error: Case '{args.case}' not found.", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            cli.print_case_dossier(data)

    elif args.benchmark:
        analytics = cli.get_benchmark_analytics()
        if args.json:
            print(json.dumps(analytics, indent=2))
        else:
            cli.print_benchmark_summary(analytics)

    elif args.stream:
        cli.run_streaming_feed(duration_seconds=args.duration)

    else:
        # Default action if no flags passed: show list
        cli.print_case_list()


if __name__ == "__main__":
    main()
