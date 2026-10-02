"""Integration test suite for Public Shareable Invoice Viewer (Task B.3 / B8 & T2.3).

Validates:
1. Anonymous GET /api/v1/invoicing/public/invoices/<uuid:share_token>/ succeeds with 200 OK.
2. TenantSecurityMiddleware does NOT block requests to public endpoint (exempt from X-Tenant-ID).
3. Private tenant fields and ledger account details are stripped from response.
4. Line items include quantities, prices, and tax amounts without internal COA references.
5. Public alias route /api/v1/public/invoices/<uuid:share_token>/ resolves identically.
6. Non-existent or malformed share_tokens return HTTP 404 Not Found.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.invoicing.models import Contact, Invoice, InvoiceLine, InvoiceStatusChoices
from apps.invoicing.utils import generate_invoice_payment_reference
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization

User = get_user_model()


class PublicInvoiceAPITests(TestCase):
    """APIClient integration tests for anonymous public invoice viewing."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()

        # Create tenant organization
        self.org = Organization.objects.create(
            name="Accra Wholesale Supplies Ltd",
            business_tin="C0012345678",
            phone="+233240001111",
            email="billing@accrawholesale.gh",
            address="Plot 5 Industrial Area, Accra",
            settlement_bank_name="GCB Bank PLC",
            settlement_account_number="1010101010101",
            settlement_momo_number="+233249998877",
        )

        # Create contact
        self.contact = Contact.objects.create(
            organization=self.org,
            name="Tema Logistics Corp",
            tin="C0009876543",
            phone="+233241112233",
            email="accounts@temalogistics.gh",
            billing_address="Harbour Road, Tema",
        )

        # Create invoice with valid Luhn payment reference
        self.payment_ref = generate_invoice_payment_reference(self.org)
        self.invoice = Invoice.objects.create(
            organization=self.org,
            customer=self.contact,
            invoice_number="INV-ACCRA-2026-00001",
            payment_reference=self.payment_ref,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=30),
            status=InvoiceStatusChoices.PENDING_GRA,
            currency="GHS",
            subtotal_amount=Decimal("1000.0000"),
            vat_amount=Decimal("150.0000"),
            nhil_amount=Decimal("25.0000"),
            getfund_amount=Decimal("25.0000"),
            total_amount=Decimal("1200.0000"),
            paid_amount=Decimal("0.0000"),
            customer_name="Tema Logistics Corp",
            customer_tin="C0009876543",
            customer_address="Harbour Road, Tema",
            customer_phone="+233241112233",
            customer_email="accounts@temalogistics.gh",
            gra_clearance_code="GRA-ACCRA-2026-X99",
            gra_qr_code="data:image/svg+xml;base64,PHN2Z...",
        )

        # Create invoice line
        self.line = InvoiceLine.objects.create(
            organization=self.org,
            invoice=self.invoice,
            description="Consulting & Supply Chain Services",
            quantity=Decimal("10.0000"),
            unit_price=Decimal("100.0000"),
            line_total=Decimal("1000.0000"),
            is_taxable=True,
            vat_rate=Decimal("0.1500"),
            nhil_rate=Decimal("0.0250"),
            getfund_rate=Decimal("0.0250"),
            vat_amount=Decimal("150.0000"),
            nhil_amount=Decimal("25.0000"),
            getfund_amount=Decimal("25.0000"),
        )

        # Ensure client is unauthenticated (anonymous guest)
        self.client.credentials()

    def tearDown(self) -> None:
        clear_current_tenant()

    def test_anonymous_get_public_invoice_success(self) -> None:
        """Anonymous GET /api/v1/invoicing/public/invoices/<uuid>/ succeeds without auth."""
        url = f"/api/v1/invoicing/public/invoices/{self.invoice.share_token}/"
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200 OK, got {response.status_code}: {response.data}",
        )

        data = response.data
        self.assertEqual(data["invoice_number"], "INV-ACCRA-2026-00001")
        self.assertEqual(data["payment_reference"], self.payment_ref)
        self.assertEqual(str(data["share_token"]), str(self.invoice.share_token))
        self.assertEqual(data["business_name"], "Accra Wholesale Supplies Ltd")
        self.assertEqual(data["business_tin"], "C0012345678")
        self.assertEqual(data["customer_name"], "Tema Logistics Corp")
        self.assertEqual(data["customer_tin"], "C0009876543")
        self.assertEqual(Decimal(data["subtotal_amount"]), Decimal("1000.0000"))
        self.assertEqual(Decimal(data["total_amount"]), Decimal("1200.0000"))
        self.assertEqual(data["gra_clearance_code"], "GRA-ACCRA-2026-X99")

        # Verify lines are serialized
        lines = data.get("lines", [])
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["description"], "Consulting & Supply Chain Services")
        self.assertEqual(Decimal(lines[0]["quantity"]), Decimal("10.0000"))
        self.assertEqual(Decimal(lines[0]["unit_price"]), Decimal("100.0000"))
        self.assertEqual(Decimal(lines[0]["line_total"]), Decimal("1000.0000"))

    def test_private_tenant_ledger_fields_stripped(self) -> None:
        """Internal accounting coordinates and GL account references are omitted from public DTO."""
        url = f"/api/v1/invoicing/public/invoices/{self.invoice.share_token}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        # 1. Organization private banking coordinates must not leak
        self.assertNotIn("settlement_bank_name", data)
        self.assertNotIn("settlement_account_number", data)
        self.assertNotIn("settlement_momo_number", data)
        self.assertNotIn("owner_email", data)

        # 2. Line item internal general ledger account references must not leak
        line_data = data["lines"][0]
        self.assertNotIn("account", line_data)
        self.assertNotIn("account_id", line_data)
        self.assertNotIn("account_number", line_data)

    def test_public_alias_route_resolves_identically(self) -> None:
        """GET /api/v1/public/invoices/<uuid>/ works as valid alias route."""
        url = f"/api/v1/public/invoices/{self.invoice.share_token}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["invoice_number"], "INV-ACCRA-2026-00001")

    def test_nonexistent_share_token_returns_404(self) -> None:
        """Random unissued share_token returns HTTP 404 Not Found."""
        random_token = uuid.uuid4()
        url = f"/api/v1/invoicing/public/invoices/{random_token}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_malformed_token_returns_404(self) -> None:
        """Malformed non-UUID string returns HTTP 404 without 500 error."""
        url = "/api/v1/invoicing/public/invoices/not-a-valid-uuid/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
