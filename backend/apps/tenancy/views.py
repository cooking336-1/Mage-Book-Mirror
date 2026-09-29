"""REST API Views for Tenancy, Team Member Management, and Financial Governance."""

import logging
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditTrail
from apps.authentication.models import CustomUser
from apps.ledger.models import FiscalCalendar, PeriodLengthChoices
from apps.ledger.services.seeder import generate_fiscal_periods, seed_standard_chart_of_accounts
from apps.payroll.models import PayrollTwoFactorProfile
from apps.payroll.services.totp_service import consume_totp_token, verify_totp_code
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices
from apps.tenancy.permissions import HasTenantRole, IsAuditorReadOnly
from apps.tenancy.serializers import (
    OrganizationCreateSerializer,
    OrganizationDetailSerializer,
    OrganizationMembershipCreateSerializer,
    OrganizationMembershipSerializer,
    OrganizationMembershipUpdateSerializer,
    OrganizationSettlementSerializer,
)

logger = logging.getLogger(__name__)


class TenantContextTestView(APIView):
    """Test verification endpoint that returns the resolved tenant context.

    Protected by TenantSecurityMiddleware and IsAuthenticated.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Returns the active tenant ID, name, and user's role within the tenant."""
        tenant = getattr(request, "tenant", None)
        tenant_role = getattr(request, "tenant_role", None)

        if not tenant:
            return Response(
                {"detail": "No tenant context resolved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "tenant_id": str(tenant.id),
                "tenant_name": tenant.name,
                "tenant_role": tenant_role,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Mutating endpoint for testing auditor write containment and authorized writes."""
        tenant = getattr(request, "tenant", None)
        return Response(
            {
                "status": "success",
                "tenant_id": str(tenant.id) if tenant else None,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================================
# TEAM MEMBER MANAGEMENT & OWNER IMMUTABILITY
# ============================================================================
class OrganizationMemberListCreateAPIView(APIView):
    """Resource collection for tenant team members: /api/v1/tenancy/members/

    - GET: List organization members (All authenticated tenant roles; Auditor read-only).
    - POST: Invite or add a new team member (OWNER and ADMIN only).
    """

    def get_permissions(self) -> list[Any]:
        if self.request.method == "POST":
            return [IsAuthenticated(), HasTenantRole(RoleChoices.OWNER, RoleChoices.ADMIN)()]
        return [IsAuthenticated(), IsAuditorReadOnly()]

    def get(self, request: Request) -> Response:
        """Returns ordered list of team members for active organization."""
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        memberships = (
            OrganizationMembership.objects.filter(organization=tenant)
            .select_related("user")
            .order_by("role", "-created_at")
        )
        serializer = OrganizationMembershipSerializer(memberships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        """Adds or invites a new member into the organization."""
        tenant = getattr(request, "tenant", None)
        caller_role = getattr(request, "tenant_role", None)

        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrganizationMembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        target_role = data.get("role", RoleChoices.BOOKKEEPER)
        target_email = data["email"].strip().lower()

        # Owner Immutability Guardrail 1: Admins cannot grant OWNER role
        if caller_role == RoleChoices.ADMIN and target_role == RoleChoices.OWNER:
            logger.warning(
                "Rogue Manager attempt blocked: Admin user=%s tried to assign OWNER role in org=%s",
                request.user.id,
                tenant.id,
            )
            raise PermissionDenied("Admins cannot assign the Organization Owner role.")

        user = CustomUser.objects.filter(email=target_email).first()
        if not user:
            user = CustomUser.objects.create_user(
                email=target_email,
                password=None,
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
            )

        if OrganizationMembership.objects.filter(organization=tenant, user=user).exists():
            return Response(
                {"detail": f"User '{target_email}' is already a member of this organization."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = OrganizationMembership(
            organization=tenant,
            user=user,
            role=target_role,
            access_expires_at=data.get("access_expires_at"),
            is_active=True,
        )
        try:
            membership.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc

        AuditTrail.objects.create(
            organization=tenant,
            user=request.user,
            action="TEAM_MEMBER_ADDED",
            entity_type="OrganizationMembership",
            entity_id=str(membership.id),
            metadata={
                "member_email": user.email,
                "role": membership.role,
                "added_by_role": caller_role,
            },
        )

        return Response(
            OrganizationMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationMemberDetailAPIView(APIView):
    """Member resource for updating role/status or removing a member:
    /api/v1/tenancy/members/<uuid:pk>/

    - GET: Retrieve member details.
    - PATCH: Update member role, active status, or expiration timestamp.
    - DELETE: Remove member from the organization.
    """

    def get_permissions(self) -> list[Any]:
        if self.request.method in ("PATCH", "DELETE"):
            return [IsAuthenticated(), HasTenantRole(RoleChoices.OWNER, RoleChoices.ADMIN)()]
        return [IsAuthenticated(), IsAuditorReadOnly()]

    def get(self, request: Request, pk: Any) -> Response:
        """Retrieves details of a specific organization member."""
        tenant = getattr(request, "tenant", None)
        membership = get_object_or_404(
            OrganizationMembership.objects.select_related("user"),
            id=pk,
            organization=tenant,
        )
        return Response(
            OrganizationMembershipSerializer(membership).data, status=status.HTTP_200_OK
        )

    def patch(self, request: Request, pk: Any) -> Response:
        """Updates role or active status of a team member enforcing Owner Immutability."""
        tenant = getattr(request, "tenant", None)
        caller_role = getattr(request, "tenant_role", None)

        membership = get_object_or_404(
            OrganizationMembership.objects.select_related("user"),
            id=pk,
            organization=tenant,
        )

        # ------------------------------------------------------------------
        # GUARD 1: Owner Immutability against Admin (Arch Manual 4.6.2)
        # ------------------------------------------------------------------
        if membership.role == RoleChoices.OWNER and caller_role == RoleChoices.ADMIN:
            logger.warning(
                "Rogue Manager attempt blocked: Admin user=%s tried to modify OWNER in org=%s",
                request.user.id,
                tenant.id,
            )
            raise PermissionDenied(
                "Admins cannot modify, demote, or deactivate an Organization Owner."
            )

        serializer = OrganizationMembershipUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        new_role = data.get("role", membership.role)
        is_active = data.get("is_active", membership.is_active)

        # Guard 2: Admin cannot promote anyone to OWNER
        if caller_role == RoleChoices.ADMIN and new_role == RoleChoices.OWNER:
            raise PermissionDenied("Admins cannot promote members to Organization Owner.")

        # Guard 3: Sole Owner protection (Owner cannot demote or deactivate sole owner)
        if membership.role == RoleChoices.OWNER:
            owner_count = OrganizationMembership.objects.filter(
                organization=tenant, role=RoleChoices.OWNER, is_active=True
            ).count()
            if owner_count <= 1:
                if new_role != RoleChoices.OWNER:
                    raise ValidationError(
                        {"role": "Cannot demote the sole active Organization Owner."}
                    )
                if is_active is False:
                    raise ValidationError(
                        {"is_active": "Cannot deactivate the sole active Organization Owner."}
                    )

        if "role" in data:
            membership.role = data["role"]
        if "is_active" in data:
            membership.is_active = data["is_active"]
        if "access_expires_at" in data:
            membership.access_expires_at = data["access_expires_at"]

        try:
            membership.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc

        AuditTrail.objects.create(
            organization=tenant,
            user=request.user,
            action="TEAM_MEMBER_UPDATED",
            entity_type="OrganizationMembership",
            entity_id=str(membership.id),
            metadata={
                "member_email": membership.user.email,
                "updated_role": membership.role,
                "is_active": membership.is_active,
            },
        )

        return Response(
            OrganizationMembershipSerializer(membership).data, status=status.HTTP_200_OK
        )

    def delete(self, request: Request, pk: Any) -> Response:
        """Removes a team member from the organization enforcing Owner Immutability."""
        tenant = getattr(request, "tenant", None)
        caller_role = getattr(request, "tenant_role", None)

        membership = get_object_or_404(
            OrganizationMembership.objects.select_related("user"),
            id=pk,
            organization=tenant,
        )

        # Owner Immutability Guard: Admin cannot delete an Owner
        if membership.role == RoleChoices.OWNER and caller_role == RoleChoices.ADMIN:
            logger.warning(
                "Rogue Manager attempt blocked: Admin user=%s tried to delete OWNER in org=%s",
                request.user.id,
                tenant.id,
            )
            raise PermissionDenied("Admins cannot remove an Organization Owner.")

        # Sole Owner removal protection
        if membership.role == RoleChoices.OWNER:
            owner_count = OrganizationMembership.objects.filter(
                organization=tenant, role=RoleChoices.OWNER
            ).count()
            if owner_count <= 1:
                raise ValidationError({"detail": "Cannot remove the sole Organization Owner."})

        member_email = membership.user.email
        membership_id = str(membership.id)
        membership.delete()

        AuditTrail.objects.create(
            organization=tenant,
            user=request.user,
            action="TEAM_MEMBER_REMOVED",
            entity_type="OrganizationMembership",
            entity_id=membership_id,
            metadata={"member_email": member_email, "removed_by_role": caller_role},
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# FINANCIAL DESTINATION LOCKS (PAYOUT ACCOUNTS & MOMO WALLETS)
# ============================================================================
class OrganizationSettlementAPIView(APIView):
    """Manages organization settlement coordinates (Bank Account & Mobile Money Wallet).

    - GET: Retrieve current settlement coordinates.
    - PATCH: Update settlement destinations.
      * OWNER: Permitted directly.
      * ADMIN: Requires Owner step-up TOTP 2FA code ('owner_totp_code') to prevent rerouting.
      * Other roles: HTTP 403 Forbidden.
    """

    permission_classes = [
        IsAuthenticated,
        HasTenantRole(RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.ACCOUNTANT),
    ]

    def get(self, request: Request) -> Response:
        """Returns settlement bank and MoMo coordinates for the active organization."""
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrganizationSettlementSerializer(tenant)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request: Request) -> Response:
        """Updates settlement coordinates with mandatory Owner Step-up OTP challenge for Admins."""
        tenant = getattr(request, "tenant", None)
        caller_role = getattr(request, "tenant_role", None)

        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if caller_role not in (RoleChoices.OWNER, RoleChoices.ADMIN):
            raise PermissionDenied(
                "Only an Organization Owner or Admin can update settlement settings."
            )

        serializer = OrganizationSettlementSerializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # ------------------------------------------------------------------
        # FINANCIAL DESTINATION LOCK: Mandatory Owner TOTP challenge for Admin
        # ------------------------------------------------------------------
        if caller_role == RoleChoices.ADMIN:
            owner_user = tenant.owner
            if not owner_user:
                raise PermissionDenied(
                    "Organization has no active Owner to authorize settlement modifications."
                )

            two_factor_profile = PayrollTwoFactorProfile.objects.filter(
                user=owner_user, is_enabled=True
            ).first()
            if not two_factor_profile:
                msg = (
                    "Organization Owner has not enrolled in Step-Up 2FA. "
                    "Settlement modifications by Admin require an enrolled Owner profile."
                )
                raise ValidationError({"owner_totp_code": msg})

            totp_code = data.get("owner_totp_code", "").strip()
            if not totp_code:
                msg = (
                    "Mandatory Owner Step-up TOTP code is required for Admins "
                    "modifying settlement destinations."
                )
                raise ValidationError({"owner_totp_code": msg})

            # Replay protection and code verification
            if not consume_totp_token(owner_user.id, totp_code):
                logger.warning(
                    "Rogue Manager attempt blocked: Admin user=%s replayed TOTP in org=%s",
                    request.user.id,
                    tenant.id,
                )
                raise PermissionDenied(
                    "TOTP token has already been consumed. Please generate a fresh code."
                )

            if not verify_totp_code(two_factor_profile.totp_secret, totp_code):
                logger.warning(
                    "Rogue Manager attempt blocked: Admin user=%s invalid TOTP in org=%s",
                    request.user.id,
                    tenant.id,
                )
                raise PermissionDenied("Invalid Owner TOTP authorization code.")

        if "settlement_bank_name" in data:
            tenant.settlement_bank_name = data["settlement_bank_name"]
        if "settlement_account_number" in data:
            tenant.settlement_account_number = data["settlement_account_number"]
        if "settlement_momo_number" in data:
            tenant.settlement_momo_number = data["settlement_momo_number"]

        tenant.settlement_locked_at = timezone.now()
        tenant.save(
            update_fields=[
                "settlement_bank_name",
                "settlement_account_number",
                "settlement_momo_number",
                "settlement_locked_at",
                "updated_at",
            ]
        )

        AuditTrail.objects.create(
            organization=tenant,
            user=request.user,
            action="SETTLEMENT_DESTINATIONS_UPDATED",
            entity_type="Organization",
            entity_id=str(tenant.id),
            metadata={
                "bank_name": tenant.settlement_bank_name,
                "account_number": tenant.settlement_account_number,
                "momo_number": tenant.settlement_momo_number,
                "modified_by_role": caller_role,
            },
        )

        return Response(OrganizationSettlementSerializer(tenant).data, status=status.HTTP_200_OK)


# ============================================================================
# SOLE DESTROYER: SOFT-ARCHIVAL DEACTIVATION (ACT 896 6-YEAR RETENTION)
# ============================================================================
class OrganizationDeactivationAPIView(APIView):
    """Endpoint for terminating and soft-archiving an organization workspace:
    DELETE /api/v1/tenancy/organizations/current/

    Architecture Manual 4.6.2: Sole Destroyer Rule
    - Strictly FORBIDDEN for Admins and all non-owners (HTTP 403 Forbidden).
    - Permitted exclusively to the primary Organization OWNER.
    - Soft-deactivates the organization preserving statutory general ledger and invoice
      records for the mandatory 6-year retention period under Ghanaian tax law.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request) -> Response:
        """Soft-deactivates the organization workspace strictly for the primary Owner."""
        tenant = getattr(request, "tenant", None)
        caller_role = getattr(request, "tenant_role", None)

        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sole Destroyer Rule check
        if caller_role != RoleChoices.OWNER:
            logger.warning(
                "Sole Destroyer Rule Violation: user=%s (role=%s) tried to delete org=%s",
                request.user.id,
                caller_role,
                tenant.id,
            )
            raise PermissionDenied(
                "Sole Destroyer Rule: Only primary Organization Owner can initiate deactivation."
            )

        tenant.is_active = False
        tenant.save(update_fields=["is_active", "updated_at"])

        AuditTrail.objects.create(
            organization=tenant,
            user=request.user,
            action="ORGANIZATION_DEACTIVATED",
            entity_type="Organization",
            entity_id=str(tenant.id),
            metadata={"organization_name": tenant.name, "initiated_by": request.user.email},
        )

        return Response(
            {
                "detail": (
                    f"Organization '{tenant.name}' has been successfully archived. "
                    "Statutory financial records have been sealed for audit retention."
                )
            },
            status=status.HTTP_200_OK,
        )


class OrganizationCreateAPIView(generics.ListCreateAPIView):
    """Exposes POST /api/v1/tenancy/organizations/ for provisioning new tenants

    with atomic Ghanaian Chart of Accounts seeding and fiscal periods,
    and GET /api/v1/tenancy/organizations/ for listing active tenant memberships.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrganizationCreateSerializer
        return OrganizationDetailSerializer

    def get_queryset(self):
        return Organization.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True,
        ).distinct()

    def perform_create(self, serializer: OrganizationCreateSerializer) -> None:
        user = self.request.user
        validated_data = serializer.validated_data

        # Fallback defaults for email / phone from user profile if blank
        if not validated_data.get("email"):
            serializer.validated_data["email"] = user.email
        if not validated_data.get("phone"):
            user_phone = getattr(user, "phone_number", "")
            serializer.validated_data["phone"] = user_phone or "+233000000000"

        period_length_str = serializer.context.get("tax_period_length", "monthly")
        period_length = (
            PeriodLengthChoices.QUARTERLY
            if period_length_str == "quarterly"
            else PeriodLengthChoices.MONTHLY
        )

        with transaction.atomic():
            org = serializer.save()

            # 1. Bind creator with OWNER role
            OrganizationMembership.objects.create(
                organization=org,
                user=user,
                role=RoleChoices.OWNER,
                is_active=True,
            )

            # 2. Bootstrap default standard Ghanaian Chart of Accounts (>=33 accounts)
            seed_standard_chart_of_accounts(org)

            # 3. Create FiscalCalendar and generate fiscal periods
            calendar_inst, _ = FiscalCalendar.objects.get_or_create(
                organization=org,
                defaults={
                    "period_length": period_length,
                    "fiscal_year_end_month": 12,
                    "fiscal_year_end_day": 31,
                },
            )
            generate_fiscal_periods(
                organization=org,
                year=timezone.now().year,
                calendar_instance=calendar_inst,
            )
