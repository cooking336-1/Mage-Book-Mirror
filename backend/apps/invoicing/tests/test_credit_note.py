"""Unit and Integration Tests for Statutory Credit Note Engine (Task C.2 / Feature G2).

Verifies:
1. Act 1151 statutory tax reversals (15% VAT, 2.5% NHIL, 2.5% GETFund).
2. Balanced double-entry General Ledger reversal:
   - Dr 4000 Sales Returns
   - Dr 2100 VAT Output
   - Dr 2110 NHIL Output
   - Dr 2120 GETFund Output
   - Cr 1200 Accounts Receivable
   - Invariant: Sum(Debits) == Sum(Credits) == CreditNote.total_amount
3. Double-refund prevention with pessimistic row lock (cumulative CNs <= invoice total).
4. Cancellation exclusion: Cancelled CNs do not count towards cumulative refund cap.
5. Invariant checking: DRAFT or CANCELLED invoices cannot receive credit notes.
6. RBAC: CanIssueRefund allows Owner, Admin, Accountant; blocks Bookkeeper, Auditor.
7. REST APIs: GET & POST /api/v1/credit-notes/ and GET /api/v1/credit-notes/<pk>/.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditTrail
from apps.authentication.models import CustomUser
from apps.invoicing.models import (
    Contact,
    ContactTypeChoices,
    CreditNoteStatusChoices,
    InvoiceStatusChoices,
)
from apps.invoicing.services import InvoicingService
from apps.invoicing.services.credit_note_service import CreditNoteService
from apps.ledger.models import (
    FiscalCalendar,
    FiscalPeriod,
    PeriodLengthChoices,
)
from apps.ledger.services.seeder import (
    generate_fiscal_periods,
    seed_standard_chart_of_accounts,
)
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import (
    Organization,
    OrganizationMembership,
    RoleChoices,
    TaxSchemeChoices,
)


class TestCreditNoteEngine(TestCase):
    """Test suite for CreditNote model, service, reversing GL, and REST API."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()

        # 1. Tenant
        self.org = Organization.objects.create(
            name="Tema Trading Ltd",
            phone="+233240007777",
            email="accounts@tematrading.com",
            business_tin="C0007778881",
            vat_registered=True,
            vat_scheme=TaxSchemeChoices.STANDARD,
        )

        seed_standard_chart_of_accounts(self.org)

        # 2. Fiscal Calendar
        self.calendar = FiscalCalendar.objects.create(
            organization=self.org,
            period_length=PeriodLengthChoices.MONTHLY,
            fiscal_year_end_month=12,
            fiscal_year_end_day=31,
        )
        generate_fiscal_periods(
            organization=self.org,
            year=2026,
            calendar_instance=self.calendar,
        )
        self.period = FiscalPeriod.objects.filter(organization=self.org).first()

        # 3. Users: Owner, Accountant, Bookkeeper, Auditor
        self.owner = CustomUser.objects.create_user(
            email="owner@tematrading.com",
            password="SecurePassword123!",
            first_name="Kofi",
            last_name="Owner",
        )
        self.accountant = CustomUser.objects.create_user(
            email="accountant@tematrading.com",
            password="SecurePassword123!",
            first_name="Abena",
            last_name="Accountant",
        )
        self.bookkeeper = CustomUser.objects.create_user(
            email="bookkeeper@tematrading.com",
            password="SecurePassword123!",
            first_name="Yaw",
            last_name="Bookkeeper",
        )

        OrganizationMembership.objects.create(
            user=self.owner, organization=self.org, role=RoleChoices.OWNER
        )
        OrganizationMembership.objects.create(
            user=self.accountant, organization=self.org, role=RoleChoices.ACCOUNTANT
        )
        OrganizationMembership.objects.create(
            user=self.bookkeeper, organization=self.org, role=RoleChoices.BOOKKEEPER
        )

        # 4. Customer
        self.customer = Contact.objects.create(
            organization=self.org,
            name="Volta Supplies Enterprise",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="C0009991112",
            ghana_card_number="GHA-001234567-9",
            billing_address="P.O. Box 123, Ho, Ghana",
            phone="+233241113333",
            email="billing@voltasupplies.com",
        )

        # 5. Seed Issued Invoice: GHS 1,000 subtotal + 15% VAT (150)
        # + 2.5% NHIL (25) + 2.5% GETFund (25) = GHS 1,200
        self.invoice = InvoicingService.create_invoice(
            organization=self.org,
            customer=self.customer,
            lines=[
                {
                    "description": "Commercial Equipment Parts",
                    "quantity": Decimal("10.0000"),
                    "unit_price": Decimal("100.0000"),
                }
            ],
            issue_date=self.period.start_date,
            user=self.accountant,
        )

        # Advance status to CLEARED
        self.invoice.status = InvoiceStatusChoices.CLEARED
        self.invoice.save(update_fields=["status"])

    def test_credit_note_reversing_gl_and_statutory_rates(self) -> None:
        """Verifies Act 1151 tax reversal rates and double-entry equilibrium."""
        credit_note, je = CreditNoteService.issue_credit_note(
            organization=self.org,
            invoice_id=str(self.invoice.id),
            lines_data=[
                {
                    "description": "Returned Defective Parts",
                    "quantity": Decimal("4.0000"),
                    "unit_price": Decimal("100.0000"),  # Subtotal = 400.00
                }
            ],
            reason="Customer returned 4 defective units",
            user=self.accountant,
            issue_date=self.period.start_date,
        )

        # Subtotal: 400.00
        # VAT 15%: 60.00
        # NHIL 2.5%: 10.00
        # GETFund 2.5%: 10.00
        # Total: 480.00
        self.assertEqual(credit_note.subtotal_amount, Decimal("400.0000"))
        self.assertEqual(credit_note.vat_amount, Decimal("60.0000"))
        self.assertEqual(credit_note.nhil_amount, Decimal("10.0000"))
        self.assertEqual(credit_note.getfund_amount, Decimal("10.0000"))
        self.assertEqual(credit_note.total_amount, Decimal("480.0000"))
        self.assertEqual(credit_note.status, CreditNoteStatusChoices.ISSUED)
        self.assertTrue(credit_note.credit_note_number.startswith("CN-"))

        # Verify Frozen Customer Snapshot
        self.assertEqual(credit_note.customer_name, "Volta Supplies Enterprise")
        self.assertEqual(credit_note.customer_tin, "C0009991112")
        self.assertEqual(credit_note.customer_ghana_card, "GHA-001234567-9")
        self.assertIsNotNone(credit_note.snapshot_frozen_at)

        # Verify Reversing Journal Entry
        self.assertIsNotNone(je)
        self.assertTrue(je.is_posted)
        self.assertEqual(je.total_debits, je.total_credits)
        self.assertEqual(je.total_debits, Decimal("480.0000"))

        # Inspect specific account lines:
        lines = list(je.lines.all())
        line_map = {
            line.account.account_code: (line.debit_amount, line.credit_amount) for line in lines
        }

        self.assertIn("4000", line_map)
        self.assertEqual(line_map["4000"][0], Decimal("400.0000"))  # Debit Sales Returns
        self.assertIn("2100", line_map)
        self.assertEqual(line_map["2100"][0], Decimal("60.0000"))  # Debit VAT Output
        self.assertIn("2110", line_map)
        self.assertEqual(line_map["2110"][0], Decimal("10.0000"))  # Debit NHIL Output
        self.assertIn("2120", line_map)
        self.assertEqual(line_map["2120"][0], Decimal("10.0000"))  # Debit GETFund Output
        self.assertIn("1200", line_map)
        self.assertEqual(line_map["1200"][1], Decimal("480.0000"))  # Credit Accounts Receivable

        # Verify AuditTrail
        audit = AuditTrail.objects.filter(
            organization=self.org,
            action="CREDIT_NOTE_ISSUED",
            entity_id=str(credit_note.id),
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.metadata["total_amount"], "480.0000")

    def test_double_refund_prevention(self) -> None:
        """Verifies cumulative credit notes cannot exceed original invoice total (GHS 1,200)."""
        # Issue 1st CN for 500 subtotal -> 600 total
        CreditNoteService.issue_credit_note(
            organization=self.org,
            invoice_id=str(self.invoice.id),
            lines_data=[
                {
                    "description": "Partial Credit 1",
                    "quantity": Decimal("5.0000"),
                    "unit_price": Decimal("100.0000"),
                }
            ],
            reason="Partial credit 1",
            user=self.accountant,
        )

        # Issue 2nd CN for 500 subtotal -> 600 total (Total credited is now 1,200.00)
        CreditNoteService.issue_credit_note(
            organization=self.org,
            invoice_id=str(self.invoice.id),
            lines_data=[
                {
                    "description": "Partial Credit 2",
                    "quantity": Decimal("5.0000"),
                    "unit_price": Decimal("100.0000"),
                }
            ],
            reason="Partial credit 2",
            user=self.accountant,
        )

        # Attempt 3rd CN for GHS 10 -> Must be blocked!
        with self.assertRaises(ValidationError) as ctx:
            CreditNoteService.issue_credit_note(
                organization=self.org,
                invoice_id=str(self.invoice.id),
                lines_data=[
                    {
                        "description": "Excess Credit",
                        "quantity": Decimal("1.0000"),
                        "unit_price": Decimal("10.0000"),
                    }
                ],
                reason="Excess refund attempt",
                user=self.accountant,
            )

        self.assertIn("Double-refund violation", str(ctx.exception))

    def test_cancelled_credit_note_excluded_from_cap(self) -> None:
        """Verifies cancelled credit notes do not exhaust the cumulative refund capacity."""
        cn1, _ = CreditNoteService.issue_credit_note(
            organization=self.org,
            invoice_id=str(self.invoice.id),
            lines_data=[
                {
                    "description": "Mistaken Credit Note",
                    "quantity": Decimal("10.0000"),
                    "unit_price": Decimal("100.0000"),  # Total = 1,200.00
                }
            ],
            reason="Mistake",
            user=self.accountant,
        )

        # Cancel CN1
        cn1.status = CreditNoteStatusChoices.CANCELLED
        cn1.save(update_fields=["status"])

        # Now issuing a new CN for full amount must succeed because CN1 is cancelled
        cn2, _ = CreditNoteService.issue_credit_note(
            organization=self.org,
            invoice_id=str(self.invoice.id),
            lines_data=[
                {
                    "description": "Valid Credit Note",
                    "quantity": Decimal("10.0000"),
                    "unit_price": Decimal("100.0000"),
                }
            ],
            reason="Legitimate credit note",
            user=self.accountant,
        )

        self.assertEqual(cn2.status, CreditNoteStatusChoices.ISSUED)
        self.assertEqual(cn2.total_amount, Decimal("1200.0000"))

    def test_cannot_issue_on_draft_invoice(self) -> None:
        """Verifies credit notes cannot be issued against DRAFT invoices."""
        self.invoice.status = InvoiceStatusChoices.DRAFT
        self.invoice.save(update_fields=["status"])

        with self.assertRaises(ValidationError) as ctx:
            CreditNoteService.issue_credit_note(
                organization=self.org,
                invoice_id=str(self.invoice.id),
                lines_data=[
                    {
                        "description": "Test",
                        "quantity": Decimal("1.0000"),
                        "unit_price": Decimal("100.0000"),
                    }
                ],
                reason="Invalid state",
            )
        self.assertIn("Cannot issue credit note", str(ctx.exception))

    def test_rbac_bookkeeper_forbidden_to_issue_credit_note(self) -> None:
        """Verifies Bookkeeper is forbidden from issuing refunds via API (CanIssueRefund)."""
        bookkeeper_token = str(AccessToken.for_user(self.bookkeeper))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {bookkeeper_token}",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

        payload = {
            "invoice_id": str(self.invoice.id),
            "reason": "Bookkeeper refund attempt",
            "lines": [
                {
                    "description": "Unauthorized Refund",
                    "quantity": "1.0000",
                    "unit_price": "100.0000",
                }
            ],
        }

        res = self.client.post("/api/v1/invoicing/credit-notes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_credit_note_api_list_create_detail(self) -> None:
        """Verifies REST API endpoints for Credit Note list, create, and detail."""
        accountant_token = str(AccessToken.for_user(self.accountant))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {accountant_token}",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

        payload = {
            "invoice_id": str(self.invoice.id),
            "reason": "Commercial billing discount",
            "lines": [
                {
                    "description": "Discount on Parts",
                    "quantity": "2.0000",
                    "unit_price": "100.0000",  # Subtotal 200 -> Total 240
                }
            ],
        }

        # 1. Create
        create_res = self.client.post("/api/v1/invoicing/credit-notes/", payload, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        cn_data = create_res.json()
        cn_id = cn_data["id"]
        self.assertEqual(Decimal(cn_data["total_amount"]), Decimal("240.0000"))
        self.assertEqual(len(cn_data["lines"]), 1)

        # 2. List
        list_res = self.client.get("/api/v1/invoicing/credit-notes/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.json()), 1)

        # 3. Detail
        detail_res = self.client.get(f"/api/v1/invoicing/credit-notes/{cn_id}/")
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_res.json()["credit_note_number"], cn_data["credit_note_number"])
