"""Admin registration for immutable audit trail."""

from typing import Any

from django.contrib import admin

from apps.audit.models import AuditTrail


@admin.register(AuditTrail)
class AuditTrailAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "action",
        "entity_type",
        "entity_id",
        "sha256_hash",
        "organization",
        "user",
        "created_at",
    )
    list_filter = ("action", "entity_type", "created_at")
    search_fields = ("action", "entity_type", "entity_id", "sha256_hash")
    readonly_fields = [f.name for f in AuditTrail._meta.fields]

    def has_add_permission(self, request: Any) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: Any, obj: Any = None) -> bool:
        return False
