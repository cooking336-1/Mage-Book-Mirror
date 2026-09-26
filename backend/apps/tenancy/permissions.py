"""Role-Based Access Control (RBAC) and Segregation of Duties (SoD) permissions.

Enforces:
1. Strict read-only containment for the AUDITOR role (GET/HEAD/OPTIONS only).
2. Ephemeral auditor access window validation (rejecting expired sessions).
3. Segregation of Duties (SoD) policies as defined in Architecture Manual 4.6.1 & 4.6.3:
   - CanCreateInvoice: Allowed for OWNER, ADMIN, ACCOUNTANT, BOOKKEEPER.
   - CanIssueRefund: Allowed for OWNER, ADMIN, ACCOUNTANT. Forbidden for BOOKKEEPER, AUDITOR.
   - CanApprovePayroll: Allowed for OWNER, ADMIN. Forbidden for ACCOUNTANT, BOOKKEEPER, AUDITOR.
   - CanModifyMasterAccounts: Allowed for OWNER, ADMIN, ACCOUNTANT.
   - CanCloseFiscalPeriod: Allowed for OWNER, ACCOUNTANT.
"""

from typing import Any

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.tenancy.models import RoleChoices


class IsAuditorReadOnly(BasePermission):
    """Enforces strict read-only containment for external auditors.

    - Permitted: GET, HEAD, OPTIONS.
    - Forbidden: POST, PUT, PATCH, DELETE.
    - Validates that active auditor sessions have not passed access_expires_at.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        role = getattr(request, "tenant_role", None)
        membership = getattr(request, "membership", None)

        if role == RoleChoices.AUDITOR:
            # Ephemeral auditor session expiration check
            if membership and membership.is_expired():
                raise PermissionDenied("Auditor access has expired for this organization.")

            # Block all mutating HTTP methods
            if request.method not in SAFE_METHODS:
                raise PermissionDenied("Auditor role has strictly read-only access.")

        return True


class HasTenantRole(BasePermission):
    """Dynamic role-based permission validator.

    Requires request.tenant_role to be within the allowed_roles set.
    """

    allowed_roles: tuple[str, ...] = ()

    def __init__(self, *roles: str) -> None:
        if roles:
            self.allowed_roles = roles

    def has_permission(self, request: Any, view: Any) -> bool:
        role = getattr(request, "tenant_role", None)
        membership = getattr(request, "membership", None)

        # Expired auditor memberships are unconditionally denied
        if role == RoleChoices.AUDITOR and membership and membership.is_expired():
            raise PermissionDenied("Auditor access has expired for this organization.")

        if role not in self.allowed_roles:
            raise PermissionDenied(
                f"Your role '{role}' is not authorized to perform this operation."
            )
        return True


class CanCreateInvoice(BasePermission):
    """Invoice creation permission (Segregation of Duties).

    Permitted for Owner, Admin, Accountant, Bookkeeper/Cashier.
    Strictly read-only for External Auditor.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True

        role = getattr(request, "tenant_role", None)
        membership = getattr(request, "membership", None)

        if role == RoleChoices.AUDITOR:
            if membership and membership.is_expired():
                raise PermissionDenied("Auditor access has expired for this organization.")
            raise PermissionDenied("Auditor role has strictly read-only access.")

        if role not in (
            RoleChoices.OWNER,
            RoleChoices.ADMIN,
            RoleChoices.ACCOUNTANT,
            RoleChoices.BOOKKEEPER,
        ):
            raise PermissionDenied("You do not have permission to create invoices.")
        return True


class CanIssueRefund(BasePermission):
    """Refunds and Credit Notes permission (Architecture Manual 4.6.1).

    Strictly FORBIDDEN for Bookkeepers and Auditors.
    Requires Accountant, Admin, or Owner privilege to prevent unauthorized cash drawdowns.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        role = getattr(request, "tenant_role", None)
        membership = getattr(request, "membership", None)

        if role == RoleChoices.AUDITOR and membership and membership.is_expired():
            raise PermissionDenied("Auditor access has expired for this organization.")

        if role in (RoleChoices.BOOKKEEPER, RoleChoices.AUDITOR):
            raise PermissionDenied(
                "Segregation of duties prohibits data entry staff "
                "and auditors from issuing refunds."
            )
        if role not in (RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.ACCOUNTANT):
            raise PermissionDenied("Only an Accountant, Admin, or Owner can authorize refunds.")
        return True


class CanApprovePayroll(BasePermission):
    """Payroll Approval and Bulk Payout permission (Architecture Manual 4.6.1 & 4.6.3).

    Strictly FORBIDDEN for Bookkeepers, Auditors, and Accountants.
    Requires Admin or Owner sign-off.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        role = getattr(request, "tenant_role", None)
        membership = getattr(request, "membership", None)

        if role == RoleChoices.AUDITOR and membership and membership.is_expired():
            raise PermissionDenied("Auditor access has expired for this organization.")

        if role not in (RoleChoices.OWNER, RoleChoices.ADMIN):
            raise PermissionDenied(
                "Only an Organization Owner or Admin can authorize payroll disbursements."
            )
        return True


class CanModifyMasterAccounts(BasePermission):
    """Chart of Accounts Modification permission (Architecture Manual 4.6.1).

    Strictly FORBIDDEN for Bookkeepers and Auditors.
    Only Accountants, Admins, and Owners can alter master general ledger accounts.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True

        role = getattr(request, "tenant_role", None)
        membership = getattr(request, "membership", None)

        if role == RoleChoices.AUDITOR:
            if membership and membership.is_expired():
                raise PermissionDenied("Auditor access has expired for this organization.")
            raise PermissionDenied("Auditor role has strictly read-only access.")

        if role not in (RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.ACCOUNTANT):
            raise PermissionDenied(
                "Only an Accountant, Admin, or Owner can create or modify master accounts."
            )
        return True


class CanCloseFiscalPeriod(BasePermission):
    """Fiscal Period Closing and GRA Declarations permission (Architecture Manual 4.6.1).

    Strictly FORBIDDEN for Admins, Bookkeepers, and Auditors.
    Only the certified Accountant and Owner can officially declare VAT and close tax periods.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        role = getattr(request, "tenant_role", None)
        membership = getattr(request, "membership", None)

        if role == RoleChoices.AUDITOR and membership and membership.is_expired():
            raise PermissionDenied("Auditor access has expired for this organization.")

        if role not in (RoleChoices.OWNER, RoleChoices.ACCOUNTANT):
            raise PermissionDenied(
                "Only the certified Accountant or Owner can close fiscal periods or declare VAT."
            )
        return True
