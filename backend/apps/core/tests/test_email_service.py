"""Unit tests for Transactional Email Service (Brevo API)."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.core.services.email import send_transactional_email


class EmailServiceTests(SimpleTestCase):
    """Test suite for send_transactional_email helper."""

    @override_settings(IS_TESTING=True)
    def test_send_transactional_email_suppressed_in_test_mode(self):
        """In IS_TESTING mode, email is suppressed and returns True without HTTP calls."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            result = send_transactional_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<p>Test</p>",
            )
            self.assertTrue(result)
            mock_urlopen.assert_not_called()

    @override_settings(IS_TESTING=False, BREVO_API_KEY="")
    def test_send_transactional_email_missing_api_key_returns_false(self):
        """When BREVO_API_KEY is empty, returns False without raising exception."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            result = send_transactional_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<p>Test</p>",
            )
            self.assertFalse(result)
            mock_urlopen.assert_not_called()

    @override_settings(
        IS_TESTING=False,
        BREVO_API_KEY="test-key-123",
        BREVO_SENDER_EMAIL="sender@example.com",
        BREVO_SENDER_NAME="Test Sender",
    )
    def test_send_transactional_email_success(self):
        """Successful Brevo API response returns True."""
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            result = send_transactional_email(
                to_email="recipient@example.com",
                subject="Welcome to Mage Books",
                html_content="<h1>Welcome</h1>",
                to_name="Recipient Name",
            )
            self.assertTrue(result)
            mock_urlopen.assert_called_once()
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.get_method(), "POST")
            self.assertEqual(req.get_header("Api-key"), "test-key-123")
            self.assertEqual(req.get_header("Content-type"), "application/json")

            data = json.loads(req.data.decode("utf-8"))
            self.assertEqual(data["sender"]["email"], "sender@example.com")
            self.assertEqual(data["to"][0]["email"], "recipient@example.com")
            self.assertEqual(data["to"][0]["name"], "Recipient Name")
            self.assertEqual(data["headers"]["X-Mailin-Track-Clicks"], "0")
            self.assertEqual(data["headers"]["X-Mailin-Track"], "0")

    @override_settings(
        IS_TESTING=False,
        BREVO_API_KEY="test-key-123",
        BREVO_SENDER_EMAIL="sender@example.com",
    )
    def test_send_transactional_email_custom_headers(self):
        """Custom headers are merged into default tracking suppression headers."""
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            result = send_transactional_email(
                to_email="recipient@example.com",
                subject="Subject",
                html_content="<p>Body</p>",
                headers={"X-Custom-Header": "value123"},
            )
            self.assertTrue(result)
            req = mock_urlopen.call_args[0][0]
            data = json.loads(req.data.decode("utf-8"))
            self.assertEqual(data["headers"]["X-Mailin-Track-Clicks"], "0")
            self.assertEqual(data["headers"]["X-Mailin-Track"], "0")
            self.assertEqual(data["headers"]["X-Custom-Header"], "value123")

    @override_settings(IS_TESTING=False, BREVO_API_KEY="test-key-123")
    def test_send_transactional_email_http_error_graceful_handling(self):
        """HTTP error from Brevo is logged and gracefully returns False."""
        mock_exc = urllib.error.HTTPError(
            url="https://api.brevo.com/v3/smtp/email",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"message":"unauthorized"}'),
        )

        with patch("urllib.request.urlopen", side_effect=mock_exc):
            result = send_transactional_email(
                to_email="recipient@example.com",
                subject="Subject",
                html_content="<p>Body</p>",
            )
            self.assertFalse(result)
