"""Payroll Mobile Money & Bank B2C Disbursement Service.

Implements:
- Feature G1: Outbound Bulk Mobile Money Payout Worker
- Master Sprint Plan v3.0 Task C.1
- Master Transaction Sequence Diagrams & Lifecycle Specification Section 5 (Step 18)
- Secondary Balancing Double-Entry Ledger Posting:
    Dr Net Salaries Payable (2010)
    Cr Mobile Money Clearing Account (1015) / Bank (1020)
- Immutable Forensic Audit Trail recording
"""

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditTrail
from apps.ledger.models import (
    AccountCategory,
    CategoryCodeChoices,
    ChartOfAccounts,
    JournalEntry,
    SourceTypeChoices,
)
from apps.ledger.services.ledger import LedgerService
from apps.payroll.models import PayrollItem, PayrollRun, PayrollStatusChoices
from apps.payroll.services.totp_service import acquire_payroll_lock
from apps.tenancy.models import Organization

logger = logging.getLogger(__name__)


class BaseTransferGateway(ABC):
    """Abstract Base Class for B2C Mobile Money & Bank Transfer Gateways."""

    @abstractmethod
    def initiate_transfer(
        self,
        recipient_phone: str,
        amount: Decimal,
        reference: str,
        recipient_name: str,
        currency: str = "GHS",
    ) -> dict[str, Any]:
        """Initiates an outbound payout transfer to a mobile wallet or bank account.

        Args:
            recipient_phone: Target MSISDN / MoMo phone number.
            amount: Payout amount in GHS.
            reference: Tenant-unique transfer idempotency reference.
            recipient_name: Legal name of employee.
            currency: ISO currency code (default: GHS).

        Returns:
            dict containing status ("SUCCESS" | "FAILED"), gateway_reference, and metadata.
        """
        pass


class MockPaystackTransferGateway(BaseTransferGateway):
    """Deterministic mock gateway for Paystack/Hubtel B2C mobile money payouts.

    Simulates instant execution with deterministic gateway transfer codes.
    Allows test configuration to simulate network or account rejections.
    """

    def __init__(
        self,
        simulate_failure: bool = False,
        fail_numbers: set[str] | None = None,
    ) -> None:
        self.simulate_failure = simulate_failure
        self.fail_numbers = fail_numbers or {"0000000000"}
        self.transfers: list[dict[str, Any]] = []

    def initiate_transfer(
        self,
        recipient_phone: str,
        amount: Decimal,
        reference: str,
        recipient_name: str,
        currency: str = "GHS",
    ) -> dict[str, Any]:
        if self.simulate_failure or recipient_phone in self.fail_numbers:
            logger.warning(
                "[MockTransferGateway] Transfer REJECTED for phone=%s, amount=%s, ref=%s",
                recipient_phone,
                amount,
                reference,
            )
            return {
                "status": "FAILED",
                "reference": reference,
                "gateway_reference": "",
                "amount": float(amount),
                "recipient_phone": recipient_phone,
                "recipient_name": recipient_name,
                "error": "Simulated B2C wallet transfer failure or invalid recipient phone.",
            }

        gateway_reference = f"TRF_MOCK_{uuid4().hex[:12].upper()}"
        record = {
            "status": "SUCCESS",
            "reference": reference,
            "gateway_reference": gateway_reference,
            "amount": float(amount),
            "currency": currency,
            "recipient_phone": recipient_phone,
            "recipient_name": recipient_name,
            "transferred_at": timezone.now().isoformat(),
        }
        self.transfers.append(record)
        logger.info(
            "[MockTransferGateway] Transfer SUCCESS: GHS %s -> %s (%s) [Ref: %s, GwRef: %s]",
            amount,
            recipient_phone,
            recipient_name,
            reference,
            gateway_reference,
        )
        return record


def _get_or_create_account(
    organization: Any,
    code: str,
    name: str,
    category_code: str,
) -> ChartOfAccounts:
    """Helper ensuring mandatory standard ledger accounts exist for disbursement posting."""
    account = ChartOfAccounts.objects.filter(organization=organization, account_code=code).first()
    if account:
        return account

    category = AccountCategory.objects.filter(code=category_code).first()
    if not category:
        category = AccountCategory.objects.create(
            code=category_code,
            name="Assets" if category_code == CategoryCodeChoices.ASSETS else "Liabilities",
            normal_balance=("DEBIT" if category_code == CategoryCodeChoices.ASSETS else "CREDIT"),
        )

    return ChartOfAccounts.objects.create(
        organization=organization,
        category=category,
        account_code=code,
        account_name=name,
        is_active=True,
    )


class PayrollDisbursementService:
    """Orchestrates automated Mobile Money bulk disbursement and secondary GL settlement."""

    @classmethod
    def disburse_payroll_run(
        cls,
        payroll_run_id: str,
        organization_id: str | None = None,
        gateway: BaseTransferGateway | None = None,
        user: Any = None,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> tuple[PayrollRun, JournalEntry]:
        """Disburses net salaries for an approved payroll run via Mobile Money / Bank transfer.

        Operational Lifecycle:
        1. Validates tenant isolation and ensures payroll status is APPROVED.
        2. Acquires distributed Redis mutex to prevent double-disbursement races.
        3. Iterates PayrollItems, invoking transfer gateway with idempotency key PAY-{item.id}.
        4. In an atomic transaction:
           - Posts secondary balancing General Ledger entry:
               Debit: Net Salaries Payable (2010)
               Credit: Mobile Money Clearing Account (1015)
           - Invariant: Sum(Debits) == Sum(Credits) == payroll_run.total_net_payout.
           - Transitions status to DISBURSED, sets disbursed_at.
           - Records forensic non-repudiation AuditTrail entry with batch transfer manifest.

        Args:
            payroll_run_id: Target PayrollRun UUID string.
            organization_id: Optional tenant UUID for cross-tenant isolation enforcement.
            gateway: B2C Transfer gateway adapter (defaults to MockPaystackTransferGateway).
            user: User executing or authorizing the disbursement.
            ip_address: Client IP for audit trail.
            user_agent: Client User-Agent string.

        Returns:
            tuple[PayrollRun, JournalEntry]: The disbursed run and the secondary journal entry.

        Raises:
            ValidationError: If run is not in APPROVED state, tenant mismatches, or payouts fail.
        """

    @classmethod
    def _validate_run_for_disbursement(
        cls,
        payroll_run_id: str,
        organization_id: str | None,
    ) -> PayrollRun:
        """Validates that payroll run exists, matches tenant, and is APPROVED."""
        try:
            payroll_run = PayrollRun.objects.select_related(
                "organization", "period", "journal_entry"
            ).get(id=payroll_run_id)
        except PayrollRun.DoesNotExist as exc:
            raise ValidationError(f"PayrollRun '{payroll_run_id}' does not exist.") from exc

        if organization_id and str(payroll_run.organization_id) != str(organization_id):
            raise ValidationError(
                f"Tenant isolation violation: PayrollRun '{payroll_run_id}' does not belong "
                f"to organization '{organization_id}'."
            )

        if (
            payroll_run.status != PayrollStatusChoices.DISBURSED
            and payroll_run.status != PayrollStatusChoices.APPROVED
        ):
            raise ValidationError(
                f"Cannot disburse payroll run in '{payroll_run.status}' state. "
                "Payroll run must be APPROVED by a designated checker before disbursement."
            )
        return payroll_run

    @classmethod
    def _execute_payout_transfers(
        cls,
        items: list[PayrollItem],
        gateway: BaseTransferGateway,
    ) -> list[dict[str, Any]]:
        """Executes B2C transfer payouts sequentially through gateway adapter."""
        if not items:
            raise ValidationError("Cannot disburse payroll run with zero employee items.")

        transfer_records: list[dict[str, Any]] = []
        for item in items:
            idempotency_ref = f"PAY-{item.id}"
            recipient_number = item.momo_number or "0000000000"
            result = gateway.initiate_transfer(
                recipient_phone=recipient_number,
                amount=item.net_salary,
                reference=idempotency_ref,
                recipient_name=item.employee_name,
            )

            if result.get("status") != "SUCCESS":
                error_msg = result.get("error", "Unknown gateway failure")
                logger.error(
                    "Disbursement aborted: Transfer failed for item=%s (employee=%s): %s",
                    item.id,
                    item.employee_name,
                    error_msg,
                )
                raise ValidationError(
                    f"Disbursement failed for {item.employee_name} "
                    f"({recipient_number}): {error_msg}"
                )

            transfer_records.append(result)
        return transfer_records

    @classmethod
    def _resolve_disbursement_accounts(
        cls,
        organization: Organization,
    ) -> tuple[ChartOfAccounts, ChartOfAccounts]:
        """Resolves Net Salaries Payable and MoMo/Bank clearing accounts."""
        acc_net_payable = ChartOfAccounts.objects.filter(
            organization=organization,
            account_code__in=["2010", "2110"],
            category__code=CategoryCodeChoices.LIABILITIES,
        ).first()
        if not acc_net_payable:
            acc_net_payable = _get_or_create_account(
                organization, "2010", "Net Salaries Payable", CategoryCodeChoices.LIABILITIES
            )

        acc_payout_source = ChartOfAccounts.objects.filter(
            organization=organization, account_code="1015"
        ).first()
        if not acc_payout_source:
            acc_payout_source = ChartOfAccounts.objects.filter(
                organization=organization, account_code="1020"
            ).first()
        if not acc_payout_source:
            acc_payout_source = _get_or_create_account(
                organization,
                "1015",
                "Mobile Money Clearing Account",
                CategoryCodeChoices.ASSETS,
            )
        return acc_net_payable, acc_payout_source

    @classmethod
    def _post_disbursement_ledger_and_audit(
        cls,
        payroll_run: PayrollRun,
        items: list[PayrollItem],
        transfer_records: list[dict[str, Any]],
        acc_net_payable: ChartOfAccounts,
        acc_payout_source: ChartOfAccounts,
        user: Any,
        ip_address: str | None,
        user_agent: str | None,
    ) -> JournalEntry:
        """Atomically posts secondary GL journal entry and creates forensic audit trail."""
        org = payroll_run.organization
        lines_data: list[dict[str, Any]] = [
            {
                "account": acc_net_payable,
                "debit": payroll_run.total_net_payout,
                "credit": Decimal("0.0000"),
                "description": f"Net Salary Settlement - Payroll Run {payroll_run.id}",
            },
            {
                "account": acc_payout_source,
                "debit": Decimal("0.0000"),
                "credit": payroll_run.total_net_payout,
                "description": f"Bulk Mobile Money Wallet Payout - Payroll Run {payroll_run.id}",
            },
        ]

        entry_date = timezone.now().date()
        if payroll_run.period.end_date and payroll_run.period.end_date <= entry_date:
            entry_date = payroll_run.period.end_date

        disbursement_journal = LedgerService.post_journal_entry(
            organization=org,
            entry_date=entry_date,
            lines_data=lines_data,
            narration=f"Bulk MoMo Disbursement Settlement for Payroll Run {payroll_run.id}",
            user=user or payroll_run.checker,
            source_type=SourceTypeChoices.PAYROLL,
            source_id=payroll_run.id,
            period=payroll_run.period,
        )

        payroll_run.status = PayrollStatusChoices.DISBURSED
        payroll_run.disbursed_at = timezone.now()
        payroll_run.save(update_fields=["status", "disbursed_at", "updated_at"])

        AuditTrail.objects.create(
            organization=org,
            user=user or payroll_run.checker,
            action="PAYROLL_RUN_DISBURSED",
            entity_type="PayrollRun",
            entity_id=str(payroll_run.id),
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "total_disbursed": str(payroll_run.total_net_payout),
                "items_count": len(items),
                "disbursement_journal_entry_id": str(disbursement_journal.id),
                "transfers": transfer_records,
            },
        )
        return disbursement_journal

    @classmethod
    def execute_disbursement_batch(
        cls,
        payroll_run_id: str,
        organization_id: str | None = None,
        gateway: BaseTransferGateway | None = None,
        user: Any = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[PayrollRun, JournalEntry]:
        """Orchestrates outbound B2C Mobile Money disbursements for an approved PayrollRun."""
        payroll_run = cls._validate_run_for_disbursement(payroll_run_id, organization_id)

        # Idempotency Guard: Check if already disbursed
        if payroll_run.status == PayrollStatusChoices.DISBURSED:
            logger.info(
                "PayrollRun '%s' is already disbursed. Returning existing state.",
                payroll_run_id,
            )
            return payroll_run, payroll_run.journal_entry

        if gateway is None:
            gateway = MockPaystackTransferGateway()

        lock_key = f"disburse_payroll_{payroll_run.id}"

        with acquire_payroll_lock(lock_key):
            payroll_run.refresh_from_db()
            if payroll_run.status == PayrollStatusChoices.DISBURSED:
                return payroll_run, payroll_run.journal_entry

            items: list[PayrollItem] = list(payroll_run.items.all().order_by("created_at"))
            transfer_records = cls._execute_payout_transfers(items, gateway)

            with transaction.atomic():
                acc_net_payable, acc_payout_source = cls._resolve_disbursement_accounts(
                    payroll_run.organization
                )
                disbursement_journal = cls._post_disbursement_ledger_and_audit(
                    payroll_run=payroll_run,
                    items=items,
                    transfer_records=transfer_records,
                    acc_net_payable=acc_net_payable,
                    acc_payout_source=acc_payout_source,
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

        return payroll_run, disbursement_journal
