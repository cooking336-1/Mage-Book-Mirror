"""Tests for Session Inactivity Unlock Endpoint (VerifyPasswordView - Task C.7 / Feature F6)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class TestVerifyPasswordEndpoint(TestCase):
    """Verifies POST /api/v1/auth/verify-password/ endpoint for session unlock."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="sessionlock@magebooks.com",
            password="CorrectPassword123!",
            first_name="Kwame",
            last_name="Appiah",
        )

    def test_verify_password_success(self) -> None:
        """Authenticated user submitting correct password receives HTTP 200."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/auth/verify-password/",
            {"password": "CorrectPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Password verified successfully.")

    def test_verify_password_incorrect(self) -> None:
        """Authenticated user submitting wrong password receives HTTP 401."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/auth/verify-password/",
            {"password": "WrongPassword999!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Incorrect password", response.data["detail"])

    def test_verify_password_missing_payload(self) -> None:
        """Submitting empty body receives HTTP 400."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/auth/verify-password/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_verify_password_unauthenticated(self) -> None:
        """Unauthenticated request is rejected with HTTP 401."""
        response = self.client.post(
            "/api/v1/auth/verify-password/",
            {"password": "AnyPassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestPasswordResetRequestEndpoint(TestCase):
    """Verifies POST /api/v1/auth/password-reset/ endpoint."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="resetme@magebooks.com",
            password="StrongPassword123!",
            first_name="Abena",
            last_name="Mansah",
        )

    def test_password_reset_existing_user(self) -> None:
        """Submitting email of active user returns HTTP 200."""
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "resetme@magebooks.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)

    def test_password_reset_nonexistent_user_returns_200_anti_enumeration(self) -> None:
        """Submitting non-existent email still returns HTTP 200 to prevent account enumeration."""
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "unknown_random_user_999@magebooks.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_invalid_email_format(self) -> None:
        """Submitting invalid email returns HTTP 400."""
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "not-an-email"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

