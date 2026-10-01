"""URL routing for Tenancy endpoints, Team Members, and Financial Destination Locks."""

from django.urls import path

from apps.tenancy.views import (
    OrganizationCreateAPIView,
    OrganizationCurrentDetailAPIView,
    OrganizationMemberDetailAPIView,
    OrganizationMemberListCreateAPIView,
    OrganizationSettlementAPIView,
    TenantContextTestView,
)

app_name = "tenancy"

urlpatterns = [
    # Tenant Provisioning & Organization Listing
    path(
        "organizations/",
        OrganizationCreateAPIView.as_view(),
        name="organization-create",
    ),
    path("context/", TenantContextTestView.as_view(), name="tenant-context"),
    # Team Member Management & Owner Immutability
    path("members/", OrganizationMemberListCreateAPIView.as_view(), name="member-list-create"),
    path("members/<uuid:pk>/", OrganizationMemberDetailAPIView.as_view(), name="member-detail"),
    # Financial Destination Locks (Payout Accounts & MoMo Wallets)
    path(
        "organization/settlement/",
        OrganizationSettlementAPIView.as_view(),
        name="organization-settlement",
    ),
    # Current Organization Details, Mode Sync, and Sole Destroyer Rule
    path(
        "organizations/current/",
        OrganizationCurrentDetailAPIView.as_view(),
        name="organization-current-detail",
    ),
]
