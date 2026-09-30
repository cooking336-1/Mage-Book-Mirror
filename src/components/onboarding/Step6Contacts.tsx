"use client";

import Image from "next/image";
import { formatGraTin, getGraTinError } from "@/lib/formatters";

type ContactType = "Customer" | "Supplier" | "Both";

interface Contact {
  id: string;
  name: string;
  type: ContactType;
  contactInfo: string;
  tin: string;
}

interface Props {
  contacts: Contact[];
  onChange: (contacts: Contact[]) => void;
}

const newContact = (): Contact => ({
  id: Math.random().toString(36).slice(2),
  name: "",
  type: "Customer",
  contactInfo: "",
  tin: "",
});

export default function Step6Contacts({ contacts, onChange }: Props) {
  const addContact = () => onChange([...contacts, newContact()]);

  const updateContact = (id: string, field: keyof Contact, value: string) => {
    onChange(contacts.map(c => c.id === id ? { ...c, [field]: value } : c));
  };

  const removeContact = (id: string) => {
    onChange(contacts.filter(c => c.id !== id));
  };

  return (
    <div className="bg-white rounded-xl border border-[#c3c6d7] shadow-sm overflow-hidden">
      {/* Header */}
      <div className="text-center pt-8 pb-2 px-8">
        <h2 className="text-[28px] font-bold text-[#141b2b]">Who do you work with?</h2>
        <p className="text-sm text-[#434655] mt-2 max-w-md mx-auto">
          Adding your customers and suppliers now helps us categorize your initial transactions and
          historical data correctly.
        </p>
      </div>

      <div className="px-8 pb-8 pt-6">
        {/* Contacts card */}
        <div className="border border-[#c3c6d7] rounded-xl overflow-hidden">
          {/* Card header */}
          <div className="flex items-center justify-between px-6 py-4 bg-[#f9f9ff] border-b border-[#c3c6d7]">
            <h3 className="text-base text-[#141b2b]">Add Contacts</h3>
            <button
              type="button"
              onClick={addContact}
              className="flex items-center gap-1.5 text-[#004ac6] text-sm hover:underline"
            >
              <Image src="/assets/add-icon.svg" alt="" width={11} height={11} />
              Add another
            </button>
          </div>

          {/* Contact rows */}
          <div className="p-4 space-y-3">
            {contacts.map((contact, idx) => (
              <div
                key={contact.id}
                className={`rounded-lg border border-[#c3c6d7] p-4 ${
                  idx === 0 ? "bg-[#f1f3ff]" : "bg-white opacity-60"
                }`}
              >
                <div className="grid grid-cols-4 gap-3">
                  {/* Name */}
                  <div className="space-y-1">
                    <label className="text-sm text-[#434655]">Contact Name</label>
                    <input
                      type="text"
                      value={contact.name}
                      onChange={e => updateContact(contact.id, "name", e.target.value)}
                      placeholder="e.g. Ama Mensah"
                      className="w-full h-10 px-3 bg-[#f9f9ff] border border-[#c3c6d7] rounded-lg text-sm text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-1 focus:ring-[#2563eb]"
                    />
                  </div>

                  {/* Type */}
                  <div className="space-y-1">
                    <label className="text-sm text-[#434655]">Type</label>
                    <select
                      value={contact.type}
                      onChange={e => updateContact(contact.id, "type", e.target.value)}
                      className="w-full h-10 px-3 bg-[#f9f9ff] border border-[#c3c6d7] rounded-lg text-sm text-[#141b2b] focus:outline-none focus:ring-1 focus:ring-[#2563eb] appearance-none"
                    >
                      <option>Customer</option>
                      <option>Supplier</option>
                      <option>Both</option>
                    </select>
                  </div>

                  {/* Phone/Email */}
                  <div className="space-y-1">
                    <label className="text-sm text-[#434655]">Phone or Email</label>
                    <input
                      type="text"
                      value={contact.contactInfo}
                      onChange={e => updateContact(contact.id, "contactInfo", e.target.value)}
                      placeholder="024 000 0000"
                      className="w-full h-10 px-3 bg-[#f9f9ff] border border-[#c3c6d7] rounded-lg text-sm text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-1 focus:ring-[#2563eb]"
                    />
                  </div>

                  {/* TIN */}
                  <div className="space-y-1">
                    <label className="text-sm text-[#434655]">TIN (Optional)</label>
                    <input
                      type="text"
                      value={contact.tin}
                      onChange={e => updateContact(contact.id, "tin", e.target.value)}
                      onBlur={() => updateContact(contact.id, "tin", formatGraTin(contact.tin))}
                      placeholder="P0012345678"
                      className={`w-full h-10 px-3 bg-[#f9f9ff] border ${
                        contact.tin && getGraTinError(contact.tin)
                          ? "border-red-400 focus:ring-red-400"
                          : "border-[#c3c6d7] focus:ring-[#2563eb]"
                      } rounded-lg text-sm text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-1 font-mono uppercase`}
                    />
                    {contact.tin && getGraTinError(contact.tin) && (
                      <p className="text-[11px] text-red-500">
                        {getGraTinError(contact.tin)}
                      </p>
                    )}
                  </div>
                </div>

                {idx > 0 && (
                  <button
                    type="button"
                    onClick={() => removeContact(contact.id)}
                    className="mt-2 text-xs text-red-500 hover:underline"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Pro-tip */}
          <div className="mx-4 mb-4 bg-[#dbe1ff] border border-[rgba(0,62,168,0.1)] rounded-lg px-4 py-3 flex gap-3">
            <Image src="/assets/protip-icon.svg" alt="" width={20} height={20} className="shrink-0 mt-0.5" />
            <p className="text-sm text-[#003ea8]">
              <span className="font-bold">Pro-tip:</span>{" "}
              <span className="font-normal">
                You can also bulk import your contacts via CSV or Excel once you finish the setup wizard.
              </span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export type { Contact };
