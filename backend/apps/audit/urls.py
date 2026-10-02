"""URL configuration for Forensic Audit and PBC Package APIs."""

from django.urls import path

from apps.audit.views import (
    AuditTrailListAPIView,
    PBCAuditExportAPIView,
    PBCAuditExportStatusAPIView,
)

app_name = "audit"

urlpatterns = [
    path("pbc/", PBCAuditExportAPIView.as_view(), name="pbc-export"),
    path("pbc/<str:task_id>/", PBCAuditExportStatusAPIView.as_view(), name="pbc-status"),
    path("trail/", AuditTrailListAPIView.as_view(), name="audit-trail-list"),
]
