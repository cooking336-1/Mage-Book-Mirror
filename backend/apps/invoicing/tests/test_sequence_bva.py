"""Boundary Value Analysis (BVA) & Sequence Generation Tests for Invoicing.

Verifies:
1. Fiscal year rollover sequence reset (2025-12-31 to 2026-01-01).
2. Dynamic padding overflow (100,000+) without truncation or formatting failure.
3. First-invoice initialization in a new fiscal year.
4. Monotonic gapless sequence increments per organization and year partition.
"""

import datetime
from decimal import Decimal

from django.test import TestCase

from apps.invoicing.models import Contact, ContactTypeChoices, Invoice, InvoiceSequence
from apps.invoicing.services.invoicing_service import InvoicingService
from apps.tenancy.middleware import clear_current_tenant, set_current_tenant
from apps.tenancy.models import Organization, RoleChoices, TaxSchemeChoices


class InvoiceSequenceBoundaryTests(TestCase):
    """BVA test suite verifying gapless invoice sequence counters and year boundaries."""

    def setUp(self) -> None:
        self.org = Organization.objects.create(
            name="Boundary Enterprise Ltd",
            business_tin="C0001122334",
            phone="+233240001122",
            email="finance@boundary.gh",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        self.customer = Contact.objects.create(
            organization=self.org,
            name="Retail Partner Ltd",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="C0009988776",
            billing_address="Accra Central, Ghana",
        )
        set_current_tenant(self.org, RoleChoices.OWNER)

    def tearDown(self) -> None:
        clear_current_tenant()
        super().tearDown()

    def test_fiscal_year_rollover_sequence_reset(self) -> None:
        """Verifies that invoice numbering resets to 00001 on Jan 1st of a new year."""
        date_2025 = datetime.date(2025, 12, 31)
        date_2026 = datetime.date(2026, 1, 1)

        # Issue final 2025 invoice
        inv_2025 = InvoicingService.create_invoice(
            organization=self.org,
            customer=self.customer,
            issue_date=date_2025,
            items=[
                {
                    "description": "2025 Final Consulting",
                    "unit_price": Decimal("100.00"),
                    "quantity": 1,
                }
            ],
        )
        self.assertEqual(inv_2025.invoice_number, "INV-2025-00001")

        # Issue first 2026 invoice
        inv_2026 = InvoicingService.create_invoice(
            organization=self.org,
            customer=self.customer,
            issue_date=date_2026,
            items=[
                {
                    "description": "2026 Initial Retainer",
                    "unit_price": Decimal("250.00"),
                    "quantity": 1,
                }
            ],
        )
        self.assertEqual(inv_2026.invoice_number, "INV-2026-00001")

        # Verify distinct yearly sequences in InvoiceSequence
        seq_2025 = InvoiceSequence.objects.get(organization=self.org, year=2025)
        seq_2026 = InvoiceSequence.objects.get(organization=self.org, year=2026)
        self.assertEqual(seq_2025.last_number, 1)
        self.assertEqual(seq_2026.last_number, 1)

    def test_sequence_padding_overflow(self) -> None:
        """Verifies sequence numbers beyond 5 digits (100,000+) format safely."""
        seq, _ = InvoiceSequence.objects.get_or_create(
            organization=self.org, year=2026, defaults={"last_number": 99999}
        )
        seq.last_number = 99999
        seq.save(update_fields=["last_number", "updated_at"])

        inv = InvoicingService.create_invoice(
            organization=self.org,
            customer=self.customer,
            issue_date=datetime.date(2026, 6, 1),
            items=[
                {
                    "description": "High Volume Item",
                    "unit_price": Decimal("10.00"),
                    "quantity": 1,
                }
            ],
        )
        self.assertEqual(inv.invoice_number, "INV-2026-100000")

    def test_multi_tenant_sequence_isolation(self) -> None:
        """Verifies sequence counters are strictly isolated across multiple tenants."""
        org_beta = Organization.objects.create(
            name="Beta Distributors Ltd",
            business_tin="C0005566778",
            phone="+233201112233",
            email="accounts@beta.gh",
            vat_registered=True,
        )
        cust_beta = Contact.objects.create(
            organization=org_beta,
            name="Beta Client",
            contact_type=ContactTypeChoices.CUSTOMER,
        )

        inv_alpha_1 = InvoicingService.create_invoice(
            organization=self.org,
            customer=self.customer,
            issue_date=datetime.date(2026, 3, 1),
            items=[{"description": "Alpha Item", "unit_price": Decimal("50.00"), "quantity": 1}],
        )
        inv_beta_1 = InvoicingService.create_invoice(
            organization=org_beta,
            customer=cust_beta,
            issue_date=datetime.date(2026, 3, 1),
            items=[{"description": "Beta Item", "unit_price": Decimal("75.00"), "quantity": 1}],
        )

        self.assertEqual(inv_alpha_1.invoice_number, "INV-2026-00001")
        self.assertEqual(inv_beta_1.invoice_number, "INV-2026-00001")

        inv_alpha_2 = InvoicingService.create_invoice(
            organization=self.org,
            customer=self.customer,
            issue_date=datetime.date(2026, 3, 2),
            items=[{"description": "Alpha Item 2", "unit_price": Decimal("50.00"), "quantity": 1}],
        )
        self.assertEqual(inv_alpha_2.invoice_number, "INV-2026-00002")

    def test_existing_invoice_synchronization_on_sequence_creation(self) -> None:
        """Verifies counter synchronizes if pre-existing invoices exist before sequence creation."""
        # Directly insert an invoice simulating historical records
        historical_invoice = Invoice.objects.create(
            organization=self.org,
            customer=self.customer,
            invoice_number="INV-2026-00001",
            issue_date=datetime.date(2026, 1, 15),
            due_date=datetime.date(2026, 2, 15),
            total_amount=Decimal("100.0000"),
        )
        self.assertIsNotNone(historical_invoice.pk)

        # Ensure no InvoiceSequence row exists yet for 2026
        InvoiceSequence.objects.filter(organization=self.org, year=2026).delete()

        # Issuing via InvoicingService should detect existing count and advance to 00002
        new_inv = InvoicingService.create_invoice(
            organization=self.org,
            customer=self.customer,
            issue_date=datetime.date(2026, 1, 16),
            items=[
                {
                    "description": "Subsequent Item",
                    "unit_price": Decimal("80.00"),
                    "quantity": 1,
                }
            ],
        )
        self.assertEqual(new_inv.invoice_number, "INV-2026-00002")
