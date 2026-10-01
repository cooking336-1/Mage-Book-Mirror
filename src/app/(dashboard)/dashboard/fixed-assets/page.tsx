"use client";

import { useMode } from "@/contexts/ModeContext";

export default function FixedAssetsPage() {
  const { mode } = useMode();
  const title = mode === "simple" ? "Things My Business Owns" : "Fixed Assets";
  const subtitle =
    mode === "simple"
      ? "Equipment, vehicles, computers, and furniture owned by your business."
      : "Fixed asset register, depreciation schedules, and book values.";

  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">{title}</h1>
          <p className="text-[#434655] text-base mt-1">{subtitle}</p>
        </div>
        <button
          type="button"
          className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-medium px-4 h-10 rounded-lg shadow-sm transition-colors"
        >
          {mode === "simple" ? "+ Add Business Property" : "+ Add Asset"}
        </button>
      </div>

      <div className="bg-white border border-[#c3c6d7] rounded-xl p-12 text-center text-[#434655]">
        <p className="font-semibold text-[#141b2b] text-lg mb-1">No assets registered</p>
        <p className="text-sm">
          {mode === "simple"
            ? "Record vehicles, computers, machinery, and tools here."
            : "Asset records and depreciation schedules will appear here."}
        </p>
      </div>
    </div>
  );
}
