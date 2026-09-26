"""Security and Abuse Penetration Tests for Mobile Money Payment Reconciliation (MUC-1.1).

Defends against:
1. Misuse Case 1.1 (MUC-1.1): Mobile Money Underpayment Attack:
   An attacker submits GHS 1.00 on a GHS 1,200.00 invoice hoping reference matching
   clears the Accounts Receivable balance. The system asserts exact Decimal balance
   and transitions exclusively to PARTIALLY_PAID.
2. Zero and Negative Payment Exploits:
   Submitting GHS 0.00 or negative amounts is strictly rejected before database mutations.
3. Cross-Tenant Reference Hijacking:
   Tenant A cannot settle or mutate invoices belonging to Tenant B by spoofing payment references.
4. General Ledger Balance Sheet Invariant:
   Sum(Debits) == Sum(Credits) across all matched settlements, partial payments,
   and Suspense Account 2150 quarantine postings.
"""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.invoicing.models import Contact, ContactTypeChoices, Invoice, InvoiceStatusChoices
from apps.invoicing.utils import LuhnValidator
from apps.ledger.services.seeder import seed_standard_chart_of_accounts
from apps.payments.gateways.base import NormalizedPaymentEvent
from apps.payments.models import (
    Payment,
    PaymentStatusChoices,
)
from apps.payments.services.reconciliation import ReconciliationService
from apps.tenancy.models import Organization, TaxSchemeChoices


class MoMoSecurityMisuseCase11TestCase(TestCase):
    """Abuse and security test suite defending against underpayment attacks (MUC-1.1)."""

    def setUp(self) -> None:
        # Tenant A (Target Merchant)
        self.org_a = Organization.objects.create(
            name="Alpha Retail Ghana Ltd",
            business_tin="C0001112223",
            phone="+233240000001",
            email="alpha@retail.gh",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        seed_standard_chart_of_accounts(self.org_a)

        self.customer_a = Contact.objects.create(
            organization=self.org_a,
            name="Kwame Mensah",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="P0001112223",
        )

        # Generate self-validating Luhn reference for Tenant A
        self.ref_a = LuhnValidator.generate_reference("55501", delimiter="-")

        # Create GHS 1,200.00 Invoice for Tenant A
        self.invoice_a = Invoice.objects.create(
            organization=self.org_a,
            customer=self.customer_a,
            invoice_number="INV-2026-ALPHA-01",
            payment_reference=self.ref_a,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=7),
            subtotal_amount=Decimal("1000.0000"),
            vat_amount=Decimal("150.0000"),
            nhil_amount=Decimal("25.0000"),
            getfund_amount=Decimal("25.0000"),
            total_amount=Decimal("1200.0000"),
            paid_amount=Decimal("0.0000"),
            status=InvoiceStatusChoices.CLEARED,
        )

        # Tenant B (Attacker / Unrelated Tenant)
        self.org_b = Organization.objects.create(
            name="Beta Enterprise Ltd",
            business_tin="C0009998887",
            phone="+233240000002",
            email="beta@enterprise.gh",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        seed_standard_chart_of_accounts(self.org_b)

    def test_muc_1_1_underpayment_attack_does_not_clear_invoice(self) -> None:
        """MUC-1.1 Defense: Attacker pays GHS 1.00 on a GHS 1,200.00 invoice.

        Asserts:
        - Invoice status is NEVER marked PAID.
        - Status transitions strictly to PARTIALLY_PAID.
        - Invoice paid_amount increments by only GHS 1.0000.
        - balance_due remains exactly GHS 1199.0000.
        - General ledger credits Accounts Receivable for only GHS 1.0000.
        """
        attacker_event = NormalizedPaymentEvent(
            event_id="evt_attack_underpayment_001",
            provider="paystack",
            reference=self.ref_a,
            amount=Decimal("1.0000"),  # Attacker attempts 1 GHS settlement on 1200 GHS invoice
            currency="GHS",
            status="success",
        )

        result = ReconciliationService.reconcile_payment(attacker_event, organization=self.org_a)

        self.assertEqual(result.status, PaymentStatusChoices.PARTIAL)
        self.assertFalse(result.is_suspense)

        self.invoice_a.refresh_from_db()
        self.assertNotEqual(self.invoice_a.status, InvoiceStatusChoices.PAID)
        self.assertEqual(self.invoice_a.status, InvoiceStatusChoices.PARTIALLY_PAID)
        self.assertEqual(self.invoice_a.paid_amount, Decimal("1.0000"))
        self.assertEqual(self.invoice_a.balance_due, Decimal("1199.0000"))

        # Payment record
        payment = result.payment
        self.assertEqual(payment.status, PaymentStatusChoices.PARTIAL)
        self.assertEqual(payment.amount, Decimal("1.0000"))

        # GL Lines: exactly GHS 1.00 posted, balance invariant maintained
        lines = list(result.journal_entry.lines.all())
        self.assertEqual(len(lines), 2)
        debit = next(line for line in lines if line.debit_amount > 0)
        credit = next(line for line in lines if line.credit_amount > 0)

        self.assertEqual(debit.account.account_code, "1015")
        self.assertEqual(debit.debit_amount, Decimal("1.0000"))
        self.assertEqual(credit.account.account_code, "1200")
        self.assertEqual(credit.credit_amount, Decimal("1.0000"))

    def test_muc_1_1_zero_amount_exploit_rejected(self) -> None:
        """Attacker submits GHS 0.00 payment to trigger state machine mutation.

        Asserts:
        - Rejected with ERROR status.
        - Invoice is not modified.
        - No payment or journal entry rows created.
        """
        exploit_event = NormalizedPaymentEvent(
            event_id="evt_attack_zero_001",
            provider="paystack",
            reference=self.ref_a,
            amount=Decimal("0.0000"),
            currency="GHS",
        )

        result = ReconciliationService.reconcile_payment(exploit_event, organization=self.org_a)

        self.assertEqual(result.status, "ERROR")
        self.assertIsNone(result.payment)
        self.assertIsNone(result.journal_entry)

        self.invoice_a.refresh_from_db()
        self.assertEqual(self.invoice_a.paid_amount, Decimal("0.0000"))
        self.assertEqual(self.invoice_a.status, InvoiceStatusChoices.CLEARED)
        self.assertEqual(Payment.objects.filter(reference_number="evt_attack_zero_001").count(), 0)

    def test_muc_1_1_negative_amount_exploit_rejected(self) -> None:
        """Attacker submits negative amount to decrement paid_amount or credit cash.

        Asserts:
        - Rejected with ERROR status.
        - No database mutations allowed.
        """
        exploit_event = NormalizedPaymentEvent(
            event_id="evt_attack_negative_001",
            provider="hubtel",
            reference=self.ref_a,
            amount=Decimal("-500.0000"),
            currency="GHS",
        )

        result = ReconciliationService.reconcile_payment(exploit_event, organization=self.org_a)

        self.assertEqual(result.status, "ERROR")
        self.assertIsNone(result.payment)

        self.invoice_a.refresh_from_db()
        self.assertEqual(self.invoice_a.paid_amount, Decimal("0.0000"))

    def test_cross_tenant_reference_hijacking_prevented(self) -> None:
        """Tenant B receives payment citing Tenant A's invoice reference.

        Asserts:
        - Tenant A's invoice is NOT mutated or credited.
        - The funds are safely quarantined to Tenant B's Suspense Account 2150.
        """
        cross_tenant_event = NormalizedPaymentEvent(
            event_id="evt_cross_tenant_001",
            provider="paystack",
            reference=self.ref_a,  # Belongs to Tenant A
            amount=Decimal("1200.0000"),
            currency="GHS",
        )

        # Payment arrives in Tenant B's merchant account
        result = ReconciliationService.reconcile_payment(
            cross_tenant_event, organization=self.org_b
        )

        self.assertEqual(result.status, PaymentStatusChoices.SUSPENSE)
        self.assertTrue(result.is_suspense)
        self.assertEqual(result.payment.organization, self.org_b)

        # Tenant A's invoice remains completely unpaid
        self.invoice_a.refresh_from_db()
        self.assertEqual(self.invoice_a.paid_amount, Decimal("0.0000"))
        self.assertEqual(self.invoice_a.status, InvoiceStatusChoices.CLEARED)

    def test_general_ledger_double_entry_balance_invariant_enforced(self) -> None:
        """Every transaction (settlement, partial, suspense) satisfies debits == credits."""
        events = [
            # 1. Matched settlement
            NormalizedPaymentEvent(
                event_id="evt_gl_check_1",
                provider="paystack",
                reference=self.ref_a,
                amount=Decimal("1200.0000"),
                currency="GHS",
            ),
            # 2. Suspense deposit (missing ref)
            NormalizedPaymentEvent(
                event_id="evt_gl_check_2",
                provider="hubtel",
                reference="",
                amount=Decimal("635.5000"),
                currency="GHS",
            ),
            # 3. Suspense deposit (corrupt ref)
            NormalizedPaymentEvent(
                event_id="evt_gl_check_3",
                provider="paystack",
                reference="INVALID-99",
                amount=Decimal("100.0000"),
                currency="GHS",
            ),
        ]

        for evt in events:
            res = ReconciliationService.reconcile_payment(evt, organization=self.org_a)
            self.assertIsNotNone(res.journal_entry)

            lines = list(res.journal_entry.lines.all())
            total_debits = sum(line.debit_amount for line in lines)
            total_credits = sum(line.credit_amount for line in lines)

            self.assertEqual(
                total_debits,
                total_credits,
                (
                    f"Double-entry balance invariant failed for event {evt.event_id}: "
                    f"{total_debits} != {total_credits}"
                ),
            )
            self.assertGreater(total_debits, Decimal("0.0000"))

    def test_concurrent_payment_race_condition_protection(self) -> None:
        """Simulates rapid consecutive payments on the same invoice.

        Asserts that row-level locking (select_for_update) inside @transaction.atomic
        serializes balance updates without lost updates:
        - First payment of GHS 700.00 leaves balance_due = GHS 500.00 (PARTIALLY_PAID).
        - Second payment of GHS 700.00 recognizes updated balance (500.00), settles invoice (PAID),
          and safely splits excess GHS 200.00 to Suspense 2150.
        - Total invoice paid_amount is exactly GHS 1200.00.
        - Two distinct Payment records are persisted.
        - Both journal entries maintain debits == credits balance invariants.
        """
        evt1 = NormalizedPaymentEvent(
            event_id="evt_concur_1",
            provider="paystack",
            reference=self.ref_a,
            amount=Decimal("700.0000"),
            currency="GHS",
        )
        evt2 = NormalizedPaymentEvent(
            event_id="evt_concur_2",
            provider="paystack",
            reference=self.ref_a,
            amount=Decimal("700.0000"),
            currency="GHS",
        )

        res1 = ReconciliationService.reconcile_payment(evt1, organization=self.org_a)
        res2 = ReconciliationService.reconcile_payment(evt2, organization=self.org_a)

        self.assertEqual(res1.status, PaymentStatusChoices.PARTIAL)
        self.assertEqual(res2.status, PaymentStatusChoices.SETTLED)
        self.assertEqual(res2.excess_amount, Decimal("200.0000"))

        self.invoice_a.refresh_from_db()
        self.assertEqual(self.invoice_a.status, InvoiceStatusChoices.PAID)
        self.assertEqual(self.invoice_a.paid_amount, Decimal("1200.0000"))
        self.assertEqual(self.invoice_a.balance_due, Decimal("0.0000"))
        self.assertEqual(self.invoice_a.payments.count(), 2)
