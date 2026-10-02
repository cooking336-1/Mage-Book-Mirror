"""Hubtel SMS Client Service and Deterministic Mock Adapter.

Provides:
1. BaseSMSClient: Abstract contract for outbound telecom SMS notifications.
2. MockHubtelSMSClient: Deterministic in-memory SMS adapter for offline testing.
3. HubtelSMSClient: Production HTTP adapter with httpx connection pooling.
4. get_sms_client: Factory function resolving active adapter based on settings.
"""

import logging
import threading
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class SMSGatewayException(Exception):
    """Raised when an outbound SMS transmission fails due to network or aggregator rejection."""

    pass


class BaseSMSClient(ABC):
    """Abstract contract for multi-tenant SMS notification dispatch."""

    @abstractmethod
    def send_sms(
        self,
        recipient_phone: str,
        message: str,
        sender_id: str | None = None,
        reference: str | None = None,
    ) -> dict[str, Any]:
        """Dispatches an outbound SMS message to a mobile subscriber.

        Args:
            recipient_phone: Destination phone number (MSISDN e.g. +233240000000 or 0240000000).
            message: Text content of the SMS message.
            sender_id: Alphanumeric sender ID (maximum 11 characters).
            reference: Tenant-scoped unique client reference for tracking/reconciliation.

        Returns:
            dict containing message_id, status ("SUCCESS" | "FAILED"), and delivery metadata.

        Raises:
            SMSGatewayException: If the gateway rejects the transmission.
        """
        pass


class MockHubtelSMSClient(BaseSMSClient):
    """Deterministic in-memory mock adapter for automated testing and local execution.

    Maintains thread-safe delivery history without making live telecom HTTP calls.
    """

    _sent_messages: list[dict[str, Any]] = []
    _lock = threading.Lock()

    def __init__(
        self,
        simulate_network_error: bool = False,
        fail_numbers: set[str] | None = None,
    ) -> None:
        self.simulate_network_error = simulate_network_error
        self.fail_numbers = fail_numbers or {"0000000000", "+233000000000"}

    @classmethod
    def clear(cls) -> None:
        """Clears all in-memory sent SMS records (used between test runs)."""
        with cls._lock:
            cls._sent_messages.clear()

    @classmethod
    def get_sent_messages(cls) -> list[dict[str, Any]]:
        """Returns a snapshot copy of all sent SMS messages."""
        with cls._lock:
            return list(cls._sent_messages)

    def send_sms(
        self,
        recipient_phone: str,
        message: str,
        sender_id: str | None = None,
        reference: str | None = None,
    ) -> dict[str, Any]:
        if self.simulate_network_error:
            logger.warning(
                "[MockHubtelSMSClient] Simulated network timeout for %s", recipient_phone
            )
            raise SMSGatewayException("Simulated Hubtel SMS connection timeout / network error.")

        cleaned_phone = recipient_phone.strip().replace(" ", "").replace("-", "")
        if cleaned_phone in self.fail_numbers:
            logger.warning(
                "[MockHubtelSMSClient] Rejected delivery for invalid phone %s", cleaned_phone
            )
            raise SMSGatewayException(
                f"Hubtel delivery rejected for invalid MSISDN: {cleaned_phone}"
            )

        effective_sender = sender_id or getattr(settings, "HUBTEL_SMS_SENDER_ID", "MageBooks")
        message_id = f"MOCK_SMS_{uuid4().hex[:12].upper()}"

        record = {
            "status": "SUCCESS",
            "message_id": message_id,
            "recipient_phone": cleaned_phone,
            "sender_id": effective_sender,
            "message": message,
            "reference": reference or f"REF_{uuid4().hex[:8].upper()}",
            "rate": 0.035,
            "currency": "GHS",
        }

        with self._lock:
            self._sent_messages.append(record)

        logger.info(
            "[MockHubtelSMSClient] SMS Sent to %s via [%s]: '%s' [ID: %s, Ref: %s]",
            cleaned_phone,
            effective_sender,
            message[:40] + ("..." if len(message) > 40 else ""),
            message_id,
            record["reference"],
        )
        return record


class HubtelSMSClient(BaseSMSClient):
    """Production Hubtel SMS Client with persistent connection pooling and basic authentication."""

    BASE_URL = "https://smsc.hubtel.com/v1/messages/send"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.client_id = client_id or getattr(settings, "HUBTEL_SMS_CLIENT_ID", "")
        self.client_secret = client_secret or getattr(settings, "HUBTEL_SMS_CLIENT_SECRET", "")
        self.timeout = timeout
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Lazy initializer for connection-pooled HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self.timeout),
                auth=(self.client_id, self.client_secret),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def send_sms(
        self,
        recipient_phone: str,
        message: str,
        sender_id: str | None = None,
        reference: str | None = None,
    ) -> dict[str, Any]:
        cleaned_phone = recipient_phone.strip().replace(" ", "").replace("-", "")
        effective_sender = sender_id or getattr(settings, "HUBTEL_SMS_SENDER_ID", "MageBooks")

        payload: dict[str, Any] = {
            "From": effective_sender[:11],
            "To": cleaned_phone,
            "Content": message,
            "RegisteredDelivery": True,
        }
        if reference:
            payload["ClientReference"] = reference

        client = self._get_client()
        try:
            response = client.post(self.BASE_URL, json=payload)
        except httpx.RequestError as exc:
            logger.error("[HubtelSMSClient] Network exception during SMS dispatch: %s", exc)
            raise SMSGatewayException(f"Hubtel SMS transport error: {exc}") from exc

        if response.status_code not in (200, 201):
            logger.error(
                "[HubtelSMSClient] Gateway rejected message to %s (HTTP %d): %s",
                cleaned_phone,
                response.status_code,
                response.text,
            )
            raise SMSGatewayException(
                f"Hubtel SMS API error HTTP {response.status_code}: {response.text}"
            )

        data = response.json()
        message_id = data.get("MessageId") or data.get("messageId") or str(uuid4())

        return {
            "status": "SUCCESS",
            "message_id": message_id,
            "recipient_phone": cleaned_phone,
            "sender_id": effective_sender,
            "reference": reference or data.get("ClientReference", ""),
            "raw_response": data,
        }

    def close(self) -> None:
        """Closes the underlying HTTP connection pool."""
        if self._client is not None and not self._client.is_closed:
            self._client.close()


def get_sms_client() -> BaseSMSClient:
    """Factory resolver returning active SMS client adapter."""
    if getattr(settings, "USE_MOCK_SMS", True):
        return MockHubtelSMSClient()
    return HubtelSMSClient()
