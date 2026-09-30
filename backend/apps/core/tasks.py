"""Asynchronous Celery tasks for core platform services and notifications."""

import logging
from typing import Any

from celery import shared_task

from apps.core.services.sms import SMSGatewayException, get_sms_client

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    retry_backoff=True,
    retry_backoff_max=120,
    name="apps.core.tasks.send_sms_notification_task",
)
def send_sms_notification_task(
    self: Any,
    recipient_phone: str,
    message: str,
    sender_id: str | None = None,
    reference: str | None = None,
) -> dict[str, Any]:
    """Asynchronously dispatches an outbound SMS notification via Hubtel SMS.

    Args:
        recipient_phone: Destination MSISDN / phone number.
        message: Notification message text.
        sender_id: Optional registered alphanumeric sender ID (default: MageBooks).
        reference: Optional idempotency / tracking reference string.

    Returns:
        dict[str, Any]: Delivery status, message ID, and delivery metadata.
    """
    logger.info(
        "[SMS Worker] Dispatching SMS to %s [Ref: %s]",
        recipient_phone,
        reference,
    )
    client = get_sms_client()

    try:
        result = client.send_sms(
            recipient_phone=recipient_phone,
            message=message,
            sender_id=sender_id,
            reference=reference,
        )
        return {
            "status": "SUCCESS",
            "message_id": result.get("message_id"),
            "recipient_phone": result.get("recipient_phone"),
            "reference": result.get("reference"),
        }
    except SMSGatewayException as exc:
        logger.warning(
            "[SMS Worker] Hubtel gateway rejection for %s: %s. Retrying...",
            recipient_phone,
            exc,
        )
        raise self.retry(exc=exc) from exc
    except Exception as exc:
        logger.exception(
            "[SMS Worker] Unexpected failure delivering SMS to %s: %s",
            recipient_phone,
            exc,
        )
        raise self.retry(exc=exc) from exc
