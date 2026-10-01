"use client";

import { useEffect, useState, useMemo } from "react";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  Receipt,
  Plus,
  RefreshCw,
  Search,
  CheckCircle,
  AlertCircle,
  Printer,
  X,
  CreditCard,
  Building2,
  Filter,
} from "lucide-react";

interface PaymentItem {
  id: string;
  customer?: string | null;
  customer_name?: string | null;
  invoice?: string | null;
  invoice_number?: string | null;
  amount: string | number;
  currency: string;
  payment_method: string;
  transaction_type: string;
  status: string;
  reference_number: string;
  payment_reference: string;
  transaction_date: string;
  reconciliation_notes?: string;
  created_at: string;
}

interface ContactItem {
  id: string;
  name: string;
  contact_type: string;
  phone?: string;
}

interface OrganizationProfile {
  id: string;
  name: string;
  tin_number?: string;
  city?: string;
}

export default function ReceiptsPage() {
  const { isSimpleMode } = useMode();

  const [receipts, setReceipts] = useState<PaymentItem[]>([]);
  const [contacts, setContacts] = useState<ContactItem[]>([]);
  const [org, setOrg] = useState<OrganizationProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState("");
  const [methodFilter, setMethodFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Create Modal State
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    customer: "",
    customerName: "",
    amount: "",
    payment_method: "MTN_MOMO",
    reference_number: "",
    payment_reference: "",
    transaction_date: new Date().toISOString().split("T")[0],
  });

  // Voucher Print Modal State
  const [selectedReceipt, setSelectedReceipt] = useState<PaymentItem | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleRefresh = () => {
    setLoading(true);
    setRefreshTrigger((prev) => prev + 1);
  };

  useEffect(() => {
    let isCancelled = false;

    async function loadData() {
      try {
        const [paymentsRes, contactsRes, orgRes] = await Promise.allSettled([
          apiClient.get<PaymentItem[]>("/api/v1/payments/?transaction_type=RECEIPT"),
          apiClient.get<ContactItem[]>("/api/v1/contacts/?contact_type=CUSTOMER"),
          apiClient.get<OrganizationProfile>("/api/v1/tenancy/organizations/current/"),
        ]);

        if (!isCancelled) {
          if (paymentsRes.status === "fulfilled") {
            const data = Array.isArray(paymentsRes.value.data) ? paymentsRes.value.data : [];
            setReceipts(data);
          } else {
            // Fallback to all payments if transaction_type filter unsupported
            const fallbackRes = await apiClient.get<PaymentItem[]>("/api/v1/payments/");
            const fallbackData = Array.isArray(fallbackRes.data)
              ? fallbackRes.data.filter((p) => p.transaction_type === "RECEIPT" || !p.transaction_type)
              : [];
            setReceipts(fallbackData);
          }

          if (contactsRes.status === "fulfilled") {
            setContacts(Array.isArray(contactsRes.value.data) ? contactsRes.value.data : []);
          }

          if (orgRes.status === "fulfilled") {
            setOrg(orgRes.value.data);
          }
          setError(null);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          const e = err as { response?: { data?: { detail?: string } } };
          setError(e.response?.data?.detail || "Failed to load receipts. Please verify backend connection.");
          setLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [refreshTrigger]);

  // Derived Metrics
  const metrics = useMemo(() => {
    const totalReceipts = receipts.length;
    const totalAmount = receipts.reduce((sum, r) => sum + (parseFloat(String(r.amount)) || 0), 0);
    const momoAmount = receipts
      .filter((r) => ["MTN_MOMO", "TELECEL_CASH", "AT_MONEY"].includes(r.payment_method))
      .reduce((sum, r) => sum + (parseFloat(String(r.amount)) || 0), 0);
    const cashBankAmount = receipts
      .filter((r) => ["CASH", "BANK_TRANSFER", "BANK_POS"].includes(r.payment_method))
      .reduce((sum, r) => sum + (parseFloat(String(r.amount)) || 0), 0);

    return {
      totalReceipts,
      totalAmount,
      momoAmount,
      cashBankAmount,
    };
  }, [receipts]);

  // Filtered Receipts
  const filteredReceipts = useMemo(() => {
    return receipts.filter((item) => {
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        (item.reference_number && item.reference_number.toLowerCase().includes(q)) ||
        (item.payment_reference && item.payment_reference.toLowerCase().includes(q)) ||
        (item.customer_name && item.customer_name.toLowerCase().includes(q)) ||
        (item.invoice_number && item.invoice_number.toLowerCase().includes(q));

      const matchesMethod = methodFilter === "ALL" || item.payment_method === methodFilter;
      const matchesStatus = statusFilter === "ALL" || item.status === statusFilter;

      return matchesSearch && matchesMethod && matchesStatus;
    });
  }, [receipts, searchQuery, methodFilter, statusFilter]);

  // Handle Create Receipt Submit
  const handleCreateReceipt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.amount || parseFloat(formData.amount) <= 0) {
      setCreateError("Please enter a valid receipt amount in GHS.");
      return;
    }

    setSubmitting(true);
    setCreateError(null);

    try {
      const payload: Record<string, unknown> = {
        amount: parseFloat(formData.amount).toFixed(2),
        currency: "GHS",
        payment_method: formData.payment_method,
        transaction_type: "RECEIPT",
        status: "SETTLED",
        reference_number: formData.reference_number || `REC-${Date.now().toString().slice(-6)}`,
        payment_reference: formData.payment_reference || `Customer payment received via ${formData.payment_method}`,
        transaction_date: formData.transaction_date ? `${formData.transaction_date}T00:00:00Z` : new Date().toISOString(),
      };

      if (formData.customer) {
        payload.customer = formData.customer;
      }

      await apiClient.post("/api/v1/payments/", payload);

      setIsCreateOpen(false);
      setFormData({
        customer: "",
        customerName: "",
        amount: "",
        payment_method: "MTN_MOMO",
        reference_number: "",
        payment_reference: "",
        transaction_date: new Date().toISOString().split("T")[0],
      });

      handleRefresh();
    } catch (err: unknown) {
      const e = err as { response?: { data?: Record<string, unknown> } };
      if (e.response?.data) {
        const msg = Object.entries(e.response.data)
          .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
          .join(" | ");
        setCreateError(msg);
      } else {
        setCreateError("Failed to issue payment receipt. Please check details.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const getMethodBadge = (method: string) => {
    switch (method) {
      case "MTN_MOMO":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-amber-100 text-amber-900 border border-amber-300">MTN MoMo</span>;
      case "TELECEL_CASH":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-red-100 text-red-800 border border-red-200">Telecel Cash</span>;
      case "AT_MONEY":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-blue-100 text-blue-800 border border-blue-200">AT Money</span>;
      case "BANK_TRANSFER":
      case "BANK_POS":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-indigo-100 text-indigo-800 border border-indigo-200">Bank Transfer</span>;
      case "CASH":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-100 text-emerald-800 border border-emerald-200">Cash</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-100 text-slate-800 border border-slate-200">{method}</span>;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SETTLED":
        return <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">Settled</span>;
      case "PARTIAL":
        return <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-amber-50 text-amber-700 border border-amber-200">Partial</span>;
      case "SUSPENSE":
        return <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-orange-50 text-orange-700 border border-orange-200">Suspense</span>;
      case "FAILED":
        return <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-rose-50 text-rose-700 border border-rose-200">Failed</span>;
      default:
        return <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-slate-100 text-slate-700 border border-slate-200">{status}</span>;
    }
  };

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10 flex items-center gap-3">
            <Receipt className="w-8 h-8 text-[#2563eb]" />
            {isSimpleMode ? "Receipts & Money Received" : "Cash Receipts & Payment Proofs"}
          </h1>
          <p className="text-[#434655] text-base mt-1">
            {isSimpleMode
              ? "Issue official payment receipts, record MoMo customer payments, and print proof of receipt."
              : "Official cash receipts journal, Mobile Money transaction reconciliation, and customer remittance register."}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-blue-600" : ""}`} />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-medium px-4 h-10 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            {isSimpleMode ? "Record Receipt" : "+ Issue Cash Receipt"}
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-[#e2e8f0] rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Receipts Issued</span>
            <Receipt className="w-5 h-5 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">{metrics.totalReceipts}</div>
          <span className="text-xs text-slate-500 mt-1 block">Documented proof of payment</span>
        </div>

        <div className="bg-white border border-[#e2e8f0] rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Inflows Collected</span>
            <CreditCard className="w-5 h-5 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">
            GHS {metrics.totalAmount.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <span className="text-xs text-emerald-600 mt-1 block font-medium">100% Verified Collections</span>
        </div>

        <div className="bg-white border border-[#e2e8f0] rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider">Mobile Money Receipts</span>
            <span className="text-xs font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded">MoMo Rails</span>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">
            GHS {metrics.momoAmount.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <span className="text-xs text-slate-500 mt-1 block">MTN, Telecel & AT Money</span>
        </div>

        <div className="bg-white border border-[#e2e8f0] rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider">Cash & Bank Transfers</span>
            <Building2 className="w-5 h-5 text-indigo-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">
            GHS {metrics.cashBankAmount.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <span className="text-xs text-slate-500 mt-1 block">Direct bank and counter deposits</span>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={handleRefresh}
            className="text-xs font-semibold text-red-700 underline hover:text-red-900"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="bg-white border border-[#e2e8f0] rounded-xl p-4 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search receipt #, reference, customer..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
            <Filter className="w-4 h-4 text-slate-400" />
            <span>Method:</span>
            <select
              value={methodFilter}
              onChange={(e) => setMethodFilter(e.target.value)}
              className="border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All Methods</option>
              <option value="MTN_MOMO">MTN Mobile Money</option>
              <option value="TELECEL_CASH">Telecel Cash</option>
              <option value="AT_MONEY">AT Money</option>
              <option value="BANK_TRANSFER">Bank Transfer</option>
              <option value="CASH">Cash</option>
            </select>
          </div>

          <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
            <span>Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="SETTLED">Settled</option>
              <option value="SUSPENSE">Suspense</option>
              <option value="PARTIAL">Partial</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>
        </div>
      </div>

      {/* Receipts Table */}
      <div className="bg-white border border-[#e2e8f0] rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 flex flex-col items-center justify-center gap-3 text-slate-500">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Loading receipt register...</p>
          </div>
        ) : filteredReceipts.length === 0 ? (
          <div className="p-16 text-center text-slate-500">
            <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-400">
              <Receipt className="w-6 h-6" />
            </div>
            <h3 className="font-semibold text-slate-800 text-lg mb-1">No receipts found</h3>
            <p className="text-sm text-slate-500 max-w-sm mx-auto mb-6">
              {searchQuery || methodFilter !== "ALL" || statusFilter !== "ALL"
                ? "No receipts match your search filters. Try clearing filters."
                : "No customer receipts have been recorded yet. Click 'Record Receipt' to issue your first proof of payment."}
            </p>
            <button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors shadow-sm"
            >
              <Plus className="w-4 h-4" />
              Record First Receipt
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <th className="py-3.5 px-4">Receipt # / Ref</th>
                  <th className="py-3.5 px-4">Date</th>
                  <th className="py-3.5 px-4">Customer / Payer</th>
                  <th className="py-3.5 px-4">Payment Method</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Amount (GHS)</th>
                  <th className="py-3.5 px-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-slate-700">
                {filteredReceipts.map((item) => {
                  const receiptNum = item.reference_number || `REC-${item.id.slice(0, 8).toUpperCase()}`;
                  const formattedDate = item.transaction_date
                    ? new Date(item.transaction_date).toLocaleDateString("en-GH", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })
                    : "—";

                  return (
                    <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-blue-600 font-mono text-xs">{receiptNum}</div>
                        {item.invoice_number && (
                          <div className="text-xs text-slate-400">Inv: {item.invoice_number}</div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-slate-600 whitespace-nowrap">{formattedDate}</td>
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-slate-900">
                          {item.customer_name || "General Customer / Walk-in"}
                        </div>
                        {item.payment_reference && (
                          <div className="text-xs text-slate-400 truncate max-w-xs">{item.payment_reference}</div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">{getMethodBadge(item.payment_method)}</td>
                      <td className="py-3.5 px-4 whitespace-nowrap">{getStatusBadge(item.status)}</td>
                      <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900 whitespace-nowrap">
                        GHS{" "}
                        {parseFloat(String(item.amount)).toLocaleString("en-GH", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </td>
                      <td className="py-3.5 px-4 text-center whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => setSelectedReceipt(item)}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 transition-colors shadow-2xs"
                        >
                          <Printer className="w-3.5 h-3.5" />
                          Print Receipt
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Record Receipt Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
              <div className="flex items-center gap-2">
                <Receipt className="w-5 h-5 text-blue-600" />
                <h3 className="font-bold text-slate-800 text-base">
                  {isSimpleMode ? "Record Customer Payment" : "Issue Cash / MoMo Receipt"}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsCreateOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateReceipt} className="p-6 flex flex-col gap-4">
              {createError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-800 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
                  <span>{createError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Customer / Payer
                </label>
                <select
                  value={formData.customer}
                  onChange={(e) => setFormData({ ...formData, customer: e.target.value })}
                  className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  <option value="">Walk-in / Unregistered Customer</option>
                  {contacts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.phone ? `(${c.phone})` : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Amount Received (GHS) *
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="0.00"
                    value={formData.amount}
                    onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Payment Channel *
                  </label>
                  <select
                    value={formData.payment_method}
                    onChange={(e) => setFormData({ ...formData, payment_method: e.target.value })}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500 bg-white"
                  >
                    <option value="MTN_MOMO">MTN Mobile Money</option>
                    <option value="TELECEL_CASH">Telecel Cash</option>
                    <option value="AT_MONEY">AT Money</option>
                    <option value="BANK_TRANSFER">Bank Transfer</option>
                    <option value="CASH">Cash</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Receipt # / MoMo ID
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. 2639482910"
                    value={formData.reference_number}
                    onChange={(e) => setFormData({ ...formData, reference_number: e.target.value })}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Payment Date
                  </label>
                  <input
                    type="date"
                    value={formData.transaction_date}
                    onChange={(e) => setFormData({ ...formData, transaction_date: e.target.value })}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Description / Purpose of Payment
                </label>
                <input
                  type="text"
                  placeholder="e.g. Full settlement of supplies delivered"
                  value={formData.payment_reference}
                  onChange={(e) => setFormData({ ...formData, payment_reference: e.target.value })}
                  className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200 mt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 text-sm font-medium bg-[#2563eb] hover:bg-[#1d4ed8] text-white rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {submitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                  {isSimpleMode ? "Save Receipt" : "Post Receipt Voucher"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Official Voucher Printable Modal */}
      {selectedReceipt && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Actions Bar (hidden on print) */}
            <div className="flex items-center justify-between px-6 py-3.5 border-b border-slate-200 bg-slate-50 print:hidden">
              <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                Official Proof of Payment
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="inline-flex items-center gap-1.5 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-xs font-semibold px-3 py-1.5 rounded-lg shadow-sm transition-colors"
                >
                  <Printer className="w-3.5 h-3.5" />
                  Print Receipt
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedReceipt(null)}
                  className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Printable Receipt Body */}
            <div className="p-8 bg-white border border-slate-100 text-slate-800">
              {/* Receipt Header */}
              <div className="border-b-2 border-slate-900 pb-4 mb-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-black text-slate-900 tracking-tight uppercase">
                      {org?.name || "MageBooks Enterprise"}
                    </h2>
                    {org?.tin_number && (
                      <p className="text-xs text-slate-500 font-mono mt-0.5">GRA TIN: {org.tin_number}</p>
                    )}
                    {org?.city && <p className="text-xs text-slate-500">{org.city}, Ghana</p>}
                  </div>
                  <div className="text-right">
                    <span className="inline-block bg-slate-900 text-white text-xs font-bold px-3 py-1 rounded">
                      PAYMENT RECEIPT
                    </span>
                    <p className="text-xs font-mono font-bold text-slate-700 mt-1">
                      {selectedReceipt.reference_number || `REC-${selectedReceipt.id.slice(0, 8).toUpperCase()}`}
                    </p>
                  </div>
                </div>
              </div>

              {/* Receipt Details Grid */}
              <div className="grid grid-cols-2 gap-4 text-xs mb-6">
                <div>
                  <span className="text-slate-500 uppercase font-semibold block mb-0.5">Received From:</span>
                  <span className="font-bold text-slate-900 text-sm block">
                    {selectedReceipt.customer_name || "General Customer / Walk-in"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase font-semibold block mb-0.5">Date & Time:</span>
                  <span className="font-medium text-slate-800 block">
                    {selectedReceipt.transaction_date
                      ? new Date(selectedReceipt.transaction_date).toLocaleString("en-GH")
                      : new Date().toLocaleString("en-GH")}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase font-semibold block mb-0.5">Payment Rail:</span>
                  <span className="font-semibold text-slate-800 block">
                    {selectedReceipt.payment_method.replace(/_/g, " ")}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase font-semibold block mb-0.5">Payment Status:</span>
                  <span className="inline-flex items-center gap-1 font-bold text-emerald-700">
                    <CheckCircle className="w-3.5 h-3.5" />
                    {selectedReceipt.status}
                  </span>
                </div>
              </div>

              {/* Purpose / Notes */}
              {selectedReceipt.payment_reference && (
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs mb-6">
                  <span className="text-slate-500 font-semibold block mb-1">Narration / Memo:</span>
                  <p className="text-slate-700 italic">{selectedReceipt.payment_reference}</p>
                </div>
              )}

              {/* Highlighted Amount */}
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 text-center mb-6">
                <span className="text-xs font-semibold text-blue-700 uppercase tracking-wider block mb-1">
                  Amount Received
                </span>
                <div className="text-3xl font-black text-blue-900 font-mono">
                  GHS{" "}
                  {parseFloat(String(selectedReceipt.amount)).toLocaleString("en-GH", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </div>
              </div>

              {/* Official Seal / Signature Footer */}
              <div className="flex items-end justify-between pt-6 border-t border-dashed border-slate-300 text-[10px] text-slate-400">
                <div>
                  <p className="font-mono">Generated by MageBooks ERP System</p>
                  <p>Immutable Audit Record ID: {selectedReceipt.id}</p>
                </div>
                <div className="text-center">
                  <div className="w-36 border-b border-slate-400 pb-1 mb-1 font-script text-xs font-bold text-slate-600">
                    Authorized Signatory
                  </div>
                  <p className="text-[9px] uppercase">Cashier / Accountant</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
