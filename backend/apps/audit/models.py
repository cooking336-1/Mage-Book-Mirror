"""Forensic Audit Trail & Immutability Models.

Satisfies:
- Architecture Manual Section 4.7 Layer 6 (Immutable Auditing & Anti-Tamper Security)
- Master 5-Sprint Implementation Plan Sprint 5 (Feature 5.3)
- Statutory requirement: Write-once append-only log of critical tenant operations
"""

from typing import Any

from django.conf import settings
from django.db import models
from rest_framework.exceptions import PermissionDenied

from apps.core.models import BaseTenantModel, TenantQuerySet


class AuditTrailQuerySet(TenantQuerySet):
    """QuerySet enforcing tamper-proof immutability on audit logs.

    Prevents bulk updates and bulk deletions at the ORM queryset level.
    """

    def update(self, **kwargs: Any) -> int:
        """Blocks bulk UPDATE operations across audit logs."""
        raise PermissionDenied(
            "Audit log entries are strictly immutable. Bulk UPDATE operations are forbidden."
        )

    def delete(self) -> tuple[int, dict[str, int]]:
        """Blocks bulk DELETE operations across audit logs."""
        raise PermissionDenied(
            "Audit log entries are strictly immutable. Bulk DELETE operations are forbidden."
        )


class AuditTrailManager(models.Manager.from_queryset(AuditTrailQuerySet)):
    """Default model manager for AuditTrail exposing immutable QuerySet helpers."""

    pass


class AuditTrail(BaseTenantModel):
    """Tamper-evident, write-once statutory audit log for financial compliance.

    Records actor, IP address, user agent, action, entity type, target entity ID,
    cryptographic SHA-256 digests, and state diffs.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_trails",
        db_index=True,
        help_text="User identity who initiated the audited operation.",
    )
    action = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Action identifier (e.g. PBC_AUDIT_PACKAGE_GENERATED, INVOICE_CLEARED).",
    )
    entity_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Domain model or resource category affected (e.g. PBCPackage, Invoice).",
    )
    entity_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Identifier of the target entity (UUID or storage path).",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address initiating the transaction.",
    )
    user_agent = models.TextField(
        blank=True,
        default="",
        help_text="Client user agent string for forensics.",
    )
    before_state = models.JSONField(
        null=True,
        blank=True,
        help_text="Snapshot of record state before mutation (if applicable).",
    )
    after_state = models.JSONField(
        null=True,
        blank=True,
        help_text="Snapshot of record state after mutation (if applicable).",
    )
    sha256_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Cryptographic SHA-256 digest for manifest non-repudiation.",
    )
    file_path = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Object storage key or export path for compiled artifacts.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary contextual metadata (e.g. fiscal year, presigned URL expiry).",
    )

    objects = AuditTrailManager()

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "id"],
                name="unique_audit_audittrail_tenant_id",
            )
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Enforces write-once immutability: UPDATE operations are strictly forbidden."""
        if self.pk and AuditTrail.objects.filter(pk=self.pk).exists():
            raise PermissionDenied(
                "Audit log entries are strictly immutable. UPDATE operations are forbidden."
            )
        # Bypasses BaseTenantModel's auditor modification block so statutory audit
        # logs can be persisted during auditor-initiated operations (e.g. PBC package exports).
        models.Model.save(self, *args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Enforces write-once immutability: DELETE operations are strictly forbidden."""
        raise PermissionDenied(
            "Audit log entries are strictly immutable. DELETE operations are forbidden."
        )

    def __str__(self) -> str:
        return f"[{self.created_at}] {self.action} on {self.entity_type} ({self.organization_id})"
