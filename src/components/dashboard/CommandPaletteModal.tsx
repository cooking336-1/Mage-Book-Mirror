"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";

interface CommandItem {
  id: string;
  title: string;
  category: "Navigation" | "Action";
  description: string;
  href?: string;
  action?: () => void;
  icon?: string;
}

interface CommandPaletteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onToggleMode?: () => void;
  currentMode?: string;
}

export default function CommandPaletteModal({
  isOpen,
  onClose,
  onToggleMode,
  currentMode,
}: CommandPaletteModalProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commandItems: CommandItem[] = [
    {
      id: "nav-dashboard",
      title: "Dashboard Overview",
      category: "Navigation",
      description: "Financial KPIs, revenue metrics, and cash flow",
      href: "/dashboard",
      icon: "/assets/nav-dashboard.svg",
    },
    {
      id: "nav-invoices",
      title: "Sales Invoices",
      category: "Navigation",
      description: "Customer sales invoices, quotes, and payment links",
      href: "/dashboard/invoices",
      icon: "/assets/activity-invoice.svg",
    },
    {
      id: "nav-receivables",
      title: "Accounts Receivable",
      category: "Navigation",
      description: "Track money owed and overdue invoices",
      href: "/dashboard/accounts-receivable",
      icon: "/assets/nav-accounts-receivable.svg",
    },
    {
      id: "nav-contacts",
      title: "Contacts & Directory",
      category: "Navigation",
      description: "Customer and supplier statutory TIN & Ghana Card records",
      href: "/dashboard/contacts",
      icon: "/assets/nav-contacts.svg",
    },
    {
      id: "nav-coa",
      title: "Chart of Accounts",
      category: "Navigation",
      description: "General Ledger 4-digit code accounts hierarchy",
      href: "/dashboard/chart-of-accounts",
      icon: "/assets/nav-chart-accounts.svg",
    },
    {
      id: "nav-payroll",
      title: "Payroll",
      category: "Navigation",
      description: "Ghanaian PAYE and SSNIT statutory payroll runs",
      href: "/dashboard/payroll",
      icon: "/assets/nav-payroll.svg",
    },
    {
      id: "nav-reports",
      title: "Financial Reports",
      category: "Navigation",
      description: "Balance Sheet, Profit & Loss, and Trial Balance",
      href: "/dashboard/reports",
      icon: "/assets/nav-reports.svg",
    },
    {
      id: "nav-payables",
      title: "Accounts Payable",
      category: "Navigation",
      description: "Vendor bills, expenses, and withholding tax",
      href: "/dashboard/accounts-payable",
      icon: "/assets/nav-accounts-payable.svg",
    },
    {
      id: "nav-payments",
      title: "Payments Register",
      category: "Navigation",
      description: "Inbound and outbound payment reconciliations",
      href: "/dashboard/payments",
      icon: "/assets/activity-salary.svg",
    },
    {
      id: "nav-receipts",
      title: "Customer Receipts",
      category: "Navigation",
      description: "Proof of payment and customer cash vouchers",
      href: "/dashboard/receipts",
      icon: "/assets/nav-receipts.svg",
    },
    {
      id: "nav-transactions",
      title: "Transaction Entries",
      category: "Navigation",
      description: "General journal entries and double-entry postings",
      href: "/dashboard/transactions",
      icon: "/assets/nav-transactions.svg",
    },
    {
      id: "nav-ledgers",
      title: "General Ledgers",
      category: "Navigation",
      description: "Account balances, trial balance, and statements",
      href: "/dashboard/ledgers",
      icon: "/assets/nav-ledgers.svg",
    },
    {
      id: "nav-users",
      title: "Users & Access",
      category: "Navigation",
      description: "Invite team members and manage RBAC roles",
      href: "/dashboard/users",
      icon: "/assets/nav-users.svg",
    },
    {
      id: "nav-fixed-assets",
      title: "Fixed Assets",
      category: "Navigation",
      description: "Property, equipment, and depreciation registers",
      href: "/dashboard/fixed-assets",
      icon: "/assets/nav-fixed-assets.svg",
    },
    {
      id: "nav-inventory",
      title: "Inventory Management",
      category: "Navigation",
      description: "Stock valuation, acquisitions, and adjustments",
      href: "/dashboard/inventory",
      icon: "/assets/nav-inventory.svg",
    },
    {
      id: "nav-audit",
      title: "Audit Trail",
      category: "Navigation",
      description: "Immutable security and accounting activity log",
      href: "/dashboard/audit",
      icon: "/assets/nav-audit.svg",
    },
    {
      id: "nav-security",
      title: "Security Log",
      category: "Navigation",
      description: "Authentication events and session tracking",
      href: "/dashboard/security",
      icon: "/assets/nav-security.svg",
    },
    {
      id: "nav-rectification",
      title: "Period Rectification",
      category: "Navigation",
      description: "Prior period adjustments and fiscal lock control",
      href: "/dashboard/period-rectification",
      icon: "/assets/nav-period-rectification.svg",
    },
    {
      id: "nav-hire-expert",
      title: "Hire An Expert",
      category: "Navigation",
      description: "Certified Ghanaian accountants and tax advisors",
      href: "/dashboard/hire-expert",
      icon: "/assets/nav-hire-expert.svg",
    },
    {
      id: "nav-settings",
      title: "Business Setup & Settings",
      category: "Navigation",
      description: "Company details, tax profile, and preferences",
      href: "/dashboard/setup",
      icon: "/assets/nav-setup.svg",
    },
    {
      id: "action-new-invoice",
      title: "Create New Invoice",
      category: "Action",
      description: "Issue a new customer invoice with GRA compliance",
      href: "/dashboard/invoices",
      icon: "/assets/activity-invoice.svg",
    },
    {
      id: "action-add-contact",
      title: "Add New Contact",
      category: "Action",
      description: "Create a customer or supplier with statutory validation",
      href: "/dashboard/contacts",
      icon: "/assets/nav-contacts.svg",
    },
  ];

  if (onToggleMode) {
    commandItems.push({
      id: "action-toggle-mode",
      title: `Switch to ${currentMode === "simple" ? "Professional" : "Simple"} Mode`,
      category: "Action",
      description: `Toggle accounting experience to ${currentMode === "simple" ? "full double-entry" : "streamlined cash-based"}`,
      action: onToggleMode,
      icon: "/assets/lightning.svg",
    });
  }

  // Filter items
  const filtered = commandItems.filter((item) => {
    const q = query.toLowerCase().trim();
    if (!q) return true;
    return (
      item.title.toLowerCase().includes(q) ||
      item.description.toLowerCase().includes(q) ||
      item.category.toLowerCase().includes(q)
    );
  });

  const handleClose = useCallback(() => {
    setQuery("");
    setSelectedIndex(0);
    onClose();
  }, [onClose]);

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        handleClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (filtered.length > 0 ? (prev + 1) % filtered.length : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          filtered.length > 0 ? (prev - 1 + filtered.length) % filtered.length : 0
        );
      } else if (e.key === "Enter") {
        e.preventDefault();
        const selected = filtered[selectedIndex];
        if (selected) {
          if (selected.action) {
            selected.action();
            handleClose();
          } else if (selected.href) {
            router.push(selected.href);
            handleClose();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filtered, selectedIndex, router, handleClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command Palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 bg-black/50 backdrop-blur-xs px-4"
      onClick={handleClose}
    >
      <div
        className="w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-[#c3c6d7] overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3.5 border-b border-[#e2e8f0] gap-3 bg-[#f8f9fa]">
          <div className="w-5 h-5 flex items-center justify-center shrink-0">
            <Image src="/assets/nav-search.svg" alt="" width={18} height={18} />
          </div>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Type a command, page, or action..."
            className="flex-1 bg-transparent text-[#191c1e] text-base placeholder-[#64748b] focus:outline-none"
          />
          <kbd className="px-2 py-0.5 text-xs font-semibold text-[#64748b] bg-white border border-[#cbd5e1] rounded-md shadow-2xs">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 divide-y divide-transparent">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-[#64748b]">
              <p className="font-medium text-sm">No results found for &ldquo;{query}&rdquo;</p>
              <p className="text-xs mt-1">Try searching for invoices, contacts, accounts, or payroll.</p>
            </div>
          ) : (
            filtered.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    if (item.action) {
                      item.action();
                    } else if (item.href) {
                      router.push(item.href);
                    }
                    handleClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`w-full text-left px-3 py-2.5 rounded-xl flex items-center gap-3 transition-colors ${
                    isSelected ? "bg-[#eff6ff] text-[#1d4ed8]" : "hover:bg-[#f8f9fa] text-[#1e293b]"
                  }`}
                >
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                      isSelected ? "bg-[#dbeafe]" : "bg-[#f1f5f9]"
                    }`}
                  >
                    {item.icon ? (
                      <Image src={item.icon} alt="" width={16} height={16} />
                    ) : (
                      <span className="text-xs font-bold">⌘</span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm truncate">{item.title}</span>
                      <span className="text-[11px] font-medium text-[#64748b] uppercase tracking-wider ml-2 shrink-0">
                        {item.category}
                      </span>
                    </div>
                    <p className="text-xs text-[#64748b] truncate mt-0.5">{item.description}</p>
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="px-4 py-2.5 bg-[#f8f9fa] border-t border-[#e2e8f0] flex items-center justify-between text-xs text-[#64748b]">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="px-1.5 py-0.5 bg-white border border-[#cbd5e1] rounded text-[10px] font-mono mr-1">
                ↑
              </kbd>
              <kbd className="px-1.5 py-0.5 bg-white border border-[#cbd5e1] rounded text-[10px] font-mono mr-1">
                ↓
              </kbd>
              navigate
            </span>
            <span>
              <kbd className="px-1.5 py-0.5 bg-white border border-[#cbd5e1] rounded text-[10px] font-mono mr-1">
                ↵
              </kbd>
              select
            </span>
          </div>
          <span>MageBooks Quick Actions</span>
        </div>
      </div>
    </div>
  );
}
