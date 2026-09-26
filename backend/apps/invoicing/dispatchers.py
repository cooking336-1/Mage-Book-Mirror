"""Asynchronous GRA E-VAT Clearance Dispatcher.

Handles queuing invoice clearance tasks to asynchronous workers.
In Sprint 3, provides an abstract dispatch interface.
In Sprint 4 (Feature 4.4), transparently routes to Celery's clear_with_gra.delay().
"""

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def enqueue_gra_clearance(invoice_id: uuid.UUID | str) -> dict[str, Any]:
    """Enqueues an invoice for asynchronous GRA E-VAT clearance.

    Returns task metadata dictionary.
    """
    invoice_uuid_str = str(invoice_id)
    logger.info("Enqueuing invoice %s for asynchronous GRA E-VAT clearance", invoice_uuid_str)

    try:
        from apps.tax.tasks import clear_with_gra

        task = clear_with_gra.delay(invoice_uuid_str)
        return {
            "task_id": str(task.id),
            "status": "QUEUED",
            "invoice_id": invoice_uuid_str,
        }
    except Exception as exc:
        logger.error(
            f"Failed to dispatch async GRA clearance task for invoice {invoice_uuid_str}: {exc}"
        )
        return {
            "task_id": f"failed-dispatch-{invoice_uuid_str[:8]}",
            "status": "FAILED",
            "invoice_id": invoice_uuid_str,
            "error": str(exc),
        }
