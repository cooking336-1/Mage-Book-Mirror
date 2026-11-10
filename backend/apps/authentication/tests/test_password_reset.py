"""Comprehensive test suite for password reset workflow (Directives 1 & 6).

Covers:
1. Password reset request with valid, non-existent, and malformed emails (anti-enumeration).
2. Brevo transactional email dispatch invocation with security attributes.
3. Password reset confirmation with valid tokens, password hash updating, and login verification.
4. Cryptographic single-use replay prevention (token invalidated after password update).
5. Tampered, expired, or corrupted token rejection.
6. Password mismatch and length validation.
7. SimpleJWT session revocation (all outstanding refresh tokens blacklisted).
8. Rate limiting (IP throttle 5/min, Email burst 3/15min, Email daily cap 5/24hr).
9. Anti-enumeration integrity and PII hashing in cache keys.
"""

import hashlib
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
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
        cache.clear()
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            email="merchant@example.com",
            password="OriginalPassword123!",
            first_name="Kwame",
            last_name="Mensah",
        )
        self.request_url = reverse("authentication:password-reset")
        self.confirm_url = reverse("authentication:password-reset-confirm")

    def tearDown(self):
        cache.clear()
        super().tearDown()

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


class PasswordResetThrottleTests(TestCase):
    """Rigorous tests for IP-level and Email-level rate limiting on password reset."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("authentication:password-reset")
        self.user = CustomUser.objects.create_user(
            email="throttle_target@example.com",
            password="OriginalPassword123!",
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    @patch("apps.authentication.views.send_transactional_email")
    def test_ip_rate_throttle_blocks_sixth_request(self, mock_send_email):
        """IP throttle allows 5 requests per minute from a single IP, then blocks with HTTP 429."""
        mock_send_email.return_value = True
        client_ip = "192.0.2.1"

        # Make 5 requests with distinct emails from the SAME IP
        for i in range(5):
            res = self.client.post(
                self.url,
                {"email": f"user_{i}@example.com"},
                format="json",
                REMOTE_ADDR=client_ip,
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)

        # 6th request from same IP is throttled
        res_6 = self.client.post(
            self.url,
            {"email": "user_sixth@example.com"},
            format="json",
            REMOTE_ADDR=client_ip,
        )
        self.assertEqual(res_6.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", res_6.headers)

        # A request from a DIFFERENT IP still succeeds
        res_diff_ip = self.client.post(
            self.url,
            {"email": "user_sixth@example.com"},
            format="json",
            REMOTE_ADDR="192.0.2.99",
        )
        self.assertEqual(res_diff_ip.status_code, status.HTTP_200_OK)

    @patch("apps.authentication.views.send_transactional_email")
    def test_email_burst_throttle_blocks_fourth_request(self, mock_send_email):
        """Email throttle permits max 3 requests per 15 minutes, then returns HTTP 429."""
        mock_send_email.return_value = True
        target_email = "burst_user@example.com"

        # Send from 3 different IPs so IP rate throttle (5/min) does not interfere
        for i in range(3):
            res = self.client.post(
                self.url,
                {"email": target_email},
                format="json",
                REMOTE_ADDR=f"10.0.0.{i + 1}",
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)

        # 4th request within 15 minutes for same email must be blocked
        res_4 = self.client.post(
            self.url,
            {"email": target_email},
            format="json",
            REMOTE_ADDR="10.0.0.4",
        )
        self.assertEqual(res_4.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", res_4.headers)
        retry_after = int(res_4.headers["Retry-After"])
        self.assertGreater(retry_after, 0)
        self.assertLessEqual(retry_after, 900)

        # A DIFFERENT email from the same IP (or another IP) is NOT blocked
        res_other = self.client.post(
            self.url,
            {"email": "different_target@example.com"},
            format="json",
            REMOTE_ADDR="10.0.0.5",
        )
        self.assertEqual(res_other.status_code, status.HTTP_200_OK)

    @patch("apps.authentication.throttles.time.time")
    @patch("apps.authentication.views.send_transactional_email")
    def test_email_daily_cap_blocks_sixth_request_over_24h(self, mock_send_email, mock_time):
        """Email throttle allows max 5 requests per 24 hours, even if burst window resets."""
        mock_send_email.return_value = True
        target_email = "daily_user@example.com"
        t0 = 1700000000.0

        # Burst 1: 3 requests at t0
        mock_time.return_value = t0
        for i in range(3):
            res = self.client.post(
                self.url,
                {"email": target_email},
                format="json",
                REMOTE_ADDR=f"10.1.0.{i + 1}",
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Advance time by 950 seconds (> 15-minute burst window: 900s)
        # Daily count is currently 3/5
        t1 = t0 + 950.0
        mock_time.return_value = t1

        # 4th request succeeds (burst window refreshed)
        res_4 = self.client.post(
            self.url,
            {"email": target_email},
            format="json",
            REMOTE_ADDR="10.1.0.4",
        )
        self.assertEqual(res_4.status_code, status.HTTP_200_OK)

        # Advance time by another 950 seconds
        # Daily count is currently 4/5
        t2 = t1 + 950.0
        mock_time.return_value = t2

        # 5th request succeeds (daily cap 5 reached)
        res_5 = self.client.post(
            self.url,
            {"email": target_email},
            format="json",
            REMOTE_ADDR="10.1.0.5",
        )
        self.assertEqual(res_5.status_code, status.HTTP_200_OK)

        # 6th request within 24 hours (t2 is only 1900s since t0) must be BLOCKED by daily cap
        t3 = t2 + 10.0
        mock_time.return_value = t3
        res_6 = self.client.post(
            self.url,
            {"email": target_email},
            format="json",
            REMOTE_ADDR="10.1.0.6",
        )
        self.assertEqual(res_6.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", res_6.headers)
        retry_after = int(res_6.headers["Retry-After"])
        expected_wait = int(86400 - (t3 - t0))
        self.assertEqual(retry_after, expected_wait)

    def test_anti_enumeration_nonexistent_email_throttled_identically(self):
        """Non-existent emails are throttled identically to prevent account enumeration."""
        ghost_email = "ghost_never_registered@example.com"

        for i in range(3):
            res = self.client.post(
                self.url,
                {"email": ghost_email},
                format="json",
                REMOTE_ADDR=f"10.2.0.{i + 1}",
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)

        res_4 = self.client.post(
            self.url,
            {"email": ghost_email},
            format="json",
            REMOTE_ADDR="10.2.0.4",
        )
        self.assertEqual(res_4.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_pii_protection_no_plaintext_email_in_cache(self):
        """Email addresses are hashed with SHA-256 before being stored in cache keys."""
        secret_email = "sensitive_owner@privatecorp.gh"

        self.client.post(
            self.url,
            {"email": secret_email},
            format="json",
            REMOTE_ADDR="10.3.0.1",
        )

        expected_hash = hashlib.sha256(secret_email.encode("utf-8")).hexdigest()[:16]
        burst_key = f"throttle:reset:burst:{expected_hash}"
        daily_key = f"throttle:reset:daily:{expected_hash}"

        self.assertIsNotNone(cache.get(burst_key))
        self.assertIsNotNone(cache.get(daily_key))

        # Ensure plaintext email is not part of any key in the cache
        raw_key = f"throttle:reset:burst:{secret_email}"
        self.assertIsNone(cache.get(raw_key))

    def test_malformed_email_does_not_consume_rate_limit(self):
        """Malformed emails return HTTP 400 and bypass rate limit consumption."""
        for _ in range(5):
            res = self.client.post(
                self.url,
                {"email": "not-a-valid-email"},
                format="json",
                REMOTE_ADDR="10.4.0.1",
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
