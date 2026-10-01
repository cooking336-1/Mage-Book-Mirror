export default function PaymentsPage() {
  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">Payments</h1>
          <p className="text-[#434655] text-base mt-1">Track outgoing payments and disbursements.</p>
        </div>
        <button
          type="button"
          className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-medium px-4 h-10 rounded-lg shadow-sm transition-colors"
        >
          + Record Payment
        </button>
      </div>

      <div className="bg-white border border-[#c3c6d7] rounded-xl p-12 text-center text-[#434655]">
        <p className="font-semibold text-[#141b2b] text-lg mb-1">No payments recorded</p>
        <p className="text-sm">Payments you&apos;ve made will appear here.</p>
      </div>
    </div>
  );
}
