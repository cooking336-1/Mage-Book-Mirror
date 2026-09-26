"""REST API Views for Ghanaian Statutory Payroll Compilation, Maker-Checker Lifecycle,
and Step-Up TOTP 2FA.

Follows RESTful conventions:
- Collection resource: GET /api/v1/payroll/runs/ (List runs)
- Collection resource: POST /api/v1/payroll/runs/ (Draft new run)
- Member resource: GET /api/v1/payroll/runs/<pk>/ (Detail run)
- State transition: POST /api/v1/payroll/runs/<pk>/submit/ (Transition DRAFT -> PENDING_APPROVAL)
- State transition: POST /api/v1/payroll/runs/<pk>/approve/ (Step-up TOTP 2FA approval)
- 2FA Setup: GET /api/v1/payroll/2fa/setup/ & POST /api/v1/payroll/2fa/verify/
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ledger.models import FiscalPeriod
from apps.payroll.models import (
    PayrollRun,
    PayrollStatusChoices,
    PayrollTwoFactorProfile,
)
from apps.payroll.serializers import (
    PayrollApprovalSerializer,
    PayrollRunCreateSerializer,
    PayrollRunSerializer,
    PayrollTwoFactorEnrollSerializer,
)
from apps.payroll.services.approval_service import PayrollApprovalService
from apps.payroll.services.calculator import StatutoryPayrollEngine
from apps.payroll.services.totp_service import (
    generate_base32_secret,
    verify_totp_code,
)
from apps.tenancy.middleware import get_current_tenant
from apps.tenancy.models import Organization, RoleChoices
from apps.tenancy.permissions import CanApprovePayroll, HasTenantRole, IsAuditorReadOnly


def resolve_request_tenant(request: Request) -> Organization | None:
    """Safely extracts tenant organization from request object or thread-local storage."""
    if hasattr(request, "tenant") and request.tenant is not None:
        return request.tenant
    tenant = get_current_tenant()
    if tenant is not None:
        return tenant
    return None


def get_client_ip(request: Request) -> str | None:
    """Extracts client IP address handling forwarding proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class PayrollRunListCreateAPIView(APIView):
    """Collection resource: GET & POST /api/v1/payroll/runs/

    Drafting allowed for: OWNER, ADMIN, ACCOUNTANT, BOOKKEEPER.
    Auditors are strictly read-only.
    """

    permission_classes = [
        IsAuthenticated,
        IsAuditorReadOnly,
        HasTenantRole(
            RoleChoices.OWNER,
            RoleChoices.ADMIN,
            RoleChoices.ACCOUNTANT,
            RoleChoices.BOOKKEEPER,
            RoleChoices.AUDITOR,
        ),
    ]

    def get(self, request: Request) -> Response:
        """Lists tenant-isolated payroll runs."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = PayrollRun.objects.filter(organization=tenant).order_by("-created_at")
        status_param = request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        serializer = PayrollRunSerializer(queryset[:50], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        """Drafts a statutory payroll run and computes Ghanaian PAYE / SSNIT deductions."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PayrollRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        period = get_object_or_404(
            FiscalPeriod,
            id=validated["period_id"],
            organization=tenant,
        )
        if period.is_closed:
            return Response(
                {"detail": f"Fiscal period '{period.period_name}' is locked and closed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payroll_run = PayrollRun.objects.create(
            organization=tenant,
            period=period,
            maker=request.user,
            status=PayrollStatusChoices.DRAFT,
        )

        StatutoryPayrollEngine.compile_payroll_run(
            payroll_run=payroll_run,
            employees_data=validated["employees"],
        )

        output_serializer = PayrollRunSerializer(payroll_run)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class PayrollRunDetailAPIView(APIView):
    """Member resource: GET /api/v1/payroll/runs/<pk>/"""

    permission_classes = [
        IsAuthenticated,
        IsAuditorReadOnly,
        HasTenantRole(
            RoleChoices.OWNER,
            RoleChoices.ADMIN,
            RoleChoices.ACCOUNTANT,
            RoleChoices.BOOKKEEPER,
            RoleChoices.AUDITOR,
        ),
    ]

    def get(self, request: Request, pk: str) -> Response:
        """Retrieves details and line items of a specific payroll run."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payroll_run = get_object_or_404(PayrollRun, id=pk, organization=tenant)
        serializer = PayrollRunSerializer(payroll_run)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PayrollRunSubmitAPIView(APIView):
    """State transition resource: POST /api/v1/payroll/runs/<pk>/submit/

    Transitions a DRAFT payroll run into PENDING_APPROVAL.
    """

    permission_classes = [
        IsAuthenticated,
        IsAuditorReadOnly,
        HasTenantRole(
            RoleChoices.OWNER,
            RoleChoices.ADMIN,
            RoleChoices.ACCOUNTANT,
            RoleChoices.BOOKKEEPER,
        ),
    ]

    def post(self, request: Request, pk: str) -> Response:
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payroll_run = get_object_or_404(PayrollRun, id=pk, organization=tenant)
        if payroll_run.status != PayrollStatusChoices.DRAFT:
            msg = f"Only DRAFT runs can be submitted. Current status: '{payroll_run.status}'."
            return Response(
                {"detail": msg},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not payroll_run.items.exists():
            return Response(
                {
                    "detail": (
                        "Cannot submit empty payroll run. Must contain at least one employee line."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payroll_run.status = PayrollStatusChoices.PENDING_APPROVAL
        payroll_run.submitted_at = timezone.now()
        payroll_run.save(update_fields=["status", "submitted_at", "updated_at"])

        return Response(
            {
                "id": str(payroll_run.id),
                "status": payroll_run.status,
                "message": "Payroll run submitted for checker review and TOTP approval.",
            },
            status=status.HTTP_200_OK,
        )


class PayrollApprovalAPIView(APIView):
    """State transition resource: POST /api/v1/payroll/runs/<pk>/approve/

    Enforces:
    - Segregation of Duties: Permitted strictly for OWNER and ADMIN (CanApprovePayroll).
    - Misuse Case 5.1: Checker != Maker (Anti-Self-Approval Gate).
    - Misuse Case 5.2: Step-Up TOTP 2FA Verification, Single-Use Cache, and Mutex Lock.
    """

    permission_classes = [IsAuthenticated, CanApprovePayroll]

    def post(self, request: Request, pk: str) -> Response:
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PayrollApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        totp_code = serializer.validated_data["totp_code"]

        payroll_run = get_object_or_404(PayrollRun, id=pk, organization=tenant)

        try:
            approved_run = PayrollApprovalService.approve_payroll_run(
                payroll_run=payroll_run,
                checker=request.user,
                totp_code=totp_code,
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except PermissionDenied as exc:
            # MUC 5.1 Violation
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except (ValidationError, DjangoValidationError) as exc:
            msg = exc.message if hasattr(exc, "message") else str(exc)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PayrollRunSerializer(approved_run).data, status=status.HTTP_200_OK)


class PayrollTwoFactorSetupAPIView(APIView):
    """2FA Setup Resource: GET /api/v1/payroll/2fa/setup/

    Generates a new RFC 6238 Base32 secret for step-up authenticator pairing.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        secret = generate_base32_secret()
        # Save or update pending secret
        profile, _ = PayrollTwoFactorProfile.objects.get_or_create(user=request.user)
        profile.totp_secret = secret
        profile.is_enabled = False  # Disabled until verified
        profile.save()

        issuer = "MageBooks"
        otpauth_url = f"otpauth://totp/{issuer}:{request.user.email}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"

        return Response(
            {
                "secret": secret,
                "otpauth_url": otpauth_url,
                "instructions": "Scan QR code in Google Authenticator or enter base32 secret.",
            },
            status=status.HTTP_200_OK,
        )


class PayrollTwoFactorVerifyAPIView(APIView):
    """2FA Verification Resource: POST /api/v1/payroll/2fa/verify/

    Verifies a code and enables step-up 2FA for the user profile.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = PayrollTwoFactorEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["totp_code"]

        profile = PayrollTwoFactorProfile.objects.filter(user=request.user).first()
        if not profile or not profile.totp_secret:
            return Response(
                {"detail": "No pending TOTP secret found. Initiate setup first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not verify_totp_code(profile.totp_secret, code):
            return Response(
                {"detail": "Invalid verification code. Please check authenticator clock."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile.is_enabled = True
        profile.save()

        return Response(
            {"status": "SUCCESS", "message": "Two-Factor Authentication successfully activated."},
            status=status.HTTP_200_OK,
        )
