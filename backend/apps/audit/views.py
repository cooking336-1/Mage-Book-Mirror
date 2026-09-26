"""REST API Views for Statutory PBC Audit Package Compilation and Tracking.

Follows RESTful conventions:
- Collection resource: POST /api/v1/audit/pbc/ (Enqueues compilation, returns 202 Accepted)
- Member resource: GET /api/v1/audit/pbc/<task_id>/ (Queries compilation status)
"""

from typing import Any

from celery.result import AsyncResult
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.tasks import compile_pbc_package
from apps.tenancy.middleware import get_current_tenant
from apps.tenancy.models import Organization
from apps.tenancy.permissions import CanExportPBC


def resolve_request_tenant(request: Request) -> Organization | None:
    """Safely extracts tenant organization from request object or thread-local storage."""
    if hasattr(request, "tenant") and request.tenant is not None:
        return request.tenant
    tenant = get_current_tenant()
    if tenant is not None:
        return tenant
    return None


class PBCAuditExportAPIView(APIView):
    """Asynchronous compilation resource: POST /api/v1/audit/pbc/"""

    permission_classes = [IsAuthenticated, CanExportPBC]

    def post(self, request: Request) -> Response:
        """Enqueues asynchronous compilation of Provided By Client (PBC) audit package."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_year = request.data.get("fiscal_year")
        if raw_year is not None:
            try:
                fiscal_year = int(raw_year)
            except (ValueError, TypeError):
                return Response(
                    {"detail": "Invalid fiscal_year provided. Must be an integer year."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if fiscal_year < 2000 or fiscal_year > 2100:
                return Response(
                    {"detail": "fiscal_year must be between 2000 and 2100."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            fiscal_year = timezone.now().year

        user_id = str(request.user.id) if request.user and request.user.is_authenticated else None
        task = compile_pbc_package.delay(
            tenant_id=str(tenant.id),
            fiscal_year=fiscal_year,
            requested_by_id=user_id,
        )

        return Response(
            {
                "task_id": task.id,
                "status": "PROCESSING",
                "fiscal_year": fiscal_year,
                "message": "PBC audit package compilation enqueued.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PBCAuditExportStatusAPIView(APIView):
    """Member status resource: GET /api/v1/audit/pbc/<task_id>/"""

    permission_classes = [IsAuthenticated, CanExportPBC]

    def get(self, request: Request, task_id: str) -> Response:
        """Queries the current status and results of a PBC package compilation task."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            res = AsyncResult(task_id)
            state = res.state
        except Exception:
            # Fallback if result backend is temporarily unreachable
            return Response(
                {
                    "task_id": task_id,
                    "status": "PROCESSING",
                },
                status=status.HTTP_200_OK,
            )

        if state in ("PENDING", "STARTED", "RECEIVED", "RETRY"):
            return Response(
                {
                    "task_id": task_id,
                    "status": "PROCESSING",
                },
                status=status.HTTP_200_OK,
            )

        if state == "SUCCESS":
            result: Any = res.result
            task_status = (
                result.get("status", "COMPLETED") if isinstance(result, dict) else "COMPLETED"
            )
            return Response(
                {
                    "task_id": task_id,
                    "status": task_status,
                    "result": result,
                },
                status=status.HTTP_200_OK,
            )

        if res.state == "FAILURE":
            return Response(
                {
                    "task_id": task_id,
                    "status": "FAILED",
                    "error": str(res.result),
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "task_id": task_id,
                "status": res.state,
            },
            status=status.HTTP_200_OK,
        )
