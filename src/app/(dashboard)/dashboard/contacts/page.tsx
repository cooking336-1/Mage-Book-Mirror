"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import apiClient from "@/lib/apiClient";
import { formatGhanaCard, formatGraTin } from "@/lib/formatters";

interface Contact {
  id: string;
  name: string;
  contact_type: "CUSTOMER" | "SUPPLIER";
  tin?: string;
  ghana_card_number?: string;
  billing_address?: string;
  phone?: string;
  email?: string;
  currency?: string;
  is_active: boolean;
  created_at: string;
}

export default function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formState, setFormState] = useState({
    name: "",
    contact_type: "CUSTOMER" as "CUSTOMER" | "SUPPLIER",
    tin: "",
    ghana_card_number: "",
    phone: "",
    email: "",
    billing_address: "",
  });

  const fetchContacts = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.get<Contact[] | { results: Contact[] }>("/api/v1/contacts/");
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setContacts(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load contacts.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let isCancelled = false;
    apiClient
      .get<Contact[] | { results: Contact[] }>("/api/v1/contacts/")
      .then((res) => {
        if (!isCancelled) {
          const data = Array.isArray(res.data) ? res.data : res.data.results || [];
          setContacts(data);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : "Failed to load contacts.";
          setError(msg);
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  const handleCreateContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formState.name.trim()) {
      setFormError("Contact name is required.");
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    try {
      const payload: Record<string, string> = {
        name: formState.name.trim(),
        contact_type: formState.contact_type,
      };
      if (formState.tin.trim()) payload.tin = formState.tin.trim().toUpperCase();
      if (formState.ghana_card_number.trim()) payload.ghana_card_number = formState.ghana_card_number.trim().toUpperCase();
      if (formState.phone.trim()) payload.phone = formState.phone.trim();
      if (formState.email.trim()) payload.email = formState.email.trim();
      if (formState.billing_address.trim()) payload.billing_address = formState.billing_address.trim();

      await apiClient.post("/api/v1/contacts/", payload);
      setIsModalOpen(false);
      setFormState({
        name: "",
        contact_type: "CUSTOMER",
        tin: "",
        ghana_card_number: "",
        phone: "",
        email: "",
        billing_address: "",
      });
      fetchContacts();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: Record<string, string[] | string> } };
      const data = axiosErr.response?.data;
      if (data && typeof data === "object") {
        const firstErr = Object.values(data).flat()[0];
        setFormError(String(firstErr || "Failed to create contact."));
      } else {
        setFormError("Failed to create contact. Please verify the input values.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
            Customers &amp; Suppliers
          </h1>
          <p className="text-[#434655] text-base mt-1">
            Manage your business contacts, statutory TINs, and credit terms.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors cursor-pointer"
        >
          + Add Contact
        </button>
      </div>

      {isLoading ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-12 text-center text-[#434655]">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-[#2563eb] border-r-transparent mb-3" />
          <p className="text-sm font-medium">Loading contacts...</p>
        </div>
      ) : error ? (
        <div className="bg-[#fef2f2] border border-[#f87171] rounded-xl p-6 text-center text-[#991b1b]">
          <p className="font-semibold text-base mb-1">Failed to load contacts</p>
          <p className="text-sm mb-4">{error}</p>
          <button
            type="button"
            onClick={fetchContacts}
            className="bg-[#dc2626] hover:bg-[#b91c1c] text-white text-xs font-semibold px-4 py-2 rounded-md"
          >
            Retry
          </button>
        </div>
      ) : contacts.length === 0 ? (
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-12 text-center text-[#434655]">
          <p className="font-semibold text-[#141b2b] text-lg mb-1">No contacts yet</p>
          <p className="text-sm">Add customers and suppliers to begin issuing invoices and bills.</p>
        </div>
      ) : (
        <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[#f8f9fa] border-b border-[#e2e8f0] text-xs font-semibold uppercase tracking-wider text-[#475569]">
                <tr>
                  <th className="py-3.5 px-6">Name</th>
                  <th className="py-3.5 px-6">Type</th>
                  <th className="py-3.5 px-6">TIN / Ghana Card</th>
                  <th className="py-3.5 px-6">Phone / Email</th>
                  <th className="py-3.5 px-6">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-[#1e293b]">
                {contacts.map((contact) => (
                  <tr key={contact.id} className="hover:bg-[#f8fafc] transition-colors">
                    <td className="py-4 px-6 font-semibold text-[#0f172a]">{contact.name}</td>
                    <td className="py-4 px-6">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          contact.contact_type === "CUSTOMER"
                            ? "bg-[#dbeafe] text-[#1e40af]"
                            : "bg-[#fef3c7] text-[#92400e]"
                        }`}
                      >
                        {contact.contact_type === "CUSTOMER" ? "Customer" : "Supplier"}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-xs text-[#64748b]">
                      <div>{contact.tin ? `TIN: ${contact.tin}` : "—"}</div>
                      {contact.ghana_card_number && <div>Card: {contact.ghana_card_number}</div>}
                    </td>
                    <td className="py-4 px-6 text-xs text-[#64748b]">
                      <div>{contact.phone || "—"}</div>
                      {contact.email && <div className="text-[#3b82f6]">{contact.email}</div>}
                    </td>
                    <td className="py-4 px-6">
                      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-[#dcfce7] text-[#166534]">
                        Active
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add Contact Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-4 border-b border-[#e2e8f0]">
              <h2 className="text-xl font-bold text-[#0f172a]">Add New Contact</h2>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-[#94a3b8] hover:text-[#0f172a] text-lg font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            {formError && (
              <div className="mt-4 p-3 bg-[#fef2f2] border border-[#fca5a5] rounded-lg text-xs text-[#991b1b]">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateContact} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#475569] uppercase mb-1">
                  Full Name / Business Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Accra Mall Supermarket"
                  value={formState.name}
                  onChange={(e) => setFormState({ ...formState, name: e.target.value })}
                  className="w-full h-10 px-3 border border-[#cbd5e1] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#475569] uppercase mb-1">
                  Contact Type
                </label>
                <select
                  value={formState.contact_type}
                  onChange={(e) =>
                    setFormState({
                      ...formState,
                      contact_type: e.target.value as "CUSTOMER" | "SUPPLIER",
                    })
                  }
                  className="w-full h-10 px-3 border border-[#cbd5e1] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                >
                  <option value="CUSTOMER">Customer (Debtor / Client)</option>
                  <option value="SUPPLIER">Supplier (Creditor / Vendor)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#475569] uppercase mb-1">
                    Ghana TIN (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. C0001234567"
                    value={formState.tin}
                    onChange={(e) => setFormState({ ...formState, tin: e.target.value })}
                    onBlur={(e) => setFormState({ ...formState, tin: formatGraTin(e.target.value) })}
                    className="w-full h-10 px-3 border border-[#cbd5e1] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#475569] uppercase mb-1">
                    Ghana Card PIN (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="GHA-123456789-0"
                    value={formState.ghana_card_number}
                    onChange={(e) => setFormState({ ...formState, ghana_card_number: e.target.value })}
                    onBlur={(e) =>
                      setFormState({
                        ...formState,
                        ghana_card_number: formatGhanaCard(e.target.value),
                      })
                    }
                    className="w-full h-10 px-3 border border-[#cbd5e1] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#475569] uppercase mb-1">
                    Phone Number
                  </label>
                  <input
                    type="tel"
                    placeholder="e.g. 0244123456"
                    value={formState.phone}
                    onChange={(e) => setFormState({ ...formState, phone: e.target.value })}
                    className="w-full h-10 px-3 border border-[#cbd5e1] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#475569] uppercase mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    placeholder="accounts@example.com"
                    value={formState.email}
                    onChange={(e) => setFormState({ ...formState, email: e.target.value })}
                    className="w-full h-10 px-3 border border-[#cbd5e1] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#475569] uppercase mb-1">
                  Billing Address
                </label>
                <textarea
                  rows={2}
                  placeholder="Street, City, Digital Address (e.g. GA-183-9022)"
                  value={formState.billing_address}
                  onChange={(e) => setFormState({ ...formState, billing_address: e.target.value })}
                  className="w-full p-2.5 border border-[#cbd5e1] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[#e2e8f0]">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-[#cbd5e1] rounded-lg text-sm font-semibold text-[#475569] hover:bg-[#f1f5f9] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white rounded-lg text-sm font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50"
                >
                  {isSubmitting ? "Saving..." : "Save Contact"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <footer className="border-t border-[#c3c6d7] mt-4 py-6 flex items-center justify-between text-[12px] font-medium text-[#434655] tracking-[0.24px]">
        <p>© 2026 Mage Books. All rights reserved.</p>
        <div className="flex items-center gap-6">
          <Link href="/legal/privacy" className="hover:underline">Privacy Policy</Link>
          <Link href="/legal/terms" className="hover:underline">Terms of Service</Link>
          <Link href="/legal/support" className="hover:underline">Help Center</Link>
        </div>
      </footer>
    </div>
  );
}
