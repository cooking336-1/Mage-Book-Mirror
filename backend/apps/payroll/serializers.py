"""Serializers for Payroll Runs, Line Items, and Step-Up TOTP Approval."""

from decimal import Decimal

from rest_framework import serializers

from apps.payroll.models import PayrollItem, PayrollRun


class PayrollItemSerializer(serializers.ModelSerializer):
    """Detailed read serializer for individual employee payroll line items."""

    class Meta:
        model = PayrollItem
        fields = [
            "id",
            "employee_name",
            "employee_tin_or_ghana_card",
            "momo_number",
            "gross_salary",
            "ssnit_employee",
            "ssnit_employer",
            "taxable_income",
            "paye_tax",
            "net_salary",
            "created_at",
        ]
        read_only_fields = fields


class PayrollRunSerializer(serializers.ModelSerializer):
    """Comprehensive read serializer for PayrollRun including line items and user details."""

    items = PayrollItemSerializer(many=True, read_only=True)
    maker_email = serializers.EmailField(source="maker.email", read_only=True)
    checker_email = serializers.EmailField(source="checker.email", read_only=True, default=None)
    period_name = serializers.CharField(source="period.period_name", read_only=True)

    class Meta:
        model = PayrollRun
        fields = [
            "id",
            "organization_id",
            "period_id",
            "period_name",
            "maker_id",
            "maker_email",
            "checker_id",
            "checker_email",
            "status",
            "total_gross_salary",
            "total_ssnit_employee",
            "total_ssnit_employer",
            "total_paye_tax",
            "total_net_payout",
            "journal_entry_id",
            "submitted_at",
            "approved_at",
            "disbursed_at",
            "created_at",
            "updated_at",
            "items",
        ]
        read_only_fields = fields


class EmployeeInputSerializer(serializers.Serializer):
    """Payload schema for an individual employee within a draft payroll compilation."""

    employee_name = serializers.CharField(max_length=255)
    gross_salary = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0.01")
    )
    employee_tin_or_ghana_card = serializers.CharField(max_length=50, required=False, default="")
    momo_number = serializers.CharField(max_length=30, required=False, default="")


class PayrollRunCreateSerializer(serializers.Serializer):
    """Payload schema for drafting a statutory payroll run."""

    period_id = serializers.UUIDField(help_text="UUID of active fiscal period.")
    employees = serializers.ListField(
        child=EmployeeInputSerializer(),
        allow_empty=False,
        help_text="Non-empty list of employee salary declarations.",
    )


class PayrollApprovalSerializer(serializers.Serializer):
    """Payload schema for Step-Up TOTP 2FA approval."""

    totp_code = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text="6-digit Time-Based One-Time Password from authenticator app.",
    )


class PayrollTwoFactorEnrollSerializer(serializers.Serializer):
    """Serializer for enrolling TOTP 2FA for a user."""

    totp_code = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text="6-digit code verifying enrollment before activating 2FA.",
    )
