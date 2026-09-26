"""PBC (Provided By Client) Audit Package Compiler Service.

Compiles an in-memory ZIP archive containing all required statutory and forensic audit workpapers:
1. 01_General_Ledger.csv: Chronological journal lines with debit/credit details.
2. 02_Trial_Balance.csv: Balanced trial balance snapshot (is_balanced: True).
3. 03_Chart_of_Accounts.csv: Master general ledger classifications (1000-5999).
4. 04_GRA_Act1151_VAT_Summary.csv: Act 1151 tax return schedules (15% VAT, 2.5% NHIL, 2.5% GETFund).
5. invoices/<invoice_number>.pdf: Official certified invoice PDF documents.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import io
import logging
import zipfile
from dataclasses import dataclass, field
from typing import Any

from django.utils import timezone

from apps.core.services.storage import get_storage_service
from apps.invoicing.models import Invoice, InvoiceStatusChoices
from apps.invoicing.services.pdf_compiler import AirGappedPDFCompiler
from apps.invoicing.services.pdf_service import InvoicePDFService
from apps.ledger.models import ChartOfAccounts, JournalLine
from apps.ledger.selectors import get_trial_balance
from apps.tenancy.models import Organization

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PBCCompilationResult:
    """Immutable result DTO representing a compiled PBC audit package archive."""

    archive_bytes: bytes
    filename: str
    sha256_hash: str
    file_count: int
    invoice_count: int
    fiscal_year: int
    organization_id: str
    created_at: datetime.datetime
    file_manifest: list[str] = field(default_factory=list)


class PBCPackageCompiler:
    """In-memory streaming compiler for statutory PBC audit packages."""

    @classmethod
    def compile_package(
        cls,
        organization: Organization,
        fiscal_year: int,
    ) -> PBCCompilationResult:
        """Compiles a complete PBC audit package for the given organization and fiscal year."""
        logger.info(
            "Starting PBC audit package compilation: org=%s (%s), fiscal_year=%d",
            organization.name,
            organization.id,
            fiscal_year,
        )

        zip_buffer = io.BytesIO()
        manifest: list[str] = []
        invoice_count = 0

        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            # 1. 01_General_Ledger.csv
            gl_csv = cls._generate_general_ledger_csv(organization, fiscal_year)
            zip_file.writestr("01_General_Ledger.csv", gl_csv.encode("utf-8"))
            manifest.append("01_General_Ledger.csv")

            # 2. 02_Trial_Balance.csv
            tb_csv = cls._generate_trial_balance_csv(organization, fiscal_year)
            zip_file.writestr("02_Trial_Balance.csv", tb_csv.encode("utf-8"))
            manifest.append("02_Trial_Balance.csv")

            # 3. 03_Chart_of_Accounts.csv
            coa_csv = cls._generate_chart_of_accounts_csv(organization)
            zip_file.writestr("03_Chart_of_Accounts.csv", coa_csv.encode("utf-8"))
            manifest.append("03_Chart_of_Accounts.csv")

            # 4. 04_GRA_Act1151_VAT_Summary.csv
            vat_csv = cls._generate_act1151_tax_summary_csv(organization, fiscal_year)
            zip_file.writestr("04_GRA_Act1151_VAT_Summary.csv", vat_csv.encode("utf-8"))
            manifest.append("04_GRA_Act1151_VAT_Summary.csv")

            # 5. invoices/*.pdf
            invoices = (
                Invoice.objects.filter(
                    organization=organization,
                    issue_date__year=fiscal_year,
                )
                .exclude(status__in=[InvoiceStatusChoices.DRAFT, InvoiceStatusChoices.CANCELLED])
                .order_by("invoice_number")
            )

            storage = get_storage_service()

            for invoice in invoices:
                try:
                    pdf_bytes = cls._get_invoice_pdf_bytes(invoice, storage)
                    clean_number = invoice.invoice_number.replace("/", "-").replace("\\", "-")
                    pdf_filename = f"invoices/{clean_number}.pdf"
                    zip_file.writestr(pdf_filename, pdf_bytes)
                    manifest.append(pdf_filename)
                    invoice_count += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to bundle invoice PDF into PBC package: invoice=%s err=%s",
                        invoice.invoice_number,
                        exc,
                    )

        zip_bytes = zip_buffer.getvalue()
        sha256_hash = hashlib.sha256(zip_bytes).hexdigest()
        org_prefix = str(organization.id)[:8]
        filename = f"pbc_{fiscal_year}_{org_prefix}.zip"

        logger.info(
            "PBC compilation complete: org=%s, size=%d bytes, files=%d, sha256=%s",
            organization.id,
            len(zip_bytes),
            len(manifest),
            sha256_hash,
        )

        return PBCCompilationResult(
            archive_bytes=zip_bytes,
            filename=filename,
            sha256_hash=sha256_hash,
            file_count=len(manifest),
            invoice_count=invoice_count,
            fiscal_year=fiscal_year,
            organization_id=str(organization.id),
            created_at=timezone.now(),
            file_manifest=manifest,
        )

    @classmethod
    def _generate_general_ledger_csv(
        cls,
        organization: Organization,
        fiscal_year: int,
    ) -> str:
        """Streams general ledger journal lines for the fiscal year to CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "Date",
                "Entry Number",
                "Source Type",
                "Narration",
                "Account Code",
                "Account Name",
                "Line Description",
                "Debit (GHS)",
                "Credit (GHS)",
            ]
        )

        lines = (
            JournalLine.objects.filter(
                journal_entry__organization=organization,
                journal_entry__is_posted=True,
                journal_entry__entry_date__year=fiscal_year,
            )
            .select_related("journal_entry", "account")
            .order_by(
                "journal_entry__entry_date",
                "journal_entry__entry_number",
                "id",
            )
        )

        for line in lines:
            writer.writerow(
                [
                    line.journal_entry.entry_date.isoformat(),
                    line.journal_entry.entry_number,
                    line.journal_entry.source_type,
                    line.journal_entry.narration,
                    line.account.account_code,
                    line.account.account_name,
                    line.description,
                    str(line.debit_amount),
                    str(line.credit_amount),
                ]
            )

        return output.getvalue()

    @classmethod
    def _generate_trial_balance_csv(
        cls,
        organization: Organization,
        fiscal_year: int,
    ) -> str:
        """Generates trial balance as of the end of the fiscal year to CSV string."""
        as_of_date = datetime.date(fiscal_year, 12, 31)
        tb_report = get_trial_balance(
            organization=organization,
            as_of_date=as_of_date,
            include_zero_balances=False,
        )

        output = io.StringIO()
        writer = csv.writer(output)
        for row in tb_report.to_csv_rows():
            writer.writerow(row)

        return output.getvalue()

    @classmethod
    def _generate_chart_of_accounts_csv(
        cls,
        organization: Organization,
    ) -> str:
        """Generates master chart of accounts to CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "Account Code",
                "Account Name",
                "Category",
                "Category Code",
                "Simple Label",
                "Normal Balance",
                "Is Active",
            ]
        )

        accounts = (
            ChartOfAccounts.objects.filter(organization=organization)
            .select_related("category")
            .order_by("account_code")
        )

        for acc in accounts:
            writer.writerow(
                [
                    acc.account_code,
                    acc.account_name,
                    acc.category.name,
                    acc.category.code,
                    acc.simple_label,
                    acc.normal_balance,
                    str(acc.is_active),
                ]
            )

        return output.getvalue()

    @classmethod
    def _generate_act1151_tax_summary_csv(
        cls,
        organization: Organization,
        fiscal_year: int,
    ) -> str:
        """Generates statutory Act 1151 VAT schedule to CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "Invoice Number",
                "Issue Date",
                "Customer Name",
                "Customer TIN",
                "Currency",
                "Subtotal (Taxable)",
                "VAT 15%",
                "NHIL 2.5%",
                "GETFund 2.5%",
                "Total Amount",
                "Status",
                "GRA Clearance Code",
            ]
        )

        invoices = (
            Invoice.objects.filter(
                organization=organization,
                issue_date__year=fiscal_year,
            )
            .exclude(status=InvoiceStatusChoices.DRAFT)
            .order_by("issue_date", "invoice_number")
        )

        for inv in invoices:
            writer.writerow(
                [
                    inv.invoice_number,
                    inv.issue_date.isoformat(),
                    inv.customer_name,
                    inv.customer_tin or "",
                    inv.currency,
                    str(inv.subtotal_amount),
                    str(inv.vat_amount),
                    str(inv.nhil_amount),
                    str(inv.getfund_amount),
                    str(inv.total_amount),
                    inv.status,
                    inv.gra_clearance_code or "",
                ]
            )

        return output.getvalue()

    @classmethod
    def _get_invoice_pdf_bytes(
        cls,
        invoice: Invoice,
        storage: Any,
    ) -> bytes:
        """Retrieves invoice PDF from storage, falling back to on-demand compilation."""
        storage_key = InvoicePDFService.get_storage_key(invoice)
        if storage.file_exists(storage_key):
            return storage.get_file_bytes(storage_key)

        return AirGappedPDFCompiler.compile_invoice_pdf(invoice)
