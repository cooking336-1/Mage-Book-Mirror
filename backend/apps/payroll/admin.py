"""Django Admin registration for Payroll models."""

from django.contrib import admin

from apps.payroll.models import PayrollItem, PayrollRun, PayrollTwoFactorProfile


class PayrollItemInline(admin.TabularInline):
    model = PayrollItem
    extra = 0
    readonly_fields = (
        "employee_name",
        "employee_tin_or_ghana_card",
        "momo_number",
        "gross_salary",
        "ssnit_employee",
        "ssnit_employer",
        "taxable_income",
        "paye_tax",
        "net_salary",
    )


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "period",
        "status",
        "total_gross_salary",
        "total_net_payout",
        "maker",
        "checker",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "organization__name")
    inlines = [PayrollItemInline]


@admin.register(PayrollTwoFactorProfile)
class PayrollTwoFactorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_enabled", "created_at", "updated_at")
    search_fields = ("user__email",)
