"""Unit and Integration Tests for PII Column Encryption & Blind Index (Task C.5 / Feature G6).

Verifies:
1. Transparent ORM encryption on save and decryption on fetch.
2. Raw database inspection verifies ciphertext (Fernet token starting with 'gAAAAA').
3. Deterministic SHA-256 blind index generation on Organization.business_tin_hash.
4. Uniqueness enforcement on business_tin via blind index (case-insensitive, whitespace-trimmed).
5. Transparent OrganizationQuerySet filter translation from business_tin to business_tin_hash.
6. Null and empty string handling with zero collisions.
7. Field encryption coverage across Contact and PayrollItem models.
"""

import hashlib
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test import TestCase

from apps.core.fields import get_fernet
from apps.invoicing.models import Contact
from apps.ledger.models import FiscalPeriod
from apps.payroll.models import PayrollItem, PayrollRun, PayrollStatusChoices
from apps.tenancy.models import Organization

User = get_user_model()


class TestPIIEncryptionAndBlindIndex(TestCase):
    """Test suite for field-level encryption and deterministic blind indexing."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="testowner@magebooks.com",
            password="SecurePassword123!",
            first_name="Kwame",
            last_name="Mensah",
        )
        self.org = Organization.objects.create(
            name="Accra Haulage Ltd",
            phone="+233240001122",
            email="ops@accrahaulage.com",
            business_tin="C0001234567",
            ghana_card_number="GHA-123456789-0",
        )

    def test_organization_transparent_encryption_and_decryption(self) -> None:
        """Verifies ORM transparently returns plaintext while database stores ciphertext."""
        # Refresh from database
        self.org.refresh_from_db()

        # 1. ORM level: plaintext access
        self.assertEqual(self.org.business_tin, "C0001234567")
        self.assertEqual(self.org.ghana_card_number, "GHA-123456789-0")

        # 2. Raw SQL level: verify ciphertext storage
        pk_param = self.org.id.hex if connection.vendor == "sqlite" else self.org.id
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT business_tin, ghana_card_number, business_tin_hash "
                "FROM organizations WHERE id = %s",
                [pk_param],
            )
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        raw_tin, raw_ghana_card, raw_hash = row

        # Raw DB column must NOT contain plaintext
        self.assertNotEqual(raw_tin, "C0001234567")
        self.assertNotEqual(raw_ghana_card, "GHA-123456789-0")

        # Raw DB column must be valid Fernet token
        self.assertTrue(raw_tin.startswith("gAAAAA"))
        self.assertTrue(raw_ghana_card.startswith("gAAAAA"))

        # Verify decryption matches original
        fernet = get_fernet()
        self.assertEqual(fernet.decrypt(raw_tin.encode("utf-8")).decode("utf-8"), "C0001234567")
        self.assertEqual(
            fernet.decrypt(raw_ghana_card.encode("utf-8")).decode("utf-8"),
            "GHA-123456789-0",
        )

        # 3. Blind index verification
        expected_hash = hashlib.sha256(b"C0001234567").hexdigest()
        self.assertEqual(raw_hash, expected_hash)
        self.assertEqual(self.org.business_tin_hash, expected_hash)

    def test_blind_index_queryset_lookup(self) -> None:
        """Verifies OrganizationQuerySet transparently translates business_tin lookups to hash."""
        # Direct lookup by plaintext TIN
        found_org = Organization.objects.filter(business_tin="C0001234567").first()
        self.assertIsNotNone(found_org)
        self.assertEqual(found_org.id, self.org.id)

        # Non-matching lookup
        not_found = Organization.objects.filter(business_tin="C0009999999").first()
        self.assertIsNone(not_found)

    def test_blind_index_uniqueness_enforcement(self) -> None:
        """Verifies duplicate TIN raises ValidationError or IntegrityError via blind index."""
        duplicate_org = Organization(
            name="Duplicate Logistics",
            phone="+233240003344",
            email="dup@logistics.com",
            business_tin=" c0001234567 ",  # Mixed case & whitespace must normalize to same hash
        )

        # clean() method validation
        with self.assertRaises(ValidationError) as ctx:
            duplicate_org.clean()
        self.assertIn("business_tin", ctx.exception.message_dict)

        # Database-level unique constraint on business_tin_hash
        with self.assertRaises(IntegrityError):
            duplicate_org.save()

    def test_null_and_empty_tin_allows_multiple_records(self) -> None:
        """Verifies organizations without TINs have NULL hash and do not collide."""
        org_blank1 = Organization.objects.create(
            name="Sole Trader 1",
            phone="+233240005511",
            email="st1@gmail.com",
            business_tin="",
        )
        org_blank2 = Organization.objects.create(
            name="Sole Trader 2",
            phone="+233240005522",
            email="st2@gmail.com",
            business_tin=None,
        )

        self.assertIsNone(org_blank1.business_tin_hash)
        self.assertIsNone(org_blank2.business_tin_hash)

    def test_contact_tin_and_ghana_card_encryption(self) -> None:
        """Verifies Contact.tin and Contact.ghana_card_number are encrypted at rest."""
        contact = Contact.objects.create(
            organization=self.org,
            name="Volta Cement Co",
            email="contact@voltacement.com",
            phone="+233241112233",
            tin="C0009876543",
            ghana_card_number="GHA-987654321-0",
        )

        contact.refresh_from_db()
        self.assertEqual(contact.tin, "C0009876543")
        self.assertEqual(contact.ghana_card_number, "GHA-987654321-0")

        # Inspect raw SQL
        pk_param = contact.id.hex if connection.vendor == "sqlite" else contact.id
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tin, ghana_card_number FROM contacts WHERE id = %s",
                [pk_param],
            )
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        raw_tin, raw_ghana_card = row

        self.assertNotEqual(raw_tin, "C0009876543")
        self.assertNotEqual(raw_ghana_card, "GHA-987654321-0")
        self.assertTrue(raw_tin.startswith("gAAAAA"))
        self.assertTrue(raw_ghana_card.startswith("gAAAAA"))

    def test_payroll_item_tin_or_ghana_card_encryption(self) -> None:
        """Verifies PayrollItem.employee_tin_or_ghana_card is encrypted at rest."""
        period = FiscalPeriod.objects.create(
            organization=self.org,
            period_name="October 2026",
            start_date="2026-10-01",
            end_date="2026-10-31",
        )
        payroll_run = PayrollRun.objects.create(
            organization=self.org,
            period=period,
            maker=self.user,
            status=PayrollStatusChoices.DRAFT,
            total_gross_salary=Decimal("5000.00"),
            total_net_payout=Decimal("4000.00"),
            total_paye_tax=Decimal("500.00"),
            total_ssnit_employee=Decimal("275.00"),
            total_ssnit_employer=Decimal("650.00"),
        )
        item = PayrollItem.objects.create(
            organization=self.org,
            payroll_run=payroll_run,
            employee_name="Kofi Boateng",
            employee_tin_or_ghana_card="GHA-554433221-1",
            momo_number="+233241119988",
            gross_salary=Decimal("5000.00"),
            ssnit_employee=Decimal("275.00"),
            ssnit_employer=Decimal("650.00"),
            taxable_income=Decimal("4725.00"),
            paye_tax=Decimal("500.00"),
            net_salary=Decimal("4000.00"),
        )

        item.refresh_from_db()
        self.assertEqual(item.employee_tin_or_ghana_card, "GHA-554433221-1")

        pk_param = item.id.hex if connection.vendor == "sqlite" else item.id
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT employee_tin_or_ghana_card FROM payroll_items WHERE id = %s",
                [pk_param],
            )
            raw_id_val = cursor.fetchone()[0]

        self.assertNotEqual(raw_id_val, "GHA-554433221-1")
        self.assertTrue(raw_id_val.startswith("gAAAAA"))
