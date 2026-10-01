export default function LedgersPage() {
  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">Ledgers</h1>
          <p className="text-[#434655] text-base mt-1">General ledger balances and account activity.</p>
        </div>
        <button
          type="button"
          className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-medium px-4 h-10 rounded-lg shadow-sm transition-colors"
        >
          View Chart of Accounts
        </button>
      </div>

      <div className="bg-white border border-[#c3c6d7] rounded-xl p-12 text-center text-[#434655]">
        <p className="font-semibold text-[#141b2b] text-lg mb-1">No ledger entries</p>
        <p className="text-sm">Ledger accounts and postings will appear here.</p>
      </div>
    </div>
  );
}
