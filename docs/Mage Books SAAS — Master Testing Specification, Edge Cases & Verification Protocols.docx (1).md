**MAGE BOOKS SAAS**

**Master Testing Specification, Edge Cases & Verification Protocols**

*Comprehensive Quality Assurance Manual, Boundary Value Analysis (BVA), Multi-Threaded Concurrency Test Harnesses, Integration Test Suites, and Multi-Stage CI/CD Quality Gates*

**Author & Engineering Lead:** Marcel Yeboah  
**Target System:** Mage Books SAAS (Ghana Enterprise Accounting Platform)  
**Document Classification:** Internal Technical Specification & Engineering Record  
**Date:** September 2026

**Mage Books SAAS — Master Testing Specification, Edge Cases & Verification Protocols**

| *\*\*Comprehensive Quality Assurance Engineering Manual, Boundary Value Analysis (BVA), Multi-Threaded Concurrency Test Harnesses, Integration Test Suites, and Multi-Stage CI/CD Quality Gates.\*\*  \*\*Target System:\*\* Mage Books SAAS (Ghana Enterprise Accounting Platform) \*\*Status:\*\* Active Engineering Protocol & Test Specification \*\*Author & Engineering Lead:\*\* Marcel Yeboah \*\*Date:\*\* September 2026 | \*\*Version:\*\* 2.0.0 (Hardened Concurrency & Full-Stack Interface Edition)* |
| :---- |

**Table of Contents**

1. Executive Summary & Quality Grading  
2. Step 2: Expanded Unit Testing & Boundary Value Analysis (BVA)

* 2.1 Sequence Generation & Fiscal Year Rollover Boundaries  
* 2.2 Statutory Tax Rounding & Multi-Line Pesewa Discrepancies (Act 1151\)  
* 2.3 Ghanaian Statutory Identifier Formats & Checksum Boundaries  
* 2.4 PAYE & SSNIT Tier 1/2 Withholding Threshold Boundaries  
* 2.5 Invoicing State Machine & Non-Negative Valuation Boundaries

3. Step 3: Integration & Interface Testing (Escaping the ORM-Only Trap)

* 3.1 Full REST HTTP Request/Response Testing via APIClient  
* 3.2 Multi-Tenant Middleware Guard Pipeline Testing  
* 3.3 Public Unauthenticated Shareable Access & Security Exemption Tests  
* 3.4 SimpleJWT Cookie Lifecycle & Token Rotation Integration  
* 3.5 Multi-Stage Tenant Provisioning & COA Bootstrap Integration

4. Step 4: System, Security, Concurrency & Stress Testing

* 4.1 Multi-Threaded Concurrency Test Harness (PostgreSQL Row Locks)  
* 4.2 Chart of Accounts Unlocked Concurrency Stress Test  
* 4.3 Boundary Overpayment & Micro-Split Reconciliation Tests  
* 4.4 Webhook Idempotency & Replay Attack Stress Verification  
* 4.5 Credit Note Statutory Inversion & Double-Refund Stress

5. Step 5: Empirical Debugging Verification & Regression Anchors

* 5.1 Regression Test Matrix for All 14 Backend Breakage Points

6. Step 6: CI/CD Quality Gates & Dual-Stage Environment Testing

* 6.1 Stage 1: Ultra-Fast In-Memory SQLite Gate (\<5s)  
* 6.2 Stage 2: Real PostgreSQL 16 Service Container Integration  
* 6.3 Automated Migration Integrity & Reversibility Check Gate

7. Consolidated Sprint Integration Matrix

**1\. Executive Summary & Quality Grading**

The Mage Books SAAS backend boasts **359 automated tests passing with 100% success**, zero Ruff linter warnings, and zero Bandit AST security vulnerabilities. However, an exhaustive audit across the codebase, sequence diagrams, and architecture manuals revealed critical blind spots resulting from the **"ORM-Only Testing Trap"** and **"Single-Threaded SQLite Isolation"**:

| Testing Stage | Current Status | Grade | Reality Check & Findings |
| :---- | :---- | :---- | :---- |
| **Step 2: Unit Testing & Boundary Value Analysis (BVA)** | 359 Tests Passing | **B+** | **Strong on financial math, weak on sequence boundaries.** Tested 15% VAT, 2.5% NHIL, and PAYE brackets down to the pesewa. Missed sequence boundary collisions (count() \+ 1) under concurrent requests, fiscal year rollover boundaries, and multi-line pesewa half-up rounding edge cases. |
| **Step 3: Integration & Interface Testing** | Service-to-DB tests pass | **C+** | **Fell into the "ORM-Only" testing trap.** Tests used Organization.objects.create() and Contact.objects.create() in Python, which masked the fact that POST /api/v1/tenancy/organizations/ and /api/v1/contacts/ REST endpoints were never registered in URLs\! |
| **Step 4: System, Security & Stress Testing** | 13 Security Suites (MUC 1.1–5.2) | **B** | **Outstanding on Abuse Cases (SAST & Penetration), but zero Stress/Concurrency Testing.** Red-teamed HMAC forgery, BOLA headers, and PDF SSRF thoroughly. However, zero concurrent load tests were run, masking 3 critical P0 database race conditions. |
| **Step 5: Empirical Debugging Method** | Documented in audit specs | **A** | **Exemplary.** The audit formulated precise hypotheses, identified exact line numbers, predicted production failure exceptions, and provided minimal KISS fixes. |
| **Step 6: CI/CD Quality Gates** | GitHub Actions with Ruff, Bandit, Gitleaks | **A-** | **Automated & clean, but running tests exclusively on in-memory SQLite masked PostgreSQL-specific row-locking deadlocks (\`select\_for\_update\`).** Requires a dual-stage CI pipeline with a real PostgreSQL 16 container. |

This specification establishes the missing test implementations, concrete Python/Django test harnesses, boundary value suites, and CI/CD pipeline definitions required to harden the platform.

**2\. Step 2: Expanded Unit Testing & Boundary Value Analysis (BVA)**

**2.1 Sequence Generation & Fiscal Year Rollover Boundaries**

The primary unit testing failure was testing sequence numbers only on static counts (1, 2, 3) rather than sequence boundaries and yearly rollovers.

**Missed Edge Cases:**

8. **Year Transition Boundary:** Invoices issued at 2025-12-31T23:59:59Z vs 2026-01-01T00:00:00Z must maintain separate yearly sequences (INV-ORG-2025-00450 vs INV-ORG-2026-00001).  
9. **First Invoice of New Year:** Tenant creating their very first invoice in a new fiscal year must initialize last\_number \= 1, not crash with DoesNotExist.  
10. **Sequential Gaplessness:** Deleting a draft invoice must never decrement or corrupt committed sequences.  
11. **Padding Overflow Boundary:** Sequences crossing 99,999 to 100,000 must expand dynamically (INV-ORG-2026-100000) without truncation or regex failure.

**Implementation (apps/invoicing/tests/test\_sequence\_bva.py):**

| from decimal import Decimalimport datetimefrom django.test import TestCasefrom django.utils import timezonefrom apps.tenancy.models import Organizationfrom apps.invoicing.models import Invoice, InvoiceSequencefrom apps.invoicing.services.invoicing\_service import InvoicingServiceclass InvoiceSequenceBoundaryTests(TestCase):    def setUp(self):        self.org \= Organization.objects.create(name="Boundary Corp", slug="bnd")    def test\_fiscal\_year\_rollover\_sequence\_reset(self):        \# Verifies that invoice numbering resets to 00001 on Jan 1st of a new year        date\_2025 \= datetime.date(2025, 12, 31\)        date\_2026 \= datetime.date(2026, 1, 1\)        \# Issue final 2025 invoice        inv\_2025 \= InvoicingService.create\_invoice(            organization=self.org,            issue\_date=date\_2025,            items=\[{"description": "Item", "unit\_price": Decimal("100.00"), "quantity": 1}\],        )        self.assertTrue(inv\_2025.invoice\_number.startswith("INV-BND-2025-"))        \# Issue first 2026 invoice        inv\_2026 \= InvoicingService.create\_invoice(            organization=self.org,            issue\_date=date\_2026,            items=\[{"description": "Item", "unit\_price": Decimal("100.00"), "quantity": 1}\],        )        self.assertEqual(inv\_2026.invoice\_number, "INV-BND-2026-00001")    def test\_sequence\_padding\_overflow(self):        \# Verifies sequence numbers beyond 5 digits (100,000+) format safely without truncation        seq, \_ \= InvoiceSequence.objects.get\_or\_create(            organization=self.org, year=2026, defaults={"last\_number": 99999}        )        seq.last\_number \= 99999        seq.save()        inv \= InvoicingService.create\_invoice(            organization=self.org,            issue\_date=datetime.date(2026, 6, 1),            items=\[{"description": "High Volume Item", "unit\_price": Decimal("10.00"), "quantity": 1}\],        )        self.assertEqual(inv.invoice\_number, "INV-BND-2026-100000") |
| :---- |

**2.2 Statutory Tax Rounding & Multi-Line Pesewa Discrepancies (Act 1151\)**

Under Ghanaian **Value Added Tax Act, 2025 (Act 1151\)**, the tax engine calculates:

* Standard VAT: 15.0%  
* NHIL: 2.5%  
* GETFund: 2.5%  
* Total Effective Non-Cascading Rate: 20.0%

**Missed Edge Cases:**

12. **Sum of Rounded Lines vs Round of Summed Lines:** When an invoice contains 50 line items each valued at GHS 0.35, line-by-line half-up rounding can diverge from document-level aggregate tax by 1 to 3 pesewas (GHS 0.01 \- 0.03).  
13. **Zero-Rated vs Exempt vs Taxable Mixed Schedules:** An invoice containing standard taxable items, zero-rated exports (0%), and exempt financial services (0% without input credit) on the same bill.  
14. **Sub-Pesewa Fractions:** Products priced at GHS 1.3333 per unit must round using ROUND\_HALF\_UP strictly to 2 decimal places at the line subtotal stage before tax computation.

**Implementation (apps/tax/tests/test\_tax\_rounding\_bva.py):**

| from decimal import Decimalfrom django.test import TestCasefrom apps.tax.services import TaxCalculationServiceclass StatutoryTaxRoundingBoundaryTests(TestCase):    def test\_multi\_line\_half\_up\_pesewa\_accumulation(self):        \# Verifies that line-level tax rounding matches GRA invoice clearance rules        lines \= \[            {"description": "Micro Item 1", "amount": Decimal("0.33"), "tax\_category": "STANDARD"},            {"description": "Micro Item 2", "amount": Decimal("0.33"), "tax\_category": "STANDARD"},            {"description": "Micro Item 3", "amount": Decimal("0.33"), "tax\_category": "STANDARD"},        \]        \# Total Net: 0.99        \# Expected: VAT 15% of 0.99 \= 0.1485 \-\> 0.15        \# Expected: NHIL 2.5% of 0.99 \= 0.02475 \-\> 0.02        \# Expected: GETFund 2.5% of 0.99 \= 0.02475 \-\> 0.02        \# Total Tax: 0.19 | Grand Total: 1.18        result \= TaxCalculationService.calculate\_invoice\_taxes(lines)        self.assertEqual(result.vat\_15, Decimal("0.15"))        self.assertEqual(result.nhil\_2\_5, Decimal("0.02"))        self.assertEqual(result.getfund\_2\_5, Decimal("0.02"))        self.assertEqual(result.total\_tax, Decimal("0.19"))        self.assertEqual(result.total\_gross, Decimal("1.18"))    def test\_mixed\_tax\_schedules\_on\_single\_invoice(self):        \# Verifies mixed lines (Standard 20%, Zero-Rated 0%, Exempt 0%) on one invoice        lines \= \[            {"description": "Taxable Goods", "amount": Decimal("1000.00"), "tax\_category": "STANDARD"},            {"description": "Exported Goods", "amount": Decimal("500.00"), "tax\_category": "ZERO\_RATED"},            {"description": "Exempt Education", "amount": Decimal("300.00"), "tax\_category": "EXEMPT"},        \]        result \= TaxCalculationService.calculate\_invoice\_taxes(lines)        self.assertEqual(result.taxable\_subtotal, Decimal("1000.00"))        self.assertEqual(result.zero\_rated\_subtotal, Decimal("500.00"))        self.assertEqual(result.exempt\_subtotal, Decimal("300.00"))        self.assertEqual(result.vat\_15, Decimal("150.00"))        self.assertEqual(result.nhil\_2\_5, Decimal("25.00"))        self.assertEqual(result.getfund\_2\_5, Decimal("25.00"))        self.assertEqual(result.total\_gross, Decimal("2000.00")) |
| :---- |

**2.3 Ghanaian Statutory Identifier Formats & Checksum Boundaries**

Ghanaian business documents require strict input formatting:

* **GRA TIN:** 11 characters starting with C, P, V, or G followed by 10 digits (C0012345678).  
* **Ghana Card (NIA PIN):** GHA-XXXXXXXXX-X (15 characters with valid check digit).  
* **Luhn Payment Reference:** 10 digits with a Mod-10 check digit.

**Missed Edge Cases:**

15. **Case-Insensitive Normalization:** c0012345678 or gha-712345678-1 must be auto-uppercased and trimmed.  
16. **Whitespace Trapping:** Leading/trailing spaces or internal tabs in TIN inputs.  
17. **Invalid Check-Digit Rejection:** A Ghana Card or Luhn reference with 1 transposed digit must raise ValidationError, not crash during database save.

**Implementation (apps/core/tests/test\_ghana\_identifiers\_bva.py):**

| from django.test import TestCasefrom django.core.exceptions import ValidationErrorfrom apps.core.validators import validate\_gra\_tin, validate\_ghana\_cardfrom apps.invoicing.utils import LuhnValidatorclass GhanaIdentifierBoundaryTests(TestCase):    def test\_gra\_tin\_valid\_prefixes(self):        for prefix in \["C", "P", "V", "G", "Q"\]:            tin \= f"{prefix}0012345678"            self.assertTrue(validate\_gra\_tin(tin))    def test\_gra\_tin\_invalid\_prefixes\_and\_lengths(self):        invalid\_tins \= \[            "X0012345678",   \# Invalid prefix            "C001234567",    \# 10 chars (too short)            "C00123456789",  \# 12 chars (too long)            "C001234567A",   \# Alphanumeric in numeric section            "",              \# Empty string        \]        for tin in invalid\_tins:            with self.assertRaises(ValidationError):                validate\_gra\_tin(tin)    def test\_luhn\_transposition\_error\_detection(self):        \# Verifies that transposing adjacent digits fails Luhn mod-10 validation        valid\_ref \= LuhnValidator.generate\_reference(10042)        transposed \= valid\_ref\[1\] \+ valid\_ref\[0\] \+ valid\_ref\[2:\]        self.assertFalse(LuhnValidator.validate\_reference(transposed)) |
| :---- |

**2.4 PAYE & SSNIT Tier 1/2 Withholding Threshold Boundaries**

Ghanaian PAYE uses progressive tax brackets (First GHS 490 @ 0%, Next GHS 110 @ 5%, etc., up to 35% on excess over GHS 50,000).

**Missed Edge Cases:**

18. **Exact Bracket Boundaries:** Gross salary hitting *exactly* GHS 490.00 (tax must be GHS 0.00), GHS 600.00, GHS 730.00, and GHS 50,000.00.  
19. **SSNIT 5.5% Employee Tier 1 Deduction Pre-Tax Exemption:** PAYE must be computed on Gross \- SSNIT Employee Contribution, not total Gross.  
20. **Over-Cap SSNIT Salary:** Monthly salary exceeding the statutory SSNIT maximum insurable earnings cap (GHS 42,000.00/mo) must cap Tier 1 contribution at 5.5% \* 42,000.

**2.5 Invoicing State Machine & Non-Negative Valuation Boundaries**

Invoices transition through DRAFT \-\> ISSUED \-\> PARTIALLY\_PAID \-\> PAID | OVERDUE | VOIDED.

**Missed Edge Cases:**

21. **Negative Quantity / Negative Price:** Negative item amounts must be rejected on standard invoices (preventing negative sales from corrupting revenue; credit notes must be used instead).  
22. **Zero Total Invoices:** Invoices with total\_amount \= 0.00 must not trigger payment gateway webhooks or QR code generation.  
23. **Illegal State Transitions:** Attempting to transition PAID \-\> DRAFT or VOIDED \-\> ISSUED must raise IllegalStateTransitionError.

**3\. Step 3: Integration & Interface Testing (Escaping the ORM-Only Trap)**

The previous test suite tested domain services by calling Python methods (InvoicingService.create\_invoice()) and ORM helpers (Contact.objects.create()). This masked three missing REST endpoints and middleware authorization bugs.

**3.1 Full REST HTTP Request/Response Testing via APIClient**

We must test every mutating action through Django REST Framework's APIClient simulating real HTTP requests, headers, and status codes.

**Implementation (apps/tenancy/tests/test\_organization\_api\_integration.py):**

| from rest\_framework.test import APITestCasefrom rest\_framework import statusfrom django.contrib.auth import get\_user\_modelfrom apps.tenancy.models import Organization, OrganizationMembership, Rolefrom apps.ledger.models import ChartOfAccountsUser \= get\_user\_model()class OrganizationRegistrationAPIIntegrationTests(APITestCase):    def setUp(self):        self.user \= User.objects.create\_user(email="owner@ghana.com", password="SecurePassword123\!")        self.client.force\_authenticate(user=self.user)    def test\_post\_tenancy\_organizations\_endpoint\_exists\_and\_provisions\_coa(self):        \# Verifies POST /api/v1/tenancy/organizations/ creates org, OWNER role, and COA        payload \= {            "name": "Accra Trading Enterprise",            "tax\_identification\_number": "C0012345678",            "vat\_status": "STANDARD\_20",            "tax\_period\_length": "monthly",            "accounting\_mode": "STRICT",            "currency": "GHS",        }        response \= self.client.post("/api/v1/tenancy/organizations/", payload, format="json")        self.assertEqual(response.status\_code, status.HTTP\_201\_CREATED)        org\_id \= response.data\["id"\]        org \= Organization.objects.get(id=org\_id)        self.assertEqual(org.name, "Accra Trading Enterprise")        \# Verify Owner Membership created        membership \= OrganizationMembership.objects.get(organization=org, user=self.user)        self.assertEqual(membership.role, Role.OWNER)        \# Verify Ghanaian Chart of Accounts seeded        coa\_count \= ChartOfAccounts.objects.filter(organization=org).count()        self.assertGreaterEqual(coa\_count, 35, "Default Ghanaian COA must seed at least 35 core accounts") |
| :---- |

**3.2 Multi-Tenant Middleware Guard Pipeline Testing**

TenantSecurityMiddleware inspects 5 stages per request:

24. Public route bypass  
25. Authentication check  
26. X-Organization-ID header validation  
27. Membership verification & Auditor expiration  
28. PostgreSQL RLS context binding

**Missed Edge Cases:**

29. **Cross-Tenant Header Spoofing:** User A belonging to Org 1 sends X-Organization-ID: \<Org 2 ID\>. Middleware must return HTTP 403 Forbidden.  
30. **Expired Auditor Access:** Auditor with expires\_at \= yesterday must be blocked with HTTP 403 Forbidden.  
31. **Malformed UUID in Tenant Header:** Sending X-Organization-ID: not-a-uuid must return HTTP 400 Bad Request, not unhandled crash.

**Implementation (apps/tenancy/tests/test\_middleware\_pipeline\_integration.py):**

| from rest\_framework.test import APITestCasefrom rest\_framework import statusfrom django.contrib.auth import get\_user\_modelfrom django.utils import timezoneimport datetimefrom apps.tenancy.models import Organization, OrganizationMembership, RoleUser \= get\_user\_model()class TenantMiddlewarePipelineTests(APITestCase):    def setUp(self):        self.user \= User.objects.create\_user(email="user@test.com", password="Password123\!")        self.org1 \= Organization.objects.create(name="Org 1", slug="org1")        self.org2 \= Organization.objects.create(name="Org 2", slug="org2")        OrganizationMembership.objects.create(organization=self.org1, user=self.user, role=Role.ADMIN)        self.client.force\_authenticate(user=self.user)    def test\_cross\_tenant\_header\_spoofing\_returns\_403(self):        \# User belonging to Org1 attempts to access Org2 data via header spoofing        response \= self.client.get(            "/api/v1/invoicing/invoices/",            HTTP\_X\_ORGANIZATION\_ID=str(self.org2.id),        )        self.assertEqual(response.status\_code, status.HTTP\_403\_FORBIDDEN)    def test\_expired\_auditor\_membership\_returns\_403(self):        \# Auditor whose expiration timestamp has passed is blocked from read access        auditor \= User.objects.create\_user(email="auditor@kpmg.com", password="Password123\!")        OrganizationMembership.objects.create(            organization=self.org1,            user=auditor,            role=Role.AUDITOR,            expires\_at=timezone.now() \- datetime.timedelta(days=1),        )        self.client.force\_authenticate(user=auditor)        response \= self.client.get(            "/api/v1/ledger/accounts/",            HTTP\_X\_ORGANIZATION\_ID=str(self.org1.id),        )        self.assertEqual(response.status\_code, status.HTTP\_403\_FORBIDDEN) |
| :---- |

**3.3 Public Unauthenticated Shareable Access & Security Exemption Tests**

Validates PublicInvoiceView at /api/v1/invoicing/public/invoices/\<uuid:public\_id\>/:

* **Unauthenticated customer access:** Allows anonymous HTTP GET without credentials or headers.  
* **Tenant Isolation Sanitization:** Verifies response payload does *not* leak internal database fields (ledger entry IDs, creator user IDs, internal tenant notes).  
* **Draft Concealment:** Draft or voided invoices must return HTTP 404 to public callers.

**3.4 SimpleJWT Cookie Lifecycle & Token Rotation Integration**

Tests cookie authentication pipeline:

* Calling POST /api/v1/auth/token/refresh/ returns a new access token *and* sets a new rotated refresh token in HttpOnly Set-Cookie.  
* Presenting the old refresh token on a subsequent call is immediately rejected with HTTP 401 Unauthorized.  
* Calling POST /api/v1/auth/logout/ clears both access\_token and refresh\_token cookies with max\_age=0.

**4\. Step 4: System, Security, Concurrency & Stress Testing**

**4.1 Multi-Threaded Concurrency Test Harness (PostgreSQL Row Locks)**

Validates that **Issue B1 (\`InvoiceSequence\` row locking)** and **Issue B2 (Luhn payment reference loop)** execute with zero duplicate key exceptions under concurrent execution.

**Implementation (backend/tests/stress/test\_concurrency\_stress.py):**

| import concurrent.futuresfrom decimal import Decimalimport datetimefrom django.test import TransactionTestCasefrom django.db import connectionfrom apps.tenancy.models import Organizationfrom apps.invoicing.models import Invoicefrom apps.invoicing.services.invoicing\_service import InvoicingServiceclass ConcurrencyStressTests(TransactionTestCase):    \# TransactionTestCase allows real DB commits across parallel threads    def setUp(self):        self.org \= Organization.objects.create(name="Concurrent Corp", slug="ccc")    def test\_20\_parallel\_invoice\_creations\_generate\_gapless\_unique\_numbers(self):        \# Spawns 20 threads simultaneously issuing invoices for the same tenant.        \# Must produce exactly 20 unique, gapless numbers with 0 duplicate key IntegrityErrors.        num\_threads \= 20        date\_today \= datetime.date(2026, 9, 28\)        def create\_single\_invoice(idx):            connection.close()            return InvoicingService.create\_invoice(                organization=self.org,                issue\_date=date\_today,                items=\[{"description": f"Batch Item {idx}", "unit\_price": Decimal("50.00"), "quantity": 1}\],            )        with concurrent.futures.ThreadPoolExecutor(max\_workers=num\_threads) as executor:            futures \= \[executor.submit(create\_single\_invoice, i) for i in range(num\_threads)\]            invoices \= \[f.result() for f in concurrent.futures.as\_completed(futures)\]        self.assertEqual(len(invoices), num\_threads)        invoice\_numbers \= \[inv.invoice\_number for inv in invoices\]        unique\_numbers \= set(invoice\_numbers)        self.assertEqual(len(unique\_numbers), num\_threads, "All concurrent invoice numbers must be unique")        expected\_numbers \= {f"INV-CCC-2026-{i:05d}" for i in range(1, num\_threads \+ 1)}        self.assertEqual(unique\_numbers, expected\_numbers, "Sequence numbers must be gapless") |
| :---- |

**4.2 Chart of Accounts Unlocked Concurrency Stress Test**

Validates **Issue B4**: Verifies that 50 concurrent transactions posting journal entries touching standard master accounts (Cash 1000, AR 1200, Sales 4000) complete in \<2 seconds without database deadlocks.

**4.3 Boundary Overpayment & Micro-Split Reconciliation Tests**

Validates payment reconciliation boundary conditions:

32. **Overpayment Rejection:** Attempting to record a payment of GHS 1,001.00 against an outstanding invoice of GHS 1,000.00 must raise ValidationError("Payment exceeds invoice balance due").  
33. **Exact Micro-Payment Splitting:** 3 consecutive Mobile Money payments of GHS 333.33, GHS 333.33, and GHS 333.34 against a GHS 1,000.00 invoice must transition status through PARTIALLY\_PAID \-\> PARTIALLY\_PAID \-\> PAID with exact 0.00 remaining balance.

**4.4 Webhook Idempotency & Replay Attack Stress Verification**

Validates **Issue G3 (Redis Idempotency Middleware)**:

* Sends 10 identical Paystack/Hubtel payment webhook POST requests in parallel with identical x-paystack-signature and event\_id.  
* Exactly **one** transaction is committed to the database; the remaining 9 requests receive the cached HTTP 200 response with zero duplicate ledger lines.

**4.5 Credit Note Statutory Inversion & Double-Refund Stress**

Validates **Issue G2 (\`CreditNote\` Model)**:

* Emits credit note against a paid invoice.  
* Verifies exact reversal lines:  
* **Debit:** Sales Revenue (4000)  
* **Debit:** VAT Output (2150)  
* **Credit:** Cash/Bank (1010)  
* Second credit note attempt exceeding original invoice total is rejected with ValidationError("Credit note exceeds remaining invoice balance").

**5\. Step 5: Empirical Debugging Verification & Regression Anchors**

Every issue identified in the Backend Breakage Audit (md\_docs/BACKEND\_BREAKAGE\_AND\_KISS\_AUDIT.md) has a dedicated regression test anchor to ensure zero regressions in CI/CD:

| Bug ID | Audit Defect | Regression Test File | Failure Condition Tested |
| :---- | :---- | :---- | :---- |
| **B1** | Invoice COUNT() race condition | tests/stress/test\_concurrency\_stress.py | 20 threads simultaneously creating invoices |
| **B2** | Luhn reference collision | tests/stress/test\_reference\_collision.py | 10 concurrent saves on identical seed count |
| **B3** | Journal entry sequence collision | tests/stress/test\_ledger\_collision.py | Parallel journal posts on identical fiscal count |
| **B4** | COA select\_for\_update() lock | tests/stress/test\_coa\_lock\_elimination.py | Parallel postings touching account 1000 |
| **B5** | Middleware atomic() wrapper | tests/integration/test\_middleware\_transactions.py | Inner caught ValidationError does not abort outer |
| **B6** | Missing Org Registration API | tests/integration/test\_org\_registration\_api.py | POST /api/v1/tenancy/organizations/ |
| **B7** | Missing Contacts CRUD | tests/integration/test\_contacts\_api.py | GET/POST /api/v1/contacts/ |
| **B8** | Missing Public Invoice Viewer | tests/integration/test\_public\_invoice\_api.py | GET /invoicing/public/invoices/\<uuid\>/ |
| **B9** | Omitted token refresh rotation | tests/integration/test\_auth\_token\_rotation.py | Verify rotated refresh token in Set-Cookie |
| **B10** | CSRF error swallowed as 401 | tests/integration/test\_csrf\_error\_unmasking.py | Invalid CSRF token yields HTTP 403, not 401 |
| **B11** | Hardcoded cookie path | tests/integration/test\_cookie\_paths.py | Custom JWT\_AUTH\_COOKIE\_PATH respected |
| **B12** | Redundant .exists() in ledger | tests/unit/test\_balance\_selectors.py | Verify query count reduced by 50% |
| **B13** | Triplicate auditor role check | tests/security/test\_auditor\_permissions.py | IsTenantAuditorReadOnly blocks mutations |
| **B14** | Monolithic service methods | tests/unit/test\_decomposed\_helpers.py | Unit tests for private calculation subroutines |

**6\. Step 6: CI/CD Quality Gates & Dual-Stage Environment Testing**

**6.1 Stage 1: Ultra-Fast In-Memory SQLite Gate (\<5s)**

Runs on every git push or pull request to provide instantaneous feedback:

* Ruff Linter (ruff check .)  
* Ruff Formatter (ruff format \--check .)  
* Bandit AST Security Scan (bandit \-r apps/ \-ll)  
* Fast Unit Tests (uv run python manage.py test \--settings=config.settings\_test)

**6.2 Stage 2: Real PostgreSQL 16 Service Container Integration**

Runs on all merges to develop and main inside GitHub Actions:

* Uses postgres:16-alpine service container.  
* Verifies real database constraints, foreign keys, row locking, and RLS policies.  
* Executes multi-threaded stress and concurrency test suites (backend/tests/stress/).

**GitHub Actions Workflow Definition (.github/workflows/ci.yml):**

| name: Mage Books SAAS — Dual-Stage CI/CD Pipelineon:  push:    branches: \[develop, main\]  pull\_request:    branches: \[develop, main\]jobs:  stage-1-fast-gate:    name: "Stage 1: Fast SQLite & Security Analysis"    runs-on: ubuntu-latest    steps:      \- uses: actions/checkout@v4      \- name: Install uv        uses: astral-sh/setup-uv@v2        with:          version: "latest"      \- name: Set up Python 3.12        uses: actions/setup-python@v5        with:          python-version: "3.12"      \- name: Install dependencies        run: uv sync \--frozen      \- name: Ruff Linter Check        run: uv run ruff check .      \- name: Ruff Format Check        run: uv run ruff format \--check .      \- name: Bandit Security AST Analysis        run: uv run bandit \-r apps/ \-ll      \- name: Run Fast SQLite Unit Tests        run: uv run python manage.py test apps/        env:          IS\_TESTING: "True"  stage-2-postgres-gate:    name: "Stage 2: Real PostgreSQL 16 Concurrency & Integration"    needs: stage-1-fast-gate    runs-on: ubuntu-latest    services:      postgres:        image: postgres:16-alpine        env:          POSTGRES\_DB: magebooks\_test          POSTGRES\_USER: postgres          POSTGRES\_PASSWORD: postgrespassword        ports:          \- 5432:5432        options: \>-          \--health-cmd pg\_isready          \--health-interval 10s          \--health-timeout 5s          \--health-retries 5    steps:      \- uses: actions/checkout@v4      \- name: Install uv        uses: astral-sh/setup-uv@v2      \- name: Set up Python 3.12        uses: actions/setup-python@v5        with:          python-version: "3.12"      \- name: Install dependencies        run: uv sync \--frozen      \- name: Verify Migration Integrity & Zero Missing Migrations        run: uv run python manage.py makemigrations \--check \--dry-run        env:          DB\_NAME: magebooks\_test          DB\_USER: postgres          DB\_PASSWORD: postgrespassword          DB\_HOST: localhost          DB\_PORT: 5432      \- name: Apply Migrations on PostgreSQL        run: uv run python manage.py migrate        env:          DB\_NAME: magebooks\_test          DB\_USER: postgres          DB\_PASSWORD: postgrespassword          DB\_HOST: localhost          DB\_PORT: 5432      \- name: Run Multi-Threaded Concurrency & Integration Stress Suite        run: uv run python manage.py test tests/stress/ tests/integration/        env:          DB\_NAME: magebooks\_test          DB\_USER: postgres          DB\_PASSWORD: postgrespassword          DB\_HOST: localhost          DB\_PORT: 5432          IS\_TESTING: "False" |
| :---- |

**6.3 Automated Migration Integrity & Reversibility Check Gate**

Automated checks prevent broken migrations:

34. **Uncommitted Model Changes:** python manage.py makemigrations \--check \--dry-run halts CI if a developer altered a model field without committing a migration.  
35. **Reversibility Testing:** For every new migration, CI executes:

|    python manage.py migrate \<app\> \<previous\_migration\>   python manage.py migrate \<app\> |
| :---- |

Ensuring zero one-way migrations without backward rollback definitions.

**7\. Consolidated Sprint Integration Matrix**

All missing edge cases, integration suites, concurrency stress tests, and CI/CD upgrades are integrated directly into our 4-sprint roadmap:

| Sprint | Code Deliverables | Integrated Testing & Quality Gates |
| :---- | :---- | :---- |
| **Sprint A (P0 Concurrency & Safety)** | • B1 (InvoiceSequence table)\<br\>• B2 (Luhn increment loop)\<br\>• B3 (Journal UUIDv7 entropy)\<br\>• B4 (Remove COA lock)\<br\>• B5 (Remove middleware atomic)\<br\>• B9 (Token refresh rotation)\<br\>• B10 (Unmask CSRF 403\) | **• Concurrency Stress Suite (20 parallel invoice threads)**\<br\>**• COA Unlocked Postings Stress (50 parallel postings)**\<br\>**• Luhn Mod-10 Collision Test Harness**\<br\>**• Middleware Exception Trap Verification** |
| **Sprint B (Core REST & Onboarding)** | • B6 (Org Registration API)\<br\>• B7 (Contacts CRUD ViewSet)\<br\>• B8 (Public Invoice Viewer)\<br\>• F1 (/dashboard/invoices)\<br\>• F2 (/forgot-password)\<br\>• F3 (750k VAT Copy)\<br\>• F4 (Monthly Return Default)\<br\>• F9 (Wire Auth Forms)\<br\>• F10 (Wire Onboarding Finish) | **• Full APIClient REST Endpoint Testing**\<br\>**• Multi-Tenant Header Spoofing Penetration Tests**\<br\>**• Public Invoice Anonymous Access & Tenant Data Sanitization Tests**\<br\>**• Onboarding Wizard to DB Verification Test** |
| **Sprint C (Statutory & Payments)** | • F5 (TIN/Card Input Masks)\<br\>• F6 (15-Min Inactivity Lock)\<br\>• G1 (Celery MoMo Payroll)\<br\>• G2 (CreditNote Model & Reversal)\<br\>• G3 (Redis Idempotency Middleware)\<br\>• G5 (Hubtel SMS Client)\<br\>• G6 (PII Column Encryption)\<br\>• B11 (Cookie Path Parameterization)\<br\>• B12 (Remove .exists() in Ledger)\<br\>• B13 (DRY Auditor Class) | **• Multi-Line Pesewa Half-Up Rounding Boundary Suite**\<br\>**• Boundary Overpayment & Partial Split Tests**\<br\>**• Credit Note Double-Refund Prevention Suite**\<br\>**• Webhook 10-Parallel Replay Idempotency Verification**\<br\>**• Ghana Card / TIN Regex Checksum Unit Tests** |
| **Sprint D (Scale, PWA & Polish)** | • F7 (Encrypted Offline IndexedDB)\<br\>• F8 (Sync Mode Toggle API)\<br\>• F11 (Wire 16 Dashboard Shells)\<br\>• F12 (TopNavBar Dynamic Hub)\<br\>• F13 (Replace Dead Links)\<br\>• G4 (Monthly AccountSnapshot)\<br\>• B14 (Decompose Service Monoliths) | **• Dual-Stage CI/CD GitHub Actions Pipeline**\<br\>**• PostgreSQL 16 Service Container Integration**\<br\>**• Migration Dry-Run & Reversibility Test Gate**\<br\>**• Decomposed Helper Unit Tests with 100% Branch Coverage** |

