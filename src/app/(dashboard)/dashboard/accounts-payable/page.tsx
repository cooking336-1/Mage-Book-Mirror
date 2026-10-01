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
  Building2,
  Check,
} from "lucide-react";

interface AccountItem {
  id: string;
  account_code: string;
  account_name: string;
  simple_label: string;
  category_name: string;
}

interface ContactItem {
  id: string;
  name: string;
  contact_type: string;
  email?: string;
  phone_number?: string;
}

interface LedgerEntryLine {
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

export default function AccountsPayablePage() {
  const { mode } = useMode();

  const [apEntries, setApEntries] = useState<LedgerEntryLine[]>([]);
  const [expenseAccounts, setExpenseAccounts] = useState<AccountItem[]>([]);
  const [apAccount, setApAccount] = useState<AccountItem | null>(null);
  const [contacts, setContacts] = useState<ContactItem[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  // New Bill Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [supplierName, setSupplierName] = useState("");
  const [billReference, setBillReference] = useState("");
  const [billDate, setBillDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [dueDate, setDueDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().split("T")[0];
  });
  const [selectedExpenseCode, setSelectedExpenseCode] = useState("");
  const [billAmount, setBillAmount] = useState("");
  const [whtRate, setWhtRate] = useState<number>(0); // 0, 0.03, 0.05, 0.075
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadData() {
      try {
        const [accRes, contactsRes] = await Promise.allSettled([
          apiClient.get<AccountItem[]>("/api/v1/ledger/accounts/"),
          apiClient.get<ContactItem[] | { results: ContactItem[] }>("/api/v1/invoicing/contacts/"),
        ]);

        if (isCancelled) return;

        let foundAp: AccountItem | null = null;
        if (accRes.status === "fulfilled" && accRes.value.data) {
          const allAcc = accRes.value.data;
          foundAp =
            allAcc.find((a) => a.account_code === "2010") ||
            allAcc.find((a) => a.account_code.startsWith("20")) ||
            null;
          setApAccount(foundAp);

          const expenses = allAcc.filter(
            (a) => a.account_code.startsWith("5") || a.category_name?.toUpperCase() === "EXPENSE"
          );
          setExpenseAccounts(expenses);
          if (expenses.length > 0 && !selectedExpenseCode) {
            setSelectedExpenseCode(expenses[0].account_code);
          }
        }

        if (contactsRes.status === "fulfilled" && contactsRes.value.data) {
          const raw = contactsRes.value.data;
          const list = Array.isArray(raw) ? raw : raw.results || [];
          setContacts(list);
        }

        if (foundAp) {
          const entriesRes = await apiClient.get<LedgerEntryLine[]>(
            `/api/v1/ledger/accounts/${foundAp.id}/entries/`
          );
          if (!isCancelled) {
            setApEntries(entriesRes.data);
          }
        }

        if (!isCancelled) {
          setError(null);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
          setError(resp?.detail || "Failed to load accounts payable records.");
          setIsLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [refreshKey, selectedExpenseCode]);

  // Compute live KPIs
  const { totalOutstanding, dueThisMonth } = useMemo(() => {
    let outstanding = 0;
    let thisMonth = 0;
    const now = new Date();

    apEntries.forEach((e) => {
      const cred = parseFloat(String(e.credit_amount || 0));
      const deb = parseFloat(String(e.debit_amount || 0));
      const netCredit = cred - deb;
      if (netCredit > 0) {
        outstanding += netCredit;

        const entryDate = new Date(e.entry_date);
        if (
          entryDate.getMonth() === now.getMonth() &&
          entryDate.getFullYear() === now.getFullYear()
        ) {
          thisMonth += netCredit;
        }
      }
    });

    return { totalOutstanding: outstanding, dueThisMonth: thisMonth };
  }, [apEntries]);

  // Handle Bill Submission via Balanced Double-Entry Journal
  const handleCreateBill = async (e: React.FormEvent) => {
    e.preventDefault();
    const gross = parseFloat(billAmount);
    if (!gross || gross <= 0) {
      setError("Please enter a valid bill amount.");
      return;
    }

    if (!selectedExpenseCode || !apAccount) {
      setError("Please select a valid expense category and ensure AP account is mapped.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const whtAmount = gross * whtRate;
    const netPayable = gross - whtAmount;
    const memo = `Bill [${billReference || "INV"}] from ${supplierName || "Supplier"}`;

    const lines: Array<{
      account: string;
      description: string;
      debit_amount: number;
      credit_amount: number;
    }> = [
      {
        account: selectedExpenseCode,
        description: memo,
        debit_amount: gross,
        credit_amount: 0,
      },
      {
        account: apAccount.account_code,
        description: `${memo} (Due: ${dueDate})`,
        debit_amount: 0,
        credit_amount: netPayable,
      },
    ];

    if (whtAmount > 0) {
      lines.push({
        account: "2130", // Withholding Tax Payable
        description: `WHT ${(whtRate * 100).toFixed(1)}% on ${memo}`,
        debit_amount: 0,
        credit_amount: whtAmount,
      });
    }

    try {
      await apiClient.post("/api/v1/ledger/journal-entries/", {
        entry_date: billDate,
        narration: memo,
        lines,
      });

      setSuccessMsg("Supplier bill recorded and posted to Accounts Payable!");
      setIsModalOpen(false);
      setSupplierName("");
      setBillReference("");
      setBillAmount("");
      setWhtRate(0);
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to record supplier bill.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredEntries = useMemo(() => {
    return apEntries.filter((e) => {
      const q = searchTerm.toLowerCase();
      return (
        e.entry_number.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q)
      );
    });
  }, [apEntries, searchTerm]);

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              {mode === "simple" ? "Money I Owe" : "Accounts Payable"}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1">
              <Check className="w-3.5 h-3.5" />
              General Ledger Linked
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            {mode === "simple"
              ? "Track bills and supplier payments due, with automatic withholding tax (WHT) calculations."
              : "Outstanding vendor liabilities, expense allocations, and Ghana Act 896 WHT withholdings."}
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
            title="Refresh payables"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            {mode === "simple" ? "+ Add Bill to Pay" : "+ New Supplier Bill"}
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
            {mode === "simple" ? "Total Owed" : "Total Outstanding"}
          </p>
          <p className="text-2xl font-bold text-[#141b2b] mt-1 font-mono">
            {formatGHS(totalOutstanding)}
          </p>
          <p className="text-xs text-[#64748b] mt-1">
            {apEntries.length} recorded bill entries
          </p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <p className="text-xs font-semibold text-[#434655] uppercase tracking-wide">
            {mode === "simple" ? "Due This Month" : "Current Month Postings"}
          </p>
          <p className="text-2xl font-bold text-amber-700 mt-1 font-mono">
            {formatGHS(dueThisMonth)}
          </p>
          <p className="text-xs text-[#64748b] mt-1">Upcoming supplier settlements</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <p className="text-xs font-semibold text-[#434655] uppercase tracking-wide">
            Mapped AP Account
          </p>
          <p className="text-lg font-bold text-blue-700 mt-1">
            {apAccount ? `${apAccount.account_code} - ${apAccount.account_name}` : "2010 - Accounts Payable"}
          </p>
          <p className="text-xs text-[#64748b] mt-1">Statutory General Ledger liability</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by entry # or memo..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border border-[#c3c6d7] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-slate-800 shadow-sm"
          />
        </div>
        <p className="text-xs text-slate-500 self-end sm:self-center">
          Showing <span className="font-semibold text-slate-700">{filteredEntries.length}</span> of{" "}
          <span className="font-semibold text-slate-700">{apEntries.length}</span> bills
        </p>
      </div>

      {/* Bills / AP Table */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
          <p className="text-sm font-bold text-[#141b2b]">Supplier Bills &amp; Liabilities</p>
          <span className="text-xs text-slate-500">Sub-ledger entry register</span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Loading supplier bills...</p>
          </div>
        ) : filteredEntries.length === 0 ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <CreditCard className="w-12 h-12 text-slate-300" />
            <p className="font-bold text-slate-700 text-lg">No outstanding bills</p>
            <p className="text-sm text-slate-400 max-w-sm">
              {searchTerm
                ? "No bills matched your search query."
                : "Bills received from suppliers and vendors will appear here."}
            </p>
            {!searchTerm && (
              <button
                type="button"
                onClick={() => setIsModalOpen(true)}
                className="mt-2 text-sm font-semibold text-blue-600 hover:underline"
              >
                + Record your first supplier bill
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
                  <th className="py-3 px-6">Supplier / Description</th>
                  <th className="py-3 px-6 text-right">Debit (Payment)</th>
                  <th className="py-3 px-6 text-right">Credit (Bill Amount)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-sm">
                {filteredEntries.map((e) => (
                  <tr key={e.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-4 px-6 font-mono font-bold text-blue-700">
                      {e.entry_number}
                    </td>

                    <td className="py-4 px-6 text-slate-600">
                      {new Date(e.entry_date).toLocaleDateString()}
                    </td>

                    <td className="py-4 px-6 font-medium text-slate-900">
                      {e.description || "Vendor liability"}
                    </td>

                    <td className="py-4 px-6 text-right font-mono text-emerald-700">
                      {parseFloat(String(e.debit_amount)) > 0
                        ? formatGHS(parseFloat(String(e.debit_amount)))
                        : "—"}
                    </td>

                    <td className="py-4 px-6 text-right font-mono font-bold text-slate-900">
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

      {/* Add Bill Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-blue-600" />
                <h3 className="text-lg font-bold text-slate-900">
                  {mode === "simple" ? "Add Bill to Pay" : "Record Supplier Bill"}
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateBill} className="mt-4 flex flex-col gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Supplier / Vendor Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  list="vendor-options"
                  placeholder="e.g. Accra Power Co or Stationery Supplies Ltd"
                  value={supplierName}
                  onChange={(e) => setSupplierName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                />
                <datalist id="vendor-options">
                  {contacts.map((c) => (
                    <option key={c.id} value={c.name} />
                  ))}
                </datalist>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Bill / Reference #
                  </label>
                  <input
                    type="text"
                    placeholder="INV-9923"
                    value={billReference}
                    onChange={(e) => setBillReference(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Expense Category <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={selectedExpenseCode}
                    onChange={(e) => setSelectedExpenseCode(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  >
                    {expenseAccounts.map((a) => (
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
                    Bill Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={billDate}
                    onChange={(e) => setBillDate(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Due Date
                  </label>
                  <input
                    type="date"
                    value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Gross Bill Amount (GH¢) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    placeholder="2500.00"
                    value={billAmount}
                    onChange={(e) => setBillAmount(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Ghana Withholding Tax (WHT)
                  </label>
                  <select
                    value={whtRate}
                    onChange={(e) => setWhtRate(parseFloat(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  >
                    <option value={0}>No WHT (0%)</option>
                    <option value={0.03}>3% WHT (Supply of Goods)</option>
                    <option value={0.05}>5% WHT (General Services)</option>
                    <option value={0.075}>7.5% WHT (Technical &amp; Consulting)</option>
                  </select>
                </div>
              </div>

              {/* Live Preview */}
              {parseFloat(billAmount) > 0 && (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs flex flex-col gap-1">
                  <div className="flex justify-between text-slate-600">
                    <span>Gross Expense:</span>
                    <span className="font-mono">{formatGHS(parseFloat(billAmount))}</span>
                  </div>
                  {whtRate > 0 && (
                    <div className="flex justify-between text-amber-700">
                      <span>WHT Withheld ({(whtRate * 100).toFixed(1)}%):</span>
                      <span className="font-mono">
                        -{formatGHS(parseFloat(billAmount) * whtRate)}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between font-bold text-slate-900 border-t border-slate-200 pt-1 mt-1">
                    <span>Net Payable to Vendor:</span>
                    <span className="font-mono">
                      {formatGHS(parseFloat(billAmount) * (1 - whtRate))}
                    </span>
                  </div>
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
                  disabled={isSubmitting || !billAmount || parseFloat(billAmount) <= 0}
                  className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                  Save &amp; Post Bill
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
