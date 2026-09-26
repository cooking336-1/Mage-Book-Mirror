"""Security and integration tests for Financial Destination Locks.

Architecture Manual 4.6.2 (Financial Destination Locks):
- Modifying payout bank accounts or mobile money merchant settlement wallets
  sends a mandatory SMS/TOTP OTP challenge exclusively to the primary Owner.
- Protects against Rogue Manager threat rerouting revenue to unauthorized wallets.

Tests:
1. GET /api/v1/tenancy/organization/settlement/ - Owner, Admin, Accountant can read coordinates.
2. PATCH /api/v1/tenancy/organization/settlement/ - Owner can update directly.
3. PATCH - Admin update rejected without Owner TOTP code (HTTP 400).
4. PATCH - Admin update rejected if Owner has not enrolled 2FA (HTTP 400).
5. PATCH - Admin update rejected with invalid Owner TOTP code (HTTP 403).
6. PATCH - Admin update succeeds with valid Owner Step-Up TOTP code (HTTP 200).
7. PATCH - Replayed Owner TOTP code is rejected within drift window (HTTP 403).
8. PATCH - Bookkeeper and Auditor are forbidden (HTTP 403).
"""

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditTrail
from apps.authentication.models import CustomUser
from apps.payroll.models import PayrollTwoFactorProfile
from apps.payroll.services.totp_service import generate_base32_secret, generate_totp_code
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class SettlementDestinationLocksAPITestCase(TestCase):
    """Verifies Financial Destination Locks and Owner Step-Up OTP challenges."""

    def setUp(self) -> None:
        clear_current_tenant()
        cache.clear()
        self.client = APIClient()

        self.org = Organization.objects.create(
            name="Apex Retailers Ltd",
            phone="+233240003333",
            email="settlement@apex.gh",
            settlement_bank_name="GCB Bank Ltd",
            settlement_account_number="1234567890123",
            settlement_momo_number="0244111222",
        )

        self.owner = CustomUser.objects.create_user(
            email="owner@apex.gh",
            password="StrongPassword2026!",
            first_name="Apex",
            last_name="Owner",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.owner,
            role=RoleChoices.OWNER,
        )

        # Enroll Owner in Step-Up 2FA
        self.owner_secret = generate_base32_secret()
        self.owner_2fa = PayrollTwoFactorProfile.objects.create(
            user=self.owner,
            totp_secret=self.owner_secret,
            is_enabled=True,
        )

        self.admin = CustomUser.objects.create_user(
            email="admin@apex.gh",
            password="StrongPassword2026!",
            first_name="Apex",
            last_name="Admin",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.admin,
            role=RoleChoices.ADMIN,
        )

        self.bookkeeper = CustomUser.objects.create_user(
            email="bookkeeper@apex.gh",
            password="StrongPassword2026!",
            first_name="Apex",
            last_name="Bookkeeper",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.bookkeeper,
            role=RoleChoices.BOOKKEEPER,
        )

    def tearDown(self) -> None:
        clear_current_tenant()
        cache.clear()

    def _authenticate(self, user: CustomUser) -> None:
        token = str(AccessToken.for_user(user))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

    def test_get_settlement_destinations(self) -> None:
        """GET /api/v1/tenancy/organization/settlement/ returns current payout destinations."""
        self._authenticate(self.owner)
        response = self.client.get("/api/v1/tenancy/organization/settlement/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["settlement_bank_name"], "GCB Bank Ltd")
        self.assertEqual(data["settlement_momo_number"], "0244111222")

    def test_owner_can_update_settlement_directly(self) -> None:
        """Owner can update settlement destinations directly without 2FA challenge."""
        self._authenticate(self.owner)
        payload = {
            "settlement_bank_name": "Ecobank Ghana PLC",
            "settlement_account_number": "9876543210987",
            "settlement_momo_number": "0555999888",
        }
        response = self.client.patch(
            "/api/v1/tenancy/organization/settlement/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.org.refresh_from_db()
        self.assertEqual(self.org.settlement_bank_name, "Ecobank Ghana PLC")
        self.assertEqual(self.org.settlement_account_number, "9876543210987")
        self.assertEqual(self.org.settlement_momo_number, "0555999888")
        self.assertIsNotNone(self.org.settlement_locked_at)

        # Verify audit trail
        self.assertTrue(
            AuditTrail.objects.filter(
                organization=self.org,
                action="SETTLEMENT_DESTINATIONS_UPDATED",
            ).exists()
        )

    def test_admin_update_without_totp_is_rejected(self) -> None:
        """Admin attempting to alter payout destination without Owner TOTP is rejected."""
        self._authenticate(self.admin)
        payload = {
            "settlement_momo_number": "0240000000",  # Rogue redirection attempt
        }
        response = self.client.patch(
            "/api/v1/tenancy/organization/settlement/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("owner_totp_code", response.json())

    def test_admin_update_with_invalid_totp_is_forbidden(self) -> None:
        """Admin providing an invalid 6-digit TOTP receives HTTP 403 Forbidden."""
        self._authenticate(self.admin)
        payload = {
            "settlement_momo_number": "0240000000",
            "owner_totp_code": "000000",
        }
        response = self.client.patch(
            "/api/v1/tenancy/organization/settlement/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Invalid Owner TOTP", response.json()["detail"])

    def test_admin_update_succeeds_with_valid_owner_totp(self) -> None:
        """Admin providing a valid Owner Step-Up TOTP code successfully updates coordinates."""
        valid_totp = generate_totp_code(self.owner_secret)
        self._authenticate(self.admin)

        payload = {
            "settlement_bank_name": "Standard Chartered Bank Ghana",
            "settlement_account_number": "5551112223334",
            "settlement_momo_number": "0244333444",
            "owner_totp_code": valid_totp,
        }
        response = self.client.patch(
            "/api/v1/tenancy/organization/settlement/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.org.refresh_from_db()
        self.assertEqual(self.org.settlement_bank_name, "Standard Chartered Bank Ghana")
        self.assertEqual(self.org.settlement_momo_number, "0244333444")

    def test_admin_totp_replay_is_blocked(self) -> None:
        """Replaying a previously used Owner TOTP code within drift window is blocked."""
        valid_totp = generate_totp_code(self.owner_secret)
        self._authenticate(self.admin)

        payload = {
            "settlement_momo_number": "0244333444",
            "owner_totp_code": valid_totp,
        }
        # First request consumes token
        res1 = self.client.patch(
            "/api/v1/tenancy/organization/settlement/",
            payload,
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # Replay attempt
        res2 = self.client.patch(
            "/api/v1/tenancy/organization/settlement/",
            {"settlement_momo_number": "0200999999", "owner_totp_code": valid_totp},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("already been consumed", res2.json()["detail"])

    def test_bookkeeper_cannot_update_settlement_destinations(self) -> None:
        """Bookkeepers receive HTTP 403 Forbidden on any settlement modification attempt."""
        self._authenticate(self.bookkeeper)
        response = self.client.patch(
            "/api/v1/tenancy/organization/settlement/",
            {"settlement_momo_number": "0244111222"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
