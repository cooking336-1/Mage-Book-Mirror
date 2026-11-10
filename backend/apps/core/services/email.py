"""Transactional Email Service for Mage Books SAAS (Brevo API).

Adheres to:
1. KISS & YAGNI: Zero third-party SDK dependencies; standard library urllib.request only.
2. Fast Deterministic Testing: Suppresses outbound HTTP calls during automated tests.
3. Resilient Error Handling: Captures HTTPError, logs details without crashing parent request.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


def send_transactional_email(
    to_email: str,
    subject: str,
    html_content: str,
    to_name: str | None = None,
) -> bool:
    """Dispatches a transactional email via Brevo's v3 SMTP API.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_content: Responsive HTML body of the email.
        to_name: Optional recipient display name.

    Returns:
        True if email was accepted by Brevo (or suppressed in test mode), False otherwise.
    """
    if getattr(settings, "IS_TESTING", False):
        logger.info("[EmailService] Test mode active: email to %s suppressed.", to_email)
        return True

    api_key = getattr(settings, "BREVO_API_KEY", "")
    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", "no-reply@magebooks.com")
    sender_name = getattr(settings, "BREVO_SENDER_NAME", "Mage Books Security")

    if not api_key:
        logger.warning("[EmailService] BREVO_API_KEY not configured. Email suppressed.")
        return False

    payload: dict[str, Any] = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            logger.info(
                "[EmailService] Email dispatched successfully to %s (HTTP %s)",
                to_email,
                resp.status,
            )
            return True
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        logger.error("[EmailService] Brevo API HTTP %s: %s", exc.code, err_body)
        return False
    except Exception as exc:
        logger.error("[EmailService] Unexpected error sending email to %s: %s", to_email, exc)
        return False
