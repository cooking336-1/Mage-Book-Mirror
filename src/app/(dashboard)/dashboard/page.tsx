"use client";

import Image from "next/image";
import Link from "next/link";
import { useMode } from "@/contexts/ModeContext";

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
  amount,
  amountColor,
}: {
  icon: string;
  iconBg: string;
  title: string;
  time: string;
  amount: string;
  amountColor: string;
}) {
  return (
    <div className="flex items-center justify-between px-6 py-5 border-t border-[#c3c6d7] first:border-0">
      <div className="flex items-center gap-4">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
          style={{ backgroundColor: iconBg }}
        >
          <Image src={icon} alt="" width={22} height={16} />
        </div>
        <div>
          <p className="font-bold text-[16px] text-[#141b2b] leading-6">{title}</p>
          <p className="text-[12px] font-medium text-[#434655] tracking-[0.24px]">{time}</p>
        </div>
      </div>
      <p className={`font-bold text-[16px] whitespace-nowrap ${amountColor}`}>{amount}</p>
    </div>
  );
}

// ── Bar Chart (CSS-only) ──────────────────────────────────────────────────────
const CHART_BARS = [
  { month: "JUN", heightPx: 48, opacity: "bg-[rgba(0,74,198,0.2)]" },
  { month: "JUL", heightPx: 80, opacity: "bg-[rgba(0,74,198,0.3)]" },
  { month: "AUG", heightPx: 64, opacity: "bg-[rgba(0,74,198,0.2)]" },
  { month: "SEP", heightPx: 96, opacity: "bg-[rgba(0,74,198,0.4)]" },
  { month: "OCT", heightPx: 56, opacity: "bg-[rgba(0,74,198,0.2)]" },
  { month: "NOV", heightPx: 112, opacity: "bg-[rgba(0,74,198,0.5)]" },
  { month: "DEC", heightPx: 128, opacity: "bg-[#004ac6]" },
];

// ── Page ──────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const { mode } = useMode();

  const metrics =
    mode === "simple"
      ? [
          { label: "Money I Owe", value: "GH¢ 23,000.00", icon: "/assets/metric-payable.svg", iconW: 31, iconH: 39 },
          { label: "Money Owed to Me", value: "GH¢ 30,040.00", icon: "/assets/metric-receivable.svg", iconW: 31, iconH: 37 },
          { label: "Petty Cash", value: "GH¢ 10,340.00", icon: "/assets/metric-cash.svg", iconW: 34, iconH: 35 },
          { label: "Taxes Due", value: "GH¢ 15,300.50", icon: "/assets/metric-tax.svg", iconW: 29, iconH: 39 },
        ]
      : [
          { label: "Accounts Payable", value: "GH¢ 23,000.00", icon: "/assets/metric-payable.svg", iconW: 31, iconH: 39 },
          { label: "Accounts Receivable", value: "GH¢ 30,040.00", icon: "/assets/metric-receivable.svg", iconW: 31, iconH: 37 },
          { label: "Petty Cash", value: "GH¢ 10,340.00", icon: "/assets/metric-cash.svg", iconW: 34, iconH: 35 },
          { label: "Tax Liabilities", value: "GH¢ 15,300.50", icon: "/assets/metric-tax.svg", iconW: 29, iconH: 39 },
        ];

  const ctaLabel = mode === "simple" ? "Record Transaction" : "New Journal Entry";

  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      {/* Greeting + CTA */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[30px] font-bold text-[#141b2b] tracking-[-0.6px] leading-tight">
            Good morning, Ama
          </h1>
          <p className="text-[#434655] text-base mt-1">
            Here&apos;s what&apos;s happening as of 25th July, 2026
          </p>
        </div>
        <button
          type="button"
          className="flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-[#eeefff] font-bold text-base px-6 h-14 rounded-lg shadow-md transition-colors"
        >
          <Image src="/assets/btn-journal-entry.svg" alt="" width={16} height={20} />
          {ctaLabel}
        </button>
      </div>

      {/* Alert strip */}
      <div className="flex items-center gap-3 bg-[#f3f3fe] border border-[rgba(195,198,215,0.5)] rounded-lg px-4 py-2.5">
        <Image src="/assets/alert-info.svg" alt="" width={15} height={15} className="shrink-0" />
        <p className="text-sm text-[#191b23]">
          <span className="font-medium">3</span>
          <span className="font-normal text-[#434655]"> invoices pending GRA clearance · </span>
          <span className="font-medium">2</span>
          <span className="font-normal text-[#434655]"> drafts · </span>
          <span className="font-medium">1</span>
          <span className="font-normal text-[#434655]"> unresolved note</span>
        </p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-6">
        {metrics.map((m) => (
          <MetricCard key={m.label} label={m.label} value={m.value} icon={m.icon} iconW={m.iconW} iconH={m.iconH} />
        ))}
      </div>

      {/* Main section: Activity + Widgets */}
      <div className="grid grid-cols-12 gap-6">
        {/* Recent Activity */}
        <div className="col-span-8 bg-white border border-[#c3c6d7] rounded-xl shadow-[0px_1px_2px_rgba(0,0,0,0.05)] overflow-hidden">
          <div className="flex items-center justify-between px-6 py-5 border-b border-[#c3c6d7]">
            <p className="text-[16px] text-[#141b2b]">Recent Activity</p>
            <Link href="/dashboard/transactions" className="text-[14px] font-bold text-[#004ac6] hover:underline">
              View All
            </Link>
          </div>
          <div>
            <ActivityRow
              icon="/assets/activity-invoice.svg"
              iconBg="#f0fdf4"
              title="Invoice #402 paid by Kojo Enterprises"
              time="2 minutes ago"
              amount="+ GH¢ 4,200.00"
              amountColor="text-[#16a34a]"
            />
            <ActivityRow
              icon="/assets/activity-quote.svg"
              iconBg="#eff6ff"
              title="New Quote #882 sent to Tema Logistics Ltd"
              time="45 minutes ago"
              amount="GH¢ 12,500.00"
              amountColor="text-[#141b2b]"
            />
            <ActivityRow
              icon="/assets/activity-expense.svg"
              iconBg="#fef2f2"
              title="Payment for Office Rent"
              time="2 hours ago"
              amount="- GH¢ 8,000.00"
              amountColor="text-[#dc2626]"
            />
            <ActivityRow
              icon="/assets/activity-subscription.svg"
              iconBg="#f3f4f6"
              title="Internet Subscription for October"
              time="1 day ago"
              amount="- GH¢ 450.00"
              amountColor="text-[#dc2626]"
            />
            <ActivityRow
              icon="/assets/activity-salary.svg"
              iconBg="#f1f5f9"
              title="Salary payment for K. Mensah"
              time="2 days ago"
              amount="- GH¢ 3,200.00"
              amountColor="text-[#dc2626]"
            />
          </div>
        </div>

        {/* Sidebar widgets */}
        <div className="col-span-4 flex flex-col gap-6">
          {/* Cash Snapshot */}
          <div className="bg-white border border-[#c3c6d7] rounded-xl shadow-[0px_1px_1px_rgba(0,0,0,0.05)] p-6">
            <div className="flex items-start justify-between mb-1">
              <div>
                <p className="text-[14px] font-bold text-[#434655] uppercase tracking-[0.7px]">
                  Cash Snapshot
                </p>
                <p className="text-[10px] font-bold text-[#434655] uppercase mt-0.5">
                  Current Balance
                </p>
                <p className="font-black text-[20px] text-[#004ac6] mt-1">GH¢ 142,500.42</p>
                <div className="flex items-center gap-1 mt-1">
                  <Image src="/assets/chart-up-arrow.svg" alt="" width={13} height={8} />
                  <span className="text-[12px] font-bold text-[#16a34a] tracking-[0.24px]">
                    +12.4% vs last month
                  </span>
                </div>
              </div>
              <button type="button" className="p-1">
                <Image src="/assets/icon-dots.svg" alt="" width={4} height={16} />
              </button>
            </div>

            {/* Bar chart */}
            <div className="flex items-end gap-2 mt-6 h-36">
              {CHART_BARS.map(({ month, heightPx, opacity }) => (
                <div key={month} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className={`w-full rounded-t-[2px] ${opacity}`}
                    style={{ height: `${heightPx}px` }}
                  />
                  <span className="text-[10px] font-bold text-[#434655] uppercase">{month}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Help card */}
          <div className="bg-[#2563eb] rounded-xl shadow-[0px_10px_15px_-3px_rgba(0,0,0,0.1)] p-6 flex items-center gap-4">
            <div className="w-12 h-12 rounded-full border-2 border-[rgba(255,255,255,0.3)] flex items-center justify-center shrink-0">
              <Image src="/assets/help-headset.svg" alt="" width={18} height={21} />
            </div>
            <div className="flex-1">
              <p className="font-bold text-[20px] text-white leading-tight">Need help?</p>
              <p className="text-white opacity-90 text-[14px] mt-1 leading-5">
                Connect with a certified Mage Accountant.
              </p>
            </div>
            <Image src="/assets/icon-chevron-right-white.svg" alt="" width={7} height={12} className="shrink-0" />
          </div>
        </div>
      </div>
    </div>
  );
}
