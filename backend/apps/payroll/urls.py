"""URL Configuration for Payroll & Statutory Remittances."""

from django.urls import path

from apps.payroll.views import (
    PayrollApprovalAPIView,
    PayrollRunDetailAPIView,
    PayrollRunListCreateAPIView,
    PayrollRunSubmitAPIView,
    PayrollTwoFactorSetupAPIView,
    PayrollTwoFactorVerifyAPIView,
)

app_name = "payroll"

urlpatterns = [
    path("runs/", PayrollRunListCreateAPIView.as_view(), name="run-list-create"),
    path("runs/<uuid:pk>/", PayrollRunDetailAPIView.as_view(), name="run-detail"),
    path("runs/<uuid:pk>/submit/", PayrollRunSubmitAPIView.as_view(), name="run-submit"),
    path("runs/<uuid:pk>/approve/", PayrollApprovalAPIView.as_view(), name="run-approve"),
    path("2fa/setup/", PayrollTwoFactorSetupAPIView.as_view(), name="2fa-setup"),
    path("2fa/verify/", PayrollTwoFactorVerifyAPIView.as_view(), name="2fa-verify"),
]
