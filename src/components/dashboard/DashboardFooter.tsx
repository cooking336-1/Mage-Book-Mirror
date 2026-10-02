import Link from "next/link";

export default function DashboardFooter() {
  return (
    <footer className="mt-auto py-6 px-8 border-t border-[#c3c6d7] text-xs text-[#737686] flex flex-col md:flex-row items-center justify-between gap-4 bg-white/50">
      <div className="flex flex-col sm:flex-row items-center gap-2 sm:gap-4">
        <span>&copy; 2026 MageBooks. All rights reserved.</span>
        <span className="hidden sm:inline text-[#c3c6d7]">&bull;</span>
        <span className="text-[#4b5563]">
          Operating in compliance with GRA E-VAT Act &amp; Data Protection Act, 2012 (Act 843)
        </span>
      </div>

      <div className="flex items-center gap-6">
        <Link
          href="/legal/privacy"
          className="hover:text-[#2563eb] transition-colors"
        >
          Privacy Policy
        </Link>
        <Link
          href="/legal/terms"
          className="hover:text-[#2563eb] transition-colors"
        >
          Terms of Service
        </Link>
        <Link
          href="/legal/support"
          className="hover:text-[#2563eb] transition-colors"
        >
          Help &amp; Support
        </Link>
      </div>
    </footer>
  );
}
