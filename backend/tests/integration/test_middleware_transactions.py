"""Integration test suite for TenantSecurityMiddleware transaction isolation (Task A.8 / T1.5).

Validates:
1. TenantSecurityMiddleware does NOT wrap request execution in transaction.atomic().
2. Handled inner exceptions do not abort outer transactions or raise TransactionManagementError.
3. InvoicingService dispatches GRA E-VAT clearance on commit via transaction.on_commit().
4. PaymentWebhookLog entries persist even when reconciliation encounters failures/rollbacks.
5. Tenant session parameters and thread-local state are cleanly deallocated on request completion.
"""

from apps.tenancy.tests.test_middleware_transactions import (
    MiddlewareTransactionUnwrappingTests,
)

__all__ = ["MiddlewareTransactionUnwrappingTests"]
