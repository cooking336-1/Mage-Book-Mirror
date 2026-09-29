"""Functional Unit & Integration Tests for Asynchronous GRA E-VAT Clearance Worker.

Covers:
1. Successful clearance transition from PENDING_GRA to CLEARED with SDC ID.
2. In-memory vector QR SVG compilation and persistence in invoice.gra_qr_code.
3. Air-gapped PDF re-compilation with official green certified stamp uploaded to R2.
4. Non-destructive state preservation: invoices in PAID or PARTIALLY_PAID retain their
   commercial status while receiving statutory clearance codes.
5. Idempotent execution on already CLEARED invoices.
6. Cancelled invoice clearance abortion.
7. Automatic Celery dispatch during invoice issuance via InvoicingService.
8. Batch retry management command (retry_pending_gra).
"""

from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
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
from apps.invoicing.services.invoicing_service import InvoicingService
from apps.invoicing.utils import LuhnValidator
from apps.ledger.services.seeder import seed_standard_chart_of_accounts
from apps.tax.gateways.mock import MockGraEvatClient
from apps.tax.tasks import clear_with_gra
from apps.tenancy.models import Organization, TaxSchemeChoices


class GraClearanceWorkerTestCase(TestCase):
    """Test suite for asynchronous GRA E-VAT clearance worker and PDF stamping."""

    def setUp(self) -> None:
        self.mock_storage = MockR2Storage()

        # Create Tenant Organization
        self.org = Organization.objects.create(
            name="Tema Supermarket Ltd",
            business_tin="C0009876543",
            phone="+233240001111",
            email="tema@supermarket.gh",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        seed_standard_chart_of_accounts(self.org)

        # Create Customer
        self.customer = Contact.objects.create(
            organization=self.org,
            name="Ama Serwaa Enterprises",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="P0001234567",
            ghana_card_number="GHA-123456789-0",
        )

        self.ref = LuhnValidator.generate_reference("98765", delimiter="-")

        # Create Invoice in PENDING_GRA state
        self.invoice = Invoice.objects.create(
            organization=self.org,
            customer=self.customer,
            invoice_number="INV-2026-GRA-01",
            payment_reference=self.ref,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=14),
            subtotal_amount=Decimal("1000.0000"),
            vat_amount=Decimal("150.0000"),
            nhil_amount=Decimal("25.0000"),
            getfund_amount=Decimal("25.0000"),
            covid_levy_amount=Decimal("0.0000"),
            total_amount=Decimal("1200.0000"),
            paid_amount=Decimal("0.0000"),
            status=InvoiceStatusChoices.PENDING_GRA,
        )

        InvoiceLine.objects.create(
            organization=self.org,
            invoice=self.invoice,
            description="Premium Imported Jasmine Rice (50kg)",
            quantity=Decimal("2.0000"),
            unit_price=Decimal("500.0000"),
            line_total=Decimal("1000.0000"),
            vat_amount=Decimal("150.0000"),
            nhil_amount=Decimal("25.0000"),
            getfund_amount=Decimal("25.0000"),
        )

    def test_successful_clearance_transitions_invoice_to_cleared(self) -> None:
        """Clearance task transitions PENDING_GRA invoice to CLEARED with SDC tokens."""
        mock_client = MockGraEvatClient()

        with (
            patch("apps.tax.tasks.get_gra_client", return_value=mock_client),
            patch(
                "apps.invoicing.services.pdf_service.get_storage_service",
                return_value=self.mock_storage,
            ),
        ):
            result = clear_with_gra(str(self.invoice.id))

        self.assertEqual(result["status"], "CLEARED")
        self.assertIn("SDC-GH-2026-", result["sdc_id"])
        self.assertIn("GRA-2026-", result["clearance_code"])

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.CLEARED)
        self.assertEqual(self.invoice.gra_clearance_code, result["clearance_code"])
        self.assertIsNotNone(self.invoice.gra_cleared_at)
        self.assertIsNotNone(self.invoice.gra_submitted_at)

    def test_clearance_compiles_vector_qr_svg_in_ram(self) -> None:
        """Clearance compiles vector SVG QR code and persists XML in invoice.gra_qr_code."""
        mock_client = MockGraEvatClient()

        with (
            patch("apps.tax.tasks.get_gra_client", return_value=mock_client),
            patch(
                "apps.invoicing.services.pdf_service.get_storage_service",
                return_value=self.mock_storage,
            ),
        ):
            clear_with_gra(str(self.invoice.id))

        self.invoice.refresh_from_db()
        self.assertIsNotNone(self.invoice.gra_qr_code)
        # Vector SVG assertion
        self.assertTrue(
            self.invoice.gra_qr_code.strip().startswith("<?xml")
            or "<svg" in self.invoice.gra_qr_code
        )
        self.assertIn("</svg>", self.invoice.gra_qr_code)

    def test_clearance_recompiles_air_gapped_pdf_and_uploads_to_r2(self) -> None:
        """Clearance regenerates air-gapped PDF with green certified stamp and uploads to R2."""
        mock_client = MockGraEvatClient()

        with (
            patch("apps.tax.tasks.get_gra_client", return_value=mock_client),
            patch(
                "apps.invoicing.services.pdf_service.get_storage_service",
                return_value=self.mock_storage,
            ),
        ):
            clear_with_gra(str(self.invoice.id))

        self.invoice.refresh_from_db()
        self.assertIsNotNone(self.invoice.pdf_url)
        self.assertTrue(self.mock_storage.file_exists(self.invoice.pdf_url))

        # Inspect raw PDF bytes stored in R2
        pdf_bytes = self.mock_storage.get_file_bytes(self.invoice.pdf_url)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    def test_clearance_preserves_paid_status_on_already_settled_invoice(self) -> None:
        """Invoice already settled via MoMo retains PAID status when clearance completes."""
        self.invoice.status = InvoiceStatusChoices.PAID
        self.invoice.paid_amount = Decimal("1200.0000")
        self.invoice.save()

        mock_client = MockGraEvatClient()

        with (
            patch("apps.tax.tasks.get_gra_client", return_value=mock_client),
            patch(
                "apps.invoicing.services.pdf_service.get_storage_service",
                return_value=self.mock_storage,
            ),
        ):
            result = clear_with_gra(str(self.invoice.id))

        self.assertEqual(result["status"], "CLEARED")
        self.invoice.refresh_from_db()

        # CRITICAL ACCOUNTING INVARIANT: Must NOT revert to CLEARED
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("1200.0000"))
        # Statutory fields are nonetheless populated
        self.assertIsNotNone(self.invoice.gra_clearance_code)
        self.assertIsNotNone(self.invoice.gra_cleared_at)

    def test_clearance_preserves_partially_paid_status(self) -> None:
        """Invoice partially settled retains PARTIALLY_PAID status upon GRA clearance."""
        self.invoice.status = InvoiceStatusChoices.PARTIALLY_PAID
        self.invoice.paid_amount = Decimal("500.0000")
        self.invoice.save()

        mock_client = MockGraEvatClient()

        with (
            patch("apps.tax.tasks.get_gra_client", return_value=mock_client),
            patch(
                "apps.invoicing.services.pdf_service.get_storage_service",
                return_value=self.mock_storage,
            ),
        ):
            result = clear_with_gra(str(self.invoice.id))

        self.assertEqual(result["status"], "CLEARED")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.PARTIALLY_PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal("500.0000"))

    def test_clearance_is_idempotent_on_already_cleared_invoice(self) -> None:
        """Re-invoking clearance on a CLEARED invoice returns ALREADY_CLEARED immediately."""
        self.invoice.status = InvoiceStatusChoices.CLEARED
        self.invoice.gra_clearance_code = "GRA-2026-ALREADY-SET"
        self.invoice.save()

        mock_client = MockGraEvatClient()

        with (
            patch("apps.tax.tasks.get_gra_client", return_value=mock_client),
            patch(
                "apps.invoicing.services.pdf_service.get_storage_service",
                return_value=self.mock_storage,
            ),
        ):
            result = clear_with_gra(str(self.invoice.id))

        self.assertEqual(result["status"], "ALREADY_CLEARED")
        self.assertEqual(len(mock_client.submitted_payloads), 0)

    def test_cancelled_invoice_aborts_clearance(self) -> None:
        """Cancelled invoices are not submitted to GRA."""
        self.invoice.status = InvoiceStatusChoices.CANCELLED
        self.invoice.save()

        mock_client = MockGraEvatClient()

        with patch("apps.tax.tasks.get_gra_client", return_value=mock_client):
            result = clear_with_gra(str(self.invoice.id))

        self.assertEqual(result["status"], "CANCELLED")
        self.assertEqual(len(mock_client.submitted_payloads), 0)

    def test_invoicing_service_dispatches_celery_task_on_creation(self) -> None:
        """InvoicingService.create_and_post_invoice automatically triggers clear_with_gra."""
        mock_client = MockGraEvatClient()

        data = {
            "customer_id": str(self.customer.id),
            "lines": [
                {
                    "description": "Consulting Services",
                    "quantity": Decimal("1.0000"),
                    "unit_price": Decimal("2000.0000"),
                }
            ],
            "issue_date": timezone.now().date(),
            "due_date": timezone.now().date() + timezone.timedelta(days=7),
            "action": "issue",
        }

        with (
            patch("apps.tax.tasks.get_gra_client", return_value=mock_client),
            patch(
                "apps.invoicing.services.pdf_service.get_storage_service",
                return_value=self.mock_storage,
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            inv = InvoicingService.create_and_post_invoice(
                organization=self.org,
                user=None,
                data=data,
            )

        # In CELERY_TASK_ALWAYS_EAGER mode, task runs synchronously to completion
        inv.refresh_from_db()
        self.assertEqual(inv.status, InvoiceStatusChoices.CLEARED)
        self.assertIsNotNone(inv.gra_clearance_code)

    def test_retry_pending_gra_management_command(self) -> None:
        """retry_pending_gra command re-queues all un-cleared PENDING_GRA invoices."""
        mock_client = MockGraEvatClient()
        out = StringIO()

        with (
            patch("apps.tax.tasks.get_gra_client", return_value=mock_client),
            patch(
                "apps.invoicing.services.pdf_service.get_storage_service",
                return_value=self.mock_storage,
            ),
        ):
            call_command("retry_pending_gra", limit=10, stdout=out)

        output = out.getvalue()
        self.assertIn("Found 1 invoice(s) pending GRA clearance", output)
        self.assertIn("Successfully re-queued 1/1 pending invoice(s)", output)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatusChoices.CLEARED)
