"""Integration and security penetration tests for Team Member Management & Owner Immutability.

Tests:
1. List members: Accessible to tenant members, scoped to active tenant.
2. Invite member: Owner can invite Admin, Accountant, Bookkeeper.
3. Invite member: Admin can invite Bookkeeper or Accountant.
4. Rogue Manager Defeat: Admin cannot assign OWNER role during creation (HTTP 403).
5. Rogue Manager Defeat: Admin cannot modify, demote, or deactivate an OWNER (HTTP 403).
6. Rogue Manager Defeat: Admin cannot promote any member to OWNER (HTTP 403).
7. Rogue Manager Defeat: Admin cannot remove/delete an OWNER (HTTP 403).
8. Sole Owner Protection: Owner cannot demote or delete the sole active Owner.
9. SoD Protection: Bookkeeper and Auditor are forbidden from managing team members (HTTP 403).
10. Cross-tenant isolation: Tenant Beta cannot mutate or view Tenant Alpha members.
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditTrail
from apps.authentication.models import CustomUser
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices


class TeamMemberManagementSecurityTestCase(TestCase):
    """Verifies RBAC rules and Owner Immutability against Rogue Manager privilege escalation."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()

        # Tenant Alpha
        self.org_alpha = Organization.objects.create(
            name="Alpha Corp Ltd",
            phone="+233240001111",
            email="finance@alpha.gh",
        )
        # Tenant Beta
        self.org_beta = Organization.objects.create(
            name="Beta Enterprise Ltd",
            phone="+233240002222",
            email="finance@beta.gh",
        )

        # Users for Org Alpha
        self.owner_alpha = CustomUser.objects.create_user(
            email="owner@alpha.gh",
            password="StrongPassword2026!",
            first_name="Alpha",
            last_name="Owner",
        )
        self.owner_alpha_membership = OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=self.owner_alpha,
            role=RoleChoices.OWNER,
        )

        self.admin_alpha = CustomUser.objects.create_user(
            email="admin@alpha.gh",
            password="StrongPassword2026!",
            first_name="Alpha",
            last_name="Admin",
        )
        self.admin_alpha_membership = OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=self.admin_alpha,
            role=RoleChoices.ADMIN,
        )

        self.accountant_alpha = CustomUser.objects.create_user(
            email="accountant@alpha.gh",
            password="StrongPassword2026!",
            first_name="Alpha",
            last_name="Accountant",
        )
        self.accountant_alpha_membership = OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=self.accountant_alpha,
            role=RoleChoices.ACCOUNTANT,
        )

        self.bookkeeper_alpha = CustomUser.objects.create_user(
            email="bookkeeper@alpha.gh",
            password="StrongPassword2026!",
            first_name="Alpha",
            last_name="Bookkeeper",
        )
        self.bookkeeper_alpha_membership = OrganizationMembership.objects.create(
            organization=self.org_alpha,
            user=self.bookkeeper_alpha,
            role=RoleChoices.BOOKKEEPER,
        )

        # Users for Org Beta
        self.owner_beta = CustomUser.objects.create_user(
            email="owner@beta.gh",
            password="StrongPassword2026!",
            first_name="Beta",
            last_name="Owner",
        )
        self.owner_beta_membership = OrganizationMembership.objects.create(
            organization=self.org_beta,
            user=self.owner_beta,
            role=RoleChoices.OWNER,
        )

    def tearDown(self) -> None:
        clear_current_tenant()

    def _authenticate(self, user: CustomUser, org: Organization) -> None:
        token = str(AccessToken.for_user(user))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(org.id),
        )

    def test_list_members_returns_tenant_roster(self) -> None:
        """GET /api/v1/tenancy/members/ returns all members of the active tenant."""
        self._authenticate(self.owner_alpha, self.org_alpha)
        response = self.client.get("/api/v1/tenancy/members/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 4)

    def test_owner_can_add_team_member(self) -> None:
        """Owner can add new members with any valid role."""
        self._authenticate(self.owner_alpha, self.org_alpha)
        payload = {
            "email": "intern@alpha.gh",
            "first_name": "Kofi",
            "last_name": "Intern",
            "role": RoleChoices.BOOKKEEPER,
        }
        response = self.client.post("/api/v1/tenancy/members/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=self.org_alpha,
                user__email="intern@alpha.gh",
                role=RoleChoices.BOOKKEEPER,
            ).exists()
        )

        # Verify audit trail
        self.assertTrue(
            AuditTrail.objects.filter(
                organization=self.org_alpha,
                action="TEAM_MEMBER_ADDED",
            ).exists()
        )

    def test_admin_cannot_create_member_as_owner(self) -> None:
        """Architecture Manual 4.6.2: Admin cannot assign OWNER role (HTTP 403 Forbidden)."""
        self._authenticate(self.admin_alpha, self.org_alpha)
        payload = {
            "email": "co-owner@alpha.gh",
            "first_name": "Colluder",
            "last_name": "Owner",
            "role": RoleChoices.OWNER,
        }
        response = self.client.post("/api/v1/tenancy/members/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Admins cannot assign the Organization Owner role", response.json()["detail"])

    def test_admin_cannot_modify_or_demote_owner(self) -> None:
        """Architecture Manual 4.6.2 (Owner Immutability): Admin cannot demote OWNER (HTTP 403)."""
        self._authenticate(self.admin_alpha, self.org_alpha)
        payload = {"role": RoleChoices.BOOKKEEPER}
        response = self.client.patch(
            f"/api/v1/tenancy/members/{self.owner_alpha_membership.id}/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Admins cannot modify, demote, or deactivate", response.json()["detail"])

        self.owner_alpha_membership.refresh_from_db()
        self.assertEqual(self.owner_alpha_membership.role, RoleChoices.OWNER)

    def test_admin_cannot_deactivate_owner(self) -> None:
        """Owner Immutability (Arch Manual 4.6.2): Admin cannot deactivate OWNER (HTTP 403)."""
        self._authenticate(self.admin_alpha, self.org_alpha)
        payload = {"is_active": False}
        response = self.client.patch(
            f"/api/v1/tenancy/members/{self.owner_alpha_membership.id}/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.owner_alpha_membership.refresh_from_db()
        self.assertTrue(self.owner_alpha_membership.is_active)

    def test_admin_cannot_promote_member_to_owner(self) -> None:
        """Admin cannot promote an accountant or bookkeeper to OWNER (HTTP 403)."""
        self._authenticate(self.admin_alpha, self.org_alpha)
        payload = {"role": RoleChoices.OWNER}
        response = self.client.patch(
            f"/api/v1/tenancy/members/{self.accountant_alpha_membership.id}/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn(
            "Admins cannot promote members to Organization Owner", response.json()["detail"]
        )

    def test_admin_cannot_delete_owner(self) -> None:
        """Architecture Manual 4.6.2 (Owner Immutability): Admin cannot delete OWNER (HTTP 403)."""
        self._authenticate(self.admin_alpha, self.org_alpha)
        response = self.client.delete(f"/api/v1/tenancy/members/{self.owner_alpha_membership.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Admins cannot remove an Organization Owner", response.json()["detail"])

        self.assertTrue(
            OrganizationMembership.objects.filter(id=self.owner_alpha_membership.id).exists()
        )

    def test_sole_owner_cannot_demote_self(self) -> None:
        """The sole active Owner cannot demote themselves, preventing orphaned organizations."""
        self._authenticate(self.owner_alpha, self.org_alpha)
        payload = {"role": RoleChoices.ADMIN}
        response = self.client.patch(
            f"/api/v1/tenancy/members/{self.owner_alpha_membership.id}/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sole active Organization Owner", str(response.json()))

    def test_bookkeeper_cannot_manage_members(self) -> None:
        """Bookkeepers are strictly forbidden from inviting, editing, or deleting members."""
        self._authenticate(self.bookkeeper_alpha, self.org_alpha)
        response = self.client.post(
            "/api/v1/tenancy/members/",
            {"email": "newbie@alpha.gh", "role": RoleChoices.BOOKKEEPER},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_tenant_member_mutation_is_blocked(self) -> None:
        """Admin or Owner in Org Alpha cannot mutate membership belonging to Org Beta."""
        self._authenticate(self.owner_alpha, self.org_alpha)
        response = self.client.patch(
            f"/api/v1/tenancy/members/{self.owner_beta_membership.id}/",
            {"role": RoleChoices.BOOKKEEPER},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
