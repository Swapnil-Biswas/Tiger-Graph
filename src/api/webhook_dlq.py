"""
Webhook Dead-Letter Queue (DLQ) and Exponential Backoff Retry Engine
(src/api/webhook_dlq.py)
Provides resilient asynchronous queuing, exponential backoff retries,
and auditability for failed external incident notifications (PagerDuty, Slack, SIEMs).
"""

import time
import uuid
import json
import threading
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable


@dataclass
class DLQMessage:
    message_id: str
    subscription_id: str
    url: str
    secret: str
    event_type: str
    payload: Dict[str, Any]
    attempts: int = 0
    max_attempts: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    next_retry_time: float = field(default_factory=time.time)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    last_attempt_time: Optional[str] = None
    last_error: Optional[str] = None
    status: str = "PENDING"  # PENDING, RETRYING, DELIVERED, DEAD_LETTER

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Mask secret for security
        d["secret_masked"] = self.secret[:4] + "...." if len(self.secret) > 4 else "...."
        del d["secret"]
        return d


class WebhookDeadLetterQueue:
    """
    Thread-safe in-memory Dead-Letter Queue with exponential backoff scheduling.
    """

    def __init__(self, default_max_attempts: int = 5, base_delay: float = 1.0, max_delay: float = 60.0):
        self.default_max_attempts = default_max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._lock = threading.RLock()
        self._messages: Dict[str, DLQMessage] = {}

    def enqueue(
        self,
        subscription_id: str,
        url: str,
        secret: str,
        event_type: str,
        payload: Dict[str, Any],
        initial_error: Optional[str] = None,
        max_attempts: Optional[int] = None,
    ) -> DLQMessage:
        """Enqueues a failed notification into the dead-letter queue."""
        with self._lock:
            msg_id = f"DLQ-{uuid.uuid4().hex[:8].upper()}"
            delay = self.base_delay
            msg = DLQMessage(
                message_id=msg_id,
                subscription_id=subscription_id,
                url=url,
                secret=secret,
                event_type=event_type,
                payload=payload,
                attempts=1,
                max_attempts=max_attempts or self.default_max_attempts,
                base_delay=self.base_delay,
                max_delay=self.max_delay,
                next_retry_time=time.time() + delay,
                last_attempt_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                last_error=initial_error,
                status="PENDING",
            )
            self._messages[msg_id] = msg
            return msg

    def calculate_backoff(self, attempts: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
        """Computes deterministic exponential backoff: delay = min(base * 2^(attempts-1), max)."""
        backoff = base_delay * (2 ** max(0, attempts - 1))
        return min(backoff, max_delay)

    def retry_message(self, message_id: str, send_fn: Optional[Callable[[DLQMessage], bool]] = None) -> bool:
        """
        Attempts to deliver a single queued message.
        """
        with self._lock:
            msg = self._messages.get(message_id)
            if not msg:
                return False

            now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            msg.last_attempt_time = now_str
            msg.status = "RETRYING"

            success = False
            error_msg = None

            if send_fn:
                try:
                    success = send_fn(msg)
                except Exception as e:
                    success = False
                    error_msg = str(e)
            else:
                # Default HTTP dispatch
                success, error_msg = self._dispatch_http(msg)

            if success:
                msg.status = "DELIVERED"
                msg.last_error = None
                return True
            else:
                msg.attempts += 1
                msg.last_error = error_msg or "HTTP dispatch failed"
                if msg.attempts >= msg.max_attempts:
                    msg.status = "DEAD_LETTER"
                else:
                    msg.status = "PENDING"
                    delay = self.calculate_backoff(msg.attempts, msg.base_delay, msg.max_delay)
                    msg.next_retry_time = time.time() + delay
                return False

    def _dispatch_http(self, msg: DLQMessage) -> tuple[bool, Optional[str]]:
        """Performs actual HTTP delivery with signature."""
        from src.api.webhooks import EnterpriseWebhookDispatcher
        payload_bytes = json.dumps(msg.payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        sig_header = EnterpriseWebhookDispatcher.sign_payload(msg.secret, payload_bytes)

        req = urllib.request.Request(
            msg.url,
            data=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-TigerGraph-Signature": sig_header,
                "X-TigerGraph-Event": msg.event_type,
                "X-TigerGraph-Retry-Attempt": str(msg.attempts),
                "User-Agent": "TigerGraph-Fraud-Agent-DLQ/1.0.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if 200 <= resp.status < 300:
                    return True, None
                return False, f"HTTP status {resp.status}"
        except urllib.error.HTTPError as e:
            return False, f"HTTP error {e.code}: {e.reason}"
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def retry_all_pending(self, send_fn: Optional[Callable[[DLQMessage], bool]] = None, force: bool = False) -> Dict[str, int]:
        """
        Retries all eligible pending messages whose next_retry_time has elapsed.
        If force is True, retries all pending and dead-letter messages immediately.
        """
        with self._lock:
            now = time.time()
            retried = 0
            succeeded = 0
            failed = 0

            target_ids = []
            for mid, msg in self._messages.items():
                if force:
                    if msg.status in ("PENDING", "DEAD_LETTER"):
                        target_ids.append(mid)
                else:
                    if msg.status == "PENDING" and now >= msg.next_retry_time:
                        target_ids.append(mid)

            for mid in target_ids:
                retried += 1
                ok = self.retry_message(mid, send_fn=send_fn)
                if ok:
                    succeeded += 1
                else:
                    failed += 1

            return {"total_evaluated": retried, "succeeded": succeeded, "failed": failed}

    def requeue_message(self, message_id: str) -> bool:
        """Manually resets a dead-letter message back to PENDING."""
        with self._lock:
            msg = self._messages.get(message_id)
            if not msg:
                return False
            msg.status = "PENDING"
            msg.attempts = 0
            msg.next_retry_time = time.time()
            return True

    def purge(self, status: Optional[str] = None) -> int:
        """Purges messages matching status (or all if None)."""
        with self._lock:
            if status:
                to_delete = [mid for mid, msg in self._messages.items() if msg.status == status]
            else:
                to_delete = list(self._messages.keys())
            for mid in to_delete:
                del self._messages[mid]
            return len(to_delete)

    def get_messages(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns list of serialized messages."""
        with self._lock:
            res = []
            for msg in self._messages.values():
                if status and msg.status != status:
                    continue
                res.append(msg.to_dict())
                if len(res) >= limit:
                    break
            return res

    def get_stats(self) -> Dict[str, Any]:
        """Returns aggregate DLQ counts."""
        with self._lock:
            counts = {"PENDING": 0, "RETRYING": 0, "DELIVERED": 0, "DEAD_LETTER": 0}
            for msg in self._messages.values():
                counts[msg.status] = counts.get(msg.status, 0) + 1
            return {
                "total": len(self._messages),
                "pending": counts.get("PENDING", 0),
                "retrying": counts.get("RETRYING", 0),
                "delivered": counts.get("DELIVERED", 0),
                "dead_letter": counts.get("DEAD_LETTER", 0),
            }


# Global singleton instance
webhook_dlq = WebhookDeadLetterQueue()
