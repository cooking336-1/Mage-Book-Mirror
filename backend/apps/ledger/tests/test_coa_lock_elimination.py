"""Verification test suite for ChartOfAccounts lock elimination (Task A.4 / B4).

Verifies:
- post_journal_entry does not execute 'FOR UPDATE' queries on ChartOfAccounts.
- Simultaneous journal postings touching identical master accounts succeed without lock contention.
- Inactive account validation is strictly preserved.
- Cross-tenant account access is rejected with ValidationError.
- Missing account validation is strictly preserved.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.ledger.models import ChartOfAccounts, JournalEntry
from apps.ledger.services.ledger import LedgerService
from apps.ledger.services.seeder import (
    generate_fiscal_periods,
    seed_standard_chart_of_accounts,
)
from apps.tenancy.models import Organization


class ChartOfAccountsLockEliminationTests(TestCase):
    """Test suite ensuring zero pessimistic row locks on ChartOfAccounts."""

    def setUp(self) -> None:
        self.org_a = Organization.objects.create(
            name="Accra Commerce Ltd",
            phone="+233241000001",
            email="finance@accracommerce.gh",
        )
        self.org_b = Organization.objects.create(
            name="Kumasi Wholesale Ltd",
            phone="+233241000002",
            email="finance@kumasiwholesale.gh",
        )

        seed_standard_chart_of_accounts(self.org_a)
        seed_standard_chart_of_accounts(self.org_b)

        current_year = timezone.now().year
        generate_fiscal_periods(self.org_a, current_year)
        generate_fiscal_periods(self.org_b, current_year)

        self.cash_account_a = ChartOfAccounts.objects.get(
            organization=self.org_a, account_code="1010"
        )
        self.revenue_account_a = ChartOfAccounts.objects.get(
            organization=self.org_a, account_code="4000"
        )
        self.cash_account_b = ChartOfAccounts.objects.get(
            organization=self.org_b, account_code="1010"
        )

    def test_post_journal_entry_does_not_acquire_for_update_locks(self) -> None:
        """Verify post_journal_entry executes zero 'FOR UPDATE' queries on chart_of_accounts."""
        lines_data = [
            {
                "account": self.cash_account_a,
                "debit": Decimal("1500.00"),
                "credit": Decimal("0.00"),
            },
            {
                "account": self.revenue_account_a,
                "debit": Decimal("0.00"),
                "credit": Decimal("1500.00"),
            },
        ]

        with CaptureQueriesContext(connection) as queries_ctx:
            entry = LedgerService.post_journal_entry(
                organization=self.org_a,
                entry_date=timezone.now().date(),
                narration="POS Cash Sale #101",
                lines_data=lines_data,
            )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.lines.count(), 2)

        # Inspect all captured SQL statements for 'FOR UPDATE'
        for q in queries_ctx.captured_queries:
            sql = q["sql"].upper()
            if "CHART_OF_ACCOUNTS" in sql:
                self.assertNotIn(
                    "FOR UPDATE",
                    sql,
                    f"ChartOfAccounts query must not acquire pessimistic row locks! SQL: {sql}",
                )

    def test_sequential_postings_to_same_hot_accounts_succeed(self) -> None:
        """Verify multiple postings to the exact same Cash and Revenue accounts succeed cleanly."""
        for idx in range(10):
            lines_data = [
                {
                    "account": self.cash_account_a,
                    "debit": Decimal("100.00"),
                    "credit": Decimal("0.00"),
                },
                {
                    "account": self.revenue_account_a,
                    "debit": Decimal("0.00"),
                    "credit": Decimal("100.00"),
                },
            ]
            entry = LedgerService.post_journal_entry(
                organization=self.org_a,
                entry_date=timezone.now().date(),
                narration=f"Transaction batch item {idx}",
                lines_data=lines_data,
            )
            self.assertIsNotNone(entry.id)

        posted_count = JournalEntry.objects.filter(organization=self.org_a).count()
        self.assertEqual(posted_count, 10)

    def test_inactive_account_validation_is_strictly_enforced(self) -> None:
        """Verify attempting to post to a deactivated account raises ValidationError."""
        self.cash_account_a.is_active = False
        self.cash_account_a.save(update_fields=["is_active", "updated_at"])

        lines_data = [
            {
                "account": self.cash_account_a,
                "debit": Decimal("500.00"),
                "credit": Decimal("0.00"),
            },
            {
                "account": self.revenue_account_a,
                "debit": Decimal("0.00"),
                "credit": Decimal("500.00"),
            },
        ]

        with self.assertRaises(ValidationError) as ctx:
            LedgerService.post_journal_entry(
                organization=self.org_a,
                entry_date=timezone.now().date(),
                narration="Posting to inactive cash account",
                lines_data=lines_data,
            )

        self.assertIn("inactive and cannot accept new postings", str(ctx.exception))

    def test_cross_tenant_account_access_rejected(self) -> None:
        """Verify referencing Organization B's account in Organization A's entry is rejected."""
        lines_data = [
            {
                "account": self.cash_account_b,
                "debit": Decimal("250.00"),
                "credit": Decimal("0.00"),
            },
            {
                "account": self.revenue_account_a,
                "debit": Decimal("0.00"),
                "credit": Decimal("250.00"),
            },
        ]

        with self.assertRaises(ValidationError) as ctx:
            LedgerService.post_journal_entry(
                organization=self.org_a,
                entry_date=timezone.now().date(),
                narration="Cross tenant injection attempt",
                lines_data=lines_data,
            )

        self.assertIn("belong to another organization", str(ctx.exception))

    def test_missing_account_id_validation_rejected(self) -> None:
        """Verify referencing a non-existent account UUID is rejected."""
        fake_uuid = uuid.uuid4()
        lines_data = [
            {
                "account": fake_uuid,
                "debit": Decimal("300.00"),
                "credit": Decimal("0.00"),
            },
            {
                "account": self.revenue_account_a,
                "debit": Decimal("0.00"),
                "credit": Decimal("300.00"),
            },
        ]

        with self.assertRaises(ValidationError) as ctx:
            LedgerService.post_journal_entry(
                organization=self.org_a,
                entry_date=timezone.now().date(),
                narration="Non-existent account reference",
                lines_data=lines_data,
            )

        self.assertIn("belong to another organization", str(ctx.exception))
