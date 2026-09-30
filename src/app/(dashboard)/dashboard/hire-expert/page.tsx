export default function HireExpertPage() {
  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div>
        <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">Hire an Expert</h1>
        <p className="text-[#434655] text-base mt-1">
          Work with certified Ghanaian accountants, tax professionals, and bookkeepers.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {[
          {
            title: "GRA Tax Filing & Compliance",
            desc: "Get help with VAT, PAYE, and annual corporate income tax returns from a licensed tax practitioner.",
          },
          {
            title: "Bookkeeping & Catch-up",
            desc: "Have a professional reconcile your bank feeds, organize your receipts, and balance your books.",
          },
          {
            title: "Payroll Setup & Management",
            desc: "Ensure complete compliance with SSNIT and GRA withholding requirements with expert setup.",
          },
          {
            title: "Financial Advisory & Audit Prep",
            desc: "Get prepared for audits and receive strategic advice to improve your business cash flow.",
          },
        ].map((item) => (
          <div
            key={item.title}
            className="bg-white border border-[#c3c6d7] rounded-xl p-6 flex flex-col justify-between"
          >
            <div>
              <p className="font-bold text-[#141b2b] text-base">{item.title}</p>
              <p className="text-[#434655] text-sm mt-2 leading-relaxed">{item.desc}</p>
            </div>
            <button
              type="button"
              className="mt-6 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-medium px-4 h-9 rounded-lg transition-colors self-start"
            >
              Find an expert &rarr;
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
