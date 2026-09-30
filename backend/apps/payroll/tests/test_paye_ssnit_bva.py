"""Ghanaian PAYE & SSNIT Statutory Bracket Boundary Value Analysis (Task C.11 / T3.3).

Verifies compliance with:
- Income Tax Act, 2015 (Act 896) as amended by Act 1094 / Act 1111 / Act 1124:
  1. GHS 0.00 to 490.00: 0% tax threshold (First 490.00 @ 0%).
  2. GHS 490.01 to 600.00: 5% tax bracket (Next 110.00 @ 5%).
  3. GHS 600.01 to 730.00: 10% tax bracket (Next 130.00 @ 10%).
  4. GHS 730.01 to 3,896.67: 17.5% bracket (Next 3,166.67 @ 17.5%).
  5. GHS 3,896.68 to 19,896.67: 25% bracket (Next 16,000.00 @ 25%).
  6. GHS 19,896.68 to 50,416.67: 30% bracket (Next 30,520.00 @ 30%).
  7. Above GHS 50,416.67: 35% top marginal rate on all excess income.

- National Pensions Act, 2008 (Act 766) Tier 1 mandatory contributions:
  1. 5.5% Employee pre-tax deduction.
  2. 13.0% Employer statutory contribution.
  3. GHS 42,000.00 statutory insurable earnings cap (maximum employee deduction of GHS 2,310.00).
"""

from decimal import Decimal

from django.test import SimpleTestCase

from apps.payroll.services.calculator import (
    SSNIT_MAX_INSURABLE_EARNINGS,
    calculate_graduated_paye,
    calculate_payroll_item_deductions,
    quantize_currency,
)


class PayeBracketBoundaryTests(SimpleTestCase):
    """BVA test cases for graduated GRA PAYE brackets."""

    def test_zero_and_negative_income_produces_zero_tax(self) -> None:
        """Verifies GHS 0.00 and negative values yield 0.0000 tax."""
        self.assertEqual(calculate_graduated_paye(Decimal("0.00")), Decimal("0.0000"))
        self.assertEqual(calculate_graduated_paye(Decimal("-500.00")), Decimal("0.0000"))

    def test_first_bracket_zero_percent_boundary_490(self) -> None:
        """First GHS 490.00 is 100% tax-free (0% statutory rate)."""
        self.assertEqual(calculate_graduated_paye(Decimal("100.00")), Decimal("0.0000"))
        self.assertEqual(calculate_graduated_paye(Decimal("490.00")), Decimal("0.0000"))

        # 1 pesewa above boundary incurs 5% on 0.01
        # 0.01 * 0.05 = 0.0005
        tax_490_01 = calculate_graduated_paye(Decimal("490.01"))
        self.assertEqual(tax_490_01, Decimal("0.0005"))

    def test_second_bracket_boundary_600(self) -> None:
        """Next GHS 110.00 (from 490.01 to 600.00) is taxed at 5%."""
        # At exactly 600.00: 490 @ 0% + 110 @ 5% = GHS 5.50
        tax_600 = calculate_graduated_paye(Decimal("600.00"))
        self.assertEqual(tax_600, Decimal("5.5000"))

        # 1 pesewa into next bracket incurs 10% on 0.01 = 0.001
        tax_600_01 = calculate_graduated_paye(Decimal("600.01"))
        self.assertEqual(tax_600_01, Decimal("5.5010"))

    def test_third_bracket_boundary_730(self) -> None:
        """Next GHS 130.00 (from 600.01 to 730.00) is taxed at 10%."""
        # At exactly 730.00: 5.50 + (130 * 0.10) = 5.50 + 13.00 = GHS 18.50
        tax_730 = calculate_graduated_paye(Decimal("730.00"))
        self.assertEqual(tax_730, Decimal("18.5000"))

    def test_mid_brackets_cumulative_tax(self) -> None:
        """Verifies 17.5% and 25% brackets."""
        # Boundary 4: 730 + 3166.67 = 3896.67
        # Tax: 18.50 + (3166.67 * 0.175) = 18.50 + 554.16725 = 572.66725 -> 572.6673
        tax_3896_67 = calculate_graduated_paye(Decimal("3896.67"))
        self.assertEqual(tax_3896_67, Decimal("572.6673"))

        # Boundary 5: 3896.67 + 16000 = 19896.67
        # Tax: 572.66725 + 4000 = 4572.66725 -> 4572.6673
        tax_19896_67 = calculate_graduated_paye(Decimal("19896.67"))
        self.assertEqual(tax_19896_67, Decimal("4572.6673"))

    def test_top_bracket_and_excess_boundary_50416_67(self) -> None:
        """Boundary at GHS 50,416.67 and 35% excess rate."""
        # 19896.67 + 30520 = 50416.67
        # Tax: 4572.66725 + (30520 * 0.30) = 4572.66725 + 9156.00 = 13728.66725 -> 13728.6673
        tax_50416_67 = calculate_graduated_paye(Decimal("50416.67"))
        self.assertEqual(tax_50416_67, Decimal("13728.6673"))

        # GHS 10,000 in excess: 60,416.67
        # Tax: 13728.66725 + (10000 * 0.35) = 17228.66725 -> 17228.6673
        tax_60416_67 = calculate_graduated_paye(Decimal("60416.67"))
        self.assertEqual(tax_60416_67, Decimal("17228.6673"))


class SsnitCapAndDeductionBoundaryTests(SimpleTestCase):
    """BVA test cases for SSNIT Tier 1 deductions and insurable earnings cap."""

    def test_ssnit_below_cap_calculates_exact_percentages(self) -> None:
        """Gross below GHS 42,000 cap incurs exact 5.5% employee and 13.0% employer deductions."""
        gross = Decimal("10000.00")
        calc = calculate_payroll_item_deductions(gross)

        # 5.5% of 10,000 = 550.00
        self.assertEqual(calc["ssnit_employee"], Decimal("550.0000"))
        # 13.0% of 10,000 = 1,300.00
        self.assertEqual(calc["ssnit_employer"], Decimal("1300.0000"))
        # Taxable income = 10,000 - 550 = 9,450.00
        self.assertEqual(calc["taxable_income"], Decimal("9450.0000"))

    def test_ssnit_exact_at_cap_boundary_42000(self) -> None:
        """At exactly GHS 42,000.00 cap: 5.5% = GHS 2,310.00, 13.0% = GHS 5,460.00."""
        calc = calculate_payroll_item_deductions(SSNIT_MAX_INSURABLE_EARNINGS)

        expected_ee = quantize_currency(Decimal("42000.00") * Decimal("0.055"))
        expected_er = quantize_currency(Decimal("42000.00") * Decimal("0.130"))

        self.assertEqual(calc["ssnit_employee"], expected_ee)
        self.assertEqual(calc["ssnit_employee"], Decimal("2310.0000"))
        self.assertEqual(calc["ssnit_employer"], expected_er)
        self.assertEqual(calc["ssnit_employer"], Decimal("5460.0000"))

    def test_ssnit_above_cap_strictly_capped_at_42000(self) -> None:
        """Earnings exceeding GHS 42,000 (e.g. 50k, 100k, 250k) cap SSNIT at GHS 2,310."""
        high_gross_salaries = [
            Decimal("50000.00"),
            Decimal("75000.00"),
            Decimal("100000.00"),
            Decimal("250000.00"),
        ]

        for gross in high_gross_salaries:
            with self.subTest(gross=str(gross)):
                calc = calculate_payroll_item_deductions(gross)

                # Employee SSNIT must never exceed GHS 2,310.00
                self.assertEqual(calc["ssnit_employee"], Decimal("2310.0000"))
                # Employer SSNIT must never exceed GHS 5,460.00
                self.assertEqual(calc["ssnit_employer"], Decimal("5460.0000"))

                # Taxable income is gross minus the CAPPED employee SSNIT (not uncapped 5.5%)
                expected_taxable = gross - Decimal("2310.0000")
                self.assertEqual(calc["taxable_income"], expected_taxable)

    def test_accounting_invariant_gross_equals_net_plus_deductions(self) -> None:
        """Verifies fundamental payroll invariant: Gross == Net + SSNIT_EE + PAYE."""
        test_salaries = [
            Decimal("350.00"),  # Below tax threshold
            Decimal("490.00"),  # Exactly tax threshold
            Decimal("550.00"),  # 5% bracket
            Decimal("700.00"),  # 10% bracket
            Decimal("2500.00"),  # 17.5% bracket
            Decimal("15000.00"),  # 25% bracket
            Decimal("42000.00"),  # At SSNIT cap
            Decimal("80000.00"),  # Above SSNIT cap & top bracket
        ]

        for gross in test_salaries:
            with self.subTest(gross=str(gross)):
                calc = calculate_payroll_item_deductions(gross)
                reconstructed_gross = calc["net_salary"] + calc["ssnit_employee"] + calc["paye_tax"]
                self.assertEqual(reconstructed_gross, calc["gross_salary"])
