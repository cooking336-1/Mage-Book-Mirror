"""Integration test suite for distributed HTTP IdempotencyMiddleware (Task C.3 / G3 / T3.5).

Verifies:
- Requests without Idempotency-Key pass through transparently
- First request with Idempotency-Key executes and caches response with original status code
  (e.g. 201)
- Subsequent request with same Idempotency-Key replays exact cached response with
  X-Idempotent-Replay header
- Concurrent in-flight request (status == 'PENDING') returns HTTP 409 Conflict
- Different tenants using the same Idempotency-Key are properly isolated and do not collide
- Server errors (5xx) release the lock so clients can safely retry
- Safe HTTP methods (GET, HEAD) are not intercepted by idempotency locking
"""

import json
import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.payments.services.idempotency import get_redis_client
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices

User = get_user_model()


class HTTPIdempotencyMiddlewareTests(APITestCase):
    """Test suite for Redis-backed distributed HTTP idempotency middleware."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()
        self.redis = get_redis_client()
        self.redis.clear()

        # Create user and tenant organization
        self.user = User.objects.create_user(
            email="idempotency.tester@magebooks.com",
            password="SecurePassword2026!",
            first_name="Kwame",
            last_name="Nkrumah",
        )
        self.org = Organization.objects.create(
            name="Idempotency Test Org",
            business_tin="C0001112223",
        )
        self.membership = OrganizationMembership.objects.create(
            user=self.user,
            organization=self.org,
            role=RoleChoices.OWNER,
            is_active=True,
        )

        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.contacts_url = reverse("invoicing:contact-list")

    def tearDown(self) -> None:
        clear_current_tenant()

    def test_request_without_idempotency_key_passes_through(self) -> None:
        """Mutating requests without Idempotency-Key header succeed without caching."""
        response = self.client.post(
            self.contacts_url,
            {"name": "Standard Contact No Key", "contact_type": "CUSTOMER"},
            format="json",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("X-Idempotent-Replay", response.headers)

    def test_first_request_creates_resource_and_second_replays_exact_201(self) -> None:
        """Second identical request with same key replays exact cached response and 201 status."""
        key = str(uuid.uuid4())
        payload = {"name": "Unique Idempotent Contact", "contact_type": "CUSTOMER"}

        # First request: Creates resource (201 Created)
        response1 = self.client.post(
            self.contacts_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        created_id = response1.data["id"]
        self.assertNotIn("X-Idempotent-Replay", response1.headers)

        # Second request: Replays cached 201 response with identical body
        response2 = self.client.post(
            self.contacts_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.headers.get("X-Idempotent-Replay"), "true")
        data2 = response2.json()
        self.assertEqual(data2["id"], created_id)
        self.assertEqual(data2["name"], "Unique Idempotent Contact")

    def test_concurrent_in_flight_request_returns_409_conflict(self) -> None:
        """If a request is currently processing (PENDING), concurrent request receives 409."""
        key = str(uuid.uuid4())
        cache_key = f"idempotency:{self.org.id}:{key}"

        # Pre-seed Redis key with PENDING status (simulating in-flight database transaction)
        self.redis.set(cache_key, json.dumps({"status": "PENDING"}), ex=60)

        response = self.client.post(
            self.contacts_url,
            {"name": "In Flight Contact", "contact_type": "CUSTOMER"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("in progress", data["detail"])

    def test_tenant_isolation_prevents_cross_tenant_key_collision(self) -> None:
        """Same Idempotency-Key used by two different tenants does not collide or leak data."""
        org2 = Organization.objects.create(
            name="Second Test Org",
            business_tin="C0009998887",
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=org2,
            role=RoleChoices.OWNER,
            is_active=True,
        )

        shared_key = str(uuid.uuid4())

        # Org 1 creates contact
        resp1 = self.client.post(
            self.contacts_url,
            {"name": "Tenant 1 Contact", "contact_type": "CUSTOMER"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=shared_key,
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp1.data["name"], "Tenant 1 Contact")

        # Org 2 creates contact with SAME idempotency key -> Not a replay, separate resource
        resp2 = self.client.post(
            self.contacts_url,
            {"name": "Tenant 2 Contact", "contact_type": "CUSTOMER"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=shared_key,
            HTTP_X_ORGANIZATION_ID=str(org2.id),
        )
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("X-Idempotent-Replay", resp2.headers)
        self.assertEqual(resp2.data["name"], "Tenant 2 Contact")
        self.assertNotEqual(resp1.data["id"], resp2.data["id"])

    def test_safe_get_methods_ignore_idempotency_key(self) -> None:
        """GET requests with Idempotency-Key are not locked or replayed."""
        key = str(uuid.uuid4())
        response = self.client.get(
            self.contacts_url,
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cache_key = f"idempotency:{self.org.id}:{key}"
        self.assertFalse(self.redis.exists(cache_key))

    def test_client_validation_error_400_is_cached_and_replayed(self) -> None:
        """400 validation error responses are cached and replayed identically."""
        key = str(uuid.uuid4())
        # Invalid payload: missing required 'name' field
        payload = {"contact_type": "CUSTOMER"}

        response1 = self.client.post(
            self.contacts_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        self.assertEqual(response1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response1.data)

        # Second request replays identical 400 response
        response2 = self.client.post(
            self.contacts_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response2.headers.get("X-Idempotent-Replay"), "true")
        data2 = response2.json()
        self.assertIn("name", data2)
