"use client";

import { useEffect, useState, useMemo } from "react";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  Package,
  Plus,
  RefreshCw,
  Search,
  AlertCircle,
  CheckCircle,
  X,
  Boxes,
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

export default function InventoryPage() {
  const { mode } = useMode();

  const [inventoryAccounts, setInventoryAccounts] = useState<AccountItem[]>([]);
  const [fundingAccounts, setFundingAccounts] = useState<AccountItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  // New Stock / Product Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [productName, setProductName] = useState("");
  const [skuCode, setSkuCode] = useState("");
  const [selectedInvCode, setSelectedInvCode] = useState("");
  const [selectedFundingCode, setSelectedFundingCode] = useState("");
  const [stockQuantity, setStockQuantity] = useState("1");
  const [unitCost, setUnitCost] = useState("");
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

        if (!isCancelled) {
          const balanceMap = new Map<string, number>();
          if (tbRes.data?.rows) {
            tbRes.data.rows.forEach((r) => {
              const deb = parseFloat(r.debit_balance || "0");
              const net = parseFloat(r.net_balance || "0");
              balanceMap.set(r.account_code, net > 0 ? net : deb);
            });
          }

          const all = accRes.data;

          // Inventory Accounts: codes 1300 to 1399
          const invList = all
            .filter(
              (a) =>
                a.account_code.startsWith("13") &&
                a.category_name?.toUpperCase() === "ASSET"
            )
            .map((a) => ({
              ...a,
              current_balance: balanceMap.get(a.account_code) || 0,
            }));

          // Fallback if no specific 13xx accounts, include general asset inventory
          const finalInv =
            invList.length > 0
              ? invList
              : all
                  .filter((a) => a.account_code.startsWith("1"))
                  .map((a) => ({ ...a, current_balance: balanceMap.get(a.account_code) || 0 }));

          const funding = all.filter(
            (a) => a.account_code.startsWith("10") || a.account_code.startsWith("20")
          );

          setInventoryAccounts(finalInv);
          setFundingAccounts(funding);

          if (finalInv.length > 0 && !selectedInvCode) {
            setSelectedInvCode(finalInv[0].account_code);
          }
          if (funding.length > 0 && !selectedFundingCode) {
            setSelectedFundingCode(funding[0].account_code);
          }

          setError(null);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
          setError(resp?.detail || "Failed to load inventory valuation.");
          setIsLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [refreshKey, selectedInvCode, selectedFundingCode]);

  const totalInventoryValuation = useMemo(() => {
    return inventoryAccounts.reduce((sum, a) => sum + (a.current_balance || 0), 0);
  }, [inventoryAccounts]);

  const totalCostCalculation = useMemo(() => {
    const qty = parseFloat(stockQuantity) || 0;
    const cost = parseFloat(unitCost) || 0;
    return qty * cost;
  }, [stockQuantity, unitCost]);

  // Handle Inventory Restock Submission
  const handleAddProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (totalCostCalculation <= 0) {
      setError("Please specify a valid quantity and unit cost.");
      return;
    }

    if (!selectedInvCode || !selectedFundingCode) {
      setError("Please select both an inventory account and a funding account.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const memo = `Inventory Restock: [${skuCode || "SKU"}] ${productName.trim()} (${stockQuantity} units)`;

    try {
      await apiClient.post("/api/v1/ledger/journal-entries/", {
        entry_date: new Date().toISOString().split("T")[0],
        narration: memo,
        lines: [
          {
            account: selectedInvCode,
            description: memo,
            debit_amount: totalCostCalculation,
            credit_amount: 0,
          },
          {
            account: selectedFundingCode,
            description: `Payment for stock: ${productName.trim()}`,
            debit_amount: 0,
            credit_amount: totalCostCalculation,
          },
        ],
      });

      setSuccessMsg(`Product "${productName}" stock initialized in General Ledger.`);
      setIsModalOpen(false);
      setProductName("");
      setSkuCode("");
      setStockQuantity("1");
      setUnitCost("");
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to initialize inventory stock.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredItems = useMemo(() => {
    return inventoryAccounts.filter((a) => {
      const q = searchTerm.toLowerCase();
      return (
        a.account_code.toLowerCase().includes(q) ||
        a.account_name.toLowerCase().includes(q) ||
        (a.simple_label && a.simple_label.toLowerCase().includes(q))
      );
    });
  }, [inventoryAccounts, searchTerm]);

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              {mode === "simple" ? "Products & Stock" : "Inventory Management"}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
              <Check className="w-3.5 h-3.5" />
              General Ledger Linked
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            {mode === "simple"
              ? "Track products you sell, stock valuations, and purchase costs."
              : "Perpetual inventory asset valuations, COGS allocation, and stock control."}
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
            title="Refresh inventory"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            + Add Product / Restock
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
            Total Inventory Valuation
          </p>
          <p className="text-2xl font-bold text-emerald-700 mt-1 font-mono">
            {formatGHS(totalInventoryValuation)}
          </p>
          <p className="text-xs text-[#64748b] mt-1">Real-time asset balance in GL</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <p className="text-xs font-semibold text-[#434655] uppercase tracking-wide">
            Active Stock Categories
          </p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{inventoryAccounts.length}</p>
          <p className="text-xs text-[#64748b] mt-1">Tracked inventory classifications</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <p className="text-xs font-semibold text-[#434655] uppercase tracking-wide">
            Valuation Method
          </p>
          <p className="text-lg font-bold text-blue-700 mt-1">FIFO / Weighted Average</p>
          <p className="text-xs text-[#64748b] mt-1">Automatic COGS relief upon invoice issue</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search product code or name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border border-[#c3c6d7] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-slate-800 shadow-sm"
          />
        </div>
        <p className="text-xs text-slate-500 self-end sm:self-center">
          Showing <span className="font-semibold text-slate-700">{filteredItems.length}</span> of{" "}
          <span className="font-semibold text-slate-700">{inventoryAccounts.length}</span> categories
        </p>
      </div>

      {/* Inventory Table */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
          <p className="text-sm font-bold text-[#141b2b]">Inventory Asset Classifications</p>
          <span className="text-xs text-slate-500">GL asset balances</span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Loading inventory valuations...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <Boxes className="w-12 h-12 text-slate-300" />
            <p className="font-bold text-slate-700 text-lg">No inventory items found</p>
            <p className="text-sm text-slate-400 max-w-sm">
              {searchTerm
                ? "No products matched your search query."
                : "Add products or stock to track your business inventory."}
            </p>
            {!searchTerm && (
              <button
                type="button"
                onClick={() => setIsModalOpen(true)}
                className="mt-2 text-sm font-semibold text-blue-600 hover:underline"
              >
                + Restock first inventory product
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-6">Account Code</th>
                  <th className="py-3 px-6">Classification</th>
                  <th className="py-3 px-6">Asset Category</th>
                  <th className="py-3 px-6 text-right">Current Valuation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-sm">
                {filteredItems.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-4 px-6 font-mono font-bold text-blue-700">
                      {item.account_code}
                    </td>

                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-50 text-emerald-700">
                          <Package className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="font-bold text-slate-900 leading-tight">
                            {mode === "simple" && item.simple_label
                              ? item.simple_label
                              : item.account_name}
                          </p>
                          {mode === "simple" && item.simple_label && (
                            <p className="text-xs text-slate-400 mt-0.5">{item.account_name}</p>
                          )}
                        </div>
                      </div>
                    </td>

                    <td className="py-4 px-6">
                      <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                        Current Assets (Inventory)
                      </span>
                    </td>

                    <td className="py-4 px-6 text-right font-mono font-bold text-emerald-700">
                      {formatGHS(item.current_balance || 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Product / Restock Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Package className="w-5 h-5 text-blue-600" />
                <h3 className="text-lg font-bold text-slate-900">
                  {mode === "simple" ? "Add Product / Restock" : "Record Inventory Stock Acquisition"}
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddProduct} className="mt-4 flex flex-col gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Product / Item Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Royal Aroma Basmati Rice 25kg"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    SKU / Product Code
                  </label>
                  <input
                    type="text"
                    placeholder="SKU-RICE-25KG"
                    value={skuCode}
                    onChange={(e) => setSkuCode(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Inventory Account (Debit) <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={selectedInvCode}
                    onChange={(e) => setSelectedInvCode(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  >
                    {inventoryAccounts.map((a) => (
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
                    Units / Quantity <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    step="1"
                    min="1"
                    required
                    value={stockQuantity}
                    onChange={(e) => setStockQuantity(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Unit Cost (GH¢) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    placeholder="120.00"
                    value={unitCost}
                    onChange={(e) => setUnitCost(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
                  />
                </div>
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

              {totalCostCalculation > 0 && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs flex justify-between items-center text-emerald-900 font-semibold">
                  <span>Total Capitalized Inventory Cost:</span>
                  <span className="font-mono text-base font-bold">
                    {formatGHS(totalCostCalculation)}
                  </span>
                </div>
              )}

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
                  disabled={isSubmitting || totalCostCalculation <= 0}
                  className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                  Record Inventory
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
