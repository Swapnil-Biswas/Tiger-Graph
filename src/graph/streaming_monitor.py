"""
Streaming Transaction Influx Monitor & Dynamic Graph Anomaly Window Detector
(src/graph/streaming_monitor.py)

Maintains an in-memory sliding window of real-time transaction events, computing rolling
velocity, novel device linkage, impossible travel, and high-risk MCC triggers
with sub-millisecond evaluation latency (< 1ms/event).
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import deque
from datetime import datetime, timezone
import math
import time
import uuid


@dataclass
class StreamingAlert:
    alert_id: str
    card_id: str
    rule_triggered: str  # "VELOCITY_SPIKE", "NOVEL_DEVICE_LINK", "IMPOSSIBLE_TRAVEL", "HIGH_RISK_MCC"
    severity: str        # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    details: Dict[str, Any]
    timestamp: str
    epoch_s: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StreamingGraphMonitor:
    """
    High-throughput sliding window accumulator and streaming anomaly detector.
    Processes live financial transactions and emits sub-millisecond alerts.
    """

    # Velocity and Anomaly Thresholds
    WINDOW_SECONDS = 300       # 5-minute rolling window
    MAX_VELOCITY_COUNT = 3     # >= 3 txns in 5 minutes triggers alert
    MAX_VELOCITY_AMOUNT = 1000.0 # >= $1,000 in 5 minutes triggers alert
    MAX_TRAVEL_SPEED_KMH = 800.0 # Commercial aircraft ceiling
    HIGH_RISK_MCCS = {"6051", "7995", "4829", "6011"}

    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self.window_events: deque = deque()  # (epoch_s, txn_dict)
        self.card_recent_txns: Dict[str, List[Dict[str, Any]]] = {}
        self.device_seen_cards: Dict[str, Set[str]] = {}
        self.card_last_location: Dict[str, Tuple[float, float, int]] = {}  # card -> (lat, lon, epoch_s)
        self.active_alerts: List[StreamingAlert] = []
        self.total_processed: int = 0

    def ingest_transaction(self, txn: Dict[str, Any]) -> List[StreamingAlert]:
        """
        Ingests a single transaction event into the sliding window, evicts expired
        events, and evaluates streaming anomaly rules. Returns newly triggered alerts.
        """
        now_epoch = int(txn.get("epoch_s") or time.time())
        card_id = str(txn.get("card_id") or "UNKNOWN")
        amount = float(txn.get("amount") or txn.get("TransactionAmt") or 0.0)
        device = str(txn.get("device_profile") or "")
        mcc = str(txn.get("mcc") or txn.get("addr2") or "")
        lat = txn.get("latitude")
        lon = txn.get("longitude")

        # 1. Add to window and update stats
        self.total_processed += 1
        self.window_events.append((now_epoch, txn))
        self.card_recent_txns.setdefault(card_id, []).append(txn)

        # 2. Evict expired events from window
        cutoff_epoch = now_epoch - self.window_seconds
        self._evict_expired(cutoff_epoch)

        # 3. Evaluate streaming rules
        new_alerts = []

        # Rule 1: Rolling Velocity Spike (Count or Amount in 5 min)
        recent_card_txns = self.card_recent_txns.get(card_id, [])
        window_card_txns = [t for t in recent_card_txns if int(t.get("epoch_s", 0)) >= cutoff_epoch]
        self.card_recent_txns[card_id] = window_card_txns

        if len(window_card_txns) >= self.MAX_VELOCITY_COUNT or sum(float(t.get("amount") or t.get("TransactionAmt") or 0.0) for t in window_card_txns) >= self.MAX_VELOCITY_AMOUNT:
            total_amt = sum(float(t.get("amount") or t.get("TransactionAmt") or 0.0) for t in window_card_txns)
            alert = StreamingAlert(
                alert_id=f"ALT-VEL-{uuid.uuid4().hex[:8].upper()}",
                card_id=card_id,
                rule_triggered="VELOCITY_SPIKE",
                severity="CRITICAL" if total_amt >= 2500.0 else "HIGH",
                details={
                    "window_txn_count": len(window_card_txns),
                    "window_total_usd": round(total_amt, 2),
                    "threshold_count": self.MAX_VELOCITY_COUNT,
                    "threshold_usd": self.MAX_VELOCITY_AMOUNT,
                },
                timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                epoch_s=now_epoch,
            )
            new_alerts.append(alert)

        # Rule 2: Novel Device Linkage
        if device and device != "nan":
            seen_cards = self.device_seen_cards.setdefault(device, set())
            if card_id not in seen_cards and len(seen_cards) >= 1:
                # Device previously used by another card, now used by a new card
                alert = StreamingAlert(
                    alert_id=f"ALT-DEV-{uuid.uuid4().hex[:8].upper()}",
                    card_id=card_id,
                    rule_triggered="NOVEL_DEVICE_LINK",
                    severity="HIGH",
                    details={
                        "device_profile": device,
                        "prior_cards_on_device": list(seen_cards)[:5],
                        "total_cards_on_device": len(seen_cards) + 1,
                    },
                    timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    epoch_s=now_epoch,
                )
                new_alerts.append(alert)
            seen_cards.add(card_id)

        # Rule 3: Impossible Physical Travel
        if lat is not None and lon is not None:
            try:
                curr_lat, curr_lon = float(lat), float(lon)
                if card_id in self.card_last_location:
                    last_lat, last_lon, last_epoch = self.card_last_location[card_id]
                    time_diff_hours = max(0.001, (now_epoch - last_epoch) / 3600.0)
                    dist_km = self._haversine_distance(last_lat, last_lon, curr_lat, curr_lon)
                    speed_kmh = dist_km / time_diff_hours

                    if speed_kmh > self.MAX_TRAVEL_SPEED_KMH and dist_km > 100.0:
                        alert = StreamingAlert(
                            alert_id=f"ALT-GEO-{uuid.uuid4().hex[:8].upper()}",
                            card_id=card_id,
                            rule_triggered="IMPOSSIBLE_TRAVEL",
                            severity="CRITICAL",
                            details={
                                "distance_km": round(dist_km, 1),
                                "time_diff_minutes": round(time_diff_hours * 60.0, 1),
                                "calculated_speed_kmh": round(speed_kmh, 1),
                                "origin": {"lat": last_lat, "lon": last_lon},
                                "destination": {"lat": curr_lat, "lon": curr_lon},
                            },
                            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            epoch_s=now_epoch,
                        )
                        new_alerts.append(alert)

                self.card_last_location[card_id] = (curr_lat, curr_lon, now_epoch)
            except (ValueError, TypeError):
                pass

        # Rule 4: High-Risk MCC on Streaming Event
        if mcc in self.HIGH_RISK_MCCS and amount >= 250.0:
            alert = StreamingAlert(
                alert_id=f"ALT-MCC-{uuid.uuid4().hex[:8].upper()}",
                card_id=card_id,
                rule_triggered="HIGH_RISK_MCC",
                severity="HIGH",
                details={
                    "mcc": mcc,
                    "mcc_description": "Quasi-Cash / Crypto / Money Transfer" if mcc == "6051" else "Gambling / High Risk",
                    "amount_usd": round(amount, 2),
                },
                timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                epoch_s=now_epoch,
            )
            new_alerts.append(alert)

        # Store alerts in active buffer
        self.active_alerts.extend(new_alerts)
        return new_alerts

    def _evict_expired(self, cutoff_epoch: int):
        """Evicts events older than the sliding window."""
        while self.window_events and self.window_events[0][0] < cutoff_epoch:
            self.window_events.popleft()

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Computes great-circle distance between two coordinates in kilometers."""
        R = 6371.0  # Earth radius in km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    def get_stats(self) -> Dict[str, Any]:
        """Returns sliding window operational metrics."""
        return {
            "window_seconds": self.window_seconds,
            "total_processed": self.total_processed,
            "current_window_events": len(self.window_events),
            "active_cards_in_window": len([c for c, txns in self.card_recent_txns.items() if txns]),
            "total_alerts_emitted": len(self.active_alerts),
            "critical_alerts": sum(1 for a in self.active_alerts if a.severity == "CRITICAL"),
            "high_alerts": sum(1 for a in self.active_alerts if a.severity == "HIGH"),
        }

    def get_alerts(self, severity: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves active alerts filtered by optional severity."""
        alerts = self.active_alerts
        if severity:
            sev_upper = severity.upper()
            alerts = [a for a in alerts if a.severity == sev_upper]
        return [a.to_dict() for a in alerts[-limit:]]
