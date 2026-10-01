"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMode } from "@/contexts/ModeContext";
import apiClient from "@/lib/apiClient";

interface InvoiceItem {
  id: string;
  invoice_number: string;
  customer_name?: string;
  total_amount: string | number;
  amount_paid: string | number;
  balance_due: string | number;
  status: string;
  issue_date: string;
  due_date: string;
  currency: string;
}

export default function AccountsReceivablePage() {
  const { mode } = useMode();
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const title = mode === "simple" ? "Money Owed to Me" : "Accounts Receivable";
  const subtitle =
    mode === "simple"
      ? "Track customers who still owe you money."
      : "Outstanding customer invoices and receivable balances.";

  const fetchReceivables = async (showLoading = false) => {
    if (showLoading) setIsLoading(true);
    try {
      const res = await apiClient.get<InvoiceItem[] | { results: InvoiceItem[] }>(
        "/api/v1/invoicing/invoices/"
      );
      const list = Array.isArray(res.data) ? res.data : res.data.results || [];
      // Filter to outstanding / unpaid invoices
      const outstanding = list.filter((inv) => inv.status !== "CANCELLED" && inv.status !== "PAID");
      setInvoices(outstanding);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load receivables.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let isCancelled = false;
    apiClient
      .get<InvoiceItem[] | { results: InvoiceItem[] }>("/api/v1/invoicing/invoices/")
      .then((res) => {
        if (!isCancelled) {
          const list = Array.isArray(res.data) ? res.data : res.data.results || [];
          const outstanding = list.filter((inv) => inv.status !== "CANCELLED" && inv.status !== "PAID");
          setInvoices(outstanding);
          setError(null);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : "Failed to load receivables.";
          setError(msg);
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  // Compute summary totals
  const totalReceivable = invoices.reduce((acc, inv) => {
    const bal = typeof inv.balance_due === "number" ? inv.balance_due : parseFloat(String(inv.balance_due || inv.total_amount || 0));
    return acc + (isNaN(bal) ? 0 : bal);
  }, 0);

  const now = new Date();
  const overdueTotal = invoices.reduce((acc, inv) => {
    const dueDate = new Date(inv.due_date);
    if (dueDate < now) {
      const bal = typeof inv.balance_due === "number" ? inv.balance_due : parseFloat(String(inv.balance_due || inv.total_amount || 0));
      return acc + (isNaN(bal) ? 0 : bal);
    }
    return acc;
  }, 0);

  const dueThisMonthTotal = invoices.reduce((acc, inv) => {
    const dueDate = new Date(inv.due_date);
    if (dueDate.getMonth() === now.getMonth() && dueDate.getFullYear() === now.getFullYear()) {
      const bal = typeof inv.balance_due === "number" ? inv.balance_due : parseFloat(String(inv.balance_due || inv.total_amount || 0));
      return acc + (isNaN(bal) ? 0 : bal);
    }
    return acc;
  }, 0);

  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
            {title}
          </h1>
          <p className="text-[#434655] text-base mt-1">{subtitle}</p>
        </div>
        <Link
          href="/dashboard/invoices"
          className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm flex items-center justify-center transition-colors"
        >
          + New Invoice
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          {
            label: mode === "simple" ? "Total Owed to Me" : "Total Receivable",
            value: `GHS ${totalReceivable.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
            color: "text-[#16a34a]",
          },
          {
            label: "Overdue",
            value: `GHS ${overdueTotal.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
            color: "text-[#dc2626]",
          },
          {
            label: "Due This Month",
            value: `GHS ${dueThisMonthTotal.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
            color: "text-[#141b2b]",
          },
        ].map((card) => (
          <div key={card.label} className="bg-white border border-[#c3c6d7] rounded-xl p-6">
            <p className="text-sm font-semibold text-[#434655] uppercase tracking-[0.35px]">
              {card.label}
            </p>
            <p className={`font-black text-[22px] mt-2 ${card.color}`}>{card.value}</p>
          </div>
        ))}
      </div>

      {isLoading ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-12 text-center text-[#434655]">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-[#2563eb] border-r-transparent mb-3" />
          <p className="text-sm font-medium">Loading receivable invoices...</p>
        </div>
      ) : error ? (
        <div className="bg-[#fef2f2] border border-[#f87171] rounded-xl p-6 text-center text-[#991b1b]">
          <p className="font-semibold text-base mb-1">Failed to load receivables</p>
          <p className="text-sm mb-4">{error}</p>
          <button
            type="button"
            onClick={() => {
              fetchReceivables(true);
            }}
            className="bg-[#dc2626] hover:bg-[#b91c1c] text-white text-xs font-semibold px-4 py-2 rounded-md"
          >
            Retry
          </button>
        </div>
      ) : invoices.length === 0 ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-12 text-center text-[#434655]">
          <p className="font-semibold text-[#141b2b] text-lg mb-1">No outstanding invoices</p>
          <p className="text-sm">Invoices issued to customers will appear here until paid.</p>
        </div>
      ) : (
        <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[#f8f9fa] border-b border-[#e2e8f0] text-xs font-semibold uppercase tracking-wider text-[#475569]">
                <tr>
                  <th className="py-3.5 px-6">Invoice #</th>
                  <th className="py-3.5 px-6">Customer</th>
                  <th className="py-3.5 px-6">Due Date</th>
                  <th className="py-3.5 px-6 text-right">Total Amount</th>
                  <th className="py-3.5 px-6 text-right">Balance Due</th>
                  <th className="py-3.5 px-6">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-[#1e293b]">
                {invoices.map((inv) => {
                  const isOverdue = new Date(inv.due_date) < now;
                  const totalNum = typeof inv.total_amount === "number" ? inv.total_amount : parseFloat(String(inv.total_amount || 0));
                  const balNum = typeof inv.balance_due === "number" ? inv.balance_due : parseFloat(String(inv.balance_due || inv.total_amount || 0));
                  return (
                    <tr key={inv.id} className="hover:bg-[#f8fafc] transition-colors">
                      <td className="py-4 px-6 font-semibold text-[#2563eb]">
                        {inv.invoice_number || inv.id.slice(0, 8)}
                      </td>
                      <td className="py-4 px-6 font-medium text-[#0f172a]">
                        {inv.customer_name || "Customer"}
                      </td>
                      <td className="py-4 px-6 text-xs text-[#64748b]">
                        <span className={isOverdue ? "text-red-600 font-semibold" : ""}>
                          {inv.due_date} {isOverdue && "(Overdue)"}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-right font-medium text-[#0f172a]">
                        GHS {totalNum.toFixed(2)}
                      </td>
                      <td className="py-4 px-6 text-right font-bold text-[#dc2626]">
                        GHS {balNum.toFixed(2)}
                      </td>
                      <td className="py-4 px-6">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                            inv.status === "CLEARED"
                              ? "bg-[#dcfce7] text-[#166534]"
                              : inv.status === "PENDING_GRA"
                              ? "bg-[#fef9c3] text-[#854d0e]"
                              : "bg-[#e2e8f0] text-[#475569]"
                          }`}
                        >
                          {inv.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <footer className="border-t border-[#c3c6d7] mt-4 py-6 flex items-center justify-between text-[12px] font-medium text-[#434655] tracking-[0.24px]">
        <p>© 2026 Mage Books. All rights reserved.</p>
        <div className="flex items-center gap-6">
          <Link href="/legal/privacy" className="hover:underline">Privacy Policy</Link>
          <Link href="/legal/terms" className="hover:underline">Terms of Service</Link>
          <Link href="/legal/support" className="hover:underline">Help Center</Link>
        </div>
      </footer>
    </div>
  );
}
