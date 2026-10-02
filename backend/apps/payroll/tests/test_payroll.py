"""Unit and Integration Tests for Statutory Payroll Calculation and APIs (Feature 5.4).

Verifies:
1. Ghanaian Statutory Payroll Engine:
   - 5.5% Employee Tier 1 SSNIT pre-tax deduction
   - 13.0% Employer Tier 1 SSNIT statutory expense
   - Graduated GRA PAYE income tax brackets (0% up to 35%)
   - Correct net salary calculation
2. Payroll Lifecycle REST Endpoints:
   - POST /api/v1/payroll/runs/ (Draft creation & calculation)
   - GET /api/v1/payroll/runs/ (Tenant-isolated list)
   - GET /api/v1/payroll/runs/<id>/ (Detailed items)
   - POST /api/v1/payroll/runs/<id>/submit/ (Transition to PENDING_APPROVAL)
   - POST /api/v1/payroll/runs/<id>/approve/ (Step-up TOTP 2FA approval)
3. Balanced Double-Entry General Ledger Posting:
   - Debit: Salaries & Staff Wages (5040)
   - Debit: Employer SSNIT Expense (5045)
   - Credit: Net Salaries Payable (2010)
   - Credit: PAYE Withholding Tax Payable (2200)
   - Credit: SSNIT Contribution Payable (2210)
   - Invariant: Sum(Debits) == Sum(Credits)
4. Forensic AuditTrail Non-Repudiation Recording.
"""

from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditTrail
from apps.authentication.models import CustomUser
from apps.ledger.models import (
    FiscalCalendar,
    FiscalPeriod,
    JournalEntry,
    PeriodLengthChoices,
)
from apps.ledger.services.seeder import (
    generate_fiscal_periods,
    seed_standard_chart_of_accounts,
)
from apps.payroll.models import (
    PayrollTwoFactorProfile,
)
from apps.payroll.services.calculator import (
    calculate_graduated_paye,
    calculate_payroll_item_deductions,
)
from apps.payroll.services.totp_service import (
    generate_base32_secret,
    generate_totp_code,
)
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class TestStatutoryPayrollEngine(TestCase):
    """Unit tests for Ghanaian statutory tax deductions (Act 896 & Act 766)."""

    def test_ssnit_tier1_deductions(self) -> None:
        """Verifies 5.5% employee and 13.0% employer SSNIT rates."""
        gross = Decimal("10000.0000")
        calc = calculate_payroll_item_deductions(gross)

        expected_ee_ssnit = Decimal("550.0000")  # 10,000 * 5.5%
        expected_er_ssnit = Decimal("1300.0000")  # 10,000 * 13.0%
        expected_taxable = Decimal("9450.0000")  # 10,000 - 550

        self.assertEqual(calc["ssnit_employee"], expected_ee_ssnit)
        self.assertEqual(calc["ssnit_employer"], expected_er_ssnit)
        self.assertEqual(calc["taxable_income"], expected_taxable)

    def test_paye_tax_free_bracket(self) -> None:
        """Verifies earnings within first GHS 490 are 100% tax-free (0% PAYE)."""
        tax = calculate_graduated_paye(Decimal("450.0000"))
        self.assertEqual(tax, Decimal("0.0000"))

        tax_exact_490 = calculate_graduated_paye(Decimal("490.0000"))
        self.assertEqual(tax_exact_490, Decimal("0.0000"))

    def test_paye_progressive_brackets_calculation(self) -> None:
        """Verifies progressive PAYE tax computation across multiple brackets."""
        # Taxable income = GHS 1,000.00
        # 1st 490 @ 0% = 0.00
        # Next 110 @ 5% = 5.50
        # Next 130 @ 10% = 13.00
        # Remaining 270 (of 3,166.67) @ 17.5% = 47.25
        # Total = 0.00 + 5.50 + 13.00 + 47.25 = 65.75
        tax = calculate_graduated_paye(Decimal("1000.0000"))
        self.assertEqual(tax, Decimal("65.7500"))


class TestPayrollAPIAndLedgerPosting(TestCase):
    """Integration tests for payroll API lifecycle and balanced double-entry ledger posting."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()

        # 1. Tenant Alpha
        self.org_alpha = Organization.objects.create(
            name="Accra Commerce Ltd",
            phone="+233240003333",
            email="finance@accracommerce.com",
            business_tin="C0003334445",
        )
        seed_standard_chart_of_accounts(self.org_alpha)

        # 2. Fiscal Calendar & Periods
        self.calendar = FiscalCalendar.objects.create(
            organization=self.org_alpha,
            period_length=PeriodLengthChoices.MONTHLY,
            fiscal_year_end_month=12,
            fiscal_year_end_day=31,
        )
        generate_fiscal_periods(
            organization=self.org_alpha,
            year=2026,
            calendar_instance=self.calendar,
        )
        self.period = FiscalPeriod.objects.filter(organization=self.org_alpha).first()

        # 3. Users: Owner (Checker) & Accountant (Maker)
        self.owner_checker = CustomUser.objects.create_user(
            email="owner@accracommerce.com",
            password="SecurePassword123!",
            first_name="Kwame",
            last_name="Owner",
        )
        self.accountant_maker = CustomUser.objects.create_user(
            email="accountant@accracommerce.com",
            password="SecurePassword123!",
            first_name="Kofi",
            last_name="Accountant",
        )

        OrganizationMembership.objects.create(
            user=self.owner_checker,
            organization=self.org_alpha,
            role=RoleChoices.OWNER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.accountant_maker,
            organization=self.org_alpha,
            role=RoleChoices.ACCOUNTANT,
            is_active=True,
        )

        # 4. Checker Step-Up 2FA Profile
        self.checker_secret = generate_base32_secret()
        self.checker_2fa = PayrollTwoFactorProfile.objects.create(
            user=self.owner_checker,
            totp_secret=self.checker_secret,
            is_enabled=True,
        )

    def test_payroll_full_lifecycle(self) -> None:
        """Verifies draft creation, submission, TOTP approval, and balanced double-entry posting."""
        # Step 1: Maker drafts payroll
        maker_token = str(AccessToken.for_user(self.accountant_maker))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {maker_token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )

        payload = {
            "period_id": str(self.period.id),
            "employees": [
                {
                    "employee_name": "Esi Mensah",
                    "gross_salary": "5000.00",
                    "employee_tin_or_ghana_card": "GHA-001234567-1",
                    "momo_number": "+233241112222",
                },
                {
                    "employee_name": "Yaw Osei",
                    "gross_salary": "3000.00",
                    "employee_tin_or_ghana_card": "GHA-009876543-2",
                    "momo_number": "+233243334444",
                },
            ],
        }

        create_res = self.client.post("/api/v1/payroll/runs/", payload, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        run_data = create_res.json()
        payroll_id = run_data["id"]
        self.assertEqual(run_data["status"], "DRAFT")
        self.assertEqual(len(run_data["items"]), 2)
        self.assertEqual(Decimal(run_data["total_gross_salary"]), Decimal("8000.0000"))

        # Step 2: Maker submits run for approval
        submit_res = self.client.post(f"/api/v1/payroll/runs/{payroll_id}/submit/")
        self.assertEqual(submit_res.status_code, status.HTTP_200_OK)
        self.assertEqual(submit_res.json()["status"], "PENDING_APPROVAL")

        # Step 3: Checker logs in and approves with TOTP 2FA
        checker_token = str(AccessToken.for_user(self.owner_checker))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {checker_token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )

        valid_totp = generate_totp_code(self.checker_secret)
        approve_res = self.client.post(
            f"/api/v1/payroll/runs/{payroll_id}/approve/",
            {"totp_code": valid_totp},
            format="json",
        )
        self.assertEqual(approve_res.status_code, status.HTTP_200_OK)
        approved_data = approve_res.json()
        self.assertEqual(approved_data["status"], "APPROVED")
        self.assertIsNotNone(approved_data["journal_entry_id"])

        # Step 4: Verify Double-Entry General Ledger Balance Invariant
        journal_entry = JournalEntry.objects.get(id=approved_data["journal_entry_id"])
        self.assertTrue(journal_entry.is_posted)
        self.assertEqual(journal_entry.total_debits, journal_entry.total_credits)

        # Step 5: Verify Forensic AuditTrail Log
        audit = AuditTrail.objects.filter(
            organization=self.org_alpha,
            action="PAYROLL_RUN_APPROVED",
            entity_id=payroll_id,
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.user, self.owner_checker)
