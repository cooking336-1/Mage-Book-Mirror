"""Unit and Integration Tests for Celery Bulk MoMo Payroll Disbursement (Task C.1 / Feature G1).

Verifies:
1. Automated B2C Mobile Money payout execution with idempotency key (PAY-{item.id}).
2. Secondary balancing double-entry General Ledger settlement:
   - Debit: Net Salaries Payable (2010)
   - Credit: Mobile Money Clearing Account (1015)
   - Invariant: Sum(Debits) == Sum(Credits) == total_net_payout
3. Lifecycle state transition to DISBURSED and timestamp recording.
4. Idempotent re-execution defense (no double payouts).
5. State validation: DRAFT and PENDING_APPROVAL runs cannot be disbursed.
6. RBAC / SoD: Only OWNER and ADMIN can authorize disbursements.
7. Background Celery task execution (disburse_payroll_run_task & execute_bulk_momo_payroll).
8. Failure rollback: If gateway transfer fails, database transaction rolls back.
"""

from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
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
    PayrollRun,
    PayrollStatusChoices,
    PayrollTwoFactorProfile,
)
from apps.payroll.services.disbursement import (
    MockPaystackTransferGateway,
    PayrollDisbursementService,
)
from apps.payroll.services.totp_service import (
    generate_base32_secret,
    generate_totp_code,
)
from apps.payroll.tasks import disburse_payroll_run_task, execute_bulk_momo_payroll
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class TestPayrollDisbursement(TestCase):
    """Test suite for bulk Mobile Money payroll disbursement service, tasks, and REST APIs."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()

        # 1. Tenant Setup
        self.org = Organization.objects.create(
            name="Kumasi Logistics Ltd",
            phone="+233240008888",
            email="finance@kumasilogistics.com",
            business_tin="C0008889991",
        )
        seed_standard_chart_of_accounts(self.org)

        # 2. Fiscal Period Setup
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

        # 3. Users: Owner (Checker/Disburser) & Accountant (Maker)
        self.owner = CustomUser.objects.create_user(
            email="owner@kumasilogistics.com",
            password="SecurePassword123!",
            first_name="Kwesi",
            last_name="Owner",
        )
        self.accountant = CustomUser.objects.create_user(
            email="accountant@kumasilogistics.com",
            password="SecurePassword123!",
            first_name="Ama",
            last_name="Accountant",
        )

        OrganizationMembership.objects.create(
            user=self.owner,
            organization=self.org,
            role=RoleChoices.OWNER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.accountant,
            organization=self.org,
            role=RoleChoices.ACCOUNTANT,
            is_active=True,
        )

        # 4. Checker Step-Up 2FA Profile
        self.checker_secret = generate_base32_secret()
        PayrollTwoFactorProfile.objects.create(
            user=self.owner,
            totp_secret=self.checker_secret,
            is_enabled=True,
        )

    def _create_and_approve_payroll_run(self) -> str:
        """Helper creating, submitting, and approving a valid statutory payroll run."""
        maker_token = str(AccessToken.for_user(self.accountant))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {maker_token}",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

        payload = {
            "period_id": str(self.period.id),
            "employees": [
                {
                    "employee_name": "Kojo Antwi",
                    "gross_salary": "6000.00",
                    "employee_tin_or_ghana_card": "GHA-001122334-1",
                    "momo_number": "+233245556666",
                },
                {
                    "employee_name": "Akua Donkor",
                    "gross_salary": "4000.00",
                    "employee_tin_or_ghana_card": "GHA-009988776-2",
                    "momo_number": "+233247778888",
                },
            ],
        }

        create_res = self.client.post("/api/v1/payroll/runs/", payload, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        payroll_id = create_res.json()["id"]

        # Submit
        submit_res = self.client.post(f"/api/v1/payroll/runs/{payroll_id}/submit/")
        self.assertEqual(submit_res.status_code, status.HTTP_200_OK)

        # Approve
        checker_token = str(AccessToken.for_user(self.owner))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {checker_token}",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

        valid_totp = generate_totp_code(self.checker_secret)
        approve_res = self.client.post(
            f"/api/v1/payroll/runs/{payroll_id}/approve/",
            {"totp_code": valid_totp},
            format="json",
        )
        self.assertEqual(approve_res.status_code, status.HTTP_200_OK)
        return payroll_id

    def test_full_disbursement_lifecycle(self) -> None:
        """Verifies end-to-end B2C disbursement, GL secondary entry, and audit trail."""
        payroll_id = self._create_and_approve_payroll_run()
        payroll_run = PayrollRun.objects.get(id=payroll_id)
        self.assertEqual(payroll_run.status, PayrollStatusChoices.APPROVED)
        initial_net = payroll_run.total_net_payout
        self.assertGreater(initial_net, Decimal("0.0000"))

        # Disburse via REST API
        owner_token = str(AccessToken.for_user(self.owner))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {owner_token}",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

        mock_gateway = MockPaystackTransferGateway()
        with patch(
            "apps.payroll.services.disbursement.MockPaystackTransferGateway",
            return_value=mock_gateway,
        ):
            response = self.client.post(f"/api/v1/payroll/runs/{payroll_id}/disburse/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "DISBURSED")
        self.assertIsNotNone(data["disbursed_at"])

        # Verify DB state
        payroll_run.refresh_from_db()
        self.assertEqual(payroll_run.status, PayrollStatusChoices.DISBURSED)
        self.assertIsNotNone(payroll_run.disbursed_at)

        # Verify gateway calls: 2 transfers with PAY-{item.id} idempotency refs
        self.assertEqual(len(mock_gateway.transfers), 2)
        for transfer in mock_gateway.transfers:
            self.assertEqual(transfer["status"], "SUCCESS")
            self.assertTrue(transfer["reference"].startswith("PAY-"))

        # Verify Secondary General Ledger Posting
        secondary_jes = JournalEntry.objects.filter(
            organization=self.org,
            source_id=payroll_run.id,
        ).exclude(id=payroll_run.journal_entry_id)

        self.assertEqual(secondary_jes.count(), 1)
        secondary_je = secondary_jes.first()
        self.assertIsNotNone(secondary_je)
        self.assertTrue(secondary_je.is_posted)
        self.assertEqual(secondary_je.total_debits, secondary_je.total_credits)
        self.assertEqual(secondary_je.total_debits, initial_net)

        # Inspect lines: Debit Net Salaries Payable (2010), Credit MoMo Clearing (1015)
        lines = list(secondary_je.lines.all())
        debit_line = [line for line in lines if line.debit_amount > Decimal("0.0000")][0]
        credit_line = [line for line in lines if line.credit_amount > Decimal("0.0000")][0]

        self.assertIn(debit_line.account.account_code, ["2010", "2110"])
        self.assertEqual(debit_line.debit_amount, initial_net)
        self.assertEqual(credit_line.account.account_code, "1015")
        self.assertEqual(credit_line.credit_amount, initial_net)

        # Verify AuditTrail Non-Repudiation
        audit = AuditTrail.objects.filter(
            organization=self.org,
            action="PAYROLL_RUN_DISBURSED",
            entity_id=str(payroll_id),
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.metadata["total_disbursed"], str(initial_net))
        self.assertEqual(audit.metadata["items_count"], 2)

    def test_disbursement_idempotency(self) -> None:
        """Verifies re-invoking disbursement on already disbursed run is safe
        and does not double-post.
        """
        payroll_id = self._create_and_approve_payroll_run()

        # First disbursement
        PayrollDisbursementService.disburse_payroll_run(payroll_run_id=payroll_id)

        initial_je_count = JournalEntry.objects.filter(
            organization=self.org, source_id=payroll_id
        ).count()
        self.assertEqual(initial_je_count, 2)  # 1 approval JE + 1 disbursement JE

        # Re-invoke disbursement (Idempotency test)
        disbursed_again, je = PayrollDisbursementService.disburse_payroll_run(
            payroll_run_id=payroll_id
        )
        self.assertEqual(disbursed_again.status, PayrollStatusChoices.DISBURSED)

        final_je_count = JournalEntry.objects.filter(
            organization=self.org, source_id=payroll_id
        ).count()
        self.assertEqual(final_je_count, initial_je_count)  # Zero duplicate JEs created

    def test_unapproved_run_disbursement_rejection(self) -> None:
        """Verifies runs in DRAFT or PENDING_APPROVAL cannot be disbursed."""
        # Draft run
        maker_token = str(AccessToken.for_user(self.accountant))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {maker_token}",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

        create_res = self.client.post(
            "/api/v1/payroll/runs/",
            {
                "period_id": str(self.period.id),
                "employees": [
                    {
                        "employee_name": "Kwame Mensah",
                        "gross_salary": "2500.00",
                        "employee_tin_or_ghana_card": "GHA-001122334-1",
                        "momo_number": "+233245556666",
                    }
                ],
            },
            format="json",
        )
        payroll_id = create_res.json()["id"]

        # Attempt to disburse DRAFT
        owner_token = str(AccessToken.for_user(self.owner))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {owner_token}",
            HTTP_X_TENANT_ID=str(self.org.id),
        )
        draft_res = self.client.post(f"/api/v1/payroll/runs/{payroll_id}/disburse/")
        self.assertEqual(draft_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("must be APPROVED", draft_res.json()["detail"])

        # Submit to PENDING_APPROVAL
        self.client.post(f"/api/v1/payroll/runs/{payroll_id}/submit/")

        # Attempt to disburse PENDING_APPROVAL
        pending_res = self.client.post(f"/api/v1/payroll/runs/{payroll_id}/disburse/")
        self.assertEqual(pending_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("must be APPROVED", pending_res.json()["detail"])

    def test_maker_cannot_disburse_payroll_rbac(self) -> None:
        """Verifies Segregation of Duties: Accountant cannot disburse funds."""
        payroll_id = self._create_and_approve_payroll_run()

        maker_token = str(AccessToken.for_user(self.accountant))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {maker_token}",
            HTTP_X_TENANT_ID=str(self.org.id),
        )

        res = self.client.post(f"/api/v1/payroll/runs/{payroll_id}/disburse/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_celery_disbursement_worker_tasks(self) -> None:
        """Verifies disburse_payroll_run_task and execute_bulk_momo_payroll Celery tasks."""
        payroll_id = self._create_and_approve_payroll_run()

        # Run task synchronously
        result = disburse_payroll_run_task(
            payroll_run_id=payroll_id,
            organization_id=str(self.org.id),
        )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["payroll_run_id"], str(payroll_id))
        self.assertIsNotNone(result["journal_entry_id"])

        payroll_run = PayrollRun.objects.get(id=payroll_id)
        self.assertEqual(payroll_run.status, PayrollStatusChoices.DISBURSED)

        # Test alias task
        alias_result = execute_bulk_momo_payroll(
            payroll_run_id=payroll_id,
            organization_id=str(self.org.id),
        )
        self.assertEqual(alias_result["status"], "SUCCESS")

    def test_gateway_failure_rollback(self) -> None:
        """Verifies that if gateway rejects payout, transaction rolls back and run
        remains APPROVED.
        """
        payroll_id = self._create_and_approve_payroll_run()

        failing_gateway = MockPaystackTransferGateway(simulate_failure=True)

        with self.assertRaises(ValidationError):
            PayrollDisbursementService.disburse_payroll_run(
                payroll_run_id=payroll_id,
                gateway=failing_gateway,
            )

        # Assert no state change occurred
        payroll_run = PayrollRun.objects.get(id=payroll_id)
        self.assertEqual(payroll_run.status, PayrollStatusChoices.APPROVED)
        self.assertIsNone(payroll_run.disbursed_at)

        # Assert no secondary journal entry was created
        secondary_jes = JournalEntry.objects.filter(
            organization=self.org,
            source_id=payroll_run.id,
        ).exclude(id=payroll_run.journal_entry_id)
        self.assertEqual(secondary_jes.count(), 0)
