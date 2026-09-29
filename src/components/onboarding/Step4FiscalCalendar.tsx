"use client";

import { useState } from "react";
import Image from "next/image";

type PeriodLength = "monthly" | "quarterly" | "annually";

interface Props {
  period: PeriodLength;
  fiscalYearEnd: Date;
  onPeriodChange: (p: PeriodLength) => void;
  onDateChange: (d: Date) => void;
}

const MONTHS = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];
const DAYS_OF_WEEK = ["S","M","T","W","T","F","S"];

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

export default function Step4FiscalCalendar({ period, fiscalYearEnd, onPeriodChange, onDateChange }: Props) {
  const [calYear, setCalYear] = useState(fiscalYearEnd.getFullYear());
  const [calMonth, setCalMonth] = useState(fiscalYearEnd.getMonth());

  const daysInMonth = getDaysInMonth(calYear, calMonth);
  const firstDay = getFirstDayOfMonth(calYear, calMonth);
  const selectedDate = fiscalYearEnd;

  const handleDateSelect = (day: number) => {
    onDateChange(new Date(calYear, calMonth, day));
  };

  const prevMonth = () => {
    if (calMonth === 0) { setCalYear(y => y - 1); setCalMonth(11); }
    else setCalMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (calMonth === 11) { setCalYear(y => y + 1); setCalMonth(0); }
    else setCalMonth(m => m + 1);
  };

  const formatDate = (d: Date) =>
    `${MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;

  const periods: { key: PeriodLength; label: string; desc: string; icon: string }[] = [
    { key: "monthly", label: "Monthly", desc: "Standard statutory cadence for GRA VAT & PAYE filings.", icon: "/assets/monthly.svg" },
    { key: "quarterly", label: "Quarterly", desc: "For quarterly accounting review cycles.", icon: "/assets/quarterly.svg" },
    { key: "annually", label: "Annually", desc: "Simplest for small, stable businesses.", icon: "/assets/annually.svg" },
  ];

  return (
    <div className="bg-white rounded-xl border border-[#c3c6d7] shadow-sm overflow-hidden">
      {/* Header */}
      <div className="text-center pt-8 pb-2 px-8">
        <h2 className="text-[28px] font-bold text-[#141b2b]">Fiscal Calendar Setup</h2>
        <p className="text-sm text-[#434655] mt-2">
          Define how your financial periods are tracked and closed.
        </p>
      </div>

      <div className="px-8 pb-8 space-y-6 pt-6">
        {/* Period length */}
        <div>
          <p className="text-xs font-semibold text-[#434655] uppercase tracking-widest mb-3">
            ACCOUNTING PERIOD LENGTH
          </p>
          <div className="grid grid-cols-3 gap-4">
            {periods.map(({ key, label, desc, icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => onPeriodChange(key)}
                className={`text-left p-4 rounded-lg border-2 transition-all ${
                  period === key
                    ? "border-[#2563eb] bg-[#f1f3ff] shadow-[0_0_0_2px_#2563eb]"
                    : "border-[#c3c6d7] bg-[#f9f9ff] hover:border-[#2563eb]"
                }`}
              >
                <Image src={icon} alt="" width={20} height={24} className="mb-2" />
                <p className="font-semibold text-sm text-[#141b2b]">{label}</p>
                <p className="text-xs text-[#434655] mt-1">{desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Fiscal year-end date */}
        <div>
          <p className="text-xs font-semibold text-[#434655] uppercase tracking-widest mb-1">
            FISCAL YEAR-END DATE
          </p>
          <p className="text-sm text-[#434655] mb-4">
            Select the date your company&apos;s fiscal year officially concludes.
          </p>
          <div className="grid grid-cols-2 gap-6">
            {/* Selected date display */}
            <div>
              <p className="text-xs font-medium text-[#434655] tracking-wide mb-2">Selected Date</p>
              <div className="flex items-center gap-3 h-[74px] px-4 bg-[#f9f9ff] border border-[#c3c6d7] rounded-lg">
                <Image src="/assets/calendar-field.svg" alt="" width={34} height={20} />
                <span className="text-base text-[#141b2b]">{formatDate(selectedDate)}</span>
              </div>
            </div>

            {/* Calendar picker */}
            <div className="bg-[#f9f9ff] border border-[#c3c6d7] rounded-xl p-4">
              {/* Month/Year nav */}
              <div className="flex items-center justify-between mb-3">
                <button type="button" onClick={prevMonth} className="text-[#141b2b] hover:text-[#2563eb] p-1">
                  <svg width="8" height="12" viewBox="0 0 8 12" fill="none">
                    <path d="M7 1L1 6L7 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </button>
                <span className="text-sm font-semibold text-[#141b2b]">
                  {MONTHS[calMonth]} {calYear}
                </span>
                <button type="button" onClick={nextMonth} className="text-[#141b2b] hover:text-[#2563eb] p-1">
                  <svg width="8" height="12" viewBox="0 0 8 12" fill="none">
                    <path d="M1 1L7 6L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>

              {/* Day headers */}
              <div className="grid grid-cols-7 mb-1">
                {DAYS_OF_WEEK.map((d, i) => (
                  <div key={i} className="text-center text-xs font-medium text-[#c3c6d7] py-1">
                    {d}
                  </div>
                ))}
              </div>

              {/* Calendar grid */}
              <div className="grid grid-cols-7 gap-0.5">
                {Array.from({ length: firstDay }).map((_, i) => (
                  <div key={`empty-${i}`} />
                ))}
                {Array.from({ length: daysInMonth }).map((_, i) => {
                  const day = i + 1;
                  const isSelected =
                    selectedDate.getDate() === day &&
                    selectedDate.getMonth() === calMonth &&
                    selectedDate.getFullYear() === calYear;
                  return (
                    <button
                      key={day}
                      type="button"
                      onClick={() => handleDateSelect(day)}
                      className={`h-10 w-full text-sm rounded-full transition-colors ${
                        isSelected
                          ? "bg-[#004ac6] text-white"
                          : "text-[#141b2b] hover:bg-[#e9edff]"
                      }`}
                    >
                      {day}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Note */}
        <div className="bg-[#d6e0f1] rounded-lg px-4 py-3 flex gap-3 items-center">
          <Image src="/assets/note-info.svg" alt="" width={36} height={20} className="shrink-0" />
          <p className="text-sm text-[#596372]">
            Your books will automatically close at the end of each selected period.
          </p>
        </div>
      </div>
    </div>
  );
}

export type { PeriodLength };
