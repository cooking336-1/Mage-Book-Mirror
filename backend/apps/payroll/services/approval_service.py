"""Payroll Approval and Double-Entry General Ledger Posting Service.

Enforces:
- Misuse Case 5.1: Maker != Checker anti-self-approval validation
- Misuse Case 5.2: Step-up TOTP 2FA Verification & Single-Use Consumption Cache
- Misuse Case 5.2: Distributed Mutex Concurrency Lock
- Double-Entry Ledger Posting:
    Dr Salaries & Staff Wages (5040)
    Dr Employer SSNIT Expense (5045)
    Cr Net Wages Payable (2010)
    Cr PAYE Tax Payable (2200)
    Cr SSNIT Contribution Payable (2210)
- Immutable Forensic Audit Trail recording
"""

import logging
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.audit.models import AuditTrail
from apps.ledger.models import (
    AccountCategory,
    CategoryCodeChoices,
    ChartOfAccounts,
    SourceTypeChoices,
)
from apps.ledger.services.ledger import LedgerService
from apps.payroll.models import (
    PayrollRun,
    PayrollStatusChoices,
    PayrollTwoFactorProfile,
)
from apps.payroll.services.totp_service import (
    acquire_payroll_lock,
    consume_totp_token,
    verify_totp_code,
)

logger = logging.getLogger(__name__)


def _get_or_create_account(
    organization: Any,
    code: str,
    name: str,
    category_code: str,
) -> ChartOfAccounts:
    """Helper ensuring mandatory standard ledger accounts exist for payroll posting."""
    account = ChartOfAccounts.objects.filter(organization=organization, account_code=code).first()
    if account:
        return account

    category = AccountCategory.objects.filter(
        code=category_code,
    ).first()
    if not category:
        category = AccountCategory.objects.create(
            code=category_code,
            name="Expenses" if category_code == CategoryCodeChoices.EXPENSES else "Liabilities",
            normal_balance=("DEBIT" if category_code == CategoryCodeChoices.EXPENSES else "CREDIT"),
        )

    return ChartOfAccounts.objects.create(
        organization=organization,
        category=category,
        account_code=code,
        account_name=name,
        is_active=True,
    )


class PayrollApprovalService:
    """Orchestrates secure authorization and general ledger posting for payroll runs."""

    @classmethod
    def approve_payroll_run(
        cls,
        payroll_run: PayrollRun,
        checker: Any,
        totp_code: str,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> PayrollRun:
        """Approves a pending payroll run, validating TOTP 2FA and Segregation of Duties.

        Args:
            payroll_run: Target PayrollRun instance.
            checker: Authenticated User acting as checker.
            totp_code: 6-digit Time-Based One-Time Password token.
            ip_address: Client IP address for audit forensics.
            user_agent: Client User-Agent string.

        Returns:
            PayrollRun: Updated run in APPROVED status with attached JournalEntry.
        """
        # 1. Enforce Misuse Case 5.1: Anti-Self-Approval Gate
        if str(checker.id) == str(payroll_run.maker_id):
            logger.warning(
                "MUC 5.1 Blocked: Maker user=%s attempted self-approval of payroll_run=%s",
                checker.id,
                payroll_run.id,
            )
            raise PermissionDenied(
                "Segregation of Duties Violation (MUC 5.1): "
                "Maker cannot authorize or approve their own payroll run."
            )

        # 2. State Validation
        if payroll_run.status != PayrollStatusChoices.PENDING_APPROVAL:
            raise ValidationError(
                f"Cannot approve payroll run in '{payroll_run.status}' state. "
                "Run must be in PENDING_APPROVAL status."
            )

        # 3. Step-Up TOTP 2FA Verification
        two_factor_profile = PayrollTwoFactorProfile.objects.filter(
            user=checker,
            is_enabled=True,
        ).first()

        if two_factor_profile:
            # Verify 6-digit code with RFC 6238 drift window
            if not verify_totp_code(two_factor_profile.totp_secret, totp_code):
                raise ValidationError("Invalid Two-Factor Authentication (TOTP) code provided.")

            # Enforce Misuse Case 5.2: Single-use consumption cache
            if not consume_totp_token(str(checker.id), totp_code):
                raise ValidationError(
                    "MUC 5.2 Violation: TOTP code has already been consumed. "
                    "Please wait for the next 30-second token."
                )

        # 4. Enforce Misuse Case 5.2: Concurrency Lock & Double-Approval Race Defense
        with acquire_payroll_lock(str(payroll_run.id)):
            payroll_run.refresh_from_db()
            if payroll_run.status == PayrollStatusChoices.APPROVED:
                raise ValidationError("Payroll run has already been approved.")

            with transaction.atomic():
                # 5. Resolve Double-Entry Ledger Accounts
                org = payroll_run.organization
                acc_wages_exp = _get_or_create_account(
                    org, "5040", "Salaries & Staff Wages", CategoryCodeChoices.EXPENSES
                )
                acc_ssnit_exp = _get_or_create_account(
                    org, "5045", "Employer SSNIT Expense", CategoryCodeChoices.EXPENSES
                )
                acc_net_payable = _get_or_create_account(
                    org, "2010", "Net Salaries Payable", CategoryCodeChoices.LIABILITIES
                )
                acc_paye_payable = _get_or_create_account(
                    org, "2200", "PAYE Withholding Tax Payable", CategoryCodeChoices.LIABILITIES
                )
                acc_ssnit_payable = _get_or_create_account(
                    org, "2210", "SSNIT Contribution Payable", CategoryCodeChoices.LIABILITIES
                )

                # Total SSNIT Remittance: Employee 5.5% + Employer 13.0% = 18.5%
                total_ssnit_liability = (
                    payroll_run.total_ssnit_employee + payroll_run.total_ssnit_employer
                )

                # Lines Construction
                lines_data: list[dict[str, Any]] = [
                    # Debits
                    {
                        "account": acc_wages_exp,
                        "debit": payroll_run.total_gross_salary,
                        "credit": Decimal("0.0000"),
                        "description": f"Gross Wages - Payroll Run {payroll_run.id}",
                    },
                    {
                        "account": acc_ssnit_exp,
                        "debit": payroll_run.total_ssnit_employer,
                        "credit": Decimal("0.0000"),
                        "description": f"Employer 13% SSNIT - Payroll Run {payroll_run.id}",
                    },
                    # Credits
                    {
                        "account": acc_net_payable,
                        "debit": Decimal("0.0000"),
                        "credit": payroll_run.total_net_payout,
                        "description": f"Net Payout - Payroll Run {payroll_run.id}",
                    },
                    {
                        "account": acc_paye_payable,
                        "debit": Decimal("0.0000"),
                        "credit": payroll_run.total_paye_tax,
                        "description": f"GRA PAYE Withholding - Payroll Run {payroll_run.id}",
                    },
                    {
                        "account": acc_ssnit_payable,
                        "debit": Decimal("0.0000"),
                        "credit": total_ssnit_liability,
                        "description": f"SSNIT Tier 1 Remittance - Payroll Run {payroll_run.id}",
                    },
                ]

                # Entry Date: End date of period or today
                entry_date = payroll_run.period.end_date or timezone.now().date()

                # Post balanced entry
                journal_entry = LedgerService.post_journal_entry(
                    organization=org,
                    entry_date=entry_date,
                    lines_data=lines_data,
                    narration=f"Statutory Payroll Run {payroll_run.id} Approved",
                    user=checker,
                    source_type=SourceTypeChoices.PAYROLL,
                    source_id=payroll_run.id,
                    period=payroll_run.period,
                )

                # Update Payroll Run
                payroll_run.status = PayrollStatusChoices.APPROVED
                payroll_run.checker = checker
                payroll_run.approved_at = timezone.now()
                payroll_run.journal_entry = journal_entry
                payroll_run.save(
                    update_fields=[
                        "status",
                        "checker",
                        "approved_at",
                        "journal_entry",
                        "updated_at",
                    ]
                )

                # Record Immutable Forensic Audit Trail Entry
                AuditTrail.objects.create(
                    organization=org,
                    user=checker,
                    action="PAYROLL_RUN_APPROVED",
                    entity_type="PayrollRun",
                    entity_id=str(payroll_run.id),
                    ip_address=ip_address,
                    user_agent=user_agent,
                    metadata={
                        "gross_salary": str(payroll_run.total_gross_salary),
                        "net_payout": str(payroll_run.total_net_payout),
                        "paye_tax": str(payroll_run.total_paye_tax),
                        "ssnit_total": str(total_ssnit_liability),
                        "journal_entry_id": str(journal_entry.id),
                        "maker_id": str(payroll_run.maker_id),
                        "checker_id": str(checker.id),
                    },
                )

                logger.info(
                    "Payroll Run %s approved by checker=%s. JournalEntry=%s posted.",
                    payroll_run.id,
                    checker.id,
                    journal_entry.id,
                )

        return payroll_run
