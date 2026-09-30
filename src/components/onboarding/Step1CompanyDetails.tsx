"use client";

import { useState } from "react";
import {
  formatGhanaCard,
  formatGraTin,
  getGhanaCardError,
  getGraTinError,
} from "@/lib/formatters";

interface Step1Data {
  companyName: string;
  businessTin: string;
  ghanaCard: string;
  address: string;
  phone: string;
  email: string;
}

interface Props {
  data: Step1Data;
  onChange: (data: Step1Data) => void;
}

export default function Step1CompanyDetails({ data, onChange }: Props) {
  const [tinTouched, setTinTouched] = useState(false);
  const [cardTouched, setCardTouched] = useState(false);

  const set = (field: keyof Step1Data) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    onChange({ ...data, [field]: e.target.value });

  const handleTinBlur = () => {
    setTinTouched(true);
    const formatted = formatGraTin(data.businessTin);
    onChange({ ...data, businessTin: formatted });
  };

  const handleCardBlur = () => {
    setCardTouched(true);
    const formatted = formatGhanaCard(data.ghanaCard);
    onChange({ ...data, ghanaCard: formatted });
  };

  const tinError = tinTouched && data.businessTin ? getGraTinError(data.businessTin) : null;
  const cardError = cardTouched && data.ghanaCard ? getGhanaCardError(data.ghanaCard) : null;

  return (
    <div className="bg-white rounded-xl border border-[#c3c6d7] shadow-sm overflow-hidden">
      {/* Card header */}
      <div className="text-center pt-8 pb-4 px-8">
        <h2 className="text-[28px] font-bold text-[#141b2b]">Company Details</h2>
        <p className="text-sm text-[#555f6d] mt-2">
          Please provide the following legal information to register your business in our system.
        </p>
      </div>

      {/* Form */}
      <div className="px-16 pb-8 space-y-5">
        {/* Company Name */}
        <div>
          <label className="block text-sm text-[#141b2b] mb-2">Company Name</label>
          <input
            type="text"
            value={data.companyName}
            onChange={set("companyName")}
            placeholder="e.g. Acme Ghana Ltd."
            className="w-full h-12 px-4 bg-[#f9f9ff] border border-[#c3c6d7] rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
          />
        </div>

        {/* Business TIN & Ghana Card */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-[#141b2b] mb-2">Business TIN</label>
            <input
              type="text"
              value={data.businessTin}
              onChange={set("businessTin")}
              onBlur={handleTinBlur}
              placeholder="C0001234567"
              className={`w-full h-12 px-4 bg-[#f9f9ff] border ${
                tinError ? "border-red-400 focus:ring-red-400" : "border-[#c3c6d7] focus:ring-[#2563eb]"
              } rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 font-mono uppercase`}
            />
            {tinError && <p className="text-xs text-red-600 mt-1">{tinError}</p>}
          </div>
          <div>
            <label className="block text-sm text-[#141b2b] mb-2">Ghana Card Number</label>
            <input
              type="text"
              value={data.ghanaCard}
              onChange={set("ghanaCard")}
              onBlur={handleCardBlur}
              placeholder="GHA-000000000-0"
              className={`w-full h-12 px-4 bg-[#f9f9ff] border ${
                cardError ? "border-red-400 focus:ring-red-400" : "border-[#c3c6d7] focus:ring-[#2563eb]"
              } rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 font-mono uppercase`}
            />
            {cardError && <p className="text-xs text-red-600 mt-1">{cardError}</p>}
          </div>
        </div>

        {/* Physical Address */}
        <div>
          <label className="block text-sm text-[#141b2b] mb-2">Physical Address</label>
          <textarea
            value={data.address}
            onChange={set("address")}
            placeholder="No. 24 Spintex Road, Accra, Ghana"
            rows={3}
            className="w-full px-4 py-3 bg-[#f9f9ff] border border-[#c3c6d7] rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#2563eb] resize-none"
          />
        </div>

        {/* Phone & Email */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-[#141b2b] mb-2">Phone Number</label>
            <div className="flex">
              <span className="inline-flex items-center px-3 bg-[#f9f9ff] border border-r-0 border-[#c3c6d7] rounded-l-lg text-sm text-[#555f6d]">
                +233
              </span>
              <input
                type="tel"
                value={data.phone}
                onChange={set("phone")}
                placeholder="24 000 0000"
                className="flex-1 h-12 px-4 bg-[#f9f9ff] border border-[#c3c6d7] rounded-r-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm text-[#141b2b] mb-2">Business Email</label>
            <input
              type="email"
              value={data.email}
              onChange={set("email")}
              placeholder="contact@company.com"
              className="w-full h-12 px-4 bg-[#f9f9ff] border border-[#c3c6d7] rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export type { Step1Data };
