"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Logo from "@/components/Logo";
import StepperBar from "@/components/StepperBar";
import Step1CompanyDetails, { type Step1Data } from "@/components/onboarding/Step1CompanyDetails";
import Step2VATStatus from "@/components/onboarding/Step2VATStatus";
import Step3ChooseExperience, { type ExperienceMode } from "@/components/onboarding/Step3ChooseExperience";
import Step4FiscalCalendar, { type PeriodLength } from "@/components/onboarding/Step4FiscalCalendar";
import Step5ChartOfAccounts, { type COAPath } from "@/components/onboarding/Step5ChartOfAccounts";
import Step6Contacts, { type Contact } from "@/components/onboarding/Step6Contacts";
import apiClient, { setActiveTenantId } from "@/lib/apiClient";

// ── State shape ──────────────────────────────────────────────────────────────
interface OnboardingState {
  // Step 1
  company: Step1Data;
  // Step 2
  vatRegistered: boolean | null;
  // Step 3
  experienceMode: ExperienceMode | null;
  // Step 4
  periodLength: PeriodLength;
  fiscalYearEnd: Date;
  // Step 5
  coaPath: COAPath | null;
  // Step 6
  contacts: Contact[];
}

const TOTAL_STEPS = 6;

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [state, setState] = useState<OnboardingState>({
    company: { companyName: "", businessTin: "", ghanaCard: "", address: "", phone: "", email: "" },
    vatRegistered: null,
    experienceMode: null,
    periodLength: "monthly",
    fiscalYearEnd: new Date(new Date().getFullYear(), 11, 31), // Dec 31
    coaPath: null,
    contacts: [{ id: "default", name: "", type: "Customer", contactInfo: "", tin: "" }],
  });

  const goBack = () => {
    setError(null);
    setStep(s => Math.max(1, s - 1));
  };
  const goNext = () => {
    setError(null);
    setStep(s => Math.min(TOTAL_STEPS, s + 1));
  };

  const handleFinish = async () => {
    setError(null);

    const companyName = state.company.companyName.trim();
    if (!companyName) {
      setError("Please provide a company name in Step 1 to register your organization.");
      setStep(1);
      return;
    }

    setLoading(true);
    try {
      // 1. Provision organization via Directive 9 Axios singleton
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const orgPayload: Record<string, any> = {
        name: companyName,
        address: state.company.address.trim(),
        phone: state.company.phone.trim(),
        email: state.company.email.trim(),
        vat_status: state.vatRegistered ? "STANDARD_20" : "EXEMPT",
        accounting_mode: state.experienceMode === "professional" ? "strict" : "simple",
        tax_period_length: state.periodLength || "monthly",
      };

      if (state.company.businessTin?.trim()) {
        orgPayload.business_tin = state.company.businessTin.trim().toUpperCase();
      }
      if (state.company.ghanaCard?.trim()) {
        orgPayload.ghana_card_number = state.company.ghanaCard.trim().toUpperCase();
      }

      const orgRes = await apiClient.post<{ id: string }>("/api/v1/tenancy/organizations/", orgPayload);
      const orgId = orgRes.data?.id;

      if (orgId) {
        setActiveTenantId(orgId);
      }

      // 2. Optionally seed initial contacts if entered in Step 6
      for (const c of state.contacts) {
        if (c.name && c.name.trim()) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const contactPayload: Record<string, any> = {
            name: c.name.trim(),
            contact_type: c.type === "Supplier" ? "SUPPLIER" : "CUSTOMER",
          };
          if (c.contactInfo?.trim()) {
            if (c.contactInfo.includes("@")) {
              contactPayload.email = c.contactInfo.trim();
            } else {
              contactPayload.phone = c.contactInfo.trim();
            }
          }
          if (c.tin?.trim()) {
            contactPayload.tin = c.tin.trim().toUpperCase();
          }

          try {
            await apiClient.post("/api/v1/contacts/", contactPayload);
          } catch (contactErr) {
            console.warn("Could not save initial contact during onboarding:", contactErr);
          }
        }
      }

      // 3. Navigate into the dashboard
      router.push("/dashboard");
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      console.error("Onboarding submission failed:", err);
      const data = err.response?.data;
      if (typeof data === "string") {
        setError(data);
      } else if (data && typeof data === "object") {
        const firstKey = Object.keys(data)[0];
        const val = data[firstKey];
        const msg = Array.isArray(val) ? val.join(" ") : String(val);
        setError(`${firstKey}: ${msg}`);
      } else {
        setError(err.message || "Failed to register organization. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };


  return (
    <div className="min-h-screen bg-[#f4f7fe] flex flex-col">
      {/* Top area: Logo + Title */}
      <div className="flex flex-col items-center pt-10 pb-6 px-4">
        <Logo />
        <h1 className="mt-8 text-3xl font-bold text-[#141b2b] tracking-wide uppercase">
          Create an Account
        </h1>
      </div>

      {/* Stepper */}
      <div className="px-4 mb-10">
        <StepperBar currentStep={step} />
      </div>

      {/* Error Banner */}
      {error && (
        <div className="max-w-5xl mx-auto w-full px-4 mb-4">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between shadow-sm">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-800 text-lg font-bold leading-none ml-4"
            >
              &times;
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 px-4 max-w-5xl mx-auto w-full pb-6">
        {step === 1 && (
          <Step1CompanyDetails
            data={state.company}
            onChange={(company) => setState(s => ({ ...s, company }))}
          />
        )}
        {step === 2 && (
          <Step2VATStatus
            vatRegistered={state.vatRegistered}
            onChange={(vatRegistered) => setState(s => ({ ...s, vatRegistered }))}
          />
        )}
        {step === 3 && (
          <Step3ChooseExperience
            mode={state.experienceMode}
            onChange={(experienceMode) => setState(s => ({ ...s, experienceMode }))}
          />
        )}
        {step === 4 && (
          <Step4FiscalCalendar
            period={state.periodLength}
            fiscalYearEnd={state.fiscalYearEnd}
            onPeriodChange={(periodLength) => setState(s => ({ ...s, periodLength }))}
            onDateChange={(fiscalYearEnd) => setState(s => ({ ...s, fiscalYearEnd }))}
          />
        )}
        {step === 5 && (
          <Step5ChartOfAccounts
            path={state.coaPath}
            onChange={(coaPath) => setState(s => ({ ...s, coaPath }))}
          />
        )}
        {step === 6 && (
          <Step6Contacts
            contacts={state.contacts}
            onChange={(contacts) => setState(s => ({ ...s, contacts }))}
          />
        )}
      </div>

      {/* Navigation bar */}
      <div className="sticky bottom-0 bg-[#f4f7fe] border-t border-[#e9edff] px-4 py-5">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          {/* Go Back */}
          <button
            type="button"
            onClick={goBack}
            disabled={step === 1 || loading}
            className="h-11 px-8 rounded-lg bg-[#94a3b8] text-white text-base font-medium shadow-md hover:bg-[#64748b] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Go Back
          </button>

          <div className="flex items-center gap-4">
            {/* Save & Continue Later */}
            <button
              type="button"
              disabled={loading}
              className="h-11 px-6 rounded-lg bg-[#94a3b8] text-white text-base font-medium shadow-md hover:bg-[#64748b] disabled:opacity-40 transition-colors"
            >
              Save &amp; Continue later
            </button>

            {/* Continue / Finish */}
            {step === 6 ? (
              <button
                type="button"
                onClick={handleFinish}
                disabled={loading}
                className="flex items-center justify-center gap-2 h-11 px-8 rounded-lg bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-base font-medium shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    <span>Setting up workspace...</span>
                  </>
                ) : (
                  "Finish"
                )}
              </button>
            ) : (
              <button
                type="button"
                onClick={goNext}
                disabled={loading}
                className="flex items-center gap-2 h-11 px-8 rounded-lg bg-[#0f766e] hover:bg-[#0d6460] text-white text-base font-medium shadow-md disabled:opacity-50 transition-colors"
              >
                Continue
                <Image src="/assets/arrow-right.svg" alt="" width={12} height={12} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
