"""REST API Views for General Ledger, Master Accounts, and Financial Reports.

Implements pure RESTful resource conventions:
1. Noun-based collections and member endpoints (/accounts/, /journal-entries/).
2. Hierarchical containment (/accounts/{id}/entries/).
3. Query string filtering for criteria (/reports/trial-balance/?as_of_date=...).
4. Protected by IsAuthenticated and IsAuditorReadOnly.
"""

import datetime
from typing import Any

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditTrail
from apps.ledger.models import ChartOfAccounts, FiscalPeriod, JournalEntry, JournalLine
from apps.ledger.selectors import (
    get_balance_sheet,
    get_profit_and_loss,
    get_trial_balance,
)
from apps.tenancy.middleware import get_current_tenant
from apps.tenancy.models import Organization
from apps.tenancy.permissions import CanCloseFiscalPeriod, IsAuditorReadOnly


def resolve_request_tenant(request: Request) -> Organization | None:
    """Helper to extract active tenant organization from request or thread context."""
    tenant = getattr(request, "tenant", None)
    if not tenant:
        tenant = getattr(request, "organization", None)
    if not tenant:
        tenant = get_current_tenant()
    return tenant


def parse_date(date_str: str | None, default: datetime.date | None = None) -> datetime.date | None:
    """Safely parses YYYY-MM-DD string or returns default."""
    if not date_str:
        return default
    try:
        return datetime.date.fromisoformat(date_str.strip())
    except (ValueError, AttributeError):
        return default


# ============================================================================
# MASTER CHART OF ACCOUNTS RESOURCES
# ============================================================================
class AccountListAPIView(APIView):
    """Resource collection for tenant master chart of accounts: GET /api/v1/accounts/"""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request) -> Response:
        """Returns ordered list of chart of accounts for the active tenant."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        accounts = (
            ChartOfAccounts.objects.filter(organization=tenant)
            .select_related("category")
            .order_by("account_code")
        )

        data = [
            {
                "id": str(acc.id),
                "account_code": acc.account_code,
                "account_name": acc.account_name,
                "simple_label": acc.simple_label,
                "category_code": acc.category.code if acc.category else None,
                "category_name": acc.category.name if acc.category else None,
                "normal_balance": acc.category.normal_balance if acc.category else None,
                "is_active": acc.is_active,
            }
            for acc in accounts
        ]
        return Response(data, status=status.HTTP_200_OK)


class AccountDetailAPIView(APIView):
    """Member resource for a single chart of accounts item: GET /api/v1/accounts/<uuid:pk>/"""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request, pk: Any) -> Response:
        """Retrieves details of a specific account."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        acc = (
            ChartOfAccounts.objects.filter(id=pk, organization=tenant)
            .select_related("category")
            .first()
        )
        if not acc:
            return Response({"detail": "Account not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "id": str(acc.id),
                "account_code": acc.account_code,
                "account_name": acc.account_name,
                "simple_label": acc.simple_label,
                "category_code": acc.category.code if acc.category else None,
                "category_name": acc.category.name if acc.category else None,
                "normal_balance": acc.category.normal_balance if acc.category else None,
                "is_active": acc.is_active,
            },
            status=status.HTTP_200_OK,
        )


class AccountJournalLineListAPIView(APIView):
    """Hierarchical containment: GET /api/v1/accounts/<uuid:account_id>/entries/"""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request, account_id: Any) -> Response:
        """Returns all posted journal lines belonging to this account within the tenant."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lines = (
            JournalLine.objects.filter(
                organization=tenant,
                account_id=account_id,
                journal_entry__is_posted=True,
            )
            .select_related("journal_entry")
            .order_by("-journal_entry__entry_date", "-created_at")
        )

        data = [
            {
                "id": str(line.id),
                "journal_entry_id": str(line.journal_entry.id),
                "entry_number": line.journal_entry.entry_number,
                "entry_date": line.journal_entry.entry_date.isoformat(),
                "description": line.description,
                "debit_amount": str(line.debit_amount),
                "credit_amount": str(line.credit_amount),
            }
            for line in lines
        ]
        return Response(data, status=status.HTTP_200_OK)


# ============================================================================
# GENERAL LEDGER JOURNAL ENTRIES
# ============================================================================
class JournalEntryListAPIView(APIView):
    """Collection resource for journal entries: GET /api/v1/journal-entries/"""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request) -> Response:
        """Returns tenant journal entries with optional date filtering."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = JournalEntry.objects.filter(organization=tenant).prefetch_related("lines__account")

        start_date = parse_date(request.query_params.get("start_date"))
        end_date = parse_date(request.query_params.get("end_date"))
        if start_date:
            qs = qs.filter(entry_date__gte=start_date)
        if end_date:
            qs = qs.filter(entry_date__lte=end_date)

        entries = qs.order_by("-entry_date", "-created_at")[:100]

        data = [
            {
                "id": str(entry.id),
                "entry_number": entry.entry_number,
                "entry_date": entry.entry_date.isoformat(),
                "narration": entry.narration,
                "source_type": entry.source_type,
                "is_posted": entry.is_posted,
                "lines": [
                    {
                        "id": str(line.id),
                        "account_code": line.account.account_code,
                        "account_name": line.account.account_name,
                        "description": line.description,
                        "debit_amount": str(line.debit_amount),
                        "credit_amount": str(line.credit_amount),
                    }
                    for line in entry.lines.all()
                ],
            }
            for entry in entries
        ]
        return Response(data, status=status.HTTP_200_OK)


class JournalEntryDetailAPIView(APIView):
    """Member resource for a single journal entry: GET /api/v1/journal-entries/<uuid:pk>/"""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request, pk: Any) -> Response:
        """Retrieves single journal entry with its lines."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry = (
            JournalEntry.objects.filter(id=pk, organization=tenant)
            .prefetch_related("lines__account")
            .first()
        )
        if not entry:
            return Response(
                {"detail": "Journal entry not found."}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "id": str(entry.id),
                "entry_number": entry.entry_number,
                "entry_date": entry.entry_date.isoformat(),
                "narration": entry.narration,
                "source_type": entry.source_type,
                "is_posted": entry.is_posted,
                "lines": [
                    {
                        "id": str(line.id),
                        "account_code": line.account.account_code,
                        "account_name": line.account.account_name,
                        "description": line.description,
                        "debit_amount": str(line.debit_amount),
                        "credit_amount": str(line.credit_amount),
                    }
                    for line in entry.lines.all()
                ],
            },
            status=status.HTTP_200_OK,
        )


# ============================================================================
# FINANCIAL STATEMENT & REPORT RESOURCES
# ============================================================================
class TrialBalanceReportAPIView(APIView):
    """Informational report resource: GET /api/v1/reports/trial-balance/?as_of_date=YYYY-MM-DD"""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request) -> Response:
        """Computes and returns real-time Trial Balance report."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        as_of_date = parse_date(request.query_params.get("as_of_date"))
        include_zeros = request.query_params.get("include_zero_balances", "false").lower() == "true"

        report = get_trial_balance(
            organization=tenant,
            as_of_date=as_of_date,
            include_zero_balances=include_zeros,
        )
        return Response(report.to_dict(), status=status.HTTP_200_OK)


class ProfitAndLossReportAPIView(APIView):
    """Informational report resource: GET /api/v1/reports/profit-and-loss/"""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request) -> Response:
        """Computes and returns Profit & Loss (Income Statement) report."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.now().date()
        start_of_year = datetime.date(today.year, 1, 1)

        start_date = parse_date(request.query_params.get("start_date"), default=start_of_year)
        end_date = parse_date(request.query_params.get("end_date"), default=today)

        report = get_profit_and_loss(
            organization=tenant,
            start_date=start_date,
            end_date=end_date,
        )
        return Response(report.to_dict(), status=status.HTTP_200_OK)


class BalanceSheetReportAPIView(APIView):
    """Informational report resource: GET /api/v1/reports/balance-sheet/?as_of_date=YYYY-MM-DD"""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request) -> Response:
        """Computes and returns Balance Sheet (Statement of Financial Position)."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.now().date()
        as_of_date = parse_date(request.query_params.get("as_of_date"), default=today)

        report = get_balance_sheet(
            organization=tenant,
            as_of_date=as_of_date,
        )
        return Response(report.to_dict(), status=status.HTTP_200_OK)


# ============================================================================
# FISCAL PERIOD MANAGEMENT & PERIOD CLOSING
# ============================================================================
class FiscalPeriodListAPIView(APIView):
    """Resource collection for tenant fiscal periods: GET /api/v1/ledger/fiscal-periods/"""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request) -> Response:
        """Returns ordered list of fiscal periods for the active tenant."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        periods = FiscalPeriod.objects.filter(organization=tenant).order_by("start_date")
        data = [
            {
                "id": str(period.id),
                "period_name": period.period_name,
                "start_date": period.start_date.isoformat(),
                "end_date": period.end_date.isoformat(),
                "is_closed": period.is_closed,
                "closed_at": period.closed_at.isoformat() if period.closed_at else None,
                "closed_by": str(period.closed_by.id) if period.closed_by else None,
            }
            for period in periods
        ]
        return Response(data, status=status.HTTP_200_OK)


class FiscalPeriodCloseAPIView(APIView):
    """Action endpoint to officially lock and close a fiscal period:
    POST /api/v1/ledger/fiscal-periods/<uuid:pk>/close/

    Permissions: Restricted to OWNER and ACCOUNTANT. Forbidden for ADMIN, BOOKKEEPER, AUDITOR.
    """

    permission_classes = [IsAuthenticated, CanCloseFiscalPeriod]

    def post(self, request: Request, pk: Any) -> Response:
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period = get_object_or_404(FiscalPeriod, id=pk, organization=tenant)
        if period.is_closed:
            return Response(
                {"detail": f"Fiscal period '{period.period_name}' is already closed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period.close_period(user=request.user)

        AuditTrail.objects.create(
            organization=tenant,
            user=request.user,
            action="FISCAL_PERIOD_CLOSED",
            entity_type="FiscalPeriod",
            entity_id=str(period.id),
            metadata={
                "period_name": period.period_name,
                "start_date": period.start_date.isoformat(),
                "end_date": period.end_date.isoformat(),
                "closed_at": period.closed_at.isoformat() if period.closed_at else None,
            },
        )

        return Response(
            {
                "id": str(period.id),
                "period_name": period.period_name,
                "start_date": period.start_date.isoformat(),
                "end_date": period.end_date.isoformat(),
                "is_closed": period.is_closed,
                "closed_at": period.closed_at.isoformat() if period.closed_at else None,
                "closed_by": str(period.closed_by.id) if period.closed_by else None,
                "detail": f"Fiscal period '{period.period_name}' locked successfully.",
            },
            status=status.HTTP_200_OK,
        )
