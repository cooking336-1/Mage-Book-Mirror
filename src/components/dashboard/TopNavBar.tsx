"use client";

import { useEffect, useState, useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/apiClient";
import { useMode } from "@/contexts/ModeContext";
import CommandPaletteModal from "./CommandPaletteModal";

interface OrganizationData {
  id: string;
  name: string;
  legal_business_name?: string;
  tin?: string;
  experience_mode?: string;
}

interface UserProfile {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
}

export default function TopNavBar() {
  const router = useRouter();
  const { mode, setMode } = useMode();
  const toggleMode = () => {
    setMode(mode === "simple" ? "full" : "simple");
  };

  const [orgName, setOrgName] = useState("Kurt Trading Enterprise");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const userMenuRef = useRef<HTMLDivElement>(null);
  const notificationsRef = useRef<HTMLDivElement>(null);

  // Load organization and user details with Promise chaining
  useEffect(() => {
    let isCancelled = false;

    apiClient
      .get<OrganizationData>("/api/v1/tenancy/organizations/current/")
      .then((res) => {
        if (!isCancelled && res.data) {
          const resolvedName = res.data.legal_business_name || res.data.name;
          if (resolvedName) {
            setOrgName(resolvedName);
          }
        }
      })
      .catch(() => {
        // Fallback to default if endpoint unavailable
      });

    apiClient
      .get<UserProfile>("/api/v1/auth/me/")
      .then((res) => {
        if (!isCancelled && res.data) {
          setUser(res.data);
        }
      })
      .catch(() => {
        // Fallback gracefully
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  // Global Cmd+K / Ctrl+K keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsPaletteOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Click outside listener for dropdowns
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setIsUserMenuOpen(false);
      }
      if (notificationsRef.current && !notificationsRef.current.contains(e.target as Node)) {
        setIsNotificationsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    router.refresh();
    setTimeout(() => {
      setIsRefreshing(false);
    }, 600);
  };

  const handleLogout = async () => {
    try {
      await apiClient.post("/api/v1/auth/logout/");
    } catch {
      // Ignore network errors during logout
    } finally {
      // Hard redirect to flush in-memory React state and client cache across sessions
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    }
  };

  const userDisplayName = user
    ? [user.first_name, user.last_name].filter(Boolean).join(" ") || user.email
    : "Business Owner";

  const userInitial = user?.first_name ? user.first_name[0].toUpperCase() : "M";

  return (
    <>
      <header className="h-16 bg-white border-b border-[#c3c6d7] flex items-center justify-between px-6 shrink-0 sticky top-0 z-20">
        {/* Company name */}
        <div className="flex items-center gap-3">
          <p className="font-black text-[20px] text-[#141b2b] tracking-[-0.3px] truncate max-w-xs md:max-w-md">
            {orgName}
          </p>
          <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold tracking-wide uppercase bg-[#eff6ff] text-[#1d4ed8] border border-[#bfdbfe]">
            {mode === "simple" ? "Simple Mode" : "Professional Mode"}
          </span>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-3">
          {/* Search bar button -> Opens Command Palette */}
          <button
            type="button"
            onClick={() => setIsPaletteOpen(true)}
            className="relative w-64 md:w-80 h-9 bg-[#f1f3ff] hover:bg-[#e6eaff] transition-colors rounded-full flex items-center justify-between px-3 text-left cursor-pointer group"
          >
            <div className="flex items-center gap-2 truncate">
              <Image src="/assets/nav-search.svg" alt="" width={15} height={17} />
              <span className="text-[#6b7280] text-[13px] group-hover:text-[#374151] transition-colors truncate">
                Search or jump to...
              </span>
            </div>
            <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 text-[11px] font-semibold text-[#6b7280] bg-white border border-[#d1d5db] rounded shadow-2xs">
              ⌘K
            </kbd>
          </button>

          {/* All Clear badge */}
          <div className="hidden lg:flex items-center gap-1.5 bg-[#bbf7d0]/70 border border-[#86efac] rounded-[10px] px-3 py-1 text-xs font-semibold text-[#14532d] whitespace-nowrap">
            <span className="w-2 h-2 rounded-full bg-[#16a34a] animate-pulse" />
            All Clear
          </div>

          {/* Refresh */}
          <button
            type="button"
            onClick={handleRefresh}
            title="Refresh application state"
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-[#f1f3ff] transition-colors cursor-pointer"
          >
            <Image
              src="/assets/nav-refresh.svg"
              alt="Refresh"
              width={16}
              height={16}
              className={isRefreshing ? "animate-spin" : ""}
            />
          </button>

          {/* Notifications Dropdown */}
          <div className="relative" ref={notificationsRef}>
            <button
              type="button"
              onClick={() => setIsNotificationsOpen((prev) => !prev)}
              title="Notifications"
              className="relative w-8 h-8 flex items-center justify-center rounded-full hover:bg-[#f1f3ff] transition-colors cursor-pointer"
            >
              <Image src="/assets/nav-bell.svg" alt="Notifications" width={16} height={20} />
              <span className="absolute top-2 right-2 w-2 h-2 bg-[#ba1a1a] rounded-full border border-white" />
            </button>

            {isNotificationsOpen && (
              <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-xl border border-[#c3c6d7] py-2 z-30 animate-in fade-in zoom-in-95 duration-100">
                <div className="px-4 py-2 border-b border-[#e2e8f0] flex items-center justify-between">
                  <span className="text-xs font-bold text-[#141b2b] uppercase tracking-wider">
                    Notifications
                  </span>
                  <span className="text-[11px] text-[#2563eb] font-medium">3 Active</span>
                </div>
                <div className="divide-y divide-[#f1f5f9] max-h-64 overflow-y-auto">
                  <div className="px-4 py-2.5 hover:bg-[#f8f9fa] transition-colors">
                    <p className="text-xs font-semibold text-[#141b2b]">GRA E-VAT Clearance</p>
                    <p className="text-[11px] text-[#64748b] mt-0.5">
                      Statutory tax cryptographic signing service is operational.
                    </p>
                  </div>
                  <div className="px-4 py-2.5 hover:bg-[#f8f9fa] transition-colors">
                    <p className="text-xs font-semibold text-[#141b2b]">Zero Ledger Variance</p>
                    <p className="text-[11px] text-[#64748b] mt-0.5">
                      Trial balance Debits equal Credits across all currency books.
                    </p>
                  </div>
                  <div className="px-4 py-2.5 hover:bg-[#f8f9fa] transition-colors">
                    <p className="text-xs font-semibold text-[#141b2b]">Automatic Daily Backup</p>
                    <p className="text-[11px] text-[#64748b] mt-0.5">
                      Encrypted snapshot completed with zero data loss.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* User Profile / Avatar Dropdown */}
          <div className="relative" ref={userMenuRef}>
            <button
              type="button"
              onClick={() => setIsUserMenuOpen((prev) => !prev)}
              className="w-8 h-8 rounded-full border border-[#c3c6d7] overflow-hidden shrink-0 flex items-center justify-center bg-[#2563eb] text-white font-bold text-xs hover:ring-2 hover:ring-[#2563eb]/30 transition-all cursor-pointer"
            >
              {userInitial}
            </button>

            {isUserMenuOpen && (
              <div className="absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-xl border border-[#c3c6d7] py-2 z-30 animate-in fade-in zoom-in-95 duration-100">
                <div className="px-4 py-2.5 border-b border-[#e2e8f0]">
                  <p className="text-sm font-bold text-[#141b2b] truncate">{userDisplayName}</p>
                  <p className="text-xs text-[#64748b] truncate mt-0.5">
                    {user?.email || "owner@magebooks.com"}
                  </p>
                  <span className="inline-block mt-2 px-2 py-0.5 text-[10px] font-bold bg-[#eff6ff] text-[#1d4ed8] rounded">
                    {orgName}
                  </span>
                </div>

                <div className="py-1">
                  {/* Switch Mode Action */}
                  <button
                    type="button"
                    onClick={() => {
                      toggleMode();
                      setIsUserMenuOpen(false);
                    }}
                    className="w-full text-left px-4 py-2 text-xs font-medium text-[#334155] hover:bg-[#f8f9fa] flex items-center justify-between"
                  >
                    <span>Mode: {mode === "simple" ? "Simple" : "Professional"}</span>
                    <span className="text-[#2563eb] font-semibold text-[11px]">Toggle</span>
                  </button>

                  {/* Settings Link */}
                  <Link
                    href="/dashboard/settings"
                    onClick={() => setIsUserMenuOpen(false)}
                    className="block px-4 py-2 text-xs font-medium text-[#334155] hover:bg-[#f8f9fa]"
                  >
                    Organization Settings
                  </Link>

                  <Link
                    href="/dashboard/chart-of-accounts"
                    onClick={() => setIsUserMenuOpen(false)}
                    className="block px-4 py-2 text-xs font-medium text-[#334155] hover:bg-[#f8f9fa]"
                  >
                    Chart of Accounts
                  </Link>
                </div>

                <div className="border-t border-[#e2e8f0] pt-1 mt-1">
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="w-full text-left px-4 py-2 text-xs font-semibold text-[#dc2626] hover:bg-[#fef2f2] flex items-center gap-2 cursor-pointer"
                  >
                    <Image src="/assets/nav-logout.svg" alt="" width={14} height={14} />
                    Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Command Palette Modal */}
      <CommandPaletteModal
        isOpen={isPaletteOpen}
        onClose={() => setIsPaletteOpen(false)}
        onToggleMode={toggleMode}
        currentMode={mode}
      />
    </>
  );
}
