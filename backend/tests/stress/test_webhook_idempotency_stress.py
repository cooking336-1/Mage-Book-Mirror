"""Distributed Webhook Idempotency Stress Test Suite (Task C.11 / T3.5).

Verifies:
1. 10 identical webhook POST requests with identical HMAC signatures and event IDs:
   - Exactly 1 request acquires distributed Redis idempotency lock and reconciles.
   - 9 duplicates intercepted by IdempotencyService and discarded with HTTP 200 IGNORED.
   - Exactly 1 Payment transaction is persisted.
   - Exactly 1 General Ledger JournalEntry posted (prevents duplicate GL entries).
   - Invoice paid_amount is credited exactly once.

2. Concurrent execution under ThreadPoolExecutor:
   - Thread-safe distributed locking prevents double-spend race conditions.

3. Independent distinct event IDs are processed without collision.
"""

import concurrent.futures
import json
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.invoicing.models import (
    Contact,
    ContactTypeChoices,
    Invoice,
    InvoiceStatusChoices,
)
from apps.invoicing.utils import LuhnValidator
from apps.ledger.models import JournalEntry
from apps.ledger.services.seeder import seed_standard_chart_of_accounts
from apps.payments.gateways.paystack import PaystackGateway
from apps.payments.models import (
    Payment,
    PaymentWebhookLog,
    WebhookStatusChoices,
)
from apps.payments.services.idempotency import get_redis_client
from apps.tenancy.models import Organization, TaxSchemeChoices


class WebhookIdempotencyStressTests(TransactionTestCase):
    """Stress suite validating atomic webhook idempotency locks and GL protection."""

    def setUp(self) -> None:
        self.redis = get_redis_client()
        self.redis.clear()

        self.org = Organization.objects.create(
            name="Tema Logistics Terminal Ltd",
            phone="+233241100223",
            email="finance@temalogistics.gh",
            business_tin="C0008877665",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        seed_standard_chart_of_accounts(self.org)

        self.customer = Contact.objects.create(
            organization=self.org,
            name="Atlantic Shipping Ghana Ltd",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="C0002233445",
            email="payments@atlanticshipping.gh",
        )

        self.luhn_ref = LuhnValidator.generate_reference("77881", delimiter="-")

        self.invoice = Invoice.objects.create(
            organization=self.org,
            customer=self.customer,
            invoice_number="INV-2026-TEMA-001",
            payment_reference=self.luhn_ref,
            status=InvoiceStatusChoices.CLEARED,
            total_amount=Decimal("500.0000"),
            paid_amount=Decimal("0.0000"),
            currency="GHS",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
        )

        self.gateway = PaystackGateway()
        self.webhook_url = reverse("payments:paystack-webhook")

    def tearDown(self) -> None:
        self.redis.clear()

    def _build_paystack_payload(
        self, event_id: str, amount_pesewas: int = 50000
    ) -> tuple[bytes, str]:
        """Constructs valid Paystack webhook JSON payload and constant-time HMAC signature."""
        payload_dict = {
            "event": "charge.success",
            "data": {
                "id": event_id,
                "reference": self.luhn_ref,
                "amount": amount_pesewas,
                "currency": "GHS",
                "status": "success",
                "paid_at": "2026-09-30T10:00:00Z",
                "customer": {
                    "email": self.customer.email,
                    "phone": "+233240001122",
                },
                "metadata": {
                    "organization_id": str(self.org.id),
                },
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        signature = self.gateway.generate_signature(raw_body)
        return raw_body, signature

    def test_ten_identical_webhooks_processed_exactly_once(self) -> None:
        """10 identical webhook POST requests execute once and ignore 9 duplicates."""
        event_id = "evt_stress_paystack_001"
        raw_body, signature = self._build_paystack_payload(event_id=event_id, amount_pesewas=50000)

        client = APIClient()
        responses = []

        # Send 10 identical webhook calls
        for _ in range(10):
            resp = client.post(
                self.webhook_url,
                data=raw_body,
                content_type="application/json",
                HTTP_X_PAYSTACK_SIGNATURE=signature,
            )
            responses.append(resp)

        # Invariant 1: All 10 requests must return HTTP 200 OK
        for idx, resp in enumerate(responses):
            self.assertEqual(
                resp.status_code,
                status.HTTP_200_OK,
                f"Request #{idx + 1} did not return HTTP 200",
            )

        # Invariant 2: Request 1 must be success/settled, Requests 2-10 must be ignored
        first_resp = responses[0].json()
        self.assertEqual(first_resp.get("status"), "success")
        self.assertEqual(first_resp.get("reconciliation_status"), "SETTLED")

        for idx, resp in enumerate(responses[1:], start=2):
            resp_data = resp.json()
            self.assertEqual(
                resp_data.get("status"),
                "ignored",
                f"Request #{idx} was not ignored by idempotency filter",
            )
            self.assertIn("Duplicate webhook event", resp_data.get("detail", ""))

        # Invariant 3: Exactly 1 Payment record created
        payment_count = Payment.objects.filter(reference_number=event_id).count()
        self.assertEqual(payment_count, 1, "Expected exactly 1 Payment row in database")

        # Invariant 4: Exactly 1 JournalEntry created
        je_count = JournalEntry.objects.filter(
            organization=self.org,
            narration__contains="INV-2026-TEMA-001",
        ).count()
        self.assertEqual(je_count, 1, "Duplicate general ledger entries were created!")

        # Invariant 5: Invoice paid_amount is strictly 500.00 and status is PAID
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("500.0000"))
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)
        self.assertEqual(self.invoice.balance_due, Decimal("0.0000"))

        # Invariant 6: PaymentWebhookLog entries (1 PROCESSED, 9 IGNORED)
        logs = PaymentWebhookLog.objects.filter(event_id=event_id)
        self.assertEqual(logs.count(), 10)
        self.assertEqual(logs.filter(status=WebhookStatusChoices.PROCESSED).count(), 1)
        self.assertEqual(logs.filter(status=WebhookStatusChoices.IGNORED).count(), 9)

    def test_concurrent_webhook_replay_stress_with_thread_pool(self) -> None:
        """Concurrent ThreadPoolExecutor dispatching identical webhook callbacks."""
        num_threads = 1 if connection.vendor == "sqlite" else 10
        event_id = "evt_concurrent_paystack_002"
        raw_body, signature = self._build_paystack_payload(event_id=event_id, amount_pesewas=50000)

        def fire_webhook(idx: int) -> tuple[int, dict]:
            connection.close()
            try:
                local_client = APIClient()
                resp = local_client.post(
                    self.webhook_url,
                    data=raw_body,
                    content_type="application/json",
                    HTTP_X_PAYSTACK_SIGNATURE=signature,
                )
                return resp.status_code, resp.json()
            finally:
                connection.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(fire_webhook, i) for i in range(num_threads)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), num_threads)
        for status_code, _body in results:
            self.assertEqual(status_code, status.HTTP_200_OK)

        # Verify only 1 payment was created regardless of concurrency
        self.assertEqual(Payment.objects.filter(reference_number=event_id).count(), 1)

    def test_distinct_events_for_same_tenant_execute_independently(self) -> None:
        """Distinct webhook events do not falsely block each other."""
        client = APIClient()

        # Event A: 200 GHS
        raw_a, sig_a = self._build_paystack_payload(event_id="evt_unique_A", amount_pesewas=20000)
        resp_a = client.post(
            self.webhook_url,
            data=raw_a,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sig_a,
        )
        self.assertEqual(resp_a.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_a.json().get("status"), "success")

        # Event B: 300 GHS
        raw_b, sig_b = self._build_paystack_payload(event_id="evt_unique_B", amount_pesewas=30000)
        resp_b = client.post(
            self.webhook_url,
            data=raw_b,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sig_b,
        )
        self.assertEqual(resp_b.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_b.json().get("status"), "success")

        # Both events persisted
        self.assertEqual(Payment.objects.filter(reference_number="evt_unique_A").count(), 1)
        self.assertEqual(Payment.objects.filter(reference_number="evt_unique_B").count(), 1)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("500.0000"))
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)
