**MAGE BOOKS SAAS**

**Remediation & Hardening Master Sprint Plan**

*Autonomous Developer & AI Agent Execution Manual:*  
*Feature-by-Feature Branching, Concurrency Hardening, Statutory Compliance Engines, and Multi-Stage CI/CD Testing Protocol*

**Author & Engineering Lead:** Marcel Yeboah  
**Target System:** Mage Books SAAS (Ghana Enterprise Accounting Platform)  
**Version:** 3.0.0 (Unified Hardening & Full-Stack Testing Master Edition)  
**Execution Protocol:** Feature Branching, Dual-Stage Testing Gate & Human-in-the-Loop Push Gate  
**Date:** September 2026

**1\. Critical Operational Directives for Developers & AI Agents**

To ensure disciplined code execution, strict ledger integrity, and zero regressions across the 4 remediation sprints, every human developer and autonomous AI agent (including Antigravity, Cursor, and Claude Code) must strictly adhere to the following seven engineering mandates:

1\. Feature-by-Feature Implementation & Branching Protocol: Development must proceed strictly feature by feature. Developers and agents must never implement multiple features at once or commit directly to the main or develop branches. For each task, create a dedicated branch ('fix/\<sprint\>-\<name\>', 'feat/\<sprint\>-\<name\>', 'refactor/...', 'test/...'). Implement the required code, execute automated unit tests and stress suites, and then halt to let the user review, commit, and push the branch to GitHub. Only upon explicit user confirmation does the agent proceed to the next feature.

2\. Human-in-the-Loop Migration Authorization: Autonomous agents are strictly forbidden from automatically executing 'python manage.py migrate' against development or production PostgreSQL databases. The agent must generate migration scripts using 'makemigrations', inspect the generated SQL using 'sqlmigrate \<app\> \<migration\_number\>', output the SQL inspection to the user, and explicitly pause to ask for confirmation before applying any changes.

3\. Escaping the 'ORM-Only' Testing Trap: Developers and agents are strictly forbidden from writing tests that only instantiate Python models via ORM methods (e.g. 'Organization.objects.create()' or 'Contact.objects.create()') to test business workflows. All mutating user flows must be tested via DRF's APIClient simulating real HTTP requests, headers (X-Organization-ID), JSON payloads, and HTTP status codes to prevent unregistered URL routes.

4\. Dual-Stage CI/CD Testing Gate: Testing must never rely exclusively on in-memory SQLite. While SQLite (:memory:) provides sub-5-second fast lint and unit test feedback in Stage 1, Stage 2 mandates executing integration, row-locking (select\_for\_update), and multi-threaded concurrency suites against a real PostgreSQL 16 container ('postgres:16-alpine') to catch database-specific deadlocks.

5\. Multi-Threaded Concurrency Verification Gate: No P0 concurrency or sequence race condition (Invoice numbers, Luhn references, Journal entry counts, Chart of Accounts locks) can be deemed resolved without passing a multi-threaded stress harness spawning at least 20 parallel threads verifying zero duplicate key IntegrityErrors and strictly gapless sequences under real database transaction isolation.

6\. Strict Statutory Ghanaian Tax & Accounting Compliance: All invoice numbering and tax schedules must strictly comply with the Value Added Tax Act, 2025 (Act 1151\) and Ghana Revenue Authority (GRA) Certified Invoicing System (CIS) regulations. Sequences must be gapless, chronological, and driven by dedicated row-locked counter tables ('InvoiceSequence'). Credit notes must be modeled as discrete statutory instruments with full reversing double-entry schedules.

7\. Single Unified Configuration via django-environ & Modern Tooling: Do not split Django settings into base.py, local.py, or production.py. Maintain exactly ONE clean 'config/settings.py' file utilizing 'django-environ' with explicit type casting. Tooling standardizes on Python 3.12, 'uv' ('uv add', 'uv run', 'uv sync'), and 'ruff' ('ruff check .', 'ruff format .').

**2\. Project Tooling, Environment & Configuration Architecture**

The backend standardizes on Python 3.12, uv, and ruff. The entire runtime configuration is managed through a single 'config/settings.py' file utilizing 'django-environ'. This eliminates environment drift while providing dynamic database routing between in-memory SQLite (fast local unit tests) and PostgreSQL (production and Stage 2 CI concurrency suites):

| \# config/settings.pyfrom pathlib import Pathimport sysimport environBASE\_DIR \= Path(\_\_file\_\_).resolve().parent.parent\# 1\. Initialize environ with explicit type casting and safe fallback defaultsenv \= environ.Env(    DJANGO\_DEBUG=(bool, False),    DJANGO\_SECRET\_KEY=(str, "django-insecure-magebooks-dev-key"),    DJANGO\_ALLOWED\_HOSTS=(list, \["\*"\]),    DJANGO\_CORS\_ALLOWED\_ORIGINS=(list, \["http://localhost:3000"\]),    JWT\_AUTH\_COOKIE\_PATH=(str, "/"),)\# 2\. Read .env file from BASE\_DIR (if present)environ.Env.read\_env(BASE\_DIR / ".env")SECRET\_KEY \= env("DJANGO\_SECRET\_KEY")DEBUG \= env("DJANGO\_DEBUG")ALLOWED\_HOSTS \= env("DJANGO\_ALLOWED\_HOSTS")JWT\_AUTH\_COOKIE\_PATH \= env("JWT\_AUTH\_COOKIE\_PATH")INSTALLED\_APPS \= \[    "django.contrib.admin",    "django.contrib.auth",    "django.contrib.contenttypes",    "django.contrib.sessions",    "django.contrib.messages",    "django.contrib.staticfiles",    \# Third-party extensions    "rest\_framework",    "corsheaders",    "storages",    \# Core Domain Apps    "apps.core",    "apps.authentication",    "apps.tenancy",    "apps.ledger",    "apps.tax",    "apps.invoicing",    "apps.payments",    "apps.payroll",    "apps.audit",\]\# Database Routing: In-Memory SQLite for Fast Stage 1 Tests, PostgreSQL for Dev/Prod & Stage 2 CIIS\_TESTING \= "test" in sys.argv or "pytest" in sys.modulesUSE\_POSTGRES\_TESTS \= env.bool("USE\_POSTGRES\_TESTS", default=False)if IS\_TESTING and not USE\_POSTGRES\_TESTS:    DATABASES \= {        "default": {            "ENGINE": "django.db.backends.sqlite3",            "NAME": ":memory:",        }    }else:    DATABASES \= {        "default": env.db("DATABASE\_URL", default="postgres://postgres:postgres@localhost:5432/magebooks\_db")    }\# Redis Cache for Idempotency Mutex Locks & Celery BrokerCACHES \= {    "default": {        "BACKEND": "django\_redis.cache.RedisCache",        "LOCATION": env("REDIS\_URL", default="redis://127.0.0.1:6379/1"),        "OPTIONS": {            "CLIENT\_CLASS": "django\_redis.client.DefaultClient",        }    }} |
| :---- |

**3\. Feature-by-Feature Git Lifecycle & Hand-off Protocol**

To ensure complete transparency, regression control, and human oversight between the autonomous agent and the project owner, every single remediation task follows a strict four-phase execution loop:

**Phase A: Feature Branch Creation**

Before writing a single line of code for any task, verify that the working tree is clean and branch off the 'develop' branch:

| git checkout developgit pull origin developgit checkout \-b \<type\>/\<sprint\>-\<task-name\>\# Types: fix/ (bugs), feat/ (features), refactor/ (cleanups), test/ (suites), chore/ (config) |
| :---- |

**Phase B: Test-Driven Implementation & Dual-Stage Verification**

Implement the models, services, views, and unit tests. Execute linting, formatting, in-memory unit tests, and multi-threaded concurrency suites:

| \# 1\. Run fast linting and formatting checksuv run ruff check .uv run ruff format .\# 2\. Execute isolated in-memory SQLite test suiteuv run python manage.py test apps.\<app\_name\>\# 3\. Run multi-threaded concurrency stress test (against PostgreSQL)USE\_POSTGRES\_TESTS=1 uv run python manage.py test tests.stress.test\_concurrency\_stress |
| :---- |

**Phase C: Migration Inspection (If Schema Modified)**

If the task introduces or mutates database models (e.g. InvoiceSequence, CreditNote), generate the migration and inspect the raw SQL. The agent must output this SQL to the user and request approval before proceeding:

| uv run python manage.py makemigrations \<app\_name\>uv run python manage.py sqlmigrate \<app\_name\> \<migration\_number\>\# \[PAUSE\]: Output SQL and prompt user for confirmation before running 'migrate'. |
| :---- |

**Phase D: Hand-off, Review & User Push Gate**

Once tests pass, the agent halts and presents the exact git command sequence to the user. The user reviews the git diff and pushes the branch to GitHub:

| git statusgit add .git commit \-m "\<type\>(\<scope\>): \<clear descriptive action\>"git push \-u origin \<type\>/\<sprint\>-\<task-name\> |
| :---- |

The agent waits for the user to confirm: 'Branch pushed, continue to next feature'. The agent then checks out develop and repeats the loop for the next numbered task.

**4\. Master Sprint Overview & Remediation Inventory**

The remediation program organizes all 33 codebase issues, refactors, and architectural gaps alongside 17 dedicated testing suites across 4 distinct execution milestones:

| Sprint | Focus Area | Tasks & Tests | Timeline | Primary Deliverables & Milestones |
| :---- | :---- | :---- | :---- | :---- |
| **Sprint A** | P0 Database Engine, Concurrency & Safety | B1–B5, B9–B10T1.1–T1.5 | Day 1 (AM/PM) | Dedicated InvoiceSequence table (select\_for\_update), Luhn increment loop, journal UUIDv7 entropy, remove COA row locks, unwrap middleware atomic, token rotation pass-through, and 20-thread concurrency stress harnesses. |
| **Sprint B** | Core Features, REST & Onboarding Lifecycle | B6–B8, F1–F4, F9–F10T2.1–T2.5 | Day 2 (AM/PM) | Tenant organization registration API, Contact CRUD ViewSet, Public invoice viewer, Next.js /dashboard/invoices list page, /forgot-password page, Act 1151 GHS 750k copy, monthly return default, and APIClient integration tests. |
| **Sprint C** | Statutory Compliance, Payment Rails & Resilience | F5–F6, G1–G3, G5–G6, B11–B13T3.1–T3.6 | Day 3 (AM/PM) | Celery bulk MoMo payroll disbursements, dedicated CreditNote model with Act 1151 tax reversals, Redis idempotency middleware, Hubtel SMS alerts, PII column encryption, 15-min auto-lock, and tax rounding BVA suites. |
| **Sprint D** | Scalability, Offline PWA & Full-Stack Hardening | F7–F8, F11–F13, G4, B14T4.1–T4.4 | Day 4 (AM/PM) | Encrypted IndexedDB PWA offline invoice drafts, accounting mode sync, wiring 14 dashboard shells, TopNavBar command search and logout, monthly AccountSnapshot rollups, and Dual-Stage CI/CD GitHub Actions pipeline. |

**Master Remediation Inventory (All 33 Code Deliverables)**

| ID | Domain | Target File | Issue Summary | Class | Pri | Selected Strategy |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **B1** | Backend | invoicing\_service.py:150 | Invoice number COUNT() race condition | BUG FIX | P0 | InvoiceSequence row-locked table (select\_for\_update) |
| **B2** | Backend | apps/invoicing/utils.py:189 | Luhn payment reference duplicate collision | BUG FIX | P0 | Active .exists() loop in utils.py (Zero Migration) |
| **B3** | Backend | ledger.py:235 | Journal entry sequence COUNT() collision | BUG FIX | P0 | UUIDv7 entropy suffix upon collision (Zero Migration) |
| **B4** | Backend | ledger.py:210 | Overzealous lock on read-only Chart of Accounts | REFACTOR | P1 | Remove select\_for\_update() entirely on COA |
| **B5** | Backend | middleware.py:188 | Middleware wraps full request in atomic() | REFACTOR | P1 | Remove atomic() from middleware; scope to services |
| **B6** | Backend | apps/tenancy/views.py | Missing POST /organizations/ endpoint | FEATURE | P1 | OrganizationCreateAPIView with atomic COA bootstrap |
| **B7** | Backend | apps/invoicing/views.py | Missing Contact CRUD endpoints (/contacts/) | FEATURE | P1 | Standard DRF ModelViewSet at /api/v1/contacts/ |
| **B8** | Backend | apps/invoicing/views.py | Missing public invoice view & 401 middleware trap | FEATURE | P1 | PublicInvoiceView \+ EXEMPT\_PATH\_PREFIXES exemption |
| **B9** | Backend | authentication/views.py:138 | Refresh token rotation omitted in cookie update | BUG FIX | P2 | Pass rotated refresh\_token to set\_jwt\_cookies |
| **B10** | Backend | middleware.py:223 | CSRF PermissionDenied swallowed as 401 | BUG FIX | P2 | Re-raise PermissionDenied to yield HTTP 403 Forbidden |
| **B11** | Backend | authentication/views.py:57 | Hardcoded cookie path='/api/v1/auth/' | REFACTOR | P2 | Move path to JWT\_AUTH\_COOKIE\_PATH setting (default '/') |
| **B12** | Backend | ledger/selectors.py:264 | Redundant .exists() call before .aggregate() | REFACTOR | P3 | Unconditionally filter journal\_entry\_\_is\_posted=True |
| **B13** | Backend | invoicing/views.py:94 | Triplicate auditor role checks (DRY violation) | REFACTOR | P3 | Declarative IsTenantAuditorReadOnly DRF permission |
| **B14** | Backend | Invoicing/Payroll/Ledger | Monolithic 180–455 line service orchestrators | REFACTOR | P3 | Decompose into private static helper subroutines |
| **G1** | Backend | apps/payroll/tasks.py | Missing Celery bulk MoMo payroll disbursal | FEATURE | High | Celery task calling Paystack/Hubtel Transfers API |
| **G2** | Backend | apps/invoicing/models.py | Missing CreditNote model & reversal endpoint | FEATURE | Med | Dedicated CreditNote model \+ discrete Act 1151 GL reversals |
| **G3** | Backend | apps/core/middleware.py | Missing global Redis IdempotencyMiddleware | FEATURE | Med | Redis cache lock (SET NX EX 120\) on mutating requests |
| **G4** | Backend | apps/ledger/models.py | Missing AccountSnapshot periodic rollup for scale | FEATURE | Low | Monthly AccountSnapshot table \+ rollup Celery task |
| **G5** | Backend | apps/core/services/sms.py | Missing dedicated HubtelSMSClient service | FEATURE | Med | HubtelSMSClient with async Celery dispatch for alerts |
| **G6** | Backend | apps/tenancy/models.py | Missing column encryption for TIN & Ghana Card | FEATURE | Low | Custom Fernet EncryptedCharField using standard crypto |
| **F1** | Frontend | (dashboard)/invoices/page.tsx | Missing Invoice list view route & navigation | FEATURE | P1 | Build /dashboard/invoices list view \+ SideNavBar link |
| **F2** | Frontend | (auth)/forgot-password/page.tsx | Dead /forgot-password route returns 404 | FEATURE | P1 | Build dedicated password reset request page |
| **F3** | Frontend | Step2VATStatus.tsx:78 | Obsolete VAT threshold (displays 200k vs 750k) | CHORE | P2 | Update string constant to statutory GHS 750,000 |
| **F4** | Frontend | onboarding/page.tsx:42 | Default VAT return period set to quarterly | CHORE | P2 | Update onboarding default periodLength to 'monthly' |
| **F5** | Frontend | onboarding/ components | Missing client-side input masks for TIN & Card | FEATURE | P2 | Native regex validation hints and auto-formatting onBlur |
| **F6** | Frontend | (dashboard)/layout.tsx | Missing 15-minute idle inactivity auto-lock | FEATURE | P2 | Custom useIdleTimer hook \+ password/PIN re-auth modal |
| **F7** | Frontend | pwa-cache-encryption.ts | PWA offline cache disconnected from IndexedDB | FEATURE | P3 | Connect WebCrypto helper to idb offline draft queue |
| **F8** | Frontend | settings/mode/page.tsx | Strict/Agile mode toggle not synced to backend | REFACTOR | P3 | Add API mutation calling PATCH /organizations/current/ |
| **F9** | Frontend | (auth)/login & register | Auth forms using mock submit handlers | FEATURE | P3 | Wire login and registration forms with HttpOnly cookies |
| **F10** | Frontend | onboarding/page.tsx | Onboarding wizard finish does not post to API | FEATURE | P3 | Wire handleFinish to POST /api/v1/tenancy/organizations/ |
| **F11** | Frontend | 16 Dashboard Shell Pages | Dashboard shells populated with static mock data | FEATURE | P3 | Phased TanStack Query hookup by operational domain |
| **F12** | Frontend | TopNavBar.tsx | Header has static tenant name, dead search & logout | REFACTOR | P3 | Wire AuthContext org name, working logout & command search |
| **F13** | Frontend | Footer & Modal components | Dead href='\#' links across auth and dashboard | CHORE | P3 | Replace all dead anchors with real routes or disabled states |

**Master Testing & Quality Assurance Architecture (All 17 Test Suites)**

| Test ID | Category | Target Test File | Verification Scope & Edge Case | Sprint |
| :---- | :---- | :---- | :---- | :---- |
| **T1.1** | Stress / Concurrency | tests/stress/test\_concurrency\_stress.py | 20 parallel threads creating invoices simultaneously; verify 0 collisions and gapless sequences | Sprint A |
| **T1.2** | Stress / Concurrency | tests/stress/test\_reference\_collision.py | 10 parallel invoice saves on identical seed count; verify active Luhn .exists() loop | Sprint A |
| **T1.3** | Stress / Concurrency | tests/stress/test\_ledger\_collision.py | Concurrent journal postings on identical fiscal count; verify UUIDv7 entropy resolution | Sprint A |
| **T1.4** | Stress / Concurrency | tests/stress/test\_coa\_lock\_elimination.py | 50 parallel postings touching Cash 1000 & AR 1200; verify 0 timeouts and 0 deadlocks | Sprint A |
| **T1.5** | Integration / Safety | tests/integration/test\_middleware\_transactions.py | Caught inner application exceptions do not abort outer transactions or raise error | Sprint A |
| **T2.1** | Integration / REST | tests/integration/test\_org\_registration\_api.py | POST /api/v1/tenancy/organizations/ provisions Org, OWNER role, and \>=35 COA accounts | Sprint B |
| **T2.2** | Integration / REST | tests/integration/test\_contacts\_api.py | Standard DRF ViewSet /api/v1/contacts/ listing, filtering, and tenant data isolation | Sprint B |
| **T2.3** | Integration / REST | tests/integration/test\_public\_invoice\_api.py | Anonymous GET /invoicing/public/invoices/\<uuid\>/; verify private tenant fields stripped | Sprint B |
| **T2.4** | Security / BOLA | tests/security/test\_middleware\_guards.py | Cross-tenant header spoofing (X-Organization-ID), malformed UUIDs, and expired auditor blocks | Sprint B |
| **T2.5** | Integration / Auth | tests/integration/test\_auth\_token\_rotation.py | Cookie refresh cycle writes new refresh token and rejects blacklisted old tokens | Sprint B |
| **T3.1** | Unit / BVA | tests/unit/test\_tax\_rounding\_bva.py | 50 micro-lines at GHS 0.35; verify multi-line half-up rounding matches GRA Act 1151 clearance | Sprint C |
| **T3.2** | Unit / BVA | tests/unit/test\_ghana\_identifiers\_bva.py | GRA TIN prefixes (C, P, V, G, Q), length bounds, whitespace trimming, and Ghana Card checksum | Sprint C |
| **T3.3** | Unit / BVA | tests/unit/test\_paye\_ssnit\_bva.py | PAYE exact bracket thresholds (GHS 490, 600, 730, 50,000) and SSNIT GHS 42k monthly cap | Sprint C |
| **T3.4** | Stress / BVA | tests/stress/test\_payment\_reconciliation\_bva.py | Overpayment rejection (GHS 1001 on 1000 balance) and 3-split partial payments (333.33 x 3\) | Sprint C |
| **T3.5** | Stress / Security | tests/stress/test\_webhook\_idempotency\_stress.py | 10 parallel identical webhook POST requests; verify Redis atomic lock prevents duplicate GL lines | Sprint C |
| **T3.6** | Integration / Tax | tests/integration/test\_credit\_note\_reversals.py | Credit note double-refund rejection and reversing GL lines (Debit Sales, Debit Tax, Credit AR) | Sprint C |
| **T4.1** | CI/CD / Pipeline | .github/workflows/ci.yml | Dual-Stage GitHub Actions: Stage 1 SQLite fast gate (\<5s) \+ Stage 2 PostgreSQL 16 container | Sprint D |
| **T4.2** | CI/CD / Gate | .github/workflows/ci.yml | Automated migration dry-run gate (makemigrations \--check \--dry-run) halts CI on uncommitted models | Sprint D |
| **T4.3** | CI/CD / Gate | .github/workflows/ci.yml | Migration reversibility verification: executes migrate \<app\> \<previous\> for all new migrations | Sprint D |
| **T4.4** | Unit / Coverage | tests/unit/test\_decomposed\_helpers.py | 100% branch-coverage unit tests for private sub-calculation routines in service classes | Sprint D |

**5\. Sprint A: P0 Database Engine, Concurrency & Transaction Safety**

Sprint Objective: Eliminate all multi-tenant race conditions, deadlocks, transaction poisoning, and authentication cookie traps across 7 discrete code tasks and 5 concurrency stress test harnesses.

**Task A.1 (B1): Dedicated InvoiceSequence Table with Row Locking (select\_for\_update)**

Branch: fix/invoicing-dedicated-sequence-table | Files: apps/invoicing/models.py, apps/invoicing/services/invoicing\_service.py

Problem: Evaluating 'SELECT COUNT(\*)' without row-level locking allows concurrent invoice issuance requests to compute the exact same 'INV-YYYY-XXXXX' string, failing with an unhandled database IntegrityError (HTTP 500).

Implementation: Create InvoiceSequence(organization, year, last\_number) model with unique\_together=('organization', 'year'). Acquire sequence using select\_for\_update().get\_or\_create(...) inside transaction.atomic(), increment last\_number, and format gapless invoice number.

| with transaction.atomic():    seq, \_ \= InvoiceSequence.objects.select\_for\_update().get\_or\_create(        organization=org,        year=invoice\_date.year,        defaults={"last\_number": 0},    )    seq.last\_number \+= 1    seq.save(update\_fields=\["last\_number"\])    invoice.invoice\_number \= f"INV-{org.slug.upper()}-{seq.year}-{seq.last\_number:05d}"\# Verification: uv run python manage.py test apps.invoicing.tests.test\_invoicing\_service |
| :---- |

**Task A.2 (B2): Luhn Payment Reference Active Collision Detection**

Branch: fix/luhn-reference-duplicate-collision | Files: apps/invoicing/utils.py, apps/invoicing/models.py

Problem: Calling generate\_invoice\_payment\_reference using default count() \+ 10001 crashes on unique constraint (organization, payment\_reference) during concurrent invoice saves.

Implementation: Add active .exists() existence loop in generate\_invoice\_payment\_reference that increments seq\_number and recomputes the Luhn check digit until a unique reference is obtained.

| ref \= LuhnValidator.generate\_reference(seq\_number, delimiter="-")while Invoice.objects.filter(organization=organization, payment\_reference=ref).exists():    seq\_number \+= 1    ref \= LuhnValidator.generate\_reference(seq\_number, delimiter="-")\# Verification: uv run python manage.py test apps.invoicing.tests.test\_validators |
| :---- |

**Task A.3 (B3): Journal Entry Number UUIDv7 Collision Entropy Suffix**

Branch: fix/ledger-journal-number-collision | File: apps/ledger/services/ledger.py

Problem: Non-atomic .exists() check in post\_journal\_entry permits identical JE-{year}-{count} sequence keys during concurrent transactions, causing unhandled IntegrityError on commit.

Implementation: Append time-sortable UUIDv7 short entropy suffix (uuid6.uuid7().hex\[:8\].upper()) when collision is detected or upon retry.

| base\_entry\_number \= f"JE-{entry\_date.year}-{entry\_count:05d}"if JournalEntry.objects.filter(organization=organization, entry\_number=base\_entry\_number).exists():    entry\_number \= f"{base\_entry\_number}-{uuid6.uuid7().hex\[:8\].upper()}"else:    entry\_number \= base\_entry\_number\# Verification: uv run python manage.py test apps.ledger.tests.test\_ledger |
| :---- |

**Task A.4 (B4): Remove Pessimistic Lock on Chart of Accounts**

Branch: refactor/ledger-coa-lock-elimination | File: apps/ledger/services/ledger.py

Problem: select\_for\_update() on ChartOfAccounts locks master accounts (Cash 1000, AR 1200\) during postings, serializing concurrent writes across the entire organization and triggering HTTP 504 timeouts.

Implementation: Replace select\_for\_update() with a standard read query. Account rows are read-only metadata records; balances are calculated dynamically from immutable journal lines.

| accounts \= {    acc.id: acc    for acc in ChartOfAccounts.objects.filter(        id\_\_in=account\_ids,        organization=organization,        is\_active=True    )}\# Verification: uv run python manage.py test apps.ledger.tests.test\_ledger |
| :---- |

**Task A.5 (B5): Scope transaction.atomic() to Domain Services & Remove from Middleware**

Branch: refactor/tenancy-middleware-transaction-unwrapping | Files: apps/tenancy/middleware.py, domain services

Problem: Wrapping entire request execution in transaction.atomic() causes internal exception handling to abort the outer transaction, raising TransactionManagementError and holding connections across network I/O.

Implementation: Remove transaction.atomic() from TenantMiddleware. Scope atomicity strictly to domain services (post\_journal\_entry, reconcile\_payment, create\_invoice).

**Task A.6 (B9): SimpleJWT Token Rotation Pass-Through in set\_jwt\_cookies**

Branch: fix/auth-refresh-token-cookie-rotation | File: apps/authentication/views.py

Problem: set\_jwt\_cookies omits refresh\_token when rotation is active, blacklisting old tokens and logging users out on the very next refresh.

Implementation: Extract data.get('refresh') from TokenRefreshView response and pass to set\_jwt\_cookies.

**Task A.7 (B10): Unmask CSRF Failures to Return HTTP 403 Forbidden**

Branch: fix/tenancy-middleware-csrf-unmasking | File: apps/tenancy/middleware.py

Problem: Swallowing broad Exception in \_resolve\_jwt\_user catches PermissionDenied from CSRF checks and reports HTTP 401 instead of HTTP 403 CSRF failure.

Implementation: Catch specific (InvalidToken, TokenError) and explicitly re-raise PermissionDenied.

**Task A.8 (T1.1–T1.5): Multi-Threaded Concurrency Test Harness & Stress Suites**

Branch: test/concurrency-and-stress-harness | Directory: backend/tests/stress/ & backend/tests/integration/

Implementation: Build multi-threaded test harness spawning 20 concurrent threads issuing invoices simultaneously for the same tenant. Verify 20 unique, gapless numbers with zero IntegrityErrors.

| class ConcurrencyStressTests(TransactionTestCase):    def test\_20\_parallel\_invoice\_creations\_generate\_gapless\_unique\_numbers(self):        num\_threads \= 20        date\_today \= datetime.date(2026, 9, 28\)        def create\_single(idx):            connection.close()            return InvoicingService.create\_invoice(                organization=self.org, issue\_date=date\_today,                items=\[{"description": f"Item {idx}", "unit\_price": Decimal("50.00"), "quantity": 1}\],            )        with concurrent.futures.ThreadPoolExecutor(max\_workers=num\_threads) as executor:            invoices \= list(executor.map(create\_single, range(num\_threads)))        self.assertEqual(len(set(inv.invoice\_number for inv in invoices)), num\_threads)\# Verification: uv run python manage.py test tests/stress/ tests/integration/ |
| :---- |

| Task ID | Git Branch | Implementation Scope & Deliverables | Verification & Test Suite |
| :---- | :---- | :---- | :---- |
| **Task A.1** | fix/invoicing-dedicated-sequence-table | Implement InvoiceSequence model with select\_for\_update() row locking; generate and inspect migration. | test\_concurrency\_stress: 20 threads produce 20 unique gapless invoices with 0 collisions. |
| **Task A.2** | fix/luhn-reference-duplicate-collision | Implement active .exists() existence loop in generate\_invoice\_payment\_reference (Zero Migration). | test\_reference\_collision: 10 parallel saves generate 10 unique valid mod-10 Luhn codes. |
| **Task A.3** | fix/ledger-journal-number-collision | Implement UUIDv7 short entropy suffix on collision detection in post\_journal\_entry (Zero Migration). | test\_ledger\_collision: Concurrent journal postings assign time-sortable entropy suffixes. |
| **Task A.4** | refactor/ledger-coa-lock-elimination | Remove select\_for\_update() on read-only ChartOfAccounts during journal entry postings. | test\_coa\_lock\_elimination: 50 concurrent postings complete in \<2s with 0 timeouts. |
| **Task A.5** | refactor/tenancy-middleware-transaction-unwrapping | Remove transaction.atomic() from TenantMiddleware; scope atomicity to domain service methods. | test\_middleware\_transactions: Handled inner exceptions do not abort outer transaction. |
| **Task A.6** | fix/auth-refresh-token-cookie-rotation | Pass rotated refresh\_token to set\_jwt\_cookies in CookieTokenRefreshView response. | test\_auth\_token\_rotation: Verify new refresh token stored in cookie; old token blacklisted. |
| **Task A.7** | fix/tenancy-middleware-csrf-unmasking | Re-raise PermissionDenied in TenantMiddleware to preserve HTTP 403 CSRF error semantics. | test\_csrf\_error\_unmasking: Invalid CSRF token returns 403 Forbidden, not 401 Unauthorized. |
| **Task A.8** | test/concurrency-and-stress-harness | Implement multi-threaded stress suites (T1.1–T1.5) testing real PostgreSQL row locking. | 359/359 existing tests pass \+ 5 new multi-threaded stress test suites pass 100% green. |

**6\. Sprint B: Core Features, REST Interfaces & Onboarding Lifecycle**

Sprint Objective: Connect the full user journey from signup and onboarding to invoice viewing across 9 code tasks and 5 REST integration test suites.

**Task B.1 (B6): Tenant Organization Registration REST API & COA Bootstrap**

Branch: feat/tenancy-organization-registration-api | Files: apps/tenancy/views.py, apps/tenancy/urls.py

Implementation: Expose POST /api/v1/tenancy/organizations/. Inside an atomic block, create Organization, assign user as OWNER, and execute bootstrap\_ghana\_chart\_of\_accounts(org).

| class OrganizationCreateAPIView(generics.CreateAPIView):    permission\_classes \= \[permissions.IsAuthenticated\]    serializer\_class \= OrganizationCreateSerializer    @transaction.atomic    def perform\_create(self, serializer):        org \= serializer.save()        OrganizationMembership.objects.create(organization=org, user=self.request.user, role=Role.OWNER)        bootstrap\_ghana\_chart\_of\_accounts(org)\# Verification: uv run python manage.py test tests/integration/test\_org\_registration\_api.py |
| :---- |

**Task B.2 (B7): Contact CRUD REST Endpoints (/api/v1/contacts/)**

Branch: feat/invoicing-contacts-rest-api | Files: apps/invoicing/views.py, apps/invoicing/urls.py

Implementation: Implement ContactViewSet(viewsets.ModelViewSet) scoped to request.organization. Register on router at /api/v1/contacts/.

**Task B.3 (B8): Public Invoice Shareable Viewer & Middleware Security Exemption**

Branch: feat/invoicing-public-invoice-viewer | Files: apps/invoicing/views.py, apps/tenancy/middleware.py

Implementation: Create PublicInvoiceView(generics.RetrieveAPIView) lookup on share\_token (UUID4). Add /api/v1/invoicing/public/ to EXEMPT\_PATH\_PREFIXES in TenantMiddleware.

**Task B.4 (F1): Next.js Invoice List View Route (/dashboard/invoices) & Navigation**

Branch: feat/frontend-dashboard-invoices-page | Files: frontend/src/app/(dashboard)/invoices/page.tsx, SideNavBar.tsx

Implementation: Create full invoice management view with KPI cards (Outstanding, Overdue, Paid), filterable data table, and action menu. Wire Invoices link into SideNavBar.tsx.

**Task B.5 (F2): Password Reset Request Page (/forgot-password)**

Branch: feat/frontend-forgot-password-route | File: frontend/src/app/(auth)/forgot-password/page.tsx

Implementation: Build dedicated password reset request page submitting to POST /api/v1/auth/password-reset/. Eliminates dead 404 link on login screen.

**Task B.6 (F3): Update Statutory VAT Registration Threshold to GHS 750,000**

Branch: fix/frontend-vat-threshold-act-1151 | File: frontend/src/components/onboarding/Step2VATStatus.tsx

Implementation: Update copy constant from GHS 200,000 to statutory Act 1151 threshold: GHS 750,000.

**Task B.7 (F4): Align Default Tax Period Cadence to Monthly Filing**

Branch: fix/frontend-onboarding-monthly-cadence | File: frontend/src/components/onboarding/Step4FiscalCalendar.tsx

Implementation: Change default onboarding periodLength state from 'quarterly' to 'monthly' (GRA VAT/PAYE cadence).

**Task B.8 (F9): Wire Login and Registration Forms with HttpOnly Cookies**

Branch: feat/frontend-wire-auth-forms | Files: frontend/src/app/(auth)/login/page.tsx, register/page.tsx

Implementation: Replace mock setTimeout submit handlers with real apiClient.post('/api/v1/auth/login/') with credentials: 'include'.

**Task B.9 (F10): Wire Onboarding Wizard Submission to Registration API**

Branch: feat/frontend-wire-onboarding-submission | File: frontend/src/app/onboarding/page.tsx

Implementation: Wire handleFinish to submit collected business details to POST /api/v1/tenancy/organizations/.

**Task B.10 (T2.1–T2.5): REST APIClient Integration & Middleware Guard Test Suites**

Branch: test/rest-api-and-middleware-integration | Directory: backend/tests/integration/ & backend/tests/security/

Implementation: Full APIClient suites testing Organization registration, Contacts CRUD, Public Invoice data sanitization, cross-tenant header spoofing (BOLA), and SimpleJWT cookie rotation.

| Task ID | Git Branch | Implementation Scope & Deliverables | Verification & Test Suite |
| :---- | :---- | :---- | :---- |
| **Task B.1** | feat/tenancy-organization-registration-api | Implement POST /api/v1/tenancy/organizations/ with atomic tenant creation and COA bootstrap. | test\_org\_registration\_api: Verifies Org, OWNER membership, and \>=35 COA accounts seeded. |
| **Task B.2** | feat/invoicing-contacts-rest-api | Implement ContactViewSet and register router at /api/v1/contacts/ scoped to organization. | test\_contacts\_api: Verifies GET/POST /contacts/ with automatic tenant data isolation. |
| **Task B.3** | feat/invoicing-public-invoice-viewer | Implement PublicInvoiceView and add /api/v1/invoicing/public/ to EXEMPT\_PATH\_PREFIXES. | test\_public\_invoice\_api: Anonymous GET succeeds; private tenant ledger fields stripped. |
| **Task B.4** | feat/frontend-dashboard-invoices-page | Build Next.js /dashboard/invoices list page with summary KPI cards and wire SideNavBar. | npm run build: Builds cleanly with zero TypeScript errors. |
| **Task B.5** | feat/frontend-forgot-password-route | Build /forgot-password request page submitting to POST /api/v1/auth/password-reset/. | Browser testing: Eliminates 404; submits reset link cleanly. |
| **Task B.6** | fix/frontend-vat-threshold-act-1151 | Update obsolete GHS 200,000 threshold copy to statutory Act 1151 threshold (GHS 750,000). | UI verification: Displays GHS 750,000 statutory threshold in Step 2\. |
| **Task B.7** | fix/frontend-onboarding-monthly-cadence | Change default onboarding periodLength from 'quarterly' to 'monthly' in Step 4\. | UI verification: Defaults to monthly statutory filing cadence. |
| **Task B.8** | feat/frontend-wire-auth-forms | Connect login and registration forms to backend API with HttpOnly JWT cookie handling. | Browser testing: Real login establishes JWT session and redirects to dashboard. |
| **Task B.9** | feat/frontend-wire-onboarding-submission | Connect onboarding wizard handleFinish to POST /api/v1/tenancy/organizations/. | Browser testing: Completing onboarding creates tenant and seeds COA in DB. |
| **Task B.10** | test/rest-api-and-middleware-integration | Execute full APIClient integration and multi-tenant security test suites (T2.1–T2.5). | All 5 integration test suites pass 100% green against REST endpoints. |

**7\. Sprint C: Statutory Compliance, Payment Rails & Resilience**

Sprint Objective: Implement automated payroll disbursements, statutory credit notes, global idempotency, SMS alerts, PII encryption, and statutory boundary value analysis suites across 10 code tasks and 6 QA test suites.

**Task C.1 (G1): Celery Bulk Mobile Money Payroll Disbursement Worker**

Branch: feat/payroll-celery-bulk-momo-disbursement | Files: apps/payroll/tasks.py, services/disbursement.py

Implementation: Celery task disburse\_payroll\_run\_task calling Paystack/Hubtel Transfers API with idempotency key (PAY-{payslip.id}). Updates status to DISBURSED and posts secondary GL entries (Dr 2110 Salaries Payable, Cr 1020/1030 Bank/MoMo).

**Task C.2 (G2): Dedicated CreditNote Model & Reversing Ledger Engine**

Branch: feat/invoicing-statutory-credit-notes | Files: apps/invoicing/models.py, services/credit\_note\_service.py

Implementation: Model CreditNote and CreditNoteLine with discrete reversing schedules for 15% VAT, 2.5% NHIL, and 2.5% GETFund. Posts reversing GL entry: Debit Sales 4000, Debit Taxes 2150/2141/2142, Credit AR 1200\.

**Task C.3 (G3): Global Redis HTTP Idempotency-Key Middleware**

Branch: feat/core-redis-idempotency-middleware | File: apps/core/middleware.py

Implementation: Inspects incoming Idempotency-Key header on mutating requests (POST/PUT/PATCH). Acquires atomic Redis lock (SET NX EX 120), caches HTTP responses, and replays cached response on re-submission.

**Task C.4 (G5): Dedicated HubtelSMSClient Service & Async Celery Dispatch**

Branch: feat/core-hubtel-sms-service | Files: apps/core/services/sms.py, apps/core/tasks.py

Implementation: Build HubtelSMSClient with connection pooling (httpx.Client) and rate limiting. Dispatches automated SMS alerts with payment reference and checkout URL upon invoice approval.

**Task C.5 (G6): PII Column-Level Encryption for TIN and Ghana Card**

Branch: feat/tenancy-pii-column-encryption | Files: apps/core/fields.py, apps/tenancy/models.py

Implementation: Implement EncryptedCharField using Python standard cryptography.fernet.Fernet to transparently encrypt/decrypt TIN and Ghana Card NIA numbers at rest in PostgreSQL.

**Task C.6 (F5): Ghanaian TIN and Ghana Card Client-Side Input Formatting**

Branch: feat/frontend-statutory-input-masks | Files: frontend/src/lib/formatters.ts, Step1CompanyDetails.tsx

Implementation: Add auto-formatting on onBlur for Ghana Card (GHA-XXXXXXXXX-X) and TIN (C0012345678) with real-time visual validation feedback.

**Task C.7 (F6): 15-Minute Inactivity Screen Auto-Lock Hook & Modal**

Branch: feat/frontend-15min-inactivity-lock | Files: frontend/src/hooks/useIdleTimer.ts, (dashboard)/layout.tsx

Implementation: Add lightweight useIdleTimer(15 \* 60 \* 1000). Renders blurred backdrop modal prompting for password to unlock without losing unsaved form data.

**Task C.8 (B11): Parameterize Cookie Path via JWT\_AUTH\_COOKIE\_PATH**

Branch: refactor/auth-cookie-path-setting | Files: apps/authentication/views.py, config/settings.py

Implementation: Replace hardcoded path='/api/v1/auth/' with path=settings.JWT\_AUTH\_COOKIE\_PATH (defaulting safely to '/').

**Task C.9 (B12): Eliminate Redundant .exists() Query in Ledger Selectors**

Branch: refactor/ledger-balance-selector-optimization | File: apps/ledger/selectors.py

Implementation: Remove .exists() pre-check query. Unconditionally execute single aggregation query filtered by journal\_entry\_\_is\_posted=True, cutting DB roundtrips by 50%.

**Task C.10 (B13): Declarative IsTenantAuditorReadOnly Permission Class**

Branch: refactor/invoicing-auditor-permission-dry | Files: apps/tenancy/permissions.py, apps/invoicing/views.py

Implementation: Centralize auditor read-only write-blocking in reusable DRF IsTenantAuditorReadOnly permission class; remove manual checks from view handler bodies.

**Task C.11 (T3.1–T3.6): Boundary Value Analysis & Webhook Replay Stress Suites**

Branch: test/statutory-bva-and-reconciliation-suites | Directory: backend/tests/unit/ & backend/tests/stress/

Implementation: Multi-line pesewa rounding boundary tests (50 micro-lines at GHS 0.35 under Act 1151), Ghana identifier regex/checksum tests, PAYE/SSNIT cap boundaries, boundary overpayment rejection, and 10-parallel webhook replay stress tests.

| Task ID | Git Branch | Implementation Scope & Deliverables | Verification & Test Suite |
| :---- | :---- | :---- | :---- |
| **Task C.1** | feat/payroll-celery-bulk-momo-disbursement | Celery task disburse\_payroll\_run\_task calling Paystack/Hubtel Transfers API with batch tracking. | test\_payroll\_disbursement: Successfully initiates B2C payouts; posts secondary GL lines. |
| **Task C.2** | feat/invoicing-statutory-credit-notes | Implement CreditNote model and service posting reversing double-entry lines under Act 1151\. | test\_credit\_note\_reversals: Verifies reversing GL lines and double-refund prevention. |
| **Task C.3** | feat/core-redis-idempotency-middleware | Global Redis IdempotencyMiddleware (SET NX EX 120\) on mutating REST requests. | test\_webhook\_idempotency\_stress: 10 parallel identical requests commit DB exactly once. |
| **Task C.4** | feat/core-hubtel-sms-service | Dedicated HubtelSMSClient service with connection pooling and async Celery dispatch. | test\_sms\_dispatch: Invoice approval enqueues SMS task; MockHubtelClient verifies payload. |
| **Task C.5** | feat/tenancy-pii-column-encryption | Implement EncryptedCharField using Python Fernet for TIN and Ghana Card PII at rest. | test\_pii\_encryption: Raw SQL query returns ciphertext; ORM access returns plaintext. |
| **Task C.6** | feat/frontend-statutory-input-masks | Client-side input masks and auto-formatting on onBlur for Ghana Card and TIN. | UI verification: Auto-inserts GHA- and hyphens; flags invalid TIN prefixes. |
| **Task C.7** | feat/frontend-15min-inactivity-lock | 15-minute idle inactivity auto-lock hook and blurred backdrop password unlock modal. | UI verification: 15-minute idle timeout triggers lock modal; preserves form state. |
| **Task C.8** | refactor/auth-cookie-path-setting | Parameterize cookie path via settings.JWT\_AUTH\_COOKIE\_PATH (default '/'). | test\_cookie\_paths: Reverse proxy rewrites attach cookie seamlessly. |
| **Task C.9** | refactor/ledger-balance-selector-optimization | Remove redundant .exists() pre-check query in get\_account\_balance selector. | test\_balance\_selectors: Query count reduced by 50% on Trial Balance calculation. |
| **Task C.10** | refactor/invoicing-auditor-permission-dry | Enforce auditor write blocking strictly via DRF IsTenantAuditorReadOnly class. | test\_auditor\_permissions: Declarative permission blocks POST/PUT/PATCH/DELETE. |
| **Task C.11** | test/statutory-bva-and-reconciliation-suites | Execute BVA suites (T3.1–T3.6): tax rounding, TIN/Card boundaries, PAYE caps, overpayments. | All 6 BVA and stress suites pass 100% green against statutory calculation rules. |

**8\. Sprint D: Scalability, Offline PWA & Full-Stack Hardening**

Sprint Objective: Scale ledger aggregation, connect PWA encrypted offline drafting, wire remaining 14 dashboard shells, and establish dual-stage CI/CD quality gates across 7 code tasks and 4 CI/CD testing gates.

**Task D.1 (F7): Offline PWA Draft Storage with Encrypted IndexedDB (idb)**

Branch: feat/frontend-offline-pwa-encrypted-cache | Files: frontend/src/lib/offline-storage.ts, pwa-cache-encryption.ts

Implementation: Connect WebCrypto AES-GCM encryption helper to idb offline draft queue. Encrypts drafts on device; auto-syncs to POST /api/v1/invoicing/invoices/ on network reconnect.

**Task D.2 (F8): Synchronize Accounting Mode Preference with Backend API**

Branch: refactor/frontend-sync-accounting-mode | File: frontend/src/contexts/ModeContext.tsx

Implementation: Update mode switch toggle to call PATCH /api/v1/tenancy/organizations/current/ with {accounting\_mode: mode} so preferences persist across devices.

**Task D.3 (F11): Connect 14 Dashboard Shell Subpages to Domain APIs**

Branch: feat/frontend-wire-dashboard-shell-pages | Directory: frontend/src/app/(dashboard)/

Implementation: Phased TanStack Query hookup across Banking (/banking/accounts/), Ledger (/ledger/accounts/), Payroll (/payroll/runs/), and Reports (/reports/trial-balance/).

**Task D.4 (F12): Dynamic TopNavBar Hub, Command Palette & Logout Handler**

Branch: refactor/frontend-dynamic-topnavbar-hub | File: frontend/src/components/dashboard/TopNavBar.tsx

Implementation: Read current tenant name from AuthContext, implement Command Palette modal (Cmd \+ K) indexing routes/invoices, and wire logout button to call POST /api/v1/auth/logout/.

**Task D.5 (F13): Replace Dead Anchors (href='\#') with Real Routes**

Branch: chore/frontend-replace-dead-anchor-links | Files: Footer, Auth, and Modal components

Implementation: Replace all href='\#' dead links with valid routes (/legal/terms, /legal/privacy, /support) or disabled button states.

**Task D.6 (G4): Materialized AccountSnapshot Monthly Rollup for Scale**

Branch: feat/ledger-materialized-account-snapshots | Files: apps/ledger/models.py, apps/ledger/tasks.py

Implementation: Create AccountSnapshot(account, period\_end, closing\_balance). Scheduled Celery task rolls up closed monthly balances, keeping query latency \<10ms for tenants with \>50,000 transactions.

**Task D.7 (B14): Decompose Monolithic Procedural Functions into Private Helpers**

Branch: refactor/core-decompose-monolithic-services | Target Files: Invoicing, Payments, Ledger, Payroll services

Implementation: Decompose 180–455 line service orchestrators into focused private static helpers (\_build\_pdf\_header(), \_apply\_payment\_split()) preserving identical public signatures and 100% test compatibility.

**Task D.8 (T4.1–T4.4): Dual-Stage CI/CD GitHub Actions & PostgreSQL 16 Service Container**

Branch: chore/ci-dual-stage-postgres-pipeline | File: .github/workflows/ci.yml

Implementation: Configure Stage 1 fast SQLite gate (\<5s) and Stage 2 real PostgreSQL 16 container ('postgres:16-alpine'). Add migration dry-run check (makemigrations \--check \--dry-run) and migration rollback test.

| \# .github/workflows/ci.yml Stage 2 Snippetservices:  postgres:    image: postgres:16-alpine    env:      POSTGRES\_DB: magebooks\_test      POSTGRES\_USER: postgres      POSTGRES\_PASSWORD: postgrespassword    ports: \[5432:5432\]steps:  \- run: uv run python manage.py makemigrations \--check \--dry-run  \- run: uv run python manage.py migrate  \- run: uv run python manage.py test tests/stress/ tests/integration/ |
| :---- |

| Task ID | Git Branch | Implementation Scope & Deliverables | Verification & Test Suite |
| :---- | :---- | :---- | :---- |
| **Task D.1** | feat/frontend-offline-pwa-encrypted-cache | Connect WebCrypto helper to idb offline draft queue with background sync on reconnect. | Browser testing: Draft created offline; auto-syncs to backend when connection restored. |
| **Task D.2** | refactor/frontend-sync-accounting-mode | Wire mode switch toggle to PATCH /api/v1/tenancy/organizations/current/. | Browser testing: Mode persisted to PostgreSQL tenant record; survives cross-device login. |
| **Task D.3** | feat/frontend-wire-dashboard-shell-pages | Phased TanStack Query hookup across Banking, Ledger, Payroll, and Reports pages. | UI verification: Replaces static mock tables with dynamic tenant API data. |
| **Task D.4** | refactor/frontend-dynamic-topnavbar-hub | Wire tenant name from AuthContext, working logout API, and Cmd+K command palette. | Browser testing: Displays dynamic org name; working logout clears cookies; Cmd+K searches. |
| **Task D.5** | chore/frontend-replace-dead-anchor-links | Replace all href='\#' dead links with valid legal routes or disabled button states. | Audit check: Zero href='\#' dead anchors remain across auth, footer, and dashboard. |
| **Task D.6** | feat/ledger-materialized-account-snapshots | AccountSnapshot monthly rollup table and period-closing background worker. | test\_snapshots: Closing balances rolled up monthly; query latency \<10ms over 50k lines. |
| **Task D.7** | refactor/core-decompose-monolithic-services | Decompose 180–455 line service orchestrators into focused private static helpers. | Unit tests: 100% branch-coverage on private calculation and validation subroutines. |
| **Task D.8** | chore/ci-dual-stage-postgres-pipeline | Dual-Stage GitHub Actions pipeline with PostgreSQL 16 container & migration dry-run. | CI verification: Dual-stage pipeline passes green on both SQLite and PostgreSQL 16\. |

**9\. Definition of Done (DoD) per Feature Branch & Master Gate**

Before requesting user review and pushing any feature branch, the developer or agent must verify that the task satisfies all six criteria of the Definition of Done:

1\. Complete Implementation: All models, services, views, serializers, and adapters defined in the task scope are fully written and free of placeholders, mock stubs, or TODO comments in production paths.

2\. 100% Test Pass Rate: All automated unit and integration tests run green against in-memory SQLite ('python manage.py test apps.\<app\_name\>'). Total execution time remains under 5 seconds.

3\. Concurrency Stress Verified (P0 Tasks): For all sequence and locking tasks, multi-threaded concurrency suites pass with at least 20 parallel threads against PostgreSQL with zero duplicate key exceptions.

4\. Linting & Formatting Compliance: 'ruff check .' and 'ruff format .' report zero errors, warnings, or unformatted files across all 10 Django domain applications.

5\. Migration Inspection Completed: If database models were added or modified, 'sqlmigrate' was executed, raw SQL output was reviewed by the user, and explicit authorization was granted before running 'migrate'.

6\. Clean Hand-off: Git status is clean, commit message adheres to Conventional Commits ('fix(\<scope\>): \<description\>' or 'feat(\<scope\>): \<description\>'), and user pushes branch to GitHub before checking out develop for the next feature.

**Master Remediation Gate Verification Checklist**

Before considering the entire remediation and hardening master sprint complete, verify:

| Audit Verification Gate | Target Standard | Automated Verification Command & Status |
| :---- | :---- | :---- |
| **All 33 Code Tasks Merged** | 100% merged into develop | git branch \--merged develop (33 feature branches merged) |
| **All 17 QA Suites Passing** | 100% passing green | uv run python manage.py test (359 base \+ 17 new QA suites) |
| **Concurrency Stress Verified** | 0 collisions under 20 threads | USE\_POSTGRES\_TESTS=1 uv run python manage.py test tests.stress |
| **Dual-Stage CI/CD Pipeline** | Green on GitHub Actions | .github/workflows/ci.yml runs SQLite \+ PostgreSQL 16 container |
| **Migration Dry-Run Gate** | 0 uncommitted model changes | uv run python manage.py makemigrations \--check \--dry-run |
| **Security Vulnerability Scan** | 0 High / Medium alerts | uv run bandit \-r apps/ \-ll (Reports 0 vulnerabilities) |
| **Secret Leak Prevention** | 0 exposed keys/credentials | gitleaks detect \--source . \-v (Reports 0 leaks) |
| **Code Quality & Linter** | 0 errors, 0 warnings | uv run ruff check . && uv run ruff format \--check . |
| **Frontend Next.js Build** | 0 TypeScript errors | cd frontend && npm run build (Static generation successful) |

