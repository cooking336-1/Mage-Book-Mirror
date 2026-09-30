"use client";

import { useState } from "react";
import Link from "next/link";
import { useMode } from "@/contexts/ModeContext";

type InvoiceItem = {
  id: string;
  invoice_number: string;
  customer_name: string;
  issue_date: string;
  due_date: string;
  subtotal: number;
  total_tax: number;
  total_amount: number;
  balance_due: number;
  status: "DRAFT" | "PENDING_GRA" | "CLEARED" | "PAID" | "OVERDUE";
  gra_clearance_code: string | null;
  share_token: string;
};

const MOCK_INVOICES: InvoiceItem[] = [
  {
    id: "01923b12-9214-7221-a1b2-000000000001",
    invoice_number: "INV-ACCRA-2026-00042",
    customer_name: "Tema Logistics & Haulage Ltd",
    issue_date: "2026-09-15",
    due_date: "2026-10-15",
    subtotal: 12000.0,
    total_tax: 2400.0,
    total_amount: 14400.0,
    balance_due: 0.0,
    status: "PAID",
    gra_clearance_code: "GRA-ACCRA-2026-C89912",
    share_token: "a1b2c3d4-e5f6-47a8-b9c0-112233445566",
  },
  {
    id: "01923b12-9214-7221-a1b2-000000000002",
    invoice_number: "INV-ACCRA-2026-00043",
    customer_name: "Kumasi Timber & Hardware Co",
    issue_date: "2026-09-20",
    due_date: "2026-10-20",
    subtotal: 18500.0,
    total_tax: 3700.0,
    total_amount: 22200.0,
    balance_due: 22200.0,
    status: "CLEARED",
    gra_clearance_code: "GRA-ACCRA-2026-C89913",
    share_token: "b2c3d4e5-f6a7-48b9-c0d1-223344556677",
  },
  {
    id: "01923b12-9214-7221-a1b2-000000000003",
    invoice_number: "INV-ACCRA-2026-00044",
    customer_name: "Osu Retail Emporium Ltd",
    issue_date: "2026-09-25",
    due_date: "2026-10-25",
    subtotal: 4500.0,
    total_tax: 900.0,
    total_amount: 5400.0,
    balance_due: 5400.0,
    status: "PENDING_GRA",
    gra_clearance_code: null,
    share_token: "c3d4e5f6-a7b8-49c0-d1e2-334455667788",
  },
  {
    id: "01923b12-9214-7221-a1b2-000000000004",
    invoice_number: "INV-ACCRA-2026-00045",
    customer_name: "Spintex Agro Processing Enterprise",
    issue_date: "2026-08-10",
    due_date: "2026-09-10",
    subtotal: 6800.0,
    total_tax: 1360.0,
    total_amount: 8160.0,
    balance_due: 8160.0,
    status: "OVERDUE",
    gra_clearance_code: "GRA-ACCRA-2026-C88741",
    share_token: "d4e5f6a7-b8c9-40d1-e2f3-445566778899",
  },
  {
    id: "01923b12-9214-7221-a1b2-000000000005",
    invoice_number: "INV-ACCRA-2026-00046",
    customer_name: "Airport West Consulting Group",
    issue_date: "2026-09-28",
    due_date: "2026-10-28",
    subtotal: 3200.0,
    total_tax: 640.0,
    total_amount: 3840.0,
    balance_due: 3840.0,
    status: "DRAFT",
    gra_clearance_code: null,
    share_token: "e5f6a7b8-c9d0-41e2-f3a4-556677889900",
  },
];

export default function InvoicesPage() {
  const { mode } = useMode();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const filteredInvoices = MOCK_INVOICES.filter((inv) => {
    const matchesSearch =
      inv.invoice_number.toLowerCase().includes(search.toLowerCase()) ||
      inv.customer_name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "ALL" || inv.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const totalInvoiced = MOCK_INVOICES.reduce((acc, inv) => acc + inv.total_amount, 0);
  const outstanding = MOCK_INVOICES.reduce((acc, inv) => acc + inv.balance_due, 0);
  const overdue = MOCK_INVOICES.filter((inv) => inv.status === "OVERDUE").reduce(
    (acc, inv) => acc + inv.balance_due,
    0
  );
  const clearedCount = MOCK_INVOICES.filter((inv) => inv.gra_clearance_code !== null).length;

  const handleCopyLink = (shareToken: string, id: string) => {
    const url = `${window.location.origin}/invoices/public/${shareToken}`;
    navigator.clipboard.writeText(url);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getStatusBadge = (status: InvoiceItem["status"]) => {
    switch (status) {
      case "PAID":
        return "bg-[#ecfdf5] text-[#059669] border-[#a7f3d0]";
      case "CLEARED":
        return "bg-[#eff6ff] text-[#2563eb] border-[#bfdbfe]";
      case "PENDING_GRA":
        return "bg-[#fffbeb] text-[#d97706] border-[#fde68a]";
      case "OVERDUE":
        return "bg-[#fef2f2] text-[#dc2626] border-[#fecaca]";
      case "DRAFT":
      default:
        return "bg-[#f3f4f6] text-[#4b5563] border-[#e5e7eb]";
    }
  };

  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      {/* ── Page Header ────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
            {mode === "simple" ? "Invoices" : "Tax Invoices"}
          </h1>
          <p className="text-[#434655] text-base mt-1">
            {mode === "simple"
              ? "Create, track, and share invoices with your customers."
              : "Manage Act 1151 compliant tax invoices, GRA CIS clearance, and receivables."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="border border-[#c3c6d7] hover:bg-[#f1f3ff] text-[#141b2b] text-sm font-semibold px-4 h-10 rounded-lg transition-colors flex items-center gap-2"
          >
            Export CSV
          </button>
          <button
            type="button"
            className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors flex items-center gap-2"
          >
            + Create Invoice
          </button>
        </div>
      </div>

      {/* ── Summary KPI Cards ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 flex flex-col gap-2">
          <p className="text-[#434655] text-xs font-semibold uppercase tracking-[0.35px]">
            Total Invoiced
          </p>
          <p className="text-[22px] font-black text-[#141b2b]">
            GH¢ {totalInvoiced.toLocaleString("en-GH", { minimumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-[#059669] font-medium">5 total active records</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 flex flex-col gap-2">
          <p className="text-[#434655] text-xs font-semibold uppercase tracking-[0.35px]">
            Outstanding
          </p>
          <p className="text-[22px] font-black text-[#2563eb]">
            GH¢ {outstanding.toLocaleString("en-GH", { minimumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-[#434655] font-medium">Awaiting customer payment</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 flex flex-col gap-2">
          <p className="text-[#434655] text-xs font-semibold uppercase tracking-[0.35px]">
            Overdue Receivables
          </p>
          <p className="text-[22px] font-black text-[#dc2626]">
            GH¢ {overdue.toLocaleString("en-GH", { minimumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-[#dc2626] font-medium">1 invoice past due date</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 flex flex-col gap-2">
          <p className="text-[#434655] text-xs font-semibold uppercase tracking-[0.35px]">
            GRA E-VAT Cleared
          </p>
          <p className="text-[22px] font-black text-[#141b2b]">
            {clearedCount} / {MOCK_INVOICES.length}
          </p>
          <p className="text-xs text-[#059669] font-medium">Act 1151 verified</p>
        </div>
      </div>

      {/* ── Filters & Search ───────────────────────────────────────── */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl p-4 flex flex-col sm:flex-row gap-4 justify-between items-center">
        <div className="relative w-full sm:w-80">
          <input
            type="text"
            placeholder="Search invoice # or customer..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-10 pl-10 pr-4 text-sm bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg focus:outline-none focus:border-[#2563eb] text-[#141b2b] placeholder-[#737687]"
          />
          <span className="absolute left-3 top-2.5 text-[#737687]">🔍</span>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <label htmlFor="status-filter" className="text-xs font-semibold text-[#434655] uppercase tracking-[0.35px] whitespace-nowrap">
            Status:
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-10 px-3 text-sm bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg text-[#141b2b] focus:outline-none focus:border-[#2563eb]"
          >
            <option value="ALL">All Invoices</option>
            <option value="PAID">Paid</option>
            <option value="CLEARED">Cleared (Pending Payment)</option>
            <option value="PENDING_GRA">Pending GRA</option>
            <option value="OVERDUE">Overdue</option>
            <option value="DRAFT">Draft</option>
          </select>
        </div>
      </div>

      {/* ── Invoice Table ──────────────────────────────────────────── */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-[0px_1px_2px_rgba(0,0,0,0.04)]">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="bg-[#f8f9ff] border-b border-[#c3c6d7] text-[#434655] text-xs font-semibold uppercase tracking-[0.35px]">
                <th className="py-3.5 px-6">Invoice #</th>
                <th className="py-3.5 px-6">Customer</th>
                <th className="py-3.5 px-6">Issue Date</th>
                <th className="py-3.5 px-6">Due Date</th>
                <th className="py-3.5 px-6 text-right">Total Amount</th>
                <th className="py-3.5 px-6 text-right">Balance Due</th>
                <th className="py-3.5 px-6 text-center">Status</th>
                <th className="py-3.5 px-6 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#c3c6d7]">
              {filteredInvoices.length > 0 ? (
                filteredInvoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-[#f8f9ff]/60 transition-colors">
                    <td className="py-4 px-6 font-semibold text-[#141b2b] whitespace-nowrap">
                      {inv.invoice_number}
                      {inv.gra_clearance_code && (
                        <span className="block text-[11px] text-[#059669] font-mono font-normal">
                          {inv.gra_clearance_code}
                        </span>
                      )}
                    </td>
                    <td className="py-4 px-6 font-medium text-[#141b2b] max-w-[220px] truncate">
                      {inv.customer_name}
                    </td>
                    <td className="py-4 px-6 text-[#434655] whitespace-nowrap">{inv.issue_date}</td>
                    <td className="py-4 px-6 text-[#434655] whitespace-nowrap">{inv.due_date}</td>
                    <td className="py-4 px-6 text-right font-bold text-[#141b2b] whitespace-nowrap">
                      GH¢ {inv.total_amount.toLocaleString("en-GH", { minimumFractionDigits: 2 })}
                    </td>
                    <td
                      className={`py-4 px-6 text-right font-bold whitespace-nowrap ${
                        inv.balance_due > 0 ? "text-[#dc2626]" : "text-[#059669]"
                      }`}
                    >
                      GH¢ {inv.balance_due.toLocaleString("en-GH", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-4 px-6 text-center whitespace-nowrap">
                      <span
                        className={`inline-block px-2.5 py-1 text-xs font-semibold rounded-full border ${getStatusBadge(
                          inv.status
                        )}`}
                      >
                        {inv.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-center whitespace-nowrap">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleCopyLink(inv.share_token, inv.id)}
                          className="px-2.5 py-1 text-xs font-semibold rounded bg-[#f1f3ff] hover:bg-[#e0e7ff] text-[#2563eb] transition-colors"
                        >
                          {copiedId === inv.id ? "Copied!" : "Share Link"}
                        </button>
                        <button
                          type="button"
                          className="px-2.5 py-1 text-xs font-semibold rounded bg-[#f8f9ff] hover:bg-[#f1f3ff] text-[#434655] border border-[#c3c6d7] transition-colors"
                        >
                          PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[#434655]">
                    <p className="font-semibold text-[#141b2b] text-base mb-1">No invoices found</p>
                    <p className="text-sm">Try adjusting your search query or status filter.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Standard Footer ────────────────────────────────────────── */}
      <footer className="border-t border-[#c3c6d7] mt-4 py-6 flex items-center justify-between text-[12px] font-medium text-[#434655] tracking-[0.24px]">
        <p>© 2026 Mage Books. All rights reserved.</p>
        <div className="flex items-center gap-6">
          <Link href="#" className="hover:underline">
            Privacy Policy
          </Link>
          <Link href="#" className="hover:underline">
            Terms of Service
          </Link>
          <Link href="#" className="hover:underline">
            Help Center
          </Link>
        </div>
      </footer>
    </div>
  );
}
