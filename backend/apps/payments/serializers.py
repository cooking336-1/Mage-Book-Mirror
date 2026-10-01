"""Serializers for Inbound Receipts, Outbound Disbursements, and Payment Transactions."""

from rest_framework import serializers

from apps.payments.models import (
    Payment,
)


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment transactions."""

    customer_name = serializers.CharField(source="customer.name", read_only=True, default=None)
    invoice_number = serializers.CharField(
        source="invoice.invoice_number", read_only=True, default=None
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "organization_id",
            "customer",
            "customer_name",
            "invoice",
            "invoice_number",
            "amount",
            "currency",
            "payment_method",
            "transaction_type",
            "status",
            "reference_number",
            "payment_reference",
            "transaction_date",
            "journal_entry_id",
            "reconciliation_notes",
            "created_at",
        ]
        read_only_fields = ["id", "organization_id", "journal_entry_id", "created_at"]
