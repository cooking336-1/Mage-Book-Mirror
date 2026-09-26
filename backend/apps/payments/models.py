"""Payment Models for Mage Books SAAS.

Provides:
1. WebhookStatusChoices: Enumeration for webhook lifecycle states.
2. PaymentWebhookLog: Immutable audit log for incoming payment webhooks from aggregators
   (Paystack, Hubtel, MTN MoMo, Telecel Cash).
"""

import uuid6
from django.db import models
from django.utils import timezone

from apps.core.models import BaseTenantModel


class WebhookStatusChoices(models.TextChoices):
    """Lifecycle status choices for incoming payment webhooks."""

    RECEIVED = "RECEIVED", "Received"
    VERIFIED = "VERIFIED", "Signature Verified"
    FAILED_SIGNATURE = "FAILED_SIGNATURE", "Signature Verification Failed"
    FAILED_TENANT_RESOLUTION = "FAILED_TENANT_RESOLUTION", "Failed Tenant Resolution"
    PROCESSED = "PROCESSED", "Processed"
    IGNORED = "IGNORED", "Ignored"


class PaymentMethodChoices(models.TextChoices):
    """Supported payment channels and Mobile Money rails in Ghana."""

    MTN_MOMO = "MTN_MOMO", "MTN Mobile Money"
    TELECEL_CASH = "TELECEL_CASH", "Telecel Cash"
    AT_MONEY = "AT_MONEY", "AT Money"
    BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
    BANK_POS = "BANK_POS", "Bank POS Card"
    CASH = "CASH", "Cash"
    CHEQUE = "CHEQUE", "Cheque"
    OTHER = "OTHER", "Other"


class PaymentTransactionTypeChoices(models.TextChoices):
    """Statutory direction of financial funds transfer."""

    RECEIPT = "RECEIPT", "Receipt (Inflow)"
    PAYMENT = "PAYMENT", "Payment (Outflow)"


class PaymentStatusChoices(models.TextChoices):
    """Reconciliation and settlement lifecycle states for payment records."""

    SETTLED = "SETTLED", "Settled"
    PARTIAL = "PARTIAL", "Partially Paid"
    SUSPENSE = "SUSPENSE", "Suspense (Unreconciled)"
    FAILED = "FAILED", "Failed"


def map_provider_to_payment_method(raw_channel: str | None) -> str:
    """Sanitizes raw gateway provider or channel strings to valid PaymentMethodChoices.

    Normalizes inputs such as 'MTN-GH', 'vodafone', 'TELECEL', 'tigo', 'airteltigo'.
    """
    if not raw_channel:
        return PaymentMethodChoices.MTN_MOMO

    normalized = str(raw_channel).strip().lower().replace("-", "_").replace(" ", "_")

    if any(k in normalized for k in ("mtn", "mtn_gh", "momo")):
        return PaymentMethodChoices.MTN_MOMO
    if any(k in normalized for k in ("vodafone", "telecel", "voda")):
        return PaymentMethodChoices.TELECEL_CASH
    if any(k in normalized for k in ("airtel", "tigo", "at_money", "at")):
        return PaymentMethodChoices.AT_MONEY
    if any(k in normalized for k in ("bank", "transfer", "ach", "ghipss")):
        return PaymentMethodChoices.BANK_TRANSFER
    if any(k in normalized for k in ("pos", "card", "visa", "mastercard")):
        return PaymentMethodChoices.BANK_POS
    if "cash" in normalized:
        return PaymentMethodChoices.CASH
    if "cheque" in normalized:
        return PaymentMethodChoices.CHEQUE

    return PaymentMethodChoices.OTHER


class PaymentWebhookLog(models.Model):
    """Immutable audit trail for incoming payment webhooks from aggregators.

    Stores the raw payload, headers, provider, event identifier, and verification status.
    Organization is nullable because failed or unauthenticated calls cannot be bound
    to a tenant until verified and resolved against internal invoices.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid6.uuid7,
        editable=False,
        help_text="Sequential UUIDv7 primary key.",
    )
    organization = models.ForeignKey(
        "tenancy.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_webhook_logs",
        help_text="Associated tenant organization once resolved from invoice reference.",
    )
    provider = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Payment gateway provider (e.g. 'paystack', 'hubtel', 'momo').",
    )
    event_id = models.CharField(
        max_length=255,
        db_index=True,
        blank=True,
        help_text="Aggregator event ID (e.g. Paystack event ID or Hubtel client reference).",
    )
    event_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of webhook event (e.g. 'charge.success').",
    )
    signature_header = models.CharField(
        max_length=512,
        blank=True,
        help_text="Raw cryptographic signature header from the incoming request.",
    )
    status = models.CharField(
        max_length=50,
        choices=WebhookStatusChoices.choices,
        default=WebhookStatusChoices.RECEIVED,
        db_index=True,
        help_text="Current processing and verification status.",
    )
    payload = models.JSONField(
        default=dict,
        help_text="Parsed JSON body of the webhook callback.",
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Relevant HTTP request headers for security forensics.",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Failure reason or security mismatch description if verification fails.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the webhook was received.",
    )

    class Meta:
        db_table = "payment_webhook_logs"
        ordering = ["-created_at"]
        verbose_name = "Payment Webhook Log"
        verbose_name_plural = "Payment Webhook Logs"
        indexes = [
            models.Index(fields=["provider", "event_id"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        evt = self.event_id or "No-Event-ID"
        return f"[{self.provider}] {evt} ({self.status}) at {self.created_at}"


class Payment(BaseTenantModel):
    """Payment transaction record for inbound receipts and outbound settlements.

    Inherits from BaseTenantModel:
    - id: Sequential UUIDv7 primary key for high-throughput append performance.
    - organization: Tenant organization ownership protected against cascading deletion.
    - Composite UNIQUE(organization, id) constraint.
    """

    customer = models.ForeignKey(
        "invoicing.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        help_text="Target customer contact record.",
    )
    invoice = models.ForeignKey(
        "invoicing.Invoice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        help_text="Target invoice settled by this payment receipt.",
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="Gross transaction amount.",
    )
    currency = models.CharField(
        max_length=3,
        default="GHS",
        help_text="ISO 4217 currency code.",
    )
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethodChoices.choices,
        default=PaymentMethodChoices.MTN_MOMO,
        help_text="Payment channel or aggregator rail.",
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=PaymentTransactionTypeChoices.choices,
        default=PaymentTransactionTypeChoices.RECEIPT,
        help_text="Direction of funds transfer.",
    )
    status = models.CharField(
        max_length=30,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.SETTLED,
        db_index=True,
        help_text="Current reconciliation and settlement status.",
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Aggregator transaction ID or bank reference code.",
    )
    payment_reference = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Customer-entered payment memo or Luhn invoice code.",
    )
    transaction_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Effective timestamp of payment recognition.",
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        help_text="Associated double-entry general ledger journal entry.",
    )
    reconciliation_notes = models.TextField(
        blank=True,
        help_text="Audit and suspense routing memo.",
    )
    raw_event = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot of normalized payment event payload.",
    )
    created_by = models.ForeignKey(
        "authentication.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payments",
        help_text="User initiating transaction, or null for machine webhooks.",
    )

    class Meta(BaseTenantModel.Meta):
        db_table = "payments"
        ordering = ["-transaction_date", "-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        constraints = BaseTenantModel.Meta.constraints + [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_amount_strictly_positive",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "payment_reference"]),
            models.Index(fields=["organization", "reference_number"]),
        ]

    def __str__(self) -> str:
        ref = self.reference_number or self.payment_reference or str(self.id)[:8]
        return f"Payment {ref} ({self.amount} {self.currency}) [{self.status}]"


# Specification compatibility alias
PaymentTransaction = Payment
