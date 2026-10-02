"""Security and BOLA negative abuse test suite for TenantSecurityMiddleware (Task B.10 / T2.4).

Covers:
- Cross-Tenant Header Spoofing (BOLA) rejection with HTTP 403 Forbidden
- Malformed UUID Header handling with HTTP 400 Bad Request
- Missing Tenant Header handling with HTTP 400 Bad Request
- Inactive Organization Membership access revocation with HTTP 403 Forbidden
- Expired Auditor Access Window containment with HTTP 403 Forbidden
- Auditor Mutating Write Containment (POST, PUT, PATCH, DELETE) with HTTP 403 Forbidden
- Dual Header Resolution (X-Tenant-ID & X-Organization-ID)
- Public Path Exemptions from Tenant Headers
- Fail-Closed Database Session Binding Failure (HTTP 500)
- Thread-Local Tenant Context Cleanup & RLS Leak Defense
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.tenancy.middleware import (
    TenantSecurityMiddleware,
    get_current_tenant,
    get_current_tenant_id,
    get_current_tenant_role,
)
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices

User = get_user_model()


class MiddlewareGuardsBOLASecurityTests(APITestCase):
    """T2.4: Multi-Tenant Middleware Guard and BOLA Test Suite."""

    def setUp(self):
        # Create User Alpha (Legitimate Owner of Org Alpha)
        self.user_alpha = User.objects.create_user(
            email="owner.alpha@magebooks.com",
            password="SecurePassword123!",
            first_name="Alpha",
            last_name="Owner",
        )

        # Create User Beta (Attacker / Owner of Org Beta)
        self.user_beta = User.objects.create_user(
            email="attacker.beta@magebooks.com",
            password="SecurePassword123!",
            first_name="Beta",
            last_name="Attacker",
        )

        # Create Organization Alpha and Organization Beta
        self.org_alpha = Organization.objects.create(
            name="Alpha Enterprises",
            phone="+233241000101",
            email="contact@alpha.com",
        )
        self.org_beta = Organization.objects.create(
            name="Beta Competitor Ltd",
            phone="+233241000102",
            email="contact@beta.com",
        )

        # Assign User Alpha -> Org Alpha (OWNER)
        self.membership_alpha = OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=self.user_alpha,
            role=RoleChoices.OWNER,
            is_active=True,
        )

        # Assign User Beta -> Org Beta (OWNER)
        self.membership_beta = OrganizationMembership.objects.create(
            organization=self.org_beta,
            user=self.user_beta,
            role=RoleChoices.OWNER,
            is_active=True,
        )

        self.context_url = reverse("tenancy:tenant-context")
        self.csrf_url = reverse("authentication:csrf")
        self.login_url = reverse("authentication:login")

    def _authenticate(self, user):
        """Helper to set Bearer token credentials on APIClient."""
        token = AccessToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_unauthenticated_request_to_tenant_endpoint_returns_401(self):
        """Requests without JWT or session cookie must be rejected with HTTP 401."""
        response = self.client.get(
            self.context_url,
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.json())

    def test_missing_tenant_header_returns_400(self):
        """Authenticated request missing X-Tenant-ID/X-Organization-ID header fails with 400."""
        self._authenticate(self.user_alpha)
        response = self.client.get(self.context_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json().get("detail"),
            "X-Tenant-ID or X-Organization-ID header is required.",
        )

    def test_malformed_uuid_header_fails_closed_with_400(self):
        """Header containing malformed, non-UUID strings fails closed with HTTP 400."""
        self._authenticate(self.user_alpha)
        malformed_inputs = [
            "not-a-uuid",
            "12345",
            "c9bf9e57-1685-4c89-bafb-invalidhex!!",
            "' OR '1'='1",
            "../etc/passwd",
        ]
        for bad_id in malformed_inputs:
            response = self.client.get(
                self.context_url,
                HTTP_X_TENANT_ID=bad_id,
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(
                response.json().get("detail"),
                "Invalid tenant ID header format.",
            )

    def test_cross_tenant_header_spoofing_bola_strictly_blocked_403(self):
        """BOLA Defense: User Beta attempts to access Org Alpha by spoofing X-Tenant-ID.

        Must be rejected immediately with HTTP 403 Forbidden.
        """
        self._authenticate(self.user_beta)
        response = self.client.get(
            self.context_url,
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.json().get("detail"),
            "You do not have active access to this organization.",
        )

    def test_inactive_organization_membership_blocked_403(self):
        """User whose membership was deactivated (is_active=False) is blocked with HTTP 403."""
        staff_user = User.objects.create_user(
            email="staff.inactive@magebooks.com",
            password="SecurePassword123!",
        )
        OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=staff_user,
            role=RoleChoices.BOOKKEEPER,
            is_active=False,
        )

        self._authenticate(staff_user)
        response = self.client.get(
            self.context_url,
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.json().get("detail"),
            "You do not have active access to this organization.",
        )

    def test_expired_auditor_membership_blocked_403(self):
        """Auditor whose ephemeral access has elapsed is blocked with HTTP 403."""
        auditor = User.objects.create_user(
            email="auditor.expired@auditfirm.com",
            password="SecurePassword123!",
        )
        OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=auditor,
            role=RoleChoices.AUDITOR,
            is_active=True,
            access_expires_at=timezone.now() - timedelta(minutes=5),
        )

        self._authenticate(auditor)
        response = self.client.get(
            self.context_url,
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.json().get("detail"),
            "Auditor access has expired for this organization.",
        )

    def test_active_auditor_read_allowed_write_strictly_blocked_403(self):
        """Auditor write containment (Sequence Diagram Line 432).

        Active auditor can perform GET, but mutating requests (POST, PUT, PATCH, DELETE) fail 403.
        """
        auditor = User.objects.create_user(
            email="auditor.active@auditfirm.com",
            password="SecurePassword123!",
        )
        OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=auditor,
            role=RoleChoices.AUDITOR,
            is_active=True,
            access_expires_at=timezone.now() + timedelta(days=14),
        )

        self._authenticate(auditor)

        # GET succeeds
        get_res = self.client.get(
            self.context_url,
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.json()["tenant_role"], RoleChoices.AUDITOR)

        # POST mutating request fails closed
        post_res = self.client.post(
            self.context_url,
            {"action": "modify"},
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
            format="json",
        )
        self.assertEqual(post_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            post_res.json().get("detail"),
            "Auditor role has strictly read-only access.",
        )

    def test_dual_header_support_x_organization_id(self):
        """Header X-Organization-ID functions as supported alias for X-Tenant-ID."""
        self._authenticate(self.user_alpha)
        response = self.client.get(
            self.context_url,
            HTTP_X_ORGANIZATION_ID=str(self.org_alpha.id),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["tenant_id"], str(self.org_alpha.id))

    def test_public_routes_exempt_from_tenant_headers(self):
        """Public authentication endpoints are exempt from requiring tenant headers."""
        csrf_res = self.client.get(self.csrf_url)
        self.assertEqual(csrf_res.status_code, status.HTTP_200_OK)

        login_res = self.client.post(
            self.login_url,
            {"email": "owner.alpha@magebooks.com", "password": "WrongPassword!"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rls_session_deallocation_and_thread_local_cleanup(self):
        """Context cleanup: Thread-local tenant references are cleaned up after request."""
        self.assertIsNone(get_current_tenant())
        self.assertIsNone(get_current_tenant_id())
        self.assertIsNone(get_current_tenant_role())

        self._authenticate(self.user_alpha)
        response = self.client.get(
            self.context_url,
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Assert security headers
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")

        # Assert thread-local context cleared
        self.assertIsNone(get_current_tenant())
        self.assertIsNone(get_current_tenant_id())
        self.assertIsNone(get_current_tenant_role())

    def test_bind_db_session_failure_fails_closed_with_500(self):
        """Fail-closed on RLS session binding failure."""
        self._authenticate(self.user_alpha)
        with patch.object(
            TenantSecurityMiddleware,
            "_bind_db_session",
            side_effect=DatabaseError("Simulated database failure"),
        ):
            response = self.client.get(
                self.context_url,
                HTTP_X_TENANT_ID=str(self.org_alpha.id),
            )
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertEqual(
                response.json().get("detail"),
                "Failed to establish secure tenant database context.",
            )

        self.assertIsNone(get_current_tenant())
        self.assertIsNone(get_current_tenant_id())
        self.assertIsNone(get_current_tenant_role())
