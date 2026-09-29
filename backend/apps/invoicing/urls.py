from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.invoicing.views import (
    ContactViewSet,
    InvoiceDetailAPIView,
    InvoiceDownloadAPIView,
    InvoiceGeneratePDFAPIView,
    InvoiceIssueAPIView,
    InvoiceListCreateAPIView,
)

app_name = "invoicing"

router = DefaultRouter()
router.register(r"contacts", ContactViewSet, basename="contact")

urlpatterns = [
    path("", include(router.urls)),
    path("invoices/", InvoiceListCreateAPIView.as_view(), name="invoice-list-create"),
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
]
