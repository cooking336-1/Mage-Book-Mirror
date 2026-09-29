"""Verification test suite for Task A.5 (B5).

Validates:
1. Handled inner exceptions do not abort outer transaction (no TransactionManagementError cascades).
2. TenantSecurityMiddleware does NOT wrap request execution in transaction.atomic().
3. InvoicingService dispatches GRA E-VAT clearance on commit via transaction.on_commit().
4. PaymentWebhookLog entries persist even when reconciliation encounters failures/rollbacks.
5. Tenant session parameters and thread-local state are cleanly deallocated on request completion.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, TransactionTestCase

from apps.invoicing.models import Contact, ContactTypeChoices, InvoiceStatusChoices
from apps.invoicing.services.invoicing_service import InvoicingService
from apps.ledger.services.seeder import generate_fiscal_periods, seed_standard_chart_of_accounts
from apps.payments.gateways.base import NormalizedPaymentEvent
from apps.payments.models import PaymentWebhookLog, WebhookStatusChoices
from apps.payments.services.reconciliation import ReconciliationService
from apps.tenancy.middleware import (
    TenantSecurityMiddleware,
    clear_current_tenant,
    get_current_tenant,
    get_current_tenant_id,
)
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices

User = get_user_model()


class MiddlewareTransactionUnwrappingTests(TransactionTestCase):
    """Verifies that TenantSecurityMiddleware does not wrap request in transaction.atomic()."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="tenant_admin@accrabooks.com",
            password="SecurePassword123!",
        )
        self.org = Organization.objects.create(
            name="Accra Hardening Enterprise",
            phone="+233240001122",
            email="ops@accrahardening.com",
        )
        self.membership = OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=RoleChoices.ADMIN,
        )

    def tearDown(self) -> None:
        clear_current_tenant()

    def test_middleware_does_not_wrap_request_in_atomic_transaction(self) -> None:
        """Verify connection.in_atomic_block is False during view execution in middleware."""
        in_atomic_at_view_time: list[bool] = []

        def dummy_view(request):
            in_atomic_at_view_time.append(connection.in_atomic_block)
            return JsonResponse({"status": "ok"})

        middleware = TenantSecurityMiddleware(dummy_view)

        request = self.factory.get("/api/v1/tenancy/context/")
        request.user = self.user
        request.headers = {"X-Tenant-ID": str(self.org.id)}

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(in_atomic_at_view_time), 1)
        self.assertFalse(
            in_atomic_at_view_time[0],
            "TenantSecurityMiddleware must NOT wrap view execution in transaction.atomic()!",
        )

    def test_handled_inner_exception_does_not_abort_subsequent_queries(self) -> None:
        """Verify handled database exceptions do not cause TransactionManagementError cascades."""

        def view_with_handled_exception(request):
            # 1. Cause and catch an IntegrityError from database unique constraint
            try:
                with transaction.atomic():
                    # bulk_create skips full_clean() and triggers the real
                    # database unique constraint
                    OrganizationMembership.objects.bulk_create(
                        [
                            OrganizationMembership(
                                organization=self.org,
                                user=self.user,
                                role=RoleChoices.ADMIN,
                            )
                        ]
                    )
            except IntegrityError:
                pass  # Gracefully handled by the view

            # 2. Subsequent query should execute cleanly without TransactionManagementError
            user_count = User.objects.filter(id=self.user.id).count()
            return JsonResponse({"user_count": user_count})

        middleware = TenantSecurityMiddleware(view_with_handled_exception)

        request = self.factory.get("/api/v1/tenancy/context/")
        request.user = self.user
        request.headers = {"X-Tenant-ID": str(self.org.id)}

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"user_count": 1', response.content)

    def test_session_variable_deallocated_on_request_completion(self) -> None:
        """Verify thread-local tenant context is wiped after request completion."""

        def dummy_view(request):
            self.assertEqual(get_current_tenant_id(), self.org.id)
            return HttpResponse("ok")

        middleware = TenantSecurityMiddleware(dummy_view)

        request = self.factory.get("/api/v1/tenancy/context/")
        request.user = self.user
        request.headers = {"X-Tenant-ID": str(self.org.id)}

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(get_current_tenant())
        self.assertIsNone(get_current_tenant_id())


class DomainOrchestrationAtomicityTests(TransactionTestCase):
    """Verifies orchestration atomicity, on_commit hooks, and audit log persistence."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.user = User.objects.create_user(
            email="cfo@accrabooks.com",
            password="SecurePassword123!",
        )
        self.org = Organization.objects.create(
            name="Accra Books Ltd",
            phone="+233240003344",
            email="cfo@accrabooks.com",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=RoleChoices.OWNER,
        )

        seed_standard_chart_of_accounts(self.org)
        generate_fiscal_periods(self.org, 2026)

        self.customer = Contact.objects.create(
            organization=self.org,
            name="Tema Logistics Corp",
            contact_type=ContactTypeChoices.CUSTOMER,
            email="accounts@temalogistics.gh",
            tin="C0001234567",
        )

    def tearDown(self) -> None:
        clear_current_tenant()

    @patch("apps.invoicing.services.invoicing_service.enqueue_gra_clearance")
    def test_invoicing_dispatches_gra_clearance_on_commit(self, mock_enqueue: MagicMock) -> None:
        """Verify InvoicingService triggers enqueue_gra_clearance via transaction.on_commit."""
        import datetime

        data = {
            "customer_id": str(self.customer.id),
            "issue_date": datetime.date(2026, 9, 29),
            "due_date": datetime.date(2026, 10, 29),
            "action": "issue",
            "currency": "GHS",
            "lines": [
                {
                    "description": "Consulting Services",
                    "quantity": 1,
                    "unit_price": "1000.00",
                }
            ],
        }

        invoice = InvoicingService.create_and_post_invoice(
            organization=self.org,
            user=self.user,
            data=data,
        )

        self.assertEqual(invoice.status, InvoiceStatusChoices.PENDING_GRA)
        # Because the atomic block committed in TransactionTestCase, on_commit handler fired
        mock_enqueue.assert_called_once_with(invoice.id)

    def test_failed_reconciliation_persists_webhook_log(self) -> None:
        """Verify PaymentWebhookLog status is preserved even when tenant resolution fails."""
        event = NormalizedPaymentEvent(
            provider="paystack",
            event_id="evt_unresolvable_999",
            amount=Decimal("200.00"),
            currency="GHS",
            reference="INVALID-REF-000",
            raw_payload={"data": {"id": "evt_unresolvable_999"}},
        )

        log = PaymentWebhookLog.objects.create(
            provider="paystack",
            event_id="evt_unresolvable_999",
            status=WebhookStatusChoices.VERIFIED,
            signature_header="test-sig",
        )

        result = ReconciliationService.reconcile_payment(event)

        self.assertEqual(result.status, "FAILED_TENANT_RESOLUTION")

        log.refresh_from_db()
        self.assertEqual(log.status, WebhookStatusChoices.FAILED_TENANT_RESOLUTION)
        self.assertIn("Could not resolve tenant organization", log.error_message)
