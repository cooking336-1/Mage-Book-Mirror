"use client";

import { useEffect, useState, useMemo } from "react";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  CreditCard,
  Plus,
  RefreshCw,
  Search,
  AlertCircle,
  CheckCircle,
  X,
  ArrowDownLeft,
  ArrowUpRight,
  Check,
} from "lucide-react";

interface PaymentItem {
  id: string;
  customer?: string;
  customer_name?: string;
  invoice?: string;
  invoice_number?: string;
  amount: string | number;
  currency: string;
  payment_method: string;
  transaction_type: "RECEIPT" | "PAYMENT";
  status: "SETTLED" | "PARTIAL" | "SUSPENSE" | "FAILED";
  reference_number: string;
  payment_reference: string;
  transaction_date: string;
  reconciliation_notes: string;
  created_at: string;
}

interface ContactItem {
  id: string;
  name: string;
  contact_type: string;
}

interface InvoiceOption {
  id: string;
  invoice_number: string;
  total_amount: string | number;
  balance_due: string | number;
}

function formatGHS(amount: string | number): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-GH", {
    style: "currency",
    currency: "GHS",
    minimumFractionDigits: 2,
  })
    .format(isNaN(num) ? 0 : num)
    .replace("GHS", "GH¢");
}

export default function PaymentsPage() {
  const { mode } = useMode();

  const [payments, setPayments] = useState<PaymentItem[]>([]);
  const [contacts, setContacts] = useState<ContactItem[]>([]);
  const [invoices, setInvoices] = useState<InvoiceOption[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState<"ALL" | "RECEIPT" | "PAYMENT">("ALL");
  const [refreshKey, setRefreshKey] = useState(0);

  // Record Payment Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [transactionType, setTransactionType] = useState<"RECEIPT" | "PAYMENT">("RECEIPT");
  const [selectedContactId, setSelectedContactId] = useState("");
  const [selectedInvoiceId, setSelectedInvoiceId] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("MTN_MOMO");
  const [amount, setAmount] = useState("");
  const [referenceNumber, setReferenceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadData() {
      try {
        const [payRes, contRes, invRes] = await Promise.allSettled([
          apiClient.get<PaymentItem[]>("/api/v1/payments/"),
          apiClient.get<ContactItem[] | { results: ContactItem[] }>("/api/v1/invoicing/contacts/"),
          apiClient.get<InvoiceOption[] | { results: InvoiceOption[] }>("/api/v1/invoices/"),
        ]);

        if (isCancelled) return;

        if (payRes.status === "fulfilled" && payRes.value.data) {
          setPayments(payRes.value.data);
        }

        if (contRes.status === "fulfilled" && contRes.value.data) {
          const raw = contRes.value.data;
          setContacts(Array.isArray(raw) ? raw : raw.results || []);
        }

        if (invRes.status === "fulfilled" && invRes.value.data) {
          const raw = invRes.value.data;
          setInvoices(Array.isArray(raw) ? raw : raw.results || []);
        }

        setError(null);
        setIsLoading(false);
      } catch (err: unknown) {
        if (!isCancelled) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
          setError(resp?.detail || "Failed to load payment transactions.");
          setIsLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [refreshKey]);

  // Aggregate Metrics
  const { totalReceipts, totalDisbursements, settledCount } = useMemo(() => {
    let receipts = 0;
    let disbursements = 0;
    let settled = 0;

    payments.forEach((p) => {
      const amt = parseFloat(String(p.amount || 0));
      if (p.transaction_type === "RECEIPT") receipts += amt;
      if (p.transaction_type === "PAYMENT") disbursements += amt;
      if (p.status === "SETTLED") settled += 1;
    });

    return { totalReceipts: receipts, totalDisbursements: disbursements, settledCount: settled };
  }, [payments]);

  // Handle Record Payment
  const handleRecordPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsedAmount = parseFloat(amount);
    if (!parsedAmount || parsedAmount <= 0) {
      setError("Please enter a valid payment amount.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await apiClient.post("/api/v1/payments/", {
        amount: parsedAmount,
        currency: "GHS",
        transaction_type: transactionType,
        payment_method: paymentMethod,
        customer: selectedContactId || undefined,
        invoice: selectedInvoiceId || undefined,
        reference_number: referenceNumber.trim() || undefined,
        reconciliation_notes: notes.trim() || undefined,
        status: "SETTLED",
      });

      setSuccessMsg(
        transactionType === "RECEIPT"
          ? "Customer receipt recorded successfully."
          : "Outgoing disbursement recorded successfully."
      );
      setIsModalOpen(false);
      setAmount("");
      setReferenceNumber("");
      setNotes("");
      setSelectedContactId("");
      setSelectedInvoiceId("");
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to record payment transaction.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredPayments = useMemo(() => {
    return payments.filter((p) => {
      const q = searchTerm.toLowerCase();
      const refMatch =
        (p.reference_number && p.reference_number.toLowerCase().includes(q)) ||
        (p.payment_reference && p.payment_reference.toLowerCase().includes(q));
      const partyMatch = p.customer_name && p.customer_name.toLowerCase().includes(q);
      const invMatch = p.invoice_number && p.invoice_number.toLowerCase().includes(q);
      const searchMatch = !searchTerm || refMatch || partyMatch || invMatch;

      const typeMatch = typeFilter === "ALL" || p.transaction_type === typeFilter;
      return searchMatch && typeMatch;
    });
  }, [payments, searchTerm, typeFilter]);

  const getMethodBadge = (method: string) => {
    switch (method) {
      case "MTN_MOMO":
        return "bg-amber-100 text-amber-900 border-amber-200";
      case "TELECEL_CASH":
        return "bg-red-100 text-red-900 border-red-200";
      case "AT_MONEY":
        return "bg-blue-100 text-blue-900 border-blue-200";
      case "BANK_TRANSFER":
        return "bg-emerald-100 text-emerald-900 border-emerald-200";
      case "CASH":
        return "bg-slate-100 text-slate-800 border-slate-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              {mode === "simple" ? "Payments & Receipts" : "Cash & MoMo Settlements"}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
              <Check className="w-3.5 h-3.5" />
              Ghana Rails Active
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            {mode === "simple"
              ? "Track customer mobile money receipts and outgoing payments sent to vendors."
              : "Inbound clearing, outgoing disbursements, and bank/MoMo settlement reconciliation."}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setIsLoading(true);
              setRefreshKey((k) => k + 1);
            }}
            disabled={isLoading}
            className="p-2.5 text-slate-600 bg-white border border-[#c3c6d7] rounded-lg hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50"
            title="Refresh payments"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            + Record Payment
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center justify-between text-sm shadow-sm">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 p-4 rounded-xl flex items-center justify-between text-sm shadow-sm">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-5 h-5 flex-shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <ArrowDownLeft className="w-4 h-4 text-emerald-600" />
            Total Inflow (Receipts)
          </div>
          <p className="text-2xl font-bold text-emerald-700 mt-2 font-mono">
            {formatGHS(totalReceipts)}
          </p>
          <p className="text-xs text-slate-500 mt-1">Customer &amp; invoice settlements</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <ArrowUpRight className="w-4 h-4 text-red-600" />
            Total Outflow (Payouts)
          </div>
          <p className="text-2xl font-bold text-red-600 mt-2 font-mono">
            {formatGHS(totalDisbursements)}
          </p>
          <p className="text-xs text-slate-500 mt-1">Supplier bills &amp; staff disbursements</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <CreditCard className="w-4 h-4 text-blue-600" />
            Settled Transactions
          </div>
          <p className="text-2xl font-bold text-[#141b2b] mt-2">{settledCount}</p>
          <p className="text-xs text-slate-500 mt-1">Successfully cleared payments</p>
        </div>
      </div>

      {/* Filter and Search */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search reference or customer..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-white border border-[#c3c6d7] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-slate-800 shadow-sm"
            />
          </div>

          <div className="flex items-center bg-white border border-[#c3c6d7] rounded-lg p-1 shadow-sm shrink-0">
            <button
              onClick={() => setTypeFilter("ALL")}
              className={`px-3 py-1 text-xs font-semibold rounded ${
                typeFilter === "ALL" ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setTypeFilter("RECEIPT")}
              className={`px-3 py-1 text-xs font-semibold rounded ${
                typeFilter === "RECEIPT"
                  ? "bg-emerald-600 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Inflows
            </button>
            <button
              onClick={() => setTypeFilter("PAYMENT")}
              className={`px-3 py-1 text-xs font-semibold rounded ${
                typeFilter === "PAYMENT"
                  ? "bg-red-600 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Outflows
            </button>
          </div>
        </div>

        <p className="text-xs text-slate-500 self-end sm:self-center">
          Showing <span className="font-semibold text-slate-700">{filteredPayments.length}</span> of{" "}
          <span className="font-semibold text-slate-700">{payments.length}</span> transactions
        </p>
      </div>

      {/* Table */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
          <p className="text-sm font-bold text-[#141b2b]">Settlement Transaction Register</p>
          <span className="text-xs text-slate-500">Dual-direction ledger ledger</span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Loading payment records...</p>
          </div>
        ) : filteredPayments.length === 0 ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <CreditCard className="w-12 h-12 text-slate-300" />
            <p className="font-bold text-slate-700 text-lg">No payments recorded</p>
            <p className="text-sm text-slate-400 max-w-sm">
              {searchTerm
                ? "No payments matched your search query."
                : "Payments and MoMo receipts will appear here as they are processed."}
            </p>
            {!searchTerm && (
              <button
                type="button"
                onClick={() => setIsModalOpen(true)}
                className="mt-2 text-sm font-semibold text-blue-600 hover:underline"
              >
                + Record a payment transaction
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-6">Date</th>
                  <th className="py-3 px-6">Type</th>
                  <th className="py-3 px-6">Counterparty / Invoice</th>
                  <th className="py-3 px-6">Channel / Rail</th>
                  <th className="py-3 px-6">Reference</th>
                  <th className="py-3 px-6 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-sm">
                {filteredPayments.map((p) => {
                  const isInflow = p.transaction_type === "RECEIPT";

                  return (
                    <tr key={p.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-4 px-6 text-slate-600 text-xs">
                        {new Date(p.transaction_date || p.created_at).toLocaleDateString()}
                      </td>

                      <td className="py-4 px-6">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                            isInflow
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                              : "bg-red-100 text-red-800 border border-red-200"
                          }`}
                        >
                          {isInflow ? (
                            <ArrowDownLeft className="w-3 h-3" />
                          ) : (
                            <ArrowUpRight className="w-3 h-3" />
                          )}
                          {isInflow ? "Receipt" : "Payout"}
                        </span>
                      </td>

                      <td className="py-4 px-6">
                        <p className="font-semibold text-slate-900 leading-tight">
                          {p.customer_name || "General Counterparty"}
                        </p>
                        {p.invoice_number && (
                          <p className="text-xs text-blue-600 mt-0.5 font-mono">
                            Inv: {p.invoice_number}
                          </p>
                        )}
                      </td>

                      <td className="py-4 px-6">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded text-xs font-medium border ${getMethodBadge(
                            p.payment_method
                          )}`}
                        >
                          {p.payment_method.replace(/_/g, " ")}
                        </span>
                      </td>

                      <td className="py-4 px-6 font-mono text-xs text-slate-600">
                        {p.reference_number || p.payment_reference || "—"}
                      </td>

                      <td
                        className={`py-4 px-6 text-right font-mono font-bold ${
                          isInflow ? "text-emerald-700" : "text-red-600"
                        }`}
                      >
                        {isInflow ? "+" : "-"} {formatGHS(p.amount)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Record Payment Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-blue-600" />
                <h3 className="text-lg font-bold text-slate-900">Record Payment Transaction</h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleRecordPayment} className="mt-4 flex flex-col gap-4">
              {/* Type Switcher */}
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Transaction Direction
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setTransactionType("RECEIPT")}
                    className={`py-2 text-xs font-bold rounded-lg border flex items-center justify-center gap-1.5 transition-colors ${
                      transactionType === "RECEIPT"
                        ? "bg-emerald-50 border-emerald-500 text-emerald-800"
                        : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    <ArrowDownLeft className="w-3.5 h-3.5" />
                    Inflow (Customer Receipt)
                  </button>
                  <button
                    type="button"
                    onClick={() => setTransactionType("PAYMENT")}
                    className={`py-2 text-xs font-bold rounded-lg border flex items-center justify-center gap-1.5 transition-colors ${
                      transactionType === "PAYMENT"
                        ? "bg-red-50 border-red-500 text-red-800"
                        : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    <ArrowUpRight className="w-3.5 h-3.5" />
                    Outflow (Vendor Payout)
                  </button>
                </div>
              </div>

              {/* Amount */}
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Amount (GH¢) <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  placeholder="500.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
                />
              </div>

              {/* Channel */}
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Payment Channel / Aggregator
                </label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                >
                  <option value="MTN_MOMO">MTN Mobile Money</option>
                  <option value="TELECEL_CASH">Telecel Cash</option>
                  <option value="AT_MONEY">AT Money</option>
                  <option value="BANK_TRANSFER">Commercial Bank Transfer</option>
                  <option value="BANK_POS">Bank Card / POS</option>
                  <option value="CASH">Cash in Hand</option>
                  <option value="CHEQUE">Cheque</option>
                </select>
              </div>

              {/* Counterparty */}
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Counterparty (Customer / Vendor)
                </label>
                <select
                  value={selectedContactId}
                  onChange={(e) => setSelectedContactId(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                >
                  <option value="">Select party (optional)</option>
                  {contacts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.contact_type})
                    </option>
                  ))}
                </select>
              </div>

              {/* Invoice link (if receipt) */}
              {transactionType === "RECEIPT" && (
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Settled Invoice (Optional)
                  </label>
                  <select
                    value={selectedInvoiceId}
                    onChange={(e) => setSelectedInvoiceId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
                  >
                    <option value="">None / Unassigned deposit</option>
                    {invoices.map((inv) => (
                      <option key={inv.id} value={inv.id}>
                        {inv.invoice_number} (Due: GH¢ {parseFloat(String(inv.balance_due || inv.total_amount)).toFixed(2)})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Reference */}
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  External Reference # / MoMo Transaction ID
                </label>
                <input
                  type="text"
                  placeholder="e.g. 2938471928"
                  value={referenceNumber}
                  onChange={(e) => setReferenceNumber(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
                />
              </div>

              {/* Notes */}
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Reconciliation Notes
                </label>
                <input
                  type="text"
                  placeholder="Optional internal notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                />
              </div>

              <div className="flex items-center justify-end gap-3 mt-4 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !amount || parseFloat(amount) <= 0}
                  className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                  Record Transaction
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
