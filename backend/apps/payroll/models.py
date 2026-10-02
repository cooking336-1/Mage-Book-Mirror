"""Payroll Domain Models for Ghanaian Statutory Remittances and Maker-Checker Lifecycle.

Satisfies:
- Master 5-Sprint Implementation Plan Sprint 5 (Feature 5.4)
- Architecture Manual Section 4.6 (SoD Policies & Anti-Self-Approval)
- Misuse Case 5.1: Maker != Checker enforcement
- Misuse Case 5.2: Step-up TOTP 2FA Verification & Replay Protection
- Statutory remittances: PAYE (Act 896), Tier 1 SSNIT 5.5% employee / 13.0% employer
"""

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import models
from rest_framework.exceptions import PermissionDenied

from apps.core.fields import EncryptedCharField
from apps.core.models import BaseTenantModel


class PayrollStatusChoices(models.TextChoices):
    """Lifecycle states of a statutory payroll disbursement run."""

    DRAFT = "DRAFT", "Draft"
    PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Approval"
    APPROVED = "APPROVED", "Approved"
    DISBURSED = "DISBURSED", "Disbursed"
    CANCELLED = "CANCELLED", "Cancelled"


class PayrollRun(BaseTenantModel):
    """Encapsulates a monthly employee payroll calculation and disbursement run."""

    period = models.ForeignKey(
        "ledger.FiscalPeriod",
        on_delete=models.PROTECT,
        related_name="payroll_runs",
        help_text="Fiscal period to which payroll expenses and statutory liabilities attach.",
    )
    maker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_runs_created",
        help_text="User (Accountant or Bookkeeper) who initiated and drafted the payroll run.",
    )
    checker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_runs_approved",
        help_text="User (Owner or Admin) who authorized the payroll disbursement with TOTP 2FA.",
    )
    status = models.CharField(
        max_length=20,
        choices=PayrollStatusChoices.choices,
        default=PayrollStatusChoices.DRAFT,
        db_index=True,
    )
    total_gross_salary = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Aggregate gross employee compensation for the run.",
    )
    total_ssnit_employee = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Aggregate 5.5% employee Tier 1 SSNIT pre-tax statutory deduction.",
    )
    total_ssnit_employer = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Aggregate 13.0% employer Tier 1 SSNIT statutory expense contribution.",
    )
    total_paye_tax = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Aggregate graduated Ghanaian Pay-As-You-Earn withholding tax.",
    )
    total_net_payout = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Aggregate net funds payable to employee Mobile Money wallets / bank accounts.",
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when run was transitioned from DRAFT to PENDING_APPROVAL.",
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when checker successfully verified TOTP 2FA and approved run.",
    )
    disbursed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when payout worker disbursed funds to employees.",
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_runs",
        help_text="Balanced double-entry journal entry recording expenses and liabilities.",
    )

    class Meta:
        db_table = "payroll_runs"
        ordering = ["-created_at"]
        verbose_name = "Payroll Run"
        verbose_name_plural = "Payroll Runs"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "id"],
                name="unique_payroll_payrollrun_tenant_id",
            )
        ]

    def clean(self) -> None:
        """Enforces Misuse Case 5.1: Maker cannot approve their own payroll run."""
        super().clean()
        if self.checker_id and self.maker_id and self.checker_id == self.maker_id:
            raise PermissionDenied(
                "Segregation of Duties Violation (MUC 5.1): "
                "Maker cannot authorize or approve their own payroll run."
            )

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"PayrollRun {self.id} ({self.get_status_display()})"


class PayrollItem(BaseTenantModel):
    """Detailed employee payroll line item detailing individual earnings and statutory
    deductions.
    """

    payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Parent payroll run.",
    )
    employee_name = models.CharField(max_length=255, help_text="Full legal name of employee.")
    employee_tin_or_ghana_card = EncryptedCharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Ghana Card PIN (GHA-...) or GRA Individual TIN.",
    )
    momo_number = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Mobile Money phone number for automatic wallet disbursement.",
    )
    gross_salary = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="Agreed gross salary / wages for the period.",
    )
    ssnit_employee = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="5.5% employee Tier 1 SSNIT pre-tax deduction.",
    )
    ssnit_employer = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="13.0% employer Tier 1 SSNIT statutory expense contribution.",
    )
    taxable_income = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="Gross salary less employee SSNIT (5.5%).",
    )
    paye_tax = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="Ghana graduated monthly PAYE tax calculation.",
    )
    net_salary = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="Net salary payable to employee (gross - ssnit_employee - paye_tax).",
    )

    class Meta:
        db_table = "payroll_items"
        ordering = ["created_at"]
        verbose_name = "Payroll Item"
        verbose_name_plural = "Payroll Items"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "id"],
                name="unique_payroll_payrollitem_tenant_id",
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee_name} - Gross GHS {self.gross_salary} -> Net GHS {self.net_salary}"


class PayrollTwoFactorProfile(models.Model):
    """Enrolled Time-Based One-Time Password (TOTP) secret profile for step-up checker
    authorization.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payroll_2fa_profile",
        help_text="Authorized user requiring step-up 2FA for payroll approvals.",
    )
    totp_secret = models.CharField(
        max_length=64,
        help_text="Base32 encoded RFC 6238 TOTP seed parameter.",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="Flag indicating whether TOTP 2FA is active.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payroll_2fa_profiles"
        verbose_name = "Payroll 2FA Profile"
        verbose_name_plural = "Payroll 2FA Profiles"

    def __str__(self) -> str:
        return f"TOTP 2FA ({self.user.email}) - {'Enabled' if self.is_enabled else 'Disabled'}"
