"use client";

import { useEffect, useState, useCallback } from "react";
import { useMode } from "@/contexts/ModeContext";
import apiClient from "@/lib/apiClient";

interface InvoiceLineItem {
  description: string;
  quantity: number;
  unit_price: number;
}

interface InvoiceItem {
  id: string;
  invoice_number: string;
  customer_name: string;
  issue_date: string;
  due_date: string;
  subtotal_amount: number | string;
  total_tax?: number | string;
  vat_amount?: number | string;
  nhil_amount?: number | string;
  getfund_amount?: number | string;
  total_amount: number | string;
  paid_amount: number | string;
  balance_due: number | string;
  status: "DRAFT" | "PENDING_GRA" | "CLEARED" | "PAID" | "OVERDUE" | "PARTIALLY_PAID" | "CANCELLED";
  gra_clearance_code: string | null;
  share_token: string;
}

interface ContactOption {
  id: string;
  name: string;
  tin?: string;
}

// ── Create Invoice Modal ───────────────────────────────────────────────────────
function CreateInvoiceModal({
  isOpen,
  onClose,
  onCreated,
}: {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [contacts, setContacts] = useState<ContactOption[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [issueDate, setIssueDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [dueDate, setDueDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().split("T")[0];
  });
  const [lines, setLines] = useState<InvoiceLineItem[]>([
    { description: "", quantity: 1, unit_price: 0 },
  ]);
  const [action, setAction] = useState<"issue" | "save_draft">("issue");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    apiClient
      .get<ContactOption[] | { results: ContactOption[] }>("/api/v1/contacts/?contact_type=CUSTOMER")
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : res.data.results || [];
        setContacts(list);
        if (list.length > 0) setCustomerId(list[0].id);
      })
      .catch((err) => console.error("Failed to load customers:", err));
  }, [isOpen]);

  if (!isOpen) return null;

  const handleLineChange = (index: number, field: keyof InvoiceLineItem, value: string | number) => {
    const updated = [...lines];
    if (field === "quantity" || field === "unit_price") {
      updated[index] = { ...updated[index], [field]: parseFloat(String(value)) || 0 };
    } else {
      updated[index] = { ...updated[index], [field]: value };
    }
    setLines(updated);
  };

  const addLine = () => {
    setLines([...lines, { description: "", quantity: 1, unit_price: 0 }]);
  };

  const removeLine = (index: number) => {
    if (lines.length <= 1) return;
    setLines(lines.filter((_, i) => i !== index));
  };

  const subtotal = lines.reduce((acc, l) => acc + l.quantity * l.unit_price, 0);
  const estimatedTax = subtotal * 0.2; // 15% VAT + 2.5% NHIL + 2.5% GETFund
  const grandTotal = subtotal + estimatedTax;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!customerId) {
      setErrorMsg("Please select a customer.");
      return;
    }

    const invalidLine = lines.find((l) => !l.description.trim() || l.quantity <= 0);
    if (invalidLine) {
      setErrorMsg("All items must have a description and quantity greater than 0.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        customer_id: customerId,
        issue_date: issueDate,
        due_date: dueDate,
        currency: "GHS",
        action,
        lines: lines.map((l) => ({
          description: l.description.trim(),
          quantity: l.quantity,
          unit_price: l.unit_price,
          supply_type: "STANDARD",
        })),
      };

      await apiClient.post("/api/v1/invoices/", payload);
      onCreated();
      onClose();
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { detail?: string;[key: string]: unknown } };
      };
      const detail =
        axiosErr.response?.data?.detail ||
        (typeof axiosErr.response?.data === "object"
          ? JSON.stringify(axiosErr.response?.data)
          : "Failed to create invoice. Please check the values entered.");
      setErrorMsg(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-xl shadow-xl border border-[#c3c6d7] max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-[#c3c6d7]">
          <h2 className="text-xl font-bold text-[#141b2b]">Create New Tax Invoice</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[#64748b] hover:text-[#141b2b] text-xl font-bold leading-none p-1"
          >
            &times;
          </button>
        </div>

        {errorMsg && (
          <div className="mt-4 p-3 bg-[#fef2f2] border border-[#fecaca] rounded-lg text-sm text-[#dc2626]">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#434655] uppercase tracking-wide mb-1">
                Customer *
              </label>
              <select
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                required
                className="w-full h-10 px-3 text-sm bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg focus:outline-none focus:border-[#2563eb]"
              >
                {contacts.length === 0 ? (
                  <option value="">No customers found (create one first)</option>
                ) : (
                  contacts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.tin ? `(${c.tin})` : ""}
                    </option>
                  ))
                )}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#434655] uppercase tracking-wide mb-1">
                Action *
              </label>
              <select
                value={action}
                onChange={(e) => setAction(e.target.value as "issue" | "save_draft")}
                className="w-full h-10 px-3 text-sm bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg focus:outline-none focus:border-[#2563eb]"
              >
                <option value="issue">Issue Immediately (Post to Ledger & GRA)</option>
                <option value="save_draft">Save as Draft</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#434655] uppercase tracking-wide mb-1">
                Issue Date *
              </label>
              <input
                type="date"
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                required
                className="w-full h-10 px-3 text-sm bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg focus:outline-none focus:border-[#2563eb]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#434655] uppercase tracking-wide mb-1">
                Due Date *
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                required
                className="w-full h-10 px-3 text-sm bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg focus:outline-none focus:border-[#2563eb]"
              />
            </div>
          </div>

          {/* Line items */}
          <div className="mt-2">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-[#434655] uppercase tracking-wide">
                Invoice Items
              </label>
              <button
                type="button"
                onClick={addLine}
                className="text-xs text-[#2563eb] font-bold hover:underline"
              >
                + Add Item
              </button>
            </div>

            <div className="flex flex-col gap-2">
              {lines.map((l, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="Description (e.g. Consulting, Hardware)"
                    value={l.description}
                    onChange={(e) => handleLineChange(i, "description", e.target.value)}
                    required
                    className="flex-3 h-9 px-3 text-xs bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg focus:outline-none focus:border-[#2563eb]"
                  />
                  <input
                    type="number"
                    min="1"
                    step="1"
                    placeholder="Qty"
                    value={l.quantity}
                    onChange={(e) => handleLineChange(i, "quantity", e.target.value)}
                    required
                    className="w-16 h-9 px-2 text-center text-xs bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg focus:outline-none focus:border-[#2563eb]"
                  />
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="Price (GH¢)"
                    value={l.unit_price}
                    onChange={(e) => handleLineChange(i, "unit_price", e.target.value)}
                    required
                    className="w-24 h-9 px-2 text-right text-xs bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg focus:outline-none focus:border-[#2563eb]"
                  />
                  <span className="text-xs font-bold text-[#141b2b] w-24 text-right">
                    GH¢ {(l.quantity * l.unit_price).toFixed(2)}
                  </span>
                  {lines.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeLine(i)}
                      className="text-[#dc2626] font-bold px-2 hover:bg-[#fee2e2] rounded"
                    >
                      &times;
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Totals Preview */}
          <div className="mt-4 p-4 bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg flex flex-col gap-1 text-xs">
            <div className="flex justify-between text-[#434655]">
              <span>Subtotal:</span>
              <span className="font-semibold text-[#141b2b]">GH¢ {subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-[#64748b]">
              <span>Act 1151 Levies (15% VAT + 2.5% NHIL + 2.5% GETFund):</span>
              <span>GH¢ {estimatedTax.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm font-bold text-[#141b2b] border-t border-[#c3c6d7] pt-1 mt-1">
              <span>Estimated Grand Total:</span>
              <span className="text-[#004ac6]">GH¢ {grandTotal.toFixed(2)}</span>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 mt-4 pt-4 border-t border-[#c3c6d7]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-[#434655] hover:bg-[#f1f3ff] rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 text-sm font-bold text-white bg-[#2563eb] hover:bg-[#1d4ed8] disabled:opacity-50 rounded-lg shadow transition-colors"
            >
              {submitting ? "Processing..." : action === "issue" ? "Issue Invoice" : "Save Draft"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Invoices Page ────────────────────────────────────────────────────────
export default function InvoicesPage() {
  const { mode } = useMode();
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchInvoices = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.append("search", search.trim());
      if (statusFilter !== "ALL") params.append("status", statusFilter);

      const query = params.toString() ? `?${params.toString()}` : "";
      const res = await apiClient.get<InvoiceItem[] | { results: InvoiceItem[] }>(
        `/api/v1/invoices/${query}`
      );
      const list = Array.isArray(res.data) ? res.data : res.data.results || [];
      setInvoices(list);
      setError(null);
    } catch (err: unknown) {
      console.error("[InvoicesPage] Error fetching invoices:", err);
      setError("Unable to load invoices. Please ensure the backend is running and try again.");
    } finally {
      setIsLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    let isCancelled = false;
    const params = new URLSearchParams();
    if (search.trim()) params.append("search", search.trim());
    if (statusFilter !== "ALL") params.append("status", statusFilter);

    const query = params.toString() ? `?${params.toString()}` : "";
    apiClient
      .get<InvoiceItem[] | { results: InvoiceItem[] }>(`/api/v1/invoices/${query}`)
      .then((res) => {
        if (!isCancelled) {
          const list = Array.isArray(res.data) ? res.data : res.data.results || [];
          setInvoices(list);
          setError(null);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          console.error("[InvoicesPage] Error fetching invoices:", err);
          setError("Unable to load invoices. Please ensure the backend is running and try again.");
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [search, statusFilter]);


  const handleCopyLink = (shareToken: string, id: string) => {
    if (!shareToken) return;
    const url = `${window.location.origin}/invoices/public/${shareToken}`;
    navigator.clipboard.writeText(url);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

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
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("[InvoicesPage] PDF download error:", err);
      alert("Unable to generate PDF. Please ensure the invoice is issued and cleared.");
    }
  };

  const handleIssueInvoice = async (id: string) => {
    if (!confirm("Issue this draft invoice? This will post entries to the general ledger.")) return;
    try {
      await apiClient.post(`/api/v1/invoices/${id}/issue/`);
      fetchInvoices();
    } catch (err) {
      console.error("[InvoicesPage] Issue error:", err);
      alert("Failed to issue invoice.");
    }
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

  const totalInvoiced = invoices.reduce((acc, inv) => acc + (parseFloat(String(inv.total_amount)) || 0), 0);
  const outstanding = invoices.reduce((acc, inv) => acc + (parseFloat(String(inv.balance_due)) || 0), 0);
  const overdue = invoices
    .filter((inv) => inv.status === "OVERDUE")
    .reduce((acc, inv) => acc + (parseFloat(String(inv.balance_due)) || 0), 0);
  const clearedCount = invoices.filter((inv) => inv.gra_clearance_code !== null).length;

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
            onClick={() => setIsModalOpen(true)}
            className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors flex items-center gap-2"
          >
            + Create Invoice
          </button>
        </div>
      </div>

      {/* ── Error Banner ───────────────────────────────────────────── */}
      {error && (
        <div className="p-4 bg-[#fef2f2] border border-[#fecaca] rounded-xl flex items-center justify-between text-sm text-[#dc2626]">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => fetchInvoices()}
            className="font-bold underline ml-4 hover:text-[#b91c1c]"
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Summary KPI Cards ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 flex flex-col gap-2 shadow-xs">
          <p className="text-[#434655] text-xs font-semibold uppercase tracking-[0.35px]">
            Total Invoiced
          </p>
          <p className="text-[22px] font-black text-[#141b2b]">
            GH¢ {totalInvoiced.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-[#059669] font-medium">{invoices.length} active records</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 flex flex-col gap-2 shadow-xs">
          <p className="text-[#434655] text-xs font-semibold uppercase tracking-[0.35px]">
            Outstanding
          </p>
          <p className="text-[22px] font-black text-[#2563eb]">
            GH¢ {outstanding.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-[#434655] font-medium">Awaiting customer payment</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 flex flex-col gap-2 shadow-xs">
          <p className="text-[#434655] text-xs font-semibold uppercase tracking-[0.35px]">
            Overdue Receivables
          </p>
          <p className="text-[22px] font-black text-[#dc2626]">
            GH¢ {overdue.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-[#dc2626] font-medium">Requires follow-up</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 flex flex-col gap-2 shadow-xs">
          <p className="text-[#434655] text-xs font-semibold uppercase tracking-[0.35px]">
            GRA E-VAT Cleared
          </p>
          <p className="text-[22px] font-black text-[#141b2b]">
            {clearedCount} / {invoices.length}
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
                <th className="py-4 px-6">Invoice #</th>
                <th className="py-4 px-6">Customer</th>
                <th className="py-4 px-6">Dates</th>
                <th className="py-4 px-6 text-right">Total (GH¢)</th>
                <th className="py-4 px-6 text-right">Balance (GH¢)</th>
                <th className="py-4 px-6 text-center">Status</th>
                <th className="py-4 px-6 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#c3c6d7]">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-[#434655]">
                    <p className="text-sm font-medium animate-pulse">Loading live invoices...</p>
                  </td>
                </tr>
              ) : invoices.length > 0 ? (
                invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-[#f8f9ff] transition-colors">
                    <td className="py-4 px-6 font-semibold text-[#141b2b] whitespace-nowrap">
                      <div>{inv.invoice_number}</div>
                      {inv.gra_clearance_code && (
                        <div className="text-[10px] text-[#059669] font-mono mt-0.5">
                          ✓ {inv.gra_clearance_code}
                        </div>
                      )}
                    </td>
                    <td className="py-4 px-6 font-medium text-[#141b2b]">
                      {inv.customer_name || "Valued Customer"}
                    </td>
                    <td className="py-4 px-6 text-xs text-[#434655] whitespace-nowrap">
                      <div>Issue: {inv.issue_date}</div>
                      <div className="text-[#64748b]">Due: {inv.due_date}</div>
                    </td>
                    <td className="py-4 px-6 text-right font-bold text-[#141b2b] whitespace-nowrap">
                      GH¢ {parseFloat(String(inv.total_amount)).toLocaleString("en-GH", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-4 px-6 text-right font-black whitespace-nowrap text-[#004ac6]">
                      GH¢ {parseFloat(String(inv.balance_due)).toLocaleString("en-GH", { minimumFractionDigits: 2 })}
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
                        {inv.status === "DRAFT" && (
                          <button
                            type="button"
                            onClick={() => handleIssueInvoice(inv.id)}
                            className="px-2.5 py-1 text-xs font-semibold rounded bg-[#059669] hover:bg-[#047857] text-white transition-colors"
                          >
                            Issue
                          </button>
                        )}
                        {inv.share_token && (
                          <button
                            type="button"
                            onClick={() => handleCopyLink(inv.share_token, inv.id)}
                            className="px-2.5 py-1 text-xs font-semibold rounded bg-[#f1f3ff] hover:bg-[#e0e7ff] text-[#2563eb] transition-colors"
                          >
                            {copiedId === inv.id ? "Copied!" : "Share Link"}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleDownloadPdf(inv.id, inv.invoice_number)}
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
                  <td colSpan={7} className="py-12 text-center text-[#434655]">
                    <p className="font-semibold text-[#141b2b] text-base mb-1">No invoices found</p>
                    <p className="text-sm mb-4">Click below to create your first tax invoice.</p>
                    <button
                      type="button"
                      onClick={() => setIsModalOpen(true)}
                      className="px-4 py-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-xs font-bold rounded-lg transition-colors inline-block"
                    >
                      + Create Invoice
                    </button>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Create Modal ───────────────────────────────────────────── */}
      <CreateInvoiceModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onCreated={() => fetchInvoices()}
      />
    </div>
  );
}
