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

  const [state, setState] = useState<OnboardingState>({
    company: { companyName: "", businessTin: "", ghanaCard: "", address: "", phone: "", email: "" },
    vatRegistered: null,
    experienceMode: null,
    periodLength: "monthly",
    fiscalYearEnd: new Date(new Date().getFullYear(), 11, 31), // Dec 31
    coaPath: null,
    contacts: [{ id: "default", name: "", type: "Customer", contactInfo: "", tin: "" }],
  });

  const goBack = () => setStep(s => Math.max(1, s - 1));
  const goNext = () => setStep(s => Math.min(TOTAL_STEPS, s + 1));

  const handleFinish = () => {
    // TODO: submit onboarding data to API
    router.push("/dashboard");
  };

  const isLastStep = step === TOTAL_STEPS;

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
            disabled={step === 1}
            className="h-11 px-8 rounded-lg bg-[#94a3b8] text-white text-base font-medium shadow-md hover:bg-[#64748b] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Go Back
          </button>

          <div className="flex items-center gap-4">
            {/* Save & Continue Later */}
            <button
              type="button"
              className="h-11 px-6 rounded-lg bg-[#94a3b8] text-white text-base font-medium shadow-md hover:bg-[#64748b] transition-colors"
            >
              Save &amp; Continue later
            </button>

            {/* Continue / Finish */}
            {step === 6 ? (
              <button
                type="button"
                onClick={handleFinish}
                className="h-11 px-8 rounded-lg bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-base font-medium shadow-md transition-colors"
              >
                Finish
              </button>
            ) : (
              <button
                type="button"
                onClick={goNext}
                className="flex items-center gap-2 h-11 px-8 rounded-lg bg-[#0f766e] hover:bg-[#0d6460] text-white text-base font-medium shadow-md transition-colors"
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
