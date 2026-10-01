"use client";

import { useEffect, useState } from "react";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  TrendingUp,
  Scale,
  Calendar,
  Download,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  ShieldCheck,
  ChevronRight,
  Layers,
} from "lucide-react";

interface AccountSnapshot {
  account_id: string;
  account_code: string;
  account_name: string;
  simple_label: string;
  category_name: string;
  debit_balance: string;
  credit_balance: string;
  net_balance: string;
}

interface ProfitAndLossData {
  start_date: string;
  end_date: string;
  operating_revenue: AccountSnapshot[];
  total_revenue: string;
  cost_of_goods_sold: AccountSnapshot[];
  total_cogs: string;
  gross_profit: string;
  operating_expenses: AccountSnapshot[];
  total_operating_expenses: string;
  net_profit: string;
  net_margin_percentage: string;
}

interface BalanceSheetData {
  as_of_date: string;
  assets: AccountSnapshot[];
  total_assets: string;
  liabilities: AccountSnapshot[];
  total_liabilities: string;
  equity: AccountSnapshot[];
  current_period_earnings: string;
  total_equity: string;
  total_liabilities_and_equity: string;
  is_balanced: boolean;
}

interface TrialBalanceData {
  as_of_date: string;
  rows: AccountSnapshot[];
  total_debits: string;
  total_credits: string;
  is_balanced: boolean;
}

type ReportType = "PNL" | "BALANCE_SHEET" | "TRIAL_BALANCE";

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

export default function ReportsPage() {
  const { mode } = useMode();

  const [activeTab, setActiveTab] = useState<ReportType>("PNL");

  // Date filters
  const currentYear = new Date().getFullYear();
  const [startDate, setStartDate] = useState(`${currentYear}-01-01`);
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [asOfDate, setAsOfDate] = useState(() => new Date().toISOString().split("T")[0]);

  // Report States
  const [pnl, setPnl] = useState<ProfitAndLossData | null>(null);
  const [bs, setBs] = useState<BalanceSheetData | null>(null);
  const [tb, setTb] = useState<TrialBalanceData | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let isCancelled = false;

    async function fetchReport() {
      setIsLoading(true);
      setError(null);

      try {
        if (activeTab === "PNL") {
          const res = await apiClient.get<ProfitAndLossData>(
            `/api/v1/ledger/reports/profit-and-loss/?start_date=${startDate}&end_date=${endDate}`
          );
          if (!isCancelled) setPnl(res.data);
        } else if (activeTab === "BALANCE_SHEET") {
          const res = await apiClient.get<BalanceSheetData>(
            `/api/v1/ledger/reports/balance-sheet/?as_of_date=${asOfDate}`
          );
          if (!isCancelled) setBs(res.data);
        } else if (activeTab === "TRIAL_BALANCE") {
          const res = await apiClient.get<TrialBalanceData>(
            `/api/v1/ledger/reports/trial-balance/?as_of_date=${asOfDate}&include_zero_balances=false`
          );
          if (!isCancelled) setTb(res.data);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
          setError(resp?.detail || "Failed to generate financial report.");
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    fetchReport();

    return () => {
      isCancelled = true;
    };
  }, [activeTab, startDate, endDate, asOfDate, refreshKey]);

  // CSV Export
  const handleExportCSV = () => {
    let csvContent = "";

    if (activeTab === "PNL" && pnl) {
      csvContent += "Category,Account Code,Account Name,Amount (GHS)\n";
      pnl.operating_revenue.forEach((r) => {
        csvContent += `Operating Revenue,${r.account_code},"${r.account_name}",${r.net_balance}\n`;
      });
      csvContent += `Total Revenue,,,${pnl.total_revenue}\n`;
      pnl.cost_of_goods_sold.forEach((r) => {
        csvContent += `Cost of Goods Sold,${r.account_code},"${r.account_name}",${r.net_balance}\n`;
      });
      csvContent += `Gross Profit,,,${pnl.gross_profit}\n`;
      pnl.operating_expenses.forEach((r) => {
        csvContent += `Operating Expense,${r.account_code},"${r.account_name}",${r.net_balance}\n`;
      });
      csvContent += `Total Operating Expenses,,,${pnl.total_operating_expenses}\n`;
      csvContent += `Net Profit,,,${pnl.net_profit}\n`;
    } else if (activeTab === "BALANCE_SHEET" && bs) {
      csvContent += "Section,Account Code,Account Name,Amount (GHS)\n";
      bs.assets.forEach((r) => {
        csvContent += `Assets,${r.account_code},"${r.account_name}",${r.debit_balance}\n`;
      });
      csvContent += `Total Assets,,,${bs.total_assets}\n`;
      bs.liabilities.forEach((r) => {
        csvContent += `Liabilities,${r.account_code},"${r.account_name}",${r.credit_balance}\n`;
      });
      csvContent += `Total Liabilities,,,${bs.total_liabilities}\n`;
      bs.equity.forEach((r) => {
        csvContent += `Equity,${r.account_code},"${r.account_name}",${r.credit_balance}\n`;
      });
      csvContent += `Current Period Earnings,,,${bs.current_period_earnings}\n`;
      csvContent += `Total Liabilities & Equity,,,${bs.total_liabilities_and_equity}\n`;
    } else if (activeTab === "TRIAL_BALANCE" && tb) {
      csvContent += "Account Code,Account Name,Category,Debit (GHS),Credit (GHS)\n";
      tb.rows.forEach((r) => {
        csvContent += `${r.account_code},"${r.account_name}",${r.category_name},${r.debit_balance},${r.credit_balance}\n`;
      });
      csvContent += `TOTALS,,,${tb.total_debits},${tb.total_credits}\n`;
    }

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${activeTab}_Report_${new Date().toISOString().split("T")[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              Financial Reports
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              Statutory Double-Entry
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            Real-time financial position, comprehensive income, and double-entry trial balance.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            disabled={isLoading}
            className="p-2.5 text-slate-600 bg-white border border-[#c3c6d7] rounded-lg hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50"
            title="Refresh Report"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <button
            onClick={handleExportCSV}
            disabled={isLoading}
            className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Report Switcher Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <button
          type="button"
          onClick={() => setActiveTab("PNL")}
          className={`p-5 rounded-xl border text-left transition-all shadow-sm ${
            activeTab === "PNL"
              ? "bg-blue-50/60 border-blue-500 ring-2 ring-blue-500/20"
              : "bg-white border-[#c3c6d7] hover:border-slate-400"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="p-2 rounded-lg bg-blue-100 text-blue-700">
              <TrendingUp className="w-5 h-5" />
            </div>
            <ChevronRight className="w-4 h-4 text-slate-400" />
          </div>
          <h3 className="font-bold text-slate-900 text-base mt-3">
            {mode === "simple" ? "Profit & Loss" : "Statement of Profit or Loss"}
          </h3>
          <p className="text-xs text-slate-500 mt-1">Operating revenue, COGS, margins &amp; net earnings</p>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("BALANCE_SHEET")}
          className={`p-5 rounded-xl border text-left transition-all shadow-sm ${
            activeTab === "BALANCE_SHEET"
              ? "bg-blue-50/60 border-blue-500 ring-2 ring-blue-500/20"
              : "bg-white border-[#c3c6d7] hover:border-slate-400"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="p-2 rounded-lg bg-emerald-100 text-emerald-700">
              <Scale className="w-5 h-5" />
            </div>
            <ChevronRight className="w-4 h-4 text-slate-400" />
          </div>
          <h3 className="font-bold text-slate-900 text-base mt-3">
            {mode === "simple" ? "Balance Sheet" : "Statement of Financial Position"}
          </h3>
          <p className="text-xs text-slate-500 mt-1">Assets, liabilities, and owners&apos; equity equilibrium</p>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("TRIAL_BALANCE")}
          className={`p-5 rounded-xl border text-left transition-all shadow-sm ${
            activeTab === "TRIAL_BALANCE"
              ? "bg-blue-50/60 border-blue-500 ring-2 ring-blue-500/20"
              : "bg-white border-[#c3c6d7] hover:border-slate-400"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="p-2 rounded-lg bg-purple-100 text-purple-700">
              <Layers className="w-5 h-5" />
            </div>
            <ChevronRight className="w-4 h-4 text-slate-400" />
          </div>
          <h3 className="font-bold text-slate-900 text-base mt-3">Trial Balance</h3>
          <p className="text-xs text-slate-500 mt-1">Asserting Sum(Debits) == Sum(Credits) across all accounts</p>
        </button>
      </div>

      {/* Date Pickers */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl p-4 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm text-slate-700 font-semibold">
          <Calendar className="w-4 h-4 text-slate-400" />
          <span>Reporting Period:</span>
        </div>

        {activeTab === "PNL" ? (
          <div className="flex items-center gap-3">
            <div>
              <span className="text-xs text-slate-500 mr-2">From:</span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm bg-white"
              />
            </div>
            <div>
              <span className="text-xs text-slate-500 mr-2">To:</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm bg-white"
              />
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">As of Date:</span>
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm bg-white"
            />
          </div>
        )}
      </div>

      {/* Error Notice */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center gap-3 text-sm shadow-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Report Body */}
      {isLoading ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-20 text-center text-slate-500 flex flex-col items-center justify-center gap-3 shadow-sm">
          <RefreshCw className="w-7 h-7 animate-spin text-blue-600" />
          <p className="text-sm font-medium">Calculating dynamic general ledger balances...</p>
        </div>
      ) : activeTab === "PNL" && pnl ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
          <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Profit &amp; Loss Statement</h2>
              <p className="text-xs text-slate-500">
                Period: {pnl.start_date} to {pnl.end_date}
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-500 uppercase font-semibold">Net Margin</span>
              <p className="font-mono font-bold text-blue-700 text-lg">
                {parseFloat(pnl.net_margin_percentage).toFixed(1)}%
              </p>
            </div>
          </div>

          <div className="p-6 flex flex-col gap-6 text-sm">
            {/* Revenue */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                1. Operating Revenue
              </h3>
              <div className="divide-y divide-slate-100">
                {pnl.operating_revenue.map((r) => (
                  <div key={r.account_id} className="flex justify-between py-2.5">
                    <span className="text-slate-800 font-medium">
                      {r.account_code} - {r.account_name}
                    </span>
                    <span className="font-mono">{formatGHS(r.net_balance)}</span>
                  </div>
                ))}
                <div className="flex justify-between py-3 font-bold text-slate-900 border-t-2 border-slate-300">
                  <span>Total Operating Revenue</span>
                  <span className="font-mono text-emerald-700">{formatGHS(pnl.total_revenue)}</span>
                </div>
              </div>
            </div>

            {/* COGS */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                2. Cost of Goods Sold (COGS)
              </h3>
              <div className="divide-y divide-slate-100">
                {pnl.cost_of_goods_sold.map((r) => (
                  <div key={r.account_id} className="flex justify-between py-2.5">
                    <span className="text-slate-800 font-medium">
                      {r.account_code} - {r.account_name}
                    </span>
                    <span className="font-mono">{formatGHS(r.net_balance)}</span>
                  </div>
                ))}
                <div className="flex justify-between py-3 font-bold text-slate-900 border-t-2 border-slate-300">
                  <span>Total COGS</span>
                  <span className="font-mono text-red-600">{formatGHS(pnl.total_cogs)}</span>
                </div>
              </div>
            </div>

            {/* Gross Profit */}
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between font-bold text-base">
              <span className="text-slate-800">Gross Margin / Profit</span>
              <span className="font-mono text-blue-700">{formatGHS(pnl.gross_profit)}</span>
            </div>

            {/* Expenses */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                3. Operating Expenses
              </h3>
              <div className="divide-y divide-slate-100">
                {pnl.operating_expenses.map((r) => (
                  <div key={r.account_id} className="flex justify-between py-2.5">
                    <span className="text-slate-800 font-medium">
                      {r.account_code} - {r.account_name}
                    </span>
                    <span className="font-mono">{formatGHS(r.net_balance)}</span>
                  </div>
                ))}
                <div className="flex justify-between py-3 font-bold text-slate-900 border-t-2 border-slate-300">
                  <span>Total Operating Expenses</span>
                  <span className="font-mono text-amber-700">
                    {formatGHS(pnl.total_operating_expenses)}
                  </span>
                </div>
              </div>
            </div>

            {/* Net Profit */}
            <div className="p-5 bg-blue-50 border border-blue-200 rounded-xl flex items-center justify-between text-lg font-bold">
              <span className="text-blue-900">Net Profit / (Loss) for the Period</span>
              <span
                className={`font-mono text-xl ${
                  parseFloat(pnl.net_profit) >= 0 ? "text-emerald-700" : "text-red-600"
                }`}
              >
                {formatGHS(pnl.net_profit)}
              </span>
            </div>
          </div>
        </div>
      ) : activeTab === "BALANCE_SHEET" && bs ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
          <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Statement of Financial Position</h2>
              <p className="text-xs text-slate-500">As of: {bs.as_of_date}</p>
            </div>
            {bs.is_balanced && (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" />
                Balanced: Assets = Liabilities + Equity
              </span>
            )}
          </div>

          <div className="p-6 flex flex-col gap-6 text-sm">
            {/* Assets */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                1. Total Assets
              </h3>
              <div className="divide-y divide-slate-100">
                {bs.assets.map((r) => (
                  <div key={r.account_id} className="flex justify-between py-2.5">
                    <span className="text-slate-800 font-medium">
                      {r.account_code} - {r.account_name}
                    </span>
                    <span className="font-mono">{formatGHS(r.debit_balance)}</span>
                  </div>
                ))}
                <div className="flex justify-between py-3 font-bold text-slate-900 border-t-2 border-slate-300">
                  <span>Total Assets</span>
                  <span className="font-mono text-blue-700">{formatGHS(bs.total_assets)}</span>
                </div>
              </div>
            </div>

            {/* Liabilities */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                2. Liabilities
              </h3>
              <div className="divide-y divide-slate-100">
                {bs.liabilities.map((r) => (
                  <div key={r.account_id} className="flex justify-between py-2.5">
                    <span className="text-slate-800 font-medium">
                      {r.account_code} - {r.account_name}
                    </span>
                    <span className="font-mono">{formatGHS(r.credit_balance)}</span>
                  </div>
                ))}
                <div className="flex justify-between py-3 font-bold text-slate-900 border-t-2 border-slate-300">
                  <span>Total Liabilities</span>
                  <span className="font-mono text-amber-700">{formatGHS(bs.total_liabilities)}</span>
                </div>
              </div>
            </div>

            {/* Equity */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                3. Equity &amp; Retained Earnings
              </h3>
              <div className="divide-y divide-slate-100">
                {bs.equity.map((r) => (
                  <div key={r.account_id} className="flex justify-between py-2.5">
                    <span className="text-slate-800 font-medium">
                      {r.account_code} - {r.account_name}
                    </span>
                    <span className="font-mono">{formatGHS(r.credit_balance)}</span>
                  </div>
                ))}
                <div className="flex justify-between py-2.5 text-slate-800">
                  <span className="font-medium italic">Current Period Earnings (P&amp;L)</span>
                  <span className="font-mono">{formatGHS(bs.current_period_earnings)}</span>
                </div>
                <div className="flex justify-between py-3 font-bold text-slate-900 border-t-2 border-slate-300">
                  <span>Total Equity</span>
                  <span className="font-mono text-purple-700">{formatGHS(bs.total_equity)}</span>
                </div>
              </div>
            </div>

            {/* Total Liabilities & Equity Verification */}
            <div className="p-5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-base font-bold">
              <span className="text-slate-900">Total Liabilities &amp; Equity</span>
              <span className="font-mono text-lg text-slate-900">
                {formatGHS(bs.total_liabilities_and_equity)}
              </span>
            </div>
          </div>
        </div>
      ) : activeTab === "TRIAL_BALANCE" && tb ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
          <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Trial Balance</h2>
              <p className="text-xs text-slate-500">As of: {tb.as_of_date}</p>
            </div>
            {tb.is_balanced && (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" />
                Equilibrium Verified: Debits == Credits
              </span>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 uppercase text-slate-600 font-bold">
                  <th className="py-3 px-6">Account Code</th>
                  <th className="py-3 px-6">Account Title</th>
                  <th className="py-3 px-6">Category</th>
                  <th className="py-3 px-6 text-right">Debit (GH¢)</th>
                  <th className="py-3 px-6 text-right">Credit (GH¢)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {tb.rows.map((r) => (
                  <tr key={r.account_id} className="hover:bg-slate-50">
                    <td className="py-3 px-6 font-bold text-blue-700">{r.account_code}</td>
                    <td className="py-3 px-6 font-sans font-medium text-slate-800">
                      {mode === "simple" && r.simple_label ? r.simple_label : r.account_name}
                    </td>
                    <td className="py-3 px-6 font-sans text-slate-500">{r.category_name}</td>
                    <td className="py-3 px-6 text-right text-slate-900">
                      {parseFloat(r.debit_balance) > 0 ? formatGHS(r.debit_balance) : "—"}
                    </td>
                    <td className="py-3 px-6 text-right text-slate-900">
                      {parseFloat(r.credit_balance) > 0 ? formatGHS(r.credit_balance) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-300 bg-slate-50 font-bold font-mono text-sm">
                  <td colSpan={3} className="py-4 px-6 font-sans">
                    TOTAL GENERAL LEDGER EQUILIBRIUM
                  </td>
                  <td className="py-4 px-6 text-right text-blue-700 font-mono">
                    {formatGHS(tb.total_debits)}
                  </td>
                  <td className="py-4 px-6 text-right text-blue-700 font-mono">
                    {formatGHS(tb.total_credits)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
