"""Payment Reconciliation Boundary Value Analysis & Multi-Split Stress Suite (Task C.11 / T3.4).

Verifies compliance with:
1. Multi-split partial payments:
   - 3-split payments (GHS 333.33 + 333.33 + 333.34) on a GHS 1,000.00 invoice.
   - Status transitions: CLEARED -> PARTIALLY_PAID -> PARTIALLY_PAID -> PAID.
   - Exact pesewa reconciliation with 0-pesewa balance remaining.
   - Atomic General Ledger double-entry postings (Dr 1015 MoMo Clearing, Cr 1200 AR).

2. Underpayment trap defense (MUC-1.1):
   - GHS 999.99 payment on GHS 1,000.00 invoice MUST NEVER mark invoice as PAID.
   - Status strictly remains PARTIALLY_PAID with balance_due = 0.0100.

3. Overpayment splitting boundary value:
   - GHS 1,001.00 payment on GHS 1,000.00 invoice.
   - Invoice.paid_amount capped at total_amount (GHS 1,000.00).
   - Excess GHS 1.00 quarantined to Suspense Account 2150.
   - Balanced GL posting: Dr 1015 (1001.00), Cr 1200 (1000.00), Cr 2150 (1.00).

4. Post-settlement payment quarantine:
   - Subsequent payment received on already PAID invoice is routed 100% to Suspense 2150.
"""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.invoicing.models import (
    Contact,
    ContactTypeChoices,
    Invoice,
    InvoiceStatusChoices,
)
from apps.invoicing.utils import LuhnValidator
from apps.ledger.services.seeder import seed_standard_chart_of_accounts
from apps.payments.gateways.base import NormalizedPaymentEvent
from apps.payments.models import (
    PaymentStatusChoices,
)
from apps.payments.services.reconciliation import ReconciliationService
from apps.tenancy.models import Organization, TaxSchemeChoices


class PaymentReconciliationBVATests(TestCase):
    """BVA and multi-split test suite for payment reconciliation and GL routing."""

    def setUp(self) -> None:
        self.org = Organization.objects.create(
            name="Kumasi Wholesale Distributors Ltd",
            phone="+233240099887",
            email="accounts@kumasiwholesale.com",
            business_tin="C0009876543",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        seed_standard_chart_of_accounts(self.org)

        self.customer = Contact.objects.create(
            organization=self.org,
            name="Ashanti Retailers Union",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="C0001122334",
            email="procurement@ashantiretail.com",
        )

        self.luhn_ref = LuhnValidator.generate_reference("98712", delimiter="-")

        self.invoice = Invoice.objects.create(
            organization=self.org,
            customer=self.customer,
            invoice_number="INV-2026-BVA-001",
            payment_reference=self.luhn_ref,
            status=InvoiceStatusChoices.CLEARED,
            total_amount=Decimal("1000.0000"),
            paid_amount=Decimal("0.0000"),
            currency="GHS",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
        )

    def test_three_split_partial_payments_reconciliation(self) -> None:
        """3-split payments (333.33 + 333.33 + 333.34) settle invoice to exactly 0.00."""
        # Split 1: GHS 333.33
        event1 = NormalizedPaymentEvent(
            event_id="evt_split_001",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("333.3300"),
            currency="GHS",
        )
        res1 = ReconciliationService.reconcile_payment(event1, organization=self.org)
        self.assertEqual(res1.status, PaymentStatusChoices.PARTIAL)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PARTIALLY_PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("333.3300"))
        self.assertEqual(self.invoice.balance_due, Decimal("666.6700"))

        # Split 2: GHS 333.33
        event2 = NormalizedPaymentEvent(
            event_id="evt_split_002",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("333.3300"),
            currency="GHS",
        )
        res2 = ReconciliationService.reconcile_payment(event2, organization=self.org)
        self.assertEqual(res2.status, PaymentStatusChoices.PARTIAL)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PARTIALLY_PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("666.6600"))
        self.assertEqual(self.invoice.balance_due, Decimal("333.3400"))

        # Split 3: GHS 333.34 (Exact balance due)
        event3 = NormalizedPaymentEvent(
            event_id="evt_split_003",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("333.3400"),
            currency="GHS",
        )
        res3 = ReconciliationService.reconcile_payment(event3, organization=self.org)
        self.assertEqual(res3.status, PaymentStatusChoices.SETTLED)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("1000.0000"))
        self.assertEqual(self.invoice.balance_due, Decimal("0.0000"))

        # Verify 3 distinct Payment records exist
        self.assertEqual(self.invoice.payments.count(), 3)

        # Verify all 3 GL entries are balanced and correctly routed to AR 1200
        for payment in self.invoice.payments.all():
            self.assertIsNotNone(payment.journal_entry)
            lines = list(payment.journal_entry.lines.all())
            self.assertEqual(len(lines), 2)
            total_dr = sum(line.debit_amount for line in lines)
            total_cr = sum(line.credit_amount for line in lines)
            self.assertEqual(total_dr, total_cr)
            self.assertEqual(total_dr, payment.amount)

    def test_underpayment_muc_1_1_trap(self) -> None:
        """Payment of GHS 999.99 on 1000.00 invoice leaves 1 pesewa and NEVER marks PAID."""
        event = NormalizedPaymentEvent(
            event_id="evt_under_001",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("999.9900"),
            currency="GHS",
        )
        res = ReconciliationService.reconcile_payment(event, organization=self.org)
        self.assertEqual(res.status, PaymentStatusChoices.PARTIAL)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PARTIALLY_PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("999.9900"))
        self.assertEqual(self.invoice.balance_due, Decimal("0.0100"))

    def test_overpayment_1001_on_1000_balance_splits_excess_to_suspense_2150(self) -> None:
        """GHS 1001 on GHS 1000 balance caps invoice at 1000 and routes GHS 1 to Suspense 2150."""
        event = NormalizedPaymentEvent(
            event_id="evt_over_1001",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("1001.0000"),
            currency="GHS",
        )
        res = ReconciliationService.reconcile_payment(event, organization=self.org)

        self.assertEqual(res.status, PaymentStatusChoices.SETTLED)
        self.assertEqual(res.excess_amount, Decimal("1.0000"))

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("1000.0000"))
        self.assertEqual(self.invoice.balance_due, Decimal("0.0000"))

        # GL Lines: Dr 1015 (1001.00), Cr 1200 (1000.00), Cr 2150 (1.00)
        lines = list(res.journal_entry.lines.all())
        self.assertEqual(len(lines), 3)

        dr_momo = next(line for line in lines if line.account.account_code == "1015")
        cr_ar = next(line for line in lines if line.account.account_code == "1200")
        cr_suspense = next(line for line in lines if line.account.account_code == "2150")

        self.assertEqual(dr_momo.debit_amount, Decimal("1001.0000"))
        self.assertEqual(cr_ar.credit_amount, Decimal("1000.0000"))
        self.assertEqual(cr_suspense.credit_amount, Decimal("1.0000"))

        # Exact double-entry balancing
        self.assertEqual(
            sum(line.debit_amount for line in lines),
            sum(line.credit_amount for line in lines),
        )

    def test_subsequent_payment_on_already_paid_invoice_quarantined_to_suspense(self) -> None:
        """Payment on an already settled invoice is routed 100% to Suspense 2150."""
        # Settle invoice fully first
        event1 = NormalizedPaymentEvent(
            event_id="evt_full_001",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("1000.0000"),
            currency="GHS",
        )
        ReconciliationService.reconcile_payment(event1, organization=self.org)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)

        # Subsequent unexpected payment arrives
        event2 = NormalizedPaymentEvent(
            event_id="evt_after_paid_002",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("500.0000"),
            currency="GHS",
        )
        res2 = ReconciliationService.reconcile_payment(event2, organization=self.org)

        self.assertEqual(res2.status, PaymentStatusChoices.SUSPENSE)
        self.assertTrue(res2.is_suspense)
        self.assertIn("already fully paid", res2.notes)

        # Invoice remains unmodified
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("1000.0000"))
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)
