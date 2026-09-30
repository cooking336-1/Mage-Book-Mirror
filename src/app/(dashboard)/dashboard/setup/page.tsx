export default function SetupPage() {
  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div>
        <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">Setup</h1>
        <p className="text-[#434655] text-base mt-1">Configure your business settings and preferences.</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {[
          { title: "Company Profile", desc: "Business name, address, logo, and contact details." },
          { title: "Tax Settings", desc: "VAT rates, GRA TIN, and tax configuration." },
          { title: "Currency & Locale", desc: "Set your default currency and date format." },
          { title: "Integrations", desc: "Connect bank feeds, payment gateways, and apps." },
          { title: "Email Templates", desc: "Customise invoice and receipt email templates." },
          { title: "Notifications", desc: "Choose what alerts and reminders you receive." },
        ].map((item) => (
          <div
            key={item.title}
            className="bg-white border border-[#c3c6d7] rounded-xl p-6 hover:border-[#2563eb] cursor-pointer transition-colors"
          >
            <p className="font-bold text-[#141b2b] text-base">{item.title}</p>
            <p className="text-[#434655] text-sm mt-1 leading-5">{item.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
