<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Mage Books SAAS — Autonomous Developer & Agent Playbook

See [`backend/AGENTS.md`](file:///m:/CODES/Work/magebooks-SAAS/backend/AGENTS.md) for full operational directives.

## Mandatory Implementation Planning Directive
Whenever an agent starts a new task or feature:
1. **Exhaustive Document Review (Zero Missed Context):**
   The agent MUST thoroughly examine all specification files in `docs/` (`DETAILED_DOCUMENTATION.md`, `Architecture Manual`, `Master 5-Sprint Implementation Plan`, `Sequence Diagrams & Lifecycle Specification`, `OVERVIEW.md`, etc.). Ensure no detail, statutory requirement, accounting invariant, or database constraint is missed.
2. **Forward-Looking Impact & Breakage Analysis:**
   The agent MUST actively inspect upcoming sprint features and downstream integrations (e.g., Invoicing, Mobile Money webhooks, GRA E-VAT clearance, General Ledger balancing, Audit/PBC exports, multi-currency, and RBAC) to verify that current implementations will not break future systems or create technical debt.
3. **Mandatory Implementation Plan & Approval Gate:**
   The implementation plan must document this future-proofing analysis (highlighting potential future breakage points and concrete architectural safeguards) and be presented in `implementation_plan.md` for explicit user approval before modifying code.

## Sprint-by-Sprint Git Protocol & Task Lifecycle
1. **Dedicated Sprint Branches:** Development is partitioned by sprint (e.g. `sprint/sprint-a-core-hardening`) off `develop`.
2. **Local-Only Task Commits (Universal across ALL Sprints A through E):** Tasks within a sprint are executed sequentially on the sprint branch. Once verified (Stage 1 + Stage 2 tests, 0 lint warnings), the task is committed to the local git branch (`git commit -m "<type>(<scope>): Task X.Y - <desc>"`). The `<type>` prefix MUST strictly represent the nature of the task (`feat`, `fix`, `refactor`, `chore`, or `test`). Individual tasks are **NEVER pushed to upstream/remote** until the full sprint completes.
3. **Sprint Push & PR Gate:** Only when the entire sprint is complete and full regression tests pass is the sprint branch pushed to origin for PR review into `develop`.
4. **Mandatory PR Merge Check & Branch Cleanup:** Before starting a subsequent sprint, verify the previous sprint PR is merged, checkout `develop`, pull latest changes, and delete both local (`git branch -d`) and remote (`git push origin --delete`) sprint branches.

## Frontend-to-Backend Wiring Architecture
1. **Client Components, Dashboard, Forms, and PWA (95% of the application):**
   - MUST use Axios via a centralized singleton: `src/lib/apiClient.ts`.
   - Configure `baseURL: process.env.NEXT_PUBLIC_API_URL`, `withCredentials: true`, and global request/response interceptors for `X-Organization-ID`, `X-CSRFToken`, and 401 refresh queuing.
2. **Server-Side Public Read-Only Pages:**
   - MUST use Next.js native `fetch` when edge caching is required on public endpoints (e.g., public invoice viewer).


