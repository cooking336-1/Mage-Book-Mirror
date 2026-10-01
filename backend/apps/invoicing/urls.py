from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.invoicing.views import (
    ContactViewSet,
    CreditNoteDetailAPIView,
    CreditNoteListCreateAPIView,
    InvoiceDetailAPIView,
    InvoiceDownloadAPIView,
    InvoiceGeneratePDFAPIView,
    InvoiceIssueAPIView,
    InvoiceListCreateAPIView,
    PublicInvoiceView,
)

app_name = "invoicing"

router = DefaultRouter()
router.register(r"contacts", ContactViewSet, basename="contact")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "invoicing/public/invoices/<uuid:share_token>/",
        PublicInvoiceView.as_view(),
        name="public-invoice-detail",
    ),
    path(
        "public/invoices/<uuid:share_token>/",
        PublicInvoiceView.as_view(),
        name="public-invoice-detail-alias",
    ),
    path("invoices/", InvoiceListCreateAPIView.as_view(), name="invoice-list-create"),
    path(
        "invoicing/invoices/",
        InvoiceListCreateAPIView.as_view(),
        name="invoicing-invoice-list-create-alias",
    ),
    path("invoices/<uuid:pk>/", InvoiceDetailAPIView.as_view(), name="invoice-detail"),
    path("invoices/<uuid:pk>/issue/", InvoiceIssueAPIView.as_view(), name="invoice-issue"),
    path(
        "invoices/<uuid:pk>/download/",
        InvoiceDownloadAPIView.as_view(),
        name="invoice-download",
    ),
    path(
        "invoices/<uuid:pk>/generate-pdf/",
        InvoiceGeneratePDFAPIView.as_view(),
        name="invoice-generate-pdf",
    ),
    path(
        "credit-notes/",
        CreditNoteListCreateAPIView.as_view(),
        name="credit-note-list-create",
    ),
    path(
        "invoicing/credit-notes/",
        CreditNoteListCreateAPIView.as_view(),
        name="credit-note-list-create-alias",
    ),
    path(
        "credit-notes/<uuid:pk>/",
        CreditNoteDetailAPIView.as_view(),
        name="credit-note-detail",
    ),
    path(
        "invoicing/credit-notes/<uuid:pk>/",
        CreditNoteDetailAPIView.as_view(),
        name="credit-note-detail-alias",
    ),
]
