# Mage Books SAAS — Frontend Breakage Points, Inconsistencies & UX Traps Audit

> **Exhaustive Technical Audit of Runtime Breakages, 404 Traps, Statutory Copy Inconsistencies, Missing Navigation Routes, and Unwired Mock Shells across the Next.js Frontend (`src/`).**
> 
> **Date:** September 2026 | **Status:** Active Reference & Remediation Blueprint  
> **Target System:** Frontend PWA (`src/`) | Next.js 16 (App Router) / React 19 / TailwindCSS v4 / TypeScript 5

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Priority Classification Matrix](#2-priority-classification-matrix)
3. [P1: Missing Core Navigation & Route Absence](#3-p1-missing-core-navigation--route-absence)
   - [3.1 Missing `/dashboard/invoices` Navigation Route and Directory](#31-missing-dashboardinvoices-navigation-route-and-directory)
   - [3.2 Dead `/forgot-password` Route in Login Screen (404 Error)](#32-dead-forgot-password-route-in-login-screen-404-error)
   - [3.3 Dead Anchors (`href="#"`) across Dashboard Subpages](#33-dead-anchors-href-across-dashboard-subpages)
4. [P2: Statutory & Regulatory Inconsistencies with Backend Rules](#4-p2-statutory--regulatory-inconsistencies-with-backend-rules)
   - [4.1 Outdated Statutory VAT Registration Threshold (GHS 200,000 vs GHS 750,000)](#41-outdated-statutory-vat-registration-threshold-ghs-200000-vs-ghs-750000)
   - [4.2 Statutory Reporting Cycle Confusion (Quarterly vs Monthly VAT/PAYE)](#42-statutory-reporting-cycle-confusion-quarterly-vs-monthly-vatpaye)
   - [4.3 Missing Client-Side Input Formatting for Ghana TIN and Ghana Card](#43-missing-client-side-input-formatting-for-ghana-tin-and-ghana-card)
5. [P2 / P3: Client Security, Session & State Management Gaps](#5-p2--p3-client-security-session--state-management-gaps)
   - [5.1 Missing 15-Minute Inactivity Screen Auto-Lock](#51-missing-15-minute-inactivity-screen-auto-lock)
   - [5.2 Orphaned Client-Side Crypto & PWA IndexedDB Cache Module](#52-orphaned-client-side-crypto--pwa-indexeddb-cache-module)
   - [5.3 Unsynchronized Mode State between LocalStorage and Backend Tenant Record](#53-unsynchronized-mode-state-between-localstorage-and-backend-tenant-record)
6. [P3: Unwired Mock Shells & API Integration Absence](#6-p3-unwired-mock-shells--api-integration-absence)
   - [6.1 Unwired Authentication Forms (Login & Signup)](#61-unwired-authentication-forms-login--signup)
   - [6.2 Unwired 6-Step Onboarding Wizard Submission](#62-unwired-6-step-onboarding-wizard-submission)
   - [6.3 16 Placeholder Dashboard Subpages](#63-16-placeholder-dashboard-subpages)
   - [6.4 Hardcoded TopNavBar Elements & Missing Profile / Logout Menu](#64-hardcoded-topnavbar-elements--missing-profile--logout-menu)
7. [Remediation Action Plan & Integration Checklist](#7-remediation-action-plan--integration-checklist)

---

# 1. Executive Summary

This audit inspects the frontend Next.js codebase (`src/`) to identify:
1. Places where user interaction will trigger runtime exceptions or dead 404 pages.
2. Inconsistencies between UI copy and Ghanaian statutory accounting law (Value Added Tax Act, 2025, Act 1151).
3. Client-side security and session gaps mandated by the Architecture Manual (15-minute idle lock, encrypted PWA cache).
4. Unwired mock forms and placeholder dashboard pages that must be connected to the Django REST backend.

While the frontend has high visual polish matching the brand design system, key transactional routes (such as `/dashboard/invoices`) and backend API integrations are not yet wired.

---

# 2. Priority Classification Matrix

| Level | Issue Description | File Location | Operational Impact |
| :-: | :--- | :--- | :--- |
| **P1** | Missing `/dashboard/invoices` Route | [`src/components/dashboard/SideNavBar.tsx`](file:///m:/CODES/Work/magebooks-SAAS/src/components/dashboard/SideNavBar.tsx) | Central platform feature (invoicing) has no link or dedicated view in the dashboard. |
| **P1** | Dead `/forgot-password` Route | [`src/app/(auth)/login/page.tsx:56-60`](file:///m:/CODES/Work/magebooks-SAAS/src/app/(auth)/login/page.tsx#L56-L60) | Clicking "Forgot Password?" directly renders a Next.js 404 page. |
| **P2** | Outdated VAT Threshold in UI | [`src/components/onboarding/Step2VATStatus.tsx:78`](file:///m:/CODES/Work/magebooks-SAAS/src/components/onboarding/Step2VATStatus.tsx#L78) | Displays obsolete GHS 200,000 threshold instead of statutory Act 1151 GHS 750,000 threshold. |
| **P2** | Misleading Fiscal Period Default | [`src/components/onboarding/Step4FiscalCalendar.tsx:55`](file:///m:/CODES/Work/magebooks-SAAS/src/components/onboarding/Step4FiscalCalendar.tsx#L55) | Suggests "Quarterly" as standard for tax reporting; GRA statutory returns are monthly. |
| **P2** | Missing TIN / Ghana Card Masks | [`src/components/onboarding/Step1CompanyDetails.tsx`](file:///m:/CODES/Work/magebooks-SAAS/src/components/onboarding/Step1CompanyDetails.tsx) | Raw unvalidated inputs trigger unhandled backend 400 validation failures. |
| **P2** | Missing 15-Minute Inactivity Lock | [`src/app/(dashboard)/layout.tsx`](file:///m:/CODES/Work/magebooks-SAAS/src/app/(dashboard)/layout.tsx) | Shared Ghanaian office terminals remain unlocked indefinitely (Architecture Manual §4.8.1 violation). |
| **P3** | Orphaned PWA Cache Crypto Utility | [`src/lib/crypto/pwa-cache-encryption.ts`](file:///m:/CODES/Work/magebooks-SAAS/src/lib/crypto/pwa-cache-encryption.ts) | 192 lines of AES-GCM encryption code are completely unused and unreferenced. |
| **P3** | Unsynchronized Experience Mode | [`src/contexts/ModeContext.tsx:21-28`](file:///m:/CODES/Work/magebooks-SAAS/src/contexts/ModeContext.tsx#L21-L28) | Simple vs Full mode is saved only in `localStorage`, resetting on cross-device login. |
| **P3** | Unwired Auth & Onboarding Forms | `src/app/(auth)/*` & `src/app/(onboarding)/*` | Submit buttons perform `router.push()` without network calls to backend APIs. |
| **P3** | 16 Unwired Dashboard Mock Shells | `src/app/(dashboard)/dashboard/*` | 16 of 17 dashboard subpages display identical static "No transactions yet" mock text. |
| **P3** | Fake Search Input & Hardcoded TopBar | [`src/components/dashboard/TopNavBar.tsx`](file:///m:/CODES/Work/magebooks-SAAS/src/components/dashboard/TopNavBar.tsx) | Search is a non-interactive `<div>`; organization name and user avatar are hardcoded. |

---

# 3. P1: Missing Core Navigation & Route Absence

### 3.1 Missing `/dashboard/invoices` Navigation Route and Directory
* **Location**: [`src/components/dashboard/SideNavBar.tsx:16-57`](file:///m:/CODES/Work/magebooks-SAAS/src/components/dashboard/SideNavBar.tsx#L16-L57) & [`src/app/(dashboard)/dashboard/`](file:///m:/CODES/Work/magebooks-SAAS/src/app/(dashboard)/dashboard)
* **Failure Mechanism**:
  The sidebar navigation includes links for `/dashboard/receipts`, `/dashboard/accounts-receivable`, and `/dashboard/transactions`, but **completely omits a dedicated route for `/dashboard/invoices`**.
  - While backend invoicing endpoints (`/api/v1/invoices/`) and GRA E-VAT clearance are the platform's flagship features, there is no directory `src/app/(dashboard)/dashboard/invoices/` and no link in `SIMPLE_NAV` or `FULL_NAV`.
* **Remediation**:
  1. Add `{ href: "/dashboard/invoices", label: "Invoices", icon: "/assets/nav-invoices.svg", w: 20, h: 20 }` to `SIMPLE_NAV` and `FULL_NAV`.
  2. Create page directory `src/app/(dashboard)/dashboard/invoices/page.tsx` with invoice data grid, status badges (Draft, Issued, Cleared, Overdue), and "Create Invoice" modal.

---

### 3.2 Dead `/forgot-password` Route in Login Screen (404 Error)
* **Location**: [`src/app/(auth)/login/page.tsx:56-60`](file:///m:/CODES/Work/magebooks-SAAS/src/app/(auth)/login/page.tsx#L56-L60)
* **Offending Code**:
  ```tsx
  <Link href="/forgot-password" className="text-sm text-[#004ac6] hover:underline">
    Forgot Password?
  </Link>
  ```
* **Failure Mechanism**:
  The directory `src/app/(auth)/forgot-password/page.tsx` does not exist in the project tree. Clicking this link on the login page renders an unhandled Next.js 404 page.
* **Remediation**:
  Create `src/app/(auth)/forgot-password/page.tsx` with email input and password reset instructions, or route to a support modal.

---

### 3.3 Dead Anchors (`href="#"`) across Dashboard Subpages
* **Location**: [`src/app/(dashboard)/dashboard/transactions/page.tsx:37-39`](file:///m:/CODES/Work/magebooks-SAAS/src/app/(dashboard)/dashboard/transactions/page.tsx#L37-L39) (and replicated across multiple dashboard screens)
* **Offending Code**:
  ```tsx
  <Link href="#" className="hover:underline">Privacy Policy</Link>
  <Link href="#" className="hover:underline">Terms of Service</Link>
  <Link href="#" className="hover:underline">Help Center</Link>
  ```
* **Failure Mechanism**:
  Clicking `href="#"` jumps the user viewport back to the top without navigating, confusing users and violating accessibility guidelines.
* **Remediation**:
  Replace `href="#"` with valid external or legal documentation routes (`/privacy`, `/terms`, `/help`) or open in a modal.

---

# 4. P2: Statutory & Regulatory Inconsistencies with Backend Rules

### 4.1 Outdated Statutory VAT Registration Threshold (GHS 200,000 vs GHS 750,000)
* **Location**: [`src/components/onboarding/Step2VATStatus.tsx:78`](file:///m:/CODES/Work/magebooks-SAAS/src/components/onboarding/Step2VATStatus.tsx#L78)
* **Offending Code**:
  ```tsx
  VAT registration is mandatory in Ghana for businesses making taxable supplies exceeding GHS 200,000 over 12 months.
  ```
* **Failure Mechanism**:
  Under the **Value Added Tax Act, 2025 (Act 1151)**, effective January 1, 2026, the Parliament of Ghana raised the statutory mandatory VAT registration threshold to **GHS 750,000**.
  - The backend statutory engine enforces `STATUTORY_VAT_THRESHOLD = Decimal('750000.0000')` ([`apps/tax/services.py:28`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/tax/services.py#L28)).
  - Displaying GHS 200,000 misinforms Ghanaian business owners and causes non-qualifying sole traders to register for VAT erroneously.
* **Remediation**:
  Update the copy to:
  ```tsx
  VAT registration is mandatory in Ghana for businesses making taxable supplies exceeding GHS 750,000 over 12 months under Act 1151.
  ```

---

### 4.2 Statutory Reporting Cycle Confusion (Quarterly vs Monthly VAT/PAYE)
* **Location**: [`src/components/onboarding/Step4FiscalCalendar.tsx:55`](file:///m:/CODES/Work/magebooks-SAAS/src/components/onboarding/Step4FiscalCalendar.tsx#L55) & [`src/app/(onboarding)/onboarding/page.tsx:42`](file:///m:/CODES/Work/magebooks-SAAS/src/app/(onboarding)/onboarding/page.tsx#L42)
* **Offending Code**:
  ```tsx
  // Step4FiscalCalendar.tsx:
  { key: "quarterly", label: "Quarterly", desc: "Standard for tax reporting cycles.", icon: "/assets/quarterly.svg" }

  // OnboardingPage.tsx:
  periodLength: "quarterly",
  ```
* **Failure Mechanism**:
  In Ghana, statutory returns for VAT, NHIL, GETFund, and PAYE must be declared and paid **monthly** by the last working day of the following month (and by the 15th for PAYE). Quarterly cycles only apply to provisional corporate income tax installments.
  - The backend `FiscalCalendar` model defaults to `period_length = "monthly"` ([`apps/ledger/models.py:54`](file:///m:/CODES/Work/magebooks-SAAS/backend/apps/ledger/models.py#L54)).
  - Telling users that Quarterly is "Standard for tax reporting cycles" leads Ghanaian SMEs into non-compliance and late-filing statutory penalties.
* **Remediation**:
  1. Default `periodLength` in `OnboardingPage.tsx` to `"monthly"`.
  2. Update the description for Monthly to: *"Recommended & standard for monthly GRA VAT & PAYE statutory returns."*

---

### 4.3 Missing Client-Side Input Formatting for Ghana TIN and Ghana Card
* **Location**: [`src/components/onboarding/Step1CompanyDetails.tsx:51-64`](file:///m:/CODES/Work/magebooks-SAAS/src/components/onboarding/Step1CompanyDetails.tsx#L51-L64)
* **Failure Mechanism**:
  The backend enforces strict statutory regexes:
  - Ghana Business TIN: `^[CPVGP]\d{10}$` (e.g. `C0001234567`)
  - Ghana National Identity Card (NIA): `^GHA-\d{9}-\d$` (e.g. `GHA-123456789-1`)
  The frontend inputs accept arbitrary unformatted strings with zero input masking or pattern validation, leading to cryptic 400 Bad Request responses when submitting to the backend.
* **Remediation**:
  Add client-side format masks and instant validation regex feedback on blur.

---

# 5. P2 / P3: Client Security, Session & State Management Gaps

### 5.1 Missing 15-Minute Inactivity Screen Auto-Lock
* **Reference**: *Architecture Manual §4.8.1 (Client-Side Fail-Secure Hygiene)*:
  > *"To safeguard shared office terminals in Ghana, client applications detect idle time and automatically lock the screen after 15 minutes, clearing active memory."*
* **Failure Mechanism**:
  No idle-timer hook or screen-lock overlay is currently implemented in `src/app/(dashboard)/layout.tsx` or `src/contexts/`. Terminal screens remain open indefinitely, exposing financial ledgers if a clerk walks away.
* **Remediation**:
  Implement a `useIdleTimer` hook listening to mouse/keyboard/touch events that presents a PIN/password re-authentication modal after 15 minutes of inactivity.

---

### 5.2 Orphaned Client-Side Crypto & PWA IndexedDB Cache Module
* **Location**: [`src/lib/crypto/pwa-cache-encryption.ts`](file:///m:/CODES/Work/magebooks-SAAS/src/lib/crypto/pwa-cache-encryption.ts) (192 lines)
* **Failure Mechanism**:
  The file defines complete WebCrypto AES-GCM (256-bit key, PBKDF2) encryption helpers for customer PII offline storage (MUC 3.1).
  - However, **it is never imported or called anywhere in `src/`**.
  - No IndexedDB storage wrapper exists to persist cached contacts, invoices, or accounts offline.
* **Remediation**:
  Either wire `pwa-cache-encryption.ts` to a local IndexedDB manager (e.g. `idb` library) or document its planned activation in Sprint 6.

---

### 5.3 Unsynchronized Mode State between LocalStorage and Backend Tenant Record
* **Location**: [`src/contexts/ModeContext.tsx:21-28`](file:///m:/CODES/Work/magebooks-SAAS/src/contexts/ModeContext.tsx#L21-L28)
* **Failure Mechanism**:
  The user's experience mode (`simple` vs. `full`) is toggled exclusively in client `localStorage` under `mage-mode`. It is not synchronized with `Organization.default_experience_mode` on the backend, meaning switching browsers or devices resets the user's UI mode.
* **Remediation**:
  When a user toggles the mode switch in `SideNavBar.tsx`, dispatch a background `PATCH /api/v1/tenancy/organizations/current/` request to save their preference to the database.

---

# 6. P3: Unwired Mock Shells & API Integration Absence

### 6.1 Unwired Authentication Forms (Login & Signup)
* **Location**: [`src/app/(auth)/login/page.tsx:13-16`](file:///m:/CODES/Work/magebooks-SAAS/src/app/(auth)/login/page.tsx#L13-L16) & [`src/app/(auth)/signup/page.tsx:16-20`](file:///m:/CODES/Work/magebooks-SAAS/src/app/(auth)/signup/page.tsx#L16-L20)
* **Offending Code**:
  ```tsx
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: wire up auth logic
    router.push("/onboarding");
  };
  ```
* **Failure Mechanism**:
  The forms accept any string, execute zero network requests to `/api/v1/auth/login/` or `/api/v1/auth/signup/`, and route directly to `/onboarding`.
* **Remediation**:
  Wire `fetch("/api/v1/auth/login/", { method: "POST", credentials: "include", ... })` and store user state in React context.

---

### 6.2 Unwired 6-Step Onboarding Wizard Submission
* **Location**: [`src/app/(onboarding)/onboarding/page.tsx:51-54`](file:///m:/CODES/Work/magebooks-SAAS/src/app/(onboarding)/onboarding/page.tsx#L51-L54)
* **Offending Code**:
  ```tsx
  const handleFinish = () => {
    // TODO: submit onboarding data to API
    router.push("/dashboard");
  };
  ```
* **Failure Mechanism**:
  All collected company details, TIN, director Ghana Card PIN, and initial contacts collected in Steps 1–6 are discarded from React state on finish, creating no organization or memberships in the backend.
* **Remediation**:
  Connect `handleFinish` to backend onboarding/organization creation endpoints.

---

### 6.3 16 Placeholder Dashboard Subpages
* **Location**: [`src/app/(dashboard)/dashboard/*`](file:///m:/CODES/Work/magebooks-SAAS/src/app/(dashboard)/dashboard) (16 pages)
* **Offending Code**:
  ```tsx
  <p className="font-semibold text-[#141b2b] text-lg mb-1">No transactions yet</p>
  <p className="text-sm">Your transaction history will appear here.</p>
  ```
* **Failure Mechanism**:
  16 out of 17 dashboard subpages display identical static mock text without fetching data from the corresponding backend REST endpoints (`/api/v1/reports/`, `/api/v1/payroll/runs/`, `/api/v1/audit/trail/`, etc.).

---

### 6.4 Hardcoded TopNavBar Elements & Missing Profile / Logout Menu
* **Location**: [`src/components/dashboard/TopNavBar.tsx:7-42`](file:///m:/CODES/Work/magebooks-SAAS/src/components/dashboard/TopNavBar.tsx#L7-L42)
* **Failure Mechanism**:
  - Organization name is hardcoded to `"Kurt Trading Enterprise"`.
  - Search bar is a non-interactive styled `<div>` rather than an `<input>` element.
  - Refresh and bell notification buttons have no click handlers.
  - There is no user profile dropdown, organization switcher, or logout button.
* **Remediation**:
  Render active tenant name from auth context, turn search into a functional input, and add user profile dropdown with logout action.

---

# 7. Remediation Action Plan & Integration Checklist

- [ ] **P1**: Create `src/app/(dashboard)/dashboard/invoices/page.tsx` and add Invoices navigation item to `SideNavBar.tsx`.
- [ ] **P1**: Create `src/app/(auth)/forgot-password/page.tsx` to eliminate the 404 trap on the login screen.
- [ ] **P2**: Update `src/components/onboarding/Step2VATStatus.tsx` threshold text to **GHS 750,000** under Act 1151.
- [ ] **P2**: Change default `periodLength` in `OnboardingPage.tsx` to `"monthly"` and update descriptive copy.
- [ ] **P2**: Add regex formatting masks for Ghana TIN (`^[CPVGP]\d{10}$`) and Ghana Card (`^GHA-\d{9}-\d$`).
- [ ] **P2**: Implement 15-minute idle auto-lock hook in `src/app/(dashboard)/layout.tsx`.
- [ ] **P3**: Wire authentication forms (`/login`, `/signup`) to backend JWT cookie endpoints (`/api/v1/auth/login/`).
- [ ] **P3**: Wire onboarding wizard submission to backend organization creation endpoint.
- [ ] **P3**: Convert `TopNavBar.tsx` search `<div>` to a functional `<input>` and dynamic tenant name/profile dropdown.
- [ ] **P3**: Replace dead `href="#"` links with valid routes.
