"""Invoicing REST API Views.

Provides:
1. InvoiceListCreateAPIView: GET paginated list, POST atomic creation with Act 1151 GL posting.
2. InvoiceDetailAPIView: GET invoice detail with customer legal snapshot and lines.
3. InvoiceIssueAPIView: POST transition draft invoice to PENDING_GRA with GL posting.
"""

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.http import HttpResponse
from rest_framework import filters, generics, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.invoicing.models import Contact, CreditNote, Invoice
from apps.invoicing.serializers import (
    ContactSerializer,
    CreditNoteCreateSerializer,
    CreditNoteSerializer,
    InvoiceCreateSerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    PublicInvoiceSerializer,
)
from apps.invoicing.services import InvoicingService
from apps.invoicing.services.credit_note_service import CreditNoteService
from apps.invoicing.services.pdf_service import InvoicePDFService
from apps.tenancy.middleware import get_current_tenant
from apps.tenancy.models import Organization
from apps.tenancy.permissions import CanCreateInvoice, CanIssueRefund, IsAuditorReadOnly


def resolve_request_tenant(request: Request) -> Organization | None:
    """Helper to extract active tenant organization from request or thread context."""
    tenant = getattr(request, "tenant", None)
    if not tenant:
        tenant = getattr(request, "organization", None)
    if not tenant:
        tenant = get_current_tenant()
    return tenant


class InvoiceListCreateAPIView(APIView):
    """List tenant invoices or compile and issue a new tax invoice."""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly, CanCreateInvoice]

    def get(self, request: Request) -> Response:
        """Retrieves tenant-scoped list of invoices with optional filtering."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = (
            Invoice.objects.filter(organization=tenant)
            .select_related("customer")
            .order_by("-issue_date", "-created_at")
        )

        # Filters
        invoice_status = request.query_params.get("status")
        if invoice_status:
            queryset = queryset.filter(status=invoice_status)

        customer_id = request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        search_query = request.query_params.get("search")
        if search_query:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(invoice_number__icontains=search_query)
                | Q(payment_reference__icontains=search_query)
                | Q(customer_name__icontains=search_query)
            )

        serializer = InvoiceListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        """Compiles, calculates Act 1151 taxes, freezes legal snapshot, and posts invoice to GL."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = InvoiceCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            invoice = InvoicingService.create_and_post_invoice(
                organization=tenant,
                user=request.user,
                data=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages}
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        output_serializer = InvoiceDetailSerializer(invoice)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class InvoiceDetailAPIView(APIView):
    """Retrieve complete invoice detail including line items and customer snapshot."""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request, pk: Any) -> Response:
        """Retrieves single invoice instance by UUID."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = (
            Invoice.objects.filter(id=pk, organization=tenant)
            .select_related("customer")
            .prefetch_related("lines__account")
            .first()
        )
        if not invoice:
            return Response(
                {"detail": "Invoice not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvoiceIssueAPIView(APIView):
    """Transitions a draft invoice to PENDING_GRA and posts balanced lines to General Ledger."""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def post(self, request: Request, pk: Any) -> Response:
        """Issues an existing draft invoice."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = Invoice.objects.filter(id=pk, organization=tenant).first()
        if not invoice:
            return Response(
                {"detail": "Invoice not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            issued_invoice = InvoicingService.issue_draft_invoice(
                invoice=invoice,
                user=request.user,
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages}
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        serializer = InvoiceDetailSerializer(issued_invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvoiceDownloadAPIView(APIView):
    """Retrieves a presigned download URL or streams raw binary PDF for an invoice."""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request, pk: Any) -> Response | HttpResponse:
        """Generates 15-minute presigned download URL or streams binary PDF."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = (
            Invoice.objects.filter(id=pk, organization=tenant)
            .select_related("customer", "organization")
            .prefetch_related("lines")
            .first()
        )
        if not invoice:
            return Response(
                {"detail": "Invoice not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Binary stream option for programmatic downloads / PDF viewers
        if request.query_params.get("stream", "").lower() == "true":
            pdf_bytes = InvoicePDFService.get_invoice_pdf_raw_bytes(invoice)
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{invoice.invoice_number}.pdf"'
            return response

        # Default: 15-minute presigned download URL
        download_url = InvoicePDFService.get_invoice_pdf_download_url(invoice, expires_in=900)
        return Response(
            {
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "download_url": download_url,
                "expires_in": 900,
            },
            status=status.HTTP_200_OK,
        )


class InvoiceGeneratePDFAPIView(APIView):
    """Explicitly triggers compilation and upload of the invoice PDF to R2."""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def post(self, request: Request, pk: Any) -> Response:
        """Compiles invoice PDF, uploads to R2, updates pdf_url, and returns download DTO."""
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = (
            Invoice.objects.filter(id=pk, organization=tenant)
            .select_related("customer", "organization")
            .prefetch_related("lines")
            .first()
        )
        if not invoice:
            return Response(
                {"detail": "Invoice not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        download_url, storage_key = InvoicePDFService.generate_and_upload_invoice_pdf(invoice)
        return Response(
            {
                "detail": "Invoice PDF compiled and uploaded successfully.",
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "storage_key": storage_key,
                "download_url": download_url,
                "expires_in": 900,
            },
            status=status.HTTP_200_OK,
        )


class ContactViewSet(viewsets.ModelViewSet):
    """CRUD ViewSet for tenant-scoped Contacts (Customers and Suppliers).

    Endpoints:
    - GET /api/v1/contacts/: List tenant contacts with optional ?contact_type= & ?search=
    - POST /api/v1/contacts/: Create a new contact bound to active tenant
    - GET /api/v1/contacts/<uuid:pk>/: Retrieve single contact
    - PUT/PATCH /api/v1/contacts/<uuid:pk>/: Update contact details
    - DELETE /api/v1/contacts/<uuid:pk>/: Delete contact (protected if invoices exist)
    """

    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated, IsAuditorReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "phone", "email", "tin"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        tenant = resolve_request_tenant(self.request)
        if not tenant:
            return Contact.objects.none()
        qs = Contact.objects.filter(organization=tenant)

        contact_type = self.request.query_params.get("contact_type")
        if contact_type:
            qs = qs.filter(contact_type=contact_type.upper())

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            if is_active.lower() in ("true", "1"):
                qs = qs.filter(is_active=True)
            elif is_active.lower() in ("false", "0"):
                qs = qs.filter(is_active=False)

        return qs

    def perform_create(self, serializer: ContactSerializer) -> None:
        tenant = resolve_request_tenant(self.request)
        if not tenant:
            raise ValidationError({"detail": "Active tenant organization context required."})

        name = serializer.validated_data.get("name")
        if name and Contact.objects.filter(organization=tenant, name__iexact=name).exists():
            raise ValidationError(
                {"name": ["A contact with this name already exists in this organization."]}
            )

        serializer.save(organization=tenant)

    def perform_update(self, serializer: ContactSerializer) -> None:
        tenant = resolve_request_tenant(self.request)
        name = serializer.validated_data.get("name")
        if name and tenant:
            duplicate = (
                Contact.objects.filter(organization=tenant, name__iexact=name)
                .exclude(pk=serializer.instance.pk)
                .exists()
            )
            if duplicate:
                raise ValidationError(
                    {"name": ["A contact with this name already exists in this organization."]}
                )

        serializer.save()

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            return super().destroy(request, *args, **kwargs)
        except models.ProtectedError:
            return Response(
                {"detail": "Cannot delete contact with existing associated invoices."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PublicInvoiceView(generics.RetrieveAPIView):
    """Anonymous public invoice viewer.

    Permits public access to an invoice using its high-entropy UUIDv4 share_token.
    Strips internal GL account IDs, tenant ledger mappings, and auditor metadata.
    Exempted from tenant header requirements in TenantSecurityMiddleware.
    """

    permission_classes = [AllowAny]
    serializer_class = PublicInvoiceSerializer
    lookup_field = "share_token"

    def get_queryset(self):
        return Invoice.objects.all().select_related("organization").prefetch_related("lines")


class CreditNoteListCreateAPIView(APIView):
    """List or issue statutory Ghanaian Credit Notes (Act 1151).

    Enforces:
    - Segregation of Duties: CanIssueRefund (Owner, Admin, Accountant).
    - Auditor Read-Only: IsAuditorReadOnly.
    - Double-refund pessimistic locking on original invoice.
    """

    permission_classes = [IsAuthenticated, IsAuditorReadOnly, CanIssueRefund]

    def get(self, request: Request) -> Response:
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = (
            CreditNote.objects.filter(organization=tenant)
            .select_related("invoice", "customer")
            .prefetch_related("lines")
            .order_by("-issue_date", "-created_at")
        )
        invoice_id = request.query_params.get("invoice_id")
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)

        serializer = CreditNoteSerializer(queryset[:100], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CreditNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        try:
            credit_note, _ = CreditNoteService.issue_credit_note(
                organization=tenant,
                invoice_id=str(validated_data["invoice_id"]),
                lines_data=validated_data["lines"],
                reason=validated_data["reason"],
                user=request.user,
                issue_date=validated_data.get("issue_date"),
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except (ValidationError, DjangoValidationError) as exc:
            msg = exc.message if hasattr(exc, "message") else str(exc)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            CreditNoteSerializer(credit_note).data,
            status=status.HTTP_201_CREATED,
        )


class CreditNoteDetailAPIView(APIView):
    """Retrieve detailed credit note record with itemized lines and legal snapshot."""

    permission_classes = [IsAuthenticated, IsAuditorReadOnly]

    def get(self, request: Request, pk: str) -> Response:
        tenant = resolve_request_tenant(request)
        if not tenant:
            return Response(
                {"detail": "No active tenant organization context found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        credit_note = (
            CreditNote.objects.filter(organization=tenant, id=pk)
            .select_related("invoice", "customer")
            .prefetch_related("lines")
            .first()
        )
        if not credit_note:
            return Response(
                {"detail": f"Credit note '{pk}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CreditNoteSerializer(credit_note)
        return Response(serializer.data, status=status.HTTP_200_OK)
