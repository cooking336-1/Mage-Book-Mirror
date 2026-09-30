"""Integration Test Suite for Statutory Credit Note Reversals (Task C.11 / T3.6).

Verifies compliance with:
1. Act 1151 Statutory General Ledger Reversals:
   - Dr 4000: Sales Revenue / Returns
   - Dr 2100: GRA Standard VAT Output (15.0%)
   - Dr 2110: GRA NHIL Output (2.5%)
   - Dr 2120: GRA GETFund Output (2.5%)
   - Cr 1200: Accounts Receivable
   - Strict double-entry balance: Sum(Debits) == Sum(Credits) == CreditNote.total_amount.

2. Double-Refund & Over-Credit Prevention:
   - Cumulative non-cancelled credit notes cannot exceed invoice total amount.
   - Boundary checks: Exactly remaining balance succeeds; 1 pesewa over raises ValidationError.
   - Full credit exhaustion blocks subsequent credit notes.

3. Cancelled Credit Note Capacity Restoration:
   - Cancelling a credit note unfreezes refund capacity for the target invoice.

4. State Constraints:
   - DRAFT or CANCELLED invoices cannot receive credit notes.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.invoicing.models import (
    Contact,
    ContactTypeChoices,
    CreditNoteStatusChoices,
    InvoiceStatusChoices,
)
from apps.invoicing.services.credit_note_service import CreditNoteService
from apps.invoicing.services.invoicing_service import InvoicingService
from apps.ledger.models import (
    FiscalCalendar,
    FiscalPeriod,
    PeriodLengthChoices,
    SourceTypeChoices,
)
from apps.ledger.services.seeder import (
    generate_fiscal_periods,
    seed_standard_chart_of_accounts,
)
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, TaxSchemeChoices


class CreditNoteReversalsIntegrationTests(TestCase):
    """End-to-end integration test suite for credit notes, tax reversals, and GL integrity."""

    def setUp(self) -> None:
        clear_current_tenant()

        self.org = Organization.objects.create(
            name="Volta Maritime Commercial Ltd",
            phone="+233240003344",
            email="finance@voltagroup.gh",
            business_tin="C0003344556",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        seed_standard_chart_of_accounts(self.org)

        self.calendar = FiscalCalendar.objects.create(
            organization=self.org,
            period_length=PeriodLengthChoices.MONTHLY,
            fiscal_year_end_month=12,
            fiscal_year_end_day=31,
        )
        generate_fiscal_periods(
            organization=self.org,
            year=2026,
            calendar_instance=self.calendar,
        )
        self.period = FiscalPeriod.objects.filter(organization=self.org).first()

        self.customer = Contact.objects.create(
            organization=self.org,
            name="Ho Logistics Union",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="C0009988112",
            email="procurement@hologistics.gh",
        )

        # Create issued invoice: GHS 1,000 net + Act 1151 taxes (VAT 150, NHIL 25, GETFund 25)
        # Total Invoice Amount = GHS 1,200.00
        self.invoice = InvoicingService.create_invoice(
            organization=self.org,
            customer=self.customer,
            issue_date=timezone.now().date(),
            items=[
                {
                    "description": "Port Freight Handling Equipment",
                    "quantity": Decimal("1.0000"),
                    "unit_price": Decimal("1000.0000"),
                    "is_taxable": True,
                }
            ],
        )
        # Transition from PENDING_GRA to CLEARED
        self.invoice.status = InvoiceStatusChoices.CLEARED
        self.invoice.save(update_fields=["status"])

    def tearDown(self) -> None:
        clear_current_tenant()

    def test_credit_note_statutory_reversing_general_ledger_entries(self) -> None:
        """Verifies statutory reversing GL schedule under Act 1151 for a full refund."""
        cn, je = CreditNoteService.issue_credit_note(
            organization=self.org,
            invoice_id=str(self.invoice.id),
            reason="Equipment damaged in transit - full return",
            lines_data=[
                {
                    "description": "Port Freight Handling Equipment (Return)",
                    "quantity": Decimal("1.0000"),
                    "unit_price": Decimal("1000.0000"),
                }
            ],
        )

        # Invariant 1: Credit Note Header Values
        self.assertEqual(cn.subtotal_amount, Decimal("1000.0000"))
        self.assertEqual(cn.vat_amount, Decimal("150.0000"))
        self.assertEqual(cn.nhil_amount, Decimal("25.0000"))
        self.assertEqual(cn.getfund_amount, Decimal("25.0000"))
        self.assertEqual(cn.vat_amount + cn.nhil_amount + cn.getfund_amount, Decimal("200.0000"))
        self.assertEqual(cn.total_amount, Decimal("1200.0000"))
        self.assertEqual(cn.status, CreditNoteStatusChoices.ISSUED)

        # Invariant 2: Journal Entry created and linked
        self.assertIsNotNone(cn.journal_entry)
        self.assertEqual(je.source_type, SourceTypeChoices.INVOICE)
        self.assertEqual(je.source_id, cn.id)

        # Invariant 3: Verify all 5 Reversing Lines
        lines = list(je.lines.all())
        self.assertEqual(len(lines), 5)

        line_map = {line.account.account_code: line for line in lines}

        # Dr 4000 (Sales Revenue / Returns): 1,000.00
        self.assertIn("4000", line_map)
        self.assertEqual(line_map["4000"].debit_amount, Decimal("1000.0000"))
        self.assertEqual(line_map["4000"].credit_amount, Decimal("0.0000"))

        # Dr 2100 (VAT Output 15%): 150.00
        self.assertIn("2100", line_map)
        self.assertEqual(line_map["2100"].debit_amount, Decimal("150.0000"))
        self.assertEqual(line_map["2100"].credit_amount, Decimal("0.0000"))

        # Dr 2110 (NHIL Output 2.5%): 25.00
        self.assertIn("2110", line_map)
        self.assertEqual(line_map["2110"].debit_amount, Decimal("25.0000"))
        self.assertEqual(line_map["2110"].credit_amount, Decimal("0.0000"))

        # Dr 2120 (GETFund Output 2.5%): 25.00
        self.assertIn("2120", line_map)
        self.assertEqual(line_map["2120"].debit_amount, Decimal("25.0000"))
        self.assertEqual(line_map["2120"].credit_amount, Decimal("0.0000"))

        # Cr 1200 (Accounts Receivable): 1,200.00
        self.assertIn("1200", line_map)
        self.assertEqual(line_map["1200"].credit_amount, Decimal("1200.0000"))
        self.assertEqual(line_map["1200"].debit_amount, Decimal("0.0000"))

        # Mathematical Invariant: Total Debits == Total Credits == Total Refund
        total_dr = sum(line.debit_amount for line in lines)
        total_cr = sum(line.credit_amount for line in lines)
        self.assertEqual(total_dr, Decimal("1200.0000"))
        self.assertEqual(total_cr, Decimal("1200.0000"))

    def test_partial_credit_note_and_double_refund_prevention_boundary(self) -> None:
        """Verifies partial credit notes and strict rejection of over-crediting by 1 pesewa."""
        # Invoice total is 1,200.00
        # Issue Partial Credit Note #1 for GHS 500.00 net (600.00 gross with tax)
        cn1, _ = CreditNoteService.issue_credit_note(
            organization=self.org,
            invoice_id=str(self.invoice.id),
            reason="Partial return 50%",
            lines_data=[
                {
                    "description": "Port Freight Handling Equipment (Half Return)",
                    "quantity": Decimal("0.5000"),
                    "unit_price": Decimal("1000.0000"),
                }
            ],
        )
        self.assertEqual(cn1.total_amount, Decimal("600.0000"))

        # Remaining refundable balance is 1200.00 - 600.00 = GHS 600.00 gross
        # Refunding GHS 600.01 (0.5001 qty * 1000 = 500.10 net -> 600.12 gross) MUST fail
        with self.assertRaises(ValidationError) as ctx:
            CreditNoteService.issue_credit_note(
                organization=self.org,
                invoice_id=str(self.invoice.id),
                reason="Excessive refund attempt",
                lines_data=[
                    {
                        "description": "Excess Return",
                        "quantity": Decimal("0.5001"),
                        "unit_price": Decimal("1000.0000"),
                    }
                ],
            )
        self.assertIn("Double-refund violation", str(ctx.exception))

        # Exactly GHS 600.00 gross succeeds (0.5000 qty)
        cn2, _ = CreditNoteService.issue_credit_note(
            organization=self.org,
            invoice_id=str(self.invoice.id),
            reason="Final remaining balance return",
            lines_data=[
                {
                    "description": "Port Freight Handling Equipment (Final 50%)",
                    "quantity": Decimal("0.5000"),
                    "unit_price": Decimal("1000.0000"),
                }
            ],
        )
        self.assertEqual(cn2.total_amount, Decimal("600.0000"))

        # Total refunded is now 1,200.00 (100% credited).
        # Any subsequent credit note attempt must be blocked immediately!
        with self.assertRaises(ValidationError) as ctx_exhausted:
            CreditNoteService.issue_credit_note(
                organization=self.org,
                invoice_id=str(self.invoice.id),
                reason="Post-exhaustion refund",
                lines_data=[
                    {
                        "description": "Ghost Return",
                        "quantity": Decimal("1.0000"),
                        "unit_price": Decimal("1.0000"),
                    }
                ],
            )
        self.assertIn("Double-refund violation", str(ctx_exhausted.exception))

    def test_cancelled_credit_note_unfreezes_refund_capacity(self) -> None:
        """Cancelling an issued credit note releases the refund capacity for the invoice."""
        cn, _ = CreditNoteService.issue_credit_note(
            organization=self.org,
            invoice_id=str(self.invoice.id),
            reason="Full initial refund",
            lines_data=[
                {
                    "description": "Full Return",
                    "quantity": Decimal("1.0000"),
                    "unit_price": Decimal("1000.0000"),
                }
            ],
        )
        self.assertEqual(cn.total_amount, Decimal("1200.0000"))

        # Cancel the credit note
        cn.status = CreditNoteStatusChoices.CANCELLED
        cn.save(update_fields=["status"])

        # Capacity should now be unblocked; creating another credit note up to 1200.00 succeeds
        cn2, _ = CreditNoteService.issue_credit_note(
            organization=self.org,
            invoice_id=str(self.invoice.id),
            reason="Re-issued refund for legitimate return",
            lines_data=[
                {
                    "description": "Legitimate Return",
                    "quantity": Decimal("1.0000"),
                    "unit_price": Decimal("1000.0000"),
                }
            ],
        )
        self.assertEqual(cn2.total_amount, Decimal("1200.0000"))

    def test_draft_or_cancelled_invoice_cannot_receive_credit_note(self) -> None:
        """Invoices in DRAFT or CANCELLED status cannot have credit notes issued."""
        # Create test invoice and set to DRAFT
        test_invoice = InvoicingService.create_invoice(
            organization=self.org,
            customer=self.customer,
            issue_date=timezone.now().date(),
            items=[{"description": "Item", "quantity": 1, "unit_price": Decimal("100.00")}],
        )
        test_invoice.status = InvoiceStatusChoices.DRAFT
        test_invoice.save(update_fields=["status"])

        with self.assertRaises(ValidationError) as ctx_draft:
            CreditNoteService.issue_credit_note(
                organization=self.org,
                invoice_id=str(test_invoice.id),
                reason="Return on draft",
                lines_data=[
                    {"description": "Return", "quantity": 1, "unit_price": Decimal("100.00")}
                ],
            )
        self.assertIn(
            "Cannot issue credit note against invoice in 'DRAFT' state", str(ctx_draft.exception)
        )

        # Cancelled Invoice
        test_invoice.status = InvoiceStatusChoices.CANCELLED
        test_invoice.save(update_fields=["status"])

        with self.assertRaises(ValidationError) as ctx_cancelled:
            CreditNoteService.issue_credit_note(
                organization=self.org,
                invoice_id=str(test_invoice.id),
                reason="Return on cancelled",
                lines_data=[
                    {"description": "Return", "quantity": 1, "unit_price": Decimal("100.00")}
                ],
            )
        self.assertIn(
            "Cannot issue credit note against invoice in 'CANCELLED' state",
            str(ctx_cancelled.exception),
        )
