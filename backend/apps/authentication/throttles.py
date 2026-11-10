"""Rate limiting throttles for authentication endpoints.

Protects password reset requests against:
1. Automated bot flooding & worker thread exhaustion (IP-level throttle: 5/min).
2. Targeted user email bombing & Brevo daily quota exhaustion:
   - Burst window: max 3 requests per 15 minutes (900s).
   - Daily ceiling: max 5 requests per 24 hours (86,400s).
3. Preserves privacy: Hashes email addresses with SHA-256 (no raw PII in cache).
4. Preserves anti-enumeration: Throttles identically whether account exists in DB or not.
"""

import hashlib
import time

from django.core.cache import cache
from rest_framework.request import Request
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
from rest_framework.views import APIView


class PasswordResetIPThrottle(SimpleRateThrottle):
    """Restricts password reset requests from any single IP to 5 per minute."""

    scope = "password_reset_ip"
    rate = "5/min"

    def get_rate(self) -> str:
        return self.rate

    def get_cache_key(self, request: Request, view: APIView) -> str:
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class PasswordResetEmailThrottle(BaseThrottle):
    """Enforces dual-window rate limiting scoped by target email address.

    1. Burst window: Max 3 requests per 15 minutes (900 seconds).
    2. Daily ceiling: Max 5 requests per 24 hours (86,400 seconds).
    """

    BURST_LIMIT = 3
    BURST_TIMEOUT = 900  # 15 minutes in seconds

    DAILY_LIMIT = 5
    DAILY_TIMEOUT = 86400  # 24 hours in seconds

    def __init__(self) -> None:
        self.wait_time: int | None = None

    def allow_request(self, request: Request, view: APIView) -> bool:
        email = request.data.get("email", "")
        if not email or not isinstance(email, str) or "@" not in email:
            # Let the serializer handle malformed input
            return True

        clean_email = email.strip().lower()
        email_hash = hashlib.sha256(clean_email.encode("utf-8")).hexdigest()[:16]

        burst_key = f"throttle:reset:burst:{email_hash}"
        daily_key = f"throttle:reset:daily:{email_hash}"

        now = time.time()

        # 1. Check Daily Cap (5 per 24 hours)
        daily_history: list[float] = cache.get(daily_key) or []
        daily_history = [t for t in daily_history if now - t < self.DAILY_TIMEOUT]
        if len(daily_history) >= self.DAILY_LIMIT:
            self.wait_time = max(1, int(self.DAILY_TIMEOUT - (now - daily_history[0])))
            return False

        # 2. Check 15-Minute Burst (3 per 15 minutes)
        burst_history: list[float] = cache.get(burst_key) or []
        burst_history = [t for t in burst_history if now - t < self.BURST_TIMEOUT]
        if len(burst_history) >= self.BURST_LIMIT:
            self.wait_time = max(1, int(self.BURST_TIMEOUT - (now - burst_history[0])))
            return False

        # Record attempt in cache
        burst_history.append(now)
        cache.set(burst_key, burst_history, timeout=self.BURST_TIMEOUT)

        daily_history.append(now)
        cache.set(daily_key, daily_history, timeout=self.DAILY_TIMEOUT)

        return True

    def wait(self) -> int | None:
        """Returns the number of seconds the client must wait before retrying."""
        return self.wait_time
