"""Asynchronous Celery Tasks for Bulk Mobile Money Payroll Disbursement.

Provides:
- disburse_payroll_run_task: Background worker executing B2C payouts via Mobile Money
  and recording secondary balancing double-entry general ledger lines.
- execute_bulk_momo_payroll: Alias matching Master Transaction Sequence Diagrams (Step 18).
"""

import logging
from typing import Any

from celery import shared_task
from django.core.exceptions import ValidationError

from apps.payroll.services.disbursement import PayrollDisbursementService
from apps.tenancy.middleware import clear_current_tenant, set_current_tenant
from apps.tenancy.models import Organization

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    retry_backoff=True,
    name="apps.payroll.tasks.disburse_payroll_run_task",
)
def disburse_payroll_run_task(
    self: Any,
    payroll_run_id: str,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """Asynchronously disburses an approved payroll run via Mobile Money B2C transfers.

    Args:
        payroll_run_id: UUID string of target PayrollRun.
        organization_id: Optional UUID string of tenant organization.

    Returns:
        dict[str, Any]: Summary status including payroll_run_id and secondary journal ID.
    """
    logger.info(
        "[Payroll Disbursal Worker] Task started: payroll_run_id=%s, organization_id=%s",
        payroll_run_id,
        organization_id,
    )

    tenant: Organization | None = None
    if organization_id:
        tenant = Organization.objects.filter(id=organization_id).first()
        if tenant:
            set_current_tenant(tenant)

    try:
        payroll_run, journal_entry = PayrollDisbursementService.disburse_payroll_run(
            payroll_run_id=payroll_run_id,
            organization_id=organization_id,
        )

        return {
            "status": "SUCCESS",
            "payroll_run_id": str(payroll_run.id),
            "disbursed_at": payroll_run.disbursed_at.isoformat()
            if payroll_run.disbursed_at
            else None,
            "total_net_payout": str(payroll_run.total_net_payout),
            "journal_entry_id": str(journal_entry.id) if journal_entry else None,
            "journal_entry_number": journal_entry.entry_number if journal_entry else None,
        }
    except ValidationError as exc:
        msg = exc.message if hasattr(exc, "message") else str(exc)
        logger.error(
            "[Payroll Disbursal Worker] Non-retryable ValidationError for run=%s: %s",
            payroll_run_id,
            msg,
        )
        return {
            "status": "FAILED",
            "error": msg,
            "payroll_run_id": payroll_run_id,
        }
    except Exception as exc:
        logger.exception(
            "[Payroll Disbursal Worker] Transient error for run=%s: %s. Scheduling retry...",
            payroll_run_id,
            exc,
        )
        raise self.retry(exc=exc) from exc
    finally:
        clear_current_tenant()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    retry_backoff=True,
    name="execute_bulk_momo_payroll",
)
def execute_bulk_momo_payroll(
    self: Any,
    payroll_run_id: str,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """Alias for disburse_payroll_run_task matching Sequence Diagram Step 18."""
    return disburse_payroll_run_task(payroll_run_id=payroll_run_id, organization_id=organization_id)
