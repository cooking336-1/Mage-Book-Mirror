"""Functional Unit and Integration Tests for Mobile Money Reconciliation and Suspense Routing.

Covers:
1. Full settlement of open invoices (`status="PAID"`, Dr 1015, Cr 1200).
2. Partial settlement (`status="PARTIALLY_PAID"`, Dr 1015, Cr 1200).
3. Accumulation of multiple partial payments to full settlement.
4. Overpayment splitting: Dr 1015, Cr 1200 (balance), Cr 2150 (excess).
5. Suspense Account 2150 routing for missing reference, failed Luhn check, missing invoice,
   cancelled invoice, already settled invoice, and foreign currency.
6. Telco provider channel sanitization (MTN-GH, Vodafone, AirtelTigo).
7. Tenant resolution fallback via payload metadata and subaccount.
8. Unresolvable tenant logging to FAILED_TENANT_RESOLUTION without HTTP 500.
9. End-to-end webhook receiver to reconciliation pipeline.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.invoicing.models import Contact, ContactTypeChoices, Invoice, InvoiceStatusChoices
from apps.invoicing.utils import LuhnValidator
from apps.ledger.services.seeder import seed_standard_chart_of_accounts
from apps.payments.gateways.base import NormalizedPaymentEvent
from apps.payments.gateways.mock import MockHubtelGateway, MockPaystackGateway
from apps.payments.models import (
    PaymentMethodChoices,
    PaymentStatusChoices,
    PaymentWebhookLog,
    WebhookStatusChoices,
)
from apps.payments.services.reconciliation import ReconciliationService
from apps.tenancy.models import Organization, TaxSchemeChoices


class ReconciliationFunctionalTestCase(TestCase):
    """Functional test suite for payment reconciliation and general ledger posting."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.paystack_mock = MockPaystackGateway()
        self.hubtel_mock = MockHubtelGateway()

        # Create Tenant Organization
        self.org = Organization.objects.create(
            name="Accra Wholesale Mart",
            business_tin="C0001234567",
            phone="+233240000001",
            email="accra@wholesale.gh",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        seed_standard_chart_of_accounts(self.org)

        # Create Customer Contact
        self.customer = Contact.objects.create(
            organization=self.org,
            name="Kofi Mensah Enterprises",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="P0009876543",
        )

        # Generate self-validating Luhn reference (base: 84291 -> check digit 4 -> "84291-4")
        self.luhn_ref = LuhnValidator.generate_reference("84291", delimiter="-")

        # Create Open Invoice (CLEARED / PENDING_PAYMENT)
        self.invoice = Invoice.objects.create(
            organization=self.org,
            customer=self.customer,
            invoice_number="INV-2026-001",
            payment_reference=self.luhn_ref,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=14),
            subtotal_amount=Decimal("1000.0000"),
            vat_amount=Decimal("150.0000"),
            nhil_amount=Decimal("25.0000"),
            getfund_amount=Decimal("25.0000"),
            total_amount=Decimal("1200.0000"),
            paid_amount=Decimal("0.0000"),
            status=InvoiceStatusChoices.CLEARED,
        )

    def test_full_payment_settles_invoice_and_posts_gl(self) -> None:
        """Exact settlement transitions invoice to PAID and posts Dr 1015, Cr 1200."""
        event = NormalizedPaymentEvent(
            event_id="evt_full_001",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("1200.0000"),
            currency="GHS",
            status="success",
            paid_at=timezone.now(),
            raw_payload={"channel": "mtn_gh"},
        )

        result = ReconciliationService.reconcile_payment(event, organization=self.org)

        self.assertEqual(result.status, PaymentStatusChoices.SETTLED)
        self.assertFalse(result.is_suspense)
        self.assertIsNotNone(result.payment)
        self.assertIsNotNone(result.journal_entry)

        # Invoice assertions
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("1200.0000"))
        self.assertEqual(self.invoice.balance_due, Decimal("0.0000"))

        # Payment record assertions
        payment = result.payment
        self.assertEqual(payment.organization, self.org)
        self.assertEqual(payment.customer, self.customer)
        self.assertEqual(payment.invoice, self.invoice)
        self.assertEqual(payment.amount, Decimal("1200.0000"))
        self.assertEqual(payment.status, PaymentStatusChoices.SETTLED)
        self.assertEqual(payment.payment_method, PaymentMethodChoices.MTN_MOMO)
        self.assertEqual(payment.journal_entry, result.journal_entry)

        # General Ledger assertions
        lines = list(result.journal_entry.lines.order_by("created_at"))
        self.assertEqual(len(lines), 2)
        debit_line = lines[0]
        credit_line = lines[1]

        self.assertEqual(debit_line.account.account_code, "1015")
        self.assertEqual(debit_line.debit_amount, Decimal("1200.0000"))
        self.assertEqual(debit_line.credit_amount, Decimal("0.0000"))

        self.assertEqual(credit_line.account.account_code, "1200")
        self.assertEqual(credit_line.credit_amount, Decimal("1200.0000"))
        self.assertEqual(credit_line.debit_amount, Decimal("0.0000"))

    def test_partial_payment_marks_partially_paid_and_posts_gl(self) -> None:
        """Partial payment updates paid_amount, sets PARTIALLY_PAID, and never marks PAID."""
        event = NormalizedPaymentEvent(
            event_id="evt_part_001",
            provider="hubtel",
            reference=self.luhn_ref,
            amount=Decimal("500.0000"),
            currency="GHS",
            status="success",
            paid_at=timezone.now(),
            raw_payload={"channel": "vodafone"},
        )

        result = ReconciliationService.reconcile_payment(event, organization=self.org)

        self.assertEqual(result.status, PaymentStatusChoices.PARTIAL)
        self.assertFalse(result.is_suspense)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PARTIALLY_PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("500.0000"))
        self.assertEqual(self.invoice.balance_due, Decimal("700.0000"))

        payment = result.payment
        self.assertEqual(payment.status, PaymentStatusChoices.PARTIAL)
        self.assertEqual(payment.amount, Decimal("500.0000"))
        self.assertEqual(payment.payment_method, PaymentMethodChoices.TELECEL_CASH)

        # GL Lines
        lines = list(result.journal_entry.lines.all())
        self.assertEqual(len(lines), 2)
        self.assertEqual(sum(line.debit_amount for line in lines), Decimal("500.0000"))
        self.assertEqual(sum(line.credit_amount for line in lines), Decimal("500.0000"))

    def test_multiple_partial_payments_accumulate_to_full_settlement(self) -> None:
        """Consecutive partial payments accumulate accurately until final settlement marks PAID."""
        # Payment 1: GHS 400
        event1 = NormalizedPaymentEvent(
            event_id="evt_acc_001",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("400.0000"),
            currency="GHS",
        )
        res1 = ReconciliationService.reconcile_payment(event1, organization=self.org)
        self.assertEqual(res1.status, PaymentStatusChoices.PARTIAL)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PARTIALLY_PAID)
        self.assertEqual(self.invoice.balance_due, Decimal("800.0000"))

        # Payment 2: GHS 800 (Remaining Balance)
        event2 = NormalizedPaymentEvent(
            event_id="evt_acc_002",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("800.0000"),
            currency="GHS",
        )
        res2 = ReconciliationService.reconcile_payment(event2, organization=self.org)
        self.assertEqual(res2.status, PaymentStatusChoices.SETTLED)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("1200.0000"))
        self.assertEqual(self.invoice.balance_due, Decimal("0.0000"))

        # 2 distinct Payment records
        self.assertEqual(self.invoice.payments.count(), 2)

    def test_overpayment_splits_between_ar_and_suspense_2150(self) -> None:
        """Amount exceeding balance due splits between accounts.

        Credits AR for balance, Credits Suspense for excess.
        """
        # Invoice balance is 1200. Customer pays 1500.
        event = NormalizedPaymentEvent(
            event_id="evt_over_001",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("1500.0000"),
            currency="GHS",
        )

        result = ReconciliationService.reconcile_payment(event, organization=self.org)

        self.assertEqual(result.status, PaymentStatusChoices.SETTLED)
        self.assertEqual(result.excess_amount, Decimal("300.0000"))

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("1200.0000"))

        # GL Lines: 1 Debit (1015: 1500), 2 Credits (1200: 1200, 2150: 300)
        lines = list(result.journal_entry.lines.all())
        self.assertEqual(len(lines), 3)

        debit_line = next(line for line in lines if line.debit_amount > 0)
        self.assertEqual(debit_line.account.account_code, "1015")
        self.assertEqual(debit_line.debit_amount, Decimal("1500.0000"))

        ar_credit = next(line for line in lines if line.account.account_code == "1200")
        self.assertEqual(ar_credit.credit_amount, Decimal("1200.0000"))

        suspense_credit = next(line for line in lines if line.account.account_code == "2150")
        self.assertEqual(suspense_credit.credit_amount, Decimal("300.0000"))

        # Total debits must strictly equal total credits
        self.assertEqual(
            sum(line.debit_amount for line in lines), sum(line.credit_amount for line in lines)
        )

    def test_missing_reference_routes_to_suspense_account_2150(self) -> None:
        """Empty reference quarantines money to Suspense 2150 without modifying invoice."""
        event = NormalizedPaymentEvent(
            event_id="evt_no_ref_001",
            provider="paystack",
            reference="",
            amount=Decimal("250.0000"),
            currency="GHS",
        )

        result = ReconciliationService.reconcile_payment(event, organization=self.org)

        self.assertEqual(result.status, PaymentStatusChoices.SUSPENSE)
        self.assertTrue(result.is_suspense)
        self.assertIsNone(result.invoice)

        payment = result.payment
        self.assertEqual(payment.status, PaymentStatusChoices.SUSPENSE)
        self.assertEqual(payment.amount, Decimal("250.0000"))
        self.assertIsNone(payment.invoice)

        # GL Posting
        lines = list(result.journal_entry.lines.all())
        self.assertEqual(len(lines), 2)
        debit = next(line for line in lines if line.debit_amount > 0)
        credit = next(line for line in lines if line.credit_amount > 0)

        self.assertEqual(debit.account.account_code, "1015")
        self.assertEqual(debit.debit_amount, Decimal("250.0000"))
        self.assertEqual(credit.account.account_code, "2150")
        self.assertEqual(credit.credit_amount, Decimal("250.0000"))

        # Invoice remains completely untouched
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("0.0000"))
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.CLEARED)

    def test_corrupted_luhn_reference_routes_to_suspense_account_2150(self) -> None:
        """Tampered or transposed reference failing Luhn check routes to Suspense 2150."""
        # 84291-4 is valid. Tamper check digit to 84291-9.
        tampered_ref = "84291-9"
        event = NormalizedPaymentEvent(
            event_id="evt_bad_luhn_001",
            provider="hubtel",
            reference=tampered_ref,
            amount=Decimal("750.0000"),
            currency="GHS",
        )

        result = ReconciliationService.reconcile_payment(event, organization=self.org)

        self.assertEqual(result.status, PaymentStatusChoices.SUSPENSE)
        self.assertTrue(result.is_suspense)

        # GL Lines
        lines = list(result.journal_entry.lines.all())
        credit = next(line for line in lines if line.credit_amount > 0)
        self.assertEqual(credit.account.account_code, "2150")
        self.assertEqual(credit.credit_amount, Decimal("750.0000"))

    def test_non_existent_invoice_reference_routes_to_suspense_2150(self) -> None:
        """Valid Luhn reference that matches no invoice in tenant records routes to Suspense."""
        # 12345-6 passes Luhn, but no invoice exists with this code
        unknown_ref = LuhnValidator.generate_reference("12345", delimiter="-")
        event = NormalizedPaymentEvent(
            event_id="evt_unknown_inv_001",
            provider="paystack",
            reference=unknown_ref,
            amount=Decimal("450.0000"),
            currency="GHS",
        )

        result = ReconciliationService.reconcile_payment(event, organization=self.org)

        self.assertEqual(result.status, PaymentStatusChoices.SUSPENSE)
        self.assertTrue(result.is_suspense)

    def test_already_paid_invoice_routes_subsequent_payment_to_suspense_2150(self) -> None:
        """Payments referencing an already paid invoice route entirely to Suspense Account 2150."""
        self.invoice.status = InvoiceStatusChoices.PAID
        self.invoice.paid_amount = Decimal("1200.0000")
        self.invoice.save()

        event = NormalizedPaymentEvent(
            event_id="evt_dup_paid_001",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("1200.0000"),
            currency="GHS",
        )

        result = ReconciliationService.reconcile_payment(event, organization=self.org)

        self.assertEqual(result.status, PaymentStatusChoices.SUSPENSE)
        self.assertTrue(result.is_suspense)

    def test_cancelled_invoice_routes_to_suspense_2150(self) -> None:
        """Payments targeting a cancelled invoice route to Suspense 2150."""
        self.invoice.status = InvoiceStatusChoices.CANCELLED
        self.invoice.save()

        event = NormalizedPaymentEvent(
            event_id="evt_cancel_001",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("1200.0000"),
            currency="GHS",
        )

        result = ReconciliationService.reconcile_payment(event, organization=self.org)

        self.assertEqual(result.status, PaymentStatusChoices.SUSPENSE)
        self.assertTrue(result.is_suspense)

    def test_foreign_currency_routes_to_suspense_2150(self) -> None:
        """Foreign currency payments (e.g. USD) cannot settle GHS AR and quarantine to Suspense."""
        event = NormalizedPaymentEvent(
            event_id="evt_foreign_cur_001",
            provider="paystack",
            reference=self.luhn_ref,
            amount=Decimal("100.0000"),
            currency="USD",
        )

        result = ReconciliationService.reconcile_payment(event, organization=self.org)

        self.assertEqual(result.status, PaymentStatusChoices.SUSPENSE)
        self.assertTrue(result.is_suspense)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("0.0000"))

    def test_telco_channel_mapping_standardization(self) -> None:
        """Raw gateway channel strings (MTN-GH, vodafone, airteltigo) map to standard choices."""
        cases = [
            ("mtn-gh", PaymentMethodChoices.MTN_MOMO),
            ("vodafone", PaymentMethodChoices.TELECEL_CASH),
            ("airteltigo", PaymentMethodChoices.AT_MONEY),
            ("bank_transfer", PaymentMethodChoices.BANK_TRANSFER),
            ("visa_card", PaymentMethodChoices.BANK_POS),
        ]
        for raw_channel, expected_choice in cases:
            event = NormalizedPaymentEvent(
                event_id=f"evt_chan_{raw_channel}",
                provider="hubtel",
                reference="",
                amount=Decimal("50.0000"),
                currency="GHS",
                raw_payload={"channel": raw_channel},
            )
            result = ReconciliationService.reconcile_payment(event, organization=self.org)
            self.assertEqual(result.payment.payment_method, expected_choice)

    def test_tenant_resolution_fallback_to_metadata(self) -> None:
        """When reference is unresolvable, resolves tenant from payload metadata."""
        event = NormalizedPaymentEvent(
            event_id="evt_meta_tenant_001",
            provider="paystack",
            reference="CORRUPT_REF",
            amount=Decimal("180.0000"),
            currency="GHS",
            raw_payload={"data": {"metadata": {"organization_id": str(self.org.id)}}},
        )

        result = ReconciliationService.reconcile_payment(event)

        self.assertEqual(result.status, PaymentStatusChoices.SUSPENSE)
        self.assertEqual(result.payment.organization, self.org)

    def test_tenant_unresolvable_logs_failed_tenant_resolution_without_500(self) -> None:
        """When tenant cannot be identified, returns FAILED_TENANT_RESOLUTION without 500."""
        event = NormalizedPaymentEvent(
            event_id="evt_lost_tenant_001",
            provider="paystack",
            reference="CORRUPT_AND_NO_TENANT",
            amount=Decimal("300.0000"),
            currency="GHS",
            raw_payload={},
        )

        result = ReconciliationService.reconcile_payment(event)

        self.assertEqual(result.status, "FAILED_TENANT_RESOLUTION")
        self.assertTrue(result.is_suspense)
        self.assertIsNone(result.payment)

    def test_e2e_momo_webhook_view_to_reconciliation(self) -> None:
        """Full HTTP POST to /api/v1/payments/webhooks/momo/ reconciles invoice end-to-end."""
        payload, raw_bytes, sig = self.paystack_mock.create_mock_webhook_payload(
            reference=self.luhn_ref,
            amount_ghs=Decimal("1200.0000"),
            event_id="evt_e2e_momo_001",
        )
        url = reverse("payments:momo-webhook")

        response = self.client.post(
            url,
            data=raw_bytes,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sig,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("reconciliation_status"), "SETTLED")

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("1200.0000"))

        # Verify PaymentWebhookLog
        log_entry = PaymentWebhookLog.objects.filter(event_id="evt_e2e_momo_001").first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.status, WebhookStatusChoices.PROCESSED)
        self.assertEqual(log_entry.organization, self.org)
