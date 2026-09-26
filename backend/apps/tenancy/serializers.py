"""Serializers for Tenancy, Team Members, and Financial Destination Settings."""

from typing import Any

from rest_framework import serializers

from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    """Read serializer for organization team memberships."""

    user_id = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = [
            "id",
            "user_id",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "access_expires_at",
            "created_at",
        ]
        read_only_fields = ["id", "user_id", "email", "first_name", "last_name", "created_at"]


class OrganizationMembershipCreateSerializer(serializers.Serializer):
    """Serializer for adding or inviting a new team member to an organization."""

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False, default="")
    last_name = serializers.CharField(max_length=150, required=False, default="")
    role = serializers.ChoiceField(choices=RoleChoices.choices, default=RoleChoices.BOOKKEEPER)
    access_expires_at = serializers.DateTimeField(required=False, allow_null=True, default=None)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        role = attrs.get("role")
        expires_at = attrs.get("access_expires_at")

        if role == RoleChoices.OWNER and expires_at is not None:
            raise serializers.ValidationError(
                {"access_expires_at": "Owner role cannot have an access expiration date."}
            )
        return attrs


class OrganizationMembershipUpdateSerializer(serializers.Serializer):
    """Serializer for updating an existing member's role, status, or expiration."""

    role = serializers.ChoiceField(choices=RoleChoices.choices, required=False)
    is_active = serializers.BooleanField(required=False)
    access_expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        role = attrs.get("role")
        expires_at = attrs.get("access_expires_at")

        if role == RoleChoices.OWNER and expires_at is not None:
            raise serializers.ValidationError(
                {"access_expires_at": "Owner role cannot have an access expiration date."}
            )
        return attrs


class OrganizationSettlementSerializer(serializers.ModelSerializer):
    """Serializer for managing commercial bank and mobile money settlement coordinates."""

    owner_totp_code = serializers.CharField(
        max_length=6,
        min_length=6,
        write_only=True,
        required=False,
        default="",
        help_text="Required when updated by an Admin to satisfy the Owner TOTP step-up challenge.",
    )

    class Meta:
        model = Organization
        fields = [
            "settlement_bank_name",
            "settlement_account_number",
            "settlement_momo_number",
            "settlement_locked_at",
            "owner_totp_code",
        ]
        read_only_fields = ["settlement_locked_at"]


class OrganizationDetailSerializer(serializers.ModelSerializer):
    """Serializer for organization profile and settings."""

    owner_email = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "business_tin",
            "ghana_card_number",
            "address",
            "phone",
            "email",
            "owner_email",
            "is_active",
            "vat_registered",
            "vat_scheme",
            "default_experience_mode",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]

    def get_owner_email(self, obj: Organization) -> str | None:
        owner = obj.owner
        return owner.email if owner else None
