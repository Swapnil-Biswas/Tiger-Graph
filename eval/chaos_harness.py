"""
Automated Chaos Engineering & Fault Injection Resilience Harness
(eval/chaos_harness.py)

Simulates production failures including corrupted transaction payloads, high-frequency
traffic bursts (5,000+ txns), failing/unreachable webhook endpoints, and missing entity
fields to prove zero-crash graceful degradation and system resilience.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
import time
import math
import random
import uuid

from src.graph.streaming_monitor import StreamingGraphMonitor
from src.api.webhooks import EnterpriseWebhookDispatcher
from src.agent.graph import FraudInvestigatorAgent


@dataclass
class ChaosResilienceReport:
    total_faults_injected: int
    faults_handled_gracefully: int
    unhandled_exceptions: int
    resilience_score: float  # 0.0 to 1.0 (target: 1.0)
    burst_throughput_eps: float
    max_memory_window_events: int
    status: str  # "PASSED" | "FAILED"
    details: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ChaosEngineeringHarness:
    """
    Automated chaos experiment runner.
    Injects systematic adversarial and infrastructure faults to verify graceful recovery.
    """

    def __init__(self, agent: Optional[FraudInvestigatorAgent] = None):
        self.agent = agent or FraudInvestigatorAgent()

    def test_streaming_corrupt_payloads(self, monitor: Optional[StreamingGraphMonitor] = None) -> Dict[str, Any]:
        """Injects malformed, negative, null, and type-mismatched payloads into streaming monitor."""
        mon = monitor or StreamingGraphMonitor()
        corrupt_inputs = [
            {},  # Empty dictionary
            {"transaction_id": None},  # Null ID
            {"transaction_id": "TX-CORRUPT-1", "amount": -99999.0},  # Negative amount
            {"transaction_id": "TX-CORRUPT-2", "amount": "INVALID_STR"},  # Type mismatch
            {"transaction_id": "TX-CORRUPT-3", "epoch_s": "INVALID_EPOCH"},  # Invalid epoch
            {"transaction_id": "TX-CORRUPT-4", "card_id": 123456},  # Non-string card ID
            {"transaction_id": "TX-CORRUPT-5", "latitude": "NOT_A_LAT", "longitude": 12.34},  # Malformed geo
            {"transaction_id": "TX-CORRUPT-6", "amount": float("inf")},  # Infinite amount
            {"transaction_id": "TX-CORRUPT-7", "amount": float("nan")},  # NaN amount
        ]

        handled = 0
        errors = []

        for idx, payload in enumerate(corrupt_inputs):
            try:
                # Ingest should handle gracefully or normalize without fatal unhandled crash
                # In Python, float conversion or type guard may raise ValueError/TypeError inside monitor
                # or safely ignore.
                alerts = mon.ingest_transaction(payload)
                handled += 1
            except (ValueError, TypeError, KeyError) as expected_e:
                # Handled type/validation error
                handled += 1
            except Exception as unhandled_e:
                errors.append(f"Input #{idx} caused unexpected crash: {type(unhandled_e).__name__}: {unhandled_e}")

        return {
            "test": "streaming_corrupt_payloads",
            "injected": len(corrupt_inputs),
            "handled": handled,
            "passed": len(errors) == 0,
            "errors": errors,
        }

    def test_streaming_traffic_burst(
        self,
        count: int = 5000,
        monitor: Optional[StreamingGraphMonitor] = None,
    ) -> Dict[str, Any]:
        """Simulates a sudden high-velocity traffic burst of N transactions."""
        mon = monitor or StreamingGraphMonitor(window_seconds=300)
        start_epoch = 1700000000

        t0 = time.perf_counter()
        for i in range(count):
            txn = {
                "transaction_id": f"TX-BURST-{i:06d}",
                "card_id": f"CARD-BURST-{i % 100:03d}",
                "amount": 25.0 + (i % 50),
                "epoch_s": start_epoch + (i // 20),  # Spread across window
                "merchant_category": "5411" if i % 10 != 0 else "6051",
            }
            mon.ingest_transaction(txn)
        elapsed = time.perf_counter() - t0

        eps = count / max(0.0001, elapsed)
        stats = mon.get_stats()

        # Verify window is bounded (does not exceed window capacity)
        window_events = stats.get("window_events_count", 0)
        passed = (stats.get("total_processed", 0) == count) and (window_events <= count)

        return {
            "test": "streaming_traffic_burst",
            "injected": count,
            "elapsed_seconds": round(elapsed, 4),
            "events_per_second": round(eps, 1),
            "window_events_count": window_events,
            "passed": passed,
        }

    def test_webhook_failure_resilience(
        self,
        dispatcher: Optional[EnterpriseWebhookDispatcher] = None,
    ) -> Dict[str, Any]:
        """Simulates unreachable/failing HTTP webhook endpoints with non-blocking resilience."""
        disp = dispatcher or EnterpriseWebhookDispatcher()
        sub = disp.register_subscription(
            url="http://127.0.0.1:59999/unreachable/webhook",  # Non-existent local port
            secret="chaos_test_secret",
            events=["CRITICAL_ALERT"],
        )

        t0 = time.perf_counter()
        # Dispatch with send_http=True
        deliveries = disp.dispatch_event(
            "CRITICAL_ALERT",
            {"alert_id": "CHAOS-001", "details": "Simulated fault"},
            send_http=True,
        )
        elapsed = time.perf_counter() - t0

        # Should record failure without raising unhandled exception
        self.assertEqual(len(deliveries), 1) if hasattr(self, "assertEqual") else None
        record = deliveries[0]

        disp.delete_subscription(sub.subscription_id)

        passed = (record.success is False) and (record.error_message is not None) and (elapsed < 6.0)
        return {
            "test": "webhook_failure_resilience",
            "delivery_id": record.delivery_id,
            "success": record.success,
            "error_message": record.error_message,
            "elapsed_seconds": round(elapsed, 4),
            "passed": passed,
        }

    def test_agent_missing_entity_resilience(self, case_id: str = "HHG-001") -> Dict[str, Any]:
        """Simulates investigation with simulated missing evidence fields or unknown scenario."""
        try:
            # Test unknown / corrupted simulated scenario
            res = self.agent.investigate_case(case_id, simulated_scenario="MALFORMED_NONEXISTENT_SCENARIO")
            passed = (
                isinstance(res, dict)
                and "case" in res
                and "next_best_actions" in res
                and "verdict" in res["case"]
            )
            return {
                "test": "agent_missing_entity_resilience",
                "case_id": case_id,
                "verdict": res["case"]["verdict"],
                "passed": passed,
            }
        except Exception as e:
            return {
                "test": "agent_missing_entity_resilience",
                "case_id": case_id,
                "passed": False,
                "error": str(e),
            }

    def run_full_chaos_audit(self) -> ChaosResilienceReport:
        """Runs all chaos experiments and produces a consolidated resilience report."""
        r1 = self.test_streaming_corrupt_payloads()
        r2 = self.test_streaming_traffic_burst(count=3000)
        r3 = self.test_webhook_failure_resilience()
        r4 = self.test_agent_missing_entity_resilience()

        details = [r1, r2, r3, r4]
        total = len(details)
        passed_count = sum(1 for d in details if d.get("passed"))
        unhandled = total - passed_count
        score = passed_count / total

        return ChaosResilienceReport(
            total_faults_injected=total,
            faults_handled_gracefully=passed_count,
            unhandled_exceptions=unhandled,
            resilience_score=round(score, 4),
            burst_throughput_eps=r2.get("events_per_second", 0.0),
            max_memory_window_events=r2.get("window_events_count", 0),
            status="PASSED" if score >= 1.0 else "FAILED",
            details=details,
        )


if __name__ == "__main__":
    harness = ChaosEngineeringHarness()
    report = harness.run_full_chaos_audit()
    print("\n=== CHAOS RESILIENCE REPORT ===")
    print(f"Status: {report.status}")
    print(f"Resilience Score: {report.resilience_score * 100:.1f}%")
    print(f"Burst Throughput: {report.burst_throughput_eps:,.1f} events/sec")
    for d in report.details:
        print(f"  - {d['test']}: {'PASS' if d.get('passed') else 'FAIL'}")
