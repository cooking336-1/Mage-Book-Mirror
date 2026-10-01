"use client";

import { useMode } from "@/contexts/ModeContext";

export default function AccountsPayablePage() {
  const { mode } = useMode();
  const title = mode === "simple" ? "Money I Owe" : "Accounts Payable";
  const subtitle =
    mode === "simple"
      ? "Bills and supplier invoices you need to pay."
      : "Manage outstanding vendor bills, due dates, and supplier balances.";

  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">{title}</h1>
          <p className="text-[#434655] text-base mt-1">{subtitle}</p>
        </div>
        <button
          type="button"
          className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-medium px-4 h-10 rounded-lg shadow-sm transition-colors"
        >
          {mode === "simple" ? "+ Add Bill to Pay" : "+ New Bill"}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {[
          { label: mode === "simple" ? "Total Owed" : "Total Outstanding", val: "GH¢ 0.00", sub: "0 unpaid bills" },
          { label: mode === "simple" ? "Past Due" : "Overdue Bills", val: "GH¢ 0.00", sub: "Requires attention" },
          { label: "Due This Month", val: "GH¢ 0.00", sub: "Upcoming payments" },
        ].map((c) => (
          <div key={c.label} className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-xs">
            <p className="text-xs font-semibold text-[#434655] uppercase tracking-wide">{c.label}</p>
            <p className="text-2xl font-bold text-[#141b2b] mt-1">{c.val}</p>
            <p className="text-xs text-[#64748b] mt-1">{c.sub}</p>
          </div>
        ))}
      </div>

      <div className="bg-white border border-[#c3c6d7] rounded-xl p-12 text-center text-[#434655]">
        <p className="font-semibold text-[#141b2b] text-lg mb-1">No outstanding bills</p>
        <p className="text-sm">Bills received from suppliers will appear here.</p>
      </div>
    </div>
  );
}
