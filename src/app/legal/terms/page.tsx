import Link from "next/link";

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-[#f8f9fa] text-[#1e293b] py-12 px-6 lg:px-8">
      <div className="max-w-4xl mx-auto bg-white rounded-2xl border border-[#c3c6d7] p-8 md:p-12 shadow-sm">
        <div className="mb-8 border-b border-[#e2e8f0] pb-6">
          <Link
            href="/dashboard"
            className="text-xs font-semibold text-[#2563eb] hover:underline mb-4 inline-block"
          >
            &larr; Back to Dashboard
          </Link>
          <h1 className="text-3xl font-extrabold text-[#0f172a] tracking-tight">
            Terms of Service
          </h1>
          <p className="text-sm text-[#64748b] mt-2">
            Last Updated: September 30, 2026 &bull; Governing Law: Republic of Ghana
          </p>
        </div>

        <div className="space-y-6 text-sm leading-relaxed text-[#334155]">
          <section>
            <h2 className="text-lg font-bold text-[#0f172a] mb-2">1. Agreement to Terms</h2>
            <p>
              By accessing or using MageBooks Enterprise Financial Suite, you agree to be bound by these
              Terms of Service and all applicable Ghanaian commercial laws, accounting standards, and
              taxation requirements.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0f172a] mb-2">2. Double-Entry Accounting Invariants</h2>
            <p>
              MageBooks enforces strict double-entry ledger balancing. Users acknowledge that posted
              journal entries and approved payroll runs cannot be unilaterally deleted or mutated.
              Corrections must be executed via formal adjusting credit notes, debit notes, or reversal
              journal entries in accordance with International Financial Reporting Standards (IFRS)
              for SMEs.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0f172a] mb-2">3. Sole Destroyer &amp; Role-Based Governance</h2>
            <p>
              Organization ownership and destruction privileges are strictly regulated. Only the verified
              Owner of an enterprise may initiate organizational archival. Dual-factor authorization
              (TOTP) is enforced on sensitive administrative operations.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0f172a] mb-2">4. Mobile Money &amp; Banking Settlements</h2>
            <p>
              Settlement payouts via Ghana Interbank Payment and Settlement Systems (GhIPSS) and Mobile
              Money networks (MTN, Telecel, AT) are subject to network availability and partner gateway
              verifications. MageBooks provides automated idempotent webhook reconciliation.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0f172a] mb-2">5. Governing Jurisdiction</h2>
            <p>
              These terms are governed by and construed under the laws of the Republic of Ghana. Any
              disputes shall be settled under the jurisdiction of the High Court (Commercial Division)
              in Accra.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
