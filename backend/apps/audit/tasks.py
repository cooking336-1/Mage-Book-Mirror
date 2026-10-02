"""Asynchronous Celery tasks for statutory audit package compilation."""

import logging
from typing import Any

from celery import shared_task
from django.utils import timezone

from apps.audit.models import AuditTrail
from apps.audit.services.pbc_compiler import PBCPackageCompiler
from apps.core.services.storage import get_storage_service
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

    Artifact:
    - Uploads ZIP to Cloudflare R2
    - Generates 24-hour presigned download URL
    - Records immutable AuditTrail entry with SHA-256 manifest hash

    Args:
        tenant_id: Target Organization UUID.
        fiscal_year: Target fiscal calendar year (e.g. 2026).
        requested_by_id: UUID of user initiating export.

    Returns:
        dict[str, Any]: Compilation metadata, presigned URL, and SHA-256 checksum.
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

        # Upload compiled archive to Cloudflare R2 object storage
        storage_key = f"tenants/{tenant.id}/audits/{fiscal_year}/{result.filename}"
        storage = get_storage_service()
        storage.upload_file_bytes(
            key=storage_key,
            data=result.archive_bytes,
            content_type="application/zip",
        )

        # Generate 24-hour cryptographically signed presigned download URL (86400 seconds)
        download_url = storage.generate_presigned_download_url(
            key=storage_key,
            expires_in=86400,
        )

        # Identify requesting user if available
        requesting_user = None
        if requested_by_id:
            from django.contrib.auth import get_user_model

            user_model = get_user_model()
            requesting_user = user_model.objects.filter(id=requested_by_id).first()

        # Persist immutable audit log entry for statutory non-repudiation
        audit_entry = AuditTrail.objects.create(
            organization=tenant,
            user=requesting_user,
            action="PBC_AUDIT_PACKAGE_GENERATED",
            entity_type="PBCPackage",
            entity_id=storage_key,
            sha256_hash=result.sha256_hash,
            file_path=storage_key,
            metadata={
                "fiscal_year": fiscal_year,
                "filename": result.filename,
                "archive_size_bytes": len(result.archive_bytes),
                "file_count": result.file_count,
                "invoice_count": result.invoice_count,
                "download_url": download_url,
                "expires_in_seconds": 86400,
            },
        )

        logger.info(
            "[PBC Worker] Package compiled and uploaded successfully: "
            "filename=%s, sha256=%s, files=%d, audit_id=%s",
            result.filename,
            result.sha256_hash,
            result.file_count,
            audit_entry.id,
        )

        return {
            "status": "COMPLETED",
            "tenant_id": str(tenant.id),
            "fiscal_year": fiscal_year,
            "filename": result.filename,
            "storage_key": storage_key,
            "download_url": download_url,
            "sha256": result.sha256_hash,
            "archive_size_bytes": len(result.archive_bytes),
            "file_count": result.file_count,
            "invoice_count": result.invoice_count,
            "file_manifest": result.file_manifest,
            "audit_trail_id": str(audit_entry.id),
            "expires_in": 86400,
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
