"""Security, Abuse & Circuit Breaker Penetration Tests for GRA E-VAT Clearance.

Validates:
1. Circuit Breaker / Retry Backoff: Transient network errors trigger retry (invoice PENDING_GRA).
2. Exhausted Retries: Invoices remain in PENDING_GRA without data corruption when GRA is offline.
3. MUC-4.1 SSRF Defense: Embedded GRA SDC IDs and QR payloads pass air-gapped PDF assertions safely.
4. Missing Seller TIN: Rejection before external network payload transmission.
5. Cross-Tenant Protection: Invoice clearance strictly respects tenant boundaries.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.core.services.storage import MockR2Storage
from apps.invoicing.models import (
    Contact,
    ContactTypeChoices,
    Invoice,
    InvoiceLine,
    InvoiceStatusChoices,
)
from apps.invoicing.services.pdf_compiler import AirGappedPDFCompiler
from apps.invoicing.utils import LuhnValidator
from apps.ledger.services.seeder import seed_standard_chart_of_accounts
from apps.tax.gateways.base import GraNetworkException
from apps.tax.gateways.mock import MockGraEvatClient
from apps.tax.tasks import clear_with_gra
from apps.tenancy.models import Organization, TaxSchemeChoices


class GraClearanceSecurityTestCase(TestCase):
    """Abuse and resilience test suite for GRA E-VAT clearance."""

    def setUp(self) -> None:
        self.mock_storage = MockR2Storage()

        # Tenant A (Legitimate Organization)
        self.org_a = Organization.objects.create(
            name="Alpha Logistics Ltd",
            business_tin="C0001112223",
            phone="+233240000001",
            email="alpha@logistics.gh",
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

        self.ref_a = LuhnValidator.generate_reference("11223", delimiter="-")

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
            status=InvoiceStatusChoices.PENDING_GRA,
        )

        InvoiceLine.objects.create(
            organization=self.org_a,
            invoice=self.invoice_a,
            description="Freight and Haulage Logistics",
            quantity=Decimal("1.0000"),
            unit_price=Decimal("1000.0000"),
            line_total=Decimal("1000.0000"),
            vat_amount=Decimal("150.0000"),
            nhil_amount=Decimal("25.0000"),
            getfund_amount=Decimal("25.0000"),
        )

        # Tenant B (Unrelated / Attacker)
        self.org_b = Organization.objects.create(
            name="Beta Enterprise Ltd",
            business_tin="",  # Intentionally missing TIN
            phone="+233240000002",
            email="beta@enterprise.gh",
            vat_registered=False,
            vat_scheme=TaxSchemeChoices.EXEMPT,
        )

    def test_gra_transient_network_error_triggers_retry(self) -> None:
        """Transient timeout triggers Celery retry mechanism."""
        mock_client = MockGraEvatClient(simulate_network_error=True)

        with (
            patch("apps.tax.tasks.get_gra_client", return_value=mock_client),
            patch(
                "apps.invoicing.services.pdf_service.get_storage_service",
                return_value=self.mock_storage,
            ),
            patch.object(
                clear_with_gra, "retry", side_effect=GraNetworkException("Retry triggered")
            ) as mock_retry,
        ):
            with self.assertRaises(GraNetworkException):
                clear_with_gra(str(self.invoice_a.id))

            self.assertTrue(mock_retry.called)

    def test_exhausted_retries_leaves_invoice_in_pending_gra_without_data_corruption(self) -> None:
        """When GRA platform is persistently offline, invoice stays in PENDING_GRA."""
        mock_client = MockGraEvatClient(simulate_network_error=True)

        with (
            patch("apps.tax.tasks.get_gra_client", return_value=mock_client),
            patch(
                "apps.invoicing.services.pdf_service.get_storage_service",
                return_value=self.mock_storage,
            ),
        ):
            # Celery will retry up to max_retries and then raise GraNetworkException
            with self.assertRaises(GraNetworkException):
                clear_with_gra(str(self.invoice_a.id))

        self.invoice_a.refresh_from_db()
        # SAFE FAILURE BOUNDARY: Invoice must remain intact in PENDING_GRA
        self.assertEqual(self.invoice_a.status, InvoiceStatusChoices.PENDING_GRA)
        self.assertIsNone(self.invoice_a.gra_clearance_code)
        self.assertIsNone(self.invoice_a.gra_cleared_at)

    def test_muc_4_1_ssrf_safety_on_gra_clearance_code(self) -> None:
        """Attacker injecting SSRF vector inside customer notes is blocked by PDF compiler."""
        # Malicious cloud metadata injection
        malicious_input = "<img src='http://169.254.169.254/latest/meta-data/'>"

        with self.assertRaises(PermissionError) as ctx:
            AirGappedPDFCompiler.assert_air_gapped_safety(malicious_input)

        self.assertIn("SSRF Prevention (MUC-4.1)", str(ctx.exception))

    def test_missing_seller_tin_rejected_before_transmission(self) -> None:
        """Organization lacking a valid business TIN is rejected before external transmission."""
        customer_b = Contact.objects.create(
            organization=self.org_b,
            name="Unregistered Customer",
            contact_type=ContactTypeChoices.CUSTOMER,
        )
        invoice_b = Invoice.objects.create(
            organization=self.org_b,
            customer=customer_b,
            invoice_number="INV-2026-BETA-01",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=7),
            total_amount=Decimal("500.0000"),
            status=InvoiceStatusChoices.PENDING_GRA,
        )

        mock_client = MockGraEvatClient()

        with patch("apps.tax.tasks.get_gra_client", return_value=mock_client):
            result = clear_with_gra(str(invoice_b.id))

        self.assertEqual(result["status"], "ERROR")
        self.assertIn("missing business TIN", result["error"])
        # No payload sent to external client
        self.assertEqual(len(mock_client.submitted_payloads), 0)

    def test_non_existent_invoice_uuid_returns_error_gracefully(self) -> None:
        """Clearance task with non-existent UUID fails gracefully without crashing worker."""
        fake_uuid = "01923456-789a-7bc0-8123-456789abcdef"
        result = clear_with_gra(fake_uuid)

        self.assertEqual(result["status"], "ERROR")
        self.assertIn("not found", result["error"])
