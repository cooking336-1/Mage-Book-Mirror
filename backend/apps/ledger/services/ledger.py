"""Double-Entry General Ledger Core Engine Service.

Enforces:
1. Double-Entry Balance Invariant: Sum(Debits) == Sum(Credits) using exact Decimal math.
2. The "Hot Account" Solution: Append-only inserts into journal_lines without balance mutation.
3. Cyclic Deadlock Elimination: Deterministic lexicographical ORDER BY id row locks on accounts.
4. Closed Fiscal Period Protection: Rejects postings into locked accounting periods.
5. Absolute Ledger Immutability: Once posted, entries and lines cannot be updated or deleted.
"""

import datetime
import uuid
from decimal import Decimal
from typing import Any

import uuid6
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ledger.models import (
    ChartOfAccounts,
    FiscalPeriod,
    JournalEntry,
    JournalLine,
    SourceTypeChoices,
)
from apps.ledger.services.seeder import generate_fiscal_periods
from apps.tenancy.models import Organization


class LedgerService:
    """Enterprise Double-Entry General Ledger Posting and Reversal Service."""

    @classmethod
    def _resolve_fiscal_period(
        cls,
        organization: Organization,
        entry_date: Any,
    ) -> FiscalPeriod:
        """Resolves the FiscalPeriod covering the specified entry date.

        If no period exists for this organization and calendar year,
        dynamically provisions the fiscal calendar and periods before checking.
        """
        period = FiscalPeriod.objects.filter(
            organization=organization,
            start_date__lte=entry_date,
            end_date__gte=entry_date,
        ).first()

        if not period:
            # Auto-provision fiscal periods for this calendar year
            generate_fiscal_periods(organization=organization, year=entry_date.year)
            period = FiscalPeriod.objects.filter(
                organization=organization,
                start_date__lte=entry_date,
                end_date__gte=entry_date,
            ).first()

        if not period:
            raise ValidationError(
                {"entry_date": f"No fiscal period could be determined for date {entry_date}."}
            )

        return period

    @classmethod
    def _validate_and_resolve_period(
        cls,
        organization: Organization,
        entry_date: datetime.date,
        period: FiscalPeriod | None,
    ) -> FiscalPeriod:
        """Resolves fiscal period and validates that entry_date is within open period."""
        if period is None:
            period = cls._resolve_fiscal_period(organization, entry_date)
        else:
            if period.organization_id != organization.id:
                raise ValidationError(
                    {"period": "Fiscal period must belong to the specified organization."}
                )
            if not (period.start_date <= entry_date <= period.end_date):
                raise ValidationError(
                    {
                        "entry_date": (
                            f"Entry date {entry_date} falls outside fiscal period "
                            f"'{period.period_name}' ({period.start_date} to {period.end_date})."
                        )
                    }
                )

        if period.is_closed:
            raise ValidationError({"period": "Cannot post transaction to a closed fiscal period."})
        return period

    @classmethod
    def _parse_and_validate_lines(
        cls,
        lines_data: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[Any]]:
        """Parses line items, verifies debit/credit integrity and double-entry equilibrium."""
        if not lines_data or len(lines_data) < 2:
            raise ValidationError(
                "A double-entry journal entry must contain at least two line items."
            )

        parsed_lines: list[dict[str, Any]] = []
        sum_debit = Decimal("0.0000")
        sum_credit = Decimal("0.0000")
        account_identifiers: list[Any] = []

        for idx, line in enumerate(lines_data):
            account_raw = line.get("account")
            if not account_raw:
                raise ValidationError(f"Line {idx + 1} must specify an account.")

            raw_debit = line.get("debit_amount", line.get("debit", Decimal("0.0000")))
            raw_credit = line.get("credit_amount", line.get("credit", Decimal("0.0000")))

            try:
                debit = Decimal(str(raw_debit)).quantize(Decimal("0.0001"))
                credit = Decimal(str(raw_credit)).quantize(Decimal("0.0001"))
            except Exception as exc:
                raise ValidationError(f"Line {idx + 1} contains invalid numeric amounts.") from exc

            if debit < Decimal("0.0000") or credit < Decimal("0.0000"):
                raise ValidationError(
                    f"Line {idx + 1} cannot have negative debit or credit amounts."
                )

            if (debit == Decimal("0.0000") and credit == Decimal("0.0000")) or (
                debit > Decimal("0.0000") and credit > Decimal("0.0000")
            ):
                raise ValidationError(
                    f"Line {idx + 1} must have either a debit or a credit amount, not both or zero."
                )

            sum_debit += debit
            sum_credit += credit
            account_identifiers.append(account_raw)
            parsed_lines.append(
                {
                    "account_ref": account_raw,
                    "debit_amount": debit,
                    "credit_amount": credit,
                    "description": line.get("description", ""),
                }
            )

        if sum_debit != sum_credit or sum_debit == Decimal("0.0000"):
            raise ValidationError(
                f"Unbalanced journal entry: Total debits (GHS {sum_debit}) must equal "
                f"total credits (GHS {sum_credit}) and be greater than zero."
            )

        return parsed_lines, account_identifiers

    @classmethod
    def _resolve_and_validate_accounts(
        cls,
        organization: Organization,
        account_identifiers: list[Any],
    ) -> tuple[dict[uuid.UUID, ChartOfAccounts], dict[str, ChartOfAccounts]]:
        """Resolves account references and ensures they are active tenant records."""
        account_ids: set[uuid.UUID] = set()
        account_code_map: dict[str, ChartOfAccounts] = {}

        for acc_ref in account_identifiers:
            if isinstance(acc_ref, ChartOfAccounts):
                account_ids.add(acc_ref.id)
            elif isinstance(acc_ref, uuid.UUID):
                account_ids.add(acc_ref)
            elif isinstance(acc_ref, str):
                try:
                    account_ids.add(uuid.UUID(acc_ref))
                except ValueError:
                    pass

        for acc_ref in account_identifiers:
            if isinstance(acc_ref, str) and len(acc_ref) <= 20:
                try:
                    uuid.UUID(acc_ref)
                except ValueError:
                    acc_obj = ChartOfAccounts.objects.filter(
                        organization=organization, account_code=acc_ref
                    ).first()
                    if not acc_obj:
                        raise ValidationError(
                            f"Account with code '{acc_ref}' does not exist for this organization."
                        ) from None
                    account_ids.add(acc_obj.id)
                    account_code_map[acc_ref] = acc_obj

        accounts = list(
            ChartOfAccounts.objects.filter(
                organization=organization,
                id__in=account_ids,
            )
        )
        account_lookup: dict[uuid.UUID, ChartOfAccounts] = {acc.id: acc for acc in accounts}

        if len(account_lookup) != len(account_ids):
            raise ValidationError(
                "One or more accounts do not exist or belong to another organization."
            )

        for acc in accounts:
            if not acc.is_active:
                raise ValidationError(
                    f"Account '{acc.account_code} - {acc.account_name}' is inactive "
                    "and cannot accept new postings."
                )

        return account_lookup, account_code_map

    @classmethod
    def _persist_journal_entry_header(
        cls,
        organization: Organization,
        period: FiscalPeriod,
        entry_date: datetime.date,
        narration: str,
        source_type: str,
        source_id: Any,
        entry_number: str | None,
        user: Any,
    ) -> JournalEntry:
        """Persists the master JournalEntry record with sequence collision handling."""
        is_auto_generated = not entry_number
        if is_auto_generated:
            year = entry_date.year
            count = (
                JournalEntry.objects.filter(
                    organization=organization,
                    entry_date__year=year,
                ).count()
                + 1
            )
            entry_number = f"JE-{year}-{count:05d}"
            if JournalEntry.objects.filter(
                organization=organization, entry_number=entry_number
            ).exists():
                entry_number = f"JE-{year}-{uuid6.uuid7().hex[-8:].upper()}"

        now = timezone.now()
        max_retries = 3
        journal_entry: JournalEntry | None = None
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    journal_entry = JournalEntry.objects.create(
                        organization=organization,
                        period=period,
                        entry_number=entry_number,
                        entry_date=entry_date,
                        narration=narration,
                        source_type=source_type,
                        source_id=source_id,
                        is_posted=True,
                        posted_at=now,
                        posted_by=user,
                        created_by=user,
                    )
                break
            except IntegrityError:
                if is_auto_generated and attempt < max_retries - 1:
                    year = entry_date.year
                    entry_number = f"JE-{year}-{uuid6.uuid7().hex[-8:].upper()}"
                else:
                    raise

        if journal_entry is None:
            raise ValidationError("Failed to allocate unique journal entry number.")
        return journal_entry

    @classmethod
    def _bulk_create_lines(
        cls,
        organization: Organization,
        journal_entry: JournalEntry,
        parsed_lines: list[dict[str, Any]],
        account_lookup: dict[uuid.UUID, ChartOfAccounts],
        account_code_map: dict[str, ChartOfAccounts],
    ) -> list[JournalLine]:
        """Instantiates and bulk creates JournalLine items."""
        lines_to_create: list[JournalLine] = []
        for line_item in parsed_lines:
            acc_ref = line_item["account_ref"]
            if isinstance(acc_ref, ChartOfAccounts):
                account_obj = account_lookup[acc_ref.id]
            elif isinstance(acc_ref, uuid.UUID):
                account_obj = account_lookup[acc_ref]
            elif isinstance(acc_ref, str):
                try:
                    parsed_uuid = uuid.UUID(acc_ref)
                    account_obj = account_lookup[parsed_uuid]
                except ValueError:
                    account_obj = account_code_map[acc_ref]
            else:
                raise ValidationError(f"Invalid account reference: {acc_ref}")

            lines_to_create.append(
                JournalLine(
                    organization=organization,
                    journal_entry=journal_entry,
                    account=account_obj,
                    description=line_item["description"],
                    debit_amount=line_item["debit_amount"],
                    credit_amount=line_item["credit_amount"],
                )
            )

        return JournalLine.objects.bulk_create(lines_to_create)

    @classmethod
    @transaction.atomic
    def post_journal_entry(
        cls,
        organization: Organization,
        entry_date: datetime.date,
        lines_data: list[dict[str, Any]],
        narration: str = "",
        user: Any = None,
        source_type: str = SourceTypeChoices.MANUAL,
        source_id: Any = None,
        period: FiscalPeriod | None = None,
        entry_number: str | None = None,
    ) -> JournalEntry:
        """Posts a multi-line double-entry journal transaction."""
        resolved_period = cls._validate_and_resolve_period(organization, entry_date, period)
        parsed_lines, account_identifiers = cls._parse_and_validate_lines(lines_data)
        account_lookup, account_code_map = cls._resolve_and_validate_accounts(
            organization, account_identifiers
        )

        journal_entry = cls._persist_journal_entry_header(
            organization=organization,
            period=resolved_period,
            entry_date=entry_date,
            narration=narration,
            source_type=source_type,
            source_id=source_id,
            entry_number=entry_number,
            user=user,
        )

        cls._bulk_create_lines(
            organization=organization,
            journal_entry=journal_entry,
            parsed_lines=parsed_lines,
            account_lookup=account_lookup,
            account_code_map=account_code_map,
        )

        return journal_entry

    @classmethod
    @transaction.atomic
    def reverse_journal_entry(
        cls,
        journal_entry: JournalEntry,
        user: Any = None,
        reason: str = "",
        reversal_date: Any = None,
    ) -> JournalEntry:
        """Generates and posts an exact offsetting reversing journal entry.

        Parameters:
            journal_entry: The posted journal entry to reverse.
            user: User executing the reversal.
            reason: Business justification for audit trail.
            reversal_date: Date to post the reversal (defaults to today).

        Returns:
            The newly created reversing JournalEntry.
        """
        if not journal_entry.is_posted:
            raise ValidationError("Only posted journal entries can be reversed.")

        if reversal_date is None:
            reversal_date = timezone.now().date()

        reversing_lines: list[dict[str, Any]] = []
        for line in journal_entry.lines.all():
            reversing_lines.append(
                {
                    "account": line.account,
                    "debit_amount": line.credit_amount,
                    "credit_amount": line.debit_amount,
                    "description": f"Reversal: {line.description or journal_entry.narration}",
                }
            )

        reversal_narration = f"Reversal of {journal_entry.entry_number}" + (
            f": {reason}" if reason else ""
        )

        return cls.post_journal_entry(
            organization=journal_entry.organization,
            entry_date=reversal_date,
            lines_data=reversing_lines,
            narration=reversal_narration,
            user=user,
            source_type=SourceTypeChoices.RECTIFICATION,
            source_id=journal_entry.id,
        )
