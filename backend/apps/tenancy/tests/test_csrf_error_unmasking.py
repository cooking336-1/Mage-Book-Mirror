"""Integration tests for unmasking CSRF failures in TenantSecurityMiddleware (Task A.7 / B10).

Verifies:
1. Cookie-authenticated mutating request without CSRF returns HTTP 403 Forbidden (not 401).
2. Cookie-authenticated mutating request with mismatched CSRF token returns HTTP 403 Forbidden.
3. Cookie-authenticated mutating request with valid CSRF token passes middleware.
4. Bearer token authenticated mutating request is exempt from CSRF checks and passes middleware.
5. Truly unauthenticated request continues to return HTTP 401 Unauthorized.
6. TenantSecurityMiddleware.process_exception standardizes PermissionDenied to JSON 403.
"""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.models import CustomUser
from apps.tenancy.middleware import TenantSecurityMiddleware, clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class CSRFErrorUnmaskingTestCase(TestCase):
    """Verifies that CSRF failures on non-exempt tenant endpoints return HTTP 403, not 401."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient(enforce_csrf_checks=True)

        self.org = Organization.objects.create(
            name="Unmasking Test Corp",
            phone="+233240003333",
            email="finance@unmasking.gh",
        )
        self.user = CustomUser.objects.create_user(
            email="admin@unmasking.gh",
            password="StrongPassword2026!",
            first_name="CSRF",
            last_name="Tester",
        )
        self.membership = OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=RoleChoices.ADMIN,
        )

        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

    def tearDown(self) -> None:
        clear_current_tenant()

    def test_cookie_authenticated_post_without_csrf_yields_403(self) -> None:
        """A mutating request using access_token cookie without CSRF token must yield HTTP 403."""
        self.client.cookies["access_token"] = self.access_token

        response = self.client.post(
            "/api/v1/tenancy/members/",
            {"email": "newuser@unmasking.gh", "role": RoleChoices.BOOKKEEPER},
            format="json",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("CSRF", response.json().get("detail", ""))

    def test_cookie_authenticated_post_with_mismatched_csrf_token_yields_403(self) -> None:
        """A mutating request with invalid/mismatched CSRF token must yield HTTP 403."""
        self.client.cookies["access_token"] = self.access_token
        self.client.cookies["csrftoken"] = "invalid_cookie_token_123"

        response = self.client.post(
            "/api/v1/tenancy/members/",
            {"email": "newuser@unmasking.gh", "role": RoleChoices.BOOKKEEPER},
            format="json",
            HTTP_X_TENANT_ID=str(self.org.id),
            HTTP_X_CSRFTOKEN="mismatched_header_token_456",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("CSRF", response.json().get("detail", ""))

    def test_cookie_authenticated_post_with_valid_csrf_passes_middleware(self) -> None:
        """A mutating request with valid access_token and matching CSRF tokens passes middleware."""
        csrf_response = self.client.get("/api/v1/auth/csrf/")
        csrf_token = csrf_response.data["csrf_token"]

        self.client.cookies["access_token"] = self.access_token
        self.client.cookies["csrftoken"] = csrf_token

        response = self.client.post(
            "/api/v1/tenancy/members/",
            {"email": "invited@unmasking.gh", "role": RoleChoices.BOOKKEEPER},
            format="json",
            HTTP_X_TENANT_ID=str(self.org.id),
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        blocked_statuses = (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(response.status_code, blocked_statuses)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_bearer_token_post_exempt_from_csrf_passes_middleware(self) -> None:
        """Bearer token authenticated mutating requests are CSRF-exempt and pass middleware."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.post(
            "/api/v1/tenancy/members/",
            {"email": "bearer_invite@unmasking.gh", "role": RoleChoices.BOOKKEEPER},
            format="json",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

        blocked_statuses = (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(response.status_code, blocked_statuses)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_unauthenticated_request_still_yields_401(self) -> None:
        """Requests with no credentials must return HTTP 401 Unauthorized."""
        response = self.client.post(
            "/api/v1/tenancy/members/",
            {"email": "unauth@unmasking.gh", "role": RoleChoices.BOOKKEEPER},
            format="json",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.json().get("detail"),
            "Authentication credentials were not provided.",
        )

    def test_process_exception_handles_drf_permission_denied(self) -> None:
        """TenantSecurityMiddleware.process_exception standardizes DRF PermissionDenied to 403."""
        middleware = TenantSecurityMiddleware(lambda req: None)
        request = RequestFactory().post("/api/v1/tenancy/members/")

        exc = DRFPermissionDenied("CSRF Failed: Missing cookie.")
        response = middleware.process_exception(request, exc)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("CSRF Failed", response.content.decode())

    def test_process_exception_handles_django_permission_denied(self) -> None:
        """TenantSecurityMiddleware.process_exception standardizes Django PermissionDenied."""
        middleware = TenantSecurityMiddleware(lambda req: None)
        request = RequestFactory().post("/api/v1/tenancy/members/")

        exc = DjangoPermissionDenied("CSRF cookie not set.")
        response = middleware.process_exception(request, exc)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("CSRF cookie not set", response.content.decode())

    def test_process_exception_ignores_unrelated_exceptions(self) -> None:
        """TenantSecurityMiddleware.process_exception returns None for non-permission exceptions."""
        middleware = TenantSecurityMiddleware(lambda req: None)
        request = RequestFactory().post("/api/v1/tenancy/members/")

        exc = ValueError("Some unexpected internal error")
        response = middleware.process_exception(request, exc)

        self.assertIsNone(response)
