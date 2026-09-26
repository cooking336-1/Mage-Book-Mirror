"""Integration and Security Tests for Audit Trail Immutability and R2 Storage (Feature 5.3).

Verifies:
1. SHA-256 cryptographic digest recorded on PBC package compilation.
2. Upload of PBC package ZIP to Cloudflare R2 object storage.
3. 24-hour presigned download URL generation (expires_in=86400).
4. Immutability defenses:
   - Model-level .save() mutation raises PermissionDenied.
   - Model-level .delete() raises PermissionDenied.
   - Bulk queryset .update() raises PermissionDenied.
   - Bulk queryset .delete() raises PermissionDenied.
   - Raw SQL UPDATE/DELETE triggers database exception.
5. REST API GET /api/v1/audit/trail/ RBAC and cross-tenant isolation:
   - Allowed for OWNER, ADMIN, and external AUDITOR.
   - Forbidden for BOOKKEEPER (HTTP 403).
   - Forbidden for expired AUDITOR sessions.
   - Tenant isolation: Tenant A records never leak to Tenant B.
"""

import hashlib
from datetime import timedelta

from django.db import Error as DatabaseError
from django.db import connection
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditTrail
from apps.audit.tasks import compile_pbc_package
from apps.authentication.models import CustomUser
from apps.core.services.storage import MockR2Storage
from apps.ledger.models import FiscalCalendar, PeriodLengthChoices
from apps.ledger.services.seeder import (
    generate_fiscal_periods,
    seed_standard_chart_of_accounts,
)
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class TestAuditTrailImmutabilityAndStorage(TestCase):
    """Test suite for Feature 5.3 AuditTrail, R2 upload, and presigned links."""

    def setUp(self) -> None:
        clear_current_tenant()
        MockR2Storage.clear()
        self.client = APIClient()

        # 1. Organization Alpha (Tenant A)
        self.org_alpha = Organization.objects.create(
            name="Alpha Corp Ghana Ltd",
            phone="+233240001111",
            email="finance@alphacorp.com",
            business_tin="C0001112223",
        )

        # 2. Organization Beta (Tenant B)
        self.org_beta = Organization.objects.create(
            name="Beta Enterprise Ltd",
            phone="+233240002222",
            email="finance@betaenterprise.com",
            business_tin="C0002223334",
        )

        # 3. Fiscal Calendars
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
        seed_standard_chart_of_accounts(self.org_alpha)

        # 4. Users
        self.owner_alpha = CustomUser.objects.create_user(
            email="owner@alphacorp.com",
            password="SecurePassword123!",
            first_name="Alpha",
            last_name="Owner",
        )
        self.admin_alpha = CustomUser.objects.create_user(
            email="admin@alphacorp.com",
            password="SecurePassword123!",
            first_name="Alpha",
            last_name="Admin",
        )
        self.auditor_alpha = CustomUser.objects.create_user(
            email="auditor@pwc-ghana.com",
            password="SecurePassword123!",
            first_name="Audit",
            last_name="Partner",
        )
        self.bookkeeper_alpha = CustomUser.objects.create_user(
            email="bookkeeper@alphacorp.com",
            password="SecurePassword123!",
            first_name="Alpha",
            last_name="Bookkeeper",
        )
        self.auditor_beta = CustomUser.objects.create_user(
            email="auditor@beta-audit.com",
            password="SecurePassword123!",
            first_name="Beta",
            last_name="Auditor",
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
        self.auditor_alpha_membership = OrganizationMembership.objects.create(
            user=self.auditor_alpha,
            organization=self.org_alpha,
            role=RoleChoices.AUDITOR,
            is_active=True,
            access_expires_at=timezone.now() + timedelta(days=7),
        )
        OrganizationMembership.objects.create(
            user=self.bookkeeper_alpha,
            organization=self.org_alpha,
            role=RoleChoices.BOOKKEEPER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.auditor_beta,
            organization=self.org_beta,
            role=RoleChoices.AUDITOR,
            is_active=True,
            access_expires_at=timezone.now() + timedelta(days=7),
        )

    def tearDown(self) -> None:
        clear_current_tenant()
        MockR2Storage.clear()

    # -------------------------------------------------------------------------
    # 1. Model & QuerySet Immutability Tests
    # -------------------------------------------------------------------------

    def test_audit_trail_creation_and_attributes(self) -> None:
        """Verifies creating an AuditTrail entry succeeds and stores non-repudiation digests."""
        audit = AuditTrail.objects.create(
            organization=self.org_alpha,
            user=self.owner_alpha,
            action="TEST_ACTION",
            entity_type="TestEntity",
            entity_id="entity-123",
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            file_path="tenants/alpha/test.zip",
            metadata={"test_key": "test_val"},
        )
        self.assertIsNotNone(audit.id)
        self.assertEqual(audit.organization, self.org_alpha)
        self.assertEqual(audit.action, "TEST_ACTION")
        self.assertEqual(
            audit.sha256_hash,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_audit_trail_model_save_mutation_blocked(self) -> None:
        """Verifies modifying an existing AuditTrail record raises PermissionDenied."""
        audit = AuditTrail.objects.create(
            organization=self.org_alpha,
            user=self.owner_alpha,
            action="INITIAL_ACTION",
            entity_type="TestEntity",
            entity_id="entity-123",
        )

        audit.action = "TAMPERED_ACTION"
        with self.assertRaises(PermissionDenied) as ctx:
            audit.save()
        self.assertIn("strictly immutable", str(ctx.exception))

    def test_audit_trail_model_delete_blocked(self) -> None:
        """Verifies calling .delete() on an AuditTrail instance raises PermissionDenied."""
        audit = AuditTrail.objects.create(
            organization=self.org_alpha,
            user=self.owner_alpha,
            action="DELETE_TARGET",
            entity_type="TestEntity",
            entity_id="entity-456",
        )

        with self.assertRaises(PermissionDenied) as ctx:
            audit.delete()
        self.assertIn("strictly immutable", str(ctx.exception))
        # Ensure record remains intact
        self.assertTrue(AuditTrail.objects.filter(id=audit.id).exists())

    def test_audit_trail_queryset_update_blocked(self) -> None:
        """Verifies bulk QuerySet .update() raises PermissionDenied."""
        AuditTrail.objects.create(
            organization=self.org_alpha,
            user=self.owner_alpha,
            action="ORIGINAL",
            entity_type="TestEntity",
        )

        with self.assertRaises(PermissionDenied) as ctx:
            AuditTrail.objects.filter(organization=self.org_alpha).update(action="HACKED")
        self.assertIn("strictly immutable", str(ctx.exception))

    def test_audit_trail_queryset_delete_blocked(self) -> None:
        """Verifies bulk QuerySet .delete() raises PermissionDenied."""
        AuditTrail.objects.create(
            organization=self.org_alpha,
            user=self.owner_alpha,
            action="ORIGINAL",
            entity_type="TestEntity",
        )

        with self.assertRaises(PermissionDenied) as ctx:
            AuditTrail.objects.filter(organization=self.org_alpha).delete()
        self.assertIn("strictly immutable", str(ctx.exception))

    def test_database_trigger_blocks_raw_sql_update_and_delete(self) -> None:
        """Verifies database-level write-once triggers abort raw SQL UPDATE and DELETE."""
        audit = AuditTrail.objects.create(
            organization=self.org_alpha,
            user=self.owner_alpha,
            action="RAW_SQL_TARGET",
            entity_type="TestEntity",
            entity_id="raw-1",
        )

        # 1. Attempt raw SQL UPDATE (triggers BEFORE UPDATE)
        with self.assertRaises(DatabaseError):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE audit_logs SET action = 'MALICIOUS_UPDATE' "
                    "WHERE action = 'RAW_SQL_TARGET'"
                )

        # 2. Attempt raw SQL DELETE (triggers BEFORE DELETE)
        with self.assertRaises(DatabaseError):
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM audit_logs WHERE action = 'RAW_SQL_TARGET'")

        # Verify record was not modified or deleted
        audit.refresh_from_db()
        self.assertEqual(audit.action, "RAW_SQL_TARGET")

    # -------------------------------------------------------------------------
    # 2. Celery Worker R2 Upload & Presigned URL Integration
    # -------------------------------------------------------------------------

    def test_compile_pbc_package_uploads_to_r2_and_creates_audit_trail(self) -> None:
        """Verifies worker uploads ZIP to R2, generates presigned URL, and logs audit record."""
        result = compile_pbc_package(
            tenant_id=str(self.org_alpha.id),
            fiscal_year=2026,
            requested_by_id=str(self.auditor_alpha.id),
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertIn("download_url", result)
        self.assertIn("storage_key", result)
        self.assertIn("sha256", result)
        self.assertIn("audit_trail_id", result)
        self.assertEqual(result["expires_in"], 86400)

        storage_key = result["storage_key"]
        download_url = result["download_url"]
        sha256_hash = result["sha256"]

        # Verify storage key structure
        self.assertTrue(storage_key.startswith(f"tenants/{self.org_alpha.id}/audits/2026/"))

        # Verify object exists in MockR2Storage
        storage = MockR2Storage()
        self.assertTrue(storage.file_exists(storage_key))
        stored_bytes = storage.get_file_bytes(storage_key)
        self.assertEqual(len(stored_bytes), result["archive_size_bytes"])

        # Mathematically verify SHA-256 digest of stored bytes matches recorded hash
        computed_hash = hashlib.sha256(stored_bytes).hexdigest()
        self.assertEqual(computed_hash, sha256_hash)

        # Verify presigned URL contains 24-hour expiration (86400s)
        self.assertIn("expires=86400", download_url)

        # Verify AuditTrail record persisted in database
        audit_record = AuditTrail.objects.get(id=result["audit_trail_id"])
        self.assertEqual(audit_record.organization, self.org_alpha)
        self.assertEqual(audit_record.user, self.auditor_alpha)
        self.assertEqual(audit_record.action, "PBC_AUDIT_PACKAGE_GENERATED")
        self.assertEqual(audit_record.entity_type, "PBCPackage")
        self.assertEqual(audit_record.entity_id, storage_key)
        self.assertEqual(audit_record.sha256_hash, sha256_hash)
        self.assertEqual(audit_record.file_path, storage_key)
        self.assertEqual(audit_record.metadata["download_url"], download_url)
        self.assertEqual(audit_record.metadata["expires_in_seconds"], 86400)

    # -------------------------------------------------------------------------
    # 3. REST API GET /api/v1/audit/trail/ Security & Access Control
    # -------------------------------------------------------------------------

    def test_audit_trail_api_allowed_for_owner_admin_auditor(self) -> None:
        """Verifies OWNER, ADMIN, and AUDITOR can access GET /api/v1/audit/trail/."""
        # Create a test audit entry
        AuditTrail.objects.create(
            organization=self.org_alpha,
            user=self.owner_alpha,
            action="PBC_AUDIT_PACKAGE_GENERATED",
            entity_type="PBCPackage",
            entity_id="test-key",
            sha256_hash="abc123hash",
        )

        for user, role_name in [
            (self.owner_alpha, "OWNER"),
            (self.admin_alpha, "ADMIN"),
            (self.auditor_alpha, "AUDITOR"),
        ]:
            token = str(AccessToken.for_user(user))
            self.client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {token}",
                HTTP_X_TENANT_ID=str(self.org_alpha.id),
            )
            response = self.client.get("/api/v1/audit/trail/")
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Role {role_name} was unexpectedly denied access.",
            )
            data = response.json()
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["action"], "PBC_AUDIT_PACKAGE_GENERATED")
            self.assertEqual(data[0]["sha256_hash"], "abc123hash")

    def test_audit_trail_api_forbidden_for_bookkeeper(self) -> None:
        """Verifies Segregation of Duties: BOOKKEEPER is forbidden from viewing audit trails."""
        token = str(AccessToken.for_user(self.bookkeeper_alpha))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )
        response = self.client.get("/api/v1/audit/trail/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_audit_trail_api_cross_tenant_isolation(self) -> None:
        """Verifies Tenant B cannot view Tenant A's audit trail records."""
        # Tenant A entry
        AuditTrail.objects.create(
            organization=self.org_alpha,
            user=self.owner_alpha,
            action="ALPHA_SECRET_AUDIT",
            entity_type="FinancialStatement",
            sha256_hash="alpha_hash",
        )
        # Tenant B entry
        AuditTrail.objects.create(
            organization=self.org_beta,
            user=self.auditor_beta,
            action="BETA_AUDIT",
            entity_type="FinancialStatement",
            sha256_hash="beta_hash",
        )

        # Query as Auditor Beta (Tenant B)
        token_beta = str(AccessToken.for_user(self.auditor_beta))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_beta}",
            HTTP_X_TENANT_ID=str(self.org_beta.id),
        )
        response = self.client.get("/api/v1/audit/trail/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        records = response.json()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["action"], "BETA_AUDIT")
        self.assertEqual(records[0]["sha256_hash"], "beta_hash")

    def test_audit_trail_api_filtering(self) -> None:
        """Verifies filtering by action, entity_type, and sha256 query params."""
        AuditTrail.objects.create(
            organization=self.org_alpha,
            action="ACTION_A",
            entity_type="TypeA",
            sha256_hash="hash_a",
        )
        AuditTrail.objects.create(
            organization=self.org_alpha,
            action="ACTION_B",
            entity_type="TypeB",
            sha256_hash="hash_b",
        )

        token = str(AccessToken.for_user(self.owner_alpha))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )

        # Filter by action
        res = self.client.get("/api/v1/audit/trail/?action=ACTION_A")
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]["action"], "ACTION_A")

        # Filter by sha256
        res = self.client.get("/api/v1/audit/trail/?sha256=hash_b")
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]["sha256_hash"], "hash_b")

    def test_audit_trail_api_expired_auditor_denied(self) -> None:
        """Verifies an external auditor whose session has expired is rejected with HTTP 403."""
        self.auditor_alpha_membership.access_expires_at = timezone.now() - timedelta(minutes=5)
        self.auditor_alpha_membership.save(update_fields=["access_expires_at"])

        token = str(AccessToken.for_user(self.auditor_alpha))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.org_alpha.id),
        )
        response = self.client.get("/api/v1/audit/trail/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
