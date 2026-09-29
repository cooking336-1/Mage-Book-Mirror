import Image from "next/image";

interface Props {
  vatRegistered: boolean | null;
  onChange: (val: boolean) => void;
}

export default function Step2VATStatus({ vatRegistered, onChange }: Props) {
  return (
    <div className="bg-white rounded-xl border border-[#c3c6d7] shadow-sm overflow-hidden">
      {/* Header */}
      <div className="text-center pt-8 pb-6 px-8">
        <h2 className="text-[28px] font-bold text-[#141b2b]">VAT Status</h2>
        <p className="text-sm text-[#434655] mt-2">
          Select your business&apos;s current VAT registration status in Ghana.
        </p>
      </div>

      {/* Options */}
      <div className="px-8 pb-6 grid grid-cols-2 gap-6">
        {/* Yes option */}
        <button
          type="button"
          onClick={() => onChange(true)}
          className={`relative text-left p-6 rounded-xl border-2 transition-all ${
            vatRegistered === true
              ? "border-[#004ac6] bg-[rgba(0,74,198,0.05)]"
              : "border-[#c3c6d7] bg-[#f9f9ff] hover:border-[#004ac6]"
          }`}
        >
          {vatRegistered === true && (
            <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-[#004ac6] flex items-center justify-center">
              <Image src="/assets/checkmark-white.svg" alt="selected" width={12} height={9} />
            </div>
          )}
          <div className="w-12 h-12 rounded-lg bg-[#004ac6] flex items-center justify-center mb-4">
            <Image src="/assets/vat-yes-icon.svg" alt="" width={24} height={24} />
          </div>
          <h3 className="text-xl font-semibold text-[#141b2b] mb-2">
            Yes, I&apos;m VAT-registered
          </h3>
          <p className="text-sm text-[#434655]">
            My business is registered for Value Added Tax with the GRA.
          </p>
        </button>

        {/* No option */}
        <button
          type="button"
          onClick={() => onChange(false)}
          className={`relative text-left p-6 rounded-xl border-2 transition-all ${
            vatRegistered === false
              ? "border-[#004ac6] bg-[rgba(0,74,198,0.05)]"
              : "border-[#c3c6d7] bg-[#f9f9ff] hover:border-[#004ac6]"
          }`}
        >
          {vatRegistered === false && (
            <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-[#004ac6] flex items-center justify-center">
              <Image src="/assets/checkmark-white.svg" alt="selected" width={12} height={9} />
            </div>
          )}
          <div className="w-12 h-12 rounded-lg bg-[#e1e8fd] flex items-center justify-center mb-4">
            <Image src="/assets/vat-no-icon.svg" alt="" width={24} height={24} />
          </div>
          <h3 className="text-xl font-semibold text-[#141b2b] mb-2">
            No, I&apos;m not VAT-registered
          </h3>
          <p className="text-sm text-[#434655]">
            My business is not currently required to be VAT-registered.
          </p>
        </button>
      </div>

      {/* Info note */}
      <div className="mx-8 mb-8 bg-[#f1f3ff] border border-[rgba(195,198,215,0.5)] rounded-lg p-4 flex gap-3">
        <Image src="/assets/vat-info.svg" alt="" width={20} height={20} className="shrink-0 mt-0.5" />
        <p className="text-sm text-[#434655]">
          VAT registration is mandatory in Ghana for businesses making taxable supplies exceeding GHS 750,000
          over 12 months under the Value Added Tax Act, 2025 (Act 1151). Choosing the correct status ensures
          your tax calculations and invoices comply with GRA standards.
        </p>
      </div>
    </div>
  );
}
