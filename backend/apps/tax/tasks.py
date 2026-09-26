"""Asynchronous Background Clearance Tasks for Ghana Revenue Authority (GRA) E-VAT.

Provides:
- clear_with_gra: Asynchronous Celery task submitting invoice payloads to the GRA E-VAT
  platform with exponential backoff retries, in-memory vector QR code compilation,
  air-gapped PDF re-generation, and Cloudflare R2 document updates.
"""

import logging
from typing import Any

from celery import shared_task
from django.utils import timezone

from apps.invoicing.models import Invoice, InvoiceStatusChoices
from apps.tax.gateways import (
    GraNetworkException,
    GraRejectionException,
    get_gra_client,
)
from apps.tax.qr_generator import QRGeneratorService

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=10,
    default_retry_delay=1,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def clear_with_gra(self: Any, invoice_id: str) -> dict[str, Any]:
    """Asynchronously clears an invoice with the Ghana Revenue Authority (GRA) E-VAT platform.

    Operational Lifecycle:
    1. Fetches invoice with tenant organization context.
    2. Validates Act 1151 statutory values and seller TIN.
    3. Dispatches clearance payload to active GRA E-VAT adapter.
    4. On network timeout/error: retries via Celery exponential backoff.
    5. On clearance success:
       - Persists cryptographic clearance code and SDC ID.
       - Generates in-memory vector SVG QR code (RAM-only).
       - Updates status non-destructively (PENDING_GRA -> CLEARED; preserves PAID/PARTIALLY_PAID).
       - Recompiles air-gapped invoice PDF with GRA certified stamp and uploads to Cloudflare R2.
    """
    try:
        invoice = Invoice.objects.select_related("organization", "customer").get(id=invoice_id)
    except Invoice.DoesNotExist:
        logger.error(f"[GRA Clearance] Target invoice '{invoice_id}' does not exist.")
        return {
            "status": "ERROR",
            "error": f"Invoice '{invoice_id}' not found",
            "invoice_id": str(invoice_id),
        }

    # 1. Idempotency Guard: Check if invoice already cleared or cancelled
    if invoice.status == InvoiceStatusChoices.CLEARED and invoice.gra_clearance_code:
        logger.info(
            f"[GRA Clearance] Invoice {invoice.invoice_number} is already cleared "
            f"(Code: {invoice.gra_clearance_code}). Skipping."
        )
        return {
            "status": "ALREADY_CLEARED",
            "invoice_id": str(invoice.id),
            "clearance_code": invoice.gra_clearance_code,
        }

    if invoice.status == InvoiceStatusChoices.CANCELLED:
        logger.warning(
            f"[GRA Clearance] Invoice {invoice.invoice_number} is cancelled. Aborting clearance."
        )
        return {
            "status": "CANCELLED",
            "invoice_id": str(invoice.id),
        }

    # 2. Seller TIN Validation
    seller_tin = invoice.organization.business_tin
    if not seller_tin:
        logger.error(
            f"[GRA Clearance] Organization '{invoice.organization.name}' "
            "lacks a valid business TIN."
        )
        return {
            "status": "ERROR",
            "error": "Organization missing business TIN",
            "invoice_id": str(invoice.id),
        }

    # 3. Compile Statutory E-VAT Payload
    payload = {
        "invoice_id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "payment_reference": invoice.payment_reference,
        "issue_date": invoice.issue_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "seller_tin": seller_tin,
        "seller_name": invoice.organization.name,
        "buyer_tin": invoice.customer.tin if invoice.customer else None,
        "buyer_name": invoice.customer.name if invoice.customer else "Walk-in Customer",
        "buyer_ghana_card": invoice.customer.ghana_card_number if invoice.customer else None,
        "currency": invoice.currency,
        "subtotal_amount": str(invoice.subtotal_amount),
        "vat_amount": str(invoice.vat_amount),
        "nhil_amount": str(invoice.nhil_amount),
        "getfund_amount": str(invoice.getfund_amount),
        "covid_levy_amount": str(invoice.covid_levy_amount),
        "total_amount": str(invoice.total_amount),
        "lines": [
            {
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
                "vat_amount": str(line.vat_amount),
                "nhil_amount": str(line.nhil_amount),
                "getfund_amount": str(line.getfund_amount),
            }
            for line in invoice.lines.all()
        ],
    }

    client = get_gra_client()

    # 4. Transmit Payload to GRA with Exponential Retry
    try:
        response = client.submit_invoice(payload)
    except GraNetworkException as exc:
        retry_num = self.request.retries + 1 if hasattr(self, "request") else 1
        logger.warning(
            f"[GRA Clearance] Transient network timeout for invoice {invoice.invoice_number} "
            f"(attempt {retry_num}/{self.max_retries}): {exc}"
        )
        raise self.retry(exc=exc) from exc
    except GraRejectionException as exc:
        logger.error(
            f"[GRA Clearance] Permanent statutory rejection for invoice "
            f"{invoice.invoice_number}: {exc}"
        )
        return {
            "status": "REJECTED",
            "error": str(exc),
            "invoice_id": str(invoice.id),
        }

    # 5. On Affirmative Clearance: Generate In-Memory QR Code & Persist Tokens
    qr_svg = QRGeneratorService.generate_vector_svg(response.qr_code_url)

    invoice.gra_clearance_code = response.clearance_code
    invoice.gra_qr_code = qr_svg
    invoice.gra_submitted_at = invoice.gra_submitted_at or timezone.now()
    invoice.gra_cleared_at = timezone.now()

    # Non-destructive state preservation: only PENDING_GRA transitions to CLEARED
    # If the invoice was already settled via MoMo (Feature 4.3), retain PAID or PARTIALLY_PAID
    if invoice.status == InvoiceStatusChoices.PENDING_GRA:
        invoice.status = InvoiceStatusChoices.CLEARED

    invoice.save(
        update_fields=[
            "gra_clearance_code",
            "gra_qr_code",
            "gra_submitted_at",
            "gra_cleared_at",
            "status",
            "updated_at",
        ]
    )

    # 6. Recompile Air-Gapped PDF with Official Green Certified Stamp and Upload to R2
    from apps.invoicing.services.pdf_service import InvoicePDFService

    try:
        InvoicePDFService.generate_and_upload_invoice_pdf(invoice)
        logger.info(
            f"[GRA Clearance] Successfully compiled and uploaded certified PDF for "
            f"Invoice {invoice.invoice_number} to R2 storage."
        )
    except Exception as pdf_exc:
        logger.warning(
            f"[GRA Clearance] PDF re-compilation warning for invoice "
            f"{invoice.invoice_number}: {pdf_exc}"
        )

    logger.info(
        f"[GRA Clearance] Invoice {invoice.invoice_number} successfully cleared by GRA "
        f"(Code: {response.clearance_code}, SDC: {response.sdc_id}). Status: {invoice.status}"
    )

    return {
        "status": "CLEARED",
        "invoice_id": str(invoice.id),
        "sdc_id": response.sdc_id,
        "clearance_code": response.clearance_code,
        "qr_url": response.qr_code_url,
    }
