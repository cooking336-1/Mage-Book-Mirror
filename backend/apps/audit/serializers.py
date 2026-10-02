"""Serializers for Forensic Audit Trail and PBC package metadata."""

from rest_framework import serializers

from apps.audit.models import AuditTrail


class AuditTrailSerializer(serializers.ModelSerializer):
    """Read-only serializer for immutable audit trail entries."""

    user_email = serializers.EmailField(source="user.email", read_only=True, default=None)

    class Meta:
        model = AuditTrail
        fields = [
            "id",
            "organization_id",
            "user_id",
            "user_email",
            "action",
            "entity_type",
            "entity_id",
            "ip_address",
            "user_agent",
            "before_state",
            "after_state",
            "sha256_hash",
            "file_path",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
