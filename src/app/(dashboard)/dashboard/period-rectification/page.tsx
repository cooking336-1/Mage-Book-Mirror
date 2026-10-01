"use client";

import { useEffect, useState, useMemo } from "react";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  Lock,
  Unlock,
  AlertTriangle,
  RefreshCw,
  Plus,
  CheckCircle,
  AlertCircle,
  X,
  ShieldCheck,
  Check,
  Clock,
  BookOpen,
} from "lucide-react";

interface FiscalPeriod {
  id: string;
  period_name: string;
  start_date: string;
  end_date: string;
  is_closed: boolean;
  closed_at: string | null;
  closed_by: string | null;
}

interface ChartAccount {
  id: string;
  account_code: string;
  account_name: string;
  simple_label: string;
}

interface LineFormRow {
  account: string;
  description: string;
  debit: string;
  credit: string;
}

function formatGHS(amount: number): string {
  return new Intl.NumberFormat("en-GH", {
    style: "currency",
    currency: "GHS",
    minimumFractionDigits: 2,
  })
    .format(amount)
    .replace("GHS", "GH¢");
}

export default function PeriodRectificationPage() {
  const { mode } = useMode();

  const [periods, setPeriods] = useState<FiscalPeriod[]>([]);
  const [accounts, setAccounts] = useState<ChartAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // Period to close
  const [periodToClose, setPeriodToClose] = useState<FiscalPeriod | null>(null);
  const [isClosingPeriod, setIsClosingPeriod] = useState(false);

  // Rectification Modal
  const [isRectifyModalOpen, setIsRectifyModalOpen] = useState(false);
  const [rectifyDate, setRectifyDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [statutoryReason, setStatutoryReason] = useState("");
  const [lineRows, setLineRows] = useState<LineFormRow[]>([
    { account: "", description: "", debit: "", credit: "" },
    { account: "", description: "", debit: "", credit: "" },
  ]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadData() {
      try {
        const [periodsRes, accRes] = await Promise.all([
          apiClient.get<FiscalPeriod[]>("/api/v1/ledger/fiscal-periods/"),
          apiClient.get<ChartAccount[]>("/api/v1/ledger/accounts/"),
        ]);

        if (!isCancelled) {
          setPeriods(periodsRes.data);
          setAccounts(accRes.data);
          setError(null);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
          setError(resp?.detail || "Failed to load fiscal periods.");
          setIsLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [refreshKey]);

  // Execute Period Hard Lock
  const handleClosePeriod = async () => {
    if (!periodToClose) return;

    setIsClosingPeriod(true);
    setError(null);

    try {
      await apiClient.post(`/api/v1/ledger/fiscal-periods/${periodToClose.id}/close/`);
      setSuccessMsg(`Fiscal period '${periodToClose.period_name}' is now officially locked and closed.`);
      setPeriodToClose(null);
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to close fiscal period. Owner or Accountant role required.");
    } finally {
      setIsClosingPeriod(false);
    }
  };

  // Double-entry validation for adjustment entry
  const formTotals = useMemo(() => {
    let totalDebit = 0;
    let totalCredit = 0;

    lineRows.forEach((r) => {
      const d = parseFloat(r.debit) || 0;
      const c = parseFloat(r.credit) || 0;
      totalDebit += d;
      totalCredit += c;
    });

    const isBalanced = Math.abs(totalDebit - totalCredit) < 0.001 && totalDebit > 0;
    return { totalDebit, totalCredit, isBalanced, difference: Math.abs(totalDebit - totalCredit) };
  }, [lineRows]);

  // Post Prior Period Adjustment
  const handlePostRectification = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTotals.isBalanced) {
      setError("Double-entry equilibrium invariant failed: Debits must strictly equal credits.");
      return;
    }

    if (!statutoryReason.trim()) {
      setError("Please document a mandatory statutory reason for this prior-period rectification.");
      return;
    }

    const validLines = lineRows
      .filter((r) => r.account && ((parseFloat(r.debit) || 0) > 0 || (parseFloat(r.credit) || 0) > 0))
      .map((r) => ({
        account: r.account,
        description: `[RECTIFICATION] ${r.description.trim() || statutoryReason.trim()}`,
        debit_amount: parseFloat(r.debit) || 0,
        credit_amount: parseFloat(r.credit) || 0,
      }));

    if (validLines.length < 2) {
      setError("Please specify at least two line items with assigned accounts.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await apiClient.post("/api/v1/ledger/journal-entries/", {
        entry_date: rectifyDate,
        narration: `[PRIOR PERIOD RECTIFICATION] ${statutoryReason.trim()}`,
        lines: validLines,
      });

      setSuccessMsg("Prior-period adjustment posted and logged to immutable audit trail.");
      setIsRectifyModalOpen(false);
      setStatutoryReason("");
      setLineRows([
        { account: "", description: "", debit: "", credit: "" },
        { account: "", description: "", debit: "", credit: "" },
      ]);
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to post adjustment voucher.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const closedCount = useMemo(() => periods.filter((p) => p.is_closed).length, [periods]);
  const openCount = useMemo(() => periods.filter((p) => !p.is_closed).length, [periods]);

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              {mode === "simple" ? "Fix a Past Mistake" : "Prior Period Rectification & Lock"}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              Statutory Hard Lock
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            {mode === "simple"
              ? "Lock completed months to protect your records, or post audited adjustments to fix past entries."
              : "Fiscal period closing enforcement, lock immutability, and audited prior-period journal adjustments."}
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
            title="Refresh periods"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsRectifyModalOpen(true)}
            className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            {mode === "simple" ? "+ Fix a Mistake" : "+ Record Adjustment Voucher"}
          </button>
        </div>
      </div>

      {/* Statutory Alert Strip */}
      <div className="bg-[#fef2f2] border border-[#fecaca] rounded-xl p-5 flex items-start gap-3 shadow-sm">
        <AlertTriangle className="text-[#dc2626] w-5 h-5 shrink-0 mt-0.5" />
        <div className="text-sm text-[#7f1d1d]">
          <p className="font-bold">Prior-Period Immutability Notice</p>
          <p className="mt-0.5 text-xs text-red-800 leading-relaxed">
            Closed fiscal periods are strictly locked against retroactive mutation. Any corrections
            made here are posted as explicit adjustment vouchers and logged into the SHA-256 forensic
            audit trail for statutory PBC audit examination.
          </p>
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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <Lock className="w-4 h-4 text-red-600" />
            Locked / Closed Periods
          </div>
          <p className="text-2xl font-bold text-red-700 mt-2">{closedCount}</p>
          <p className="text-xs text-slate-500 mt-1">Immutable fiscal periods</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <Unlock className="w-4 h-4 text-emerald-600" />
            Open Active Periods
          </div>
          <p className="text-2xl font-bold text-emerald-700 mt-2">{openCount}</p>
          <p className="text-xs text-slate-500 mt-1">Accepting live postings</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <BookOpen className="w-4 h-4 text-blue-600" />
            Total Configured Periods
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{periods.length}</p>
          <p className="text-xs text-slate-500 mt-1">Fiscal calendar partitions</p>
        </div>
      </div>

      {/* Periods Table */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
          <p className="text-sm font-bold text-[#141b2b]">Fiscal Accounting Periods</p>
          <span className="text-xs text-slate-500">Period closing lock enforcement</span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Loading fiscal periods...</p>
          </div>
        ) : periods.length === 0 ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <Lock className="w-12 h-12 text-slate-300" />
            <p className="font-bold text-slate-700 text-lg">No fiscal periods found</p>
            <p className="text-sm text-slate-400 max-w-sm">
              Fiscal periods are auto-generated when transactions are recorded or seeded during onboarding.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-6">Period Name</th>
                  <th className="py-3 px-6">Date Range</th>
                  <th className="py-3 px-6">Status</th>
                  <th className="py-3 px-6">Closing Details</th>
                  <th className="py-3 px-6 text-right">Lock Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-sm">
                {periods.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-4 px-6 font-bold text-slate-900">{p.period_name}</td>

                    <td className="py-4 px-6 text-slate-600 text-xs font-mono">
                      {new Date(p.start_date).toLocaleDateString()} &mdash;{" "}
                      {new Date(p.end_date).toLocaleDateString()}
                    </td>

                    <td className="py-4 px-6">
                      {p.is_closed ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
                          <Lock className="w-3 h-3" />
                          Locked &amp; Closed
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                          <Unlock className="w-3 h-3" />
                          Open
                        </span>
                      )}
                    </td>

                    <td className="py-4 px-6 text-xs text-slate-500">
                      {p.closed_at ? (
                        <span className="flex items-center gap-1 text-slate-600">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          Closed on {new Date(p.closed_at).toLocaleDateString()}
                        </span>
                      ) : (
                        <span className="text-slate-400">Open for new entries</span>
                      )}
                    </td>

                    <td className="py-4 px-6 text-right">
                      {p.is_closed ? (
                        <span className="text-xs font-medium text-slate-400">Locked</span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setPeriodToClose(p)}
                          className="inline-flex items-center gap-1 px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-xs font-semibold shadow-sm transition-colors"
                        >
                          <Lock className="w-3 h-3" />
                          Lock Period
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Lock Period Confirmation Modal */}
      {periodToClose && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-100">
            <div className="flex items-center gap-3 pb-3 border-b border-slate-100">
              <div className="p-2 rounded-lg bg-red-50 text-red-600">
                <Lock className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">Lock Fiscal Period</h3>
            </div>

            <p className="text-sm text-slate-600 mt-3 leading-relaxed">
              Are you sure you want to permanently lock and close{" "}
              <span className="font-bold text-slate-900">&quot;{periodToClose.period_name}&quot;</span>?
            </p>
            <p className="text-xs text-red-700 bg-red-50 p-3 rounded-lg border border-red-200 mt-2">
              Warning: Once closed, no further transactions or bills can be posted to this period. Any future fixes will require an explicit prior-period adjustment.
            </p>

            <div className="flex items-center justify-end gap-3 mt-6">
              <button
                type="button"
                onClick={() => setPeriodToClose(null)}
                className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleClosePeriod}
                disabled={isClosingPeriod}
                className="px-5 py-2 text-sm font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
              >
                {isClosingPeriod && <RefreshCw className="w-4 h-4 animate-spin" />}
                Confirm &amp; Lock
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Record Adjustment Voucher Modal */}
      {isRectifyModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  {mode === "simple" ? "Fix Past Mistake" : "Prior-Period Adjustment Voucher"}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Audited double-entry correction logged to forensic trail.
                </p>
              </div>
              <button
                onClick={() => setIsRectifyModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handlePostRectification} className="mt-4 flex flex-col gap-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Adjustment Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={rectifyDate}
                    onChange={(e) => setRectifyDate(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Mandatory Statutory Justification <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Prior period revenue correction per GRA audit"
                    value={statutoryReason}
                    onChange={(e) => setStatutoryReason(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  />
                </div>
              </div>

              {/* Adjustment Lines */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-bold uppercase text-slate-600">
                    Adjustment Lines
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
                              {acc.account_code} - {acc.account_name}
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
                          placeholder="Adjustment memo"
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
                            if (parseFloat(e.target.value) > 0) updated[idx].credit = "";
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
                            if (parseFloat(e.target.value) > 0) updated[idx].debit = "";
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

              {/* Balanced Entry Notice */}
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
                <div>
                  {formTotals.isBalanced ? (
                    <span className="flex items-center gap-1 text-emerald-700 font-semibold">
                      <Check className="w-4 h-4" />
                      Balanced Entry
                    </span>
                  ) : (
                    <span className="font-semibold">
                      Difference: {formatGHS(formTotals.difference)}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 mt-4 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsRectifyModalOpen(false)}
                  className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !formTotals.isBalanced || !statutoryReason}
                  className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                  Post Adjustment Voucher
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
