"""Security Penetration Tests for Payroll Maker-Checker & TOTP 2FA (Sprint 5 Feature 5.4).

Evaluates:
1. Misuse Case 5.1: Payroll Maker Self-Approval Collusion
   - Accountant drafts payroll run and attempts to approve own payment run.
   - System enforces 'maker_id != checker_id' and returns HTTP 403 Forbidden.
2. Misuse Case 5.2: Step-Up TOTP 2FA Replay Attack
   - Attacker sniffs 6-digit TOTP code and attempts to replay it within 30s window.
   - Single-use TOTP consumption cache in Redis (60s TTL) detects replay and rejects with HTTP 400.
3. Misuse Case 5.2: Concurrency Race Condition Lock
   - Concurrent approval threads blocked by distributed Redis mutex on payroll_id.
4. Segregation of Duties (SoD) Policies:
   - Bookkeeper role forbidden from approving payroll runs (HTTP 403).
   - External Auditor forbidden from drafting or approving payroll runs (HTTP 403).
   - Expired auditor sessions rejected with HTTP 403.
5. Cross-Tenant Isolation:
   - Tenant B checker cannot approve or inspect Tenant A payroll runs.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import CustomUser
from apps.ledger.models import FiscalCalendar, FiscalPeriod, PeriodLengthChoices
from apps.ledger.services.seeder import (
    generate_fiscal_periods,
    seed_standard_chart_of_accounts,
)
from apps.payments.services.idempotency import MockRedisClient
from apps.payroll.models import (
    PayrollRun,
    PayrollStatusChoices,
    PayrollTwoFactorProfile,
)
from apps.payroll.services.calculator import StatutoryPayrollEngine
from apps.payroll.services.totp_service import (
    acquire_payroll_lock,
    generate_base32_secret,
    generate_totp_code,
)
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class TestPayrollSecurity(TestCase):
    """Penetration test suite for Misuse Cases 5.1 & 5.2 and RBAC Segregation of Duties."""

    def setUp(self) -> None:
        clear_current_tenant()
        MockRedisClient().clear()
        self.client = APIClient()

        # 1. Organization Alpha (Tenant A)
        self.org_alpha = Organization.objects.create(
            name="Alpha Mining Ghana Ltd",
            phone="+233240004444",
            email="finance@alphamining.com",
            business_tin="C0004445556",
        )
        seed_standard_chart_of_accounts(self.org_alpha)

        # 2. Organization Beta (Tenant B)
        self.org_beta = Organization.objects.create(
            name="Beta Logistics Ghana Ltd",
            phone="+233240005555",
            email="finance@betalogistics.com",
            business_tin="C0005556667",
        )
        seed_standard_chart_of_accounts(self.org_beta)

        # 3. Fiscal Periods
        self.cal_alpha = FiscalCalendar.objects.create(
            organization=self.org_alpha,
            period_length=PeriodLengthChoices.MONTHLY,
            fiscal_year_end_month=12,
            fiscal_year_end_day=31,
        )
        generate_fiscal_periods(self.org_alpha, 2026, self.cal_alpha)
        self.period_alpha = FiscalPeriod.objects.filter(organization=self.org_alpha).first()

        self.cal_beta = FiscalCalendar.objects.create(
            organization=self.org_beta,
            period_length=PeriodLengthChoices.MONTHLY,
            fiscal_year_end_month=12,
            fiscal_year_end_day=31,
        )
        generate_fiscal_periods(self.org_beta, 2026, self.cal_beta)
        self.period_beta = FiscalPeriod.objects.filter(organization=self.org_beta).first()

        # 4. Users in Tenant Alpha
        self.owner_alpha = CustomUser.objects.create_user(
            email="owner@alphamining.com",
            password="SecurePassword123!",
            first_name="Kwame",
            last_name="Owner",
        )
        self.admin_alpha = CustomUser.objects.create_user(
            email="admin@alphamining.com",
            password="SecurePassword123!",
            first_name="Ama",
            last_name="Admin",
        )
        self.accountant_alpha = CustomUser.objects.create_user(
            email="accountant@alphamining.com",
            password="SecurePassword123!",
            first_name="Kofi",
            last_name="Accountant",
        )
        self.bookkeeper_alpha = CustomUser.objects.create_user(
            email="bookkeeper@alphamining.com",
            password="SecurePassword123!",
            first_name="Esi",
            last_name="Bookkeeper",
        )
        self.auditor_alpha = CustomUser.objects.create_user(
            email="auditor@pwc-ghana.com",
            password="SecurePassword123!",
            first_name="Kojo",
            last_name="Auditor",
        )

        # User in Tenant Beta
        self.owner_beta = CustomUser.objects.create_user(
            email="owner@betalogistics.com",
            password="SecurePassword123!",
            first_name="Yaw",
            last_name="BetaOwner",
        )

        # 5. Memberships
        OrganizationMembership.objects.create(
            user=self.owner_alpha,
            organization=self.org_alpha,
            role=RoleChoices.OWNER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.admin_alpha,
            organization=self.org_alpha,
            role=RoleChoices.ADMIN,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.accountant_alpha,
            organization=self.org_alpha,
            role=RoleChoices.ACCOUNTANT,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.bookkeeper_alpha,
            organization=self.org_alpha,
            role=RoleChoices.BOOKKEEPER,
            is_active=True,
        )
        self.auditor_membership = OrganizationMembership.objects.create(
            user=self.auditor_alpha,
            organization=self.org_alpha,
            role=RoleChoices.AUDITOR,
            is_active=True,
            access_expires_at=timezone.now() + timedelta(days=7),
        )
        OrganizationMembership.objects.create(
            user=self.owner_beta,
            organization=self.org_beta,
            role=RoleChoices.OWNER,
            is_active=True,
        )

        # 6. Step-Up 2FA Profiles
        self.owner_secret = generate_base32_secret()
        PayrollTwoFactorProfile.objects.create(
            user=self.owner_alpha,
            totp_secret=self.owner_secret,
            is_enabled=True,
        )

        self.accountant_secret = generate_base32_secret()
        PayrollTwoFactorProfile.objects.create(
            user=self.accountant_alpha,
            totp_secret=self.accountant_secret,
            is_enabled=True,
        )

        # 7. Helper: Create pending payroll run
        self.payroll_run = PayrollRun.objects.create(
            organization=self.org_alpha,
            period=self.period_alpha,
            maker=self.accountant_alpha,
            status=PayrollStatusChoices.PENDING_APPROVAL,
        )
        StatutoryPayrollEngine.compile_payroll_run(
            self.payroll_run,
            [
                {
                    "employee_name": "Test Employee",
                    "gross_salary": "6000.00",
                    "employee_tin_or_ghana_card": "GHA-111111111-1",
                    "momo_number": "+233241112222",
                }
            ],
        )

    def tearDown(self) -> None:
        clear_current_tenant()
        MockRedisClient().clear()

    # -------------------------------------------------------------------------
    # 1. Misuse Case 5.1: Maker Self-Approval Collusion
    # -------------------------------------------------------------------------

    def test_muc_5_1_maker_self_approval_blocked_at_api_level(self) -> None:
        """MUC 5.1: Accountant attempts to authorize own payroll run -> HTTP 403 Forbidden."""
        token = str(AccessToken.for_user(self.accountant_alpha))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )

        totp = generate_totp_code(self.accountant_secret)
        response = self.client.post(
            f"/api/v1/payroll/runs/{self.payroll_run.id}/approve/",
            {"totp_code": totp},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Verify run remains in PENDING_APPROVAL
        self.payroll_run.refresh_from_db()
        self.assertEqual(self.payroll_run.status, PayrollStatusChoices.PENDING_APPROVAL)

    def test_muc_5_1_owner_as_maker_cannot_self_approve(self) -> None:
        """MUC 5.1: Even an OWNER who drafted a run cannot approve their own run."""
        owner_run = PayrollRun.objects.create(
            organization=self.org_alpha,
            period=self.period_alpha,
            maker=self.owner_alpha,
            status=PayrollStatusChoices.PENDING_APPROVAL,
        )
        StatutoryPayrollEngine.compile_payroll_run(
            owner_run,
            [{"employee_name": "Worker", "gross_salary": "2000.00"}],
        )

        token = str(AccessToken.for_user(self.owner_alpha))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )

        totp = generate_totp_code(self.owner_secret)
        response = self.client.post(
            f"/api/v1/payroll/runs/{owner_run.id}/approve/",
            {"totp_code": totp},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Maker cannot authorize or approve", response.json()["detail"])

    def test_muc_5_1_model_level_validation_raises_permission_denied(self) -> None:
        """MUC 5.1: Defense-in-depth: ORM clean() prevents checker == maker."""
        self.payroll_run.checker = self.accountant_alpha
        with self.assertRaises(PermissionDenied):
            self.payroll_run.save()

    # -------------------------------------------------------------------------
    # 2. Misuse Case 5.2: TOTP 2FA Replay & Mutex Lock
    # -------------------------------------------------------------------------

    def test_muc_5_2_totp_replay_within_drift_window_is_rejected(self) -> None:
        """MUC 5.2: Replaying valid 6-digit TOTP is rejected by single-use cache."""
        # 1. First approval request succeeds
        valid_totp = generate_totp_code(self.owner_secret)

        token = str(AccessToken.for_user(self.owner_alpha))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )

        res1 = self.client.post(
            f"/api/v1/payroll/runs/{self.payroll_run.id}/approve/",
            {"totp_code": valid_totp},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # 2. Setup a second pending run
        second_run = PayrollRun.objects.create(
            organization=self.org_alpha,
            period=self.period_alpha,
            maker=self.accountant_alpha,
            status=PayrollStatusChoices.PENDING_APPROVAL,
        )
        StatutoryPayrollEngine.compile_payroll_run(
            second_run,
            [{"employee_name": "Worker 2", "gross_salary": "1500.00"}],
        )

        # 3. Attempt replay of same TOTP code on second run
        res2 = self.client.post(
            f"/api/v1/payroll/runs/{second_run.id}/approve/",
            {"totp_code": valid_totp},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been consumed", res2.json()["detail"])
        # Second run was protected from unauthorized approval
        second_run.refresh_from_db()
        self.assertEqual(second_run.status, PayrollStatusChoices.PENDING_APPROVAL)

    def test_muc_5_2_concurrent_race_lock_blocks_double_approval(self) -> None:
        """MUC 5.2: Distributed lock prevents concurrent approval race conditions."""
        token = str(AccessToken.for_user(self.owner_alpha))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )

        valid_totp = generate_totp_code(self.owner_secret)

        # Hold distributed lock simulating concurrent thread in execution
        with acquire_payroll_lock(str(self.payroll_run.id)):
            res = self.client.post(
                f"/api/v1/payroll/runs/{self.payroll_run.id}/approve/",
                {"totp_code": valid_totp},
                format="json",
            )
            # Must be rejected because lock is actively held
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
            self.assertIn("concurrent approval operation", res.json()["detail"])

    # -------------------------------------------------------------------------
    # 3. Segregation of Duties (SoD) & Role Boundaries
    # -------------------------------------------------------------------------

    def test_sod_bookkeeper_cannot_approve_payroll(self) -> None:
        """Bookkeeper role is forbidden from authorizing payroll disbursements."""
        token = str(AccessToken.for_user(self.bookkeeper_alpha))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )
        res = self.client.post(
            f"/api/v1/payroll/runs/{self.payroll_run.id}/approve/",
            {"totp_code": "123456"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_sod_auditor_strictly_read_only_on_payroll(self) -> None:
        """External auditor cannot draft or approve payroll runs."""
        token = str(AccessToken.for_user(self.auditor_alpha))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )

        # 1. Auditor read is permitted
        get_res = self.client.get("/api/v1/payroll/runs/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

        # 2. Auditor draft POST is blocked
        post_res = self.client.post(
            "/api/v1/payroll/runs/",
            {"period_id": str(self.period_alpha.id), "employees": []},
            format="json",
        )
        self.assertEqual(post_res.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Auditor approve POST is blocked
        appr_res = self.client.post(
            f"/api/v1/payroll/runs/{self.payroll_run.id}/approve/",
            {"totp_code": "123456"},
            format="json",
        )
        self.assertEqual(appr_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_sod_expired_auditor_membership_denied_everything(self) -> None:
        """Expired auditor membership cannot read or write payroll."""
        self.auditor_membership.access_expires_at = timezone.now() - timedelta(minutes=1)
        self.auditor_membership.save(update_fields=["access_expires_at"])

        token = str(AccessToken.for_user(self.auditor_alpha))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )

        res = self.client.get("/api/v1/payroll/runs/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 4. Cross-Tenant BOLA / IDOR Isolation
    # -------------------------------------------------------------------------

    def test_cross_tenant_isolation_tenant_b_cannot_approve_tenant_a(self) -> None:
        """Tenant B Owner cannot inspect or authorize Tenant A's payroll run."""
        token = str(AccessToken.for_user(self.owner_beta))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_beta.id),
        )

        # Attempting to access Tenant A payroll ID under Tenant B context returns 404
        res = self.client.post(
            f"/api/v1/payroll/runs/{self.payroll_run.id}/approve/",
            {"totp_code": "123456"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
