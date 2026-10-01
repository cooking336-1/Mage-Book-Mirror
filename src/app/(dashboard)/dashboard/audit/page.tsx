"use client";

import { useMode } from "@/contexts/ModeContext";

export default function AuditPage() {
  const { mode } = useMode();
  const title = mode === "simple" ? "Activity Log" : "Audit Trail";
  const subtitle =
    mode === "simple"
      ? "A log of everything that has happened in your account."
      : "Complete audit trail of all system actions and changes.";

  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div>
        <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">{title}</h1>
        <p className="text-[#434655] text-base mt-1">{subtitle}</p>
      </div>

      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f7f9fb]">
          <p className="text-sm font-semibold text-[#434655]">Today</p>
        </div>
        {[
          { user: "Ama Osei", action: "Recorded a payment of GH¢ 4,200 from Kojo Enterprises", time: "2 min ago" },
          { user: "Ama Osei", action: "Sent quote #882 to Tema Logistics Ltd", time: "45 min ago" },
          { user: "System", action: "Automatic backup completed", time: "1 hr ago" },
        ].map((entry, i) => (
          <div key={i} className="flex items-start gap-4 px-6 py-4 border-b border-[#c3c6d7] last:border-0">
            <div className="w-8 h-8 rounded-full bg-[#dbeafe] flex items-center justify-center text-[#2563eb] text-xs font-bold shrink-0">
              {entry.user[0]}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-[#141b2b]">{entry.user}</p>
              <p className="text-sm text-[#434655]">{entry.action}</p>
            </div>
            <p className="text-xs text-[#94a3b8] whitespace-nowrap">{entry.time}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
