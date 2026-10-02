"use client";

import { useEffect, useState, useMemo } from "react";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  Laptop,
  Car,
  Armchair,
  Wrench,
  Plus,
  RefreshCw,
  Search,
  AlertCircle,
  CheckCircle,
  X,
  Building,
  Check,
} from "lucide-react";

interface AccountItem {
  id: string;
  account_code: string;
  account_name: string;
  simple_label: string;
  category_name: string;
  current_balance?: number;
}

interface TrialBalanceRow {
  account_code: string;
  account_name: string;
  debit_balance: string;
  credit_balance: string;
  net_balance: string;
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

function getAssetIcon(code: string, name: string) {
  const lower = name.toLowerCase();
  if (lower.includes("vehicle") || lower.includes("car") || lower.includes("truck")) {
    return <Car className="w-5 h-5 text-blue-600" />;
  }
  if (lower.includes("computer") || lower.includes("electronic") || lower.includes("hardware")) {
    return <Laptop className="w-5 h-5 text-indigo-600" />;
  }
  if (lower.includes("furniture") || lower.includes("fitting")) {
    return <Armchair className="w-5 h-5 text-amber-600" />;
  }
  return <Wrench className="w-5 h-5 text-slate-600" />;
}

export default function FixedAssetsPage() {
  const { mode } = useMode();

  const [assetAccounts, setAssetAccounts] = useState<AccountItem[]>([]);
  const [fundingAccounts, setFundingAccounts] = useState<AccountItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  // New Asset Acquisition Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [assetName, setAssetName] = useState("");
  const [selectedAssetCode, setSelectedAssetCode] = useState("");
  const [selectedFundingCode, setSelectedFundingCode] = useState("");
  const [acquisitionDate, setAcquisitionDate] = useState(
    () => new Date().toISOString().split("T")[0]
  );
  const [purchaseCost, setPurchaseCost] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadData() {
      try {
        const [accRes, tbRes] = await Promise.all([
          apiClient.get<AccountItem[]>("/api/v1/ledger/accounts/"),
          apiClient.get<{ rows?: TrialBalanceRow[] }>(
            "/api/v1/ledger/reports/trial-balance/?include_zero_balances=true"
          ),
        ]);

        if (isCancelled) return;

        const balanceMap = new Map<string, number>();
        if (tbRes.data?.rows) {
          tbRes.data.rows.forEach((r) => {
            const deb = parseFloat(r.debit_balance || "0");
            const net = parseFloat(r.net_balance || "0");
            balanceMap.set(r.account_code, net > 0 ? net : deb);
          });
        }

        const all = accRes.data;

        // Fixed Assets: codes 1500 to 1899 or category Asset and sub-category
        const fixed = all
          .filter(
            (a) =>
              (a.account_code.startsWith("15") ||
                a.account_code.startsWith("16") ||
                a.account_code.startsWith("17")) &&
              a.category_name?.toUpperCase() === "ASSET"
          )
          .map((a) => ({
            ...a,
            current_balance: balanceMap.get(a.account_code) || 0,
          }));

        // Funding accounts: Cash & Bank (10xx) or AP (2010)
        const funding = all.filter(
          (a) => a.account_code.startsWith("10") || a.account_code.startsWith("20")
        );

        setAssetAccounts(fixed.length > 0 ? fixed : all.filter((a) => a.account_code.startsWith("1")));
        setFundingAccounts(funding);

        if (fixed.length > 0 && !selectedAssetCode) {
          setSelectedAssetCode(fixed[0].account_code);
        }
        if (funding.length > 0 && !selectedFundingCode) {
          setSelectedFundingCode(funding[0].account_code);
        }

        setError(null);
        setIsLoading(false);
      } catch (err: unknown) {
        if (!isCancelled) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
          setError(resp?.detail || "Failed to load fixed asset register.");
          setIsLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [refreshKey, selectedAssetCode, selectedFundingCode]);

  // Aggregate Total Book Value
  const totalBookValue = useMemo(() => {
    return assetAccounts.reduce((sum, a) => sum + (a.current_balance || 0), 0);
  }, [assetAccounts]);

  // Handle Asset Acquisition Submission
  const handleAddAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    const cost = parseFloat(purchaseCost);
    if (!cost || cost <= 0) {
      setError("Please enter a valid purchase cost.");
      return;
    }

    if (!selectedAssetCode || !selectedFundingCode) {
      setError("Please select both an asset category and a funding account.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const memo = `Asset Acquisition: ${assetName.trim()}`;

    try {
      await apiClient.post("/api/v1/ledger/journal-entries/", {
        entry_date: acquisitionDate,
        narration: memo,
        lines: [
          {
            account: selectedAssetCode,
            description: memo,
            debit_amount: cost,
            credit_amount: 0,
          },
          {
            account: selectedFundingCode,
            description: `Payment for ${assetName.trim()}`,
            debit_amount: 0,
            credit_amount: cost,
          },
        ],
      });

      setSuccessMsg(`Asset "${assetName}" recorded and capitalized in General Ledger.`);
      setIsModalOpen(false);
      setAssetName("");
      setPurchaseCost("");
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to record asset acquisition.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredAssets = useMemo(() => {
    return assetAccounts.filter((a) => {
      const q = searchTerm.toLowerCase();
      return (
        a.account_code.toLowerCase().includes(q) ||
        a.account_name.toLowerCase().includes(q) ||
        (a.simple_label && a.simple_label.toLowerCase().includes(q))
      );
    });
  }, [assetAccounts, searchTerm]);

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              {mode === "simple" ? "Things My Business Owns" : "Fixed Assets Register"}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1">
              <Check className="w-3.5 h-3.5" />
              Capitalized in GL
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            {mode === "simple"
              ? "Track vehicles, computers, machinery, and equipment owned by your business."
              : "Fixed asset register, capitalized book values, and acquisition double-entry postings."}
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
            title="Refresh assets"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            {mode === "simple" ? "+ Add Business Property" : "+ Add Asset"}
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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <p className="text-xs font-semibold text-[#434655] uppercase tracking-wide">
            Total Fixed Asset Value
          </p>
          <p className="text-2xl font-bold text-blue-700 mt-1 font-mono">
            {formatGHS(totalBookValue)}
          </p>
          <p className="text-xs text-[#64748b] mt-1">Capitalized balance in General Ledger</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <p className="text-xs font-semibold text-[#434655] uppercase tracking-wide">
            Registered Asset Classes
          </p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{assetAccounts.length}</p>
          <p className="text-xs text-[#64748b] mt-1">Active equipment &amp; property categories</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <p className="text-xs font-semibold text-[#434655] uppercase tracking-wide">
            Tax Depreciation Schedule
          </p>
          <p className="text-lg font-bold text-emerald-700 mt-1">Ghana GRA Capital Allowance</p>
          <p className="text-xs text-[#64748b] mt-1">Class 1-4 pooling per Act 896</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search asset class or code..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border border-[#c3c6d7] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-slate-800 shadow-sm"
          />
        </div>
        <p className="text-xs text-slate-500 self-end sm:self-center">
          Showing <span className="font-semibold text-slate-700">{filteredAssets.length}</span> of{" "}
          <span className="font-semibold text-slate-700">{assetAccounts.length}</span> asset categories
        </p>
      </div>

      {/* Asset Register Table */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
          <p className="text-sm font-bold text-[#141b2b]">Asset Categories &amp; Book Values</p>
          <span className="text-xs text-slate-500">Double-entry ledger balance</span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Loading fixed asset register...</p>
          </div>
        ) : filteredAssets.length === 0 ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <Building className="w-12 h-12 text-slate-300" />
            <p className="font-bold text-slate-700 text-lg">No assets registered</p>
            <p className="text-sm text-slate-400 max-w-sm">
              {searchTerm
                ? "No asset class matched your search query."
                : "Record equipment, vehicles, or property to capitalize them."}
            </p>
            {!searchTerm && (
              <button
                type="button"
                onClick={() => setIsModalOpen(true)}
                className="mt-2 text-sm font-semibold text-blue-600 hover:underline"
              >
                + Capitalize your first asset
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-6">Account Code</th>
                  <th className="py-3 px-6">Asset Category</th>
                  <th className="py-3 px-6">Classification</th>
                  <th className="py-3 px-6 text-right">Total Book Value (Cost)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-sm">
                {filteredAssets.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-4 px-6 font-mono font-bold text-blue-700">
                      {a.account_code}
                    </td>

                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-slate-100">
                          {getAssetIcon(a.account_code, a.account_name)}
                        </div>
                        <div>
                          <p className="font-bold text-slate-900 leading-tight">
                            {mode === "simple" && a.simple_label ? a.simple_label : a.account_name}
                          </p>
                          {mode === "simple" && a.simple_label && (
                            <p className="text-xs text-slate-400 mt-0.5">{a.account_name}</p>
                          )}
                        </div>
                      </div>
                    </td>

                    <td className="py-4 px-6">
                      <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                        Property, Plant &amp; Equipment
                      </span>
                    </td>

                    <td className="py-4 px-6 text-right font-mono font-bold text-slate-900">
                      {formatGHS(a.current_balance || 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Asset Acquisition Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Building className="w-5 h-5 text-blue-600" />
                <h3 className="text-lg font-bold text-slate-900">
                  {mode === "simple" ? "Add Business Property" : "Capitalize Fixed Asset"}
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddAsset} className="mt-4 flex flex-col gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Asset Description / Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. MacBook Pro 16 M3 Max, Toyota Hilux GA-123-24"
                  value={assetName}
                  onChange={(e) => setAssetName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Asset Class (Debit) <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={selectedAssetCode}
                    onChange={(e) => setSelectedAssetCode(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  >
                    {assetAccounts.map((a) => (
                      <option key={a.id} value={a.account_code}>
                        {a.account_code} - {a.account_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Funding Source (Credit) <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={selectedFundingCode}
                    onChange={(e) => setSelectedFundingCode(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  >
                    {fundingAccounts.map((a) => (
                      <option key={a.id} value={a.account_code}>
                        {a.account_code} - {a.account_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Purchase Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={acquisitionDate}
                    onChange={(e) => setAcquisitionDate(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Purchase Cost (GH¢) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    placeholder="15000.00"
                    value={purchaseCost}
                    onChange={(e) => setPurchaseCost(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
                  />
                </div>
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
                  disabled={isSubmitting || !purchaseCost || parseFloat(purchaseCost) <= 0}
                  className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                  Capitalize Asset
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
