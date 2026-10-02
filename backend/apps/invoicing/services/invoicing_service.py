"""Invoicing Domain Service.

Coordinates:
1. Act 1151 statutory sales tax calculation and multi-line itemization.
2. Point-in-time customer legal identity snapshot freezing.
3. Automatic Luhn payment reference generation.
4. Atomic double-entry General Ledger journal posting (Dr 1200, Cr 4000, Cr 2100/2110/2120).
5. Asynchronous GRA E-VAT clearance task dispatching.
"""

import logging
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.invoicing.dispatchers import enqueue_gra_clearance
from apps.invoicing.models import (
    Contact,
    ContactTypeChoices,
    Invoice,
    InvoiceLine,
    InvoiceSequence,
    InvoiceStatusChoices,
)
from apps.ledger.models import ChartOfAccounts, SourceTypeChoices
from apps.ledger.services.ledger import LedgerService
from apps.ledger.services.seeder import seed_standard_chart_of_accounts
from apps.tax.services import (
    ACCOUNT_CODE_AR,
    ACCOUNT_CODE_GETFUND_OUTPUT,
    ACCOUNT_CODE_NHIL_OUTPUT,
    ACCOUNT_CODE_REVENUE_STANDARD,
    ACCOUNT_CODE_VAT_OUTPUT,
    STATUTORY_GETFUND_RATE,
    STATUTORY_NHIL_RATE,
    STATUTORY_VAT_RATE,
    LineTaxItem,
    TaxBreakdown,
    TaxCalculationEngine,
)
from apps.tenancy.models import Organization, TaxSchemeChoices

logger = logging.getLogger(__name__)


def ensure_organization_tax_accounts(organization: Organization) -> dict[str, ChartOfAccounts]:
    """Ensures standard Chart of Accounts (1200, 4000, 2100, 2110, 2120) exist for the organization.

    If any are missing, seeds the standard Ghanaian Chart of Accounts idempotently.
    """
    needed_codes = [
        ACCOUNT_CODE_AR,
        ACCOUNT_CODE_REVENUE_STANDARD,
        ACCOUNT_CODE_VAT_OUTPUT,
        ACCOUNT_CODE_NHIL_OUTPUT,
        ACCOUNT_CODE_GETFUND_OUTPUT,
    ]

    accounts = {
        acc.account_code: acc
        for acc in ChartOfAccounts.objects.filter(
            organization=organization,
            account_code__in=needed_codes,
        )
    }

    missing_codes = [code for code in needed_codes if code not in accounts]
    if missing_codes:
        # Auto-seed standard Ghanaian chart of accounts
        seed_standard_chart_of_accounts(organization)
        accounts = {
            acc.account_code: acc
            for acc in ChartOfAccounts.objects.filter(
                organization=organization,
                account_code__in=needed_codes,
            )
        }

    return accounts


class InvoicingService:
    """Core domain service for Invoice creation, tax breakdown, and General Ledger posting."""

    @classmethod
    def _validate_customer(
        cls,
        organization: Organization,
        customer_id: Any,
    ) -> Contact:
        """Validates that customer exists and belongs to the given tenant."""
        customer = Contact.objects.filter(id=customer_id, organization=organization).first()
        if not customer:
            raise ValidationError(
                {"customer_id": "Customer does not exist or does not belong to this organization."}
            )
        return customer

    @classmethod
    def _compile_tax_lines(
        cls,
        organization: Organization,
        lines_data: list[dict[str, Any]],
    ) -> tuple[Any, TaxBreakdown]:
        """Calculates multi-line taxes using the Act 1151 TaxCalculationEngine."""
        if not lines_data:
            raise ValidationError({"lines": "At least one invoice line item is required."})

        tax_lines_input: list[LineTaxItem] = []
        for idx, line in enumerate(lines_data):
            qty = Decimal(str(line["quantity"]))
            unit_price = Decimal(str(line["unit_price"]))
            supply_type = line.get("supply_type", TaxSchemeChoices.STANDARD)
            is_taxable = supply_type != TaxSchemeChoices.EXEMPT

            tax_lines_input.append(
                LineTaxItem(
                    description=line["description"],
                    quantity=qty,
                    unit_price=unit_price,
                    supply_type=supply_type,
                    is_taxable=is_taxable,
                    line_id=str(idx),
                )
            )

        tax_summary = TaxCalculationEngine.calculate_line_taxes(
            lines=tax_lines_input,
            organization=organization,
        )

        aggregate_breakdown = TaxBreakdown(
            taxable_amount=tax_summary.total_subtotal,
            vat_amount=tax_summary.total_vat,
            nhil_amount=tax_summary.total_nhil,
            getfund_amount=tax_summary.total_getfund,
            total_tax=tax_summary.total_tax,
            gross_amount=tax_summary.total_gross,
            effective_rate=Decimal("0.2000"),
        )
        return tax_summary, aggregate_breakdown

    @classmethod
    def _persist_invoice(
        cls,
        organization: Organization,
        customer: Contact,
        data: dict[str, Any],
        invoice_number: str,
        aggregate_breakdown: TaxBreakdown,
    ) -> Invoice:
        """Instantiates and saves the parent Invoice record with frozen snapshot."""
        currency = data.get("currency", "GHS")
        issue_date = data["issue_date"]

        invoice = Invoice(
            organization=organization,
            customer=customer,
            invoice_number=invoice_number,
            issue_date=issue_date,
            due_date=data["due_date"],
            currency=currency,
            subtotal_amount=aggregate_breakdown.taxable_amount,
            vat_amount=aggregate_breakdown.vat_amount,
            nhil_amount=aggregate_breakdown.nhil_amount,
            getfund_amount=aggregate_breakdown.getfund_amount,
            covid_levy_amount=Decimal("0.0000"),
            total_amount=aggregate_breakdown.gross_amount,
            paid_amount=Decimal("0.0000"),
            status=InvoiceStatusChoices.DRAFT,
        )
        invoice.freeze_customer_snapshot(force=True)
        invoice.save()
        return invoice

    @classmethod
    def _persist_invoice_lines(
        cls,
        organization: Organization,
        invoice: Invoice,
        lines_data: list[dict[str, Any]],
        tax_summary: Any,
    ) -> list[InvoiceLine]:
        """Creates and links all child InvoiceLine item rows."""
        created_lines: list[InvoiceLine] = []
        for idx, line in enumerate(lines_data):
            line_breakdown = tax_summary.line_breakdowns[idx]
            account_id = line.get("account_id")
            line_account = None

            if account_id:
                line_account = ChartOfAccounts.objects.filter(
                    id=account_id, organization=organization
                ).first()
                if not line_account:
                    raise ValidationError(
                        {"account_id": f"Account {account_id} not found in this organization."}
                    )

            inv_line = InvoiceLine(
                organization=organization,
                invoice=invoice,
                description=line["description"],
                quantity=Decimal(str(line["quantity"])),
                unit_price=Decimal(str(line["unit_price"])),
                vat_rate=(
                    STATUTORY_VAT_RATE if line_breakdown.vat_amount > 0 else Decimal("0.0000")
                ),
                nhil_rate=(
                    STATUTORY_NHIL_RATE if line_breakdown.nhil_amount > 0 else Decimal("0.0000")
                ),
                getfund_rate=(
                    STATUTORY_GETFUND_RATE
                    if line_breakdown.getfund_amount > 0
                    else Decimal("0.0000")
                ),
                vat_amount=line_breakdown.vat_amount,
                nhil_amount=line_breakdown.nhil_amount,
                getfund_amount=line_breakdown.getfund_amount,
                line_total=line_breakdown.gross_amount,
                account=line_account,
            )
            inv_line.save()
            created_lines.append(inv_line)
        return created_lines

    @classmethod
    def _post_and_enqueue_issue(
        cls,
        organization: Organization,
        invoice: Invoice,
        aggregate_breakdown: TaxBreakdown,
        user: Any,
    ) -> None:
        """Posts invoice journal entries to the GL and enqueues GRA clearance."""
        cls._post_invoice_to_ledger(
            organization=organization,
            invoice=invoice,
            tax_breakdown=aggregate_breakdown,
            user=user,
        )
        invoice.status = InvoiceStatusChoices.PENDING_GRA
        invoice.save(update_fields=["status"])

        invoice_id = invoice.id
        transaction.on_commit(lambda: enqueue_gra_clearance(invoice_id))

    @classmethod
    def create_and_post_invoice(
        cls,
        organization: Organization,
        user: Any,
        data: dict[str, Any],
    ) -> Invoice:
        """Compiles, calculates, freezes snapshots, and atomically posts an invoice.

        Parameters:
            organization: Authenticated tenant organization.
            user: Initiating user.
            data: Validated dictionary from InvoiceCreateSerializer.

        Returns:
            The created Invoice instance.
        """
        customer = cls._validate_customer(organization, data["customer_id"])
        tax_summary, aggregate_breakdown = cls._compile_tax_lines(organization, data["lines"])

        action = data.get("action", "issue")
        issue_date = data["issue_date"]

        with transaction.atomic():
            invoice_number = cls._generate_sequential_invoice_number(
                organization=organization,
                issue_date=issue_date,
            )
            invoice = cls._persist_invoice(
                organization=organization,
                customer=customer,
                data=data,
                invoice_number=invoice_number,
                aggregate_breakdown=aggregate_breakdown,
            )
            cls._persist_invoice_lines(
                organization=organization,
                invoice=invoice,
                lines_data=data["lines"],
                tax_summary=tax_summary,
            )

            if action == "issue":
                cls._post_and_enqueue_issue(
                    organization=organization,
                    invoice=invoice,
                    aggregate_breakdown=aggregate_breakdown,
                    user=user,
                )

        return invoice

    @classmethod
    def issue_draft_invoice(
        cls,
        invoice: Invoice,
        user: Any,
    ) -> Invoice:
        """Transitions a draft invoice to PENDING_GRA and posts to General Ledger."""
        if invoice.status != InvoiceStatusChoices.DRAFT:
            raise ValidationError(
                {"status": f"Only DRAFT invoices can be issued. Current status: {invoice.status}"}
            )

        # Reconstruct TaxBreakdown from stored invoice totals
        tax_breakdown = TaxBreakdown(
            taxable_amount=invoice.subtotal_amount,
            vat_amount=invoice.vat_amount,
            nhil_amount=invoice.nhil_amount,
            getfund_amount=invoice.getfund_amount,
            total_tax=invoice.vat_amount + invoice.nhil_amount + invoice.getfund_amount,
            gross_amount=invoice.total_amount,
            effective_rate=Decimal("0.2000"),
        )

        with transaction.atomic():
            cls._post_invoice_to_ledger(
                organization=invoice.organization,
                invoice=invoice,
                tax_breakdown=tax_breakdown,
                user=user,
            )

            invoice.status = InvoiceStatusChoices.PENDING_GRA
            invoice.save(update_fields=["status"])

            # Enqueue asynchronous GRA clearance strictly after transaction commit
            invoice_id = invoice.id
            transaction.on_commit(lambda: enqueue_gra_clearance(invoice_id))

        return invoice

    @classmethod
    def _post_invoice_to_ledger(
        cls,
        organization: Organization,
        invoice: Invoice,
        tax_breakdown: Any,
        user: Any,
    ) -> Any:
        """Resolves standard chart of accounts and posts balanced journal lines to LedgerService."""
        accounts = ensure_organization_tax_accounts(organization)

        ar_account = accounts[ACCOUNT_CODE_AR]
        revenue_account = accounts[ACCOUNT_CODE_REVENUE_STANDARD]
        vat_account = accounts.get(ACCOUNT_CODE_VAT_OUTPUT)
        nhil_account = accounts.get(ACCOUNT_CODE_NHIL_OUTPUT)
        getfund_account = accounts.get(ACCOUNT_CODE_GETFUND_OUTPUT)

        ledger_lines = TaxCalculationEngine.get_invoice_ledger_lines(
            tax_breakdown=tax_breakdown,
            ar_account=ar_account,
            revenue_account=revenue_account,
            vat_account=vat_account,
            nhil_account=nhil_account,
            getfund_account=getfund_account,
            narration=f"Invoice {invoice.invoice_number}",
        )

        journal_entry = LedgerService.post_journal_entry(
            organization=organization,
            entry_date=invoice.issue_date,
            lines_data=ledger_lines,
            narration=f"Tax Invoice {invoice.invoice_number} - {invoice.customer_name}",
            user=user,
            source_type=SourceTypeChoices.INVOICE,
            source_id=invoice.id,
        )

        logger.info(
            "Posted balanced journal entry %s for invoice %s",
            journal_entry.entry_number,
            invoice.invoice_number,
        )
        return journal_entry

    @classmethod
    def _generate_sequential_invoice_number(
        cls,
        organization: Organization,
        issue_date: Any,
    ) -> str:
        """Generates a strictly gapless, collision-proof invoice number using row-level locking.

        Under Ghanaian statutory regulations (Act 1151 / GRA CIS), invoice sequences
        must be strictly chronological and gapless. Acquiring a row-level lock on the
        tenant's yearly InvoiceSequence record inside transaction.atomic() guarantees
        zero duplicate key collisions and strictly sequential numbers even under heavy
        concurrent load.
        """
        year = issue_date.year
        seq, created = InvoiceSequence.objects.select_for_update().get_or_create(
            organization=organization,
            year=year,
            defaults={"last_number": 0},
        )
        if created:
            # Synchronize with any pre-existing invoices for this organization and year
            existing_count = Invoice.objects.filter(
                organization=organization,
                issue_date__year=year,
            ).count()
            if existing_count > 0:
                seq.last_number = existing_count

        seq.last_number += 1
        seq.save(update_fields=["last_number", "updated_at"])

        org_slug = getattr(organization, "slug", None)
        if org_slug:
            return f"INV-{str(org_slug).upper()}-{year}-{seq.last_number:05d}"
        return f"INV-{year}-{seq.last_number:05d}"

    @classmethod
    @transaction.atomic
    def create_invoice(
        cls,
        organization: Organization,
        user: Any = None,
        data: dict[str, Any] | None = None,
        customer: Contact | None = None,
        issue_date: Any = None,
        due_date: Any = None,
        items: list[dict[str, Any]] | None = None,
        lines: list[dict[str, Any]] | None = None,
        currency: str = "GHS",
        action: str = "issue",
        **kwargs: Any,
    ) -> Invoice:
        """Convenience interface for invoice creation supporting dictionary or keyword arguments."""
        payload: dict[str, Any] = dict(data) if data is not None else {}

        if issue_date is not None:
            payload["issue_date"] = issue_date
        elif "issue_date" not in payload:
            from django.utils import timezone

            payload["issue_date"] = timezone.now().date()

        if due_date is not None:
            payload["due_date"] = due_date
        elif "due_date" not in payload:
            payload["due_date"] = payload["issue_date"]

        lines_list = items or lines or payload.get("lines") or payload.get("items") or []
        payload["lines"] = lines_list

        if customer is not None:
            payload["customer_id"] = str(customer.id)
        elif "customer_id" not in payload:
            default_customer = Contact.objects.filter(
                organization=organization,
                contact_type__in=[ContactTypeChoices.CUSTOMER, ContactTypeChoices.BOTH],
                is_active=True,
            ).first()
            if not default_customer:
                default_customer = Contact.objects.create(
                    organization=organization,
                    name=f"Customer - {organization.name}",
                    contact_type=ContactTypeChoices.CUSTOMER,
                )
            payload["customer_id"] = str(default_customer.id)

        payload.setdefault("currency", currency)
        payload.setdefault("action", action)

        return cls.create_and_post_invoice(organization=organization, user=user, data=payload)
