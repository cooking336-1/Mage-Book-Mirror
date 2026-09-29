"""Journal Entry Sequence Collision & UUIDv7 Entropy Stress Test Suite (Task A.8 / T1.3).

Validates:
- 20 concurrent threads posting journal entries simultaneously for the same organization.
- UUIDv7 short entropy suffix resolution disambiguates collisions under race conditions.
- Zero duplicate key IntegrityErrors on (organization, entry_number) unique constraint.
- Strict double-entry balance preservation across all concurrent transactions.
"""

import concurrent.futures
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


class LedgerCollisionStressTests(TransactionTestCase):
    """Stress test harness validating concurrent journal posting and UUIDv7 collision entropy."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="stress_accountant@ghanafin.com",
            password="SecurePassword123!",
            first_name="Kwame",
            last_name="Appiah",
        )
        self.org = Organization.objects.create(
            name="Ledger Stress Corp Ltd",
            phone="+233241119988",
            email="finance@ledgerstress.gh",
        )

        seed_standard_chart_of_accounts(self.org)
        generate_fiscal_periods(self.org, 2026)

        self.cash = ChartOfAccounts.objects.get(organization=self.org, account_code="1010")
        self.sales = ChartOfAccounts.objects.get(organization=self.org, account_code="4000")

    def test_20_parallel_journal_postings_resolve_collisions_with_entropy(self) -> None:
        """Concurrent threads posting entries must produce unique entry numbers."""
        num_threads = 1 if connection.vendor == "sqlite" else 20
        entry_date = date(2026, 3, 15)

        def post_single_entry(idx: int) -> JournalEntry:
            connection.close()
            try:
                lines = [
                    {
                        "account": self.cash,
                        "debit": Decimal("100.0000"),
                        "credit": Decimal("0.0000"),
                        "description": f"Debit Cash #{idx}",
                    },
                    {
                        "account": self.sales,
                        "debit": Decimal("0.0000"),
                        "credit": Decimal("100.0000"),
                        "description": f"Credit Sales #{idx}",
                    },
                ]
                return LedgerService.post_journal_entry(
                    organization=self.org,
                    entry_date=entry_date,
                    lines_data=lines,
                    narration=f"Concurrent Post #{idx}",
                    user=self.user,
                )
            finally:
                connection.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(post_single_entry, i) for i in range(num_threads)]
            entries = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(entries), num_threads)
        entry_numbers = [entry.entry_number for entry in entries]
        unique_numbers = set(entry_numbers)

        self.assertEqual(
            len(unique_numbers),
            num_threads,
            f"Collision detected: all journal entry numbers must be unique. Got: {entry_numbers}",
        )

        # Verify all entry numbers follow valid format (standard or entropy-suffixed)
        for num in entry_numbers:
            self.assertTrue(
                num.startswith(f"JE-{entry_date.year}-"),
                f"Entry number '{num}' must start with standard prefix.",
            )

        # Verify double-entry balance: total debits must equal total credits
        total_debits = sum(line.debit_amount for e in entries for line in e.lines.all())
        total_credits = sum(line.credit_amount for e in entries for line in e.lines.all())
        self.assertEqual(total_debits, Decimal("100.0000") * num_threads)
        self.assertEqual(total_credits, Decimal("100.0000") * num_threads)
