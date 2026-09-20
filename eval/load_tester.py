"""
Automated End-to-End Stress and Concurrent Load Testing Harness
Benchmarks throughput (RPS), latency percentiles (P50, P90, P99), and stability
under high-concurrency multi-threaded load for TigerGraph Agentic Fraud API.
"""

import sys
import time
import json
import argparse
import statistics
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.api.main import app


class LoadTestHarness:
    """Executes multi-threaded concurrent load tests against API endpoints."""

    def __init__(self, client: Optional[TestClient] = None):
        self.client = client or TestClient(app)

    def run_load_test(
        self,
        endpoints: Optional[List[str]] = None,
        total_requests: int = 50,
        concurrency: int = 5,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Executes concurrent requests and measures latency percentiles and throughput.
        """
        target_endpoints = endpoints or [
            "/api/cases/HHG-001",
            "/api/cases/HHG-002",
            "/api/cases/HHG-001/briefing/markdown",
            "/api/audit/ledger?limit=10",
            "/api/security/ratelimit/stats",
        ]

        latencies_ms: List[float] = []
        status_codes: Dict[int, int] = {}
        errors: List[str] = []

        start_time = time.time()

        def _worker_task(idx: int) -> Dict[str, Any]:
            ep = target_endpoints[idx % len(target_endpoints)]
            t0 = time.perf_counter()
            try:
                resp = self.client.get(ep)
                t_elapsed = (time.perf_counter() - t0) * 1000.0  # ms
                return {"status": resp.status_code, "latency_ms": t_elapsed, "error": None}
            except Exception as e:
                t_elapsed = (time.perf_counter() - t0) * 1000.0
                return {"status": 0, "latency_ms": t_elapsed, "error": str(e)}

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(_worker_task, i) for i in range(total_requests)]
            for fut in as_completed(futures):
                res = fut.result()
                latencies_ms.append(res["latency_ms"])
                code = res["status"]
                status_codes[code] = status_codes.get(code, 0) + 1
                if res["error"]:
                    errors.append(res["error"])

        total_wall_time = time.time() - start_time
        throughput_rps = total_requests / total_wall_time if total_wall_time > 0 else 0.0

        latencies_sorted = sorted(latencies_ms)
        n = len(latencies_sorted)

        def _percentile(p: float) -> float:
            if not latencies_sorted:
                return 0.0
            idx = int((p / 100.0) * n)
            idx = min(idx, n - 1)
            return latencies_sorted[idx]

        p50 = _percentile(50.0)
        p90 = _percentile(90.0)
        p95 = _percentile(95.0)
        p99 = _percentile(99.0)
        mean_lat = statistics.mean(latencies_ms) if latencies_ms else 0.0
        min_lat = min(latencies_ms) if latencies_ms else 0.0
        max_lat = max(latencies_ms) if latencies_ms else 0.0

        success_count = status_codes.get(200, 0)
        success_rate = (success_count / total_requests) * 100.0 if total_requests > 0 else 0.0

        results = {
            "total_requests": total_requests,
            "concurrency": concurrency,
            "total_wall_time_seconds": round(total_wall_time, 3),
            "throughput_rps": round(throughput_rps, 2),
            "success_count": success_count,
            "success_rate_percent": round(success_rate, 2),
            "status_code_distribution": status_codes,
            "latency_ms": {
                "min": round(min_lat, 2),
                "max": round(max_lat, 2),
                "mean": round(mean_lat, 2),
                "p50": round(p50, 2),
                "p90": round(p90, 2),
                "p95": round(p95, 2),
                "p99": round(p99, 2),
            },
            "error_count": len(errors),
            "errors": errors[:5],
        }
        return results

    def format_report(self, results: Dict[str, Any]) -> str:
        """Generates a structured ASCII summary table."""
        lat = results["latency_ms"]
        lines = [
            "======================================================================",
            "  TIGERGRAPH AGENTIC FRAUD INVESTIGATOR: CONCURRENT LOAD TEST REPORT",
            "======================================================================",
            f"Concurrency Workers     : {results['concurrency']}",
            f"Total Requests Dispatched: {results['total_requests']}",
            f"Total Elapsed Time      : {results['total_wall_time_seconds']} s",
            f"Throughput (RPS)        : {results['throughput_rps']} req/sec",
            f"Success Rate            : {results['success_rate_percent']}% ({results['success_count']}/{results['total_requests']})",
            "----------------------------------------------------------------------",
            "Latency Distribution (ms):",
            f"  Min: {lat['min']:>6.2f} ms | Mean: {lat['mean']:>6.2f} ms | Max: {lat['max']:>6.2f} ms",
            f"  P50: {lat['p50']:>6.2f} ms | P90 : {lat['p90']:>6.2f} ms",
            f"  P95: {lat['p95']:>6.2f} ms | P99 : {lat['p99']:>6.2f} ms",
            "----------------------------------------------------------------------",
            f"Status Codes            : {json.dumps(results['status_code_distribution'])}",
            f"Errors Encountered      : {results['error_count']}",
            "======================================================================",
        ]
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="TigerGraph Concurrent Load Testing Harness")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of worker threads")
    parser.add_argument("--requests", type=int, default=50, help="Total requests to dispatch")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--export-file", type=str, default=None, help="File path to save results JSON")
    args = parser.parse_args()

    harness = LoadTestHarness()
    results = harness.run_load_test(total_requests=args.requests, concurrency=args.concurrency)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(harness.format_report(results))

    if args.export_file:
        with open(args.export_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Report written to: {args.export_file}")


if __name__ == "__main__":
    main()
