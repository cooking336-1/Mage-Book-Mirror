"""Unit test suite for decomposed service orchestrator helpers (Task D.7 / B14).

Verifies that the private modular helper methods in InvoicingService,
LedgerService, and PayrollDisbursementService enforce their accounting,
tenancy, and validation invariants in isolation.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import CustomUser
from apps.invoicing.models import Contact, ContactTypeChoices, InvoiceStatusChoices
from apps.invoicing.services.invoicing_service import InvoicingService
from apps.ledger.models import (
    ChartOfAccounts,
    FiscalCalendar,
    FiscalPeriod,
    PeriodLengthChoices,
)
from apps.ledger.services.ledger import LedgerService
from apps.ledger.services.seeder import (
    generate_fiscal_periods,
    seed_standard_chart_of_accounts,
)
from apps.payroll.models import PayrollRun, PayrollStatusChoices
from apps.payroll.services.disbursement import PayrollDisbursementService
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, TaxSchemeChoices


class DecomposedHelpersUnitTests(TestCase):
    """Verifies domain invariants of decomposed service helpers."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.org = Organization.objects.create(
            name="Decomposed Services Test Org Ltd",
            phone="+233240008899",
            email="test_decomposed@example.com",
            business_tin="C0012399999",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        self.other_org = Organization.objects.create(
            name="Other Tenant Org Ltd",
            phone="+233240008800",
            email="other_tenant@example.com",
            business_tin="C0012300000",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        seed_standard_chart_of_accounts(self.org)
        seed_standard_chart_of_accounts(self.other_org)

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
        self.period = FiscalPeriod.objects.filter(
            calendar=self.calendar, is_closed=False
        ).first()

        self.maker = CustomUser.objects.create_user(
            email="maker@example.com",
            password="SecurePassword123!",
            first_name="Kwame",
            last_name="Maker",
        )

        self.customer = Contact.objects.create(
            organization=self.org,
            name="Accra Commercial Logistics",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="C0000111222",
            email="client@example.com",
        )

    # =========================================================================
    # InvoicingService Decomposed Helpers
    # =========================================================================

    def test_invoicing_validate_customer_success(self) -> None:
        """_validate_customer returns the customer when valid and matching tenant."""
        found = InvoicingService._validate_customer(self.org, self.customer.id)
        self.assertEqual(found.id, self.customer.id)

    def test_invoicing_validate_customer_cross_tenant_rejected(self) -> None:
        """_validate_customer rejects a customer belonging to another organization."""
        other_customer = Contact.objects.create(
            organization=self.other_org,
            name="Foreign Customer",
            contact_type=ContactTypeChoices.CUSTOMER,
        )
        with self.assertRaises(ValidationError) as ctx:
            InvoicingService._validate_customer(self.org, other_customer.id)
        self.assertIn("customer_id", ctx.exception.message_dict)

    def test_invoicing_validate_customer_nonexistent_rejected(self) -> None:
        """_validate_customer rejects an unknown UUID."""
        with self.assertRaises(ValidationError) as ctx:
            InvoicingService._validate_customer(self.org, uuid.uuid4())
        self.assertIn("customer_id", ctx.exception.message_dict)

    def test_invoicing_compile_tax_lines_empty_rejected(self) -> None:
        """_compile_tax_lines raises ValidationError when no lines provided."""
        with self.assertRaises(ValidationError) as ctx:
            InvoicingService._compile_tax_lines(self.org, [])
        self.assertIn("lines", ctx.exception.message_dict)

    def test_invoicing_compile_tax_lines_computes_breakdown(self) -> None:
        """_compile_tax_lines accurately invokes TaxCalculationEngine."""
        lines_data = [
            {"description": "IT Support", "quantity": 2, "unit_price": "100.00"},
            {"description": "Consulting", "quantity": 1, "unit_price": "300.00"},
        ]
        tax_summary, breakdown = InvoicingService._compile_tax_lines(self.org, lines_data)
        self.assertEqual(breakdown.taxable_amount, Decimal("500.00"))
        self.assertTrue(breakdown.total_tax > Decimal("0.00"))
        self.assertEqual(
            breakdown.gross_amount,
            breakdown.taxable_amount + breakdown.total_tax,
        )

    def test_invoicing_persist_invoice_creates_draft_with_snapshot(self) -> None:
        """_persist_invoice creates an Invoice in DRAFT status with frozen snapshot."""
        lines_data = [{"description": "Service", "quantity": 1, "unit_price": "100.00"}]
        _, breakdown = InvoicingService._compile_tax_lines(self.org, lines_data)
        payload = {
            "customer_id": str(self.customer.id),
            "issue_date": timezone.now().date(),
            "due_date": timezone.now().date() + timezone.timedelta(days=30),
            "currency": "GHS",
        }
        inv = InvoicingService._persist_invoice(
            organization=self.org,
            customer=self.customer,
            data=payload,
            invoice_number="INV-2026-TEST-001",
            aggregate_breakdown=breakdown,
        )
        self.assertEqual(inv.status, InvoiceStatusChoices.DRAFT)
        self.assertEqual(inv.invoice_number, "INV-2026-TEST-001")
        self.assertEqual(inv.customer_name, "Accra Commercial Logistics")
        self.assertIsNotNone(inv.snapshot_frozen_at)

    # =========================================================================
    # LedgerService Decomposed Helpers
    # =========================================================================

    def test_ledger_validate_and_resolve_period_auto_resolution(self) -> None:
        """_validate_and_resolve_period resolves open period matching entry date."""
        today = self.period.start_date + timezone.timedelta(days=2)
        resolved = LedgerService._validate_and_resolve_period(self.org, today, None)
        self.assertEqual(resolved.id, self.period.id)

    def test_ledger_validate_and_resolve_period_closed_rejected(self) -> None:
        """_validate_and_resolve_period rejects a closed accounting period."""
        self.period.is_closed = True
        self.period.save(update_fields=["is_closed"])
        today = self.period.start_date + timezone.timedelta(days=2)
        with self.assertRaises(ValidationError) as ctx:
            LedgerService._validate_and_resolve_period(self.org, today, self.period)
        self.assertIn("closed", str(ctx.exception).lower())

    def test_ledger_parse_and_validate_lines_unbalanced_rejected(self) -> None:
        """_parse_and_validate_lines enforces Sum(Debits) == Sum(Credits)."""
        acc_id1 = uuid.uuid4()
        acc_id2 = uuid.uuid4()
        unbalanced_lines = [
            {"account": acc_id1, "debit": "100.00", "credit": "0.00"},
            {"account": acc_id2, "debit": "0.00", "credit": "50.00"},
        ]
        with self.assertRaises(ValidationError) as ctx:
            LedgerService._parse_and_validate_lines(unbalanced_lines)
        self.assertIn("unbalanced journal entry", str(ctx.exception).lower())

    def test_ledger_parse_and_validate_lines_negative_amount_rejected(self) -> None:
        """_parse_and_validate_lines rejects negative amounts."""
        acc_id1 = uuid.uuid4()
        acc_id2 = uuid.uuid4()
        bad_lines = [
            {"account": acc_id1, "debit": "-10.00", "credit": "0.00"},
            {"account": acc_id2, "debit": "0.00", "credit": "10.00"},
        ]
        with self.assertRaises(ValidationError) as ctx:
            LedgerService._parse_and_validate_lines(bad_lines)
        self.assertIn("negative debit or credit amounts", str(ctx.exception).lower())

    def test_ledger_resolve_and_validate_accounts_cross_tenant_rejected(self) -> None:
        """_resolve_and_validate_accounts rejects accounts from another tenant."""
        other_acc = ChartOfAccounts.objects.filter(organization=self.other_org).first()
        with self.assertRaises(ValidationError) as ctx:
            LedgerService._resolve_and_validate_accounts(self.org, [other_acc.id])
        self.assertIn("belong to another organization", str(ctx.exception).lower())

    # =========================================================================
    # PayrollDisbursementService Decomposed Helpers
    # =========================================================================

    def test_payroll_validate_run_for_disbursement_unapproved_rejected(self) -> None:
        """_validate_run_for_disbursement rejects runs in DRAFT or PENDING_APPROVAL status."""
        payroll_run = PayrollRun.objects.create(
            organization=self.org,
            period=self.period,
            maker=self.maker,
            status=PayrollStatusChoices.PENDING_APPROVAL,
        )
        with self.assertRaises(ValidationError) as ctx:
            PayrollDisbursementService._validate_run_for_disbursement(
                str(payroll_run.id), str(self.org.id)
            )
        self.assertIn("must be approved", str(ctx.exception).lower())

    def test_payroll_resolve_disbursement_accounts_success(self) -> None:
        """_resolve_disbursement_accounts returns net payable and payout source accounts."""
        payable, payout = PayrollDisbursementService._resolve_disbursement_accounts(self.org)
        self.assertIsNotNone(payable)
        self.assertIsNotNone(payout)
        self.assertEqual(payable.organization, self.org)
        self.assertEqual(payout.organization, self.org)
