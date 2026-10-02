# Mage Books SAAS — Backend Codebase Breakage Points & KISS Convention Audit

> **Exhaustive Technical Audit of Architectural Failure Modes, Concurrency Race Conditions, Transaction Traps, and KISS / DRY Convention Violations in the Django REST Backend (`backend/`).**
> 
> **Date:** September 2026 | **Status:** Active Reference & Remediation Blueprint  
> **Target System:** Backend API (`backend/`) | Django 5.x / Django REST Framework / PostgreSQL / Redis

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Priority Classification Matrix](#2-priority-classification-matrix)
3. [P0: Concurrency Race Conditions & Sequence Collisions](#3-p0-concurrency-race-conditions--sequence-collisions)
   - [3.1 Non-Atomic Invoice Number Generation Collision](#31-non-atomic-invoice-number-generation-collision)
   - [3.2 Luhn Payment Reference Duplicate Key Collision](#32-luhn-payment-reference-duplicate-key-collision)
   - [3.3 Journal Entry Number Sequence Collision](#33-journal-entry-number-sequence-collision)
4. [P1: Concurrency Bottlenecks & Architectural Inversions](#4-p1-concurrency-bottlenecks--architectural-inversions)
   - [4.1 Pessimistic Row Locking on Read-Only Chart of Accounts](#41-pessimistic-row-locking-on-read-only-chart-of-accounts)
   - [4.2 Universal `transaction.atomic()` Wrapping in Middleware](#42-universal-transactionatomic-wrapping-in-middleware)
5. [P1: Missing REST Endpoints & Route Configuration Gaps](#5-p1-missing-rest-endpoints--route-configuration-gaps)
   - [5.1 Missing Organization Registration Endpoint (`POST /api/v1/tenancy/organizations/`)](#51-missing-organization-registration-endpoint-post-apiv1tenancyorganizations)
   - [5.2 Missing Contacts REST Endpoint (`/api/v1/contacts/`)](#52-missing-contacts-rest-endpoint-apiv1contacts)
   - [5.3 Missing Public Invoice Viewer Endpoint & Middleware Exemption](#53-missing-public-invoice-viewer-endpoint--middleware-exemption)
6. [P2: Authentication, Session & Error Masking Hazards](#6-p2-authentication-session--error-masking-hazards)
   - [6.1 Omitted Refresh Token Rotation in `RefreshTokenView`](#61-omitted-refresh-token-rotation-in-refreshtokenview)
   - [6.2 Masked CSRF Failure in `TenantSecurityMiddleware`](#62-masked-csrf-failure-in-tenantsecuritymiddleware)
   - [6.3 Hardcoded Cookie Paths & Reverse Proxy Disconnects](#63-hardcoded-cookie-paths--reverse-proxy-disconnects)
7. [P2 / P3: Premature Optimization & KISS/DRY Redundancies](#7-p2--p3-premature-optimization--kissdry-redundancies)
   - [7.1 Redundant "Fast Path" Query in Balance Selectors](#71-redundant-fast-path-query-in-balance-selectors)
   - [7.2 Triplicate Auditor Role Checks](#72-triplicate-auditor-role-checks)
8. [Maintainability: Monolithic Procedural Functions](#8-maintainability-monolithic-procedural-functions)
9. [Remediation Action Plan & Checklist](#9-remediation-action-plan--checklist)

---

# 1. Executive Summary

This audit systematically examines the backend Django REST codebase (`backend/`) to identify:
1. Places where the code will break at runtime under production concurrency, high transaction volume, or edge-case network/database errors.
2. Violations of **KISS (Keep It Simple, Stupid)**, **YAGNI (You Aren't Gonna Need It)**, and **DRY (Don't Repeat Yourself)** principles that introduce locking bottlenecks or maintenance liabilities.
3. Missing REST endpoints required by the frontend client or specified in the Architecture Manual.

All 359 current backend tests pass in SQLite in-memory, but several critical runtime failure modes exist when deployed against PostgreSQL under multi-user concurrent traffic.

---

# 2. Priority Classification Matrix

| Level | Issue Description | File Location | Operational Impact |
| :-: | :--- | :--- | :--- |
| **P0** | Invoice Number Race Condition | [`apps/invoicing/services/invoicing_service.py:150-154`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/services/invoicing_service.py#L150-L154) | Concurrent invoice creation crashes with unhandled DB `IntegrityError` (HTTP 500). |
| **P0** | Payment Reference Race Condition | [`apps/invoicing/utils.py:189-193`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/utils.py#L189-L193) & [`models.py:400-403`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/models.py#L400-L403) | Duplicate Luhn reference collision crashes on unique constraint under traffic. |
| **P0** | Journal Entry Sequence Race Condition | [`apps/ledger/services/ledger.py:236-250`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/services/ledger.py#L236-L250) | Non-atomic `.exists()` check permits duplicate sequence keys, crashing on commit. |
| **P1** | Chart of Accounts Lock Bottleneck | [`apps/ledger/services/ledger.py:210-217`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/services/ledger.py#L210-L217) | `select_for_update()` serializes all postings, creating severe concurrency bottlenecks (HTTP 504). |
| **P1** | Universal Middleware `transaction.atomic()` | [`apps/tenancy/middleware.py:188-198`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/middleware.py#L188-L198) | Database exceptions mark outer transaction aborted; subsequent queries raise `TransactionManagementError`. |
| **P1** | Missing Tenant Organization Creation Endpoint | [`apps/tenancy/urls.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/urls.py) & [`views.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/views.py) | Frontend onboarding cannot create an Organization via API; users cannot register tenants. |
| **P1** | Missing Contacts REST Endpoints | [`apps/invoicing/urls.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/urls.py) & [`views.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/views.py) | No `/api/v1/contacts/` collection to manage customers and suppliers collected in onboarding. |
| **P1** | Missing Public Invoice Viewer Endpoint | [`apps/invoicing/urls.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/urls.py) & [`apps/tenancy/middleware.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/middleware.py) | Customer invoice links return HTTP 404 / 401 Unauthorized; endpoint was never registered. |
| **P2** | Refresh Token Rotation Cookie Omission | [`apps/authentication/views.py:126-138`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/authentication/views.py#L126-L138) | Turning on SimpleJWT rotation invalidates session and logs users out on refresh. |
| **P2** | Masked CSRF Error in Middleware | [`apps/tenancy/middleware.py:216-225`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/middleware.py#L216-L225) | Swallowing broad `Exception` converts HTTP 403 CSRF failures into misleading HTTP 401 Auth errors. |
| **P2** | Hardcoded Cookie Path Scoping | [`apps/authentication/views.py:57, 67`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/authentication/views.py#L57) | Refresh cookie strictly bound to `/api/v1/auth/`, failing if frontend proxies to `/api/auth/`. |
| **P3** | Redundant "Fast Path" Selector Query | [`apps/ledger/selectors.py:264-272`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/selectors.py#L264-L272) | Extra `.exists()` round-trip adds latency and permits unposted line leakage. |
| **P3** | Triplicate Auditor Role Checks | [`apps/invoicing/views.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/views.py) & [`apps/tenancy/middleware.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/middleware.py) | Auditor checks evaluated 3 times per request; violates DRY convention. |

---

# 3. P0: Concurrency Race Conditions & Sequence Collisions

### 3.1 Non-Atomic Invoice Number Generation Collision
* **Location**: [`apps/invoicing/services/invoicing_service.py:150-154`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/services/invoicing_service.py#L150-L154)
* **Offending Code**:
  ```python
  existing_count = Invoice.objects.filter(
      organization=organization,
      issue_date__year=issue_date.year,
  ).count()
  invoice_number = f"INV-{issue_date.year}-{existing_count + 1:05d}"
  ```
* **Failure Mechanism**:
  `existing_count` uses `SELECT COUNT(*)` without row locking or database sequences. When two cashiers or API requests issue invoices within the same second:
  1. Both execute `.count()` simultaneously and receive the same count (e.g., `42`).
  2. Both compute identical invoice numbers: `INV-2026-00043`.
  3. The [`Invoice`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/models.py#L286-L289) model enforces `UniqueConstraint(fields=["organization", "invoice_number"], name="unique_org_invoice_number")`.
  4. The first transaction commits; the second crashes with an unhandled exception:
     ```text
     django.db.utils.IntegrityError: duplicate key value violates unique constraint "unique_org_invoice_number"
     ```
* **KISS Remediation (Verdict Approved)**:
  Dedicated `InvoiceSequence` model (`organization`, `year`, `next_number`) with `select_for_update()`. Fulfills statutory gapless requirements under GRA E-VAT / Act 1151 with deterministic $O(1)$ row locking per tenant/year.

---

### 3.2 Luhn Payment Reference Duplicate Key Collision
* **Location**: [`apps/invoicing/utils.py:189-193`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/utils.py#L189-L193) & [`apps/invoicing/models.py:400-403`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/models.py#L400-L403)
* **Offending Code**:
  ```python
  if seq_number is None:
      count = Invoice.objects.filter(organization=organization).count()
      seq_number = 10001 + count

  return LuhnValidator.generate_reference(seq_number, delimiter="-")
  ```
* **Failure Mechanism**:
  In `Invoice.save()`, if `payment_reference` is empty, it calls `generate_invoice_payment_reference(self.organization)` using `count() + 10001`.
  - Under concurrent saves, identical base sequences (e.g. `10042`) generate identical Luhn references (`10042-8`).
  - Migration `0002_invoice_payment_reference` enforces a unique constraint on `(organization, payment_reference)`.
  - The second request crashes with an unhandled `IntegrityError` (HTTP 500).
* **KISS Remediation (Verdict Approved - Zero Migration)**:
  Add an active collision loop in `generate_invoice_payment_reference`:
  ```python
  ref = LuhnValidator.generate_reference(seq_number, delimiter="-")
  while Invoice.objects.filter(organization=organization, payment_reference=ref).exists():
      seq_number += 1
      ref = LuhnValidator.generate_reference(seq_number, delimiter="-")
  ```
  Guarantees valid 10-digit mod-10 Luhn references without schema changes.

---

### 3.3 Journal Entry Number Sequence Collision
* **Location**: [`apps/ledger/services/ledger.py:236-250`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/services/ledger.py#L236-L250)
* **Offending Code**:
  ```python
  count = JournalEntry.objects.filter(
      organization=organization,
      entry_date__year=year,
  ).count() + 1
  entry_number = f"JE-{year}-{count:05d}"
  if JournalEntry.objects.filter(organization=organization, entry_number=entry_number).exists():
      entry_number = f"JE-{year}-{uuid6.uuid7().hex[:8].upper()}"
  ```
* **Failure Mechanism**:
  The `.exists()` check is **non-atomic**. If Request A and Request B evaluate `.exists()` before either commits, both receive `False`, bypass the UUID fallback, and insert identical `JE-{year}-{count}` keys, crashing on `unique_org_journal_entry_number`.
* **KISS Remediation (Verdict Approved - Zero Migration)**:
  Use short UUIDv7 entropy suffix (`uuid6.uuid7().hex[:8].upper()`) upon collision. Preserves time-sortability and high parallel background throughput without bottlenecking on a shared counter.

---

# 4. P1: Concurrency Bottlenecks & Architectural Inversions

### 4.1 Pessimistic Row Locking on Read-Only Chart of Accounts
* **Location**: [`apps/ledger/services/ledger.py:210-217`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/services/ledger.py#L210-L217)
* **Offending Code**:
  ```python
  locked_accounts = list(
      ChartOfAccounts.objects.filter(
          organization=organization,
          id__in=sorted_account_ids,
      )
      .order_by("id")
      .select_for_update()
  )
  ```
* **KISS & Architectural Violation**:
  Architecture Manual §4.3.1 specifically outlines the **Hot Account Solution**:
  > *"Because INSERT statements do not block other INSERT statements in PostgreSQL, concurrent transactions execute simultaneously without holding locks on the master accounts."*
* **Failure Mechanism**:
  In `post_journal_entry`, `ChartOfAccounts` rows are **never updated or modified** (only checked for `is_active`). However, calling `select_for_update()` forces PostgreSQL to acquire exclusive row-level locks on master accounts (such as Account `1010` Cash or Account `1200` Accounts Receivable).
  - All simultaneous transactions touching Cash or AR serialize single-file.
  - Under load (e.g. mobile money webhook bursts), transactions queue up and trigger HTTP 504 Gateway Timeouts or PostgreSQL lock timeout crashes.
* **KISS Remediation**:
  Remove `select_for_update()`. A standard `SELECT` query is sufficient to verify `is_active` without blocking concurrent writes.

---

### 4.2 Universal `transaction.atomic()` Wrapping in Middleware
* **Location**: [`apps/tenancy/middleware.py:188-198`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/middleware.py#L188-L198)
* **Offending Code**:
  ```python
  with transaction.atomic():
      self._bind_db_session(tenant_uuid)
      response = self.get_response(request)
  ```
* **Failure Mechanisms**:
  1. **Aborted Transaction Cascades**: If any view or serializer handles a database error internally (e.g. in a try/except block catching `ObjectDoesNotExist` or validating a unique TIN), PostgreSQL marks the underlying transaction as broken. Any subsequent query in that request will raise `TransactionManagementError`.
  2. **Connection Pool Starvation**: Wrapping `get_response(request)` in an atomic transaction holds an active database connection and row locks for the entire request duration (including serialization, PDF rendering, and response transmission).
  3. **Silent Commit on HTTP 4xx Errors**: If a view catches an error and returns `Response({"error": ...}, status=400)`, any database writes that occurred before the validation failure are silently committed on middleware exit.
* **KISS Remediation**:
  Remove `transaction.atomic()` from the middleware. Scope atomic transactions exclusively to the domain service methods (`InvoicingService`, `LedgerService`, `PayrollApprovalService`).

---

# 5. P1: Missing REST Endpoints & Route Configuration Gaps

### 5.1 Missing Organization Registration Endpoint (`POST /api/v1/tenancy/organizations/`)
* **Location**: [`apps/tenancy/urls.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/urls.py) & [`apps/tenancy/views.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/views.py)
* **Failure Mechanism**:
  The backend has no public or authenticated endpoint for a new user to register a tenant organization.
  - In unit tests, organizations are created via `Organization.objects.create(...)`.
  - When a user signs up on the frontend and completes Onboarding Step 1 (`companyName`, `businessTin`, `ghanaCard`, `address`, `phone`, `email`), there is no REST endpoint to receive this payload, create the `Organization`, assign the user as `OWNER`, and bootstrap the default Chart of Accounts.
* **KISS Remediation (Verdict Approved)**:
  Implement `POST /api/v1/tenancy/organizations/` to create the tenant, assign the user as `OWNER`, and bootstrap the default Ghanaian Chart of Accounts in a single atomic transaction.

---

### 5.2 Missing Contacts REST Endpoint (`/api/v1/contacts/`)
* **Location**: [`apps/invoicing/urls.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/urls.py) & [`apps/invoicing/views.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/views.py)
* **Failure Mechanism**:
  The backend defines `Contact` model ([`apps/invoicing/models.py:37`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/models.py#L37)) and `ContactSerializer` ([`apps/invoicing/serializers.py:18`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/serializers.py#L18)), supporting Customers, Vendors, and Both.
  - However, **no views or URL routes exist in `apps/invoicing/urls.py`** for `/api/v1/contacts/`.
  - Frontend Onboarding Step 6 and Dashboard Contacts (`/dashboard/contacts`) have no backend endpoints to query or persist customer/supplier contacts.
* **KISS Remediation (Verdict Approved)**:
  Implement standard DRF `ModelViewSet` at `/api/v1/contacts/` scoped automatically to `request.organization` with search and filtering.

---

### 5.3 Missing Public Invoice Viewer Endpoint & Middleware Exemption
* **Location**: [`apps/invoicing/urls.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/urls.py) & [`apps/invoicing/views.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/views.py)
* **Failure Mechanism**:
  - Invoices inherit from `PublicShareableMixin` with `share_token = uuid4()`, intended for public view without credentials.
  - No view exists in `apps/invoicing/views.py` and no route exists in `apps/invoicing/urls.py`.
  - `/api/v1/invoicing/public/` is missing from `TenantSecurityMiddleware.EXEMPT_PATH_PREFIXES` ([`apps/tenancy/middleware.py:63-70`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/middleware.py#L63-L70)), meaning unauthenticated customers viewing public invoice links receive HTTP 401 Unauthorized.
* **KISS Remediation (Verdict Approved)**:
  1. Add `PublicInvoiceView(generics.RetrieveAPIView)` at `/api/v1/invoicing/public/invoices/<uuid:public_id>/` with `permission_classes = [AllowAny]`.
  2. Add `"/api/v1/invoicing/public/"` to `TenantSecurityMiddleware.EXEMPT_PATH_PREFIXES`.

---

# 6. P2: Authentication, Session & Error Masking Hazards

### 6.1 Omitted Refresh Token Rotation in `RefreshTokenView`
* **Location**: [`apps/authentication/views.py:126-138`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/authentication/views.py#L126-L138)
* **Offending Code**:
  ```python
  refresh = RefreshToken(raw_refresh)
  new_access_token = str(refresh.access_token)
  set_jwt_cookies(response, access_token=new_access_token)  # refresh_token is None!
  ```
* **Failure Mechanism**:
  When `"ROTATE_REFRESH_TOKENS": True` is active in production, SimpleJWT blacklists the old refresh token. Because no new refresh cookie is attached, the client retains the blacklisted token and the next refresh attempt crashes with `TokenError`, unexpectedly logging out users.
* **KISS Remediation**:
  Pass rotated refresh token into `set_jwt_cookies`:
  ```python
  if api_settings.ROTATE_REFRESH_TOKENS:
      refresh.set_jti()
      refresh.set_exp()
      set_jwt_cookies(response, access_token=new_access_token, refresh_token=str(refresh))
  ```

---

### 6.2 Masked CSRF Failure in `TenantSecurityMiddleware`
* **Location**: [`apps/tenancy/middleware.py:216-225`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/middleware.py#L216-L225)
* **Offending Code**:
  ```python
  def _resolve_jwt_user(self, request: HttpRequest) -> Any:
      try:
          auth_result = self.jwt_authenticator.authenticate(request)
          if auth_result is not None:
              user, _ = auth_result
              return user
      except (InvalidToken, TokenError, Exception):  # Catches all exceptions!
          pass
      return None
  ```
* **Failure Mechanism**:
  When a user with a valid JWT cookie makes a mutating request (`POST`/`PUT`/`DELETE`) but omits or provides an invalid `X-CSRFToken` header, `enforce_csrf` raises `exceptions.PermissionDenied`.
  - Swallowing broad `Exception` catches this and returns `None`.
  - The middleware then reports: `{"detail": "Authentication credentials were not provided."}` (HTTP 401), masking the true HTTP 403 CSRF failure.
* **KISS Remediation**:
  Do not swallow `PermissionDenied`; re-raise it so Django returns a proper HTTP 403 response.

---

### 6.3 Hardcoded Cookie Paths & Reverse Proxy Disconnects
* **Location**: [`apps/authentication/views.py:57, 67`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/authentication/views.py#L57)
* **Offending Code**:
  ```python
  response.set_cookie(key=refresh_cookie_name, ..., path="/api/v1/auth/")
  ```
* **Failure Mechanism**:
  The refresh token cookie is scoped strictly to `path="/api/v1/auth/"`. If a frontend Next.js application proxies authentication requests via `/api/auth/` (omitting `v1`), the browser will refuse to transmit the cookie.

---

# 7. P2 / P3: Premature Optimization & KISS/DRY Redundancies

### 7.1 Redundant "Fast Path" Query in Balance Selectors
* **Location**: [`apps/ledger/selectors.py:264-272`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/selectors.py#L264-L272)
* **Offending Code**:
  ```python
  has_unposted = (
      JournalEntry.objects.filter(organization=organization, is_posted=False)
      .order_by()
      .exists()
  )
  if has_unposted:
      lines_qs = lines_qs.filter(journal_entry__is_posted=True)
  ```
* **KISS Violation & Race Condition**:
  Attempting to avoid an SQL `INNER JOIN` adds an extra database query round-trip on every balance query.
  - If a concurrent transaction inserts an unposted journal entry between the `.exists()` check and the aggregate query, unposted journal lines leak into the trial balance totals.
* **KISS Remediation**:
  Delete the `has_unposted` check and unconditionally filter `journal_entry__is_posted=True`.

---

### 7.2 Triplicate Auditor Role Checks
* **Location**: [`apps/invoicing/views.py:45, 94-99`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/views.py#L45) & [`apps/tenancy/middleware.py:164-181`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/middleware.py#L164-L181)
* **DRY Violation**:
  The auditor read-only constraint is evaluated three separate times on the same request:
  1. In `TenantSecurityMiddleware` Guard 4.
  2. In `permission_classes = [IsAuditorReadOnly]`.
  3. Inside view methods: `if role == RoleChoices.AUDITOR: return Response(...)`.
* **KISS Remediation**:
  Rely on DRF's `IsAuditorReadOnly` permission class and delete manual boilerplate from individual view methods.

---

# 8. Maintainability: Monolithic Procedural Functions

Several functions exceed 150–450 lines, mixing multiple distinct responsibilities in a single procedural block:

| Function | File | Lines | Responsibilities Tangled |
| :--- | :--- | :---: | :--- |
| `compile_invoice_pdf` | [`apps/invoicing/services/pdf_compiler.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/services/pdf_compiler.py#L62-L518) | **455** | Color palettes, typography styling, SSRF regex checks, table layout math, vector QR widgets, flowable story building. |
| `reconcile_payment` | [`apps/payments/services/reconciliation.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/payments/services/reconciliation.py#L162-L525) | **363** | Luhn parsing, invoice matching, partial payment logic, suspense account quarantine, GL entry construction, status updating. |
| `post_journal_entry` | [`apps/ledger/services/ledger.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/services/ledger.py#L69-L297) | **228** | Fiscal period validation, line normalization, debit/credit sum math, account locking, entry number generation, line creation. |
| `approve_payroll_run` | [`apps/payroll/services/approval_service.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/payroll/services/approval_service.py#L81-L261) | **180** | Maker-Checker validation, TOTP verification, account bootstrapping, GL line construction, status saving, audit log creation. |

* **KISS Remediation**:
  Decompose into focused private helper methods (`_validate_lines`, `_build_gl_lines`, `_format_table_headers`).

---

# 9. Remediation Action Plan & Checklist

- [ ] **P0**: Add atomic collision retry loops for invoice numbers in [`apps/invoicing/services/invoicing_service.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/services/invoicing_service.py).
- [ ] **P0**: Add collision loop for Luhn payment references in [`apps/invoicing/utils.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/utils.py).
- [ ] **P0**: Replace count-based journal entry numbers with collision retry/entropy in [`apps/ledger/services/ledger.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/services/ledger.py).
- [ ] **P1**: Remove `select_for_update()` on `ChartOfAccounts` in [`apps/ledger/services/ledger.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/services/ledger.py).
- [ ] **P1**: Remove `transaction.atomic()` from [`apps/tenancy/middleware.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/middleware.py) and scope atomicity strictly to domain services.
- [ ] **P1**: Implement `OrganizationCreateAPIView` and register `path("organizations/", ...)` in [`apps/tenancy/urls.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tenancy/urls.py).
- [ ] **P1**: Implement `ContactListCreateAPIView` and register `path("contacts/", ...)` in [`apps/invoicing/urls.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/invoicing/urls.py).
- [ ] **P1**: Implement `PublicInvoiceView`, register route, and add path to `TenantSecurityMiddleware.EXEMPT_PATH_PREFIXES`.
- [ ] **P2**: Pass `refresh_token` in `RefreshTokenView.set_jwt_cookies` when rotation is active.
- [ ] **P2**: Re-raise `PermissionDenied` in `TenantSecurityMiddleware._resolve_jwt_user`.
- [ ] **P3**: Unconditionally filter `journal_entry__is_posted=True` in [`apps/ledger/selectors.py`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/selectors.py).
