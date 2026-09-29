"""Integration test suite for Organization Registration API & COA Bootstrap (Task B.1 / B6 & T2.1).

Validates:
1. POST /api/v1/tenancy/organizations/ provisions Org, assigns OWNER role, and seeds Ghanaian COA.
2. Generates 12 monthly FiscalPeriod records for the current year.
3. Unauthenticated requests return HTTP 401 Unauthorized.
4. Invalid TIN format fails validation with HTTP 400 Bad Request.
5. GET /api/v1/tenancy/organizations/ lists user's active tenant organizations.
6. Atomic rollback: If COA or calendar seeding fails, no orphaned Organization row persists.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.ledger.models import ChartOfAccounts, FiscalCalendar, FiscalPeriod, PeriodLengthChoices
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices, TaxSchemeChoices

User = get_user_model()


class OrganizationRegistrationAPITests(TestCase):
    """APIClient integration tests for tenant registration and onboarding lifecycle."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="kwame.founder@accrabooks.gh",
            password="StrongPassword2026!",
            first_name="Kwame",
            last_name="Founder",
            phone_number="+233241112233",
        )
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def tearDown(self) -> None:
        clear_current_tenant()

    def test_post_organizations_success_provisions_tenant_owner_and_coa(self) -> None:
        """POST /api/v1/tenancy/organizations/ atomically creates org, OWNER role, and COA."""
        payload = {
            "name": "Accra Trading Enterprise Ltd",
            "tax_identification_number": "C0012345678",
            "vat_status": "STANDARD_20",
            "tax_period_length": "monthly",
            "accounting_mode": "STRICT",
            "currency": "GHS",
            "address": "14 Independence Avenue, Accra, Ghana",
            "phone": "+233240001122",
            "email": "finance@accratrading.gh",
        }

        response = self.client.post("/api/v1/tenancy/organizations/", payload, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201 Created, got {response.status_code}: {response.data}",
        )

        org_id = response.data["id"]
        org = Organization.objects.get(id=org_id)
        self.assertEqual(org.name, "Accra Trading Enterprise Ltd")
        self.assertEqual(org.business_tin, "C0012345678")
        self.assertTrue(org.vat_registered)
        self.assertEqual(org.vat_scheme, TaxSchemeChoices.STANDARD)
        self.assertEqual(org.default_experience_mode, "full")

        # 1. Verify caller has active OWNER membership
        membership = OrganizationMembership.objects.filter(
            organization=org,
            user=self.user,
            is_active=True,
        ).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, RoleChoices.OWNER)

        # 2. Verify standard Ghanaian Chart of Accounts seeded
        coa_count = ChartOfAccounts.objects.filter(organization=org).count()
        self.assertGreaterEqual(
            coa_count,
            33,
            f"Expected >= 33 standard Ghanaian COA accounts seeded, found {coa_count}",
        )

        # 3. Verify Fiscal Calendar and 12 monthly periods created
        calendar_inst = FiscalCalendar.objects.filter(organization=org).first()
        self.assertIsNotNone(calendar_inst)
        self.assertEqual(calendar_inst.period_length, PeriodLengthChoices.MONTHLY)

        periods_count = FiscalPeriod.objects.filter(organization=org).count()
        self.assertEqual(periods_count, 12, "Must initialize 12 monthly fiscal periods.")

    def test_post_organizations_unauthenticated_returns_401(self) -> None:
        """Unauthenticated POST to organizations endpoint is blocked by permission guard."""
        self.client.credentials()  # Clear authorization credentials
        payload = {"name": "Unauth Business"}

        response = self.client.post("/api/v1/tenancy/organizations/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_organizations_invalid_tin_rejected(self) -> None:
        """Invalid GRA TIN format fails serializer validation with 400 Bad Request."""
        payload = {
            "name": "Invalid TIN Corp",
            "business_tin": "INVALID123",  # Does not match ^[CPGVT]\d{10}$
        }

        response = self.client.post("/api/v1/tenancy/organizations/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("business_tin", response.data)

    def test_get_organizations_lists_user_memberships(self) -> None:
        """GET /api/v1/tenancy/organizations/ returns organizations where user is member."""
        # Create an org via POST
        post_response = self.client.post(
            "/api/v1/tenancy/organizations/",
            {"name": "Listing Test Org", "business_tin": "C0009876543"},
            format="json",
        )
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)
        created_id = post_response.data["id"]

        # Call GET /organizations/ without X-Tenant-ID header
        get_response = self.client.get("/api/v1/tenancy/organizations/")
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)

        data = get_response.data
        results = data if isinstance(data, list) else data.get("results", [])
        org_ids = [str(item["id"]) for item in results]
        self.assertIn(str(created_id), org_ids)

    def test_atomic_rollback_on_seeder_failure(self) -> None:
        """If COA bootstrap fails, atomic transaction ensures zero orphaned Organization records."""
        payload = {
            "name": "Rollback Corp",
            "business_tin": "C0001112223",
        }

        with (
            patch(
                "apps.tenancy.views.seed_standard_chart_of_accounts",
                side_effect=RuntimeError("Simulated COA database failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.client.post("/api/v1/tenancy/organizations/", payload, format="json")

        # Verify no orphaned Organization was created in database
        self.assertFalse(Organization.objects.filter(name="Rollback Corp").exists())
        self.assertFalse(Organization.objects.filter(business_tin="C0001112223").exists())
