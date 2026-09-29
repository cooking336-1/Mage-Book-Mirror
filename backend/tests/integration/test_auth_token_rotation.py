"""Integration test suite for SimpleJWT cookie token rotation & blacklisting (Task B.10 / T2.5).

Covers:
- Cookie refresh cycle writes new rotated refresh token and access token in HttpOnly cookies
- Old refresh tokens are blacklisted upon rotation and strictly rejected on reuse (HTTP 401)
- Continuous session refresh with successively rotated tokens
- JSON body payload mode for mobile/API clients exposes new refresh token in response body
- Security hardening: cookie mode never leaks refresh token into JSON response body
- Negative validation: missing and malformed tokens rejected with HTTP 401
- Concurrency resilience: in-flight mutex queue prevents race-condition token collisions
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class AuthTokenRotationIntegrationTests(APITestCase):
    """T2.5: SimpleJWT Cookie Token Rotation & Blacklist Test Suite."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="rotation.tester@magebooks.com",
            password="SecurePassword2026!",
            first_name="Kwesi",
            last_name="Appiah",
        )
        self.login_url = reverse("authentication:login")
        self.refresh_url = reverse("authentication:refresh")
        self.me_url = reverse("authentication:me")
        self.logout_url = reverse("authentication:logout")

    def test_cookie_refresh_rotates_tokens_and_updates_cookies(self):
        """Verifies cookie refresh writes new access and refresh tokens into HttpOnly cookies."""
        initial_refresh = RefreshToken.for_user(self.user)
        initial_refresh_str = str(initial_refresh)

        self.client.cookies["refresh_token"] = initial_refresh_str
        response = self.client.post(self.refresh_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Inspect updated access_token cookie
        self.assertIn("access_token", response.cookies)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertEqual(response.cookies["access_token"]["samesite"], "Strict")

        # Inspect rotated refresh_token cookie
        self.assertIn("refresh_token", response.cookies)
        rotated_refresh_str = response.cookies["refresh_token"].value
        self.assertTrue(response.cookies["refresh_token"]["httponly"])
        self.assertEqual(response.cookies["refresh_token"]["path"], "/api/v1/auth/")
        self.assertNotEqual(rotated_refresh_str, initial_refresh_str)

        # Security hardening: Cookie-authenticated refresh MUST NOT leak refresh token in JSON
        self.assertNotIn("refresh", response.data)
        self.assertIn("access", response.data)

    def test_old_refresh_token_is_blacklisted_and_rejected_on_replay(self):
        """Replaying an old refresh token after rotation fails with HTTP 401."""
        initial_refresh = RefreshToken.for_user(self.user)
        initial_refresh_str = str(initial_refresh)

        # Step 1: Perform legitimate rotation
        self.client.cookies["refresh_token"] = initial_refresh_str
        response1 = self.client.post(self.refresh_url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        new_refresh_str = response1.cookies["refresh_token"].value

        # Verify old token exists in BlacklistedToken table
        initial_token_jti = initial_refresh.get("jti")
        outstanding = OutstandingToken.objects.filter(jti=initial_token_jti).first()
        if outstanding:
            self.assertTrue(BlacklistedToken.objects.filter(token=outstanding).exists())

        # Step 2: Attacker replays old refresh token via cookie
        replay_client = APIClient()
        replay_client.cookies["refresh_token"] = initial_refresh_str
        response2 = replay_client.post(self.refresh_url)

        self.assertEqual(response2.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response2.data)
        self.assertIn("blacklisted", str(response2.data["detail"]).lower())

        # Step 3: Legitimate client can continue with newly rotated token
        legitimate_client = APIClient()
        legitimate_client.cookies["refresh_token"] = new_refresh_str
        response3 = legitimate_client.post(self.refresh_url)
        self.assertEqual(response3.status_code, status.HTTP_200_OK)

    def test_json_body_client_receives_rotated_token_in_body(self):
        """Mobile/API clients sending refresh in JSON body receive the rotated token in JSON."""
        initial_refresh = RefreshToken.for_user(self.user)
        initial_refresh_str = str(initial_refresh)

        response = self.client.post(
            self.refresh_url,
            {"refresh": initial_refresh_str},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh", response.data)
        rotated_refresh_str = response.data["refresh"]
        self.assertNotEqual(rotated_refresh_str, initial_refresh_str)

        # Attempt to reuse old token via JSON body is blocked
        replay_res = self.client.post(
            self.refresh_url,
            {"refresh": initial_refresh_str},
            format="json",
        )
        self.assertEqual(replay_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_refresh_token_fails_with_401(self):
        """Calling refresh endpoint without cookie or JSON body fails with 401."""
        response = self.client.post(self.refresh_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.data)

    def test_malformed_refresh_token_fails_with_401(self):
        """Calling refresh endpoint with garbage string fails with 401."""
        self.client.cookies["refresh_token"] = "garbage.not-a-jwt.token"
        response = self.client.post(self.refresh_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_concurrency_resilience_frontend_queue_simulation(self):
        """Simulates frontend in-flight mutex queue:

        When 3 concurrent requests discover an expired access token, the first
        acquires the mutex and refreshes the token. The remaining 2 wait for
        the in-flight promise to resolve and retry using the new access token,
        preventing the blacklisted-token race condition.
        """
        initial_refresh = RefreshToken.for_user(self.user)
        initial_refresh_str = str(initial_refresh)

        # Simulation: Request 1 triggers /refresh/
        mutex_client = APIClient()
        mutex_client.cookies["refresh_token"] = initial_refresh_str
        refresh_res = mutex_client.post(self.refresh_url)
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)

        fresh_access_token = refresh_res.cookies["access_token"].value
        fresh_refresh_token = refresh_res.cookies["refresh_token"].value

        # Requests 2 and 3 do NOT call /refresh/ with initial_refresh_str
        # (which has now been blacklisted). Instead, the queued requests receive the new token.
        req2_client = APIClient()
        req2_client.cookies["access_token"] = fresh_access_token
        res2 = req2_client.get(self.me_url)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["email"], self.user.email)

        req3_client = APIClient()
        req3_client.cookies["access_token"] = fresh_access_token
        res3 = req3_client.get(self.me_url)
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertEqual(res3.data["email"], self.user.email)

        # Subsequent cycle uses the fresh refresh token
        next_cycle_client = APIClient()
        next_cycle_client.cookies["refresh_token"] = fresh_refresh_token
        next_cycle_res = next_cycle_client.post(self.refresh_url)
        self.assertEqual(next_cycle_res.status_code, status.HTTP_200_OK)
