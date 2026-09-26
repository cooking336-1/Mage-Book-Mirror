"""Management Command to Retry Stalled PENDING_GRA Invoices.

Usage:
    uv run python manage.py retry_pending_gra [--limit 50] [--dry-run] [--org-id <UUID>]
"""

import logging
from typing import Any

from django.core.management.base import BaseCommand

from apps.invoicing.models import Invoice, InvoiceStatusChoices
from apps.tax.tasks import clear_with_gra

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Retries GRA E-VAT clearance for invoices remaining in PENDING_GRA state."""

    help = "Enqueues asynchronous GRA E-VAT clearance for invoices in PENDING_GRA state."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of pending invoices to re-queue (default: 100).",
        )
        parser.add_argument(
            "--org-id",
            type=str,
            default=None,
            help="Filter by specific tenant organization UUID.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report pending invoices without re-enqueuing tasks.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        limit = options["limit"]
        org_id = options["org_id"]
        dry_run = options["dry_run"]

        qs = Invoice.objects.filter(status=InvoiceStatusChoices.PENDING_GRA).order_by("created_at")

        if org_id:
            qs = qs.filter(organization_id=org_id)

        invoices = list(qs[:limit])
        count = len(invoices)

        self.stdout.write(
            self.style.NOTICE(f"Found {count} invoice(s) pending GRA clearance (limit={limit}).")
        )

        if dry_run:
            for inv in invoices:
                self.stdout.write(f"[DRY-RUN] Would re-queue: {inv.invoice_number} ({inv.id})")
            return

        requeued = 0
        for inv in invoices:
            try:
                clear_with_gra.delay(str(inv.id))
                requeued += 1
                self.stdout.write(self.style.SUCCESS(f"Re-queued: {inv.invoice_number} ({inv.id})"))
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(f"Failed to re-queue {inv.invoice_number}: {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully re-queued {requeued}/{count} pending invoice(s) for GRA clearance."
            )
        )
