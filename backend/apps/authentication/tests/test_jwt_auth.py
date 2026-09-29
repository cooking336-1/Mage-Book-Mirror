"""Test suite for CustomUser model and JWT cookie authentication."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class CustomUserModelTests(TestCase):
    """Tests for CustomUser model and CustomUserManager."""

    def setUp(self):
        self.email = "accra.accountant@magebooks.com"
        self.password = "StrongPassword2026!"

    def test_create_user_success(self):
        """Verify standard user creation with UUIDv7 primary key and normalized email."""
        user = User.objects.create_user(
            email="  Accra.Accountant@Magebooks.COM ",
            password=self.password,
            first_name="Kwame",
            last_name="Mensah",
            phone_number="+233241234567",
        )
        self.assertEqual(user.email, "Accra.Accountant@magebooks.com")
        self.assertTrue(user.check_password(self.password))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertIsInstance(user.id, uuid.UUID)
        # Check that it is UUIDv7 (version 7)
        self.assertEqual(user.id.version, 7)
        self.assertEqual(user.get_full_name(), "Kwame Mensah")
        self.assertEqual(user.get_short_name(), "Kwame")
        self.assertEqual(str(user), "Accra.Accountant@magebooks.com")

    def test_create_user_missing_email_raises_value_error(self):
        """Verify that creating a user without an email raises ValueError."""
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password=self.password)

    def test_create_superuser_success(self):
        """Verify superuser creation with correct staff and superuser privileges."""
        admin = User.objects.create_superuser(
            email="superadmin@magebooks.com",
            password=self.password,
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)

    def test_create_superuser_invalid_flags_raise_value_error(self):
        """Verify validation errors if is_staff or is_superuser flags are overridden to False."""
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="admin1@magebooks.com",
                password=self.password,
                is_staff=False,
            )
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="admin2@magebooks.com",
                password=self.password,
                is_superuser=False,
            )


class JWTAuthAPITests(TestCase):
    """Integration tests for JWT login, refresh, logout, and cookie sessions."""

    def setUp(self):
        self.client = APIClient()
        self.email = "finance@magebooks.gh"
        self.password = "ValidSecurePass2026!"
        self.user = User.objects.create_user(
            email=self.email,
            password=self.password,
            first_name="Abena",
            last_name="Osei",
            phone_number="+233209876543",
        )

    def test_login_success_sets_httponly_strict_cookies(self):
        """Verify login returns 200 and sets HttpOnly, SameSite=Strict session cookies."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], self.email)

        # Inspect access_token cookie
        self.assertIn("access_token", response.cookies)
        access_cookie = response.cookies["access_token"]
        self.assertTrue(access_cookie["httponly"])
        self.assertEqual(access_cookie["samesite"], "Strict")
        self.assertEqual(access_cookie["path"], "/")

        # Inspect refresh_token cookie
        self.assertIn("refresh_token", response.cookies)
        refresh_cookie = response.cookies["refresh_token"]
        self.assertTrue(refresh_cookie["httponly"])
        self.assertEqual(refresh_cookie["samesite"], "Strict")
        self.assertEqual(refresh_cookie["path"], "/api/v1/auth/")

    def test_login_invalid_credentials_returns_401(self):
        """Verify login with incorrect password returns 401 Unauthorized."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.email, "password": "WrongPassword!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access_token", response.cookies)

    def test_login_inactive_user_returns_401(self):
        """Verify disabled user cannot log in."""
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_request_returns_401(self):
        """Verify protected endpoint /api/v1/auth/me/ rejects unauthenticated requests."""
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_request_via_cookie(self):
        """Verify protected endpoint authenticates successfully via access_token cookie."""
        refresh = RefreshToken.for_user(self.user)
        access_token = str(refresh.access_token)

        self.client.cookies["access_token"] = access_token
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.email)
        self.assertEqual(response.data["full_name"], "Abena Osei")

    def test_authenticated_request_via_bearer_header(self):
        """Verify protected endpoint authenticates via Authorization header as fallback."""
        refresh = RefreshToken.for_user(self.user)
        access_token = str(refresh.access_token)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.email)

    def test_refresh_token_endpoint(self):
        """Verify refresh endpoint accepts refresh cookie and issues new access token cookie."""
        refresh = RefreshToken.for_user(self.user)
        refresh_token = str(refresh)

        self.client.cookies["refresh_token"] = refresh_token
        response = self.client.post("/api/v1/auth/refresh/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertTrue(response.cookies["access_token"]["httponly"])

    def test_refresh_token_missing_cookie_returns_401(self):
        """Verify refresh endpoint returns 401 when refresh cookie is absent."""
        response = self.client.post("/api/v1/auth/refresh/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_clears_cookies(self):
        """Verify logout endpoint clears both access_token and refresh_token cookies."""
        self.client.cookies["access_token"] = "mock_access_token"
        self.client.cookies["refresh_token"] = "mock_refresh_token"

        response = self.client.post("/api/v1/auth/logout/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify cookies are expired/deleted
        self.assertEqual(response.cookies["access_token"].value, "")
        self.assertEqual(response.cookies["refresh_token"].value, "")

    def test_csrf_token_endpoint_provides_valid_token(self):
        """Verify GET /api/v1/auth/csrf/ returns CSRF token for SPAs."""
        response = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("csrf_token", response.data)
        self.assertTrue(len(response.data["csrf_token"]) > 0)

    def test_cookie_authenticated_mutating_request_without_csrf_fails_403(self):
        """Verify mutating request using access_token cookie without CSRF header is rejected."""
        csrf_client = APIClient(enforce_csrf_checks=True)
        refresh = RefreshToken.for_user(self.user)
        csrf_client.cookies["access_token"] = str(refresh.access_token)

        response = csrf_client.patch(
            "/api/v1/auth/me/",
            {"first_name": "ForgedName"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("CSRF Failed", response.data.get("detail", ""))

    def test_cookie_authenticated_mutating_request_with_csrf_succeeds(self):
        """Verify mutating request using access_token cookie succeeds with valid CSRF token."""
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf_response = csrf_client.get("/api/v1/auth/csrf/")
        csrf_token = csrf_response.data["csrf_token"]

        refresh = RefreshToken.for_user(self.user)
        csrf_client.cookies["access_token"] = str(refresh.access_token)
        csrf_client.cookies["csrftoken"] = csrf_token

        response = csrf_client.patch(
            "/api/v1/auth/me/",
            {"first_name": "UpdatedAbena"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "UpdatedAbena")
        self.assertEqual(response.data["full_name"], "UpdatedAbena Osei")

    def test_bearer_token_authenticated_mutating_request_exempt_from_csrf(self):
        """Verify mutating request using Bearer header is exempt from CSRF checks."""
        refresh = RefreshToken.for_user(self.user)
        access_token = str(refresh.access_token)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"first_name": "BearerUser"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "BearerUser")

    def test_expired_cookie_falls_back_to_bearer_header(self):
        """Verify that an invalid/expired access_token cookie falls through to Bearer header."""
        refresh = RefreshToken.for_user(self.user)
        access_token = str(refresh.access_token)

        # Set an invalid or expired cookie
        self.client.cookies["access_token"] = "invalid.expired.jwt.token"
        # Provide valid Bearer credentials in Authorization header
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.email)

    @override_settings(
        SIMPLE_JWT={
            "ROTATE_REFRESH_TOKENS": True,
            "BLACKLIST_AFTER_ROTATION": False,
        }
    )
    def test_refresh_token_rotation_when_enabled_sets_new_cookie(self):
        """Verify that when rotation is enabled, refresh response sets new rotated cookie."""
        refresh = RefreshToken.for_user(self.user)
        initial_refresh_token = str(refresh)

        self.client.cookies["refresh_token"] = initial_refresh_token
        response = self.client.post("/api/v1/auth/refresh/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Access token cookie must be updated
        self.assertIn("access_token", response.cookies)

        # Refresh token cookie must be rotated and different from initial token
        self.assertIn("refresh_token", response.cookies)
        new_cookie_val = response.cookies["refresh_token"].value
        self.assertNotEqual(new_cookie_val, initial_refresh_token)

        # Security hardening: When cookie was used, refresh must NOT leak in JSON body
        self.assertNotIn("refresh", response.data)

    @override_settings(
        SIMPLE_JWT={
            "ROTATE_REFRESH_TOKENS": True,
            "BLACKLIST_AFTER_ROTATION": False,
        }
    )
    def test_refresh_token_rotation_when_sent_via_json_body_includes_refresh_in_json(self):
        """Verify mobile/API clients sending refresh via JSON body receive rotated token in JSON."""
        refresh = RefreshToken.for_user(self.user)
        initial_refresh_token = str(refresh)

        # No cookie set; payload passed in JSON body
        response = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh": initial_refresh_token},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh", response.data)
        self.assertNotEqual(response.data["refresh"], initial_refresh_token)
        self.assertIn("access", response.data)

    @override_settings(
        SIMPLE_JWT={
            "ROTATE_REFRESH_TOKENS": True,
            "BLACKLIST_AFTER_ROTATION": False,
        }
    )
    def test_subsequent_refresh_with_new_rotated_token_succeeds(self):
        """Verify session continuity: refreshing with newly rotated token succeeds."""
        refresh = RefreshToken.for_user(self.user)
        initial_refresh_token = str(refresh)

        # Step 1: Initial refresh
        self.client.cookies["refresh_token"] = initial_refresh_token
        response1 = self.client.post("/api/v1/auth/refresh/")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        rotated_refresh_token = response1.cookies["refresh_token"].value

        # Step 2: Second refresh using newly rotated token
        self.client.cookies["refresh_token"] = rotated_refresh_token
        response2 = self.client.post("/api/v1/auth/refresh/")
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response2.cookies)
        self.assertIn("refresh_token", response2.cookies)
        second_rotated_token = response2.cookies["refresh_token"].value
        self.assertNotEqual(second_rotated_token, rotated_refresh_token)

    @override_settings(
        SIMPLE_JWT={
            "ROTATE_REFRESH_TOKENS": False,
            "BLACKLIST_AFTER_ROTATION": False,
        }
    )
    def test_refresh_token_without_rotation_preserves_single_access_cookie(self):
        """Verify backward compatibility: when rotation is disabled, refresh cookie is unchanged."""
        refresh = RefreshToken.for_user(self.user)
        initial_refresh_token = str(refresh)

        self.client.cookies["refresh_token"] = initial_refresh_token
        response = self.client.post("/api/v1/auth/refresh/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertNotIn("refresh_token", response.cookies)
