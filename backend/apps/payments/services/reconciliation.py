"""Mobile Money Payment Reconciliation and Suspense Engine.

Implements:
1. Misuse Case 1.1 (MUC-1.1) Defense: Strict Decimal underpayment trap; partial payments
   transition to PARTIALLY_PAID and NEVER mark invoices as PAID.
2. Suspense Account 2150 Routing: Missing, corrupted (failed Luhn), unmatched, or foreign currency
   deposits are safely quarantined to Suspense Account 2150 (Unreconciled Payments) without
   dropping cash or skewing double-entry balance sheets.
3. Overpayment Splitting: When amount > invoice.balance_due, splits credit line between AR 1200
   and Suspense Account 2150.
4. Tenant Resolution Fallback: Gracefully handles unresolvable tenants via FAILED_TENANT_RESOLUTION
   without raising HTTP 500 errors.
5. Telco Sanitization: Standardizes raw aggregator channels to valid PaymentMethodChoices.
6. Atomic General Ledger Postings: Enforces Dr 1015 MoMo Clearing and Cr 1200 AR / 2150 Suspense
   via LedgerService.post_journal_entry within @transaction.atomic.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.invoicing.models import Invoice, InvoiceStatusChoices
from apps.invoicing.utils import LuhnValidator
from apps.ledger.models import ChartOfAccounts, JournalEntry, SourceTypeChoices
from apps.ledger.services.ledger import LedgerService
from apps.ledger.services.seeder import seed_standard_chart_of_accounts
from apps.payments.gateways.base import NormalizedPaymentEvent
from apps.payments.models import (
    Payment,
    PaymentStatusChoices,
    PaymentTransactionTypeChoices,
    PaymentWebhookLog,
    WebhookStatusChoices,
    map_provider_to_payment_method,
)
from apps.tenancy.models import Organization

logger = logging.getLogger(__name__)

ZERO_MONEY = Decimal("0.0000")
QUANTIZE_FOUR_PLACES = Decimal("0.0001")


@dataclass
class ReconciliationResult:
    """Outcome summary of a payment reconciliation attempt."""

    status: str  # "SETTLED", "PARTIAL", "SUSPENSE", "FAILED_TENANT_RESOLUTION", "ERROR"
    payment: Payment | None = None
    journal_entry: JournalEntry | None = None
    invoice: Invoice | None = None
    is_suspense: bool = False
    excess_amount: Decimal = ZERO_MONEY
    notes: str = ""
    error: str | None = None


class ReconciliationService:
    """Enterprise reconciliation service resolving MoMo payments against invoices and
    general ledger.
    """

    @classmethod
    def resolve_organization(
        cls,
        event: NormalizedPaymentEvent,
        explicit_org: Organization | None = None,
    ) -> tuple[Organization | None, Invoice | None]:
        """Resolves tenant organization and candidate invoice from payment event data.

        Resolution Hierarchy:
        1. Explicitly provided organization instance.
        2. Customer reference matching an open invoice (by Luhn ref or invoice number).
        3. Aggregator payload metadata (organization_id, tenant_id, subaccount).
        4. Prior PaymentWebhookLog tenant association.
        """
        if explicit_org:
            return explicit_org, None

        raw_ref = (event.reference or "").strip()
        matched_invoice: Invoice | None = None

        # 1. Attempt Invoice Lookup from Reference
        if raw_ref:
            is_valid_luhn, base_payload, check_digit = LuhnValidator.clean_and_validate(raw_ref)
            full_digits = re.sub(r"[^0-9]", "", raw_ref)
            delimited_ref = f"{base_payload}-{check_digit}" if check_digit is not None else raw_ref
            ref_variants = list(
                {v for v in [raw_ref, delimited_ref, full_digits, base_payload] if v}
            )

            candidates = Invoice.objects.select_related("organization", "customer").filter(
                Q(payment_reference__in=ref_variants) | Q(invoice_number__in=ref_variants)
            )
            # Prefer active/open invoices
            open_inv = candidates.filter(
                status__in=[
                    InvoiceStatusChoices.PENDING_GRA,
                    InvoiceStatusChoices.CLEARED,
                    InvoiceStatusChoices.PARTIALLY_PAID,
                    InvoiceStatusChoices.OVERDUE,
                ]
            ).first()
            matched_invoice = open_inv or candidates.first()

            if matched_invoice and matched_invoice.organization:
                return matched_invoice.organization, matched_invoice

        # 2. Attempt Metadata / Subaccount Lookup
        payload = event.raw_payload or {}
        metadata = payload.get("data", {}).get("metadata", {}) or payload.get("metadata", {})

        org_id_raw = (
            metadata.get("organization_id")
            or metadata.get("tenant_id")
            or payload.get("organization_id")
            or payload.get("tenant_id")
        )
        if org_id_raw:
            try:
                org_uuid = uuid.UUID(str(org_id_raw))
                org = Organization.objects.filter(id=org_uuid).first()
                if org:
                    return org, matched_invoice
            except (ValueError, TypeError):
                pass

        # 3. Prior Webhook Log Lookup
        if event.event_id:
            log_entry = PaymentWebhookLog.objects.filter(
                provider=event.provider,
                event_id=event.event_id,
            ).first()
            if log_entry and log_entry.organization:
                return log_entry.organization, matched_invoice

        return None, matched_invoice

    @classmethod
    def _resolve_clearing_account_code(cls, organization: Organization) -> str:
        """Resolves the active Mobile Money Clearing account (1015, fallback 1010)."""
        if ChartOfAccounts.objects.filter(
            organization=organization, account_code="1015", is_active=True
        ).exists():
            return "1015"
        if ChartOfAccounts.objects.filter(
            organization=organization, account_code="1010", is_active=True
        ).exists():
            return "1010"
        # Ensure standard accounts exist
        seed_standard_chart_of_accounts(organization)
        return "1015"

    @classmethod
    def reconcile_payment(
        cls,
        event: NormalizedPaymentEvent,
        organization: Organization | None = None,
    ) -> ReconciliationResult:
        """Executes atomic reconciliation and double-entry GL posting for a payment event.

        Enforces:
        - Strict positive amount check.
        - Currency guard (foreign currencies routed to Suspense 2150).
        - Luhn reference verification.
        - Misuse Case 1.1 underpayment defense.
        - Overpayment splitting (AR 1200 + Suspense 2150).
        - Suspense routing for unresolvable references or missing invoices.
        """
        # 1. Zero or Negative Amount Guard
        amount = Decimal(str(event.amount)).quantize(QUANTIZE_FOUR_PLACES)
        if amount <= ZERO_MONEY:
            logger.warning(
                f"[{event.provider}] Rejected payment with non-positive amount: "
                f"{amount} {event.currency}"
            )
            return ReconciliationResult(
                status="ERROR",
                is_suspense=False,
                notes="Payment amount must be strictly positive (> 0.0000).",
                error="Non-positive payment amount",
            )

        # 2. Resolve Tenant Organization
        resolved_org, candidate_invoice = cls.resolve_organization(event, explicit_org=organization)
        if not resolved_org:
            logger.warning(
                f"[{event.provider}] Webhook failed tenant resolution: event_id={event.event_id}, "
                f"ref='{event.reference}'."
            )
            PaymentWebhookLog.objects.filter(
                provider=event.provider,
                event_id=event.event_id,
            ).update(
                status=WebhookStatusChoices.FAILED_TENANT_RESOLUTION,
                error_message=(
                    "Could not resolve tenant organization from reference, metadata, or subaccount."
                ),
            )
            return ReconciliationResult(
                status="FAILED_TENANT_RESOLUTION",
                is_suspense=True,
                notes="Tenant unresolvable from payment payload or reference.",
                error="Tenant unresolvable",
            )

        # Ensure standard Chart of Accounts exists
        cls._resolve_clearing_account_code(resolved_org)

        # 3. Currency Guard (Refinement 3)
        currency_code = (event.currency or "GHS").upper().strip()
        if currency_code != "GHS":
            logger.warning(
                f"[{event.provider}] Foreign currency deposit ({currency_code}) detected. "
                "Quarantining to Suspense Account 2150."
            )
            return cls._route_to_suspense(
                organization=resolved_org,
                event=event,
                amount=amount,
                reason=f"Foreign currency '{currency_code}' quarantined to Suspense Account 2150.",
            )

        # 4. Reference & Luhn Check-Digit Validation
        raw_ref = (event.reference or "").strip()
        if not raw_ref:
            return cls._route_to_suspense(
                organization=resolved_org,
                event=event,
                amount=amount,
                reason="Missing payment reference: deposit routed to Suspense Account 2150.",
            )

        is_valid_luhn, clean_ref, _ = LuhnValidator.clean_and_validate(raw_ref)
        if not is_valid_luhn:
            logger.warning(
                f"[{event.provider}] Corrupted or invalid Luhn reference '{raw_ref}'. "
                "Routing to Suspense Account 2150."
            )
            return cls._route_to_suspense(
                organization=resolved_org,
                event=event,
                amount=amount,
                reason=(
                    f"Failed Luhn check-digit verification on '{raw_ref}': routed to Suspense 2150."
                ),
            )

        # 5. Resolve Target Open Invoice
        # Lock target invoice row to prevent race conditions during concurrent settlements
        full_digits = re.sub(r"[^0-9]", "", raw_ref)
        base_payload, check_digit = (
            LuhnValidator.clean_and_validate(raw_ref)[1],
            LuhnValidator.clean_and_validate(raw_ref)[2],
        )
        delimited_ref = f"{base_payload}-{check_digit}" if check_digit is not None else raw_ref
        ref_variants = list({v for v in [raw_ref, delimited_ref, full_digits, base_payload] if v})

        invoice = (
            Invoice.objects.select_for_update()
            .filter(
                organization=resolved_org,
            )
            .filter(Q(payment_reference__in=ref_variants) | Q(invoice_number__in=ref_variants))
            .first()
        )

        if not invoice:
            return cls._route_to_suspense(
                organization=resolved_org,
                event=event,
                amount=amount,
                reason=(
                    f"Invoice reference '{raw_ref}' not found in tenant records: "
                    "routed to Suspense 2150."
                ),
            )

        # Disallow settlement of cancelled or draft invoices
        if invoice.status in [InvoiceStatusChoices.CANCELLED, InvoiceStatusChoices.DRAFT]:
            return cls._route_to_suspense(
                organization=resolved_org,
                event=event,
                amount=amount,
                reason=(
                    f"Invoice {invoice.invoice_number} is in '{invoice.status}' state: "
                    "routed to Suspense 2150."
                ),
            )

        # Check remaining balance
        balance_due = invoice.balance_due.quantize(QUANTIZE_FOUR_PLACES)
        if balance_due <= ZERO_MONEY or invoice.status == InvoiceStatusChoices.PAID:
            return cls._route_to_suspense(
                organization=resolved_org,
                event=event,
                amount=amount,
                reason=(
                    f"Invoice {invoice.invoice_number} is already fully paid: "
                    "routed to Suspense 2150."
                ),
            )

        # 6. Reconcile Amount & Defend Against Underpayment (MUC-1.1)
        momo_acc = cls._resolve_clearing_account_code(resolved_org)
        clearing_date = event.paid_at.date() if event.paid_at else timezone.now().date()
        method = map_provider_to_payment_method(
            event.raw_payload.get("channel")
            or event.raw_payload.get("data", {}).get("channel")
            or event.provider
        )

        if amount < balance_due:
            # --- Case A2: Partial Payment (MUC-1.1 Underpayment Defense) ---
            # Attacker paid fractional amount; NEVER mark PAID!
            with transaction.atomic():
                invoice.paid_amount = (invoice.paid_amount + amount).quantize(QUANTIZE_FOUR_PLACES)
                invoice.status = InvoiceStatusChoices.PARTIALLY_PAID
                invoice.save(update_fields=["paid_amount", "status", "updated_at"])

                lines_data = [
                    {
                        "account": momo_acc,
                        "debit": amount,
                        "description": (
                            f"MoMo collection for Invoice {invoice.invoice_number} (Ref: {raw_ref})"
                        ),
                    },
                    {
                        "account": "1200",  # Accounts Receivable
                        "credit": amount,
                        "description": f"AR partial payment for Invoice {invoice.invoice_number}",
                    },
                ]

                payment = Payment.objects.create(
                    organization=resolved_org,
                    customer=invoice.customer,
                    invoice=invoice,
                    amount=amount,
                    currency=currency_code,
                    payment_method=method,
                    transaction_type=PaymentTransactionTypeChoices.RECEIPT,
                    status=PaymentStatusChoices.PARTIAL,
                    reference_number=event.event_id,
                    payment_reference=raw_ref,
                    transaction_date=event.paid_at or timezone.now(),
                    reconciliation_notes=(
                        f"Partial payment received. Remaining balance: "
                        f"GHS {invoice.balance_due:.4f}"
                    ),
                    raw_event=event.raw_payload,
                )

                journal_entry = LedgerService.post_journal_entry(
                    organization=resolved_org,
                    entry_date=clearing_date,
                    lines_data=lines_data,
                    narration=(
                        f"MoMo partial settlement for Invoice "
                        f"{invoice.invoice_number} (Ref: {raw_ref})"
                    ),
                    source_type=SourceTypeChoices.PAYMENT,
                    source_id=payment.id,
                )

                payment.journal_entry = journal_entry
                payment.save(update_fields=["journal_entry"])

            logger.info(
                f"[{event.provider}] Reconciled PARTIAL payment of GHS {amount} for "
                f"Invoice {invoice.invoice_number}. Remaining: GHS {invoice.balance_due}."
            )
            return ReconciliationResult(
                status=PaymentStatusChoices.PARTIAL,
                payment=payment,
                journal_entry=journal_entry,
                invoice=invoice,
                is_suspense=False,
                notes=f"Partially paid. Remaining balance: GHS {invoice.balance_due:.4f}",
            )

        elif amount == balance_due:
            # --- Case A1: Exact Full Settlement ---
            with transaction.atomic():
                invoice.paid_amount = (invoice.paid_amount + amount).quantize(QUANTIZE_FOUR_PLACES)
                invoice.status = InvoiceStatusChoices.PAID
                invoice.save(update_fields=["paid_amount", "status", "updated_at"])

                lines_data = [
                    {
                        "account": momo_acc,
                        "debit": amount,
                        "description": (
                            f"MoMo settlement for Invoice {invoice.invoice_number} (Ref: {raw_ref})"
                        ),
                    },
                    {
                        "account": "1200",  # Accounts Receivable
                        "credit": amount,
                        "description": f"AR clearance for Invoice {invoice.invoice_number}",
                    },
                ]

                payment = Payment.objects.create(
                    organization=resolved_org,
                    customer=invoice.customer,
                    invoice=invoice,
                    amount=amount,
                    currency=currency_code,
                    payment_method=method,
                    transaction_type=PaymentTransactionTypeChoices.RECEIPT,
                    status=PaymentStatusChoices.SETTLED,
                    reference_number=event.event_id,
                    payment_reference=raw_ref,
                    transaction_date=event.paid_at or timezone.now(),
                    reconciliation_notes="Invoice settled in full.",
                    raw_event=event.raw_payload,
                )

                journal_entry = LedgerService.post_journal_entry(
                    organization=resolved_org,
                    entry_date=clearing_date,
                    lines_data=lines_data,
                    narration=(
                        f"MoMo settlement for Invoice {invoice.invoice_number} (Ref: {raw_ref})"
                    ),
                    source_type=SourceTypeChoices.PAYMENT,
                    source_id=payment.id,
                )

                payment.journal_entry = journal_entry
                payment.save(update_fields=["journal_entry"])

            logger.info(
                f"[{event.provider}] Reconciled FULL payment of GHS {amount} for "
                f"Invoice {invoice.invoice_number} -> PAID."
            )
            return ReconciliationResult(
                status=PaymentStatusChoices.SETTLED,
                payment=payment,
                journal_entry=journal_entry,
                invoice=invoice,
                is_suspense=False,
                notes="Invoice settled in full.",
            )

        else:
            # --- Case A3: Overpayment Handling (Refinement 1) ---
            # amount > balance_due: Split credit line between AR 1200 and Suspense Account 2150
            with transaction.atomic():
                excess = (amount - balance_due).quantize(QUANTIZE_FOUR_PLACES)
                invoice.paid_amount = invoice.total_amount
                invoice.status = InvoiceStatusChoices.PAID
                invoice.save(update_fields=["paid_amount", "status", "updated_at"])

                lines_data = [
                    {
                        "account": momo_acc,
                        "debit": amount,
                        "description": (
                            f"MoMo collection for Invoice {invoice.invoice_number} (Ref: {raw_ref})"
                        ),
                    },
                    {
                        "account": "1200",  # Accounts Receivable
                        "credit": balance_due,
                        "description": f"AR settlement for Invoice {invoice.invoice_number}",
                    },
                    {
                        "account": "2150",  # Suspense Account
                        "credit": excess,
                        "description": (
                            f"Overpayment excess for Invoice {invoice.invoice_number} to Suspense"
                        ),
                    },
                ]

                payment = Payment.objects.create(
                    organization=resolved_org,
                    customer=invoice.customer,
                    invoice=invoice,
                    amount=amount,
                    currency=currency_code,
                    payment_method=method,
                    transaction_type=PaymentTransactionTypeChoices.RECEIPT,
                    status=PaymentStatusChoices.SETTLED,
                    reference_number=event.event_id,
                    payment_reference=raw_ref,
                    transaction_date=event.paid_at or timezone.now(),
                    reconciliation_notes=(
                        f"Invoice fully settled (GHS {balance_due:.4f}). "
                        f"Excess deposit of GHS {excess:.4f} routed to Suspense Account 2150."
                    ),
                    raw_event=event.raw_payload,
                )

                journal_entry = LedgerService.post_journal_entry(
                    organization=resolved_org,
                    entry_date=clearing_date,
                    lines_data=lines_data,
                    narration=(
                        f"MoMo settlement for Invoice {invoice.invoice_number} (Ref: {raw_ref}) - "
                        f"Excess GHS {excess} to Suspense 2150"
                    ),
                    source_type=SourceTypeChoices.PAYMENT,
                    source_id=payment.id,
                )

                payment.journal_entry = journal_entry
                payment.save(update_fields=["journal_entry"])

            logger.info(
                f"[{event.provider}] Reconciled OVERPAYMENT of GHS {amount} for "
                f"Invoice {invoice.invoice_number}. Excess GHS {excess} routed to Suspense 2150."
            )
            return ReconciliationResult(
                status=PaymentStatusChoices.SETTLED,
                payment=payment,
                journal_entry=journal_entry,
                invoice=invoice,
                is_suspense=False,
                excess_amount=excess,
                notes=f"Invoice fully paid; excess GHS {excess:.4f} routed to Suspense 2150.",
            )

    @classmethod
    def _route_to_suspense(
        cls,
        organization: Organization,
        event: NormalizedPaymentEvent,
        amount: Decimal,
        reason: str,
    ) -> ReconciliationResult:
        """Quarantines unidentified or erroneous funds to Suspense Account 2150.

        Guarantees that cash deposited into the merchant's MoMo wallet is never discarded
        and remains auditable on the double-entry balance sheet.
        """
        momo_acc = cls._resolve_clearing_account_code(organization)
        clearing_date = event.paid_at.date() if event.paid_at else timezone.now().date()
        method = map_provider_to_payment_method(
            event.raw_payload.get("channel")
            or event.raw_payload.get("data", {}).get("channel")
            or event.provider
        )

        lines_data = [
            {
                "account": momo_acc,
                "debit": amount,
                "description": f"Unreconciled MoMo deposit (Ref: {event.reference or 'NONE'})",
            },
            {
                "account": "2150",  # Suspense Account
                "credit": amount,
                "description": f"Suspense Account 2150 holding: {reason}",
            },
        ]

        with transaction.atomic():
            payment = Payment.objects.create(
                organization=organization,
                amount=amount,
                currency=(event.currency or "GHS").upper().strip(),
                payment_method=method,
                transaction_type=PaymentTransactionTypeChoices.RECEIPT,
                status=PaymentStatusChoices.SUSPENSE,
                reference_number=event.event_id,
                payment_reference=(event.reference or "").strip(),
                transaction_date=event.paid_at or timezone.now(),
                reconciliation_notes=reason,
                raw_event=event.raw_payload,
            )

            journal_entry = LedgerService.post_journal_entry(
                organization=organization,
                entry_date=clearing_date,
                lines_data=lines_data,
                narration=(
                    f"Unreconciled MoMo deposit (Ref: {event.reference or 'NONE'}) - "
                    "Suspense Account 2150"
                ),
                source_type=SourceTypeChoices.PAYMENT,
                source_id=payment.id,
            )

            payment.journal_entry = journal_entry
            payment.save(update_fields=["journal_entry"])

        logger.warning(
            f"[{event.provider}] QUARANTINED TO SUSPENSE 2150: amount=GHS {amount}, "
            f"ref='{event.reference}', reason: {reason}"
        )

        return ReconciliationResult(
            status=PaymentStatusChoices.SUSPENSE,
            payment=payment,
            journal_entry=journal_entry,
            invoice=None,
            is_suspense=True,
            notes=reason,
        )
