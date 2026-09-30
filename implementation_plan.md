# Implementation Plan — Sprint D: Scalability, Offline PWA & Full-Stack Hardening

> **Sprint Branch:** `sprint/sprint-d-scalability-pwa`  
> **Master Playbook & Rules:** [`backend/AGENTS.md`](file:///m:/CODES/Work/magebooks-SAAS/backend/AGENTS.md)  
> **Execution Specification Reference:** [`docs/Mage Books SAAS — Remediation & Hardening Master Sprint Plan (v3.0).docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Remediation%20&%20Hardening%20Master%20Sprint%20Plan%20%28v3.0%29.docx.md) §8  
> **Detailed Engineering Inventory:** [`docs/COMPREHENSIVE_FIX_PLAN.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/COMPREHENSIVE_FIX_PLAN.md) (Items F7, F8, F11, F12, F13, G4, B14, T4.1–T4.4)  
> **Author & Lead:** Marcel Yeboah  

---

## 1. Executive Summary & Sprint Scope

Sprint D transitions Mage Books SAAS from core functional compliance to production-grade enterprise scalability, offline progressive web app (PWA) resilience, complete frontend-to-backend API wiring, and automated dual-stage CI/CD verification.

### Core Objectives
1. **PWA Offline Resilience (MUC 3.1 & F7):** Connect WebCrypto AES-GCM encryption to local IndexedDB (`idb`) draft queue with automatic background sync upon internet reconnect.
2. **Dynamic Tenancy & Mode Sync (F8 & F12):** Wire accounting mode toggle to backend `PATCH /api/v1/tenancy/organizations/current/`, make TopNavBar display live tenant metadata, implement Cmd+K command palette, and wire secure HttpOnly cookie logout.
3. **Full-Stack Wiring & Route Hygiene (F11 & F13):** Connect dashboard shell views to live REST endpoints via centralized `apiClient.ts` and replace 50+ dead `href="#"` links with unified shared footer and legal routes.
4. **General Ledger Scalability (G4):** Implement `AccountSnapshot` monthly rollup model and Celery background task, optimizing `get_account_balance` for high-volume tenants (>50k transactions) to maintain <10ms response times.
5. **Architectural Cleanliness (B14):** Decompose monolithic 180–455 line service orchestrators in Invoicing, Ledger, and Payroll into focused, single-responsibility private static helpers while preserving 100% backward compatibility.
6. **Dual-Stage CI/CD Pipeline (T4.1–T4.4):** Implement PostgreSQL 16 service container in GitHub Actions, migration dry-run checks (`makemigrations --check --dry-run`), and automated migration reversibility tests.

---

## 2. Forward-Looking Impact & Breakage Analysis

Per the **Mandatory Implementation Planning Directive** in `backend/AGENTS.md`:

| Subsystem / Integration | Potential Breakage Points | Concrete Architectural Safeguards |
|:---|:---|:---|
| **Invoicing & Double-Entry Ledger** | Monolithic service decomposition (B14) or snapshot rollups (G4) could alter debit/credit posting balances or break invoice creation. | Public service method signatures, arguments, and return types remain 100% identical. Snapshot selector only aggregates closed periods; in-flight and current-month transactions continue to query atomic `JournalLine` rows. Existing 507 backend tests run as an inviolable regression gate. |
| **PWA Offline Invoicing & Sync** | Replaying encrypted offline drafts when internet resumes could generate duplicate invoice numbers or bypass GRA E-VAT clearance. | Offline sync invokes standard `POST /api/v1/invoicing/invoices/` passing `Idempotency-Key` headers (protected by Redis `IdempotencyMiddleware`). The backend assigns canonical gapless sequential numbers via `InvoiceSequence` table row locks. |
| **Tenancy & Accounting Modes** | Updating accounting mode via `PATCH /organizations/current/` could permit unauthorized role changes or leak cross-tenant settings. | `PATCH /organizations/current/` strictly scopes to the resolved `request.tenant` from `TenantSecurityMiddleware`. Only `OWNER` and `ADMIN` can mutate organizational settings; auditor write blocking remains enforced via `IsAuditorReadOnly`. |
| **PostgreSQL Database Schema** | Introducing `AccountSnapshot` model could cause unapplied migration drift in development or CI. | Directive 5 strictly observed: generate migration with `makemigrations`, inspect raw SQL with `sqlmigrate`, present SQL to user for explicit approval before migrating. |
| **CI/CD Quality Gates** | Adding PostgreSQL 16 container to GitHub Actions could fail due to timing or connection latency. | Use GitHub Actions healthchecks (`pg_isready -U postgres`) to ensure the container is fully healthy before executing Stage 2 tests. |

---

## 3. Sprint D Task Breakdown & Execution Plan

Development proceeds sequentially on `sprint/sprint-d-scalability-pwa`. Each task is verified with Stage 1 & Stage 2 tests and zero linter warnings, then committed to the **local git branch only** (`git commit -m "<type>(<scope>): Task D.X - <desc>"`).

### Task D.1 (F7): Offline PWA Draft Storage with Encrypted IndexedDB
- **Classification:** `FEATURE` | **Commit:** `feat(pwa): Task D.1 - encrypted IndexedDB offline draft queue`
- **Files:** `src/lib/offline-storage.ts`, `src/lib/crypto/pwa-cache-encryption.ts`
- **Implementation:**
  - Build `offline-storage.ts` using browser IndexedDB (`magebooks_offline_db`) with stores: `offline_invoices` and `offline_contacts`.
  - Connect `encryptCustomerCacheRecord` and `encryptSensitivePayload` from `pwa-cache-encryption.ts` to encrypt all sensitive draft data at rest (AES-GCM 256-bit).
  - Add offline queue management: `saveOfflineDraft()`, `getOfflineDrafts()`, `deleteOfflineDraft()`, and `syncOfflineDrafts(apiClient)`.
  - Listen to `window.addEventListener("online")` to trigger background synchronization when connection is re-established.
- **Verification:** Frontend test suite / TypeScript build verifying encryption round-trips and offline draft lifecycle.

### Task D.2 (F8): Synchronize Accounting Mode Preference with Backend API
- **Classification:** `REFACTOR` | **Commit:** `refactor(tenancy): Task D.2 - synchronize accounting mode with backend API`
- **Files:** `backend/apps/tenancy/views.py`, `backend/apps/tenancy/serializers.py`, `backend/apps/tenancy/urls.py`, `src/contexts/ModeContext.tsx`
- **Implementation:**
  - Backend: Extend `OrganizationDeactivationAPIView` to `OrganizationCurrentDetailAPIView` supporting `GET` (return current org details) and `PATCH` (update `default_experience_mode`, `name`, `address`, etc.) restricted to `OWNER` / `ADMIN`.
  - Frontend: Update `ModeContext.tsx` to asynchronously call `apiClient.patch("/api/v1/tenancy/organizations/current/", { default_experience_mode: mode })`. On initial mount, fetch current tenant preferences to ensure cross-device consistency.
- **Verification:** DRF `APIClient` integration test verifying `GET` and `PATCH /api/v1/tenancy/organizations/current/`.

### Task D.3 (F11): Connect Dashboard Shell Subpages to Domain APIs
- **Classification:** `FEAT` | **Commit:** `feat(dashboard): Task D.3 - wire dashboard shell pages to REST APIs`
- **Files:** `src/app/(dashboard)/dashboard/...` (Contacts, Ledgers, Accounts Payable/Receivable, Chart of Accounts, Reports, Payments)
- **Implementation:**
  - Replace hardcoded static dummy arrays with dynamic fetching via `apiClient.get()`.
  - Integrate loading skeletons, error states, and empty states.
  - Format monetary values using standard Ghanaian Cedi formatting (`GHS X,XXX.XX`).
- **Verification:** Next.js build (`npx tsc --noEmit` and `npm run lint`) passes with zero errors.

### Task D.4 (F12): Dynamic TopNavBar Hub, Command Palette & Logout Handler
- **Classification:** `REFACTOR` | **Commit:** `refactor(navigation): Task D.4 - dynamic TopNavBar hub, Cmd+K search and logout`
- **Files:** `src/components/dashboard/TopNavBar.tsx`
- **Implementation:**
  - Dynamic Organization Name: Fetch and display active tenant organization name from `/api/v1/tenancy/context/` or current org data.
  - Command Palette: Implement accessible modal triggered by `Cmd+K` / `Ctrl+K` or search bar click, enabling keyboard navigation across dashboard routes, invoices, and contacts.
  - User Profile & Logout: Add dropdown on avatar displaying user role and a working "Log out" button executing `POST /api/v1/auth/logout/` via `apiClient`, clearing cookies and redirecting to `/login`.
- **Verification:** TypeScript checks and UI component behavior verified.

### Task D.5 (F13): Replace Dead Anchors (`href="#"`) with Real Routes
- **Classification:** `CHORE` | **Commit:** `chore(navigation): Task D.5 - replace dead anchor links with shared footer and legal routes`
- **Files:** `src/components/dashboard/DashboardFooter.tsx`, `src/app/legal/privacy/page.tsx`, `src/app/legal/terms/page.tsx`, `src/app/legal/support/page.tsx`, dashboard views
- **Implementation:**
  - Create reusable `DashboardFooter` with clean, accessible links to `/legal/privacy`, `/legal/terms`, and `/legal/support`.
  - Create lightweight legal and support landing pages.
  - Replace all occurrences of `<Link href="#">` across dashboard pages with `<DashboardFooter />` or explicit interactive button handlers.
- **Verification:** Grep audit confirming zero `href="#"` dead links remain in `src/`.

### Task D.6 (G4): Materialized `AccountSnapshot` Monthly Rollup for Scale
- **Classification:** `FEAT` | **Commit:** `feat(ledger): Task D.6 - AccountSnapshot monthly rollup model and Celery task`
- **Files:** `backend/apps/ledger/models.py`, `backend/apps/ledger/tasks.py`, `backend/apps/ledger/selectors.py`, `backend/apps/ledger/tests/test_snapshots.py`
- **Implementation:**
  - Model: Create `AccountSnapshot(BaseTenantModel)` with fields: `account` (FK `ChartOfAccounts`), `period_end` (DateField), `closing_balance` (DecimalField max_digits=18, decimal_places=4). Unique constraint: `(organization, account, period_end)`.
  - Migration Gate (Directive 5): `makemigrations`, `sqlmigrate`, present SQL for confirmation before applying.
  - Background Task: Create Celery task `rollup_monthly_account_snapshots` in `apps/ledger/tasks.py` rolling up balances for closed periods.
  - Selector Optimization: Update `get_account_balance` in `apps/ledger/selectors.py` to utilize the latest closed snapshot and sum subsequent lines.
- **Verification:** Unit test suite verifying snapshot generation, rollup accuracy, and balance query optimization.

### Task D.7 (B14): Decompose Monolithic Procedural Functions into Private Helpers
- **Classification:** `REFACTOR` | **Commit:** `refactor(services): Task D.7 - decompose monolithic service orchestrators`
- **Files:** `backend/apps/invoicing/services/invoicing_service.py`, `backend/apps/ledger/services/ledger.py`, `backend/apps/payroll/services/calculator.py`, `backend/apps/payroll/services/disbursement.py`
- **Implementation:**
  - Decompose 180–455 line methods (`create_invoice`, `post_journal_entry`, `disburse_payroll_run`) into private static helpers (`_validate_line_taxes()`, `_calculate_totals()`, `_post_gl_lines()`).
  - Keep public API contracts completely intact.
  - Create `backend/tests/unit/test_decomposed_helpers.py` testing private subroutines with 100% branch coverage.
- **Verification:** Full regression test pass across all 507 backend tests + new decomposed helper tests.

### Task D.8 (T4.1–T4.4): Dual-Stage CI/CD GitHub Actions & PostgreSQL 16 Service Container
- **Classification:** `CHORE` | **Commit:** `chore(ci): Task D.8 - configure dual-stage PostgreSQL 16 CI pipeline`
- **Files:** `.github/workflows/ci.yml`
- **Implementation:**
  - Configure PostgreSQL 16 service container (`postgres:16-alpine`) in GitHub Actions.
  - Add migration dry-run step: `uv run python manage.py makemigrations --check --dry-run`.
  - Add migration rollback test step.
  - Execute Stage 1 fast SQLite gate (<5s) followed by Stage 2 PostgreSQL integration and concurrency stress tests (`USE_POSTGRES_TESTS=1`).
- **Verification:** Validate `.github/workflows/ci.yml` schema and local test pass.

---

## 4. Verification & Sprint Completion Gate

Before completing Sprint D and presenting the push command:
1. **Full Backend Test Suite:** `uv run python manage.py test` passes 100% green.
2. **PostgreSQL Concurrency Tests:** `USE_POSTGRES_TESTS=1 uv run python manage.py test tests.stress` passes with 0 collisions.
3. **Linting & Formatting:** `uv run ruff check .` and `uv run ruff format --check .` report 0 errors.
4. **Frontend Quality:** `npx tsc --noEmit` and `npm run lint` report 0 warnings or errors.
5. **No Remote Pushes during Tasks:** All task commits remain local on `sprint/sprint-d-scalability-pwa`.
6. **Sprint PR Gate:** User will be prompted to push the entire sprint branch and open the PR for merge into `develop`.
