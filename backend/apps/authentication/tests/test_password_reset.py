"""Comprehensive test suite for password reset workflow (Directives 1 & 6).

Covers:
1. Password reset request with valid, non-existent, and malformed emails (anti-enumeration).
2. Brevo transactional email dispatch invocation with security attributes.
3. Password reset confirmation with valid tokens, password hash updating, and login verification.
4. Cryptographic single-use replay prevention (token invalidated after password update).
5. Tampered, expired, or corrupted token rejection.
6. Password mismatch and length validation.
7. SimpleJWT session revocation (all outstanding refresh tokens blacklisted).
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

CustomUser = get_user_model()


class PasswordResetTests(TestCase):
    """End-to-end integration tests for password reset endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            email="merchant@example.com",
            password="OriginalPassword123!",
            first_name="Kwame",
            last_name="Mensah",
        )
        self.request_url = reverse("authentication:password-reset")
        self.confirm_url = reverse("authentication:password-reset-confirm")

    @patch("apps.authentication.views.send_transactional_email")
    def test_password_reset_request_valid_email(self, mock_send_email):
        """Valid email dispatches reset email with token and returns HTTP 200."""
        mock_send_email.return_value = True

        response = self.client.post(
            self.request_url,
            {"email": "merchant@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)
        self.assertIn("reset instructions have been dispatched", response.data["detail"])

        mock_send_email.assert_called_once()
        _, kwargs = mock_send_email.call_args
        self.assertEqual(kwargs["to_email"], "merchant@example.com")
        self.assertIn("Reset your Mage Books password", kwargs["subject"])
        self.assertIn("reset-password?uid=", kwargs["html_content"])

    @patch("apps.authentication.views.send_transactional_email")
    def test_password_reset_request_nonexistent_email_anti_enumeration(self, mock_send_email):
        """Non-existent email returns identical HTTP 200 without leaking account existence."""
        response = self.client.post(
            self.request_url,
            {"email": "nonexistent@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)
        self.assertIn("reset instructions have been dispatched", response.data["detail"])
        mock_send_email.assert_not_called()

    def test_password_reset_request_invalid_email_format(self):
        """Malformed email returns HTTP 400."""
        response = self.client.post(
            self.request_url,
            {"email": "not-an-email"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    @patch("apps.authentication.views.send_transactional_email")
    def test_password_reset_confirm_success(self, mock_send_email):
        """Valid reset token successfully updates password and permits login with new password."""
        token = default_token_generator.make_token(self.user)
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))

        new_password = "BrandNewSecurePassword456!"

        response = self.client.post(
            self.confirm_url,
            {
                "uid": uidb64,
                "token": token,
                "new_password": new_password,
                "confirm_password": new_password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)

        # Refresh user from database
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password("OriginalPassword123!"))

        # Verify login endpoint with new credentials succeeds
        login_url = reverse("authentication:login")
        login_res = self.client.post(
            login_url,
            {"email": "merchant@example.com", "password": new_password},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)

        # Verify old password fails
        failed_res = self.client.post(
            login_url,
            {"email": "merchant@example.com", "password": "OriginalPassword123!"},
            format="json",
        )
        self.assertEqual(failed_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_confirm_token_replay_rejected(self):
        """Single-use guarantee: Re-using a token after password change is rejected."""
        token = default_token_generator.make_token(self.user)
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))

        # First reset succeeds
        first_res = self.client.post(
            self.confirm_url,
            {
                "uid": uidb64,
                "token": token,
                "new_password": "FirstPassword123!",
                "confirm_password": "FirstPassword123!",
            },
            format="json",
        )
        self.assertEqual(first_res.status_code, status.HTTP_200_OK)

        # Second attempt with the SAME token must be rejected
        replay_res = self.client.post(
            self.confirm_url,
            {
                "uid": uidb64,
                "token": token,
                "new_password": "SecondPassword456!",
                "confirm_password": "SecondPassword456!",
            },
            format="json",
        )
        self.assertEqual(replay_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", replay_res.data)

    def test_password_reset_confirm_tampered_token_rejected(self):
        """Tampered cryptographic token returns HTTP 400."""
        token = default_token_generator.make_token(self.user)
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))

        # Tamper with token
        tampered_token = token[:-4] + "xxxx"

        response = self.client.post(
            self.confirm_url,
            {
                "uid": uidb64,
                "token": tampered_token,
                "new_password": "ValidPassword123!",
                "confirm_password": "ValidPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", response.data)

    def test_password_reset_confirm_password_mismatch(self):
        """Conflicting passwords return HTTP 400."""
        token = default_token_generator.make_token(self.user)
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.post(
            self.confirm_url,
            {
                "uid": uidb64,
                "token": token,
                "new_password": "PasswordOne123!",
                "confirm_password": "PasswordTwo456!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_password", response.data)

    def test_password_reset_confirm_password_too_short(self):
        """Password shorter than 8 characters returns HTTP 400."""
        token = default_token_generator.make_token(self.user)
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.post(
            self.confirm_url,
            {
                "uid": uidb64,
                "token": token,
                "new_password": "short",
                "confirm_password": "short",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_password_reset_confirm_revokes_jwt_sessions(self):
        """Password reset invalidates active refresh tokens via token blacklist."""
        RefreshToken.for_user(self.user)

        # Verify token exists in OutstandingToken
        outstanding = OutstandingToken.objects.filter(user=self.user)
        self.assertTrue(outstanding.exists())

        token = default_token_generator.make_token(self.user)
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.post(
            self.confirm_url,
            {
                "uid": uidb64,
                "token": token,
                "new_password": "BrandNewPassword789!",
                "confirm_password": "BrandNewPassword789!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify all tokens for this user are now in BlacklistedToken
        blacklisted = BlacklistedToken.objects.filter(token__user=self.user)
        self.assertEqual(blacklisted.count(), outstanding.count())
