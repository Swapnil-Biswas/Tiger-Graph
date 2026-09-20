#!/usr/bin/env python3
"""
TigerGraph Agentic Fraud Investigator - Cross-Platform Smoke & Sanity Runner
=============================================================================
Fast, zero-setup operational smoke test suite verifying end-to-end system health
across platform runtime, GraphStore integrity, API endpoints, GraphQL, compliance,
and telemetry in under 15 seconds.

Usage:
    python scripts/smoke_test.py [--quick] [--json] [--verbose]
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Add repository root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# ANSI terminal colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class SmokeTestRunner:
    """Executes rapid cross-platform end-to-end smoke tests."""

    def __init__(self, quick: bool = False, verbose: bool = False):
        self.quick = quick
        self.verbose = verbose
        self.checks: List[Dict[str, Any]] = []

    def log(self, msg: str):
        if self.verbose:
            print(msg)

    def _record(self, check_id: str, name: str, category: str, passed: bool, detail: str, duration_ms: float):
        self.checks.append({
            "check_id": check_id,
            "name": name,
            "category": category,
            "passed": passed,
            "detail": detail,
            "duration_ms": round(duration_ms, 2),
        })

    def run_environment_checks(self):
        """Verify Python version and standard library modules."""
        t0 = time.perf_counter()
        v = sys.version_info
        passed = (v.major, v.minor) >= (3, 10)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "ENV-01", "Python Runtime Version", "Environment", passed,
            f"Python {v.major}.{v.minor}.{v.micro} (Requires >= 3.10)", dt
        )

        t0 = time.perf_counter()
        required_pkgs = ["fastapi", "networkx", "pydantic", "starlette"]
        missing = []
        for pkg in required_pkgs:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "ENV-02", "Core Package Imports", "Environment", len(missing) == 0,
            "All core packages importable" if not missing else f"Missing: {', '.join(missing)}", dt
        )

    def run_data_and_graph_checks(self):
        """Verify GraphStore and benchmark cases directory."""
        t0 = time.perf_counter()
        cases_dir = ROOT_DIR / "cases"
        case_files = list(cases_dir.glob("*.json")) if cases_dir.exists() else []
        passed = len(case_files) >= 20
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "DATA-01", "Benchmark Cases Files", "Data & Graph", passed,
            f"Found {len(case_files)} benchmark case files in cases/", dt
        )

        t0 = time.perf_counter()
        cache_file = ROOT_DIR / "data" / "graph_cache.pkl"
        has_cache = cache_file.exists() and cache_file.stat().st_size > 1024
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "DATA-02", "GraphStore Cache Integrity", "Data & Graph", has_cache,
            f"Cache pkl present ({cache_file.stat().st_size / 1024 / 1024:.1f} MB)" if has_cache else "Cache pkl missing", dt
        )

    def run_api_smoke_checks(self):
        """Verify in-process FastAPI endpoints with TestClient."""
        try:
            from fastapi.testclient import TestClient
            from src.api.main import app
            client = TestClient(app)
        except Exception as e:
            self._record("API-00", "FastAPI App Initialization", "API", False, f"Failed to initialize app: {e}", 0.0)
            return

        endpoints = [
            ("API-01", "Cases List Endpoint", "GET", "/api/cases", lambda r: r.status_code == 200 and len(r.json().get("cases", [])) >= 20),
            ("API-02", "Single Case Endpoint", "GET", "/api/cases/HHG-001", lambda r: r.status_code == 200 and r.json().get("case_id") == "HHG-001"),
            ("API-03", "Compliance Report Endpoint", "GET", "/api/compliance/report/HHG-001?format=json", lambda r: r.status_code == 200 and "compliance_score" in r.json()),
            ("API-04", "Executive Briefing HTML", "GET", "/api/cases/HHG-001/briefing/html", lambda r: r.status_code == 200 and "<!DOCTYPE html>" in r.text),
            ("API-05", "Graph Temporal Diff", "GET", "/api/cases/HHG-001/graph-diff", lambda r: r.status_code == 200 and "risk_shift" in r.json()),
            ("API-06", "GraphQL Query Resolver", "POST", "/graphql", lambda r: r.status_code == 200 and "case_id" in str(r.json()), {"query": 'query { case(caseId: "HHG-001") { case_id verdict } }'}),
            ("API-07", "Rate Limiter Stats", "GET", "/api/security/ratelimit/stats", lambda r: r.status_code == 200 and "active_clients" in r.json()),
            ("API-08", "Webhook DLQ Stats", "GET", "/api/webhooks/dlq/stats", lambda r: r.status_code == 200 and "total" in r.json()),
            ("API-09", "Prometheus Telemetry", "GET", "/metrics", lambda r: r.status_code == 200 and "fraud_investigations_total" in r.text),
        ]

        for check_id, name, method, path, validator, *rest in endpoints:
            t0 = time.perf_counter()
            body = rest[0] if rest else None
            try:
                if method == "GET":
                    resp = client.get(path)
                elif method == "POST":
                    resp = client.post(path, json=body)
                passed = validator(resp)
                detail = f"HTTP {resp.status_code} ({len(resp.content)} bytes)"
            except Exception as e:
                passed = False
                detail = f"Exception: {str(e)[:60]}"
            dt = (time.perf_counter() - t0) * 1000
            self._record(check_id, name, "API", passed, detail, dt)

    def run_all(self) -> Dict[str, Any]:
        """Runs all configured smoke test checks."""
        t_start = time.perf_counter()
        self.run_environment_checks()
        self.run_data_and_graph_checks()
        if not self.quick:
            self.run_api_smoke_checks()
        total_time_s = time.perf_counter() - t_start

        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        failed = total - passed
        all_passed = (failed == 0)

        return {
            "status": "PASS" if all_passed else "FAIL",
            "all_passed": all_passed,
            "total_checks": total,
            "checks_passed": passed,
            "checks_failed": failed,
            "elapsed_seconds": round(total_time_s, 3),
            "checks": self.checks,
        }

    def print_ascii_report(self, results: Dict[str, Any]):
        """Prints a clean, formatted ASCII report to stdout."""
        status_color = GREEN if results["all_passed"] else RED
        status_str = f"{status_color}{BOLD}{results['status']}{RESET}"

        print("\n" + "=" * 78)
        print(f" {BOLD}TIGERGRAPH AGENTIC FRAUD INVESTIGATOR: SMOKE & SANITY REPORT{RESET}")
        print("=" * 78)
        print(f" Status: {status_str} | Checks: {results['checks_passed']}/{results['total_checks']} Passed | Duration: {results['elapsed_seconds']}s\n")

        print(f" {'ID':<8} {'Category':<14} {'Check Name':<32} {'Status':<8} {'Latency':<9} {'Detail'}")
        print(" " + "-" * 76)

        for c in results["checks"]:
            c_color = GREEN if c["passed"] else RED
            c_status = f"{c_color}{'PASS' if c['passed'] else 'FAIL'}{RESET}"
            print(f" {c['check_id']:<8} {c['category']:<14} {c['name']:<32} {c_status:<17} {c['duration_ms']:>6.1f}ms  {c['detail']}")

        print("=" * 78 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Cross-Platform Smoke & Sanity Runner")
    parser.add_argument("--quick", action="store_true", help="Run only fast environment and data checks")
    parser.add_argument("--json", action="store_true", help="Output results as machine-readable JSON")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    runner = SmokeTestRunner(quick=args.quick, verbose=args.verbose)
    results = runner.run_all()

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        runner.print_ascii_report(results)

    sys.exit(0 if results["all_passed"] else 1)


if __name__ == "__main__":
    main()
