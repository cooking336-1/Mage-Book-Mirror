"""Tests for Journal Entry Number Collision Defense and UUIDv7 Entropy Suffix (Task A.3 / B3).

Verifies:
1. Standard sequential journal entry generation (JE-2026-00001, JE-2026-00002).
2. Active .exists() collision defense falling back to time-sortable UUIDv7 entropy suffix.
3. Multi-tenant isolation of journal entry numbering.
4. Savepoint retry recovering cleanly from concurrent IntegrityError collision.
5. Caller-specified entry_number preservation without alteration.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from apps.ledger.models import (
    ChartOfAccounts,
    JournalEntry,
)
from apps.ledger.services.ledger import LedgerService
from apps.ledger.services.seeder import (
    generate_fiscal_periods,
    seed_standard_chart_of_accounts,
)
from apps.tenancy.models import Organization

User = get_user_model()


class JournalEntryCollisionTests(TestCase):
    """Test suite for journal entry number generation and UUIDv7 entropy collision fallback."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="accountant@ghanafin.com",
            password="SecurePassword123!",
            first_name="Kwame",
            last_name="Appiah",
        )
        self.org_a = Organization.objects.create(
            name="Alpha Holdings Ltd",
            phone="+233241112233",
            email="finance@alpha.gh",
        )
        self.org_b = Organization.objects.create(
            name="Beta Ventures Ltd",
            phone="+233249998877",
            email="finance@beta.gh",
        )

        seed_standard_chart_of_accounts(self.org_a)
        seed_standard_chart_of_accounts(self.org_b)

        generate_fiscal_periods(self.org_a, 2026)
        generate_fiscal_periods(self.org_b, 2026)

        # Retrieve accounts for balancing lines
        self.cash_a = ChartOfAccounts.objects.get(organization=self.org_a, account_code="1010")
        self.sales_a = ChartOfAccounts.objects.get(organization=self.org_a, account_code="4000")
        self.cash_b = ChartOfAccounts.objects.get(organization=self.org_b, account_code="1010")
        self.sales_b = ChartOfAccounts.objects.get(organization=self.org_b, account_code="4000")

    def _sample_lines_a(self, amount: Decimal = Decimal("500.0000")) -> list[dict]:
        return [
            {
                "account": self.cash_a,
                "debit": amount,
                "credit": Decimal("0.0000"),
                "description": "Debit Cash",
            },
            {
                "account": self.sales_a,
                "debit": Decimal("0.0000"),
                "credit": amount,
                "description": "Credit Sales",
            },
        ]

    def _sample_lines_b(self, amount: Decimal = Decimal("300.0000")) -> list[dict]:
        return [
            {
                "account": self.cash_b,
                "debit": amount,
                "credit": Decimal("0.0000"),
                "description": "Debit Cash",
            },
            {
                "account": self.sales_b,
                "debit": Decimal("0.0000"),
                "credit": amount,
                "description": "Credit Sales",
            },
        ]

    def test_standard_sequential_entry_number_generation(self) -> None:
        """First entry for 2026 generates JE-2026-00001, second generates JE-2026-00002."""
        entry_1 = LedgerService.post_journal_entry(
            organization=self.org_a,
            entry_date=date(2026, 3, 15),
            narration="First Transaction",
            lines_data=self._sample_lines_a(),
            user=self.user,
        )
        self.assertEqual(entry_1.entry_number, "JE-2026-00001")

        entry_2 = LedgerService.post_journal_entry(
            organization=self.org_a,
            entry_date=date(2026, 3, 16),
            narration="Second Transaction",
            lines_data=self._sample_lines_a(),
            user=self.user,
        )
        self.assertEqual(entry_2.entry_number, "JE-2026-00002")

    def test_active_collision_detection_uses_uuid7_entropy_suffix(self) -> None:
        """When pre-existing JE-2026-00003 exists and count computes 3, appends UUIDv7 entropy."""
        entry_1 = LedgerService.post_journal_entry(
            organization=self.org_a,
            entry_date=date(2026, 4, 1),
            narration="Base Entry 1",
            lines_data=self._sample_lines_a(),
            user=self.user,
        )
        self.assertEqual(entry_1.entry_number, "JE-2026-00001")

        # Pre-seed entry with JE-2026-00003
        entry_manual = LedgerService.post_journal_entry(
            organization=self.org_a,
            entry_date=date(2026, 4, 2),
            narration="Pre-seeded Slot 3",
            entry_number="JE-2026-00003",
            lines_data=self._sample_lines_a(),
            user=self.user,
        )
        self.assertEqual(entry_manual.entry_number, "JE-2026-00003")

        # Third entry: total entries for year is now 2. Next computed number is count + 1 = 3.
        # It detects JE-2026-00003 already exists, so it immediately falls back to UUIDv7 entropy.
        entry_collided = LedgerService.post_journal_entry(
            organization=self.org_a,
            entry_date=date(2026, 4, 3),
            narration="Auto Collided Entry",
            lines_data=self._sample_lines_a(),
            user=self.user,
        )

        self.assertNotEqual(entry_collided.entry_number, "JE-2026-00003")
        self.assertTrue(entry_collided.entry_number.startswith("JE-2026-"))
        suffix = entry_collided.entry_number.replace("JE-2026-", "")
        self.assertEqual(len(suffix), 8)

    def test_multi_tenant_journal_number_isolation(self) -> None:
        """Organization A and Organization B both independently generate JE-2026-00001."""
        entry_a = LedgerService.post_journal_entry(
            organization=self.org_a,
            entry_date=date(2026, 1, 10),
            narration="Org A First Entry",
            lines_data=self._sample_lines_a(),
            user=self.user,
        )
        entry_b = LedgerService.post_journal_entry(
            organization=self.org_b,
            entry_date=date(2026, 1, 10),
            narration="Org B First Entry",
            lines_data=self._sample_lines_b(),
            user=self.user,
        )
        self.assertEqual(entry_a.entry_number, "JE-2026-00001")
        self.assertEqual(entry_b.entry_number, "JE-2026-00001")
        self.assertNotEqual(entry_a.organization_id, entry_b.organization_id)

    def test_savepoint_retry_on_integrity_error_collision(self) -> None:
        """Simulated IntegrityError on create triggers savepoint retry with UUIDv7 suffix."""
        orig_create = JournalEntry.objects.create
        call_count = 0

        def flaky_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First attempt raises IntegrityError (simulating concurrent insert race)
                raise IntegrityError("unique constraint violated on entry_number")
            return orig_create(*args, **kwargs)

        with patch.object(JournalEntry.objects, "create", side_effect=flaky_create):
            entry = LedgerService.post_journal_entry(
                organization=self.org_a,
                entry_date=date(2026, 5, 1),
                narration="Savepoint Retry Entry",
                lines_data=self._sample_lines_a(),
                user=self.user,
            )

        self.assertEqual(call_count, 2)
        self.assertTrue(entry.entry_number.startswith("JE-2026-"))
        suffix = entry.entry_number.replace("JE-2026-", "")
        self.assertEqual(len(suffix), 8)

    def test_explicit_entry_number_is_preserved(self) -> None:
        """When an explicit entry_number is provided by the caller, it is stored as-is."""
        custom_number = "JE-CUSTOM-2026-999"
        entry = LedgerService.post_journal_entry(
            organization=self.org_a,
            entry_date=date(2026, 6, 1),
            narration="Explicit Number Entry",
            entry_number=custom_number,
            lines_data=self._sample_lines_a(),
            user=self.user,
        )
        self.assertEqual(entry.entry_number, custom_number)
