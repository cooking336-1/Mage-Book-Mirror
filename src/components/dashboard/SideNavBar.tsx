"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useMode, type AppMode } from "@/contexts/ModeContext";

type NavItem = {
  href: string;
  label: string;
  icon: string;
  w: number;
  h: number;
};

const SIMPLE_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: "/assets/nav-dashboard.svg", w: 20, h: 20 },
  { href: "/dashboard/transactions", label: "All Transactions", icon: "/assets/nav-transactions.svg", w: 18, h: 16 },
  { href: "/dashboard/chart-of-accounts", label: "My Categories", icon: "/assets/nav-chart-accounts.svg", w: 19, h: 20 },
  { href: "/dashboard/receipts", label: "Receipts", icon: "/assets/nav-receipts.svg", w: 18, h: 20 },
  { href: "/dashboard/invoices", label: "Invoices", icon: "/assets/activity-invoice.svg", w: 20, h: 20 },
  { href: "/dashboard/payments", label: "Payments", icon: "/assets/activity-salary.svg", w: 22, h: 16 },
  { href: "/dashboard/accounts-receivable", label: "Money Owed to Me", icon: "/assets/nav-accounts-receivable.svg", w: 19, h: 18 },
  { href: "/dashboard/accounts-payable", label: "Money I Owe", icon: "/assets/nav-accounts-payable.svg", w: 19, h: 21 },
  { href: "/dashboard/reports", label: "Reports", icon: "/assets/nav-reports.svg", w: 18, h: 18 },
  { href: "/dashboard/contacts", label: "Customers & Suppliers", icon: "/assets/nav-contacts.svg", w: 18, h: 18 },
  { href: "/dashboard/payroll", label: "Staff Pay", icon: "/assets/nav-payroll.svg", w: 21, h: 21 },
  { href: "/dashboard/fixed-assets", label: "Equipment & Property", icon: "/assets/nav-fixed-assets.svg", w: 20, h: 20 },
  { href: "/dashboard/inventory", label: "Inventory", icon: "/assets/nav-inventory.svg", w: 20, h: 20 },
  { href: "/dashboard/users", label: "Users & Access", icon: "/assets/nav-users.svg", w: 20, h: 16 },
  { href: "/dashboard/hire-expert", label: "Hire An Expert", icon: "/assets/nav-hire-expert.svg", w: 19, h: 20 },
  { href: "/dashboard/audit", label: "Activity Log", icon: "/assets/nav-audit.svg", w: 19, h: 16 },
  { href: "/dashboard/security", label: "Security Log", icon: "/assets/nav-security.svg", w: 19, h: 19 },
  { href: "/dashboard/period-rectification", label: "Fix a Past Mistake", icon: "/assets/nav-period-rectification.svg", w: 19, h: 19 },
  { href: "/dashboard/setup", label: "Setup", icon: "/assets/nav-setup.svg", w: 20, h: 20 },
];

const FULL_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: "/assets/nav-dashboard.svg", w: 20, h: 20 },
  { href: "/dashboard/transactions", label: "Transaction Entries", icon: "/assets/nav-transactions.svg", w: 18, h: 16 },
  { href: "/dashboard/chart-of-accounts", label: "Chart of Accounts", icon: "/assets/nav-chart-accounts.svg", w: 19, h: 20 },
  { href: "/dashboard/ledgers", label: "Ledgers", icon: "/assets/nav-ledgers.svg", w: 24, h: 24 },
  { href: "/dashboard/receipts", label: "Receipts", icon: "/assets/nav-receipts.svg", w: 18, h: 20 },
  { href: "/dashboard/invoices", label: "Tax Invoices", icon: "/assets/activity-invoice.svg", w: 20, h: 20 },
  { href: "/dashboard/payments", label: "Payments", icon: "/assets/activity-salary.svg", w: 22, h: 16 },
  { href: "/dashboard/accounts-receivable", label: "Accounts Receivable", icon: "/assets/nav-accounts-receivable.svg", w: 19, h: 18 },
  { href: "/dashboard/accounts-payable", label: "Accounts Payable", icon: "/assets/nav-accounts-payable.svg", w: 19, h: 21 },
  { href: "/dashboard/reports", label: "Reports", icon: "/assets/nav-reports.svg", w: 18, h: 18 },
  { href: "/dashboard/contacts", label: "Customers & Suppliers", icon: "/assets/nav-contacts.svg", w: 18, h: 18 },
  { href: "/dashboard/payroll", label: "Payroll", icon: "/assets/nav-payroll.svg", w: 21, h: 21 },
  { href: "/dashboard/fixed-assets", label: "Fixed Asset Register", icon: "/assets/nav-fixed-assets.svg", w: 20, h: 20 },
  { href: "/dashboard/inventory", label: "Inventory Management", icon: "/assets/nav-inventory.svg", w: 20, h: 20 },
  { href: "/dashboard/users", label: "Users & Access", icon: "/assets/nav-users.svg", w: 20, h: 16 },
  { href: "/dashboard/hire-expert", label: "Hire An Expert", icon: "/assets/nav-hire-expert.svg", w: 19, h: 20 },
  { href: "/dashboard/audit", label: "Audit Trail", icon: "/assets/nav-audit.svg", w: 19, h: 16 },
  { href: "/dashboard/security", label: "Security Log", icon: "/assets/nav-security.svg", w: 19, h: 19 },
  { href: "/dashboard/period-rectification", label: "Prior Period Rectification", icon: "/assets/nav-period-rectification.svg", w: 19, h: 19 },
  { href: "/dashboard/setup", label: "Setup", icon: "/assets/nav-setup.svg", w: 20, h: 20 },
];

function ModeToggle({ mode, setMode }: { mode: AppMode; setMode: (m: AppMode) => void }) {
  return (
    <div className="shrink-0 px-[17px] pt-2 pb-1">
      <div className="flex rounded-lg bg-[#f1f3ff] p-1 gap-1">
        <button
          type="button"
          onClick={() => setMode("simple")}
          className={`flex-1 text-[11px] font-semibold py-1.5 rounded-md transition-colors ${
            mode === "simple"
              ? "bg-white text-[#2563eb] shadow-sm"
              : "text-[#434655] hover:text-[#141b2b]"
          }`}
        >
          Simple
        </button>
        <button
          type="button"
          onClick={() => setMode("full")}
          className={`flex-1 text-[11px] font-semibold py-1.5 rounded-md transition-colors ${
            mode === "full"
              ? "bg-white text-[#2563eb] shadow-sm"
              : "text-[#434655] hover:text-[#141b2b]"
          }`}
        >
          Accounting
        </button>
      </div>
    </div>
  );
}

export default function SideNavBar() {
  const pathname = usePathname();
  const { mode, setMode } = useMode();

  const items = mode === "simple" ? SIMPLE_NAV : FULL_NAV;

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-white border-r border-[#c3c6d7] flex flex-col z-30">
      {/* Logo */}
      <div className="h-[88px] px-6 flex items-center shrink-0">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="bg-[#2563eb] rounded-lg w-10 h-10 flex items-center justify-center shrink-0">
            <Image src="/assets/sidebar-logo.svg" alt="Mage Books" width={24} height={24} />
          </div>
          <div>
            <p className="text-[#1e3a8a] font-bold text-[18px] leading-tight">Mage Books</p>
            <p className="text-[#94a3b8] text-[10px] font-bold tracking-[1px] uppercase">SAAS ACCOUNTING</p>
          </div>
        </Link>
      </div>

      {/* Nav list */}
      <nav className="flex-1 overflow-y-auto px-[17px] py-2">
        <ul className="space-y-0.5">
          {items.map(({ href, label, icon, w, h }) => {
            const active = pathname === href;
            return (
              <li key={href}>
                <Link
                  href={href}
                  className={`flex items-center gap-3 h-10 px-3 rounded-lg transition-colors ${
                    active
                      ? "bg-[#dbeafe] border-r-4 border-[#2563eb] text-[#1e40af] font-semibold"
                      : "text-[#434655] font-semibold hover:bg-[#f1f5f9]"
                  }`}
                >
                  <Image src={icon} alt="" width={w} height={h} className="shrink-0" />
                  <span className="text-sm truncate">{label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Mode toggle */}
      <ModeToggle mode={mode} setMode={setMode} />

      {/* Logout */}
      <div className="shrink-0 border-t border-[#c3c6d7] px-[17px] py-3">
        <Link
          href="/login"
          className="flex items-center gap-3 h-10 px-3 rounded-lg text-[#ba1a1a] font-semibold hover:bg-red-50 transition-colors"
        >
          <Image src="/assets/nav-logout.svg" alt="" width={18} height={18} className="shrink-0" />
          <span className="text-sm">Logout</span>
        </Link>
      </div>
    </aside>
  );
}
