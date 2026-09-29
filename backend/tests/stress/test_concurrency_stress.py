"""Multi-Threaded Concurrency Test Harness for Invoice Sequence Generation (Task A.8 / T1.1).

Validates:
- Spawns 20 threads simultaneously issuing invoices for the same tenant under PostgreSQL.
- Must produce exactly 20 unique, gapless numbers with 0 duplicate key IntegrityErrors.
- Real row-level locking via dedicated InvoiceSequence table under concurrent transactions.
"""

import concurrent.futures
import datetime
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TransactionTestCase

from apps.invoicing.models import Contact, ContactTypeChoices, Invoice, InvoiceSequence
from apps.invoicing.services.invoicing_service import InvoicingService
from apps.ledger.services.seeder import seed_standard_chart_of_accounts
from apps.tenancy.models import Organization, TaxSchemeChoices


class ConcurrencyStressTests(TransactionTestCase):
    """Stress test harness exercising concurrent invoice creation and sequence generation."""

    def setUp(self) -> None:
        self.org = Organization.objects.create(
            name="Concurrent Corp Ltd",
            business_tin="C0009988776",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )
        self.customer = Contact.objects.create(
            organization=self.org,
            name="Concurrent Buyer Ltd",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="C0001234567",
        )
        # Pre-seed standard chart of accounts so invoice GL posting has necessary accounts
        seed_standard_chart_of_accounts(self.org)

    def test_20_parallel_invoice_creations_generate_gapless_unique_numbers(self) -> None:
        """Verify concurrent threads issuing invoices produce gapless unique numbers."""
        num_threads = 1 if connection.vendor == "sqlite" else 20
        date_today = datetime.date(2026, 9, 28)

        def create_single_invoice(idx: int) -> Invoice:
            connection.close()
            try:
                with patch("apps.invoicing.services.invoicing_service.enqueue_gra_clearance"):
                    return InvoicingService.create_invoice(
                        organization=self.org,
                        customer=self.customer,
                        issue_date=date_today,
                        items=[
                            {
                                "description": f"Batch Item {idx}",
                                "unit_price": Decimal("50.00"),
                                "quantity": 1,
                            }
                        ],
                    )
            finally:
                connection.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_single_invoice, i) for i in range(num_threads)]
            invoices = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(invoices), num_threads)
        invoice_numbers = [inv.invoice_number for inv in invoices]
        unique_numbers = set(invoice_numbers)
        self.assertEqual(
            len(unique_numbers),
            num_threads,
            f"All concurrent invoice numbers must be unique. Got duplicates: {invoice_numbers}",
        )

        expected_numbers = {f"INV-{date_today.year}-{i:05d}" for i in range(1, num_threads + 1)}
        self.assertEqual(
            unique_numbers,
            expected_numbers,
            "Sequence numbers must be strictly gapless.",
        )

        # Verify sequence record in database matches exact count
        seq_record = InvoiceSequence.objects.get(organization=self.org, year=date_today.year)
        self.assertEqual(seq_record.last_number, num_threads)
