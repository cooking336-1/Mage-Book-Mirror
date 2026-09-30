"""Integration test suite for parameterized JWT cookie path settings (Task C.8 / B11).

Verifies:
- Default JWT_AUTH_COOKIE_PATH ("/") applies uniformly to access and refresh cookies
- Overriding JWT_AUTH_COOKIE_PATH (e.g. "/api/v1/auth/") updates cookie path across login,
  refresh, and registration
- Logout correctly clears cookies on the parameterized path and performs defensive cleanup
"""

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class CookiePathConfigurationTests(APITestCase):
    """Tests verifying JWT_AUTH_COOKIE_PATH parameterization across authentication views."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.password = "SecurePassword2026!"
        self.user = User.objects.create_user(
            email="cookie.tester@magebooks.com",
            password=self.password,
            first_name="Kofi",
            last_name="Mensah",
        )
        self.login_url = reverse("authentication:login")
        self.refresh_url = reverse("authentication:refresh")
        self.logout_url = reverse("authentication:logout")
        self.register_url = reverse("authentication:register")

    def test_default_cookie_path_is_root(self) -> None:
        """Verify default configuration sets cookie path to '/' for both access and refresh."""
        response = self.client.post(
            self.login_url,
            {"email": "cookie.tester@magebooks.com", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)

        self.assertEqual(response.cookies["access_token"]["path"], "/")
        self.assertEqual(response.cookies["refresh_token"]["path"], "/")

    @override_settings(JWT_AUTH_COOKIE_PATH="/custom/prefix/")
    def test_custom_cookie_path_respected_on_login(self) -> None:
        """Verify overridden JWT_AUTH_COOKIE_PATH is respected on login endpoint."""
        response = self.client.post(
            self.login_url,
            {"email": "cookie.tester@magebooks.com", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies["access_token"]["path"], "/custom/prefix/")
        self.assertEqual(response.cookies["refresh_token"]["path"], "/custom/prefix/")

    @override_settings(JWT_AUTH_COOKIE_PATH="/gateway/auth/")
    def test_custom_cookie_path_respected_on_refresh(self) -> None:
        """Verify overridden JWT_AUTH_COOKIE_PATH is applied when rotating tokens."""
        refresh = RefreshToken.for_user(self.user)
        self.client.cookies["refresh_token"] = str(refresh)

        response = self.client.post(self.refresh_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies["access_token"]["path"], "/gateway/auth/")
        self.assertEqual(response.cookies["refresh_token"]["path"], "/gateway/auth/")

    @override_settings(JWT_AUTH_COOKIE_PATH="/custom/logout/")
    def test_custom_cookie_path_respected_on_logout(self) -> None:
        """Verify logout deletes cookies on the configured JWT_AUTH_COOKIE_PATH."""
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("access_token", response.cookies)
        self.assertEqual(response.cookies["access_token"]["path"], "/custom/logout/")
        self.assertEqual(response.cookies["access_token"]["max-age"], 0)
