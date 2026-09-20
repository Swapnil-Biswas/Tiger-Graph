"""
Dynamic Rate Limiting and DoS Interception Filter for TigerGraph Agentic Fraud API
Implements thread-safe Token Bucket rate limiting, tiered endpoint quotas,
client quarantining/blacklisting, and RFC 6585 HTTP 429 responses.
"""

import time
import threading
from typing import Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass
class RateLimitQuota:
    """Defines rate limit capacity and refill rate."""
    capacity: int          # Maximum burst tokens
    refill_rate: float     # Tokens per second
    cost: int = 1          # Cost per request


class TokenBucket:
    """Thread-safe Token Bucket for a single client identifier."""
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def consume(self, cost: int = 1) -> Tuple[bool, float, int]:
        """
        Attempts to consume `cost` tokens.
        Returns (allowed: bool, retry_after: float, remaining: int).
        """
        with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.last_refill = now

            # Refill tokens up to capacity
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

            if self.tokens >= cost:
                self.tokens -= cost
                remaining = int(self.tokens)
                return True, 0.0, remaining
            else:
                deficit = cost - self.tokens
                retry_after = deficit / self.refill_rate if self.refill_rate > 0 else 1.0
                return False, retry_after, int(self.tokens)

    def reset(self):
        with self._lock:
            self.tokens = self.capacity
            self.last_refill = time.time()


class DynamicRateLimiter:
    """
    Coordinates multi-client token buckets, route-based tiering,
    and automatic quarantining of abusive clients.
    """
    def __init__(
        self,
        default_capacity: int = 60,
        default_refill_rate: float = 1.0,  # 60 req/min
        tier_quotas: Optional[Dict[str, RateLimitQuota]] = None,
        quarantine_threshold: int = 5,     # Violations before quarantine
        quarantine_duration: float = 30.0, # Quarantine duration in seconds
    ):
        self.default_quota = RateLimitQuota(capacity=default_capacity, refill_rate=default_refill_rate)
        self.quarantine_threshold = quarantine_threshold
        self.quarantine_duration = quarantine_duration

        self._lock = threading.RLock()
        self.buckets: Dict[str, Dict[str, TokenBucket]] = {}  # client_id -> {tier -> TokenBucket}
        self.violations: Dict[str, list[float]] = {}          # client_id -> timestamps
        self.quarantined: Dict[str, float] = {}               # client_id -> quarantine_expiry
        self.whitelist: Set[str] = set()

        # Route tiers
        if tier_quotas is not None:
            self.tier_quotas = tier_quotas
        else:
            self.tier_quotas = {
                "critical": RateLimitQuota(capacity=min(10, default_capacity), refill_rate=min(0.5, default_refill_rate), cost=1),
                "standard": RateLimitQuota(capacity=default_capacity, refill_rate=default_refill_rate, cost=1),
                "relaxed": RateLimitQuota(capacity=max(200, default_capacity), refill_rate=max(10.0, default_refill_rate), cost=1),
            }

    def get_tier_for_path(self, path: str) -> str:
        """Categorize request path into rate limit tiers."""
        if path.startswith("/api/investigate") or path.startswith("/api/benchmark/run") or path == "/graphql":
            return "critical"
        if path.startswith("/api/docs") or path.startswith("/docs") or path.startswith("/openapi.json"):
            return "relaxed"
        if path.startswith("/health") or path.startswith("/metrics"):
            return "relaxed"
        return "standard"

    def check_limit(self, client_id: str, path: str) -> Tuple[bool, float, int, int]:
        """
        Evaluates whether a request from client_id to path is permitted.
        Returns: (allowed: bool, retry_after: float, remaining: int, limit: int).
        """
        now = time.time()

        with self._lock:
            # Check whitelist
            if client_id in self.whitelist:
                return True, 0.0, 9999, 9999

            # Check active quarantine
            if client_id in self.quarantined:
                expiry = self.quarantined[client_id]
                if now < expiry:
                    retry_after = expiry - now
                    return False, retry_after, 0, 0
                else:
                    # Quarantine expired
                    del self.quarantined[client_id]

            tier = self.get_tier_for_path(path)
            quota = self.tier_quotas.get(tier, self.default_quota)

            if client_id not in self.buckets:
                self.buckets[client_id] = {}
            if tier not in self.buckets[client_id]:
                self.buckets[client_id][tier] = TokenBucket(quota.capacity, quota.refill_rate)

            bucket = self.buckets[client_id][tier]
            allowed, retry_after, remaining = bucket.consume(quota.cost)

            if not allowed:
                # Record violation for quarantine evaluation
                v_list = self.violations.get(client_id, [])
                # Prune violations older than 30s
                v_list = [t for t in v_list if now - t <= 30.0]
                v_list.append(now)
                self.violations[client_id] = v_list

                if len(v_list) >= self.quarantine_threshold:
                    self.quarantined[client_id] = now + self.quarantine_duration
                    retry_after = self.quarantine_duration

            return allowed, retry_after, remaining, quota.capacity

    def reset_client(self, client_id: str):
        """Reset rate limit buckets and violations for a client."""
        with self._lock:
            if client_id in self.buckets:
                for bucket in self.buckets[client_id].values():
                    bucket.reset()
            self.violations.pop(client_id, None)
            self.quarantined.pop(client_id, None)

    def get_stats(self) -> Dict[str, Any]:
        """Returns diagnostic rate limiter statistics."""
        with self._lock:
            return {
                "active_clients": len(self.buckets),
                "quarantined_clients": len(self.quarantined),
                "quarantined_ids": list(self.quarantined.keys()),
                "total_tracked_violations": sum(len(v) for v in self.violations.values()),
            }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing dynamic rate limits on HTTP requests."""

    def __init__(self, app, limiter: Optional[DynamicRateLimiter] = None):
        super().__init__(app)
        self.limiter = limiter or DynamicRateLimiter()

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract client identifier: X-Forwarded-For, X-API-Key, or client.host
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
        client_id = f"key:{api_key}" if api_key else f"ip:{client_ip}"

        path = request.url.path

        # Bypass static UI and favicon
        if path.startswith("/ui") or path.endswith(".css") or path.endswith(".js") or path.endswith(".ico") or path.endswith(".png"):
            return await call_next(request)

        allowed, retry_after, remaining, limit = self.limiter.check_limit(client_id, path)

        if not allowed:
            headers = {
                "Retry-After": str(int(retry_after) + 1),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + retry_after)),
            }
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {int(retry_after) + 1} seconds.",
                    "retry_after_seconds": round(retry_after, 2),
                    "client_id": client_id,
                },
                headers=headers,
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


# Global singleton instance
rate_limiter = DynamicRateLimiter()
