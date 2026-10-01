export default function SecurityPage() {
  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div>
        <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">Security Log</h1>
        <p className="text-[#434655] text-base mt-1">Monitor login activity and access events.</p>
      </div>

      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f7f9fb]">
          <p className="text-sm font-semibold text-[#434655]">Recent events</p>
        </div>
        {[
          { event: "Successful login", ip: "197.255.x.x", device: "Chrome · Windows", time: "Just now" },
          { event: "Password changed", ip: "197.255.x.x", device: "Chrome · Windows", time: "3 days ago" },
          { event: "Two-factor enabled", ip: "197.255.x.x", device: "Mobile · iOS", time: "1 week ago" },
        ].map((entry, i) => (
          <div key={i} className="flex items-center gap-6 px-6 py-4 border-b border-[#c3c6d7] last:border-0">
            <div className="flex-1">
              <p className="text-sm font-semibold text-[#141b2b]">{entry.event}</p>
              <p className="text-xs text-[#434655] mt-0.5">{entry.device} · {entry.ip}</p>
            </div>
            <p className="text-xs text-[#94a3b8] whitespace-nowrap">{entry.time}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
