"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  BookOpen,
  Search,
  RefreshCw,
  AlertCircle,
  X,
  ArrowUpRight,
  ExternalLink,
  ChevronRight,
  Receipt,
  Scale,
} from "lucide-react";

interface AccountItem {
  id: string;
  account_code: string;
  account_name: string;
  simple_label: string;
  category_code: string;
  category_name: string;
  normal_balance: "DEBIT" | "CREDIT";
  is_active: boolean;
  current_balance?: number;
}

interface TrialBalanceRow {
  account_code: string;
  account_name: string;
  category_name: string;
  net_balance: string;
  debit_balance: string;
  credit_balance: string;
}

interface AccountEntryLine {
  id: string;
  journal_entry_id: string;
  entry_number: string;
  entry_date: string;
  description: string;
  debit_amount: string | number;
  credit_amount: string | number;
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

export default function LedgersPage() {
  const { mode } = useMode();

  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [refreshKey, setRefreshKey] = useState(0);

  // Drilldown Statement Modal
  const [statementAccount, setStatementAccount] = useState<AccountItem | null>(null);
  const [statementEntries, setStatementEntries] = useState<AccountEntryLine[]>([]);
  const [isLoadingStatement, setIsLoadingStatement] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadLedgers() {
      try {
        const [accRes, tbRes] = await Promise.all([
          apiClient.get<AccountItem[]>("/api/v1/ledger/accounts/"),
          apiClient.get<{ rows?: TrialBalanceRow[] }>(
            "/api/v1/ledger/reports/trial-balance/?include_zero_balances=true"
          ),
        ]);

        if (!isCancelled) {
          const balanceMap = new Map<string, number>();
          if (tbRes.data?.rows) {
            tbRes.data.rows.forEach((r) => {
              const net = parseFloat(r.net_balance || "0");
              const deb = parseFloat(r.debit_balance || "0");
              const cred = parseFloat(r.credit_balance || "0");
              balanceMap.set(r.account_code, net !== 0 ? net : deb - cred);
            });
          }

          const combined = accRes.data.map((acc) => ({
            ...acc,
            current_balance: balanceMap.get(acc.account_code) || 0,
          }));

          setAccounts(combined);
          setError(null);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
          setError(resp?.detail || "Failed to load ledger accounts.");
          setIsLoading(false);
        }
      }
    }

    loadLedgers();

    return () => {
      isCancelled = true;
    };
  }, [refreshKey]);

  // Load Account Statement Drilldown
  const handleOpenStatement = async (acc: AccountItem) => {
    setStatementAccount(acc);
    setIsLoadingStatement(true);
    try {
      const res = await apiClient.get<AccountEntryLine[]>(
        `/api/v1/ledger/accounts/${acc.id}/entries/`
      );
      setStatementEntries(res.data);
    } catch {
      setStatementEntries([]);
    } finally {
      setIsLoadingStatement(false);
    }
  };

  const categories = useMemo(() => {
    const set = new Set<string>();
    accounts.forEach((a) => {
      if (a.category_name) set.add(a.category_name);
    });
    return Array.from(set).sort();
  }, [accounts]);

  const filteredAccounts = useMemo(() => {
    return accounts.filter((acc) => {
      const q = searchTerm.toLowerCase();
      const matchesSearch =
        acc.account_code.toLowerCase().includes(q) ||
        acc.account_name.toLowerCase().includes(q) ||
        (acc.simple_label && acc.simple_label.toLowerCase().includes(q));

      const matchesCat =
        selectedCategory === "ALL" || acc.category_name === selectedCategory;

      return matchesSearch && matchesCat;
    });
  }, [accounts, searchTerm, selectedCategory]);

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              {mode === "simple" ? "Account Balances" : "General Ledgers"}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1">
              <Scale className="w-3.5 h-3.5" />
              Hot-Account Aggregations
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            {mode === "simple"
              ? "View real-time balances for all business buckets and drill into account statements."
              : "Sub-5ms lock-free dynamic general ledger aggregations and detailed journal lines."}
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
            title="Refresh accounts"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <Link
            href="/dashboard/chart-of-accounts"
            className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors"
          >
            View Chart of Accounts
            <ArrowUpRight className="w-4 h-4" />
          </Link>
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

      {/* Category Pills & Search */}
      <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 max-w-full">
          <button
            onClick={() => setSelectedCategory("ALL")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
              selectedCategory === "ALL"
                ? "bg-blue-600 text-white shadow-sm"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            All Accounts ({accounts.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                selectedCategory === cat
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search account code or name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-white border border-[#c3c6d7] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-slate-800 shadow-sm"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
          <p className="text-sm font-bold text-[#141b2b]">General Ledger Accounts</p>
          <span className="text-xs text-slate-500">Live sub-ledger balance</span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Loading ledger accounts...</p>
          </div>
        ) : filteredAccounts.length === 0 ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <BookOpen className="w-12 h-12 text-slate-300" />
            <p className="font-bold text-slate-700 text-lg">No accounts found</p>
            <p className="text-sm text-slate-400 max-w-sm">
              {searchTerm
                ? "No account matches your search query."
                : "No accounts found in this category."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-6">Account Code</th>
                  <th className="py-3 px-6">Account Title</th>
                  <th className="py-3 px-6">Category</th>
                  <th className="py-3 px-6">Normal Balance</th>
                  <th className="py-3 px-6 text-right">Current Balance</th>
                  <th className="py-3 px-6 text-right">Statement</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-sm">
                {filteredAccounts.map((acc) => (
                  <tr key={acc.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-4 px-6 font-mono font-bold text-blue-700">
                      {acc.account_code}
                    </td>

                    <td className="py-4 px-6">
                      <p className="font-bold text-slate-900 leading-tight">
                        {mode === "simple" && acc.simple_label ? acc.simple_label : acc.account_name}
                      </p>
                      {mode === "simple" && acc.simple_label && (
                        <p className="text-xs text-slate-400 mt-0.5">{acc.account_name}</p>
                      )}
                    </td>

                    <td className="py-4 px-6">
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                        {acc.category_name}
                      </span>
                    </td>

                    <td className="py-4 px-6 text-xs text-slate-600">
                      {acc.normal_balance}
                    </td>

                    <td className="py-4 px-6 text-right font-mono font-bold text-slate-900">
                      {formatGHS(acc.current_balance || 0)}
                    </td>

                    <td className="py-4 px-6 text-right">
                      <button
                        type="button"
                        onClick={() => handleOpenStatement(acc)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 p-1.5 rounded hover:bg-blue-50 transition-colors"
                      >
                        Drilldown
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Account Statement Drilldown Drawer */}
      {statementAccount && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-4xl w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <div className="flex items-center gap-2">
                  <Receipt className="w-5 h-5 text-blue-600" />
                  <h3 className="text-lg font-bold text-slate-900">
                    Account Statement: {statementAccount.account_code} - {statementAccount.account_name}
                  </h3>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Category: {statementAccount.category_name} · Normal Balance:{" "}
                  {statementAccount.normal_balance}
                </p>
              </div>
              <button
                onClick={() => setStatementAccount(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4">
              <div className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-xl mb-4">
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">Current Ledger Balance</p>
                  <p className="text-2xl font-bold font-mono text-blue-700 mt-0.5">
                    {formatGHS(statementAccount.current_balance || 0)}
                  </p>
                </div>
                <Link
                  href="/dashboard/transactions"
                  className="text-xs font-semibold text-blue-600 hover:underline inline-flex items-center gap-1"
                >
                  Inspect Journal Entries
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>
              </div>

              {isLoadingStatement ? (
                <div className="p-12 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
                  <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
                  <p className="text-sm">Fetching journal postings...</p>
                </div>
              ) : statementEntries.length === 0 ? (
                <div className="p-12 text-center text-slate-400">
                  <p className="font-semibold text-slate-600">No journal lines recorded for this account</p>
                  <p className="text-xs mt-1">Postings will appear when transactions are recorded.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-100 uppercase text-slate-600 font-bold">
                        <th className="py-2.5 px-3">Date</th>
                        <th className="py-2.5 px-3">Entry #</th>
                        <th className="py-2.5 px-3">Memo / Description</th>
                        <th className="py-2.5 px-3 text-right">Debit (GH¢)</th>
                        <th className="py-2.5 px-3 text-right">Credit (GH¢)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono">
                      {statementEntries.map((e) => (
                        <tr key={e.id} className="hover:bg-slate-50">
                          <td className="py-3 px-3 font-sans text-slate-600">
                            {new Date(e.entry_date).toLocaleDateString()}
                          </td>
                          <td className="py-3 px-3 font-bold text-blue-600">{e.entry_number}</td>
                          <td className="py-3 px-3 font-sans text-slate-800">{e.description || "—"}</td>
                          <td className="py-3 px-3 text-right text-slate-900">
                            {parseFloat(String(e.debit_amount)) > 0
                              ? formatGHS(parseFloat(String(e.debit_amount)))
                              : "—"}
                          </td>
                          <td className="py-3 px-3 text-right text-slate-900">
                            {parseFloat(String(e.credit_amount)) > 0
                              ? formatGHS(parseFloat(String(e.credit_amount)))
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="flex justify-end mt-6 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setStatementAccount(null)}
                className="px-5 py-2 text-sm font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
