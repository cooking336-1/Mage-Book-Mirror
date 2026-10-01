import Link from "next/link";
import Logo from "@/components/Logo";

interface PublicInvoiceLine {
  id?: string;
  description: string;
  quantity: number;
  unit_price: string | number;
  line_total: string | number;
  is_taxable: boolean;
}

interface PublicInvoiceData {
  invoice_number: string;
  payment_reference: string;
  share_token: string;
  issue_date: string;
  due_date: string;
  status: string;
  currency: string;
  subtotal_amount: string | number;
  vat_amount: string | number;
  nhil_amount: string | number;
  getfund_amount: string | number;
  covid_levy_amount: string | number;
  total_amount: string | number;
  paid_amount: string | number;
  balance_due: string | number;
  is_cleared: boolean;
  business_name: string;
  business_tin: string;
  business_address: string;
  business_phone: string;
  business_email: string;
  customer_name: string;
  customer_tin: string;
  customer_ghana_card: string;
  customer_address: string;
  gra_clearance_code: string | null;
  gra_qr_code: string | null;
  gra_cleared_at: string | null;
  pdf_url: string | null;
  lines: PublicInvoiceLine[];
}

export default async function PublicInvoicePage({
  params,
}: {
  params: Promise<{ share_token: string }>;
}) {
  const { share_token } = await params;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  let invoice: PublicInvoiceData | null = null;
  let fetchError = false;

  try {
    const res = await fetch(`${apiUrl}/api/v1/invoicing/public/invoices/${share_token}/`, {
      next: { revalidate: 60 },
      headers: { Accept: "application/json" },
    });

    if (res.ok) {
      invoice = (await res.json()) as PublicInvoiceData;
    } else {
      // Try fallback alias endpoint
      const aliasRes = await fetch(`${apiUrl}/api/v1/public/invoices/${share_token}/`, {
        next: { revalidate: 60 },
        headers: { Accept: "application/json" },
      });
      if (aliasRes.ok) {
        invoice = (await aliasRes.json()) as PublicInvoiceData;
      } else {
        fetchError = true;
      }
    }
  } catch (err) {
    console.error("[PublicInvoicePage] Fetch exception:", err);
    fetchError = true;
  }

  if (fetchError || !invoice) {
    return (
      <div className="min-h-screen bg-[#f4f7fe] flex flex-col items-center justify-center p-6 text-center">
        <Logo />
        <div className="mt-8 bg-white border border-[#c3c6d7] rounded-xl p-8 max-w-md w-full shadow-sm">
          <div className="w-12 h-12 rounded-full bg-[#fef2f2] text-[#dc2626] flex items-center justify-center mx-auto mb-4 font-bold text-xl">
            !
          </div>
          <h1 className="text-xl font-bold text-[#141b2b]">Invoice Not Found</h1>
          <p className="text-sm text-[#434655] mt-2">
            The link you followed may have expired, or the invoice share token is invalid.
          </p>
          <Link
            href="/login"
            className="inline-block mt-6 px-4 py-2 bg-[#2563eb] text-white text-sm font-semibold rounded-lg hover:bg-[#1d4ed8] transition-colors"
          >
            Go to Mage Books
          </Link>
        </div>
      </div>
    );
  }

  const formatGHS = (val: string | number) => {
    const num = typeof val === "string" ? parseFloat(val) : val;
    return `GH¢ ${Number.isNaN(num) ? "0.00" : num.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const isPaid = invoice.status === "PAID" || parseFloat(String(invoice.balance_due)) <= 0;

  return (
    <div className="min-h-screen bg-[#f4f7fe] py-10 px-4 sm:px-6">
      <div className="max-w-4xl mx-auto flex flex-col gap-6">
        {/* Navigation & Brand */}
        <div className="flex items-center justify-between">
          <Logo />
          <div className="flex items-center gap-3">
            <span
              className={`px-3 py-1 rounded-full text-xs font-bold border ${
                isPaid
                  ? "bg-[#ecfdf5] text-[#059669] border-[#a7f3d0]"
                  : invoice.status === "CLEARED"
                  ? "bg-[#eff6ff] text-[#2563eb] border-[#bfdbfe]"
                  : "bg-[#fffbeb] text-[#d97706] border-[#fde68a]"
              }`}
            >
              {isPaid ? "PAID" : invoice.status.replace("_", " ")}
            </span>
          </div>
        </div>

        {/* Invoice Card */}
        <div className="bg-white border border-[#c3c6d7] rounded-xl shadow-sm overflow-hidden p-8 sm:p-12">
          {/* Header Row */}
          <div className="flex flex-col sm:flex-row justify-between items-start gap-6 border-b border-[#c3c6d7] pb-8">
            <div>
              <p className="text-xs uppercase font-bold tracking-wider text-[#64748b]">TAX INVOICE</p>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-[#141b2b] mt-1">
                {invoice.invoice_number}
              </h1>
              {invoice.payment_reference && (
                <p className="text-xs text-[#434655] mt-1">
                  Payment Reference: <span className="font-mono font-semibold">{invoice.payment_reference}</span>
                </p>
              )}
            </div>

            <div className="text-left sm:text-right">
              <p className="text-lg font-bold text-[#141b2b]">{invoice.business_name || "Mage Books Merchant"}</p>
              {invoice.business_tin && (
                <p className="text-xs text-[#434655] mt-0.5">TIN: {invoice.business_tin}</p>
              )}
              {invoice.business_email && (
                <p className="text-xs text-[#434655]">{invoice.business_email}</p>
              )}
              {invoice.business_phone && (
                <p className="text-xs text-[#434655]">{invoice.business_phone}</p>
              )}
            </div>
          </div>

          {/* Customer & Dates Meta */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 py-6 border-b border-[#c3c6d7] text-sm">
            <div>
              <p className="text-xs uppercase font-bold text-[#64748b]">Billed To</p>
              <p className="font-bold text-[#141b2b] text-base mt-1">{invoice.customer_name || "Valued Customer"}</p>
              {invoice.customer_tin && (
                <p className="text-xs text-[#434655] mt-0.5">TIN: {invoice.customer_tin}</p>
              )}
              {invoice.customer_ghana_card && (
                <p className="text-xs text-[#434655]">Ghana Card: {invoice.customer_ghana_card}</p>
              )}
              {invoice.customer_address && (
                <p className="text-xs text-[#434655] mt-0.5">{invoice.customer_address}</p>
              )}
            </div>

            <div className="sm:text-right flex flex-col justify-start sm:items-end">
              <div>
                <p className="text-xs text-[#64748b]">Issue Date: <span className="font-semibold text-[#141b2b]">{invoice.issue_date}</span></p>
                <p className="text-xs text-[#64748b] mt-1">Due Date: <span className="font-semibold text-[#141b2b]">{invoice.due_date}</span></p>
              </div>

              {invoice.gra_clearance_code && (
                <div className="mt-4 p-2.5 bg-[#f0fdf4] border border-[#bbf7d0] rounded-lg text-left inline-block">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-[#15803d]">
                    <span>✓</span> GRA E-VAT Fiscalized
                  </div>
                  <p className="text-[11px] font-mono text-[#166534] mt-0.5">
                    Clearance: {invoice.gra_clearance_code}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Line Items Table */}
          <div className="py-6 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[#c3c6d7] text-[#64748b] text-xs font-bold uppercase">
                  <th className="py-3 px-2">Item Description</th>
                  <th className="py-3 px-2 text-center">Qty</th>
                  <th className="py-3 px-2 text-right">Unit Price</th>
                  <th className="py-3 px-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0]">
                {invoice.lines && invoice.lines.length > 0 ? (
                  invoice.lines.map((line, idx) => (
                    <tr key={line.id || idx}>
                      <td className="py-3 px-2 text-[#141b2b] font-medium">
                        {line.description}
                        {line.is_taxable && (
                          <span className="ml-2 text-[10px] uppercase font-bold text-[#059669] bg-[#ecfdf5] px-1.5 py-0.5 rounded">
                            Taxable
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-2 text-center text-[#434655]">{line.quantity}</td>
                      <td className="py-3 px-2 text-right text-[#434655]">{formatGHS(line.unit_price)}</td>
                      <td className="py-3 px-2 text-right font-semibold text-[#141b2b]">
                        {formatGHS(line.line_total)}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-[#64748b]">
                      Standard Invoiced Services
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Totals Section */}
          <div className="border-t border-[#c3c6d7] pt-6 flex flex-col sm:flex-row justify-between items-start gap-6">
            <div className="max-w-xs text-xs text-[#64748b]">
              <p className="font-semibold text-[#141b2b] mb-1">Ghana Revenue Authority (GRA) Compliance</p>
              <p>
                This invoice has been issued in compliance with the Value Added Tax Act, 2013 (Act 870) and
                Amendment Act, 2023 (Act 1151).
              </p>
            </div>

            <div className="w-full sm:w-72 flex flex-col gap-2 text-sm">
              <div className="flex justify-between text-[#434655]">
                <span>Subtotal:</span>
                <span className="font-semibold text-[#141b2b]">{formatGHS(invoice.subtotal_amount)}</span>
              </div>
              <div className="flex justify-between text-xs text-[#64748b]">
                <span>VAT (15.0%):</span>
                <span>{formatGHS(invoice.vat_amount)}</span>
              </div>
              <div className="flex justify-between text-xs text-[#64748b]">
                <span>NHIL (2.5%):</span>
                <span>{formatGHS(invoice.nhil_amount)}</span>
              </div>
              <div className="flex justify-between text-xs text-[#64748b]">
                <span>GETFund (2.5%):</span>
                <span>{formatGHS(invoice.getfund_amount)}</span>
              </div>
              <div className="flex justify-between border-t border-[#c3c6d7] pt-2 text-base font-bold text-[#141b2b]">
                <span>Total:</span>
                <span>{formatGHS(invoice.total_amount)}</span>
              </div>
              <div className="flex justify-between text-xs text-[#059669]">
                <span>Paid to Date:</span>
                <span>- {formatGHS(invoice.paid_amount)}</span>
              </div>
              <div className="flex justify-between bg-[#f8f9ff] p-3 rounded-lg border border-[#c3c6d7] font-black text-lg text-[#004ac6] mt-1">
                <span>Balance Due:</span>
                <span>{formatGHS(invoice.balance_due)}</span>
              </div>
            </div>
          </div>

          {/* Payment CTA Strip */}
          {!isPaid && (
            <div className="mt-8 pt-6 border-t border-[#c3c6d7] flex flex-col sm:flex-row items-center justify-between gap-4 bg-[#eff6ff] p-6 rounded-xl">
              <div>
                <p className="font-bold text-[#141b2b] text-base">Ready to pay this invoice?</p>
                <p className="text-xs text-[#434655] mt-0.5">
                  Instant settlement via MTN MoMo, Telecel Cash, AT Money, or Visa/Mastercard.
                </p>
              </div>
              <button
                type="button"
                className="w-full sm:w-auto px-6 py-3 bg-[#2563eb] hover:bg-[#1d4ed8] text-white font-bold text-sm rounded-lg shadow transition-colors flex items-center justify-center gap-2"
              >
                <span>💳</span> Pay Now ({formatGHS(invoice.balance_due)})
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-[#94a3b8]">
          Powered by <span className="font-bold text-[#434655]">Mage Books SAAS</span> · Secure Ghanaian Cloud Accounting
        </p>
      </div>
    </div>
  );
}
