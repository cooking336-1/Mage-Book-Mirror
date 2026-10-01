"use client";

import { useEffect, useState, useMemo } from "react";
import Image from "next/image";
import Link from "next/link";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import { RefreshCw, ArrowUpRight } from "lucide-react";

// ── Metric Card ───────────────────────────────────────────────────────────────
function MetricCard({
  label,
  value,
  icon,
  iconW,
  iconH,
}: {
  label: string;
  value: string;
  icon: string;
  iconW: number;
  iconH: number;
}) {
  return (
    <div className="bg-white border border-[#c3c6d7] rounded-xl shadow-[0px_1px_1px_rgba(0,0,0,0.05)] p-6 flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <p className="text-[#434655] text-sm font-semibold uppercase tracking-[0.35px] leading-tight">
          {label}
        </p>
        <Image src={icon} alt="" width={iconW} height={iconH} className="shrink-0" />
      </div>
      <p className="font-black text-[20px] text-[#141b2b] leading-tight">{value}</p>
    </div>
  );
}

// ── Activity Row ──────────────────────────────────────────────────────────────
function ActivityRow({
  icon,
  iconBg,
  title,
  time,
  detail,
}: {
  icon: string;
  iconBg: string;
  title: string;
  time: string;
  detail: string;
}) {
  return (
    <div className="flex items-center justify-between px-6 py-4 border-t border-[#c3c6d7] first:border-0 hover:bg-slate-50/50 transition-colors">
      <div className="flex items-center gap-4">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
          style={{ backgroundColor: iconBg }}
        >
          <Image src={icon} alt="" width={22} height={16} />
        </div>
        <div>
          <p className="font-bold text-[15px] text-[#141b2b] leading-tight">{title}</p>
          <p className="text-[12px] font-medium text-[#434655] tracking-[0.24px] mt-0.5">{time}</p>
        </div>
      </div>
      <p className="text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full border border-slate-200">
        {detail}
      </p>
    </div>
  );
}

// ── Formatters ────────────────────────────────────────────────────────────────
function formatGHS(amount: number): string {
  return new Intl.NumberFormat("en-GH", {
    style: "currency",
    currency: "GHS",
    minimumFractionDigits: 2,
  })
    .format(amount)
    .replace("GHS", "GH¢");
}

function getOrdinalSuffix(day: number): string {
  if (day > 3 && day < 21) return `${day}th`;
  switch (day % 10) {
    case 1:
      return `${day}st`;
    case 2:
      return `${day}nd`;
    case 3:
      return `${day}rd`;
    default:
      return `${day}th`;
  }
}

function formatTodayDate(): string {
  const d = new Date();
  const dayWithSuffix = getOrdinalSuffix(d.getDate());
  const month = d.toLocaleString("en-US", { month: "long" });
  const year = d.getFullYear();
  return `${dayWithSuffix} ${month}, ${year}`;
}

function getTimeGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function formatRelativeTime(dateStr: string): string {
  try {
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return "Just now";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 30) return `${diffDays}d ago`;
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return dateStr;
  }
}

interface AuditItem {
  id: string;
  action: string;
  user_email: string | null;
  entity_type: string;
  entity_id: string;
  created_at: string;
}

interface InvoiceItem {
  id: string;
  status: string;
  total_amount: string | number;
  balance_due: string | number;
}

interface TrialBalanceAccount {
  account_code: string;
  account_name: string;
  simple_label: string;
  category_name: string;
  net_balance: string;
  debit_balance: string;
  credit_balance: string;
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const { mode } = useMode();

  const [userName, setUserName] = useState("there");
  const [cashBalance, setCashBalance] = useState(0);
  const [accountsReceivable, setAccountsReceivable] = useState(0);
  const [accountsPayable, setAccountsPayable] = useState(0);
  const [taxLiabilities, setTaxLiabilities] = useState(0);

  const [pendingGraCount, setPendingGraCount] = useState(0);
  const [draftCount, setDraftCount] = useState(0);
  const [activities, setActivities] = useState<AuditItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let isCancelled = false;

    async function fetchDashboardData() {
      try {
        const [meRes, invoicesRes, tbRes, auditRes] = await Promise.allSettled([
          apiClient.get<{ first_name?: string; full_name?: string; email: string }>("/api/v1/auth/me/"),
          apiClient.get<InvoiceItem[] | { results: InvoiceItem[] }>("/api/v1/invoices/"),
          apiClient.get<{ rows?: TrialBalanceAccount[] }>("/api/v1/ledger/reports/trial-balance/?include_zero_balances=true"),
          apiClient.get<AuditItem[] | { results: AuditItem[] }>("/api/v1/audit/trail/"),
        ]);

        if (isCancelled) return;

        // 1. User Name
        if (meRes.status === "fulfilled" && meRes.value.data) {
          const user = meRes.value.data;
          const name = user.first_name || user.full_name || user.email.split("@")[0];
          if (name) setUserName(name);
        }

        // 2. Invoices metrics
        let totalArFromInvoices = 0;
        if (invoicesRes.status === "fulfilled" && invoicesRes.value.data) {
          const raw = invoicesRes.value.data;
          const invList = Array.isArray(raw) ? raw : raw.results || [];
          const pending = invList.filter((inv) => inv.status === "PENDING_GRA").length;
          const drafts = invList.filter((inv) => inv.status === "DRAFT").length;
          setPendingGraCount(pending);
          setDraftCount(drafts);

          // Calculate outstanding invoices for Accounts Receivable fallback
          totalArFromInvoices = invList
            .filter((inv) => inv.status === "ISSUED" || inv.status === "PENDING_GRA")
            .reduce((sum, inv) => sum + parseFloat(String(inv.balance_due || inv.total_amount || 0)), 0);
        }

        // 3. Trial Balance Accounts
        if (tbRes.status === "fulfilled" && tbRes.value.data?.rows) {
          const rows = tbRes.value.data.rows;

          let cashSum = 0;
          let arSum = 0;
          let apSum = 0;
          let taxSum = 0;

          rows.forEach((row) => {
            const code = row.account_code || "";
            const debit = parseFloat(row.debit_balance || "0");
            const credit = parseFloat(row.credit_balance || "0");
            const net = parseFloat(row.net_balance || "0");

            // Cash & Bank (Codes 1000 - 1099)
            if (code.startsWith("10")) {
              cashSum += net !== 0 ? net : debit - credit;
            }
            // Accounts Receivable (Code 1200)
            else if (code.startsWith("12")) {
              arSum += net !== 0 ? net : debit - credit;
            }
            // Accounts Payable (Code 2000)
            else if (code.startsWith("20")) {
              apSum += net !== 0 ? Math.abs(net) : credit - debit;
            }
            // Tax Liabilities (Code 2100)
            else if (code.startsWith("21")) {
              taxSum += net !== 0 ? Math.abs(net) : credit - debit;
            }
          });

          setCashBalance(cashSum);
          setAccountsReceivable(arSum > 0 ? arSum : totalArFromInvoices);
          setAccountsPayable(apSum);
          setTaxLiabilities(taxSum);
        } else if (totalArFromInvoices > 0) {
          setAccountsReceivable(totalArFromInvoices);
        }

        // 4. Audit Trail Activities
        if (auditRes.status === "fulfilled" && auditRes.value.data) {
          const raw = auditRes.value.data;
          const auditList = Array.isArray(raw) ? raw : raw.results || [];
          setActivities(auditList.slice(0, 5));
        }
      } catch (err) {
        console.error("Dashboard overview fetch error:", err);
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    fetchDashboardData();

    return () => {
      isCancelled = true;
    };
  }, [refreshKey]);

  const metrics = useMemo(() => {
    if (mode === "simple") {
      return [
        {
          label: "Money I Owe",
          value: formatGHS(accountsPayable),
          icon: "/assets/metric-payable.svg",
          iconW: 31,
          iconH: 39,
        },
        {
          label: "Money Owed to Me",
          value: formatGHS(accountsReceivable),
          icon: "/assets/metric-receivable.svg",
          iconW: 31,
          iconH: 37,
        },
        {
          label: "Petty Cash & Bank",
          value: formatGHS(cashBalance),
          icon: "/assets/metric-cash.svg",
          iconW: 34,
          iconH: 35,
        },
        {
          label: "Taxes Due",
          value: formatGHS(taxLiabilities),
          icon: "/assets/metric-tax.svg",
          iconW: 29,
          iconH: 39,
        },
      ];
    }

    return [
      {
        label: "Accounts Payable",
        value: formatGHS(accountsPayable),
        icon: "/assets/metric-payable.svg",
        iconW: 31,
        iconH: 39,
      },
      {
        label: "Accounts Receivable",
        value: formatGHS(accountsReceivable),
        icon: "/assets/metric-receivable.svg",
        iconW: 31,
        iconH: 37,
      },
      {
        label: "Cash & Cash Equivalents",
        value: formatGHS(cashBalance),
        icon: "/assets/metric-cash.svg",
        iconW: 34,
        iconH: 35,
      },
      {
        label: "Tax Liabilities",
        value: formatGHS(taxLiabilities),
        icon: "/assets/metric-tax.svg",
        iconW: 29,
        iconH: 39,
      },
    ];
  }, [mode, accountsPayable, accountsReceivable, cashBalance, taxLiabilities]);

  const ctaLabel = mode === "simple" ? "Record Transaction" : "New Journal Entry";

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-8">
      {/* Greeting + CTA */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-[30px] font-bold text-[#141b2b] tracking-[-0.6px] leading-tight">
            {getTimeGreeting()}, {userName}
          </h1>
          <p className="text-[#434655] text-base mt-1">
            Here&apos;s what&apos;s happening as of {formatTodayDate()}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setIsLoading(true);
              setRefreshKey((k) => k + 1);
            }}
            disabled={isLoading}
            className="p-3 text-slate-600 bg-white border border-[#c3c6d7] rounded-lg hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50"
            title="Refresh dashboard metrics"
          >
            <RefreshCw className={`w-5 h-5 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <Link
            href="/dashboard/transactions"
            className="flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-[#eeefff] font-bold text-base px-6 h-12 rounded-lg shadow-md transition-colors"
          >
            <Image src="/assets/btn-journal-entry.svg" alt="" width={16} height={20} />
            {ctaLabel}
          </Link>
        </div>
      </div>

      {/* Alert strip */}
      <div className="flex items-center gap-3 bg-[#f3f3fe] border border-[rgba(195,198,215,0.5)] rounded-lg px-4 py-3">
        <Image src="/assets/alert-info.svg" alt="" width={15} height={15} className="shrink-0" />
        <p className="text-sm text-[#191b23]">
          <span className="font-semibold text-blue-700">{pendingGraCount}</span>
          <span className="font-normal text-[#434655]"> invoices pending GRA clearance · </span>
          <span className="font-semibold text-slate-700">{draftCount}</span>
          <span className="font-normal text-[#434655]"> drafts · </span>
          <span className="font-semibold text-slate-700">{activities.length}</span>
          <span className="font-normal text-[#434655]"> audit records logged</span>
        </p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {metrics.map((m) => (
          <MetricCard
            key={m.label}
            label={m.label}
            value={isLoading ? "Loading..." : m.value}
            icon={m.icon}
            iconW={m.iconW}
            iconH={m.iconH}
          />
        ))}
      </div>

      {/* Main section: Activity + Widgets */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Recent Activity */}
        <div className="lg:col-span-8 bg-white border border-[#c3c6d7] rounded-xl shadow-[0px_1px_2px_rgba(0,0,0,0.05)] overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-[#c3c6d7] bg-[#f8fafc]">
            <p className="text-[16px] font-bold text-[#141b2b]">Recent Activity</p>
            <Link
              href="/dashboard/audit"
              className="text-[14px] font-bold text-[#004ac6] hover:underline inline-flex items-center gap-1"
            >
              View All Audit Records
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div>
            {activities.length === 0 ? (
              <div className="p-12 text-center text-slate-500 flex flex-col items-center justify-center gap-2">
                <Image src="/assets/alert-info.svg" alt="" width={24} height={24} className="opacity-40" />
                <p className="font-medium text-slate-700">No activity logged yet</p>
                <p className="text-xs text-slate-400">
                  Operations like invoice creation, journal entries, and approvals will show here.
                </p>
              </div>
            ) : (
              activities.map((act) => (
                <ActivityRow
                  key={act.id}
                  icon="/assets/activity-invoice.svg"
                  iconBg="#eff6ff"
                  title={act.action.replace(/_/g, " ")}
                  time={formatRelativeTime(act.created_at)}
                  detail={act.entity_type}
                />
              ))
            )}
          </div>
        </div>

        {/* Sidebar widgets */}
        <div className="lg:col-span-4 flex flex-col gap-6">
          {/* Cash Snapshot */}
          <div className="bg-white border border-[#c3c6d7] rounded-xl shadow-[0px_1px_1px_rgba(0,0,0,0.05)] p-6">
            <div className="flex items-start justify-between mb-1">
              <div>
                <p className="text-[14px] font-bold text-[#434655] uppercase tracking-[0.7px]">
                  Cash Snapshot
                </p>
                <p className="text-[10px] font-bold text-[#434655] uppercase mt-0.5">
                  Available Liquidity
                </p>
                <p className="font-black text-[22px] text-[#004ac6] mt-1">
                  {isLoading ? "Loading..." : formatGHS(cashBalance)}
                </p>
                <div className="flex items-center gap-1 mt-1">
                  <Image src="/assets/chart-up-arrow.svg" alt="" width={13} height={8} />
                  <span className="text-[12px] font-bold text-[#16a34a] tracking-[0.24px]">
                    Real-time general ledger balance
                  </span>
                </div>
              </div>
            </div>

            {/* Account Quick Links */}
            <div className="mt-5 pt-4 border-t border-slate-100 flex flex-col gap-2.5">
              <Link
                href="/dashboard/accounts-receivable"
                className="flex items-center justify-between text-xs text-slate-600 hover:text-blue-600 transition-colors py-1"
              >
                <span>Accounts Receivable</span>
                <span className="font-semibold text-slate-800">{formatGHS(accountsReceivable)}</span>
              </Link>
              <Link
                href="/dashboard/chart-of-accounts"
                className="flex items-center justify-between text-xs text-slate-600 hover:text-blue-600 transition-colors py-1"
              >
                <span>Chart of Accounts</span>
                <span className="font-semibold text-blue-600">Inspect &rarr;</span>
              </Link>
            </div>
          </div>

          {/* Help card */}
          <Link
            href="/dashboard/hire-expert"
            className="bg-[#2563eb] hover:bg-[#1d4ed8] transition-colors rounded-xl shadow-[0px_10px_15px_-3px_rgba(0,0,0,0.1)] p-6 flex items-center gap-4 block cursor-pointer"
          >
            <div className="w-12 h-12 rounded-full border-2 border-[rgba(255,255,255,0.3)] flex items-center justify-center shrink-0">
              <Image src="/assets/help-headset.svg" alt="" width={18} height={21} />
            </div>
            <div className="flex-1">
              <p className="font-bold text-[18px] text-white leading-tight">Need help?</p>
              <p className="text-white opacity-90 text-[13px] mt-1 leading-snug">
                Connect with a certified Mage Accountant for Ghana compliance.
              </p>
            </div>
            <Image
              src="/assets/icon-chevron-right-white.svg"
              alt=""
              width={7}
              height={12}
              className="shrink-0"
            />
          </Link>
        </div>
      </div>
    </div>
  );
}
