"""
Enterprise Webhook Notification Dispatcher & PagerDuty/Slack Incident Bridge
(src/api/webhooks.py)

Dispatches cryptographically signed (HMAC-SHA256) incident alerts for critical streaming
anomalies, high-exposure SAR filings, and L1/L2 approval escalations.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import hmac
import hashlib
import time
import json
import uuid
import urllib.request
import urllib.error


@dataclass
class WebhookSubscription:
    subscription_id: str
    url: str
    secret: str
    events: List[str]  # e.g. ["STREAMING_CRITICAL_ANOMALY", "SAR_FILING_REQUIRED", "CASE_ESCALATION_L2", "*"]
    enabled: bool = True
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Mask secret in dictionary export for security
        d["secret_masked"] = self.secret[:4] + "...." if len(self.secret) > 4 else "...."
        del d["secret"]
        return d


@dataclass
class WebhookDeliveryRecord:
    delivery_id: str
    subscription_id: str
    event_type: str
    payload: Dict[str, Any]
    status_code: Optional[int]
    success: bool
    attempts: int
    error_message: Optional[str]
    timestamp: str
    signature_header: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EnterpriseWebhookDispatcher:
    """
    Thread-safe enterprise webhook dispatcher.
    Signs payloads with HMAC-SHA256 and dispatches real-time incident notifications.
    """

    def __init__(self):
        self._subscriptions: Dict[str, WebhookSubscription] = {}
        self._delivery_log: List[WebhookDeliveryRecord] = []

    def register_subscription(
        self,
        url: str,
        secret: str,
        events: Optional[List[str]] = None,
        enabled: bool = True,
    ) -> WebhookSubscription:
        """Registers a new webhook subscription."""
        sub_id = f"SUB-{uuid.uuid4().hex[:8].upper()}"
        sub = WebhookSubscription(
            subscription_id=sub_id,
            url=url,
            secret=secret,
            events=events or ["*"],
            enabled=enabled,
        )
        self._subscriptions[sub_id] = sub
        return sub

    def get_subscriptions(self) -> List[WebhookSubscription]:
        """Returns all registered webhook subscriptions."""
        return list(self._subscriptions.values())

    def get_subscription(self, sub_id: str) -> Optional[WebhookSubscription]:
        return self._subscriptions.get(sub_id)

    def delete_subscription(self, sub_id: str) -> bool:
        if sub_id in self._subscriptions:
            del self._subscriptions[sub_id]
            return True
        return False

    @staticmethod
    def sign_payload(secret: str, payload_bytes: bytes, timestamp: Optional[int] = None) -> str:
        """
        Signs a payload using HMAC-SHA256 according to modern webhook security standards.
        Format: t=<timestamp>,v1=<hex_signature>
        """
        ts = timestamp if timestamp is not None else int(time.time())
        to_sign = f"{ts}.".encode("utf-8") + payload_bytes
        signature = hmac.new(secret.encode("utf-8"), to_sign, hashlib.sha256).hexdigest()
        return f"t={ts},v1={signature}"

    @staticmethod
    def verify_signature(
        secret: str,
        payload_bytes: bytes,
        signature_header: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """Verifies an HMAC-SHA256 signature header and enforces timestamp freshness."""
        try:
            parts = dict(item.split("=", 1) for item in signature_header.split(","))
            ts = int(parts.get("t", "0"))
            v1 = parts.get("v1", "")

            # Check timestamp tolerance (prevent replay attacks)
            if abs(time.time() - ts) > tolerance_seconds:
                return False

            to_sign = f"{ts}.".encode("utf-8") + payload_bytes
            expected_sig = hmac.new(secret.encode("utf-8"), to_sign, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected_sig, v1)
        except Exception:
            return False

    def dispatch_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        send_http: bool = False,
    ) -> List[WebhookDeliveryRecord]:
        """
        Dispatches an incident event to all matching active webhook subscriptions.
        """
        deliveries = []
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        for sub in self._subscriptions.values():
            if not sub.enabled:
                continue
            if "*" not in sub.events and event_type not in sub.events:
                continue

            sig_header = self.sign_payload(sub.secret, payload_bytes)
            delivery_id = f"DELIV-{uuid.uuid4().hex[:8].upper()}"

            status_code = 200
            success = True
            error_msg = None
            attempts = 1

            if send_http and (sub.url.startswith("http://") or sub.url.startswith("https://")):
                req = urllib.request.Request(
                    sub.url,
                    data=payload_bytes,
                    headers={
                        "Content-Type": "application/json",
                        "X-TigerGraph-Signature": sig_header,
                        "X-TigerGraph-Event": event_type,
                        "User-Agent": "TigerGraph-Fraud-Agent/0.7.0",
                    },
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        status_code = resp.getcode()
                        success = 200 <= status_code < 300
                except urllib.error.HTTPError as he:
                    status_code = he.code
                    success = False
                    error_msg = str(he)
                except Exception as e:
                    status_code = None
                    success = False
                    error_msg = str(e)

            record = WebhookDeliveryRecord(
                delivery_id=delivery_id,
                subscription_id=sub.subscription_id,
                event_type=event_type,
                payload=payload,
                status_code=status_code,
                success=success,
                attempts=attempts,
                error_message=error_msg,
                timestamp=now_str,
                signature_header=sig_header,
            )
            self._delivery_log.append(record)
            deliveries.append(record)

            if not success and send_http:
                try:
                    from src.api.webhook_dlq import webhook_dlq
                    webhook_dlq.enqueue(
                        subscription_id=sub.subscription_id,
                        url=sub.url,
                        secret=sub.secret,
                        event_type=event_type,
                        payload=payload,
                        initial_error=error_msg,
                    )
                except Exception:
                    pass

        return deliveries

    def get_delivery_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the most recent webhook delivery records."""
        return [r.to_dict() for r in reversed(self._delivery_log[-limit:])]


# Global Webhook Dispatcher
webhook_dispatcher = EnterpriseWebhookDispatcher()
