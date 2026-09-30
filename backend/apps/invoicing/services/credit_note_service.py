"""Credit Note Domain Service & Statutory Act 1151 Reversal Engine.

Satisfies:
- Master Sprint Plan v3.0 Task C.2 (Feature G2)
- Ghana Value Added Tax Act, 2025 (Act 1151)
- Double-refund prevention with pessimistic row-level locking (select_for_update)
- Statutory Ghanaian Reversing General Ledger Schedule:
    Debit: 4000 (Sales Revenue / Returns)
    Debit: 2100 (GRA Standard VAT Output — 15.0%)
    Debit: 2110 (GRA NHIL Output — 2.5%)
    Debit: 2120 (GRA GETFund Output — 2.5%)
    Credit: 1200 (Accounts Receivable)
    Invariant: Sum(Debits) == Sum(Credits) == CreditNote.total_amount
- Immutable Forensic Audit Trail recording
"""

import datetime
import logging
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.audit.models import AuditTrail
from apps.invoicing.models import (
    CreditNote,
    CreditNoteLine,
    CreditNoteSequence,
    CreditNoteStatusChoices,
    Invoice,
    InvoiceStatusChoices,
)
from apps.ledger.models import (
    AccountCategory,
    CategoryCodeChoices,
    ChartOfAccounts,
    FiscalPeriod,
    JournalEntry,
    SourceTypeChoices,
)
from apps.ledger.services.ledger import LedgerService
from apps.tax.services import (
    STATUTORY_GETFUND_RATE,
    STATUTORY_NHIL_RATE,
    STATUTORY_VAT_RATE,
)

logger = logging.getLogger(__name__)

ZERO_MONEY = Decimal("0.0000")
FOUR_DECIMALS = Decimal("0.0001")


def _get_or_create_account(
    organization: Any,
    code: str,
    name: str,
    category_code: str,
) -> ChartOfAccounts:
    """Helper ensuring mandatory standard ledger accounts exist for reversing entries."""
    account = ChartOfAccounts.objects.filter(organization=organization, account_code=code).first()
    if account:
        return account

    category = AccountCategory.objects.filter(code=category_code).first()
    if not category:
        category = AccountCategory.objects.create(
            code=category_code,
            name="Income"
            if category_code == CategoryCodeChoices.INCOME
            else ("Liabilities" if category_code == CategoryCodeChoices.LIABILITIES else "Assets"),
            normal_balance=(
                "CREDIT"
                if category_code in (CategoryCodeChoices.INCOME, CategoryCodeChoices.LIABILITIES)
                else "DEBIT"
            ),
        )

    return ChartOfAccounts.objects.create(
        organization=organization,
        category=category,
        account_code=code,
        account_name=name,
        is_active=True,
    )


class CreditNoteService:
    """Orchestrates creation, validation, tax reversal, and ledger posting for credit notes."""

    @classmethod
    def generate_credit_note_number(
        cls,
        organization: Any,
        issue_date: datetime.date | None = None,
    ) -> str:
        """Generates a strictly gapless credit note number using row-level locking."""
        date_val = issue_date or timezone.now().date()
        year = date_val.year

        seq, created = CreditNoteSequence.objects.select_for_update().get_or_create(
            organization=organization,
            year=year,
            defaults={"last_number": 0},
        )
        if created:
            existing_count = CreditNote.objects.filter(
                organization=organization,
                issue_date__year=year,
            ).count()
            if existing_count > 0:
                seq.last_number = existing_count

        seq.last_number += 1
        seq.save(update_fields=["last_number", "updated_at"])

        return f"CN-{year}-{seq.last_number:05d}"

    @classmethod
    @transaction.atomic
    def issue_credit_note(
        cls,
        organization: Any,
        invoice_id: str,
        lines_data: list[dict[str, Any]],
        reason: str,
        user: Any = None,
        issue_date: datetime.date | None = None,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> tuple[CreditNote, JournalEntry]:
        """Issues a statutory credit note against an existing invoice with pessimistic row lock.

        Operational Lifecycle:
        1. Acquires select_for_update() row lock on target Invoice.
        2. Validates original invoice status (cannot credit DRAFT or CANCELLED).
        3. Double-Refund Defense: Sum(active CNs) + new CN total <= Invoice.total_amount.
        4. Calculates Act 1151 statutory tax reversals (15% VAT, 2.5% NHIL, 2.5% GETFund).
        5. Freezes point-in-time legal customer identity snapshot.
        6. Emits balanced double-entry reversing General Ledger entry:
           - Debit: 4000 (Sales Revenue / Returns)
           - Debit: 2100 (GRA Standard VAT Output — 15.0%)
           - Debit: 2110 (GRA NHIL Output — 2.5%)
           - Debit: 2120 (GRA GETFund Output — 2.5%)
           - Credit: 1200 (Accounts Receivable)
        7. Records immutable forensic AuditTrail entry.

        Args:
            organization: Tenant Organization instance.
            invoice_id: UUID string of original invoice.
            lines_data: List of line items [{description, quantity, unit_price}].
            reason: Commercial or statutory justification for credit note.
            user: Authenticated user authorizing the credit note.
            issue_date: Optional transaction date.
            ip_address: Client IP for audit forensics.
            user_agent: Client User-Agent string.

        Returns:
            tuple[CreditNote, JournalEntry]: Issued credit note and balanced reversing entry.

        Raises:
            ValidationError: If original invoice is invalid or cumulative cap is exceeded.
        """
        if not lines_data:
            raise ValidationError("A credit note must contain at least one line item.")

        date_val = issue_date or timezone.now().date()

        # 1. Pessimistic row-level lock on original Invoice
        try:
            invoice = (
                Invoice.objects.select_for_update()
                .select_related("organization", "customer")
                .get(id=invoice_id, organization=organization)
            )
        except Invoice.DoesNotExist as exc:
            raise ValidationError(
                f"Invoice '{invoice_id}' does not exist for organization '{organization.id}'."
            ) from exc

        # 2. Original Invoice Status Validation
        if invoice.status in (InvoiceStatusChoices.DRAFT, InvoiceStatusChoices.CANCELLED):
            raise ValidationError(
                f"Cannot issue credit note against invoice in '{invoice.status}' state. "
                "Invoice must be issued or cleared."
            )

        # 3. Compute Line Items and Act 1151 Tax Reversals
        total_subtotal = ZERO_MONEY
        total_vat = ZERO_MONEY
        total_nhil = ZERO_MONEY
        total_getfund = ZERO_MONEY
        computed_lines: list[dict[str, Any]] = []

        for line_data in lines_data:
            desc = line_data.get("description", "").strip()
            if not desc:
                raise ValidationError("Each credit note line must have a description.")

            qty = Decimal(str(line_data.get("quantity", "1.0000")))
            if qty <= ZERO_MONEY:
                raise ValidationError("Line quantity must be greater than zero.")

            price = Decimal(str(line_data.get("unit_price", "0.0000")))
            if price < ZERO_MONEY:
                raise ValidationError("Unit price cannot be negative.")

            line_subtotal = (qty * price).quantize(FOUR_DECIMALS)
            line_vat = (line_subtotal * STATUTORY_VAT_RATE).quantize(FOUR_DECIMALS)
            line_nhil = (line_subtotal * STATUTORY_NHIL_RATE).quantize(FOUR_DECIMALS)
            line_getfund = (line_subtotal * STATUTORY_GETFUND_RATE).quantize(FOUR_DECIMALS)
            line_total = line_subtotal + line_vat + line_nhil + line_getfund

            total_subtotal += line_subtotal
            total_vat += line_vat
            total_nhil += line_nhil
            total_getfund += line_getfund

            computed_lines.append(
                {
                    "description": desc,
                    "quantity": qty,
                    "unit_price": price,
                    "line_total": line_total,
                    "vat_rate": STATUTORY_VAT_RATE,
                    "nhil_rate": STATUTORY_NHIL_RATE,
                    "getfund_rate": STATUTORY_GETFUND_RATE,
                    "vat_amount": line_vat,
                    "nhil_amount": line_nhil,
                    "getfund_amount": line_getfund,
                }
            )

        new_total_credit = total_subtotal + total_vat + total_nhil + total_getfund

        # 4. Double-Refund / Cumulative Credit Cap Validation
        existing_active_cns = CreditNote.objects.filter(
            organization=organization,
            invoice=invoice,
        ).exclude(status=CreditNoteStatusChoices.CANCELLED)

        total_previously_credited = (
            existing_active_cns.aggregate(total=models.Sum("total_amount"))["total"] or ZERO_MONEY
        )

        if total_previously_credited + new_total_credit > invoice.total_amount:
            raise ValidationError(
                f"Double-refund violation: Cumulative credit notes "
                f"(GHS {total_previously_credited + new_total_credit}) "
                f"exceed original invoice total (GHS {invoice.total_amount})."
            )

        # 5. Generate gapless Credit Note Number
        cn_number = cls.generate_credit_note_number(organization, issue_date=date_val)

        # 6. Create CreditNote model
        credit_note = CreditNote.objects.create(
            organization=organization,
            credit_note_number=cn_number,
            invoice=invoice,
            customer=invoice.customer,
            issue_date=date_val,
            reason=reason,
            status=CreditNoteStatusChoices.ISSUED,
            currency=invoice.currency,
            subtotal_amount=total_subtotal,
            vat_amount=total_vat,
            nhil_amount=total_nhil,
            getfund_amount=total_getfund,
            total_amount=new_total_credit,
        )

        for line_item in computed_lines:
            CreditNoteLine.objects.create(
                organization=organization,
                credit_note=credit_note,
                **line_item,
            )

        # 7. Post Reversing Double-Entry General Ledger Schedule:
        # Resolve Statutory Ghanaian Accounts
        acc_sales_returns = _get_or_create_account(
            organization, "4000", "Sales Revenue / Returns", CategoryCodeChoices.INCOME
        )
        acc_vat_output = _get_or_create_account(
            organization, "2100", "GRA Standard VAT Output (15.0%)", CategoryCodeChoices.LIABILITIES
        )
        acc_nhil_output = _get_or_create_account(
            organization, "2110", "GRA NHIL Output (2.5%)", CategoryCodeChoices.LIABILITIES
        )
        acc_getfund_output = _get_or_create_account(
            organization, "2120", "GRA GETFund Output (2.5%)", CategoryCodeChoices.LIABILITIES
        )
        acc_receivable = _get_or_create_account(
            organization, "1200", "Accounts Receivable", CategoryCodeChoices.ASSETS
        )

        lines_data_gl: list[dict[str, Any]] = [
            # Debits (Reversals of Revenue and Tax Liabilities)
            {
                "account": acc_sales_returns,
                "debit": total_subtotal,
                "credit": ZERO_MONEY,
                "description": f"Sales Return / Credit - {cn_number}",
            },
            {
                "account": acc_vat_output,
                "debit": total_vat,
                "credit": ZERO_MONEY,
                "description": f"Reversal 15% VAT Output - {cn_number}",
            },
            {
                "account": acc_nhil_output,
                "debit": total_nhil,
                "credit": ZERO_MONEY,
                "description": f"Reversal 2.5% NHIL Output - {cn_number}",
            },
            {
                "account": acc_getfund_output,
                "debit": total_getfund,
                "credit": ZERO_MONEY,
                "description": f"Reversal 2.5% GETFund Output - {cn_number}",
            },
            # Credit (Reduction of Accounts Receivable)
            {
                "account": acc_receivable,
                "debit": ZERO_MONEY,
                "credit": new_total_credit,
                "description": f"AR Reversal Credit - {cn_number} on {invoice.invoice_number}",
            },
        ]

        # Resolve Fiscal Period
        fiscal_period = FiscalPeriod.objects.filter(
            organization=organization,
            start_date__lte=date_val,
            end_date__gte=date_val,
            is_closed=False,
        ).first()

        journal_entry = LedgerService.post_journal_entry(
            organization=organization,
            entry_date=date_val,
            lines_data=lines_data_gl,
            narration=f"Statutory Credit Note {cn_number} on {invoice.invoice_number}: {reason}",
            user=user,
            source_type=SourceTypeChoices.INVOICE,
            source_id=credit_note.id,
            period=fiscal_period,
        )

        credit_note.journal_entry = journal_entry
        credit_note.save(update_fields=["journal_entry", "updated_at"])

        # 8. Record Forensic Audit Trail
        AuditTrail.objects.create(
            organization=organization,
            user=user,
            action="CREDIT_NOTE_ISSUED",
            entity_type="CreditNote",
            entity_id=str(credit_note.id),
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "credit_note_number": cn_number,
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "total_amount": str(new_total_credit),
                "subtotal_amount": str(total_subtotal),
                "vat_amount": str(total_vat),
                "nhil_amount": str(total_nhil),
                "getfund_amount": str(total_getfund),
                "journal_entry_id": str(journal_entry.id),
            },
        )

        logger.info(
            "Credit Note %s issued on Invoice %s: GHS %s (JE: %s)",
            cn_number,
            invoice.invoice_number,
            new_total_credit,
            journal_entry.entry_number,
        )

        return credit_note, journal_entry
