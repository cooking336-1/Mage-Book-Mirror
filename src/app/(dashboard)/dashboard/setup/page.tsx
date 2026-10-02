"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  Building2,
  Receipt,
  Sliders,
  Lock,
  Users,
  Shield,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  X,
  ExternalLink,
  Save,
  Check,
} from "lucide-react";

interface OrganizationData {
  id: string;
  name: string;
  business_tin: string;
  ghana_card_number: string;
  address: string;
  phone: string;
  email: string;
  vat_registered: boolean;
  vat_scheme: string;
  default_experience_mode: "simple" | "professional";
  created_at: string;
}

interface SettlementData {
  settlement_bank_name: string;
  settlement_account_number: string;
  settlement_momo_number: string;
  settlement_locked_at: string | null;
}

type SettingsTab = "PROFILE" | "TAX" | "MODE" | "SETTLEMENT";

export default function SetupPage() {
  const { mode, setMode } = useMode();

  const [activeTab, setActiveTab] = useState<SettingsTab>("PROFILE");
  const [org, setOrg] = useState<OrganizationData | null>(null);
  const [settlement, setSettlement] = useState<SettlementData | null>(null);

  // Profile Form
  const [companyName, setCompanyName] = useState("");
  const [companyAddress, setCompanyAddress] = useState("");
  const [companyPhone, setCompanyPhone] = useState("");
  const [companyEmail, setCompanyEmail] = useState("");

  // Settlement Form
  const [bankName, setBankName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [momoNumber, setMomoNumber] = useState("");
  const [ownerTotp, setOwnerTotp] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let isCancelled = false;

    async function loadSettings() {
      try {
        const [orgRes, settleRes] = await Promise.allSettled([
          apiClient.get<OrganizationData>("/api/v1/tenancy/organizations/current/"),
          apiClient.get<SettlementData>("/api/v1/tenancy/organization/settlement/"),
        ]);

        if (isCancelled) return;

        if (orgRes.status === "fulfilled" && orgRes.value.data) {
          const o = orgRes.value.data;
          setOrg(o);
          setCompanyName(o.name || "");
          setCompanyAddress(o.address || "");
          setCompanyPhone(o.phone || "");
          setCompanyEmail(o.email || "");
        }

        if (settleRes.status === "fulfilled" && settleRes.value.data) {
          const s = settleRes.value.data;
          setSettlement(s);
          setBankName(s.settlement_bank_name || "");
          setAccountNumber(s.settlement_account_number || "");
          setMomoNumber(s.settlement_momo_number || "");
        }

        setError(null);
        setIsLoading(false);
      } catch (err: unknown) {
        if (!isCancelled) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
          setError(resp?.detail || "Failed to load business setup.");
          setIsLoading(false);
        }
      }
    }

    loadSettings();

    return () => {
      isCancelled = true;
    };
  }, [refreshKey]);

  // Save Profile Changes
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await apiClient.patch<OrganizationData>(
        "/api/v1/tenancy/organizations/current/",
        {
          name: companyName.trim(),
          address: companyAddress.trim(),
          phone: companyPhone.trim(),
          email: companyEmail.trim(),
        }
      );
      setOrg(res.data);
      setSuccessMsg("Company profile updated successfully.");
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to update company settings.");
    } finally {
      setIsSaving(false);
    }
  };

  // Switch Experience Mode
  const handleSwitchMode = async (newMode: "simple" | "professional") => {
    setIsSaving(true);
    setError(null);

    try {
      await apiClient.patch("/api/v1/tenancy/organizations/current/", {
        default_experience_mode: newMode,
      });
      setMode(newMode);
      setSuccessMsg(`Switched default interface to ${newMode === "simple" ? "Simple Mode" : "Professional Accounting Mode"}.`);
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to update experience mode.");
    } finally {
      setIsSaving(false);
    }
  };

  // Save Settlement Locks
  const handleSaveSettlement = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await apiClient.post<SettlementData>(
        "/api/v1/tenancy/organization/settlement/",
        {
          settlement_bank_name: bankName.trim(),
          settlement_account_number: accountNumber.trim(),
          settlement_momo_number: momoNumber.trim(),
          owner_totp_code: ownerTotp.trim() || undefined,
        }
      );
      setSettlement(res.data);
      setOwnerTotp("");
      setSuccessMsg("Financial destination settlement lock saved successfully.");
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to update settlement destination. (Step-up TOTP code may be required for Admins).");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              Business Setup &amp; Settings
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
              <Check className="w-3.5 h-3.5" />
              Tenant Isolated
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            Configure company registration, Ghana statutory tax settings, experience mode, and settlement locks.
          </p>
        </div>

        <button
          onClick={() => {
            setIsLoading(true);
            setRefreshKey((k) => k + 1);
          }}
          disabled={isLoading}
          className="p-2.5 text-slate-600 bg-white border border-[#c3c6d7] rounded-lg hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50 self-start sm:self-auto"
          title="Refresh settings"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
        </button>
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

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <button
          type="button"
          onClick={() => setActiveTab("PROFILE")}
          className={`p-4 rounded-xl border text-left transition-all ${
            activeTab === "PROFILE"
              ? "bg-blue-50/70 border-blue-500 ring-2 ring-blue-500/20"
              : "bg-white border-[#c3c6d7] hover:border-slate-400"
          }`}
        >
          <Building2 className="w-5 h-5 text-blue-600 mb-2" />
          <p className="font-bold text-slate-900 text-sm">Company Profile</p>
          <p className="text-[11px] text-slate-500 mt-0.5">Name, contact, address</p>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("TAX")}
          className={`p-4 rounded-xl border text-left transition-all ${
            activeTab === "TAX"
              ? "bg-blue-50/70 border-blue-500 ring-2 ring-blue-500/20"
              : "bg-white border-[#c3c6d7] hover:border-slate-400"
          }`}
        >
          <Receipt className="w-5 h-5 text-amber-600 mb-2" />
          <p className="font-bold text-slate-900 text-sm">Tax &amp; GRA Registration</p>
          <p className="text-[11px] text-slate-500 mt-0.5">TIN, VAT status &amp; scheme</p>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("MODE")}
          className={`p-4 rounded-xl border text-left transition-all ${
            activeTab === "MODE"
              ? "bg-blue-50/70 border-blue-500 ring-2 ring-blue-500/20"
              : "bg-white border-[#c3c6d7] hover:border-slate-400"
          }`}
        >
          <Sliders className="w-5 h-5 text-purple-600 mb-2" />
          <p className="font-bold text-slate-900 text-sm">Experience Mode</p>
          <p className="text-[11px] text-slate-500 mt-0.5">Simple vs Professional</p>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("SETTLEMENT")}
          className={`p-4 rounded-xl border text-left transition-all ${
            activeTab === "SETTLEMENT"
              ? "bg-blue-50/70 border-blue-500 ring-2 ring-blue-500/20"
              : "bg-white border-[#c3c6d7] hover:border-slate-400"
          }`}
        >
          <Lock className="w-5 h-5 text-emerald-600 mb-2" />
          <p className="font-bold text-slate-900 text-sm">Settlement Lock</p>
          <p className="text-[11px] text-slate-500 mt-0.5">Bank &amp; MoMo accounts</p>
        </button>
      </div>

      {/* Main Settings Card */}
      {isLoading ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3 shadow-sm">
          <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
          <p className="text-sm">Loading business settings...</p>
        </div>
      ) : activeTab === "PROFILE" ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900 pb-3 border-b border-slate-100">
            Company Profile &amp; Contact Details
          </h2>
          <form onSubmit={handleSaveProfile} className="mt-5 flex flex-col gap-4 max-w-xl">
            <div>
              <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                Company Legal Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                Ghana Digital Address / Location
              </label>
              <input
                type="text"
                placeholder="e.g. GA-183-9022, Airport Residential, Accra"
                value={companyAddress}
                onChange={(e) => setCompanyAddress(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Business Phone Number
                </label>
                <input
                  type="text"
                  placeholder="+233 24 123 4567"
                  value={companyPhone}
                  onChange={(e) => setCompanyPhone(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Official Billing Email
                </label>
                <input
                  type="email"
                  placeholder="accounts@company.com"
                  value={companyEmail}
                  onChange={(e) => setCompanyEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                />
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-400">
                Created: {org?.created_at ? new Date(org.created_at).toLocaleDateString() : "—"}
              </span>
              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50"
              >
                {isSaving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save Profile
              </button>
            </div>
          </form>
        </div>
      ) : activeTab === "TAX" ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900 pb-3 border-b border-slate-100">
            Statutory Tax &amp; GRA Registration
          </h2>
          <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl text-sm">
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
              <p className="text-xs font-semibold text-slate-500 uppercase">
                Ghana Revenue Authority TIN
              </p>
              <p className="text-lg font-mono font-bold text-slate-900 mt-1">
                {org?.business_tin || "Not Registered"}
              </p>
              <p className="text-xs text-slate-400 mt-1">Used on statutory Act 1151 invoices</p>
            </div>

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
              <p className="text-xs font-semibold text-slate-500 uppercase">
                Director / Signatory Ghana Card
              </p>
              <p className="text-lg font-mono font-bold text-slate-900 mt-1">
                {org?.ghana_card_number || "GHA-XXXXXXXXX-X"}
              </p>
              <p className="text-xs text-slate-400 mt-1">Primary identity credential</p>
            </div>

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
              <p className="text-xs font-semibold text-slate-500 uppercase">VAT Registration</p>
              <p className="text-lg font-bold text-emerald-700 mt-1">
                {org?.vat_registered ? "VAT Registered" : "Not Registered"}
              </p>
              <p className="text-xs text-slate-400 mt-1">VAT Act compliance status</p>
            </div>

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
              <p className="text-xs font-semibold text-slate-500 uppercase">Tax Scheme</p>
              <p className="text-lg font-bold text-blue-700 mt-1">
                {org?.vat_scheme || "STANDARD (15% + 6% Levies)"}
              </p>
              <p className="text-xs text-slate-400 mt-1">
                NHIL 2.5% · GETFund 2.5% · COVID 1%
              </p>
            </div>
          </div>
        </div>
      ) : activeTab === "MODE" ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900 pb-3 border-b border-slate-100">
            Workspace Experience Mode
          </h2>
          <p className="text-sm text-slate-600 mt-2">
            Switch between human-friendly Ghanaian business terms and statutory double-entry accounting terminology.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-5 max-w-2xl">
            <div
              onClick={() => handleSwitchMode("simple")}
              className={`p-5 rounded-xl border cursor-pointer transition-all ${
                mode === "simple"
                  ? "bg-blue-50 border-blue-500 ring-2 ring-blue-500/20"
                  : "bg-white border-slate-200 hover:border-slate-400"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-900 text-base">Simple Mode</span>
                {mode === "simple" && <Check className="w-5 h-5 text-blue-600" />}
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Designed for everyday Ghanaian SME owners: &quot;Money Owed to Me&quot;, &quot;Money I Owe&quot;, &quot;Pay Staff&quot;, &quot;Record Transaction&quot;.
              </p>
            </div>

            <div
              onClick={() => handleSwitchMode("professional")}
              className={`p-5 rounded-xl border cursor-pointer transition-all ${
                mode === "professional"
                  ? "bg-blue-50 border-blue-500 ring-2 ring-blue-500/20"
                  : "bg-white border-slate-200 hover:border-slate-400"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-900 text-base">Professional Accounting Mode</span>
                {mode === "professional" && <Check className="w-5 h-5 text-blue-600" />}
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Designed for Certified Accountants &amp; Statutory Auditors: &quot;Accounts Receivable&quot;, &quot;Accounts Payable&quot;, &quot;General Ledgers&quot;, &quot;Journal Vouchers&quot;.
              </p>
            </div>
          </div>
        </div>
      ) : activeTab === "SETTLEMENT" ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Financial Settlement Destination Lock
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Architecture Manual 4.6.2 &amp; Anti-Tamper Security: Bank and Mobile Money disbursement lock.
              </p>
            </div>
            {settlement?.settlement_locked_at && (
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center gap-1">
                <Lock className="w-3.5 h-3.5" />
                Locked on {new Date(settlement.settlement_locked_at).toLocaleDateString()}
              </span>
            )}
          </div>

          <form onSubmit={handleSaveSettlement} className="mt-5 flex flex-col gap-4 max-w-xl">
            <div>
              <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                Settlement Bank Name
              </label>
              <input
                type="text"
                placeholder="e.g. Ecobank Ghana, GCB Bank, Stanbic"
                value={bankName}
                onChange={(e) => setBankName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                Bank Account Number
              </label>
              <input
                type="text"
                placeholder="144100XXXXXXX"
                value={accountNumber}
                onChange={(e) => setAccountNumber(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                Mobile Money (MoMo) Wallet Number
              </label>
              <input
                type="text"
                placeholder="024XXXXXXX (MTN, Telecel, AT)"
                value={momoNumber}
                onChange={(e) => setMomoNumber(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                Owner TOTP Code (If updated by Admin)
              </label>
              <input
                type="text"
                maxLength={6}
                placeholder="6-digit authorization code"
                value={ownerTotp}
                onChange={(e) => setOwnerTotp(e.target.value.replace(/\D/g, ""))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white font-mono"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Required only when updated by an Administrator to satisfy the Owner step-up authorization challenge.
              </p>
            </div>

            <div className="pt-4 border-t border-slate-100 flex justify-end">
              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50"
              >
                {isSaving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Lock Settlement Coordinates
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {/* Cross Links */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link
          href="/dashboard/users"
          className="p-5 bg-white border border-[#c3c6d7] rounded-xl hover:border-blue-500 transition-colors flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <p className="font-bold text-slate-900 text-sm">Team &amp; Access Governance</p>
              <p className="text-xs text-slate-500">Manage user roles and auditor permissions</p>
            </div>
          </div>
          <ExternalLink className="w-4 h-4 text-slate-400" />
        </Link>

        <Link
          href="/dashboard/audit"
          className="p-5 bg-white border border-[#c3c6d7] rounded-xl hover:border-blue-500 transition-colors flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-600">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <p className="font-bold text-slate-900 text-sm">Immutable Audit Trail</p>
              <p className="text-xs text-slate-500">View forensic logs and SHA-256 cryptographic chain</p>
            </div>
          </div>
          <ExternalLink className="w-4 h-4 text-slate-400" />
        </Link>
      </div>
    </div>
  );
}
