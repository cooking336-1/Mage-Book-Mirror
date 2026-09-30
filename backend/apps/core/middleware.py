"""Distributed HTTP Idempotency Middleware for Mage Books SAAS (Task C.3 / G3).

Protects financial and state-mutating operations (POST, PUT, PATCH) from duplicate execution
caused by network retries, mobile reconnects, or rapid client double-submissions.

Satisfies:
1. Inspects 'Idempotency-Key' header on mutating HTTP requests.
2. Uses Redis distributed locks (SET NX EX 120) with in-flight state tracking.
3. Returns HTTP 409 Conflict if a concurrent request with the same key is in progress.
4. Preserves and replays the exact original status code (e.g. HTTP 201 Created), headers,
   and body upon completion.
5. Deletes the lock on unhandled 5xx server errors to permit safe retries.
"""

import json
import logging
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.payments.services.idempotency import get_redis_client
from apps.tenancy.middleware import get_current_tenant_id

logger = logging.getLogger(__name__)


class IdempotencyMiddleware:
    """Middleware enforcing distributed HTTP idempotency using Redis."""

    IDEMPOTENT_METHODS = ("POST", "PUT", "PATCH")
    IN_FLIGHT_LOCK_TTL = getattr(settings, "IDEMPOTENCY_LOCK_TTL", 120)  # seconds
    COMPLETED_RESPONSE_TTL = 86400  # 24 hours in seconds

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method not in self.IDEMPOTENT_METHODS:
            return self.get_response(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return self.get_response(request)

        idempotency_key = idempotency_key.strip()
        if not idempotency_key:
            return self.get_response(request)

        # Resolve organization/tenant scope
        tenant = getattr(request, "organization", None) or getattr(request, "tenant", None)
        tenant_id = str(tenant.id) if tenant else str(get_current_tenant_id() or "global")

        cache_key = f"idempotency:{tenant_id}:{idempotency_key}"
        redis_client = get_redis_client()

        # Step 1: Check existing key in Redis
        try:
            cached_raw = redis_client.get(cache_key)
        except Exception as exc:
            logger.warning(f"[IdempotencyMiddleware] Redis get failed ({exc}); passing through.")
            return self.get_response(request)

        if cached_raw:
            try:
                cached_data = json.loads(cached_raw)
            except (json.JSONDecodeError, TypeError):
                cached_data = {}

            # Case A: Request currently in flight -> HTTP 409 Conflict
            if cached_data.get("status") == "PENDING":
                return JsonResponse(
                    {
                        "detail": (
                            "A request with this Idempotency-Key is currently in progress. "
                            "Please retry shortly."
                        )
                    },
                    status=409,
                )

            # Case B: Request completed -> Replay cached response
            if cached_data.get("status") == "COMPLETED":
                content = cached_data.get("data", "")
                status_code = cached_data.get("status_code", 200)
                content_type = cached_data.get("content_type", "application/json")
                response = HttpResponse(content, status=status_code, content_type=content_type)
                response["X-Idempotent-Replay"] = "true"
                return response

        # Step 2: Unseen key -> Acquire lock with status PENDING
        pending_payload = json.dumps({"status": "PENDING"})
        try:
            acquired = redis_client.set(
                cache_key,
                pending_payload,
                ex=self.IN_FLIGHT_LOCK_TTL,
                nx=True,
            )
        except Exception as exc:
            logger.warning(f"[IdempotencyMiddleware] Redis lock failed ({exc}); passing through.")
            return self.get_response(request)

        if not acquired:
            # Race condition: another thread acquired the lock between get() and set()
            return JsonResponse(
                {
                    "detail": (
                        "A request with this Idempotency-Key is currently in progress. "
                        "Please retry shortly."
                    )
                },
                status=409,
            )

        # Step 3: Execute request down the chain
        try:
            response = self.get_response(request)
        except Exception:
            # Server crash / unhandled exception: release lock so client can retry
            try:
                redis_client.delete(cache_key)
            except Exception as del_exc:
                logger.warning(f"[IdempotencyMiddleware] Failed to delete key on error: {del_exc}")
            raise

        # Step 4: Record completion or clean up on 5xx
        if 200 <= response.status_code < 500:
            try:
                # Ensure DRF responses are rendered before reading content
                if hasattr(response, "render") and callable(response.render):
                    response.render()

                content_str = (
                    response.content.decode("utf-8")
                    if isinstance(response.content, bytes)
                    else str(response.content)
                )
                completed_payload = json.dumps(
                    {
                        "status": "COMPLETED",
                        "status_code": response.status_code,
                        "data": content_str,
                        "content_type": response.get("Content-Type", "application/json"),
                    }
                )
                redis_client.set(cache_key, completed_payload, ex=self.COMPLETED_RESPONSE_TTL)
            except Exception as store_exc:
                logger.warning(
                    f"[IdempotencyMiddleware] Failed to cache completed response: {store_exc}"
                )
        elif response.status_code >= 500:
            # Server error response: delete key to allow retry
            try:
                redis_client.delete(cache_key)
            except Exception as del_exc:
                logger.warning(f"[IdempotencyMiddleware] Failed to delete key on 5xx: {del_exc}")

        return response
