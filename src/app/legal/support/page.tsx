import Link from "next/link";

export default function SupportPage() {
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
            Help &amp; Support Center
          </h1>
          <p className="text-sm text-[#64748b] mt-2">
            MageBooks Customer Care &bull; Dedicated Accounting &amp; Compliance Advisory
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="border border-[#e2e8f0] rounded-xl p-6 bg-[#f8fafc]">
            <h2 className="text-base font-bold text-[#0f172a] mb-2">Technical &amp; Billing Support</h2>
            <p className="text-xs text-[#64748b] mb-4">
              Need assistance with system navigation, PWA offline sync, or bank settlement?
            </p>
            <p className="text-sm font-semibold text-[#2563eb]">support@magebooks.com</p>
            <p className="text-xs text-[#64748b] mt-1">+233 (0) 30 200 0000 (Mon-Fri 8am-5pm GMT)</p>
          </div>

          <div className="border border-[#e2e8f0] rounded-xl p-6 bg-[#f8fafc]">
            <h2 className="text-base font-bold text-[#0f172a] mb-2">GRA Tax &amp; E-VAT Assistance</h2>
            <p className="text-xs text-[#64748b] mb-4">
              Help with Ghana Card / TIN validation, E-VAT digital signatures, and monthly returns.
            </p>
            <p className="text-sm font-semibold text-[#2563eb]">tax-compliance@magebooks.com</p>
            <p className="text-xs text-[#64748b] mt-1">Accra, Ghana &bull; Dedicated Tax Specialist Team</p>
          </div>
        </div>

        <div className="space-y-4">
          <h2 className="text-lg font-bold text-[#0f172a]">Frequently Asked Questions</h2>
          <div className="border border-[#e2e8f0] rounded-xl p-4">
            <h3 className="text-sm font-bold text-[#1e293b]">How does offline invoice creation work?</h3>
            <p className="text-xs text-[#64748b] mt-1">
              MageBooks uses encrypted IndexedDB local storage. When you are offline, you can draft
              invoices freely. Once internet connectivity is restored, drafts automatically sync with
              the server.
            </p>
          </div>
          <div className="border border-[#e2e8f0] rounded-xl p-4">
            <h3 className="text-sm font-bold text-[#1e293b]">Can I switch between Simple and Professional modes?</h3>
            <p className="text-xs text-[#64748b] mt-1">
              Yes. You can switch modes at any time from the top navigation bar or settings. In Simple
              Mode, technical accounting terms are simplified into plain language while retaining
              full double-entry integrity underneath.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
