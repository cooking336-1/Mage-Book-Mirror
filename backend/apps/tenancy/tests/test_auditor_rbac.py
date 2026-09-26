"""Functional Unit Tests for Auditor RBAC and Segregation of Duties (SoD) Permissions.

Validates:
1. IsAuditorReadOnly: Permits safe methods (GET, HEAD, OPTIONS); rejects mutating methods with 403.
2. Ephemeral session expiration check: Rejects expired auditor sessions unconditionally.
3. Segregation of Duties policies:
   - CanCreateInvoice: Owner, Admin, Accountant, Bookkeeper (Auditor read-only).
   - CanIssueRefund: Owner, Admin, Accountant (Bookkeeper & Auditor forbidden).
   - CanApprovePayroll: Owner, Admin (Accountant, Bookkeeper, Auditor forbidden).
   - CanModifyMasterAccounts: Owner, Admin, Accountant (Bookkeeper & Auditor forbidden).
   - CanCloseFiscalPeriod: Owner, Accountant (Admin, Bookkeeper, Auditor forbidden).
"""

import datetime
from unittest.mock import MagicMock

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.authentication.models import CustomUser
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices
from apps.tenancy.permissions import (
    CanApprovePayroll,
    CanCloseFiscalPeriod,
    CanCreateInvoice,
    CanIssueRefund,
    CanModifyMasterAccounts,
    HasTenantRole,
    IsAuditorReadOnly,
)


class AuditorRBACPermissionsTestCase(TestCase):
    """Verifies RBAC and SoD permission classes."""

    def setUp(self) -> None:
        self.org = Organization.objects.create(
            name="Apex Ghana Ltd",
            phone="+233240000001",
            email="info@apex.gh",
        )
        self.user = CustomUser.objects.create_user(
            email="auditor@pwc.com",
            password="StrongAuditorPass2026!",
            first_name="Kwesi",
            last_name="Auditor",
        )
        self.future_expiry = timezone.now() + datetime.timedelta(days=30)
        self.past_expiry = timezone.now() - datetime.timedelta(days=1)

        self.auditor_membership = OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=RoleChoices.AUDITOR,
            access_expires_at=self.future_expiry,
        )

    def _create_mock_request(
        self,
        method: str = "GET",
        role: str = RoleChoices.AUDITOR,
        membership: OrganizationMembership | None = None,
    ) -> MagicMock:
        request = MagicMock()
        request.method = method
        request.tenant = self.org
        request.tenant_role = role
        request.membership = membership or self.auditor_membership
        request.user = self.user
        return request

    def test_is_auditor_read_only_permits_safe_methods_for_active_auditor(self) -> None:
        """Auditor can execute GET, HEAD, OPTIONS when session is active."""
        perm = IsAuditorReadOnly()

        for method in ("GET", "HEAD", "OPTIONS"):
            req = self._create_mock_request(method=method)
            self.assertTrue(
                perm.has_permission(req, None),
                f"Failed for safe method: {method}",
            )

    def test_is_auditor_read_only_blocks_mutating_methods(self) -> None:
        """Auditor attempting POST, PUT, PATCH, DELETE raises PermissionDenied."""
        perm = IsAuditorReadOnly()

        for method in ("POST", "PUT", "PATCH", "DELETE"):
            req = self._create_mock_request(method=method)
            with self.assertRaises(PermissionDenied) as ctx:
                perm.has_permission(req, None)
            self.assertIn("Auditor role has strictly read-only access", str(ctx.exception))

    def test_is_auditor_read_only_rejects_expired_session_even_on_get(self) -> None:
        """Expired auditor membership raises PermissionDenied on any method including GET."""
        perm = IsAuditorReadOnly()
        self.auditor_membership.access_expires_at = self.past_expiry
        self.auditor_membership.save(update_fields=["access_expires_at"])

        req = self._create_mock_request(method="GET", membership=self.auditor_membership)
        with self.assertRaises(PermissionDenied) as ctx:
            perm.has_permission(req, None)
        self.assertIn("Auditor access has expired", str(ctx.exception))

    def test_has_tenant_role_validator(self) -> None:
        """HasTenantRole strictly verifies membership role."""
        perm = HasTenantRole(RoleChoices.OWNER, RoleChoices.ADMIN)

        req_owner = self._create_mock_request(role=RoleChoices.OWNER)
        self.assertTrue(perm.has_permission(req_owner, None))

        req_accountant = self._create_mock_request(role=RoleChoices.ACCOUNTANT)
        with self.assertRaises(PermissionDenied):
            perm.has_permission(req_accountant, None)

    def test_can_create_invoice_sod_policy(self) -> None:
        """CanCreateInvoice permits creation for standard roles; blocks Auditor."""
        perm = CanCreateInvoice()

        # Permitted roles
        for role in (
            RoleChoices.OWNER,
            RoleChoices.ADMIN,
            RoleChoices.ACCOUNTANT,
            RoleChoices.BOOKKEEPER,
        ):
            req = self._create_mock_request(method="POST", role=role)
            self.assertTrue(perm.has_permission(req, None), f"Failed for {role}")

        # Auditor write is blocked
        req_auditor = self._create_mock_request(method="POST", role=RoleChoices.AUDITOR)
        with self.assertRaises(PermissionDenied):
            perm.has_permission(req_auditor, None)

        # Auditor read is permitted
        req_auditor_read = self._create_mock_request(method="GET", role=RoleChoices.AUDITOR)
        self.assertTrue(perm.has_permission(req_auditor_read, None))

    def test_can_issue_refund_sod_policy(self) -> None:
        """CanIssueRefund allows Owner, Admin, Accountant; blocks Bookkeeper and Auditor."""
        perm = CanIssueRefund()

        for role in (RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.ACCOUNTANT):
            req = self._create_mock_request(method="POST", role=role)
            self.assertTrue(perm.has_permission(req, None))

        for role in (RoleChoices.BOOKKEEPER, RoleChoices.AUDITOR):
            req = self._create_mock_request(method="POST", role=role)
            with self.assertRaises(PermissionDenied):
                perm.has_permission(req, None)

    def test_can_approve_payroll_sod_policy(self) -> None:
        """CanApprovePayroll allows only Owner and Admin; blocks Accountant, Bookkeeper, Auditor."""
        perm = CanApprovePayroll()

        for role in (RoleChoices.OWNER, RoleChoices.ADMIN):
            req = self._create_mock_request(method="POST", role=role)
            self.assertTrue(perm.has_permission(req, None))

        for role in (RoleChoices.ACCOUNTANT, RoleChoices.BOOKKEEPER, RoleChoices.AUDITOR):
            req = self._create_mock_request(method="POST", role=role)
            with self.assertRaises(PermissionDenied):
                perm.has_permission(req, None)

    def test_can_modify_master_accounts_sod_policy(self) -> None:
        """CanModifyMasterAccounts allows Owner, Admin, Accountant; blocks Bookkeeper, Auditor."""
        perm = CanModifyMasterAccounts()

        for role in (RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.ACCOUNTANT):
            req = self._create_mock_request(method="POST", role=role)
            self.assertTrue(perm.has_permission(req, None))

        for role in (RoleChoices.BOOKKEEPER, RoleChoices.AUDITOR):
            req = self._create_mock_request(method="POST", role=role)
            with self.assertRaises(PermissionDenied):
                perm.has_permission(req, None)

    def test_can_close_fiscal_period_sod_policy(self) -> None:
        """CanCloseFiscalPeriod allows Owner, Accountant; blocks Admin, Bookkeeper, Auditor."""
        perm = CanCloseFiscalPeriod()

        for role in (RoleChoices.OWNER, RoleChoices.ACCOUNTANT):
            req = self._create_mock_request(method="POST", role=role)
            self.assertTrue(perm.has_permission(req, None))

        for role in (RoleChoices.ADMIN, RoleChoices.BOOKKEEPER, RoleChoices.AUDITOR):
            req = self._create_mock_request(method="POST", role=role)
            with self.assertRaises(PermissionDenied):
                perm.has_permission(req, None)
