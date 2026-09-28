"""Tests for Luhn Payment Reference Active Collision Detection (Task A.2 / B2).

Verifies:
1. Baseline valid Luhn reference generation on invoice creation.
2. Active .exists() collision loop increments past existing references.
3. Multi-collision resolution skips multiple consecutive occupied sequence slots.
4. Strict multi-tenant isolation of payment reference namespaces.
5. Self-exclusion handling during invoice updates.
6. 100% mathematical validity under Luhn mod-10 verification.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.invoicing.models import Contact, ContactTypeChoices, Invoice, InvoiceStatusChoices
from apps.invoicing.utils import LuhnValidator, generate_invoice_payment_reference
from apps.tenancy.models import Organization


class LuhnPaymentReferenceCollisionTests(TestCase):
    """Boundary Value Analysis and Concurrency Collision Suite for Luhn Payment References."""

    def setUp(self) -> None:
        self.org_a = Organization.objects.create(
            name="Alpha Corp Ltd",
            business_tin="C0001112233",
        )
        self.org_b = Organization.objects.create(
            name="Beta Logistics Ltd",
            business_tin="C0009998877",
        )
        self.customer_a = Contact.objects.create(
            organization=self.org_a,
            name="Customer A",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="C0001234567",
        )
        self.customer_b = Contact.objects.create(
            organization=self.org_b,
            name="Customer B",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="C0009876543",
        )

    def test_baseline_luhn_reference_generation(self) -> None:
        """Invoice auto-generates a valid, formatted Luhn payment reference on initial save."""
        invoice = Invoice.objects.create(
            organization=self.org_a,
            customer=self.customer_a,
            invoice_number="INV-ALPHA-2026-00001",
            issue_date=date(2026, 9, 28),
            due_date=date(2026, 10, 28),
            total_amount=Decimal("100.0000"),
            status=InvoiceStatusChoices.DRAFT,
        )
        self.assertTrue(bool(invoice.payment_reference))
        self.assertTrue(LuhnValidator.validate(invoice.payment_reference))
        # Initial count = 0 -> seed = 10001 -> '10001-6'
        expected_ref = LuhnValidator.generate_reference(10001, delimiter="-")
        self.assertEqual(invoice.payment_reference, expected_ref)
        self.assertEqual(invoice.payment_reference, "10001-6")

    def test_active_collision_loop_increments_past_existing_reference(self) -> None:
        """When base sequence reference exists, loop advances to next available reference."""
        # Pre-seed invoice with '10001-6'
        ref_10001 = LuhnValidator.generate_reference(10001, delimiter="-")
        Invoice.objects.create(
            organization=self.org_a,
            customer=self.customer_a,
            invoice_number="INV-ALPHA-2026-00001",
            payment_reference=ref_10001,
            issue_date=date(2026, 9, 28),
            due_date=date(2026, 10, 28),
            total_amount=Decimal("200.0000"),
            status=InvoiceStatusChoices.DRAFT,
        )

        # Calling generator with seed 10001 must detect that '10001-6' exists and return '10002-4'
        resolved_ref = generate_invoice_payment_reference(self.org_a, seq_number=10001)
        expected_10002 = LuhnValidator.generate_reference(10002, delimiter="-")
        self.assertEqual(resolved_ref, expected_10002)
        self.assertEqual(resolved_ref, "10002-4")
        self.assertTrue(LuhnValidator.validate(resolved_ref))

    def test_consecutive_collision_resolution(self) -> None:
        """Collision loop safely iterates past multiple consecutive occupied references."""
        # Occupy 10001, 10002, 10003
        for seq, inv_num in [(10001, "INV-001"), (10002, "INV-002"), (10003, "INV-003")]:
            ref = LuhnValidator.generate_reference(seq, delimiter="-")
            Invoice.objects.create(
                organization=self.org_a,
                customer=self.customer_a,
                invoice_number=inv_num,
                payment_reference=ref,
                issue_date=date(2026, 9, 28),
                due_date=date(2026, 10, 28),
                total_amount=Decimal("300.0000"),
                status=InvoiceStatusChoices.DRAFT,
            )

        # Generation starting at seed 10001 must jump across all 3 to 10004-0
        next_ref = generate_invoice_payment_reference(self.org_a, seq_number=10001)
        expected_10004 = LuhnValidator.generate_reference(10004, delimiter="-")
        self.assertEqual(next_ref, expected_10004)
        self.assertEqual(next_ref, "10004-0")
        self.assertTrue(LuhnValidator.validate(next_ref))

    def test_multi_tenant_reference_isolation(self) -> None:
        """Tenant A occupying reference 10001-6 does not block Tenant B from using 10001-6."""
        inv_a = Invoice.objects.create(
            organization=self.org_a,
            customer=self.customer_a,
            invoice_number="INV-ALPHA-001",
            issue_date=date(2026, 9, 28),
            due_date=date(2026, 10, 28),
            total_amount=Decimal("500.0000"),
            status=InvoiceStatusChoices.DRAFT,
        )
        self.assertEqual(inv_a.payment_reference, "10001-6")

        # Org B generating its first invoice should also receive 10001-6 cleanly
        inv_b = Invoice.objects.create(
            organization=self.org_b,
            customer=self.customer_b,
            invoice_number="INV-BETA-001",
            issue_date=date(2026, 9, 28),
            due_date=date(2026, 10, 28),
            total_amount=Decimal("500.0000"),
            status=InvoiceStatusChoices.DRAFT,
        )
        self.assertEqual(inv_b.payment_reference, "10001-6")
        self.assertTrue(LuhnValidator.validate(inv_b.payment_reference))

    def test_exclude_invoice_id_on_update(self) -> None:
        """Updating an existing invoice does not self-collide with its own payment reference."""
        invoice = Invoice.objects.create(
            organization=self.org_a,
            customer=self.customer_a,
            invoice_number="INV-ALPHA-001",
            payment_reference="10001-6",
            issue_date=date(2026, 9, 28),
            due_date=date(2026, 10, 28),
            total_amount=Decimal("150.0000"),
            status=InvoiceStatusChoices.DRAFT,
        )
        # Re-generating with exclude_invoice_id allows keeping 10001-6
        ref = generate_invoice_payment_reference(
            self.org_a,
            seq_number=10001,
            exclude_invoice_id=invoice.id,
        )
        self.assertEqual(ref, "10001-6")

    def test_all_sequential_references_pass_luhn_validation(self) -> None:
        """Generates 25 sequential invoices and verifies all pass mod-10 Luhn check."""
        for i in range(1, 26):
            inv = Invoice.objects.create(
                organization=self.org_a,
                customer=self.customer_a,
                invoice_number=f"INV-ALPHA-{i:05d}",
                issue_date=date(2026, 9, 28),
                due_date=date(2026, 10, 28),
                total_amount=Decimal("50.0000"),
                status=InvoiceStatusChoices.DRAFT,
            )
            self.assertTrue(LuhnValidator.validate(inv.payment_reference))
