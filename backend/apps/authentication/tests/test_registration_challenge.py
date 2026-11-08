"""Adversarial stress and edge-case verification tests for registration flow.

EMPIRICAL CHALLENGER TEST SUITE (Sprint A / Milestone 1)
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class RegistrationAdversarialChallengeTests(TestCase):
    """Adversarial challenge tests for the registration endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.register_url = "/api/v1/auth/register/"
        self.login_url = "/api/v1/auth/login/"

    # =========================================================================
    # 1. EMAIL CASE SENSITIVITY & NORMALIZATION
    # =========================================================================

    def test_case_sensitivity_duplicate_rejection(self):
        """Registering User@Example.Com must prevent duplicate variations."""
        # 1. Initial registration with mixed case
        res1 = self.client.post(
            self.register_url,
            {
                "email": "Case.Test@Example.COM",
                "password": "Password123!",
                "first_name": "Case",
                "last_name": "Test",
            },
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data["user"]["email"], "case.test@example.com")

        # 2. Duplicate attempt with all lowercase
        res2 = self.client.post(
            self.register_url,
            {
                "email": "case.test@example.com",
                "password": "DifferentPassword123!",
            },
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", res2.data)

        # 3. Duplicate attempt with all uppercase
        res3 = self.client.post(
            self.register_url,
            {
                "email": "CASE.TEST@EXAMPLE.COM",
                "password": "DifferentPassword123!",
            },
            format="json",
        )
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", res3.data)

        # 4. Duplicate attempt with mixed case and leading/trailing whitespace
        res4 = self.client.post(
            self.register_url,
            {
                "email": "   CaSe.TeSt@ExAmPlE.cOm   ",
                "password": "DifferentPassword123!",
            },
            format="json",
        )
        self.assertEqual(res4.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", res4.data)

    def test_registered_user_login_behavior_with_case_variations(self):
        """Empirical evaluation: Can a user registered with mixed case log in?

        Investigates whether email normalization at registration aligns with login.
        """
        res_reg = self.client.post(
            self.register_url,
            {
                "email": "LoginCase@MageBooks.COM",
                "password": "ValidPassword2026!",
            },
            format="json",
        )
        self.assertEqual(res_reg.status_code, status.HTTP_201_CREATED)
        # Email stored as lowercase in DB
        self.assertEqual(res_reg.data["user"]["email"], "logincase@magebooks.com")

        # 1. Login with lowercase succeeds
        res_login_lower = self.client.post(
            self.login_url,
            {"email": "logincase@magebooks.com", "password": "ValidPassword2026!"},
            format="json",
        )
        self.assertEqual(res_login_lower.status_code, status.HTTP_200_OK)

        # 2. Login with original mixed-case email fails with 401
        # because LoginSerializer does not normalize email.
        res_login_mixed = self.client.post(
            self.login_url,
            {"email": "LoginCase@MageBooks.COM", "password": "ValidPassword2026!"},
            format="json",
        )
        # Assert empirical finding: LoginView returns 401 when email has uppercase letters
        self.assertEqual(
            res_login_mixed.status_code,
            status.HTTP_401_UNAUTHORIZED,
            "Documented finding: Login fails with 401 when entering mixed-case email",
        )

    # =========================================================================
    # 2. BOUNDARY PASSWORD INPUTS
    # =========================================================================

    def test_password_length_boundary_7_chars(self):
        """Password of 7 characters must be rejected with 400 Bad Request."""
        res = self.client.post(
            self.register_url,
            {"email": "boundary7@example.com", "password": "Pass12!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)

    def test_password_length_boundary_8_chars(self):
        """Password of exactly 8 characters must be accepted."""
        res = self.client.post(
            self.register_url,
            {"email": "boundary8@example.com", "password": "Pass123!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_password_length_1000_chars(self):
        """Extremely long password (1000 chars) must not crash or cause unhandled 500."""
        long_password = "SecurePassword123!#" * 50
        res = self.client.post(
            self.register_url,
            {"email": "boundary1000@example.com", "password": long_password},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # Ensure user can log in with this 1000-char password
        res_login = self.client.post(
            self.login_url,
            {"email": "boundary1000@example.com", "password": long_password},
            format="json",
        )
        self.assertEqual(res_login.status_code, status.HTTP_200_OK)

    def test_password_special_characters_and_unicode(self):
        """Password with symbols, emojis, and non-ASCII Unicode characters must succeed."""
        complex_pw = "P@sswørd!#$%^&*()_+-=[]{}|;':\",./<>?~`🎉🇬🇭"
        res = self.client.post(
            self.register_url,
            {"email": "unicode.pw@example.com", "password": complex_pw},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # Verify login with same unicode password
        res_login = self.client.post(
            self.login_url,
            {"email": "unicode.pw@example.com", "password": complex_pw},
            format="json",
        )
        self.assertEqual(res_login.status_code, status.HTTP_200_OK)

    def test_password_whitespace_only(self):
        """Password of only whitespace characters must be rejected with 400 Bad Request."""
        res = self.client.post(
            self.register_url,
            {"email": "whitespace.pw@example.com", "password": "        "},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)

    # =========================================================================
    # 3. COMPLEX EMAIL FORMATS & EDGES
    # =========================================================================

    def test_complex_valid_rfc_emails(self):
        """Valid complex RFC emails must succeed."""
        valid_emails = [
            "user.name+tag@sub.domain.co.uk",
            "first_last-123@example.org",
            "customer.service+ghana@magebooks.africa",
        ]
        for email in valid_emails:
            res = self.client.post(
                self.register_url,
                {"email": email, "password": "Password123!"},
                format="json",
            )
            self.assertEqual(
                res.status_code,
                status.HTTP_201_CREATED,
                f"Valid email '{email}' rejected: {res.data}",
            )

    def test_email_leading_and_trailing_whitespace(self):
        """Emails with surrounding whitespace must be trimmed and registered cleanly."""
        res = self.client.post(
            self.register_url,
            {
                "email": "   spaced.account@example.com   \t\n",
                "password": "Password123!",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["user"]["email"], "spaced.account@example.com")

    def test_invalid_email_formats(self):
        """Malformed emails must be rejected with 400 Bad Request."""
        invalid_emails = [
            "missingdomain@",
            "@missinguser.com",
            "user with spaces@example.com",
            "plainaddress",
            "user@domain..com",
            "",
            "   ",
            "user@" + "a" * 250 + ".com",  # Exceeds max length
        ]
        for email in invalid_emails:
            res = self.client.post(
                self.register_url,
                {"email": email, "password": "Password123!"},
                format="json",
            )
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Invalid email '{email}' was unexpectedly accepted or crashed: {res.status_code}",
            )
            self.assertIn("email", res.data)

    # =========================================================================
    # 4. COOKIE SECURITY ATTRIBUTES
    # =========================================================================

    def test_jwt_cookie_security_attributes(self):
        """Verify access_token and refresh_token have HttpOnly, SameSite=Strict, path=/."""
        res = self.client.post(
            self.register_url,
            {"email": "cookies.test@example.com", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Access token cookie
        self.assertIn("access_token", res.cookies)
        access = res.cookies["access_token"]
        self.assertTrue(access["httponly"], "access_token must have HttpOnly=True")
        self.assertEqual(access["samesite"].lower(), "strict")
        self.assertEqual(access["path"], "/", "access_token path must be /")
        self.assertGreater(access["max-age"], 0, "access_token max-age must be > 0")

        # Refresh token cookie
        self.assertIn("refresh_token", res.cookies)
        refresh = res.cookies["refresh_token"]
        self.assertTrue(refresh["httponly"], "refresh_token must have HttpOnly=True")
        self.assertEqual(refresh["samesite"].lower(), "strict")
        self.assertEqual(refresh["path"], "/", "refresh_token path must be /")
        self.assertGreater(refresh["max-age"], 0, "refresh_token max-age must be > 0")

    # =========================================================================
    # 5. SIMULATED STALE OR ACTIVE COOKIES PRESENT
    # =========================================================================

    def test_registration_with_stale_or_active_tokens(self):
        """Verify registration succeeds when client has active or stale cookies."""
        csrf_client = APIClient(enforce_csrf_checks=True)

        # 1. Stale / expired garbage tokens
        csrf_client.cookies["access_token"] = "stale.garbage.token"
        csrf_client.cookies["refresh_token"] = "stale.garbage.refresh"

        res = csrf_client.post(
            self.register_url,
            {"email": "stale.cookies@example.com", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["user"]["email"], "stale.cookies@example.com")
        self.assertNotEqual(res.cookies["access_token"].value, "stale.garbage.token")

        # 2. Existing valid user's tokens present during registration of a new user
        res2 = csrf_client.post(
            self.register_url,
            {"email": "another.account@example.com", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.data["user"]["email"], "another.account@example.com")

    # =========================================================================
    # 6. RAPID SEQUENTIAL REGISTRATIONS WITH IDENTICAL EMAIL
    # =========================================================================

    def test_rapid_sequential_registrations_identical_email(self):
        """Rapid repeated registration attempts with identical email must not return 500."""
        payload = {
            "email": "rapid.repeat@magebooks.com",
            "password": "Password123!",
            "first_name": "Rapid",
            "last_name": "Tester",
        }

        # First registration should succeed (201)
        res1 = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Subsequent 10 rapid registrations must all return 400 Bad Request, never 500
        for i in range(10):
            res = self.client.post(self.register_url, payload, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Attempt {i+1} returned status {res.status_code} instead of 400",
            )
            self.assertIn("email", res.data)

    # =========================================================================
    # 7. SECURITY: PRIVILEGE ESCALATION & INPUT OVERFLOW PREVENTION
    # =========================================================================

    def test_privilege_escalation_fields_ignored(self):
        """Attacker injecting is_staff, is_superuser, or groups must NOT gain privileges."""
        res = self.client.post(
            self.register_url,
            {
                "email": "hacker@example.com",
                "password": "Password123!",
                "is_staff": True,
                "is_superuser": True,
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="hacker@example.com")
        self.assertFalse(user.is_staff, "User must NOT be staff")
        self.assertFalse(user.is_superuser, "User must NOT be superuser")
        self.assertTrue(user.is_active, "User should default to active")

    def test_oversized_first_and_last_name_rejected_without_500(self):
        """Fields exceeding max_length (150 chars) must return 400, not 500."""
        res = self.client.post(
            self.register_url,
            {
                "email": "overflow@example.com",
                "password": "Password123!",
                "first_name": "A" * 200,
                "last_name": "B" * 200,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("first_name", res.data)
        self.assertIn("last_name", res.data)

    def test_malformed_json_returns_400_not_500(self):
        """Malformed JSON payload must return 400 Bad Request, not unhandled 500."""
        res = self.client.post(
            self.register_url,
            data="{invalid_json:",
            content_type="application/json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # =========================================================================
    # 8. CONCURRENCY RACE CONDITION / TOCTOU STRESS TEST
    # =========================================================================

    def test_concurrency_race_condition_toctou_save_integrity_error(self):
        """Adversarial stress: Demonstrates unhandled IntegrityError if TOCTOU occurs.

        If two concurrent requests pass serializer validation simultaneously,
        the second save() raises database IntegrityError.
        This test documents that RegisterView currently lets IntegrityError bubble up uncaught.
        """
        payload = {
            "email": "toctou.race@magebooks.com",
            "password": "Password123!",
        }

        with patch.object(
            User.objects,
            "create_user",
            side_effect=IntegrityError("duplicate key value violates unique constraint"),
        ):
            # RegisterView currently lacks try/except IntegrityError, raising uncaught
            with self.assertRaises(IntegrityError):
                self.client.post(self.register_url, payload, format="json")
