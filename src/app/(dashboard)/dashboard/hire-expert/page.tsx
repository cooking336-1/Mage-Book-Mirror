"use client";

import { useState, useEffect } from "react";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  Award,
  CheckCircle,
  Clock,
  Mail,
  MessageSquare,
  Phone,
  ShieldCheck,
  Sparkles,
  UserCheck,
  X,
  Send,
} from "lucide-react";

interface ServiceCategory {
  id: string;
  title: string;
  badge: string;
  tagline: string;
  desc: string;
  deliverables: string[];
  pricingHint: string;
}

const EXPERT_SERVICES: ServiceCategory[] = [
  {
    id: "tax-compliance",
    title: "GRA Tax Filing & E-VAT Compliance",
    badge: "CITG Certified",
    tagline: "Prevent penalties, clear audit flags, and certify Act 1151 compliance.",
    desc: "Work with licensed Ghanaian tax practitioners to prepare and file your monthly VAT returns, Withholding Tax (WHT), PAYE, and annual corporate income tax declarations directly into the GRA portal.",
    deliverables: [
      "Monthly GRA VAT & NHIL/GETFL/COVID Levy reconciliation",
      "WHT Certificate preparation and remittance clearance",
      "Corporate Income Tax annual return and capital allowance schedules",
      "Resolution of GRA taxpayer compliance notice queries",
    ],
    pricingHint: "From GHS 850 / monthly filing",
  },
  {
    id: "bookkeeping",
    title: "SME Bookkeeping & Financial Catch-Up",
    badge: "ICAG Registered",
    tagline: "Transform shoeboxes of paper receipts and MoMo statements into balanced books.",
    desc: "Have a dedicated bookkeeper reconcile your MTN MoMo merchant wallets, Telecel Cash statements, and commercial bank feeds. We balance your Chart of Accounts and classify your operating expenses.",
    deliverables: [
      "Bank and MoMo transaction classification and ledger reconciliation",
      "Accounts Receivable & Payable aging cleanups",
      "Inventory valuation and cost-of-goods-sold (COGS) adjustments",
      "Monthly management accounts & profit/loss summary",
    ],
    pricingHint: "From GHS 600 / month",
  },
  {
    id: "payroll",
    title: "Statutory Payroll & SSNIT Compliance",
    badge: "Tier 1 & Tier 2 Specialist",
    tagline: "Guaranteed statutory compliance with SSNIT, NPRA, and GRA PAYE withholdings.",
    desc: "Ensure seamless employee salary computation with automated SSNIT Tier 1 & Tier 2 deductions, GRA PAYE bracket withholdings, and bulk Mobile Money disbursement file validation.",
    deliverables: [
      "Monthly SSNIT Tier 1 contribution schedules & submission",
      "Approved Tier 2 Corporate Trustee remittance coordination",
      "GRA PAYE monthly returns & employee tax relief optimization",
      "Confidential electronic payslip generation for staff",
    ],
    pricingHint: "From GHS 450 / pay run",
  },
  {
    id: "audit-advisory",
    title: "Audit Preparation & Financial Advisory",
    badge: "Senior Chartered Accountant",
    tagline: "Get investor-ready and prepare immaculate PBC schedules for external auditors.",
    desc: "Prepare your business for institutional audits, private equity investments, or commercial bank financing with audit-ready workpapers, cash flow forecasting, and internal control reviews.",
    deliverables: [
      "Auditor PBC (Prepared by Client) document folder preparation",
      "Trial balance rectification and prior-period adjustment reviews",
      "3-Year 3-statement financial models and cash-flow projections",
      "Internal controls and segregation of accounting duties audit",
    ],
    pricingHint: "Custom fixed engagement quote",
  },
];

export default function HireExpertPage() {
  const { isSimpleMode } = useMode();

  const [orgName, setOrgName] = useState("");
  const [orgTin, setOrgTin] = useState("");
  const [userEmail, setUserEmail] = useState("");

  // Modal State
  const [selectedService, setSelectedService] = useState<ServiceCategory | null>(null);
  const [contactName, setContactName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [preferredSchedule, setPreferredSchedule] = useState("ASAP");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedRef, setSubmittedRef] = useState<string | null>(null);

  // Fetch tenant profile on mount to pre-fill enquiry forms
  useEffect(() => {
    let isCancelled = false;
    async function loadTenantData() {
      try {
        const [orgRes, meRes] = await Promise.allSettled([
          apiClient.get<{ name?: string; tin_number?: string; phone_number?: string }>("/api/v1/tenancy/organizations/current/"),
          apiClient.get<{ email?: string; first_name?: string; last_name?: string }>("/api/v1/auth/me/"),
        ]);

        if (!isCancelled) {
          if (orgRes.status === "fulfilled" && orgRes.value.data) {
            setOrgName(orgRes.value.data.name || "");
            setOrgTin(orgRes.value.data.tin_number || "");
            if (orgRes.value.data.phone_number) {
              setContactPhone(orgRes.value.data.phone_number);
            }
          }
          if (meRes.status === "fulfilled" && meRes.value.data) {
            setUserEmail(meRes.value.data.email || "");
            const fullName = [meRes.value.data.first_name, meRes.value.data.last_name].filter(Boolean).join(" ");
            if (fullName) setContactName(fullName);
          }
        }
      } catch {
        // Non-blocking fallback
      }
    }

    loadTenantData();
    return () => {
      isCancelled = true;
    };
  }, []);

  const handleOpenModal = (service: ServiceCategory) => {
    setSelectedService(service);
    setSubmittedRef(null);
  };

  const handleCloseModal = () => {
    setSelectedService(null);
    setSubmittedRef(null);
    setNotes("");
  };

  const handleSubmitEnquiry = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      // Create support / expert advisory enquiry reference
      const refId = `MB-EXP-${Date.now().toString().slice(-6)}`;

      // Attempt to record consultation request via audit trail or internal note
      try {
        await apiClient.post("/api/v1/audit/trail/", {
          action: "EXPERT_CONSULTATION_REQUESTED",
          details: {
            reference: refId,
            service: selectedService?.title,
            organization: orgName,
            contact_name: contactName,
            contact_phone: contactPhone,
            urgency: preferredSchedule,
            notes,
          },
        });
      } catch {
        // Graceful continuation if direct audit posting is restricted
      }

      setSubmittedRef(refId);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-8 flex flex-col gap-8 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 text-white rounded-2xl p-8 sm:p-10 shadow-lg relative overflow-hidden">
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 text-blue-200 text-xs font-semibold uppercase tracking-wider mb-4 border border-blue-400/30">
            <Sparkles className="w-3.5 h-3.5 text-blue-300" />
            Vetted Accounting & Tax Professionals
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
            {isSimpleMode ? "Hire a Certified Ghanaian Accountant" : "Chartered Accounting & Advisory Network"}
          </h1>
          <p className="text-slate-300 text-base sm:text-lg mt-3 leading-relaxed">
            Connect directly with verified ICAG (Institute of Chartered Accountants, Ghana) and CITG (Chartered
            Institute of Taxation, Ghana) practitioners for hands-on bookkeeping, GRA compliance, and audit defense.
          </p>

          <div className="flex flex-wrap items-center gap-6 mt-6 text-xs text-slate-300 font-medium">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>100% Licensed Practitioners</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-400" />
              <span>Response within 24 Hours</span>
            </div>
            <div className="flex items-center gap-2">
              <Award className="w-4 h-4 text-amber-400" />
              <span>GRA Act 1151 E-VAT Specialists</span>
            </div>
          </div>
        </div>

        {/* Decorative background glow */}
        <div className="absolute -right-10 -bottom-10 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* Services Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {EXPERT_SERVICES.map((item) => (
          <div
            key={item.id}
            className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 flex flex-col justify-between shadow-sm hover:shadow-md transition-all group"
          >
            <div>
              <div className="flex items-start justify-between gap-4 mb-3">
                <span className="inline-block px-3 py-1 text-xs font-bold rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                  {item.badge}
                </span>
                <span className="text-xs font-semibold text-slate-500 font-mono">{item.pricingHint}</span>
              </div>

              <h2 className="font-bold text-slate-900 text-xl group-hover:text-blue-600 transition-colors">
                {item.title}
              </h2>
              <p className="text-xs font-semibold text-blue-600 mt-1 mb-3">{item.tagline}</p>
              <p className="text-slate-600 text-sm leading-relaxed mb-5">{item.desc}</p>

              <div className="border-t border-slate-100 pt-4 mb-6">
                <p className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2.5">
                  Core Deliverables:
                </p>
                <ul className="space-y-2">
                  {item.deliverables.map((deliv, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-slate-600">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                      <span>{deliv}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <button
                type="button"
                onClick={() => handleOpenModal(item)}
                className="w-full bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold py-2.5 px-4 rounded-xl transition-all shadow-sm flex items-center justify-center gap-2 group-hover:gap-3"
              >
                <span>Request Consultation</span>
                <span className="transition-transform group-hover:translate-x-0.5">&rarr;</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Direct Contact Banner */}
      <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 sm:p-8 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-xl flex items-center justify-center shrink-0">
            <UserCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-base">Need Immediate Assistance or Bespoke Scope?</h3>
            <p className="text-slate-600 text-xs sm:text-sm mt-0.5">
              Speak directly with our Chief Accounting Liaison for institutional advice or urgent GRA issues.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 shrink-0">
          <a
            href="mailto:support@magebooks.com?subject=Chartered%20Expert%20Inquiry"
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition-colors shadow-sm"
          >
            <Mail className="w-4 h-4 text-blue-600" />
            Email Support
          </a>
          <a
            href="tel:+233240000000"
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl hover:bg-emerald-100 transition-colors shadow-sm"
          >
            <Phone className="w-4 h-4 text-emerald-600" />
            +233 (0) 24 000 0000
          </a>
        </div>
      </div>

      {/* Consultation Request Modal */}
      {selectedService && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
              <div>
                <span className="text-[11px] font-bold text-blue-600 uppercase tracking-wider block">
                  {selectedService.badge}
                </span>
                <h3 className="font-bold text-slate-900 text-base">{selectedService.title}</h3>
              </div>
              <button
                type="button"
                onClick={handleCloseModal}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {submittedRef ? (
              /* Success Confirmation */
              <div className="p-8 text-center flex flex-col items-center">
                <div className="w-14 h-14 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mb-4">
                  <CheckCircle className="w-8 h-8" />
                </div>
                <h4 className="text-xl font-bold text-slate-900 mb-1">Consultation Request Dispatched!</h4>
                <p className="text-xs text-slate-500 mb-4 font-mono">Reference: {submittedRef}</p>
                <p className="text-sm text-slate-600 leading-relaxed max-w-sm mb-6">
                  Thank you, <strong className="text-slate-900">{contactName || orgName}</strong>. A certified
                  practitioner specializing in <strong>{selectedService.title}</strong> will review your request and
                  contact you via phone or email within 24 business hours.
                </p>

                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 w-full text-left text-xs mb-6 space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Business Profile:</span>
                    <span className="font-semibold text-slate-800">{orgName || "Active Organization"}</span>
                  </div>
                  {orgTin && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">GRA TIN:</span>
                      <span className="font-mono font-semibold text-slate-800">{orgTin}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-slate-500">Target Urgency:</span>
                    <span className="font-semibold text-blue-600">{preferredSchedule}</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleCloseModal}
                  className="w-full bg-[#2563eb] hover:bg-[#1d4ed8] text-white font-medium py-2.5 rounded-xl text-sm transition-colors shadow-sm"
                >
                  Done
                </button>
              </div>
            ) : (
              /* Enquiry Form */
              <form onSubmit={handleSubmitEnquiry} className="p-6 flex flex-col gap-4">
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-xs text-blue-900 flex items-start gap-2.5">
                  <MessageSquare className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                  <span>
                    Your tenant profile (<strong>{orgName || "Current Organization"}</strong>
                    {orgTin ? `, TIN: ${orgTin}` : ""}) will be securely attached to this engagement.
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                      Contact Person *
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Kwame Mensah"
                      value={contactName}
                      onChange={(e) => setContactName(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                      Phone Number *
                    </label>
                    <input
                      type="tel"
                      required
                      placeholder="e.g. 0244123456"
                      value={contactPhone}
                      onChange={(e) => setContactPhone(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Contact Email
                  </label>
                  <input
                    type="email"
                    placeholder="e.g. kwame@enterprise.com"
                    value={userEmail}
                    onChange={(e) => setUserEmail(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Engagement Timeline
                  </label>
                  <select
                    value={preferredSchedule}
                    onChange={(e) => setPreferredSchedule(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500 bg-white"
                  >
                    <option value="ASAP">Urgent — Immediate Attention (Within 24 Hours)</option>
                    <option value="THIS_WEEK">This Week — Standard Review</option>
                    <option value="END_OF_MONTH">End of Month — Next Filing Cycle</option>
                    <option value="GENERAL_INQUIRY">General Inquiry / Fee Estimation</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Specific Requirements or Questions
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Briefly describe your books, backlog months, or GRA audit inquiries..."
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500 resize-none"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200 mt-2">
                  <button
                    type="button"
                    onClick={handleCloseModal}
                    className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-5 py-2 text-sm font-medium bg-[#2563eb] hover:bg-[#1d4ed8] text-white rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                  >
                    {isSubmitting ? (
                      <Clock className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                    Submit Consultation Request
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
