"""URL configuration for General Ledger and Financial Statement reports."""

from django.urls import path

from apps.ledger.views import (
    AccountDetailAPIView,
    AccountJournalLineListAPIView,
    AccountListAPIView,
    BalanceSheetReportAPIView,
    FiscalPeriodCloseAPIView,
    FiscalPeriodListAPIView,
    JournalEntryDetailAPIView,
    JournalEntryListAPIView,
    ProfitAndLossReportAPIView,
    TrialBalanceReportAPIView,
)

app_name = "ledger"

urlpatterns = [
    # Master Chart of Accounts Resources
    path("accounts/", AccountListAPIView.as_view(), name="account-list"),
    path("accounts/<uuid:pk>/", AccountDetailAPIView.as_view(), name="account-detail"),
    path(
        "accounts/<uuid:account_id>/entries/",
        AccountJournalLineListAPIView.as_view(),
        name="account-entries-list",
    ),
    # Journal Entries (General Ledger)
    path("journal-entries/", JournalEntryListAPIView.as_view(), name="journal-entry-list"),
    path(
        "journal-entries/<uuid:pk>/",
        JournalEntryDetailAPIView.as_view(),
        name="journal-entry-detail",
    ),
    # Financial Statement Report Resources
    path(
        "reports/trial-balance/",
        TrialBalanceReportAPIView.as_view(),
        name="report-trial-balance",
    ),
    path(
        "reports/profit-and-loss/",
        ProfitAndLossReportAPIView.as_view(),
        name="report-profit-loss",
    ),
    path(
        "reports/balance-sheet/",
        BalanceSheetReportAPIView.as_view(),
        name="report-balance-sheet",
    ),
    # Fiscal Periods & Period Closing
    path(
        "fiscal-periods/",
        FiscalPeriodListAPIView.as_view(),
        name="fiscal-period-list",
    ),
    path(
        "fiscal-periods/<uuid:pk>/close/",
        FiscalPeriodCloseAPIView.as_view(),
        name="fiscal-period-close",
    ),
]
