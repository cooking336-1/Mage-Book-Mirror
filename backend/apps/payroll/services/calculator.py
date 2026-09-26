"""Ghanaian Statutory Payroll Engine (PAYE & SSNIT Tier 1 Deductions).

Satisfies:
- Ghana Income Tax Act, 2015 (Act 896) as amended by Act 1094 / Act 1111 / Act 1124
- National Pensions Act, 2008 (Act 766) Tier 1 mandatory contributions:
  - 5.5% Employee pre-tax deduction
  - 13.0% Employer statutory contribution (18.5% total SSNIT)
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.payroll.models import PayrollItem, PayrollRun

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")

# Progressive Monthly PAYE Brackets under GRA statutory schedule
# Tuple of (bracket_width, tax_rate)
GRA_PAYE_MONTHLY_BRACKETS: list[tuple[Decimal, Decimal]] = [
    (Decimal("490.00"), Decimal("0.00")),  # First 490 @ 0%
    (Decimal("110.00"), Decimal("0.05")),  # Next 110 @ 5%
    (Decimal("130.00"), Decimal("0.10")),  # Next 130 @ 10%
    (Decimal("3166.67"), Decimal("0.175")),  # Next 3,166.67 @ 17.5%
    (Decimal("16000.00"), Decimal("0.25")),  # Next 16,000 @ 25%
    (Decimal("30520.00"), Decimal("0.30")),  # Next 30,520 @ 30%
]
EXCESS_PAYE_RATE = Decimal("0.35")  # Balance above 50,416.67 @ 35%


def quantize_currency(value: Decimal, places: Decimal = FOUR_PLACES) -> Decimal:
    """Helper to deterministically quantize decimals with standard financial ROUND_HALF_UP."""
    return value.quantize(places, rounding=ROUND_HALF_UP)


def calculate_graduated_paye(taxable_income: Decimal) -> Decimal:
    """Computes Ghanaian Pay-As-You-Earn (PAYE) income tax according to GRA progressive brackets.

    Args:
        taxable_income: Gross salary less employee 5.5% SSNIT contribution.

    Returns:
        Decimal: Total PAYE tax withholding quantized to 4 decimal places.
    """
    if taxable_income <= Decimal("0.00"):
        return Decimal("0.0000")

    remaining_income = taxable_income
    total_tax = Decimal("0.00")

    for bracket_limit, rate in GRA_PAYE_MONTHLY_BRACKETS:
        if remaining_income <= Decimal("0.00"):
            break
        taxable_in_bracket = min(remaining_income, bracket_limit)
        bracket_tax = taxable_in_bracket * rate
        total_tax += bracket_tax
        remaining_income -= taxable_in_bracket

    if remaining_income > Decimal("0.00"):
        total_tax += remaining_income * EXCESS_PAYE_RATE

    return quantize_currency(total_tax)


def calculate_payroll_item_deductions(gross_salary: Decimal) -> dict[str, Decimal]:
    """Computes statutory deductions and net payout for an individual employee.

    Args:
        gross_salary: Agreed employee compensation.

    Returns:
        dict: gross_salary, ssnit_employee, ssnit_employer, taxable_income, paye_tax, net_salary
    """
    gross = quantize_currency(gross_salary)

    # 1. SSNIT Tier 1 Deductions
    ssnit_employee = quantize_currency(gross * Decimal("0.055"))
    ssnit_employer = quantize_currency(gross * Decimal("0.130"))

    # 2. Taxable Income (Gross minus Employee SSNIT)
    taxable_income = max(Decimal("0.0000"), gross - ssnit_employee)

    # 3. Graduated PAYE Tax
    paye_tax = calculate_graduated_paye(taxable_income)

    # 4. Net Salary Payable
    net_salary = gross - ssnit_employee - paye_tax

    return {
        "gross_salary": gross,
        "ssnit_employee": ssnit_employee,
        "ssnit_employer": ssnit_employer,
        "taxable_income": taxable_income,
        "paye_tax": paye_tax,
        "net_salary": net_salary,
    }


class StatutoryPayrollEngine:
    """Orchestrates multi-employee payroll compilation and aggregates statutory totals."""

    @classmethod
    def compile_payroll_run(
        cls,
        payroll_run: PayrollRun,
        employees_data: list[dict[str, Any]],
    ) -> list[PayrollItem]:
        """Calculates line items for all employees and updates aggregate run totals.

        Args:
            payroll_run: Target PayrollRun instance (must be in DRAFT status).
            employees_data: List of employee records with gross salary and details.

        Returns:
            list[PayrollItem]: Instantiated and persisted payroll items.
        """
        # Delete existing draft items if re-compiling
        payroll_run.items.all().delete()

        created_items: list[PayrollItem] = []
        tot_gross = Decimal("0.0000")
        tot_ssnit_ee = Decimal("0.0000")
        tot_ssnit_er = Decimal("0.0000")
        tot_paye = Decimal("0.0000")
        tot_net = Decimal("0.0000")

        for emp in employees_data:
            gross = Decimal(str(emp["gross_salary"]))
            calc = calculate_payroll_item_deductions(gross)

            item = PayrollItem.objects.create(
                organization=payroll_run.organization,
                payroll_run=payroll_run,
                employee_name=emp["employee_name"],
                employee_tin_or_ghana_card=emp.get("employee_tin_or_ghana_card", ""),
                momo_number=emp.get("momo_number", ""),
                gross_salary=calc["gross_salary"],
                ssnit_employee=calc["ssnit_employee"],
                ssnit_employer=calc["ssnit_employer"],
                taxable_income=calc["taxable_income"],
                paye_tax=calc["paye_tax"],
                net_salary=calc["net_salary"],
            )
            created_items.append(item)

            tot_gross += calc["gross_salary"]
            tot_ssnit_ee += calc["ssnit_employee"]
            tot_ssnit_er += calc["ssnit_employer"]
            tot_paye += calc["paye_tax"]
            tot_net += calc["net_salary"]

        payroll_run.total_gross_salary = tot_gross
        payroll_run.total_ssnit_employee = tot_ssnit_ee
        payroll_run.total_ssnit_employer = tot_ssnit_er
        payroll_run.total_paye_tax = tot_paye
        payroll_run.total_net_payout = tot_net
        payroll_run.save(
            update_fields=[
                "total_gross_salary",
                "total_ssnit_employee",
                "total_ssnit_employer",
                "total_paye_tax",
                "total_net_payout",
                "updated_at",
            ]
        )

        return created_items
