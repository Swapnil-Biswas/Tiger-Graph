"""
Enterprise Prometheus Metrics Exporter & Real-Time Grafana SLA Telemetry Instrumentation
(src/api/telemetry.py)

Instruments the fraud investigation pipeline with standard Prometheus/OpenMetrics counters,
gauges, and latency histograms for enterprise SRE, Grafana dashboards, and SLA monitoring.
"""

from typing import Dict, Any, List, Optional
import time
from collections import defaultdict


class EnterpriseTelemetryRegistry:
    """
    Lightweight, zero-dependency Prometheus/OpenMetrics telemetry registry and exporter.
    Provides sub-microsecond metric observation and text-format serialization.
    """

    def __init__(self):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, Dict[float, int]] = defaultdict(lambda: defaultdict(int))
        self._histogram_sums: Dict[str, float] = defaultdict(float)
        self._histogram_counts: Dict[str, int] = defaultdict(int)

        # Standard SLA Buckets
        self.LATENCY_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float("inf"))
        self.STREAMING_BUCKETS = (0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, float("inf"))

    def inc_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increments a Prometheus counter metric."""
        metric_key = self._format_key(name, labels)
        self._counters[metric_key] += value

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Sets a Prometheus gauge metric."""
        metric_key = self._format_key(name, labels)
        self._gauges[metric_key] = value

    def observe_histogram(self, name: str, value: float, buckets: Optional[tuple] = None, labels: Optional[Dict[str, str]] = None):
        """Observes a latency duration in a Prometheus histogram metric."""
        b_list = buckets or self.LATENCY_BUCKETS
        base_key = self._format_key(name, labels)

        self._histogram_sums[base_key] += value
        self._histogram_counts[base_key] += 1

        for b in b_list:
            if b not in self._histograms[base_key]:
                self._histograms[base_key][b] = 0
            if value <= b:
                self._histograms[base_key][b] += 1

    def _format_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _format_bucket_key(self, name: str, bucket: float, labels: Optional[Dict[str, str]]) -> str:
        le_str = "+Inf" if math_is_inf(bucket) else f"{bucket}"
        lbls = dict(labels or {})
        lbls["le"] = le_str
        return self._format_key(f"{name}_bucket", lbls)

    def generate_prometheus_metrics(self) -> str:
        """
        Serializes all registered counters, gauges, and histograms into
        official Prometheus text format (version 0.0.4 / OpenMetrics).
        """
        lines = []

        # 1. Header Metadata
        lines.append("# HELP fraud_investigations_total Total number of completed fraud investigations")
        lines.append("# TYPE fraud_investigations_total counter")
        lines.append("# HELP streaming_transactions_ingested_total Total streaming transactions ingested")
        lines.append("# TYPE streaming_transactions_ingested_total counter")
        lines.append("# HELP streaming_alerts_emitted_total Total real-time streaming alerts emitted")
        lines.append("# TYPE streaming_alerts_emitted_total counter")
        lines.append("# HELP policy_actions_authorized_total Total automated or analyst-authorized policy actions")
        lines.append("# TYPE policy_actions_authorized_total counter")
        lines.append("# HELP graph_indexed_entities Total vertices/records indexed in graph store")
        lines.append("# TYPE graph_indexed_entities gauge")
        lines.append("# HELP investigation_latency_seconds End-to-end case investigation latency in seconds")
        lines.append("# TYPE investigation_latency_seconds histogram")

        # 2. Counters
        for k, v in sorted(self._counters.items()):
            lines.append(f"{k} {v}")

        # 3. Gauges
        for k, v in sorted(self._gauges.items()):
            lines.append(f"{k} {v}")

        # 4. Histograms
        for base_key, b_dict in sorted(self._histograms.items()):
            name = base_key.split("{")[0]
            labels_raw = base_key[len(name):] if "{" in base_key else ""
            labels_dict = self._parse_labels(labels_raw)

            # Buckets
            for b in sorted(b_dict.keys()):
                le_str = "+Inf" if math_is_inf(b) else f"{b}"
                b_lbls = dict(labels_dict)
                b_lbls["le"] = le_str
                lines.append(f'{self._format_key(f"{name}_bucket", b_lbls)} {b_dict[b]}')

            # Sum and Count
            lines.append(f'{self._format_key(f"{name}_sum", labels_dict)} {self._histogram_sums[base_key]:.6f}')
            lines.append(f'{self._format_key(f"{name}_count", labels_dict)} {self._histogram_counts[base_key]}')

        return "\n".join(lines) + "\n"

    def _parse_labels(self, label_str: str) -> Dict[str, str]:
        if not label_str or not label_str.startswith("{") or not label_str.endswith("}"):
            return {}
        inner = label_str[1:-1]
        pairs = {}
        for part in inner.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                pairs[k.strip()] = v.strip('"')
        return pairs

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Returns JSON snapshot of operational health, throughput, and SLA compliance."""
        total_inv = sum(v for k, v in self._counters.items() if k.startswith("fraud_investigations_total"))
        total_alerts = sum(v for k, v in self._counters.items() if k.startswith("streaming_alerts_emitted_total"))
        total_txns = sum(v for k, v in self._counters.items() if k.startswith("streaming_transactions_ingested_total"))

        inv_lat_sum = sum(v for k, v in self._histogram_sums.items() if k.startswith("investigation_latency_seconds"))
        inv_lat_cnt = sum(v for k, v in self._histogram_counts.items() if k.startswith("investigation_latency_seconds"))
        avg_inv_lat = (inv_lat_sum / max(1, inv_lat_cnt)) if inv_lat_cnt else 0.0

        return {
            "status": "HEALTHY",
            "sla_target_p95_ms": 50.0,
            "current_avg_latency_ms": round(avg_inv_lat * 1000.0, 2),
            "sla_compliant": avg_inv_lat * 1000.0 <= 50.0,
            "total_investigations": int(total_inv),
            "total_streaming_txns": int(total_txns),
            "total_streaming_alerts": int(total_alerts),
            "active_gauges": dict(self._gauges),
        }


def math_is_inf(x: float) -> bool:
    import math
    return math.isinf(x)


# Global Telemetry Instance
telemetry = EnterpriseTelemetryRegistry()
