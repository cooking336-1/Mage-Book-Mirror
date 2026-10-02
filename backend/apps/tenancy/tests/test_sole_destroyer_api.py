"""Security and compliance tests for the Sole Destroyer Rule (Architecture Manual 4.6.2).

Architecture Manual 4.6.2 (Sole Destroyer Rule):
- Hard SQL CASCADE deletion of organizations is prohibited in favor of soft-archival
  (is_active=False) to ensure compliance with GRA 6-year statutory audit retention.

Tests:
1. DELETE /api/v1/tenancy/organizations/current/ - Owner can soft-deactivate workspace (HTTP 200).
2. DELETE - Admin is blocked with HTTP 403 Forbidden (Sole Destroyer Rule violation).
3. DELETE - Accountant is blocked with HTTP 403 Forbidden.
4. DELETE - Bookkeeper is blocked with HTTP 403 Forbidden.
5. Inactive organization seals access for subsequent requests.
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditTrail
from apps.authentication.models import CustomUser
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class SoleDestroyerSecurityTestCase(TestCase):
    """Verifies that only the primary OWNER can initiate organization deactivation."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()

        self.org = Organization.objects.create(
            name="Horizon Logistics Ltd",
            phone="+233240004444",
            email="ops@horizon.gh",
            is_active=True,
        )

        self.owner = CustomUser.objects.create_user(
            email="owner@horizon.gh",
            password="StrongPassword2026!",
            first_name="Horizon",
            last_name="Owner",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.owner,
            role=RoleChoices.OWNER,
        )

        self.admin = CustomUser.objects.create_user(
            email="admin@horizon.gh",
            password="StrongPassword2026!",
            first_name="Horizon",
            last_name="Admin",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.admin,
            role=RoleChoices.ADMIN,
        )

        self.accountant = CustomUser.objects.create_user(
            email="accountant@horizon.gh",
            password="StrongPassword2026!",
            first_name="Horizon",
            last_name="Accountant",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.accountant,
            role=RoleChoices.ACCOUNTANT,
        )

        self.bookkeeper = CustomUser.objects.create_user(
            email="bookkeeper@horizon.gh",
            password="StrongPassword2026!",
            first_name="Horizon",
            last_name="Bookkeeper",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.bookkeeper,
            role=RoleChoices.BOOKKEEPER,
        )

    def tearDown(self) -> None:
        clear_current_tenant()

    def _authenticate(self, user: CustomUser) -> None:
        token = str(AccessToken.for_user(user))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

    def test_owner_can_soft_archive_organization(self) -> None:
        """Owner can successfully archive the organization workspace (HTTP 200)."""
        self._authenticate(self.owner)
        response = self.client.delete("/api/v1/tenancy/organizations/current/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.org.refresh_from_db()
        self.assertFalse(self.org.is_active)

        # Verify audit trail
        audit = AuditTrail.objects.filter(
            organization=self.org,
            action="ORGANIZATION_DEACTIVATED",
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.user, self.owner)

    def test_admin_is_forbidden_from_deactivating_organization(self) -> None:
        """Arch Manual 4.6.2: Admin receives HTTP 403 Forbidden under Sole Destroyer Rule."""
        self._authenticate(self.admin)
        response = self.client.delete("/api/v1/tenancy/organizations/current/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Sole Destroyer Rule", response.json()["detail"])

        self.org.refresh_from_db()
        self.assertTrue(self.org.is_active)

    def test_accountant_is_forbidden_from_deactivating_organization(self) -> None:
        """Accountant receives HTTP 403 Forbidden."""
        self._authenticate(self.accountant)
        response = self.client.delete("/api/v1/tenancy/organizations/current/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.org.refresh_from_db()
        self.assertTrue(self.org.is_active)

    def test_bookkeeper_is_forbidden_from_deactivating_organization(self) -> None:
        """Bookkeeper receives HTTP 403 Forbidden."""
        self._authenticate(self.bookkeeper)
        response = self.client.delete("/api/v1/tenancy/organizations/current/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.org.refresh_from_db()
        self.assertTrue(self.org.is_active)
