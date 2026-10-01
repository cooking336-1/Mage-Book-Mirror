# Mage Books SAAS — Frontend Wiring & Mock Remediation Plan

This document provides a comprehensive audit of all frontend screens in the repository, identifying those currently using hardcoded mock data or empty placeholders, along with **concrete, production-ready remediation blueprints** to wire each screen to the Django REST Framework backend.

---

## 1. High-Level Summary Matrix

| Category | Count | Screen Routes |
| :--- | :---: | :--- |
| **Fully Wired Screens** | **6** | `/login`, `/signup`, `/onboarding`, `/dashboard/chart-of-accounts`, `/dashboard/contacts`, `/dashboard/accounts-receivable` *(+ TopNavBar & ModeContext)* |
| **Partially Wired / Missing Backend** | **1** | `/forgot-password` (calls unrouted endpoint with silent error swallow) |
| **Unwired with Hardcoded Mock Data** | **4** | `/dashboard` (Overview), `/dashboard/invoices`, `/dashboard/audit`, `/dashboard/security` |
| **Unwired Empty-State / Placeholder Screens** | **12** | `/dashboard/accounts-payable`, `/dashboard/payroll`, `/dashboard/reports`, `/dashboard/transactions`, `/dashboard/ledgers`, `/dashboard/users`, `/dashboard/setup`, `/dashboard/payments`, `/dashboard/period-rectification`, `/dashboard/fixed-assets`, `/dashboard/inventory`, `/dashboard/receipts` |
| **Static / Informational Pages** | **5** | `/` (Splash screen), `/dashboard/hire-expert`, `/legal/privacy`, `/legal/terms`, `/legal/support` |
| **Missing Screens for Existing Backend Endpoints** | **1** | Public invoice viewer for `GET /api/v1/invoices/public/invoices/{share_token}/` |

---

## 2. Standard Wiring Architecture & Rules (Ref: `AGENTS.md`)

All remediation implementations must strictly adhere to the following architecture:

1. **Centralized HTTP Client:**
   - Must use `apiClient` from `src/lib/apiClient.ts` (configured with `withCredentials: true`, automatic `X-Organization-ID` header injection, CSRF token handling, and 401 token refresh queue).
   - Never use raw `axios` or raw `fetch` for dashboard operations.
2. **Dual-Mode Experience:**
   - Consume `useMode()` from `src/contexts/ModeContext.tsx`.
   - In **Simple Mode**, use human-centric Ghanaian business terminology (*"Money Owed to Me"*, *"Pay Staff"*, *"Record Transaction"*).
   - In **Professional Mode**, use statutory double-entry accounting terminology (*"Accounts Receivable"*, *"Payroll Management"*, *"New Journal Entry"*).
3. **Offline-First Resilience:**
   - Integrate with `src/lib/offline-storage.ts` using IndexedDB and AES-GCM encryption (`pwa-cache-encryption.ts`) for cached reads and write mutation queues.
4. **State Transitions:**
   - Every wired page must manage three core states: `isLoading` (skeleton state), `error` (banner with retry CTA), and `data` (live collection).

---

## 3. Screen-by-Screen Remediation Blueprints

---

### Screen 1: Dashboard Overview
* **File:** `src/app/(dashboard)/dashboard/page.tsx`
* **Route:** `/dashboard`
* **Status:** 🔴 **100% Mock Data**

#### Current Mock Artifacts
* Hardcoded greeting `"Good morning, Ama"` and static date `"25th July, 2026"`.
* Hardcoded badge counters: `"3 invoices pending GRA clearance · 2 drafts · 1 unresolved note"`.
* Hardcoded metric cards: `GH¢ 23,000.00`, `GH¢ 30,040.00`, `GH¢ 10,340.00`, `GH¢ 15,300.50`.
* Hardcoded 5-item activity feed and static CSS bar chart (`CHART_BARS`).
* Inert `"+ Record Transaction"` button.

#### Backend Endpoints Required
1. `GET /api/v1/auth/me/` — Retrieve user's first name.
2. `GET /api/v1/tenancy/organizations/current/` — Retrieve active organization name & mode.
3. `GET /api/v1/ledger/reports/trial-balance/` or `GET /api/v1/ledger/accounts/` — Compute real cash balances, accounts payable, accounts receivable, and tax liabilities.
4. `GET /api/v1/invoices/?status=PENDING_GRA` & `?status=DRAFT` — Live badge counts.
5. `GET /api/v1/audit/trail/?limit=5` — Live 5 most recent activities.

#### How to Wire & Fix
```tsx
// 1. DTO Interfaces
interface DashboardMetrics {
  accountsPayable: number;
  accountsReceivable: number;
  pettyCash: number;
  taxLiabilities: number;
  pendingGraCount: number;
  draftCount: number;
}

interface ActivityItem {
  id: string;
  action: string;
  user_email: string;
  created_at: string;
}

// 2. Fetcher Hook inside DashboardPage
const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
const [recentActivities, setRecentActivities] = useState<ActivityItem[]>([]);
const [userName, setUserName] = useState("User");
const [isLoading, setIsLoading] = useState(true);

useEffect(() => {
  async function loadDashboard() {
    try {
      setIsLoading(true);
      const [userRes, invoicesRes, auditRes, accountsRes] = await Promise.all([
        apiClient.get("/api/v1/auth/me/"),
        apiClient.get("/api/v1/invoices/"),
        apiClient.get("/api/v1/audit/trail/?limit=5"),
        apiClient.get("/api/v1/ledger/accounts/"),
      ]);

      setUserName(userRes.data.first_name || userRes.data.email.split("@")[0]);
      
      const invoices = Array.isArray(invoicesRes.data) ? invoicesRes.data : invoicesRes.data.results || [];
      const pendingGra = invoices.filter((i: any) => i.status === "PENDING_GRA").length;
      const drafts = invoices.filter((i: any) => i.status === "DRAFT").length;
      
      // Calculate AP, AR, Cash from accounts
      const accounts = accountsRes.data || [];
      const cash = accounts.filter((a: any) => a.category === "ASSET" && a.sub_category === "CASH")
        .reduce((sum: number, a: any) => sum + parseFloat(a.current_balance || 0), 0);
      const ar = accounts.filter((a: any) => a.account_number.startsWith("1200"))
        .reduce((sum: number, a: any) => sum + parseFloat(a.current_balance || 0), 0);
      const ap = accounts.filter((a: any) => a.account_number.startsWith("2000"))
        .reduce((sum: number, a: any) => sum + parseFloat(a.current_balance || 0), 0);
      const tax = accounts.filter((a: any) => a.account_number.startsWith("2100"))
        .reduce((sum: number, a: any) => sum + parseFloat(a.current_balance || 0), 0);

      setMetrics({
        accountsPayable: ap,
        accountsReceivable: ar,
        pettyCash: cash,
        taxLiabilities: tax,
        pendingGraCount: pendingGra,
        draftCount: drafts,
      });

      const auditList = Array.isArray(auditRes.data) ? auditRes.data : auditRes.data.results || [];
      setRecentActivities(auditList);
    } catch (err) {
      console.error("Dashboard loading error:", err);
    } finally {
      setIsLoading(false);
    }
  }
  loadDashboard();
}, []);
```
* **CTA Button Fix:** Connect `"+ Record Transaction"` / `"+ New Journal Entry"` to route to `/dashboard/transactions?action=new` or trigger a transaction entry drawer.

---

### Screen 2: Invoices Management
* **File:** `src/app/(dashboard)/dashboard/invoices/page.tsx`
* **Route:** `/dashboard/invoices`
* **Status:** 🔴 **Unwired — In-Memory `MOCK_INVOICES` Array**

#### Current Mock Artifacts
* `const MOCK_INVOICES: InvoiceItem[] = [...]` containing 5 hardcoded objects.
* Summary cards and filter bars evaluate only the mock array.
* Inert `"+ New Invoice"` button.
* `"Download PDF"` triggers mock timeout alert.

#### Backend Endpoints Required
* `GET /api/v1/invoices/?search=&status=` — List invoices with query filtering.
* `POST /api/v1/invoices/` — Create new invoice draft.
* `POST /api/v1/invoices/{id}/issue/` — Submit to GRA for E-VAT clearance.
* `GET /api/v1/invoices/{id}/generate-pdf/` — Download fiscalized PDF.

#### How to Wire & Fix
```tsx
// 1. Replace MOCK_INVOICES with state:
const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
const [isLoading, setIsLoading] = useState(true);
const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

const fetchInvoices = async () => {
  setIsLoading(true);
  try {
    const params = new URLSearchParams();
    if (search.trim()) params.append("search", search.trim());
    if (statusFilter !== "ALL") params.append("status", statusFilter);
    const res = await apiClient.get<InvoiceItem[] | { results: InvoiceItem[] }>(
      `/api/v1/invoices/?${params.toString()}`
    );
    const list = Array.isArray(res.data) ? res.data : res.data.results || [];
    setInvoices(list);
  } catch (err) {
    console.error("Failed to fetch invoices", err);
  } finally {
    setIsLoading(false);
  }
};

useEffect(() => {
  fetchInvoices();
}, [statusFilter]);

// 2. Wire PDF Download:
const handleDownloadPdf = async (id: string, invoiceNumber: string) => {
  try {
    const res = await apiClient.get(`/api/v1/invoices/${id}/generate-pdf/`, {
      responseType: "blob",
    });
    const blob = new Blob([res.data], { type: "application/pdf" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${invoiceNumber}.pdf`;
    a.click();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert("Failed to download PDF. Please ensure the invoice is issued.");
  }
};
```
* **Modal Wiring:** Implement `<InvoiceCreateModal isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} onCreated={fetchInvoices} />` with line-item dynamic calculation (Quantity × Unit Price + Ghana VAT 15%, NHIL 2.5%, GETFund 2.5%, COVID-19 Levy 1%).

---

### Screen 3: Audit Trail / Activity Log
* **File:** `src/app/(dashboard)/dashboard/audit/page.tsx`
* **Route:** `/dashboard/audit`
* **Status:** 🔴 **Unwired — 3 Hardcoded Mock Rows**

#### Backend Endpoints Required
* `GET /api/v1/audit/trail/` (Already implemented in backend with SHA256 cryptographic chain, actor details, before/after states).

#### How to Wire & Fix
```tsx
interface AuditEntry {
  id: string;
  action: string;
  user_email: string;
  entity_type: string;
  entity_id: string;
  ip_address: string;
  sha256_hash: string;
  created_at: string;
}

const [entries, setEntries] = useState<AuditEntry[]>([]);
const [loading, setLoading] = useState(true);

useEffect(() => {
  async function fetchAuditTrail() {
    try {
      const res = await apiClient.get<AuditEntry[] | { results: AuditEntry[] }>("/api/v1/audit/trail/");
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setEntries(data);
    } finally {
      setLoading(false);
    }
  }
  fetchAuditTrail();
}, []);
```
* **UI Enhancement:** Display cryptographic hash badge (`sha256_hash.slice(0, 10)...`) verifying tamper-evident log integrity.

---

### Screen 4: Security Log
* **File:** `src/app/(dashboard)/dashboard/security/page.tsx`
* **Route:** `/dashboard/security`
* **Status:** 🔴 **Unwired — 3 Hardcoded Mock Rows**

#### Backend Endpoints Required
* `GET /api/v1/audit/trail/?action_type=SECURITY` or filter on `entity_type=UserSession`.

#### How to Wire & Fix
```tsx
useEffect(() => {
  apiClient.get("/api/v1/audit/trail/").then((res) => {
    const all = Array.isArray(res.data) ? res.data : res.data.results || [];
    const securityEvents = all.filter((e: any) => 
      e.action.includes("login") || e.action.includes("password") || e.action.includes("2fa")
    );
    setEvents(securityEvents);
  });
}, []);
```

---

### Screen 5: Accounts Payable ("Money I Owe")
* **File:** `src/app/(dashboard)/dashboard/accounts-payable/page.tsx`
* **Route:** `/dashboard/accounts-payable`
* **Status:** 🔴 **Unwired Empty Placeholder — Backend Endpoints Not Yet Implemented**

#### Backend Status: Does this exist?
* **NO.** The current `Invoice` model in `backend/apps/invoicing/models.py` only models **Customer Sales Invoices** (`customer` FK to `Contact`).
* There is **no `invoice_type` field** on `Invoice`, and `GET /api/v1/invoices/` only filters by `status`, `customer_id`, and `search`.
* In `docs/DETAILED_DOCUMENTATION.md` (Section 7), vendor bills are designed as a separate `bills` model (`supplier_id`, `bill_number`, `bill_date`, `due_date`, `total_amount`, `withholding_tax_amount`, `paid_amount`, `status`).

#### Required Backend Additions (Choose One Pattern)
1. **Dedicated Bill Model (Recommended per Architecture Spec):**
   - Create `Bill` and `BillLine` models in `backend/apps/invoicing/models.py` (or `backend/apps/bills/`).
   - Expose endpoints:
     - `GET /api/v1/bills/` (list vendor bills with status, due date, supplier name)
     - `POST /api/v1/bills/` (record supplier bill with WHT and expense account allocation)
2. **Polymorphic Invoices:**
   - Add `invoice_type = models.CharField(choices=[('SALES', 'Sales Invoice'), ('BILL', 'Vendor Bill')], default='SALES')` to `Invoice`.
   - Add `GET /api/v1/invoices/?invoice_type=BILL`.
3. **Interim Ledger Solution (Available Now):**
   - Query the General Ledger directly for account `2010 Accounts Payable`:
     - `GET /api/v1/ledger/accounts/?category=LIABILITY`
     - Post supplier bills via manual journal vouchers to `POST /api/v1/ledger/journal-entries/`.

#### How to Wire & Fix (Once `Bill` or `invoice_type` Endpoint is Created)
* Replicate the pattern deployed in `src/app/(dashboard)/dashboard/accounts-receivable/page.tsx`:
* Dynamically calculate:
  * **Total Owed:** Sum of `balance_due` on all unpaid vendor bills.
  * **Past Due:** Sum of `balance_due` where `due_date < today`.
  * **Due This Month:** Sum of `balance_due` where `due_date` falls in the current calendar month.
* Wire `"+ Add Bill to Pay"` to a vendor bill entry modal submitting to the bills endpoint.

---

### Screen 6: Payroll Management ("Pay Staff")
* **File:** `src/app/(dashboard)/dashboard/payroll/page.tsx`
* **Route:** `/dashboard/payroll`
* **Status:** 🔴 **Unwired Empty Placeholder**

#### Backend Endpoints Required (Fully implemented on backend!)
* `GET /api/v1/payroll/runs/` — List all payroll runs (Draft, Submitted, Approved, Disbursed).
* `POST /api/v1/payroll/runs/` — Create new payroll run.
* `POST /api/v1/payroll/runs/{id}/submit/` — Maker submits for approval.
* `POST /api/v1/payroll/runs/{id}/approve/` — Checker approves.
* `POST /api/v1/payroll/runs/{id}/disburse/` — Trigger MoMo payouts with TOTP step-up.
* `POST /api/v1/payroll/2fa/verify/` — Step-up 2FA code verification.

#### How to Wire & Fix
```tsx
interface PayrollRun {
  id: string;
  payroll_period: string;
  status: "DRAFT" | "SUBMITTED" | "APPROVED" | "DISBURSED";
  total_gross: number;
  total_paye: number;
  total_ssnit: number;
  total_net: number;
  created_at: string;
}

const [runs, setRuns] = useState<PayrollRun[]>([]);
const [isNewRunModalOpen, setIsNewRunModalOpen] = useState(false);

const loadPayroll = async () => {
  const res = await apiClient.get<PayrollRun[]>("/api/v1/payroll/runs/");
  setRuns(res.data);
};

useEffect(() => { loadPayroll(); }, []);
```
* **Disbursement Modal:** When clicking `"Disburse Payouts"`, open a modal requesting the manager's 6-digit TOTP code, submit to `POST /api/v1/payroll/2fa/verify/`, and on success invoke `POST /api/v1/payroll/runs/{id}/disburse/`.

---

### Screen 7: Financial Reports
* **File:** `src/app/(dashboard)/dashboard/reports/page.tsx`
* **Route:** `/dashboard/reports`
* **Status:** 🔴 **Unwired Placeholder (6 Static Cards)**

#### Backend Endpoints Required (Fully implemented on backend!)
* `GET /api/v1/ledger/reports/profit-and-loss/?start_date=&end_date=`
* `GET /api/v1/ledger/reports/balance-sheet/?as_of_date=`
* `GET /api/v1/ledger/reports/trial-balance/?as_of_date=`

#### How to Wire & Fix
* Convert the 6 cards into interactive selectors with date pickers (Start Date, End Date, As of Date).
* Clicking a card (e.g. *Profit & Loss*) dynamically fetches the structured JSON from the corresponding endpoint and renders:
  * Operating Income (Sales, Service Revenue)
  * Cost of Goods Sold (COGS)
  * Gross Margin
  * Operating Expenses (Salaries, Rent, Utilities)
  * Net Profit / Loss before and after tax.
* Add an `"Export to CSV / PDF"` action using the returned report lines.

---

### Screen 8: Transactions ("Journal Entries")
* **File:** `src/app/(dashboard)/dashboard/transactions/page.tsx`
* **Route:** `/dashboard/transactions`
* **Status:** 🔴 **Unwired Empty Placeholder**

#### Backend Endpoints Required (Fully implemented on backend!)
* `GET /api/v1/ledger/journal-entries/` — List all balanced journal entries.
* `POST /api/v1/ledger/journal-entries/` — Post manual balanced entry (Debits == Credits).

#### How to Wire & Fix
```tsx
interface JournalEntry {
  id: string;
  entry_number: string;
  date: string;
  reference: string;
  description: string;
  is_posted: boolean;
  lines: Array<{
    id: string;
    account_number: string;
    account_name: string;
    debit: number;
    credit: number;
  }>;
}

const [entries, setEntries] = useState<JournalEntry[]>([]);

useEffect(() => {
  apiClient.get<JournalEntry[]>("/api/v1/ledger/journal-entries/").then((res) => {
    setEntries(res.data);
  });
}, []);
```
* **New Journal Entry Modal:** Create a form with dynamic line item addition where total debits and credits are checked for equality in real time before enabling the Submit button.

---

### Screen 9: General Ledgers
* **File:** `src/app/(dashboard)/dashboard/ledgers/page.tsx`
* **Route:** `/dashboard/ledgers`
* **Status:** 🔴 **Unwired Empty Placeholder**

#### Backend Endpoints Required (Fully implemented on backend!)
* `GET /api/v1/ledger/accounts/` — Master accounts.
* `GET /api/v1/ledger/accounts/{id}/entries/` — Account ledger drilldown.

#### How to Wire & Fix
* Wire the button `"View Chart of Accounts"` to `router.push('/dashboard/chart-of-accounts')`.
* Render a ledger table listing each account, account code, category, and running balance.
* Clicking an account opens the account statement showing all debits, credits, and running balance.

---

### Screen 10: Users & Access Management
* **File:** `src/app/(dashboard)/dashboard/users/page.tsx`
* **Route:** `/dashboard/users`
* **Status:** 🔴 **Unwired Empty Placeholder**

#### Backend Endpoints Required (Fully implemented on backend!)
* `GET /api/v1/tenancy/members/` — List organization members.
* `POST /api/v1/tenancy/members/` — Invite member (`email`, `role`: `OWNER | ADMIN | ACCOUNTANT | AUDITOR | BOOKKEEPER`).
* `DELETE /api/v1/tenancy/members/{id}/` — Revoke member access.

#### How to Wire & Fix
```tsx
interface TeamMember {
  id: string;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  access_expires_at: string | null;
}

const [members, setMembers] = useState<TeamMember[]>([]);
const [isInviteOpen, setIsInviteOpen] = useState(false);

const loadMembers = async () => {
  const res = await apiClient.get<TeamMember[]>("/api/v1/tenancy/members/");
  setMembers(res.data);
};

useEffect(() => { loadMembers(); }, []);

const handleInvite = async (email: string, role: string) => {
  await apiClient.post("/api/v1/tenancy/members/", { email, role });
  setIsInviteOpen(false);
  loadMembers();
};
```

---

### Screen 11: Business Setup & Settings
* **File:** `src/app/(dashboard)/dashboard/setup/page.tsx`
* **Route:** `/dashboard/setup`
* **Status:** 🔴 **Unwired Static Grid (6 Cards)**

#### Backend Endpoints Required (Fully implemented on backend!)
* `GET /api/v1/tenancy/organizations/current/` — Fetch company name, TIN, Ghana GPS, tax scheme.
* `PATCH /api/v1/tenancy/organizations/current/` — Update company settings.
* `GET & POST /api/v1/tenancy/organization/settlement/` — Payout bank / MoMo destination lock.

#### How to Wire & Fix
* Wire each of the 6 tiles (*Company Profile*, *Tax Settings*, *Integrations*, etc.) to sub-modals or tab views.
* Pre-populate form fields from `organizations/current/` and save changes via `PATCH`.

---

### Screen 12: Payments & Outgoing Disbursements
* **File:** `src/app/(dashboard)/dashboard/payments/page.tsx`
* **Route:** `/dashboard/payments`
* **Status:** 🔴 **Unwired Empty Placeholder**

#### Backend Endpoints Required
* `GET /api/v1/ledger/journal-entries/?category=PAYMENT` or payment ledger filter.
* `POST /api/v1/ledger/journal-entries/` (record vendor payment or direct bank/MoMo disbursement).

#### How to Wire & Fix
* Render table of historical outgoing payments (Vendor Bill Payments, Salary Disbursements, Tax Remittances).
* Wire `"+ Record Payment"` to create a cash/bank debit-credit entry.

---

### Screen 13: Prior Period Rectification ("Fix a Past Mistake")
* **File:** `src/app/(dashboard)/dashboard/period-rectification/page.tsx`
* **Route:** `/dashboard/period-rectification`
* **Status:** 🔴 **Unwired Empty Placeholder**

#### Backend Endpoints Required (Fully implemented on backend!)
* `GET /api/v1/ledger/fiscal-periods/` — List all open and closed fiscal years/months.
* `POST /api/v1/ledger/fiscal-periods/{id}/close/` — Execute hard lock closing.

#### How to Wire & Fix
* Render a list of closed fiscal periods with lock status and closing timestamps.
* Provide an audited form for authorized accountants/owners to post prior-period adjustments with mandatory reason documentation logged directly into the immutable audit trail.

---

### Screen 14: Fixed Assets ("Things My Business Owns")
* **File:** `src/app/(dashboard)/dashboard/fixed-assets/page.tsx`
* **Route:** `/dashboard/fixed-assets`
* **Status:** 🔴 **Unwired Empty Placeholder**

#### Backend Endpoints Required
* `GET /api/v1/ledger/accounts/?category=ASSET` (filtering fixed asset accounts `1500–1899`).

#### How to Wire & Fix
* Query asset accounts from `/api/v1/ledger/accounts/`.
* Display asset categories (Motor Vehicles, Office Equipment, Computers & Electronics, Furniture).
* Wire `"+ Add Business Property"` to post an acquisition journal entry debiting Fixed Assets and crediting Cash/Bank/Payable.

---

### Screen 15: Inventory Management
* **File:** `src/app/(dashboard)/dashboard/inventory/page.tsx`
* **Route:** `/dashboard/inventory`
* **Status:** 🔴 **Unwired Empty Placeholder**

#### Backend Endpoints Required
* `GET /api/v1/ledger/accounts/` (filtering Inventory accounts `1300–1399`).
* Inventory item catalog endpoints.

#### How to Wire & Fix
* Render current inventory asset valuations and item quantities.
* Wire `"+ Add Product"` to save item definition and initialize inventory balance.

---

### Screen 16: Receipts Management
* **File:** `src/app/(dashboard)/dashboard/receipts/page.tsx`
* **Route:** `/dashboard/receipts`
* **Status:** 🔴 **Unwired Empty Placeholder**

#### Backend Endpoints Required
* Receipt attachment endpoint / Cloudflare R2 upload.

#### How to Wire & Fix
* Add a drag-and-drop file uploader accepting images (JPEG, PNG) and PDFs.
* Upload receipt image to Cloudflare R2 via presigned URL, and record an expense voucher.

---

### Screen 17: Hire an Expert
* **File:** `src/app/(dashboard)/dashboard/hire-expert/page.tsx`
* **Route:** `/dashboard/hire-expert`
* **Status:** 🟡 **Informational Directory UI**

#### How to Fix
* Wire the `"Find an expert"` buttons to open an enquiry modal that submits the user's business profile and contact information to customer support or pre-fills an email link to `support@magebooks.com`.

---

### Screen 18: Forgot Password (Partially Wired Auth Screen)
* **File:** `src/app/(auth)/forgot-password/page.tsx`
* **Route:** `/forgot-password`
* **Status:** 🟡 **Broken Backend Endpoint**

#### The Root Cause
* The frontend makes a raw `fetch` call to `POST /api/v1/auth/password-reset/`.
* This route **does not exist** in `backend/apps/authentication/urls.py`, resulting in 404/network errors.

#### How to Fix

**1. Add Backend View & URL:**
In `backend/apps/authentication/views.py`:
```python
class PasswordResetRequestView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        # Find user, generate token, send password reset email via Hubtel or SMTP
        # Always return 200 OK to prevent email enumeration
        return Response({"detail": "If an account exists, a password reset link has been dispatched."}, status=status.HTTP_200_OK)
```
In `backend/apps/authentication/urls.py`:
```python
path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
```

**2. Update Frontend Call:**
Switch from raw `fetch` to `apiClient.post("/api/v1/auth/password-reset/", { email })`.

---

### Screen 19: Public Customer Invoice Viewer (Missing Frontend Screen)
* **Backend Endpoint:** `GET /api/v1/public/invoices/{share_token}/`
* **Missing File:** `src/app/(public)/invoices/[share_token]/page.tsx`

#### How to Implement
Create a server-side read-only page using native Next.js `fetch` (per `AGENTS.md` for edge caching):
```tsx
interface PublicInvoiceProps {
  params: { share_token: string };
}

export default async function PublicInvoicePage({ params }: PublicInvoiceProps) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const res = await fetch(`${apiUrl}/api/v1/public/invoices/${params.share_token}/`, {
    next: { revalidate: 60 },
  });

  if (!res.ok) {
    return <div>Invoice not found or link has expired.</div>;
  }

  const invoice = await res.json();

  return (
    <div className="max-w-3xl mx-auto p-8">
      {/* Official invoice header with GRA clearance QR code and Pay Now MoMo button */}
      <h1 className="text-2xl font-bold">Invoice {invoice.invoice_number}</h1>
      <p>Amount Due: GHS {invoice.balance_due}</p>
      {/* Paystack / MoMo Checkout Component */}
    </div>
  );
}
```

---

## 4. Prioritized Execution Sequence (Sprint E Roadmap)

The recommended execution order tackles screens whose backend APIs are already 100% complete and verified:

```
[Phase 1: High-Traffic Core Dashboard]
  1. InvoicesPage (/dashboard/invoices) ──> Wire to /api/v1/invoices/
  2. AuditPage (/dashboard/audit) ────────> Wire to /api/v1/audit/trail/
  3. UsersPage (/dashboard/users) ────────> Wire to /api/v1/tenancy/members/
  4. DashboardPage (/dashboard) ──────────> Aggregate live data from Accounts + Invoices + Audit

[Phase 2: Financial Governance & Ledgers]
  5. TransactionsPage (/dashboard/transactions) ──> Wire to /api/v1/ledger/journal-entries/
  6. ReportsPage (/dashboard/reports) ────────────> Wire to /api/v1/ledger/reports/*
  7. PayrollPage (/dashboard/payroll) ────────────> Wire to /api/v1/payroll/runs/
  8. SetupPage (/dashboard/setup) ────────────────> Wire to /api/v1/tenancy/organizations/current/

[Phase 3: Auth & Public Portals]
  9. ForgotPasswordPage (/forgot-password) ───────> Add backend view & wire apiClient
 10. PublicInvoicePage (/invoices/[token]) ───────> Implement Next.js public cached viewer
```
