"""Asynchronous Celery tasks for statutory audit package compilation."""

import logging
from typing import Any

from celery import shared_task
from django.utils import timezone

from apps.audit.services.pbc_compiler import PBCPackageCompiler
from apps.tenancy.middleware import clear_current_tenant, set_current_tenant
from apps.tenancy.models import Organization, RoleChoices

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def compile_pbc_package(
    self: Any,
    tenant_id: str,
    fiscal_year: int,
    requested_by_id: str | None = None,
) -> dict[str, Any]:
    """Compiles a complete PBC (Provided By Client) audit package asynchronously.

    Streams:
    - 01_General_Ledger.csv
    - 02_Trial_Balance.csv
    - 03_Chart_of_Accounts.csv
    - 04_GRA_Act1151_VAT_Summary.csv
    - invoices/*.pdf

    Args:
        tenant_id: Target Organization UUID.
        fiscal_year: Target fiscal calendar year (e.g. 2026).
        requested_by_id: UUID of user initiating export.

    Returns:
        dict[str, Any]: Compilation metadata, manifest, and SHA-256 checksum.
    """
    logger.info(
        "[PBC Worker] Task started: tenant_id=%s, fiscal_year=%d, requested_by=%s",
        tenant_id,
        fiscal_year,
        requested_by_id,
    )

    try:
        tenant = Organization.objects.filter(id=tenant_id).first()
        if not tenant:
            logger.error("[PBC Worker] Target organization '%s' does not exist.", tenant_id)
            return {
                "status": "FAILED",
                "error": f"Organization '{tenant_id}' not found.",
                "tenant_id": tenant_id,
                "fiscal_year": fiscal_year,
            }

        # Bind tenant context to prevent data leaks across tasks
        set_current_tenant(tenant, RoleChoices.AUDITOR)

        result = PBCPackageCompiler.compile_package(
            organization=tenant,
            fiscal_year=fiscal_year,
        )

        logger.info(
            "[PBC Worker] Package compiled successfully: filename=%s, sha256=%s, files=%d",
            result.filename,
            result.sha256_hash,
            result.file_count,
        )

        return {
            "status": "COMPLETED",
            "tenant_id": str(tenant.id),
            "fiscal_year": fiscal_year,
            "filename": result.filename,
            "sha256": result.sha256_hash,
            "archive_size_bytes": len(result.archive_bytes),
            "file_count": result.file_count,
            "invoice_count": result.invoice_count,
            "file_manifest": result.file_manifest,
            "completed_at": timezone.now().isoformat(),
        }

    except Exception as exc:
        retry_num = self.request.retries + 1 if hasattr(self, "request") else 1
        logger.exception(
            "[PBC Worker] Transient error compiling PBC package (attempt %d/%d): %s",
            retry_num,
            self.max_retries,
            exc,
        )
        if retry_num <= self.max_retries:
            raise self.retry(exc=exc) from exc
        return {
            "status": "FAILED",
            "error": str(exc),
            "tenant_id": tenant_id,
            "fiscal_year": fiscal_year,
        }

    finally:
        clear_current_tenant()
