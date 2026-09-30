"""Unit and Integration Tests for Hubtel SMS Client & Celery Dispatch (Task C.4 / Feature G5).

Verifies:
1. MockHubtelSMSClient deterministic dispatch, recipient phone normalization, and history tracking.
2. Simulated network failure and invalid phone rejection via SMSGatewayException.
3. HubtelSMSClient connection pooling and payload structure against Hubtel API endpoint.
4. Factory function get_sms_client resolution based on settings.
5. Asynchronous Celery task send_sms_notification_task execution.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.services.sms import (
    HubtelSMSClient,
    MockHubtelSMSClient,
    SMSGatewayException,
    get_sms_client,
)
from apps.core.tasks import send_sms_notification_task


class TestHubtelSMSClient(TestCase):
    """Test suite for Hubtel SMS client service and Celery notification dispatch."""

    def setUp(self) -> None:
        MockHubtelSMSClient.clear()

    def test_mock_sms_client_successful_dispatch(self) -> None:
        """Verifies deterministic in-memory SMS dispatch and record tracking."""
        client = MockHubtelSMSClient()
        result = client.send_sms(
            recipient_phone="+233 24 123 4567",
            message="Your invoice #INV-2026-0001 for GHS 1,500.00 is ready.",
            sender_id="MageBooks",
            reference="REF-INV-001",
        )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["recipient_phone"], "+233241234567")
        self.assertEqual(result["sender_id"], "MageBooks")
        self.assertEqual(result["reference"], "REF-INV-001")
        self.assertTrue(result["message_id"].startswith("MOCK_SMS_"))

        # Verify history snapshot
        history = MockHubtelSMSClient.get_sent_messages()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["recipient_phone"], "+233241234567")

    def test_mock_sms_client_simulated_network_error(self) -> None:
        """Verifies simulated network error raises SMSGatewayException."""
        client = MockHubtelSMSClient(simulate_network_error=True)
        with self.assertRaises(SMSGatewayException) as ctx:
            client.send_sms(
                recipient_phone="+233241234567",
                message="Test timeout",
            )
        self.assertIn("timeout", str(ctx.exception))

    def test_mock_sms_client_rejected_number(self) -> None:
        """Verifies blacklisted/invalid numbers are rejected with SMSGatewayException."""
        client = MockHubtelSMSClient()
        with self.assertRaises(SMSGatewayException) as ctx:
            client.send_sms(
                recipient_phone="0000000000",
                message="Test rejection",
            )
        self.assertIn("invalid", str(ctx.exception).lower())

    @override_settings(USE_MOCK_SMS=True)
    def test_factory_returns_mock_client(self) -> None:
        """Verifies get_sms_client returns MockHubtelSMSClient when USE_MOCK_SMS is True."""
        client = get_sms_client()
        self.assertIsInstance(client, MockHubtelSMSClient)

    @override_settings(USE_MOCK_SMS=False)
    def test_factory_returns_production_client(self) -> None:
        """Verifies get_sms_client returns HubtelSMSClient when USE_MOCK_SMS is False."""
        client = get_sms_client()
        self.assertIsInstance(client, HubtelSMSClient)

    def test_production_client_payload_and_headers(self) -> None:
        """Verifies HubtelSMSClient constructs valid payload and basic auth for Hubtel API."""
        client = HubtelSMSClient(
            client_id="test_client_id",
            client_secret="test_client_secret",
        )

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "MessageId": "HUBTEL_MSG_998877",
            "Status": 0,
            "ClientReference": "INV-REF-99",
        }

        with patch.object(client._get_client(), "post", return_value=mock_response) as mock_post:
            result = client.send_sms(
                recipient_phone="0241234567",
                message="Invoice paid successfully.",
                sender_id="CustomOrg",
                reference="INV-REF-99",
            )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["message_id"], "HUBTEL_MSG_998877")
        self.assertEqual(result["recipient_phone"], "0241234567")

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["From"], "CustomOrg")
        self.assertEqual(payload["To"], "0241234567")
        self.assertEqual(payload["Content"], "Invoice paid successfully.")
        self.assertEqual(payload["ClientReference"], "INV-REF-99")
        self.assertTrue(payload["RegisteredDelivery"])

        client.close()

    def test_production_client_gateway_error(self) -> None:
        """Verifies HTTP non-200 responses from Hubtel raise SMSGatewayException."""
        client = HubtelSMSClient(client_id="cid", client_secret="csec")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"message": "Unauthorized"}'

        with patch.object(client._get_client(), "post", return_value=mock_response):
            with self.assertRaises(SMSGatewayException) as ctx:
                client.send_sms(
                    recipient_phone="+233240001111",
                    message="Test message",
                )
        self.assertIn("401", str(ctx.exception))
        client.close()

    def test_celery_task_send_sms_notification(self) -> None:
        """Verifies asynchronous Celery task executes successfully in eager test mode."""
        result = send_sms_notification_task(
            recipient_phone="+233249998888",
            message="Your payment was received. Thank you!",
            sender_id="MageBooks",
            reference="TXN-PAY-0042",
        )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["recipient_phone"], "+233249998888")
        self.assertEqual(result["reference"], "TXN-PAY-0042")
        self.assertIsNotNone(result["message_id"])

        # Confirm message recorded in mock adapter
        messages = MockHubtelSMSClient.get_sent_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["recipient_phone"], "+233249998888")
