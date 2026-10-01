"use client";

import { useEffect, useState, useMemo } from "react";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  FileText,
  Plus,
  RefreshCw,
  Search,
  AlertCircle,
  CheckCircle,
  X,
  BookOpen,
  ArrowRightLeft,
  Calendar,
  Check,
  Eye,
} from "lucide-react";

interface JournalLineItem {
  id?: string;
  account_code: string;
  account_name: string;
  description: string;
  debit_amount: string | number;
  credit_amount: string | number;
}

interface JournalEntry {
  id: string;
  entry_number: string;
  entry_date: string;
  narration: string;
  source_type: string;
  is_posted: boolean;
  lines: JournalLineItem[];
}

interface ChartAccount {
  id: string;
  account_code: string;
  account_name: string;
  simple_label: string;
  category_name: string;
}

interface LineFormRow {
  account: string; // account code or id
  description: string;
  debit: string;
  credit: string;
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

export default function TransactionsPage() {
  const { mode } = useMode();

  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [accounts, setAccounts] = useState<ChartAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  // Detail Modal
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null);

  // Create Modal
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [entryDate, setEntryDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [narration, setNarration] = useState("");
  const [lineRows, setLineRows] = useState<LineFormRow[]>([
    { account: "", description: "", debit: "", credit: "" },
    { account: "", description: "", debit: "", credit: "" },
  ]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadData() {
      try {
        const [entriesRes, accountsRes] = await Promise.all([
          apiClient.get<JournalEntry[]>("/api/v1/ledger/journal-entries/"),
          apiClient.get<ChartAccount[]>("/api/v1/ledger/accounts/"),
        ]);

        if (!isCancelled) {
          setEntries(entriesRes.data);
          setAccounts(accountsRes.data);
          setError(null);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
          setError(resp?.detail || "Failed to load transactions.");
          setIsLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [refreshKey]);

  // Real-time double-entry calculations for create modal
  const formTotals = useMemo(() => {
    let totalDebit = 0;
    let totalCredit = 0;

    lineRows.forEach((r) => {
      const d = parseFloat(r.debit) || 0;
      const c = parseFloat(r.credit) || 0;
      totalDebit += d;
      totalCredit += c;
    });

    const isBalanced =
      Math.abs(totalDebit - totalCredit) < 0.001 && totalDebit > 0;

    return { totalDebit, totalCredit, isBalanced, difference: Math.abs(totalDebit - totalCredit) };
  }, [lineRows]);

  const handleCreateEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTotals.isBalanced) {
      setError("Double-entry invariant failed: Total debits must equal total credits.");
      return;
    }

    const validLines = lineRows
      .filter((r) => r.account && ((parseFloat(r.debit) || 0) > 0 || (parseFloat(r.credit) || 0) > 0))
      .map((r) => ({
        account: r.account,
        description: r.description.trim() || narration.trim(),
        debit_amount: parseFloat(r.debit) || 0,
        credit_amount: parseFloat(r.credit) || 0,
      }));

    if (validLines.length < 2) {
      setError("Please complete at least two line items with assigned accounts.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await apiClient.post("/api/v1/ledger/journal-entries/", {
        entry_date: entryDate,
        narration: narration.trim(),
        lines: validLines,
      });

      setSuccessMsg("Journal entry posted to double-entry general ledger.");
      setIsCreateOpen(false);
      setNarration("");
      setLineRows([
        { account: "", description: "", debit: "", credit: "" },
        { account: "", description: "", debit: "", credit: "" },
      ]);
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to post journal entry.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredEntries = useMemo(() => {
    return entries.filter((entry) => {
      const q = searchTerm.toLowerCase();
      const num = entry.entry_number.toLowerCase();
      const narr = entry.narration.toLowerCase();
      const linesMatch = entry.lines.some(
        (l) =>
          l.account_name.toLowerCase().includes(q) ||
          l.account_code.toLowerCase().includes(q)
      );
      return num.includes(q) || narr.includes(q) || linesMatch;
    });
  }, [entries, searchTerm]);

  const totalTurnover = useMemo(() => {
    return entries.reduce((sum, entry) => {
      const entryDebit = entry.lines.reduce(
        (lSum, l) => lSum + parseFloat(String(l.debit_amount || 0)),
        0
      );
      return sum + entryDebit;
    }, 0);
  }, [entries]);

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              {mode === "simple" ? "All Transactions" : "Transaction Entries"}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1">
              <Check className="w-3.5 h-3.5" />
              Double-Entry Balanced
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            {mode === "simple"
              ? "A chronological record of every business movement, payment, and adjustment."
              : "Audit-ready general ledger journal vouchers and double-entry postings."}
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
            title="Refresh transactions"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsCreateOpen(true)}
            className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            {mode === "simple" ? "+ Record Transaction" : "+ New Journal Entry"}
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
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <BookOpen className="w-4 h-4 text-blue-600" />
            Total Recorded Entries
          </div>
          <p className="text-2xl font-bold text-[#191c1e] mt-2">{entries.length}</p>
          <p className="text-xs text-slate-500 mt-1">Balanced double-entry records</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <ArrowRightLeft className="w-4 h-4 text-emerald-600" />
            Turnover Volume
          </div>
          <p className="text-2xl font-bold text-emerald-700 mt-2">{formatGHS(totalTurnover)}</p>
          <p className="text-xs text-slate-500 mt-1">Cumulative debits posted</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <Calendar className="w-4 h-4 text-amber-600" />
            Active Master Accounts
          </div>
          <p className="text-2xl font-bold text-[#191c1e] mt-2">{accounts.length}</p>
          <p className="text-xs text-slate-500 mt-1">Chart of accounts available</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by entry #, narration, or account..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border border-[#c3c6d7] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-slate-800 shadow-sm"
          />
        </div>
        <p className="text-xs text-slate-500 self-end sm:self-center">
          Showing <span className="font-semibold text-slate-700">{filteredEntries.length}</span> of{" "}
          <span className="font-semibold text-slate-700">{entries.length}</span> entries
        </p>
      </div>

      {/* Table */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
          <p className="text-sm font-bold text-[#141b2b]">Transaction Register</p>
          <span className="text-xs text-slate-500">Immutable posting records</span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Loading journal entries...</p>
          </div>
        ) : filteredEntries.length === 0 ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <FileText className="w-12 h-12 text-slate-300" />
            <p className="font-bold text-slate-700 text-lg">No transactions found</p>
            <p className="text-sm text-slate-400 max-w-sm">
              {searchTerm
                ? "No entries matched your search query."
                : "Record your first transaction or journal entry."}
            </p>
            {!searchTerm && (
              <button
                type="button"
                onClick={() => setIsCreateOpen(true)}
                className="mt-2 text-sm font-semibold text-blue-600 hover:underline"
              >
                + Record transaction
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-6">Entry Number</th>
                  <th className="py-3 px-6">Date</th>
                  <th className="py-3 px-6">Narration</th>
                  <th className="py-3 px-6">Source</th>
                  <th className="py-3 px-6 text-right">Debit / Credit Amount</th>
                  <th className="py-3 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-sm">
                {filteredEntries.map((entry) => {
                  const entryTotal = entry.lines.reduce(
                    (sum, l) => sum + parseFloat(String(l.debit_amount || 0)),
                    0
                  );

                  return (
                    <tr key={entry.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-4 px-6 font-mono font-bold text-blue-700">
                        {entry.entry_number}
                      </td>

                      <td className="py-4 px-6 text-slate-600">
                        {new Date(entry.entry_date).toLocaleDateString()}
                      </td>

                      <td className="py-4 px-6">
                        <p className="font-medium text-slate-900">{entry.narration || "—"}</p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {entry.lines.length} double-entry line{entry.lines.length !== 1 ? "s" : ""}
                        </p>
                      </td>

                      <td className="py-4 px-6">
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                          {entry.source_type}
                        </span>
                      </td>

                      <td className="py-4 px-6 text-right font-mono font-bold text-slate-900">
                        {formatGHS(entryTotal)}
                      </td>

                      <td className="py-4 px-6 text-right">
                        <button
                          type="button"
                          onClick={() => setSelectedEntry(entry)}
                          className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-800 p-1 rounded hover:bg-blue-50 transition-colors"
                        >
                          <Eye className="w-4 h-4" />
                          Inspect
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

      {/* Inspect Journal Entry Modal */}
      {selectedEntry && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-slate-900">
                    Journal Voucher: {selectedEntry.entry_number}
                  </h3>
                  <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                    POSTED
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Posted on {new Date(selectedEntry.entry_date).toLocaleDateString()} · Source:{" "}
                  {selectedEntry.source_type}
                </p>
              </div>
              <button
                onClick={() => setSelectedEntry(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4">
              <p className="text-sm font-semibold text-slate-700">Narration:</p>
              <p className="text-sm text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-200 mt-1">
                {selectedEntry.narration || "No narration provided."}
              </p>
            </div>

            <div className="mt-5 overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 uppercase text-slate-500 font-bold">
                    <th className="py-2.5 px-3">Account Code</th>
                    <th className="py-2.5 px-3">Account Title</th>
                    <th className="py-2.5 px-3">Description</th>
                    <th className="py-2.5 px-3 text-right">Debit (GH¢)</th>
                    <th className="py-2.5 px-3 text-right">Credit (GH¢)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  {selectedEntry.lines.map((l, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="py-2.5 px-3 font-bold text-blue-700">{l.account_code}</td>
                      <td className="py-2.5 px-3 font-sans font-medium text-slate-800">
                        {l.account_name}
                      </td>
                      <td className="py-2.5 px-3 font-sans text-slate-500">{l.description || "—"}</td>
                      <td className="py-2.5 px-3 text-right text-slate-900">
                        {parseFloat(String(l.debit_amount)) > 0
                          ? formatGHS(l.debit_amount)
                          : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-900">
                        {parseFloat(String(l.credit_amount)) > 0
                          ? formatGHS(l.credit_amount)
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end mt-6 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setSelectedEntry(null)}
                className="px-5 py-2 text-sm font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Journal Entry Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  {mode === "simple" ? "Record Transaction" : "New Double-Entry Journal Voucher"}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Debits must strictly equal credits (Double-Entry Invariant).
                </p>
              </div>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateEntry} className="mt-4 flex flex-col gap-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Transaction Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={entryDate}
                    onChange={(e) => setEntryDate(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Narration / Memo <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Office supplies purchase or settlement adjustment"
                    value={narration}
                    onChange={(e) => setNarration(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  />
                </div>
              </div>

              {/* Dynamic Line Rows */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-bold uppercase text-slate-600">
                    Journal Lines
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      setLineRows([...lineRows, { account: "", description: "", debit: "", credit: "" }])
                    }
                    className="text-xs font-bold text-blue-600 hover:underline flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Line
                  </button>
                </div>

                <div className="flex flex-col gap-2.5">
                  {lineRows.map((row, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-slate-50 border border-slate-200 rounded-lg grid grid-cols-1 sm:grid-cols-12 gap-2.5 items-end"
                    >
                      <div className="sm:col-span-4">
                        <label className="block text-[11px] font-semibold text-slate-500 mb-0.5">
                          Account *
                        </label>
                        <select
                          value={row.account}
                          onChange={(e) => {
                            const updated = [...lineRows];
                            updated[idx].account = e.target.value;
                            setLineRows(updated);
                          }}
                          required
                          className="w-full px-2 py-1.5 border border-slate-300 rounded text-xs bg-white"
                        >
                          <option value="">Select Account</option>
                          {accounts.map((acc) => (
                            <option key={acc.id} value={acc.account_code}>
                              {acc.account_code} -{" "}
                              {mode === "simple" && acc.simple_label
                                ? acc.simple_label
                                : acc.account_name}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="sm:col-span-3">
                        <label className="block text-[11px] font-semibold text-slate-500 mb-0.5">
                          Description
                        </label>
                        <input
                          type="text"
                          placeholder="Optional memo"
                          value={row.description}
                          onChange={(e) => {
                            const updated = [...lineRows];
                            updated[idx].description = e.target.value;
                            setLineRows(updated);
                          }}
                          className="w-full px-2 py-1.5 border border-slate-300 rounded text-xs bg-white"
                        />
                      </div>

                      <div className="sm:col-span-2">
                        <label className="block text-[11px] font-semibold text-slate-500 mb-0.5">
                          Debit (GH¢)
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          placeholder="0.00"
                          value={row.debit}
                          onChange={(e) => {
                            const updated = [...lineRows];
                            updated[idx].debit = e.target.value;
                            if (parseFloat(e.target.value) > 0) {
                              updated[idx].credit = "";
                            }
                            setLineRows(updated);
                          }}
                          className="w-full px-2 py-1.5 border border-slate-300 rounded text-xs bg-white font-mono"
                        />
                      </div>

                      <div className="sm:col-span-2">
                        <label className="block text-[11px] font-semibold text-slate-500 mb-0.5">
                          Credit (GH¢)
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          placeholder="0.00"
                          value={row.credit}
                          onChange={(e) => {
                            const updated = [...lineRows];
                            updated[idx].credit = e.target.value;
                            if (parseFloat(e.target.value) > 0) {
                              updated[idx].debit = "";
                            }
                            setLineRows(updated);
                          }}
                          className="w-full px-2 py-1.5 border border-slate-300 rounded text-xs bg-white font-mono"
                        />
                      </div>

                      <div className="sm:col-span-1 flex justify-center pb-1">
                        {lineRows.length > 2 && (
                          <button
                            type="button"
                            onClick={() => setLineRows(lineRows.filter((_, i) => i !== idx))}
                            className="p-1 text-red-500 hover:text-red-700"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Double-Entry Balancing Bar */}
              <div
                className={`p-3 rounded-lg border flex items-center justify-between text-xs ${
                  formTotals.isBalanced
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                    : "bg-amber-50 border-amber-200 text-amber-800"
                }`}
              >
                <div>
                  <span className="font-bold">Total Debits: </span>
                  <span className="font-mono">{formatGHS(formTotals.totalDebit)}</span>
                  <span className="mx-2">|</span>
                  <span className="font-bold">Total Credits: </span>
                  <span className="font-mono">{formatGHS(formTotals.totalCredit)}</span>
                </div>
                <div className="font-semibold">
                  {formTotals.isBalanced ? (
                    <span className="flex items-center gap-1 text-emerald-700">
                      <Check className="w-4 h-4" />
                      Balanced Entry
                    </span>
                  ) : (
                    <span>Difference: {formatGHS(formTotals.difference)}</span>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 mt-4 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !formTotals.isBalanced}
                  className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                  Post Transaction
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
