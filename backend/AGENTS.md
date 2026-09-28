<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Mage Books SAAS — Autonomous Developer & Agent Playbook
### Unified Engineering Directives for Remediation, Hardening, Statutory Compliance & Testing

> **System Target:** Mage Books SAAS (`backend/`) — Enterprise Multi-Tenant Accounting Platform  
> **Statutory Jurisdiction:** Republic of Ghana (Value Added Tax Act, 2025, Act 1151 / GRA CIS E-VAT)  
> **Author & Engineering Lead:** Marcel Yeboah  
> **Playbook Status:** Mandatory & Enforced Across All Autonomous AI Agents and Developers

---

## 1. Core Operating Philosophy & Mandates

Mage Books SAAS is an enterprise financial engine. In an accounting platform, a single race condition corrupts the general ledger, an unverified migration causes data loss, an unhandled transaction lock freezes multi-tenant traffic, and an inaccurate tax split triggers severe regulatory penalties under Ghana Revenue Authority (GRA) laws.

Every autonomous AI agent (including Antigravity, Cursor, and Claude Code) and human engineer operating in this repository **MUST** adhere to the following Golden Operational Directives without exception.

---

## 2. The Golden Operational Directives

### Directive 1: Exhaustive Root-Cause Investigation (Depth-of-Problem Protocol)
> [!CRITICAL]
> **NEVER TOUCH A SINGLE LINE OF CODE OR DRAFT A SOLUTION BEFORE UNDERSTANDING THE FULL ROOT CAUSE AND ARCHITECTURAL DEPTH OF THE PROBLEM.**

Before modifying, creating, or refactoring any code, the agent **MUST** inspect the four **Root-Cause Investigation Audits** in [`docs/`](file:///m:/CODES/Work/magebooks-SAAS/docs):
1. [`docs/BACKEND_BREAKAGE_AND_KISS_AUDIT.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/BACKEND_BREAKAGE_AND_KISS_AUDIT.md): Technical audit of database race conditions, locking bottlenecks, middleware traps, and KISS/DRY violations.
2. [`docs/BACKEND_IMPLEMENTATION_GAPS.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/BACKEND_IMPLEMENTATION_GAPS.md): Inventory of deferred features, missing Celery workers, and scale patterns.
3. [`docs/CODEBASE_BREAKAGE_AND_KISS_AUDIT.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/CODEBASE_BREAKAGE_AND_KISS_AUDIT.md): Cross-system audit across backend APIs and frontend consumer views.
4. [`docs/COMPREHENSIVE_FIX_PLAN.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/COMPREHENSIVE_FIX_PLAN.md): Detailed 33-item inventory of bugs, refactors, missing features, and architectural trade-offs.

The agent must understand:
* Exactly how the current code fails under production PostgreSQL multi-tenant concurrency.
* How the failure ripples across database transactions, session-level Row-Level Security (RLS), and external statutory integrations.
* Why naive solutions (such as locking entire tables or wrapping middleware in transactions) violate KISS and introduce worse failure modes.

---

### Directive 2: Authoritative Action Blueprints (Execution Sources)
When executing any remediation, bug fix, architectural refactoring, feature addition, or test suite implementation, the agent **MUST** base its work strictly upon the following **Execution Reference Documents**:
1. [`docs/Mage Books SAAS — Remediation & Hardening Master Sprint Plan (v3.0).docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Remediation%20&%20Hardening%20Master%20Sprint%20Plan%20%28v3.0%29.docx.md): The phased 4-sprint roadmap defining exact task groupings, branch names, and acceptance criteria.
2. [`docs/Mage Books SAAS — Comprehensive Fix, Refactor & Feature Remediation Plan.docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Comprehensive%20Fix,%20Refactor%20&%20Feature%20Remediation%20Plan.docx.md): The detailed engineering implementation blueprint for all 33 breakage items.
3. [`docs/Mage Books SAAS — Master Testing Specification, Edge Cases & Verification Protocols.docx (1).md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Master%20Testing%20Specification,%20Edge%20Cases%20&%20Verification%20Protocols.docx%20%281%29.md): Boundary value analysis, multi-threaded concurrency test harnesses, API integration tests, and quality gates.
4. [`docs/FRONTEND_BREAKAGE_AND_UX_AUDIT.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/FRONTEND_BREAKAGE_AND_UX_AUDIT.md): Contractual alignment for frontend API consumption, route parameters, payloads, and statutory copy.

---

### Directive 3: Strict Architectural Arbitration & Option Selection Rule
> [!IMPORTANT]
> **ZERO SPECULATIVE ARCHITECTURE. IMPLEMENT ONLY PRE-APPROVED DECISIONS.**

In [`docs/COMPREHENSIVE_FIX_PLAN.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/COMPREHENSIVE_FIX_PLAN.md), numerous items outline multiple possible options (e.g., Option A vs. Option B). 

Whenever an agent encounters multiple options or trade-offs for an item:
* The agent **MUST cross-reference** what was explicitly chosen and approved in:
  1. [`docs/Mage Books SAAS — Remediation & Hardening Master Sprint Plan (v3.0).docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Remediation%20&%20Hardening%20Master%20Sprint%20Plan%20%28v3.0%29.docx.md)
  2. [`docs/Mage Books SAAS — Comprehensive Fix, Refactor & Feature Remediation Plan.docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Comprehensive%20Fix,%20Refactor%20&%20Feature%20Remediation%20Plan.docx.md)
  3. [`docs/Mage Books SAAS — Master Transaction Sequence Diagrams & Lifecycle Specification.docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Master%20Transaction%20Sequence%20Diagrams%20&%20Lifecycle%20Specification.docx.md)
* **Strict Mandate**: The agent **MUST ONLY implement the option selected and approved in these three master documents**.
* **Under NO circumstance** may an agent:
  * Guess or select an alternate option because it seems easier.
  * Invent a new, unvetted architectural pattern.
  * Deviate from the canonical database schemas, sequence algorithms, or sequence diagram transaction boundaries.

---

### Directive 4: Human-in-the-Loop Inspection & Push Gate (No Auto-Push)
> [!CAUTION]
> **AUTONOMOUS AGENTS ARE STRICTLY PROHIBITED FROM PUSHING CODE TO REMOTE REPOSITORIES (`git push`).**

The user reserves sole authority over git remote pushes and PR creation:
1. Development proceeds strictly on dedicated feature branches: `fix/<sprint>-<task>`, `feat/<sprint>-<task>`, `refactor/...`, or `test/...`.
2. Never commit directly to `main` or `develop`.
3. When code implementation, linting, and all dual-stage tests are 100% passing:
   * **Halt execution immediately.**
   * Present the exact `git add`, `git commit -m "..."`, and `git push -u origin <branch>` commands in code blocks for the user.
   * **Wait for explicit confirmation from the user** that the branch was inspected, pushed, and merged via PR before proceeding.
4. **Mandatory Pre-Feature PR Merge Check & Branch Cleanup**:
   Before creating a branch for the next task:
   * Confirm the previous feature's PR has been merged into `develop`.
   * Switch to `develop` and pull latest changes:
     ```bash
     git checkout develop
     git pull origin develop
     ```
   * Delete the local merged branch:
     ```bash
     git branch -d <branch-name>
     ```
   * Delete the remote merged branch:
     ```bash
     git push origin --delete <branch-name>
     ```

---

### Directive 5: Human-in-the-Loop Database Migration Authorization
> [!CAUTION]
> **NEVER AUTOMATICALLY RUN `python manage.py migrate` AGAINST POSTGRESQL OR SHARED DATABASES.**

If a task introduces or mutates database models (e.g., `InvoiceSequence`, `CreditNote`, `IdempotencyKey`):
1. Generate the migration using `uv run python manage.py makemigrations <app_name>`.
2. Inspect the raw SQL using `uv run python manage.py sqlmigrate <app_name> <migration_number>`.
3. Output the complete SQL statements to the user inside a markdown code block.
4. **Pause and explicitly request user authorization** before applying migrations to any PostgreSQL database.

---

### Directive 6: Dual-Stage CI/CD Testing & Escaping the ORM-Only Trap
* **Escape the ORM-Only Trap**: Writing tests that only call `Model.objects.create()` is strictly forbidden for business flows. All state-mutating flows must be tested via DRF's `APIClient` simulating real HTTP requests, headers (`X-Organization-ID`), JSON serialization, URL resolution, and permission gates.
* **Stage 1: In-Memory SQLite Fast Gate (<5s)**:
  * Fast feedback for unit testing, schema validation, and linting.
  * Executed via `uv run python manage.py test apps.<app_name>`.
* **Stage 2: Real PostgreSQL 16 Concurrency Stress Gate**:
  * Mandatory for all sequence generation (Invoices, Luhn references, Journal entries) and row-locking logic.
  * Must pass a multi-threaded stress harness spawning **at least 20 concurrent threads** under real PostgreSQL transaction isolation (`USE_POSTGRES_TESTS=1`), verifying zero duplicate key `IntegrityError` exceptions and strictly gapless sequences.

---

### Directive 7: Statutory Ghanaian Tax & Accounting Compliance (Act 1151)
All financial logic must comply strictly with the **Ghana Value Added Tax Act, 2025 (Act 1151)**:
* **Statutory Rates**:
  * Standard VAT: **15.0%**
  * National Health Insurance Levy (NHIL): **2.5%**
  * Ghana Education Trust Fund (GETFund): **2.5%**
  * COVID-19 Health Recovery Levy: **0.0% (REPEALED — NEVER RE-INTRODUCE)**
* **Non-Cascading Calculations**: Levies are calculated directly on the taxable base, not compounded.
* **Immutable Snapshotting**: Point-in-time legal customer data (Name, TIN/Ghana Card PIN, Address) must be frozen on the invoice document at issuance to prevent historical alteration upon customer profile updates.
* **Discrete Statutory Credit Notes**: Credit notes must never be simple negative invoice quantities; they must be modeled as discrete statutory instruments with reversing double-entry schedules.
* **Suspense Account 2150**: Unmatched or erroneous Mobile Money deposits must be quarantined into Suspense Account 2150 to preserve balance sheet equilibrium.

---

### Directive 8: Tooling & Runtime Environment Discipline (`uv`, `ruff`)
* **Strict Virtual Environment Execution**: NEVER run `python` or `manage.py` directly using system Python. Always prefix with `uv run` (e.g., `uv run python manage.py <command>`) or run inside the activated `.venv`.
* **Modern Package Management**: Use `uv add`, `uv remove`, `uv sync`.
* **Zero Linter Warnings**: Enforce code formatting and linting via `uv run ruff check .` and `uv run ruff format .` prior to staging any commit.
* **Unified Configuration**: Maintain exactly one clean `config/settings.py` file utilizing `django-environ`. Never split into `base.py`, `local.py`, or `production.py`.
* **Deterministic Mock Adapters**: Always maintain deterministic mock service adapters (`MockPaystackGateway`, `MockHubtelGateway`, `MockGraEvatClient`, `MockR2Storage`) so automated tests never depend on external network availability.

---

## 3. The 6-Step Agent Remediation Loop

For every single fix, refactor, or feature task, the agent must execute this standardized six-phase lifecycle:

```mermaid
flowchart TD
    A[Step 1: Document Investigation & Problem Depth Discovery] --> B[Step 2: Cross-Reference & Option Arbitration]
    B --> C[Step 3: Implementation Plan & Human Approval Gate]
    C --> D[Step 4: Branch Creation & Test-Driven Code Execution]
    D --> E{Schema Changes?}
    E -- Yes --> F[Step 5: SQL Migration Inspection Gate]
    E -- No --> G[Step 6: Dual-Stage Testing & User Push Handoff]
    F --> G
    G --> H[Pause & Await User Push & PR Merge]
```

### Step 1: Document Investigation & Problem Depth Discovery
* Read the target issue description in [`docs/COMPREHENSIVE_FIX_PLAN.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/COMPREHENSIVE_FIX_PLAN.md) and cross-reference with:
  * [`docs/BACKEND_BREAKAGE_AND_KISS_AUDIT.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/BACKEND_BREAKAGE_AND_KISS_AUDIT.md)
  * [`docs/BACKEND_IMPLEMENTATION_GAPS.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/BACKEND_IMPLEMENTATION_GAPS.md)
  * [`docs/CODEBASE_BREAKAGE_AND_KISS_AUDIT.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/CODEBASE_BREAKAGE_AND_KISS_AUDIT.md)
* Trace the code in `backend/` to see exact line numbers, existing decorators (`@transaction.atomic`), middleware interactions, and test coverage.

### Step 2: Cross-Reference & Option Arbitration
* If options are presented (e.g. Option A vs Option B in `COMPREHENSIVE_FIX_PLAN.md`):
  * Open [`docs/Mage Books SAAS — Remediation & Hardening Master Sprint Plan (v3.0).docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Remediation%20&%20Hardening%20Master%20Sprint%20Plan%20%28v3.0%29.docx.md) and [`docs/Mage Books SAAS — Master Transaction Sequence Diagrams & Lifecycle Specification.docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Master%20Transaction%20Sequence%20Diagrams%20&%20Lifecycle%20Specification.docx.md).
  * Confirm the **exact approved option** and its architectural constraints.
  * Formulate the implementation strategy strictly matching that approved option.

### Step 3: Implementation Plan & Human Approval Gate
* Before touching code, write or update an `implementation_plan.md` artifact detailing:
  * Root cause and systemic impact.
  * Selected approved option with references to the master docs.
  * Forward-looking impact analysis (verifying downstream features like Invoicing, GRA E-VAT, MoMo webhooks, and GL balancing will not break).
  * Step-by-step code and test modifications.
* Present the plan to the user and obtain explicit approval before editing code.

### Step 4: Branch Creation & Test-Driven Code Execution
* Verify a clean working tree: `git status`.
* Create a dedicated task branch off `develop`:
  ```bash
  git checkout develop
  git pull origin develop
  git checkout -b <type>/<sprint>-<task-name>
  ```
  *(Types: `fix/`, `feat/`, `refactor/`, `test/`)*
* Write automated API integration tests first (`APIClient`) to capture the bug or missing feature.
* Implement minimal, robust code adhering strictly to KISS, DRY, and Ghanaian statutory invariants.

### Step 5: SQL Migration Inspection Gate (If Models Mutated)
* If `models.py` was altered:
  ```bash
  uv run python manage.py makemigrations <app_name>
  uv run python manage.py sqlmigrate <app_name> <migration_number>
  ```
* Display the raw SQL output to the user.
* Request user authorization before running `migrate` on PostgreSQL.

### Step 6: Dual-Stage Testing, Linting & User Push Hand-off
* Run fast formatting and linting checks:
  ```bash
  uv run ruff check .
  uv run ruff format .
  ```
* Run Stage 1 fast in-memory SQLite suite:
  ```bash
  uv run python manage.py test apps.<app_name>
  ```
* Run Stage 2 multi-threaded concurrency stress suite (if touching sequences, locks, or ledger):
  ```bash
  USE_POSTGRES_TESTS=1 uv run python manage.py test tests.stress.test_concurrency_stress
  ```
* Ensure 100% test pass rate with zero warnings.
* **Halt and present git commands to the user**:
  ```bash
  git status
  git add <modified_files>
  git commit -m "<type>(<scope>): <concise descriptive message>"
  git push -u origin <branch-name>
  ```
* Wait for the user to push and merge the PR before starting the next task.

---

## 4. Master Remediation Decisions Quick-Reference (The Canonical Truth)

When working on any of the 33 remediation items, use this table as the authoritative summary of **pre-approved options** decided in the master specifications:

| ID | Component / Area | Issue | Approved / Selected Option | Key Document Reference |
|:---|:---|:---|:---|:---|
| **B1** | `invoicing_service.py` | Invoice number `COUNT()` race condition | **Option B**: Dedicated `InvoiceSequence` table with `select_for_update()` row-level locks | Sprint Plan v3.0 §4.1; Comp Fix Plan §B1 |
| **B2** | `apps/invoicing/utils.py` | Luhn payment reference `COUNT()` race condition | **Option A**: Active `.exists()` collision loop with counter increment (Zero Migration) | Comp Fix Plan §B2 |
| **B3** | `ledger/services/ledger.py` | Journal entry sequence `COUNT()` collision | **Option A**: Short UUIDv7 entropy suffix upon collision (Zero Migration) | Comp Fix Plan §B3 |
| **B4** | `ledger/services/ledger.py` | Overzealous `select_for_update()` on Chart of Accounts | **Option A**: Remove `select_for_update()` completely; pure dynamic indexed queries | Comp Fix Plan §B4; Seq Diagrams §1.1 |
| **B5** | `apps/core/middleware.py` | Universal `atomic()` in `TenantSecurityMiddleware` | **Option A**: Remove `atomic()` from middleware; enforce in service layer | Comp Fix Plan §B5 |
| **B6** | `apps/tenancy/views.py` | Missing `POST /api/v1/tenancy/organizations/` | **Option A**: Dedicated atomic endpoint bootstrapping Organization + Chart of Accounts | Sprint Plan v3.0 §4.2; Comp Fix Plan §B6 |
| **B7** | `apps/invoicing/views.py` | Missing Contact CRUD endpoints | **Option A**: Standard DRF `ModelViewSet` at `/api/v1/contacts/` | Comp Fix Plan §B7 |
| **B8** | `apps/invoicing/views.py` | Missing public invoice view (`UUIDv4`) | **Option A**: `PublicInvoiceView` + `EXEMPT_PATH_PREFIXES` in security middleware | Seq Diagrams §1; Comp Fix Plan §B8 |
| **B9** | `authentication/views.py` | Omitted refresh token rotation in cookie update | **Option A**: Pass refreshed refresh token to client cookie if rotation enabled | Comp Fix Plan §B9 |
| **B10**| `apps/core/middleware.py` | CSRF `PermissionDenied` swallowed as 401 | **Option A**: Re-raise `PermissionDenied` to yield HTTP 403 Forbidden | Comp Fix Plan §B10 |
| **B11**| `authentication/views.py` | Hardcoded cookie `path="/api/v1/auth/"` | **Option A**: Configurable `JWT_AUTH_COOKIE_PATH` in `settings.py` defaulting to `"/"` | Comp Fix Plan §B11 |
| **B12**| `ledger/selectors.py` | Redundant `.exists()` before `.aggregate()` | **Option A**: Remove redundant query; rely directly on `aggregate()['balance']` | Comp Fix Plan §B12 |
| **B13**| `invoicing/views.py` | Triplicate manual auditor role checks | **Option A**: Remove manual role checks; rely on DRF permission classes | Comp Fix Plan §B13 |
| **B14**| All Services | Monolithic procedural methods (180–455 lines) | **Option A**: Decompose into private single-responsibility helper methods | Comp Fix Plan §B14 |
| **G1** | `apps/payroll/tasks.py` | Missing outbound bulk MoMo disbursal worker | **Option A**: Async Celery task `execute_bulk_momo_payroll` calling Hubtel B2C | Sequence Diagram 5; Gap Audit §3.1 |
| **G2** | `apps/invoicing/models.py`| Missing CreditNote model & refund endpoint | **Option A**: Discrete `CreditNote` model + reverse double-entry journal schedules | Comp Fix Plan §G2; Sprint Plan §4.3 |
| **G3** | `apps/core/middleware.py` | Missing global HTTP `IdempotencyMiddleware` | **Option A**: Redis NX key cache middleware (120s TTL) on state-mutating requests | Comp Fix Plan §G3; Gap Audit §3.3 |
| **G4** | `apps/ledger/models.py` | Missing `AccountSnapshot` periodic rollup | **Option A**: Monthly snapshot table + Celery task for organizations with >50k entries | Architecture Manual §4.2; Gap Audit §3.4 |
| **G5** | `apps/core/services/sms.py` | Missing dedicated `HubtelSMSClient` | **Option A**: Reusable Hubtel SMS client service with Celery async dispatch | Comp Fix Plan §G5 |
| **G6** | `apps/tenancy/models.py` | Plaintext TIN and Ghana Card storage | **Option B**: Custom Fernet `EncryptedCharField` for TIN and Ghana Card fields | Comp Fix Plan §G6 |

---

## 5. Master Specifications Document Index

All specification files are located in [`docs/`](file:///m:/CODES/Work/magebooks-SAAS/docs):

| Document | Primary Role | Key Usage Instructions |
|:---|:---|:---|
| [`docs/BACKEND_BREAKAGE_AND_KISS_AUDIT.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/BACKEND_BREAKAGE_AND_KISS_AUDIT.md) | **Root-Cause Audit** | Inspect before touching backend code; reveals exact runtime failure modes and race conditions. |
| [`docs/BACKEND_IMPLEMENTATION_GAPS.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/BACKEND_IMPLEMENTATION_GAPS.md) | **Root-Cause Audit** | Inspect for Celery background tasks, scaling patterns, and architectural deferrals. |
| [`docs/CODEBASE_BREAKAGE_AND_KISS_AUDIT.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/CODEBASE_BREAKAGE_AND_KISS_AUDIT.md) | **Root-Cause Audit** | Full-stack audit linking backend breakage to frontend user journeys. |
| [`docs/COMPREHENSIVE_FIX_PLAN.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/COMPREHENSIVE_FIX_PLAN.md) | **Root-Cause & Trade-Offs** | Authoritative 33-item inventory of bugs, refactors, and features with trade-off analysis. |
| [`docs/Mage Books SAAS — Remediation & Hardening Master Sprint Plan (v3.0).docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Remediation%20&%20Hardening%20Master%20Sprint%20Plan%20%28v3.0%29.docx.md) | **Execution Blueprint & Arbitration** | The primary sprint guide defining task branches, sprint phases, and approved options. |
| [`docs/Mage Books SAAS — Comprehensive Fix, Refactor & Feature Remediation Plan.docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Comprehensive%20Fix,%20Refactor%20&%20Feature%20Remediation%20Plan.docx.md) | **Execution Blueprint & Arbitration** | Granular technical implementation specifications for all backend/frontend fixes. |
| [`docs/Mage Books SAAS — Master Transaction Sequence Diagrams & Lifecycle Specification.docx.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Master%20Transaction%20Sequence%20Diagrams%20&%20Lifecycle%20Specification.docx.md) | **Arbitration & Transaction Lifecycles** | State machines, sequence flows, rollbacks, and idempotency guarantees for financial workflows. |
| [`docs/Mage Books SAAS — Master Testing Specification, Edge Cases & Verification Protocols.docx (1).md`](file:///m:/CODES/Work/magebooks-SAAS/docs/Mage%20Books%20SAAS%20%E2%80%94%20Master%20Testing%20Specification,%20Edge%20Cases%20&%20Verification%20Protocols.docx%20%281%29.md) | **Testing & Quality Assurance** | Concurrency harnesses, Boundary Value Analysis, APIClient interface testing, and CI quality gates. |
| [`docs/FRONTEND_BREAKAGE_AND_UX_AUDIT.md`](file:///m:/CODES/Work/magebooks-SAAS/docs/FRONTEND_BREAKAGE_AND_UX_AUDIT.md) | **Execution & Interface Contract** | Frontend route audits, missing views, statutory copy checks, and client-side integration requirements. |

---

## 6. Architecture & Directory Standards

### Unified Configuration (`config/settings.py`)
All settings reside in a single file driven by `django-environ`:
```python
# config/settings.py
from pathlib import Path
import sys
import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_SECRET_KEY=(str, "django-insecure-magebooks-dev-key"),
    DJANGO_ALLOWED_HOSTS=(list, ["*"]),
    DJANGO_CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000"]),
    JWT_AUTH_COOKIE_PATH=(str, "/"),
)
environ.Env.read_env(BASE_DIR / ".env")

# Dynamic Database Routing:
IS_TESTING = "test" in sys.argv or "pytest" in sys.modules
USE_POSTGRES_TESTS = env.bool("USE_POSTGRES_TESTS", default=False)

if IS_TESTING and not USE_POSTGRES_TESTS:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    DATABASES = {
        "default": env.db(
            "DATABASE_URL", default="postgres://postgres:postgres@localhost:5432/magebooks_db"
        )
    }
```

### Target Backend App Architecture
```text
backend/
├── apps/
│   ├── core/           # BaseTenantModel (UUIDv7), IdempotencyMiddleware, PublicShareableMixin
│   ├── authentication/ # CustomUser model, HttpOnly JWT cookies, token rotation
│   ├── tenancy/        # Organization, OrganizationMembership, TenantSecurityMiddleware
│   ├── ledger/         # FiscalCalendar, ChartOfAccounts (1000-5999), JournalEntry, JournalLine
│   ├── tax/            # Act 1151 TaxCalculationEngine (15% VAT, 2.5% NHIL, 2.5% GETFund), GRA tasks
│   ├── invoicing/      # Invoice, InvoiceSequence, CreditNote, Contact, Luhn sequence, Air-gapped PDF
│   ├── payments/       # MomoWebhookView, HMAC verification, Redis idempotency, Suspense 2150
│   ├── payroll/        # PayrollRun, Maker-Checker, Tier 1/2 SSNIT, PAYE, Hubtel B2C Celery worker
│   └── audit/          # Auditor read-only permissions, PBC package compiler, SHA-256 manifest
├── config/
│   ├── settings.py     # Single unified django-environ configuration
│   ├── urls.py         # Root URL routing with EXEMPT_PATH_PREFIXES
│   ├── celery.py       # Celery broker & task configuration
│   └── asgi.py / wsgi.py
├── tests/
│   └── stress/         # Multi-threaded PostgreSQL concurrency test harnesses
└── pyproject.toml      # uv & ruff dependencies and configurations
```

---

## 7. Developer & Agent Command Cheat-Sheet

All commands must be executed within `backend/` using `uv`:

```bash
# 1. Environment & Dependencies
uv sync
uv add <package_name>

# 2. Linting & Formatting
uv run ruff check .
uv run ruff format .

# 3. Running Stage 1 Fast Unit Tests (In-Memory SQLite < 5s)
uv run python manage.py test apps.invoicing
uv run python manage.py test apps.ledger
uv run python manage.py test apps.tenancy

# 4. Running Stage 2 Multi-Threaded Concurrency Tests (PostgreSQL)
USE_POSTGRES_TESTS=1 uv run python manage.py test tests.stress.test_concurrency_stress

# 5. Database Migrations (Inspect First!)
uv run python manage.py makemigrations <app_name>
uv run python manage.py sqlmigrate <app_name> <migration_number>
# Output SQL to user -> Wait for explicit confirmation -> Then apply:
uv run python manage.py migrate

# 6. Development Server
uv run python manage.py runserver 0.0.0.0:8000
```