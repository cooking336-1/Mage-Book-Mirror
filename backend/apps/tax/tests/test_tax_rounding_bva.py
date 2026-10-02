"""Statutory Tax Rounding & Multi-Line Pesewa Boundary Value Analysis (Task C.11 / T3.1).

Verifies compliance with Value Added Tax Act, 2025 (Act 1151):
1. 50 micro-lines at GHS 0.35: Linear Cumulative Method guarantees exact 0-pesewa variance.
2. Mixed schedules on single invoice (STANDARD 20%, ZERO_RATED 0%, EXEMPT 0%).
3. Sub-pesewa fractions rounding strictly using ROUND_HALF_UP.
4. Mathematical invariants: sum(line.tax) == invoice.tax and total == subtotal + total_tax.
"""

from decimal import Decimal

from django.test import TestCase

from apps.tax.services import (
    LineTaxItem,
    TaxCalculationEngine,
)
from apps.tenancy.models import Organization, TaxSchemeChoices


class StatutoryTaxRoundingBoundaryTests(TestCase):
    """BVA test suite for statutory Ghanaian tax rounding under Act 1151."""

    def setUp(self) -> None:
        self.org = Organization.objects.create(
            name="Accra Commercial Trading Ltd",
            phone="+233240001122",
            email="finance@accratrading.com",
            business_tin="C0001234567",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )

    def test_fifty_micro_lines_linear_cumulative_rounding(self) -> None:
        """50 lines at GHS 0.35: Verifies linear cumulative method eliminates pesewa drift."""
        # 50 lines of GHS 0.35 = GHS 17.50 subtotal
        # Expected VAT: 17.50 * 0.15 = 2.625 -> GHS 2.63
        # Expected NHIL: 17.50 * 0.025 = 0.4375 -> GHS 0.44
        # Expected GETFund: 17.50 * 0.025 = 0.4375 -> GHS 0.44
        # Expected Total Tax: 2.63 + 0.44 + 0.44 = GHS 3.51
        # Expected Gross: 17.50 + 3.51 = GHS 21.01
        lines = [
            LineTaxItem(
                description=f"Micro Line Item {i + 1}",
                quantity=Decimal("1.0000"),
                unit_price=Decimal("0.3500"),
                supply_type=TaxSchemeChoices.STANDARD,
                is_taxable=True,
            )
            for i in range(50)
        ]

        summary = TaxCalculationEngine.calculate_line_taxes(lines, organization=self.org)

        # Header totals must match expected values
        self.assertEqual(summary.total_subtotal, Decimal("17.50"))
        self.assertEqual(summary.total_vat, Decimal("2.63"))
        self.assertEqual(summary.total_nhil, Decimal("0.44"))
        self.assertEqual(summary.total_getfund, Decimal("0.44"))
        self.assertEqual(summary.total_tax, Decimal("3.51"))
        self.assertEqual(summary.total_gross, Decimal("21.01"))

        # Invariant 1: Sum of rounded line items must match header total EXACTLY (zero drift)
        summed_line_vat = sum(b.vat_amount for b in summary.line_breakdowns)
        summed_line_nhil = sum(b.nhil_amount for b in summary.line_breakdowns)
        summed_line_getfund = sum(b.getfund_amount for b in summary.line_breakdowns)
        summed_line_subtotal = sum(b.taxable_amount for b in summary.line_breakdowns)

        self.assertEqual(summed_line_vat, summary.total_vat)
        self.assertEqual(summed_line_nhil, summary.total_nhil)
        self.assertEqual(summed_line_getfund, summary.total_getfund)
        self.assertEqual(summed_line_subtotal, summary.total_subtotal)

    def test_mixed_tax_schedules_on_single_invoice(self) -> None:
        """Verifies mixed lines (Standard 20%, Zero-Rated 0%, Exempt 0%) on one document."""
        lines = [
            LineTaxItem(
                description="Taxable Commercial Goods",
                quantity=Decimal("1.0000"),
                unit_price=Decimal("1000.0000"),
                supply_type=TaxSchemeChoices.STANDARD,
                is_taxable=True,
            ),
            LineTaxItem(
                description="Exported Cocoa Butter (Zero-Rated)",
                quantity=Decimal("1.0000"),
                unit_price=Decimal("500.0000"),
                supply_type=TaxSchemeChoices.ZERO_RATED,
                is_taxable=True,
            ),
            LineTaxItem(
                description="Educational Course Books (Exempt)",
                quantity=Decimal("1.0000"),
                unit_price=Decimal("300.0000"),
                supply_type=TaxSchemeChoices.EXEMPT,
                is_taxable=False,
            ),
        ]

        summary = TaxCalculationEngine.calculate_line_taxes(lines, organization=self.org)

        # Subtotal: 1000 + 500 + 300 = 1800.00
        self.assertEqual(summary.total_subtotal, Decimal("1800.00"))

        # Only standard taxable line (1000.00) incurs tax:
        # VAT 15%: 150.00
        # NHIL 2.5%: 25.00
        # GETFund 2.5%: 25.00
        self.assertEqual(summary.total_vat, Decimal("150.00"))
        self.assertEqual(summary.total_nhil, Decimal("25.00"))
        self.assertEqual(summary.total_getfund, Decimal("25.00"))
        self.assertEqual(summary.total_tax, Decimal("200.00"))
        self.assertEqual(summary.total_gross, Decimal("2000.00"))

    def test_sub_pesewa_half_up_fraction_rounding(self) -> None:
        """Verifies fractional sub-pesewa amounts round strictly ROUND_HALF_UP."""
        # 1 unit @ 0.33 -> base 0.33
        # VAT 15% of 0.33 = 0.0495 -> 0.05
        # NHIL 2.5% of 0.33 = 0.00825 -> 0.01
        # GETFund 2.5% of 0.33 = 0.00825 -> 0.01
        result = TaxCalculationEngine.calculate_exclusive(
            Decimal("0.3300"),
            organization=self.org,
        ).round_to_currency()

        self.assertEqual(result.vat_amount, Decimal("0.05"))
        self.assertEqual(result.nhil_amount, Decimal("0.01"))
        self.assertEqual(result.getfund_amount, Decimal("0.01"))
        self.assertEqual(result.total_tax, Decimal("0.07"))
        self.assertEqual(result.gross_amount, Decimal("0.40"))

    def test_covid_levy_is_permanently_zero(self) -> None:
        """Act 1151 repealed the 1.0% COVID-19 Health Recovery Levy (must strictly remain 0.00)."""
        result = TaxCalculationEngine.calculate_exclusive(
            Decimal("10000.0000"),
            organization=self.org,
        )
        self.assertEqual(result.covid_amount, Decimal("0.0000"))
        self.assertEqual(result.round_to_currency().covid_amount, Decimal("0.0000"))
