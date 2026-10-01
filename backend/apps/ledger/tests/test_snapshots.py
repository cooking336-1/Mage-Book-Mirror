"""Unit & Integration Tests for Materialized AccountSnapshot and Celery Rollup (G4)."""

import datetime
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from apps.ledger.models import (
    AccountSnapshot,
    ChartOfAccounts,
)
from apps.ledger.selectors import get_account_balance
from apps.ledger.services.ledger import LedgerService
from apps.ledger.services.seeder import seed_standard_chart_of_accounts
from apps.ledger.tasks import rollup_account_snapshots_task
from apps.tenancy.models import Organization


class AccountSnapshotModelTestCase(TestCase):
    """Verifies schema constraints and invariants of AccountSnapshot."""

    def setUp(self) -> None:
        self.org = Organization.objects.create(name="Snapshot Enterprise Ltd")
        seed_standard_chart_of_accounts(self.org)
        self.cash_acc = ChartOfAccounts.objects.get(organization=self.org, account_code="1010")

    def test_create_account_snapshot(self) -> None:
        """Verifies creating an AccountSnapshot record with correct period and totals."""
        period_end = datetime.date(2026, 1, 31)
        snap = AccountSnapshot.objects.create(
            organization=self.org,
            account=self.cash_acc,
            period_end=period_end,
            total_debits=Decimal("15000.0000"),
            total_credits=Decimal("5000.0000"),
            closing_balance=Decimal("10000.0000"),
        )
        self.assertIsNotNone(snap.id)
        self.assertEqual(snap.closing_balance, Decimal("10000.0000"))
        self.assertIn("1010", str(snap))

    def test_unique_constraint_on_org_account_period(self) -> None:
        """Enforces that an account can only have one snapshot per period_end date."""
        period_end = datetime.date(2026, 1, 31)
        AccountSnapshot.objects.create(
            organization=self.org,
            account=self.cash_acc,
            period_end=period_end,
            total_debits=Decimal("5000.0000"),
            total_credits=Decimal("2000.0000"),
            closing_balance=Decimal("3000.0000"),
        )

        with self.assertRaises(IntegrityError):
            AccountSnapshot.objects.create(
                organization=self.org,
                account=self.cash_acc,
                period_end=period_end,
                total_debits=Decimal("6000.0000"),
                total_credits=Decimal("2500.0000"),
                closing_balance=Decimal("3500.0000"),
            )


class AccountSnapshotRollupTaskTestCase(TestCase):
    """Verifies Celery background task for period closing monthly snapshot rollups."""

    def setUp(self) -> None:
        self.org = Organization.objects.create(name="Rollup Trading Co")
        seed_standard_chart_of_accounts(self.org)
        self.cash_acc = ChartOfAccounts.objects.get(organization=self.org, account_code="1010")
        self.sales_acc = ChartOfAccounts.objects.get(organization=self.org, account_code="4000")

        # Post a journal entry in January 2026 via LedgerService
        LedgerService.post_journal_entry(
            organization=self.org,
            entry_date=datetime.date(2026, 1, 15),
            lines_data=[
                {
                    "account": self.cash_acc,
                    "debit": Decimal("12000.0000"),
                    "credit": Decimal("0.0000"),
                },
                {
                    "account": self.sales_acc,
                    "debit": Decimal("0.0000"),
                    "credit": Decimal("12000.0000"),
                },
            ],
            narration="January cash sales",
        )

    def test_rollup_task_execution(self) -> None:
        """Runs the rollup celery task and verifies snapshots are materialized accurately."""
        period_end_str = "2026-01-31"
        res = rollup_account_snapshots_task(
            organization_id=str(self.org.id),
            period_end_str=period_end_str,
        )
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(res["processed_organizations"], 1)

        # Cash Account Snapshot Check
        cash_snap = AccountSnapshot.objects.filter(
            organization=self.org,
            account=self.cash_acc,
            period_end=datetime.date(2026, 1, 31),
        ).first()
        self.assertIsNotNone(cash_snap)
        self.assertEqual(cash_snap.total_debits, Decimal("12000.0000"))
        self.assertEqual(cash_snap.total_credits, Decimal("0.0000"))
        self.assertEqual(cash_snap.closing_balance, Decimal("12000.0000"))

        # Sales Account Snapshot Check
        sales_snap = AccountSnapshot.objects.filter(
            organization=self.org,
            account=self.sales_acc,
            period_end=datetime.date(2026, 1, 31),
        ).first()
        self.assertIsNotNone(sales_snap)
        self.assertEqual(sales_snap.total_debits, Decimal("0.0000"))
        self.assertEqual(sales_snap.total_credits, Decimal("12000.0000"))
        self.assertEqual(sales_snap.closing_balance, Decimal("12000.0000"))

    def test_incremental_query_combines_snapshot_and_subsequent_entries(self) -> None:
        """Verifies that balance query seamlessly adds incremental journal lines post-snapshot."""
        # 1. Run rollup for January 2026
        rollup_account_snapshots_task(
            organization_id=str(self.org.id),
            period_end_str="2026-01-31",
        )

        # 2. Add February 2026 journal entry
        LedgerService.post_journal_entry(
            organization=self.org,
            entry_date=datetime.date(2026, 2, 10),
            lines_data=[
                {
                    "account": self.cash_acc,
                    "debit": Decimal("8000.0000"),
                    "credit": Decimal("0.0000"),
                },
                {
                    "account": self.sales_acc,
                    "debit": Decimal("0.0000"),
                    "credit": Decimal("8000.0000"),
                },
            ],
            narration="February cash sales",
        )

        # 3. Query balance as of 2026-02-15
        cash_balance = get_account_balance(
            organization=self.org,
            account=self.cash_acc,
            as_of_date=datetime.date(2026, 2, 15),
        )
        # Expected: 12,000 (from Jan snapshot) + 8,000 (from Feb journal line) = 20,000
        self.assertEqual(cash_balance, Decimal("20000.0000"))

        sales_balance = get_account_balance(
            organization=self.org,
            account=self.sales_acc,
            as_of_date=datetime.date(2026, 2, 15),
        )
        self.assertEqual(sales_balance, Decimal("20000.0000"))
