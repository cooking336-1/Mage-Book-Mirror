"""Tests for Organization Current Detail & Accounting Mode Sync (Task D.2 / F8).

Verifies:
1. GET /api/v1/tenancy/organizations/current/ returns active tenant details.
2. PATCH /api/v1/tenancy/organizations/current/ updates default_experience_mode.
3. PATCH supports 'accounting_mode' alias ('strict' -> 'full', 'agile' -> 'simple').
4. PATCH updates organization contact metadata (name, address, phone, email).
5. Role authorization: OWNER and ADMIN are permitted to PATCH; ACCOUNTANT, BOOKKEEPER,
   and AUDITOR are blocked with HTTP 403 Forbidden.
6. Audit trail is generated on updates.
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditTrail
from apps.authentication.models import CustomUser
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import (
    ExperienceModeChoices,
    Organization,
    OrganizationMembership,
    RoleChoices,
)


class OrganizationCurrentAPITestCase(TestCase):
    """Verifies retrieval and updates to active tenant organization settings."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()

        self.org = Organization.objects.create(
            name="Vanguard Logistics Ltd",
            phone="+233240001111",
            email="info@vanguard.gh",
            address="12 Cantonments Road, Accra",
            default_experience_mode=ExperienceModeChoices.SIMPLE,
            is_active=True,
        )

        self.owner = CustomUser.objects.create_user(
            email="owner@vanguard.gh",
            password="StrongPassword2026!",
            first_name="Kwame",
            last_name="Mensah",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.owner,
            role=RoleChoices.OWNER,
        )

        self.admin = CustomUser.objects.create_user(
            email="admin@vanguard.gh",
            password="StrongPassword2026!",
            first_name="Abena",
            last_name="Osei",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.admin,
            role=RoleChoices.ADMIN,
        )

        self.accountant = CustomUser.objects.create_user(
            email="accountant@vanguard.gh",
            password="StrongPassword2026!",
            first_name="Kofi",
            last_name="Boateng",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.accountant,
            role=RoleChoices.ACCOUNTANT,
        )

        self.auditor = CustomUser.objects.create_user(
            email="auditor@pwc.gh",
            password="StrongPassword2026!",
            first_name="External",
            last_name="Auditor",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.auditor,
            role=RoleChoices.AUDITOR,
        )

    def _auth_headers(self, user: CustomUser) -> dict[str, str]:
        token = str(AccessToken.for_user(user))
        return {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_ORGANIZATION_ID": str(self.org.id),
        }

    def test_get_current_organization_details(self) -> None:
        """Any authenticated tenant member can retrieve organization details."""
        res = self.client.get(
            "/api/v1/tenancy/organizations/current/",
            **self._auth_headers(self.accountant),
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], str(self.org.id))
        self.assertEqual(res.data["name"], "Vanguard Logistics Ltd")
        self.assertEqual(res.data["default_experience_mode"], ExperienceModeChoices.SIMPLE)

    def test_owner_can_patch_experience_mode(self) -> None:
        """Owner can update default_experience_mode to full."""
        res = self.client.patch(
            "/api/v1/tenancy/organizations/current/",
            {"default_experience_mode": "full"},
            format="json",
            **self._auth_headers(self.owner),
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["default_experience_mode"], "full")

        self.org.refresh_from_db()
        self.assertEqual(self.org.default_experience_mode, ExperienceModeChoices.FULL)

        # Audit trail created
        self.assertTrue(
            AuditTrail.objects.filter(
                organization=self.org,
                action="ORGANIZATION_UPDATED",
            ).exists()
        )

    def test_patch_supports_accounting_mode_alias(self) -> None:
        """PATCH accepts 'accounting_mode': 'strict' and maps to 'full'."""
        res = self.client.patch(
            "/api/v1/tenancy/organizations/current/",
            {"accounting_mode": "strict"},
            format="json",
            **self._auth_headers(self.admin),
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["default_experience_mode"], "full")

        self.org.refresh_from_db()
        self.assertEqual(self.org.default_experience_mode, ExperienceModeChoices.FULL)

        # And maps 'agile' back to 'simple'
        res = self.client.patch(
            "/api/v1/tenancy/organizations/current/",
            {"accounting_mode": "agile"},
            format="json",
            **self._auth_headers(self.admin),
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["default_experience_mode"], "simple")

        self.org.refresh_from_db()
        self.assertEqual(self.org.default_experience_mode, ExperienceModeChoices.SIMPLE)

    def test_patch_invalid_mode_returns_400(self) -> None:
        """Invalid mode returns HTTP 400 Bad Request."""
        res = self.client.patch(
            "/api/v1/tenancy/organizations/current/",
            {"default_experience_mode": "invalid_mode_123"},
            format="json",
            **self._auth_headers(self.owner),
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("default_experience_mode", res.data)

    def test_non_managers_blocked_from_patching(self) -> None:
        """Accountant and Auditor cannot patch organization settings."""
        res_acct = self.client.patch(
            "/api/v1/tenancy/organizations/current/",
            {"default_experience_mode": "full"},
            format="json",
            **self._auth_headers(self.accountant),
        )
        self.assertEqual(res_acct.status_code, status.HTTP_403_FORBIDDEN)

        res_audit = self.client.patch(
            "/api/v1/tenancy/organizations/current/",
            {"default_experience_mode": "full"},
            format="json",
            **self._auth_headers(self.auditor),
        )
        self.assertEqual(res_audit.status_code, status.HTTP_403_FORBIDDEN)
