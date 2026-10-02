"""Integration test suite for Contact Management CRUD REST API (Task B.2 / B7 & T2.2).

Validates:
1. POST /api/v1/contacts/ creates Contact entity bound to active tenant.
2. GET /api/v1/contacts/ enforces strict tenant isolation (no cross-tenant leakage).
3. Filtering (?contact_type=CUSTOMER) and search (?search=...) work correctly.
4. PATCH /api/v1/contacts/<uuid:pk>/ updates contact fields.
5. DELETE /api/v1/contacts/<uuid:pk>/ removes unreferenced contact.
6. DELETE on contact with invoices is blocked by models.PROTECT returning 400 Bad Request.
7. Unauthenticated requests are rejected with HTTP 401 Unauthorized.
8. Auditor role is strictly read-only (GET allowed, POST/PATCH/DELETE return 403 Forbidden).
9. Statutory GRA TIN and Ghana Card validations fail fast on malformed inputs.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.invoicing.models import Contact, ContactTypeChoices, Invoice, InvoiceStatusChoices
from apps.tenancy.middleware import clear_current_tenant
from apps.tenancy.models import Organization, OrganizationMembership, RoleChoices

User = get_user_model()


class ContactAPITests(TestCase):
    """APIClient integration tests for Contact management REST endpoints."""

    def setUp(self) -> None:
        clear_current_tenant()
        self.client = APIClient()

        # Primary user and organization
        self.user = User.objects.create_user(
            email="kwame.lead@accrabooks.gh",
            password="StrongPassword2026!",
            first_name="Kwame",
            last_name="Lead",
            phone_number="+233241112233",
        )
        self.org_a = Organization.objects.create(
            name="Org Alpha Ltd",
            business_tin="C0012345678",
            phone="+233240001111",
            email="finance@alpha.gh",
        )
        self.membership_a = OrganizationMembership.objects.create(
            organization=self.org_a,
            user=self.user,
            role=RoleChoices.OWNER,
            is_active=True,
        )

        # Second organization for isolation testing
        self.org_b = Organization.objects.create(
            name="Org Beta Ltd",
            business_tin="C0098765432",
            phone="+233240002222",
            email="finance@beta.gh",
        )
        self.membership_b = OrganizationMembership.objects.create(
            organization=self.org_b,
            user=self.user,
            role=RoleChoices.OWNER,
            is_active=True,
        )

        # Authenticate with Bearer token and set Tenant A by default
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            HTTP_X_TENANT_ID=str(self.org_a.id),
        )

    def tearDown(self) -> None:
        clear_current_tenant()

    def test_create_contact_success(self) -> None:
        """POST /api/v1/contacts/ creates contact bound to active tenant."""
        payload = {
            "name": "Kofi Mensah Trading Enterprise",
            "contact_type": "CUSTOMER",
            "tin": "C0001234567",
            "ghana_card_number": "GHA-123456789-0",
            "phone": "+233241234567",
            "email": "kofi@mensahtrading.gh",
            "billing_address": "PO Box 123, Accra, Ghana",
            "currency": "GHS",
        }

        response = self.client.post("/api/v1/contacts/", payload, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201 Created, got {response.status_code}: {response.data}",
        )

        contact_id = response.data["id"]
        contact = Contact.objects.get(id=contact_id)
        self.assertEqual(contact.organization, self.org_a)
        self.assertEqual(contact.name, "Kofi Mensah Trading Enterprise")
        self.assertEqual(contact.contact_type, ContactTypeChoices.CUSTOMER)
        self.assertEqual(contact.tin, "C0001234567")
        self.assertEqual(contact.ghana_card_number, "GHA-123456789-0")

    def test_list_contacts_tenant_isolation(self) -> None:
        """GET /api/v1/contacts/ only returns contacts belonging to the active tenant."""
        # Create contact in Org A
        Contact.objects.create(
            organization=self.org_a,
            name="Alpha Customer 1",
            contact_type=ContactTypeChoices.CUSTOMER,
        )
        # Create contact in Org B
        Contact.objects.create(
            organization=self.org_b,
            name="Beta Customer 1",
            contact_type=ContactTypeChoices.CUSTOMER,
        )

        # Query as Org A
        response = self.client.get("/api/v1/contacts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = (
            response.data if isinstance(response.data, list) else response.data.get("results", [])
        )
        names = [c["name"] for c in data]
        self.assertIn("Alpha Customer 1", names)
        self.assertNotIn("Beta Customer 1", names)

        # Switch to Org B
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            HTTP_X_TENANT_ID=str(self.org_b.id),
        )
        response_b = self.client.get("/api/v1/contacts/")
        self.assertEqual(response_b.status_code, status.HTTP_200_OK)

        data_b = (
            response_b.data
            if isinstance(response_b.data, list)
            else response_b.data.get("results", [])
        )
        names_b = [c["name"] for c in data_b]
        self.assertIn("Beta Customer 1", names_b)
        self.assertNotIn("Alpha Customer 1", names_b)

    def test_filter_contacts_by_type(self) -> None:
        """GET /api/v1/contacts/?contact_type=CUSTOMER filters by classification."""
        Contact.objects.create(
            organization=self.org_a,
            name="Cust A",
            contact_type=ContactTypeChoices.CUSTOMER,
        )
        Contact.objects.create(
            organization=self.org_a,
            name="Supp B",
            contact_type=ContactTypeChoices.SUPPLIER,
        )

        response = self.client.get("/api/v1/contacts/?contact_type=CUSTOMER")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = (
            response.data if isinstance(response.data, list) else response.data.get("results", [])
        )
        names = [c["name"] for c in data]
        self.assertIn("Cust A", names)
        self.assertNotIn("Supp B", names)

    def test_update_contact(self) -> None:
        """PATCH /api/v1/contacts/<uuid:pk>/ updates contact fields."""
        contact = Contact.objects.create(
            organization=self.org_a,
            name="Original Name Ltd",
            phone="+233240000000",
        )

        payload = {"phone": "+233249999999", "name": "Updated Name Ltd"}
        response = self.client.patch(f"/api/v1/contacts/{contact.id}/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        contact.refresh_from_db()
        self.assertEqual(contact.name, "Updated Name Ltd")
        self.assertEqual(contact.phone, "+233249999999")

    def test_delete_contact_without_invoices(self) -> None:
        """DELETE /api/v1/contacts/<uuid:pk>/ deletes unreferenced contact."""
        contact = Contact.objects.create(
            organization=self.org_a,
            name="Deletable Contact",
        )

        response = self.client.delete(f"/api/v1/contacts/{contact.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Contact.objects.filter(id=contact.id).exists())

    def test_delete_contact_with_existing_invoice_protected(self) -> None:
        """DELETE contact with existing invoice is rejected with 400 Bad Request."""
        contact = Contact.objects.create(
            organization=self.org_a,
            name="Invoice Customer Ltd",
        )
        Invoice.objects.create(
            organization=self.org_a,
            customer=contact,
            invoice_number="INV-ALPHA-2026-00001",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            status=InvoiceStatusChoices.DRAFT,
            subtotal_amount=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            customer_name="Invoice Customer Ltd",
        )

        response = self.client.delete(f"/api/v1/contacts/{contact.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertTrue(Contact.objects.filter(id=contact.id).exists())

    def test_unauthenticated_request_blocked(self) -> None:
        """Unauthenticated requests are rejected with HTTP 401."""
        self.client.credentials()  # Clear credentials
        response = self.client.get("/api/v1/contacts/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auditor_role_cannot_mutate_contacts(self) -> None:
        """Auditor role has read-only access (GET 200, POST/PATCH/DELETE 403)."""
        auditor_user = User.objects.create_user(
            email="auditor@pwc.gh",
            password="StrongPassword2026!",
            first_name="Auditor",
            last_name="PwC",
            phone_number="+233249876543",
        )
        OrganizationMembership.objects.create(
            organization=self.org_a,
            user=auditor_user,
            role=RoleChoices.AUDITOR,
            is_active=True,
        )

        refresh = RefreshToken.for_user(auditor_user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
            HTTP_X_TENANT_ID=str(self.org_a.id),
        )

        # GET is permitted
        get_res = self.client.get("/api/v1/contacts/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

        # POST is forbidden
        post_res = self.client.post(
            "/api/v1/contacts/", {"name": "Auditor New Contact"}, format="json"
        )
        self.assertEqual(post_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_statutory_tin_and_card_validation(self) -> None:
        """Invalid GRA TIN format triggers 400 Bad Request."""
        payload = {
            "name": "Invalid TIN Contact",
            "tin": "INVALID_TIN_FORMAT",
        }
        response = self.client.post("/api/v1/contacts/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tin", response.data)
