"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMode } from "@/contexts/ModeContext";
import apiClient from "@/lib/apiClient";

interface BackendAccount {
  id: string;
  account_code: string;
  account_name: string;
  simple_label?: string;
  category_code?: string;
  category_name?: string;
  normal_balance?: "DEBIT" | "CREDIT";
  is_active: boolean;
}

type AccountItem = { code: string; name: string; label: string; amount?: string; negative?: boolean };
type Section = {
  id: string;
  title: string;
  type: "neutral" | "owe";
  items: AccountItem[];
};

export default function ChartOfAccountsPage() {
  const { mode } = useMode();
  const [accounts, setAccounts] = useState<BackendAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAccounts = async (showLoading = false) => {
    if (showLoading) setIsLoading(true);
    try {
      const res = await apiClient.get<BackendAccount[]>("/api/v1/ledger/accounts/");
      setAccounts(Array.isArray(res.data) ? res.data : []);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load accounts.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let isCancelled = false;
    apiClient
      .get<BackendAccount[]>("/api/v1/ledger/accounts/")
      .then((res) => {
        if (!isCancelled) {
          setAccounts(Array.isArray(res.data) ? res.data : []);
          setError(null);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : "Failed to load accounts.";
          setError(msg);
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  // Group fetched accounts by 4-digit code hierarchy
  const assetItems: AccountItem[] = [];
  const liabilityItems: AccountItem[] = [];
  const equityItems: AccountItem[] = [];
  const incomeItems: AccountItem[] = [];
  const expenseItems: AccountItem[] = [];

  for (const acc of accounts) {
    const codeNum = parseInt(acc.account_code, 10);
    const item: AccountItem = {
      code: acc.account_code,
      name: acc.account_name,
      label: acc.simple_label || acc.account_name,
    };

    if (codeNum >= 1000 && codeNum < 2000) {
      assetItems.push(item);
    } else if (codeNum >= 2000 && codeNum < 3000) {
      liabilityItems.push(item);
    } else if (codeNum >= 3000 && codeNum < 4000) {
      equityItems.push(item);
    } else if (codeNum >= 4000 && codeNum < 5000) {
      incomeItems.push(item);
    } else if (codeNum >= 5000 && codeNum < 6000) {
      expenseItems.push(item);
    }
  }

  const sections: Section[] =
    mode === "simple"
      ? [
          { id: "own", title: "WHAT I OWN", type: "neutral", items: assetItems },
          { id: "owe", title: "WHAT I OWE", type: "owe", items: liabilityItems },
          { id: "share", title: "MY SHARE", type: "neutral", items: equityItems },
          { id: "income", title: "MONEY MADE", type: "neutral", items: incomeItems },
          { id: "expense", title: "MONEY SPENT", type: "owe", items: expenseItems },
        ]
      : [
          { id: "assets", title: "1000 — ASSETS", type: "neutral", items: assetItems },
          { id: "liabilities", title: "2000 — LIABILITIES", type: "owe", items: liabilityItems },
          { id: "equity", title: "3000 — EQUITY", type: "neutral", items: equityItems },
          { id: "income", title: "4000 — REVENUE & INCOME", type: "neutral", items: incomeItems },
          { id: "expense", title: "5000 — OPERATING EXPENSES", type: "owe", items: expenseItems },
        ];

  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
            {mode === "simple" ? "My Accounts" : "Chart of Accounts"}
          </h1>
          <p className="text-[#434655] text-base mt-1">
            {mode === "simple"
              ? "A simplified view of what you own, what you owe, and money moving through your business."
              : "Hierarchical general ledger account structure compliant with Ghanaian standard accounting."}
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-12 text-center text-[#434655]">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-[#2563eb] border-r-transparent mb-3" />
          <p className="text-sm font-medium">Loading Chart of Accounts from ledger...</p>
        </div>
      ) : error ? (
        <div className="bg-[#fef2f2] border border-[#f87171] rounded-xl p-6 text-center text-[#991b1b]">
          <p className="font-semibold text-base mb-1">Failed to load Chart of Accounts</p>
          <p className="text-sm mb-4">{error}</p>
          <button
            type="button"
            onClick={() => {
              fetchAccounts(true);
            }}
            className="bg-[#dc2626] hover:bg-[#b91c1c] text-white text-xs font-semibold px-4 py-2 rounded-md cursor-pointer"
          >
            Retry
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {sections.map((section) => (
            <div
              key={section.id}
              className="bg-white border border-[#c3c6d7] rounded-xl p-6 flex flex-col gap-4 shadow-xs"
            >
              <div className="flex items-center justify-between border-b border-[#e2e8f0] pb-2">
                <h2 className="text-xs font-bold tracking-wider text-[#475569] uppercase">
                  {section.title}
                </h2>
                <span className="text-xs font-semibold text-[#94a3b8]">
                  {section.items.length} accounts
                </span>
              </div>

              <div className="space-y-2">
                {section.items.length === 0 ? (
                  <p className="text-xs text-[#94a3b8] italic">No accounts mapped</p>
                ) : (
                  section.items.map((acc) => (
                    <div
                      key={acc.code}
                      className="flex items-center justify-between text-sm py-1.5 border-b border-[#f1f5f9] last:border-0"
                    >
                      <div className="flex items-baseline gap-2">
                        <span className="font-mono text-xs font-bold text-[#64748b]">
                          {acc.code}
                        </span>
                        <span className="font-medium text-[#1e293b]">
                          {mode === "simple" ? acc.label : acc.name}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <footer className="border-t border-[#c3c6d7] mt-4 py-6 flex items-center justify-between text-[12px] font-medium text-[#434655] tracking-[0.24px]">
        <p>© 2026 Mage Books. All rights reserved.</p>
        <div className="flex items-center gap-6">
          <Link href="/legal/privacy" className="hover:underline">Privacy Policy</Link>
          <Link href="/legal/terms" className="hover:underline">Terms of Service</Link>
          <Link href="/legal/support" className="hover:underline">Help Center</Link>
        </div>
      </footer>
    </div>
  );
}
