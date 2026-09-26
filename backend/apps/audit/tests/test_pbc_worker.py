"""Integration and Unit Tests for PBC Audit Package Compilation Worker and APIs.

Validates:
1. Celery task 'compile_pbc_package' compiles an in-memory ZIP archive with all 4 CSV workpapers.
2. Cleared invoice PDFs are stored inside the 'invoices/' directory of the archive.
3. 01_General_Ledger.csv contains accurate posted journal lines.
4. 02_Trial_Balance.csv balances debits and credits for the target fiscal year.
5. 03_Chart_of_Accounts.csv enumerates tenant master accounts.
6. 04_GRA_Act1151_VAT_Summary.csv details 15% VAT, 2.5% NHIL, 2.5% GETFund and GRA clearance codes.
7. REST endpoint POST /api/v1/audit/pbc/ enqueues task and returns HTTP 202 Accepted.
8. REST endpoint GET /api/v1/audit/pbc/<task_id>/ returns task status and manifest.
9. Segregation of Duties: Bookkeeper role is denied access (HTTP 403 Forbidden).
10. Cross-tenant isolation: Tenant A's audit package never contains Tenant B's data.
"""

import csv
import datetime
import io
import zipfile
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.services.pbc_compiler import PBCPackageCompiler
from apps.audit.tasks import compile_pbc_package
from apps.authentication.models import CustomUser
from apps.core.services.storage import MockR2Storage
from apps.invoicing.models import Contact, ContactTypeChoices, Invoice, InvoiceStatusChoices
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
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class TestPBCWorker(TestCase):
    """Test suite for Provided By Client (PBC) audit package compilation and APIs."""

    def setUp(self) -> None:
        clear_current_tenant()
        MockR2Storage.clear()
        self.client = APIClient()

        # 1. Organization Alpha & Accounts
        self.org_alpha = Organization.objects.create(
            name="Alpha Corp Ghana Ltd",
            phone="+233240001111",
            email="finance@alphacorp.com",
            business_tin="C0001112223",
        )
        seed_standard_chart_of_accounts(self.org_alpha)

        self.calendar_alpha = FiscalCalendar.objects.create(
            organization=self.org_alpha,
            period_length=PeriodLengthChoices.MONTHLY,
            fiscal_year_end_month=12,
            fiscal_year_end_day=31,
        )
        generate_fiscal_periods(
            organization=self.org_alpha,
            year=2026,
            calendar_instance=self.calendar_alpha,
        )

        # 2. Organization Beta (for multi-tenant isolation testing)
        self.org_beta = Organization.objects.create(
            name="Beta Enterprise Ghana Ltd",
            phone="+233240002222",
            email="finance@betaent.com",
            business_tin="C0009998887",
        )
        seed_standard_chart_of_accounts(self.org_beta)

        # 3. Users and Memberships
        self.auditor_user = CustomUser.objects.create_user(
            email="auditor@pwc-ghana.com",
            password="StrongPassword123!",
            first_name="Kwame",
            last_name="Auditor",
        )
        self.membership_auditor = OrganizationMembership.objects.create(
            user=self.auditor_user,
            organization=self.org_alpha,
            role=RoleChoices.AUDITOR,
            is_active=True,
            access_expires_at=timezone.now() + datetime.timedelta(days=365),
        )

        self.owner_user = CustomUser.objects.create_user(
            email="owner@alphacorp.com",
            password="StrongPassword123!",
            first_name="Kofi",
            last_name="Owner",
        )
        OrganizationMembership.objects.create(
            user=self.owner_user,
            organization=self.org_alpha,
            role=RoleChoices.OWNER,
            is_active=True,
        )

        self.bookkeeper_user = CustomUser.objects.create_user(
            email="clerk@alphacorp.com",
            password="StrongPassword123!",
            first_name="Ama",
            last_name="Clerk",
        )
        OrganizationMembership.objects.create(
            user=self.bookkeeper_user,
            organization=self.org_alpha,
            role=RoleChoices.BOOKKEEPER,
            is_active=True,
        )

        # 4. Seed Journal Entries for Org Alpha
        bank_alpha = ChartOfAccounts.objects.get(organization=self.org_alpha, account_code="1010")
        sales_alpha = ChartOfAccounts.objects.get(organization=self.org_alpha, account_code="4000")
        LedgerService.post_journal_entry(
            organization=self.org_alpha,
            entry_date=datetime.date(2026, 3, 15),
            narration="Q1 Commercial Software License Sale",
            source_type=SourceTypeChoices.INVOICE,
            lines_data=[
                {
                    "account": bank_alpha,
                    "debit_amount": Decimal("10000.00"),
                    "credit_amount": Decimal("0.00"),
                    "description": "Bank receipt from customer",
                },
                {
                    "account": sales_alpha,
                    "debit_amount": Decimal("0.00"),
                    "credit_amount": Decimal("10000.00"),
                    "description": "Software license revenue recognized",
                },
            ],
        )

        # 5. Seed Cleared Invoice for Org Alpha
        customer_alpha = Contact.objects.create(
            organization=self.org_alpha,
            name="Acme Consulting Ltd",
            contact_type=ContactTypeChoices.CUSTOMER,
            tin="C0004445556",
        )
        self.invoice_alpha = Invoice.objects.create(
            organization=self.org_alpha,
            customer=customer_alpha,
            customer_name=customer_alpha.name,
            customer_tin=customer_alpha.tin,
            invoice_number="INV-2026-001",
            payment_reference="84291-4",
            issue_date=datetime.date(2026, 3, 15),
            due_date=datetime.date(2026, 4, 15),
            subtotal_amount=Decimal("8333.3333"),
            vat_amount=Decimal("1250.0000"),
            nhil_amount=Decimal("208.3333"),
            getfund_amount=Decimal("208.3333"),
            total_amount=Decimal("10000.0000"),
            paid_amount=Decimal("10000.0000"),
            status=InvoiceStatusChoices.CLEARED,
            currency="GHS",
            gra_clearance_code="GRA-CLEAR-2026-ALPHA-01",
        )

        # 6. Seed Distinct Data for Org Beta (Isolation check)
        bank_beta = ChartOfAccounts.objects.get(organization=self.org_beta, account_code="1010")
        sales_beta = ChartOfAccounts.objects.get(organization=self.org_beta, account_code="4000")
        LedgerService.post_journal_entry(
            organization=self.org_beta,
            entry_date=datetime.date(2026, 4, 20),
            narration="Beta Secret Gold Mining Operations",
            source_type=SourceTypeChoices.MANUAL,
            lines_data=[
                {
                    "account": bank_beta,
                    "debit_amount": Decimal("500000.00"),
                    "credit_amount": Decimal("0.00"),
                    "description": "Beta confidential deposit",
                },
                {
                    "account": sales_beta,
                    "debit_amount": Decimal("0.00"),
                    "credit_amount": Decimal("500000.00"),
                    "description": "Beta confidential revenue",
                },
            ],
        )

    def tearDown(self) -> None:
        clear_current_tenant()
        MockR2Storage.clear()
        super().tearDown()

    def _authenticate(self, user: CustomUser, tenant: Organization) -> None:
        """Helper to inject Bearer JWT credentials and tenant header."""
        token = AccessToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.client.defaults["HTTP_X_TENANT_ID"] = str(tenant.id)

    def test_compile_pbc_package_creates_valid_zip_archive(self) -> None:
        """Verifies Celery worker compiles a valid in-memory ZIP archive with workpapers."""
        result = compile_pbc_package(
            tenant_id=str(self.org_alpha.id),
            fiscal_year=2026,
            requested_by_id=str(self.auditor_user.id),
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["tenant_id"], str(self.org_alpha.id))
        self.assertEqual(result["fiscal_year"], 2026)
        self.assertTrue(result["archive_size_bytes"] > 0)
        self.assertTrue(result["file_count"] >= 5)
        self.assertEqual(result["invoice_count"], 1)
        self.assertIn("01_General_Ledger.csv", result["file_manifest"])
        self.assertIn("02_Trial_Balance.csv", result["file_manifest"])
        self.assertIn("03_Chart_of_Accounts.csv", result["file_manifest"])
        self.assertIn("04_GRA_Act1151_VAT_Summary.csv", result["file_manifest"])
        self.assertIn("invoices/INV-2026-001.pdf", result["file_manifest"])

    def test_general_ledger_csv_structure_and_data(self) -> None:
        """Verifies 01_General_Ledger.csv contains headers, entries, and debit/credit lines."""
        compilation = PBCPackageCompiler.compile_package(self.org_alpha, 2026)
        zip_file = zipfile.ZipFile(io.BytesIO(compilation.archive_bytes))

        self.assertIn("01_General_Ledger.csv", zip_file.namelist())
        gl_content = zip_file.read("01_General_Ledger.csv").decode("utf-8")
        rows = list(csv.reader(io.StringIO(gl_content)))

        # Header assertion
        expected_header = [
            "Date",
            "Entry Number",
            "Source Type",
            "Narration",
            "Account Code",
            "Account Name",
            "Line Description",
            "Debit (GHS)",
            "Credit (GHS)",
        ]
        self.assertEqual(rows[0], expected_header)

        # Data rows
        self.assertTrue(len(rows) >= 3)
        found_sale = any("Q1 Commercial Software License Sale" in row[3] for row in rows[1:])
        self.assertTrue(found_sale)

    def test_trial_balance_csv_matches_ledger(self) -> None:
        """Verifies 02_Trial_Balance.csv reports balanced totals and accounts."""
        compilation = PBCPackageCompiler.compile_package(self.org_alpha, 2026)
        zip_file = zipfile.ZipFile(io.BytesIO(compilation.archive_bytes))

        self.assertIn("02_Trial_Balance.csv", zip_file.namelist())
        tb_content = zip_file.read("02_Trial_Balance.csv").decode("utf-8")
        rows = list(csv.reader(io.StringIO(tb_content)))

        self.assertEqual(rows[0][0], "Account Code")
        # Check totals row exists
        totals_row = rows[-1]
        self.assertEqual(totals_row[0], "TOTALS")
        self.assertEqual(totals_row[6], "10000.0000")
        self.assertEqual(totals_row[7], "10000.0000")

    def test_chart_of_accounts_csv_contains_all_accounts(self) -> None:
        """Verifies 03_Chart_of_Accounts.csv contains all seeded master accounts."""
        compilation = PBCPackageCompiler.compile_package(self.org_alpha, 2026)
        zip_file = zipfile.ZipFile(io.BytesIO(compilation.archive_bytes))

        self.assertIn("03_Chart_of_Accounts.csv", zip_file.namelist())
        coa_content = zip_file.read("03_Chart_of_Accounts.csv").decode("utf-8")
        rows = list(csv.reader(io.StringIO(coa_content)))

        codes = [row[0] for row in rows[1:]]
        self.assertIn("1010", codes)
        self.assertIn("1200", codes)
        self.assertIn("2010", codes)
        self.assertIn("4000", codes)

    def test_act1151_tax_summary_csv_splits_taxes(self) -> None:
        """Verifies 04_GRA_Act1151_VAT_Summary.csv details VAT, NHIL, GETFund, and clearance."""
        compilation = PBCPackageCompiler.compile_package(self.org_alpha, 2026)
        zip_file = zipfile.ZipFile(io.BytesIO(compilation.archive_bytes))

        self.assertIn("04_GRA_Act1151_VAT_Summary.csv", zip_file.namelist())
        vat_content = zip_file.read("04_GRA_Act1151_VAT_Summary.csv").decode("utf-8")
        rows = list(csv.reader(io.StringIO(vat_content)))

        self.assertEqual(rows[0][0], "Invoice Number")
        invoice_row = rows[1]
        self.assertEqual(invoice_row[0], "INV-2026-001")
        self.assertEqual(invoice_row[2], "Acme Consulting Ltd")
        self.assertEqual(invoice_row[3], "C0004445556")
        self.assertEqual(invoice_row[6], "1250.0000")  # 15% VAT
        self.assertEqual(invoice_row[7], "208.3333")  # 2.5% NHIL
        self.assertEqual(invoice_row[8], "208.3333")  # 2.5% GETFund
        self.assertEqual(invoice_row[9], "10000.0000")  # Total
        self.assertEqual(invoice_row[11], "GRA-CLEAR-2026-ALPHA-01")

    def test_cleared_invoices_included_in_zip(self) -> None:
        """Verifies cleared invoice PDF is bundled inside the invoices/ directory."""
        compilation = PBCPackageCompiler.compile_package(self.org_alpha, 2026)
        zip_file = zipfile.ZipFile(io.BytesIO(compilation.archive_bytes))

        self.assertIn("invoices/INV-2026-001.pdf", zip_file.namelist())
        pdf_bytes = zip_file.read("invoices/INV-2026-001.pdf")
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_pbc_export_api_enqueues_task_and_returns_202(self) -> None:
        """POST /api/v1/audit/pbc/ enqueues task and returns HTTP 202 Accepted with task ID."""
        self._authenticate(self.auditor_user, self.org_alpha)

        response = self.client.post(
            "/api/v1/audit/pbc/",
            data={"fiscal_year": 2026},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json() if hasattr(response, "json") else response.data
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "PROCESSING")
        self.assertEqual(data["fiscal_year"], 2026)

    def test_pbc_status_endpoint_returns_task_state(self) -> None:
        """GET /api/v1/audit/pbc/<task_id>/ returns completed state under Celery eager testing."""
        self._authenticate(self.auditor_user, self.org_alpha)

        # Trigger export
        post_res = self.client.post(
            "/api/v1/audit/pbc/",
            data={"fiscal_year": 2026},
            format="json",
        )
        task_id = post_res.data["task_id"]

        # In eager testing, the task completes synchronously
        get_res = self.client.get(f"/api/v1/audit/pbc/{task_id}/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        data = get_res.json() if hasattr(get_res, "json") else get_res.data
        self.assertEqual(data["task_id"], task_id)
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("sha256", data["result"])

    def test_sod_bookkeeper_cannot_trigger_pbc_export(self) -> None:
        """Segregation of Duties: Bookkeeper role cannot trigger PBC export (HTTP 403 Forbidden)."""
        self._authenticate(self.bookkeeper_user, self.org_alpha)

        response = self.client.post(
            "/api/v1/audit/pbc/",
            data={"fiscal_year": 2026},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_tenant_isolation_in_pbc_archive(self) -> None:
        """Ensures Tenant Alpha's PBC package contains zero entries or accounts from Tenant Beta."""
        compilation = PBCPackageCompiler.compile_package(self.org_alpha, 2026)
        zip_file = zipfile.ZipFile(io.BytesIO(compilation.archive_bytes))

        gl_content = zip_file.read("01_General_Ledger.csv").decode("utf-8")
        self.assertNotIn("Beta Secret Gold Mining", gl_content)
        self.assertNotIn("500000.00", gl_content)

    def test_non_existent_tenant_fails_gracefully(self) -> None:
        """Celery worker handles non-existent tenant gracefully without unhandled crashes."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        result = compile_pbc_package(tenant_id=fake_uuid, fiscal_year=2026)

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("not found", result["error"])
