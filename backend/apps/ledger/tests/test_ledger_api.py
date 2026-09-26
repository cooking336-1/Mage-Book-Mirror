"""Integration Tests for General Ledger and Financial Statements REST API.

Validates:
1. Auditor Read-Only Access: Query accounts, journal entries, and financial statements.
2. Trial Balance equilibrium (is_balanced = True).
3. Profit & Loss computation over query string date ranges.
4. Balance Sheet computation as-of query string dates.
5. Invoicing & Ledger mutation blocking: Auditor write operations receive HTTP 403.
6. Ephemeral session invalidation: Expired auditor receives HTTP 403 Forbidden.
"""

import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import CustomUser
from apps.ledger.models import (
    ChartOfAccounts,
    FiscalCalendar,
    PeriodLengthChoices,
    SourceTypeChoices,
)
from apps.ledger.services.ledger import LedgerService
from apps.ledger.services.seeder import (
    generate_fiscal_periods,
    seed_standard_chart_of_accounts,
)
from apps.tenancy.middleware import clear_current_tenant, set_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class LedgerAPITests(TestCase):
    """Verifies REST endpoints for Accounts, Journal Entries, and Financial Statements."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()

        # 1. Organization & Accounts
        self.org = Organization.objects.create(
            name="Apex Ghanaian Enterprises Ltd",
            phone="+233240001122",
            email="finance@apexghana.com",
            business_tin="C0001234567",
        )
        seed_standard_chart_of_accounts(self.org)

        # Fiscal calendar & periods
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

        # 2. Key Accounts
        self.acc_cash = ChartOfAccounts.objects.get(organization=self.org, account_code="1010")
        self.acc_revenue = ChartOfAccounts.objects.get(organization=self.org, account_code="4000")
        self.acc_vat = ChartOfAccounts.objects.get(organization=self.org, account_code="2100")

        # 3. Post a sample journal entry
        self.entry = LedgerService.post_journal_entry(
            organization=self.org,
            entry_date=datetime.date(2026, 3, 1),
            narration="Q1 Service Revenue & VAT Collection",
            source_type=SourceTypeChoices.MANUAL,
            lines_data=[
                {
                    "account": self.acc_cash,
                    "debit_amount": Decimal("1200.0000"),
                    "credit_amount": Decimal("0.0000"),
                    "description": "Cash Received",
                },
                {
                    "account": self.acc_revenue,
                    "debit_amount": Decimal("0.0000"),
                    "credit_amount": Decimal("1000.0000"),
                    "description": "Service Revenue",
                },
                {
                    "account": self.acc_vat,
                    "debit_amount": Decimal("0.0000"),
                    "credit_amount": Decimal("200.0000"),
                    "description": "Output VAT 20%",
                },
            ],
            entry_number="JRN-2026-001",
        )

        # 4. Auditor User (Active)
        self.auditor_user = CustomUser.objects.create_user(
            email="lead.auditor@kpmg.com",
            password="StrongAuditorPass2026!",
            first_name="Kofi",
            last_name="Auditor",
        )
        self.auditor_membership = OrganizationMembership.objects.create(
            organization=self.org,
            user=self.auditor_user,
            role=RoleChoices.AUDITOR,
            access_expires_at=timezone.now() + datetime.timedelta(days=30),
            is_active=True,
        )

        # Authenticate client as auditor
        self._authenticate(self.auditor_user)
        self.client.defaults["HTTP_X_TENANT_ID"] = str(self.org.id)
        set_current_tenant(self.org, RoleChoices.AUDITOR)

    def _authenticate(self, user: CustomUser) -> None:
        """Injects JWT bearer token."""
        token = AccessToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_auditor_can_list_master_accounts(self) -> None:
        """GET /api/v1/accounts/ returns 200 and lists tenant chart of accounts."""
        response = self.client.get("/api/v1/accounts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertGreaterEqual(len(response.data), 10)

        codes = [acc["account_code"] for acc in response.data]
        self.assertIn("1010", codes)
        self.assertIn("4000", codes)
        self.assertIn("2100", codes)

    def test_auditor_can_retrieve_single_account(self) -> None:
        """GET /api/v1/accounts/<uuid:pk>/ returns 200 and account detail."""
        response = self.client.get(f"/api/v1/accounts/{self.acc_cash.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["account_code"], "1010")
        self.assertEqual(response.data["normal_balance"], "DEBIT")

    def test_auditor_can_retrieve_account_journal_lines(self) -> None:
        """GET /api/v1/accounts/<uuid:id>/entries/ returns posted lines for that account."""
        response = self.client.get(f"/api/v1/accounts/{self.acc_cash.id}/entries/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["debit_amount"], "1200.0000")

    def test_auditor_can_list_journal_entries(self) -> None:
        """GET /api/v1/journal-entries/ returns 200 and list of entries with lines."""
        response = self.client.get("/api/v1/journal-entries/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["entry_number"], "JRN-2026-001")
        self.assertEqual(len(response.data[0]["lines"]), 3)

    def test_auditor_can_retrieve_single_journal_entry(self) -> None:
        """GET /api/v1/journal-entries/<uuid:pk>/ returns 200."""
        response = self.client.get(f"/api/v1/journal-entries/{self.entry.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["entry_number"], "JRN-2026-001")

    def test_auditor_can_retrieve_trial_balance(self) -> None:
        """GET /api/v1/reports/trial-balance/ computes dynamic trial balance in equilibrium."""
        response = self.client.get("/api/v1/reports/trial-balance/?as_of_date=2026-12-31")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_balanced"])
        self.assertEqual(Decimal(response.data["total_debits"]), Decimal("1200.0000"))
        self.assertEqual(Decimal(response.data["total_credits"]), Decimal("1200.0000"))

    def test_auditor_can_retrieve_profit_and_loss(self) -> None:
        """GET /api/v1/reports/profit-and-loss/ computes dynamic P&L statement."""
        response = self.client.get(
            "/api/v1/reports/profit-and-loss/?start_date=2026-01-01&end_date=2026-12-31"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["total_revenue"]), Decimal("1000.0000"))
        self.assertEqual(Decimal(response.data["net_profit"]), Decimal("1000.0000"))

    def test_auditor_can_retrieve_balance_sheet(self) -> None:
        """GET /api/v1/reports/balance-sheet/ computes dynamic balance sheet."""
        response = self.client.get("/api/v1/reports/balance-sheet/?as_of_date=2026-12-31")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_balanced"])
        self.assertEqual(Decimal(response.data["total_assets"]), Decimal("1200.0000"))
        self.assertEqual(Decimal(response.data["total_liabilities"]), Decimal("200.0000"))
        self.assertEqual(Decimal(response.data["current_period_earnings"]), Decimal("1000.0000"))

    def tearDown(self) -> None:
        clear_current_tenant()
        super().tearDown()

    def test_auditor_write_mutation_to_invoices_is_forbidden(self) -> None:
        """POST /api/v1/invoices/ by an Auditor returns HTTP 403 Forbidden."""
        response = self.client.post(
            "/api/v1/invoices/",
            data={"customer_id": "01923456-789a-7bc0-8123-456789abcdef", "lines": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        json_data = response.json() if hasattr(response, "json") else response.data
        self.assertIn("Auditor role has strictly read-only access", json_data["detail"])

    def test_expired_auditor_cannot_access_reports(self) -> None:
        """Auditor with access_expires_at in the past is locked out with HTTP 403."""
        self.auditor_membership.access_expires_at = timezone.now() - datetime.timedelta(days=1)
        self.auditor_membership.save(update_fields=["access_expires_at"])

        response = self.client.get("/api/v1/reports/trial-balance/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        json_data = response.json() if hasattr(response, "json") else response.data
        self.assertIn("Auditor access has expired for this organization", json_data["detail"])

    def test_unauthenticated_request_is_rejected(self) -> None:
        """Request without credentials returns 401."""
        self.client.credentials()  # clear credentials
        response = self.client.get("/api/v1/accounts/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
