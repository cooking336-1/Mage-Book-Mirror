"""Integration tests for Fiscal Period Listing and Closing API endpoints.

Tests:
1. GET /api/v1/ledger/fiscal-periods/ - Tenant period listing
2. POST /api/v1/ledger/fiscal-periods/<id>/close/ - OWNER can close period
3. POST /api/v1/ledger/fiscal-periods/<id>/close/ - ACCOUNTANT can close period
4. POST /api/v1/ledger/fiscal-periods/<id>/close/ - ADMIN is blocked (HTTP 403)
5. POST /api/v1/ledger/fiscal-periods/<id>/close/ - BOOKKEEPER is blocked (HTTP 403)
6. POST /api/v1/ledger/fiscal-periods/<id>/close/ - AUDITOR is blocked (HTTP 403)
7. POST /api/v1/ledger/fiscal-periods/<id>/close/ - Already closed period returns 400
8. Cross-tenant isolation - Tenant Beta cannot close Tenant Alpha's period
"""

import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditTrail
from apps.authentication.models import CustomUser
from apps.ledger.models import FiscalPeriod
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class FiscalPeriodClosingAPITestCase(TestCase):
    """Verifies RBAC rules and ledger locking on the fiscal period closing endpoint."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()

        # Organization Alpha
        self.org_alpha = Organization.objects.create(
            name="Alpha Corp Ltd",
            phone="+233240001111",
            email="finance@alpha.gh",
        )
        # Organization Beta
        self.org_beta = Organization.objects.create(
            name="Beta Enterprise Ltd",
            phone="+233240002222",
            email="finance@beta.gh",
        )

        # Users & Memberships for Org Alpha
        self.owner = CustomUser.objects.create_user(
            email="owner@alpha.gh",
            password="StrongPassword2026!",
            first_name="Alpha",
            last_name="Owner",
        )
        OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=self.owner,
            role=RoleChoices.OWNER,
        )

        self.accountant = CustomUser.objects.create_user(
            email="accountant@alpha.gh",
            password="StrongPassword2026!",
            first_name="Alpha",
            last_name="Accountant",
        )
        OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=self.accountant,
            role=RoleChoices.ACCOUNTANT,
        )

        self.admin = CustomUser.objects.create_user(
            email="admin@alpha.gh",
            password="StrongPassword2026!",
            first_name="Alpha",
            last_name="Admin",
        )
        OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=self.admin,
            role=RoleChoices.ADMIN,
        )

        self.bookkeeper = CustomUser.objects.create_user(
            email="bookkeeper@alpha.gh",
            password="StrongPassword2026!",
            first_name="Alpha",
            last_name="Bookkeeper",
        )
        OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=self.bookkeeper,
            role=RoleChoices.BOOKKEEPER,
        )

        self.auditor = CustomUser.objects.create_user(
            email="auditor@pwc.gh",
            password="StrongPassword2026!",
            first_name="External",
            last_name="Auditor",
        )
        OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=self.auditor,
            role=RoleChoices.AUDITOR,
            access_expires_at=timezone.now() + datetime.timedelta(days=14),
        )

        # Period for Org Alpha
        self.period_alpha = FiscalPeriod.objects.create(
            organization=self.org_alpha,
            period_name="January 2026",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 31),
            is_closed=False,
        )

        # Period for Org Beta
        self.period_beta = FiscalPeriod.objects.create(
            organization=self.org_beta,
            period_name="January 2026",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 31),
            is_closed=False,
        )

    def tearDown(self) -> None:
        clear_current_tenant()

    def _authenticate(self, user: CustomUser, org: Organization) -> None:
        token = str(AccessToken.for_user(user))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(org.id),
        )

    def test_list_fiscal_periods_returns_tenant_periods(self) -> None:
        """GET /api/v1/ledger/fiscal-periods/ returns only periods for authenticated tenant."""
        self._authenticate(self.owner, self.org_alpha)
        response = self.client.get("/api/v1/fiscal-periods/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], str(self.period_alpha.id))
        self.assertEqual(data[0]["period_name"], "January 2026")
        self.assertFalse(data[0]["is_closed"])

    def test_owner_can_close_fiscal_period(self) -> None:
        """Owner can successfully close a fiscal period, locking it and emitting an audit log."""
        self._authenticate(self.owner, self.org_alpha)
        response = self.client.post(f"/api/v1/fiscal-periods/{self.period_alpha.id}/close/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.period_alpha.refresh_from_db()
        self.assertTrue(self.period_alpha.is_closed)
        self.assertEqual(self.period_alpha.closed_by, self.owner)
        self.assertIsNotNone(self.period_alpha.closed_at)

        # Verify audit log
        audit = AuditTrail.objects.filter(
            organization=self.org_alpha,
            action="FISCAL_PERIOD_CLOSED",
            entity_id=str(self.period_alpha.id),
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.user, self.owner)

    def test_accountant_can_close_fiscal_period(self) -> None:
        """Certified Accountant can successfully close a fiscal period."""
        self._authenticate(self.accountant, self.org_alpha)
        response = self.client.post(f"/api/v1/fiscal-periods/{self.period_alpha.id}/close/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.period_alpha.refresh_from_db()
        self.assertTrue(self.period_alpha.is_closed)
        self.assertEqual(self.period_alpha.closed_by, self.accountant)

    def test_admin_is_forbidden_from_closing_fiscal_period(self) -> None:
        """Architecture Manual 4.6.1: Admins are strictly forbidden from closing fiscal periods."""
        self._authenticate(self.admin, self.org_alpha)
        response = self.client.post(f"/api/v1/fiscal-periods/{self.period_alpha.id}/close/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.period_alpha.refresh_from_db()
        self.assertFalse(self.period_alpha.is_closed)

    def test_bookkeeper_is_forbidden_from_closing_fiscal_period(self) -> None:
        """Bookkeepers are strictly forbidden from closing fiscal periods."""
        self._authenticate(self.bookkeeper, self.org_alpha)
        response = self.client.post(f"/api/v1/fiscal-periods/{self.period_alpha.id}/close/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.period_alpha.refresh_from_db()
        self.assertFalse(self.period_alpha.is_closed)

    def test_auditor_is_forbidden_from_closing_fiscal_period(self) -> None:
        """Auditors are strictly read-only and forbidden from mutating fiscal periods."""
        self._authenticate(self.auditor, self.org_alpha)
        response = self.client.post(f"/api/v1/fiscal-periods/{self.period_alpha.id}/close/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.period_alpha.refresh_from_db()
        self.assertFalse(self.period_alpha.is_closed)

    def test_closing_already_closed_period_returns_bad_request(self) -> None:
        """Attempting to close an already locked period returns HTTP 400 Bad Request."""
        self.period_alpha.close_period(self.owner)
        self._authenticate(self.owner, self.org_alpha)

        response = self.client.post(f"/api/v1/fiscal-periods/{self.period_alpha.id}/close/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already closed", response.json()["detail"])

    def test_cross_tenant_period_closing_is_blocked(self) -> None:
        """User in Org Alpha cannot close period belonging to Org Beta (returns 404)."""
        self._authenticate(self.owner, self.org_alpha)
        response = self.client.post(f"/api/v1/fiscal-periods/{self.period_beta.id}/close/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.period_beta.refresh_from_db()
        self.assertFalse(self.period_beta.is_closed)
