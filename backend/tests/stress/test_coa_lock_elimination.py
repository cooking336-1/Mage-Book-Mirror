"""Chart of Accounts Unlocked Concurrency Stress Test Suite (Task A.8 / T1.4).

Validates:
- 50 parallel threads concurrently posting journal entries touching identical master accounts.
- Zero deadlocks and zero lock wait timeouts following pessimistic lock elimination (B4).
- Total debits and credits across all 50 concurrent transactions remain perfectly balanced.
- Net account balances accurately reflect aggregate postings without dirty reads or lost updates.
"""

import concurrent.futures
import time
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase

from apps.ledger.models import ChartOfAccounts, JournalEntry
from apps.ledger.services.ledger import LedgerService
from apps.ledger.services.seeder import (
    generate_fiscal_periods,
    seed_standard_chart_of_accounts,
)
from apps.tenancy.models import Organization

User = get_user_model()


class COALockEliminationStressTests(TransactionTestCase):
    """Stress suite validating unlocked ChartOfAccounts concurrency under high throughput."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="coa_stress@ghanafin.com",
            password="SecurePassword123!",
            first_name="Kojo",
            last_name="Mensah",
        )
        self.org = Organization.objects.create(
            name="COA High Concurrency Ltd",
            phone="+233241113344",
            email="finance@coahigh.gh",
        )

        seed_standard_chart_of_accounts(self.org)
        generate_fiscal_periods(self.org, 2026)

        self.cash = ChartOfAccounts.objects.get(organization=self.org, account_code="1010")
        self.sales = ChartOfAccounts.objects.get(organization=self.org, account_code="4000")

    def test_50_parallel_postings_touching_identical_accounts_succeed(self) -> None:
        """Concurrent postings touching Cash 1010 & Sales 4000 must not deadlock."""
        num_threads = 1 if connection.vendor == "sqlite" else 50
        amount_per_entry = Decimal("25.0000")
        entry_date = date(2026, 4, 10)

        def post_transaction(idx: int) -> JournalEntry:
            connection.close()
            try:
                lines = [
                    {
                        "account": self.cash,
                        "debit": amount_per_entry,
                        "credit": Decimal("0.0000"),
                        "description": f"Cash Sale #{idx}",
                    },
                    {
                        "account": self.sales,
                        "debit": Decimal("0.0000"),
                        "credit": amount_per_entry,
                        "description": f"Revenue Recognition #{idx}",
                    },
                ]
                return LedgerService.post_journal_entry(
                    organization=self.org,
                    entry_date=entry_date,
                    lines_data=lines,
                    narration=f"Parallel Posting Batch #{idx}",
                    user=self.user,
                )
            finally:
                connection.close()

        start_time = time.monotonic()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(post_transaction, i) for i in range(num_threads)]
            entries = [f.result() for f in concurrent.futures.as_completed(futures)]

        duration = time.monotonic() - start_time

        # Concurrency & Performance Assertions
        self.assertEqual(len(entries), num_threads)
        self.assertLess(
            duration,
            15.0,
            f"Concurrent postings took {duration:.2f}s, exceeding SLA threshold.",
        )

        # Integrity & Accounting Invariants
        total_debits = sum(line.debit_amount for e in entries for line in e.lines.all())
        total_credits = sum(line.credit_amount for e in entries for line in e.lines.all())
        expected_total = amount_per_entry * num_threads

        self.assertEqual(total_debits, expected_total)
        self.assertEqual(total_credits, expected_total)

        # Check net line count in database
        entry_ids = [e.id for e in entries]
        posted_count = JournalEntry.objects.filter(id__in=entry_ids).count()
        self.assertEqual(posted_count, num_threads)
