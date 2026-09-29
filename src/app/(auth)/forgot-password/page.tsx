"use client";

import { useState } from "react";
import Link from "next/link";
import Logo from "@/components/Logo";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!email.trim()) {
      setErrorMessage("Please enter your registered email address.");
      return;
    }

    setIsLoading(true);

    try {
      // Endpoint is POST /api/v1/auth/password-reset/
      // Uses standard fetch/axios gracefully with fallback
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/v1/auth/password-reset/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });

      if (response.ok || response.status === 400 || response.status === 404) {
        // For security, always show success to prevent email enumeration
        setIsSubmitted(true);
      } else {
        setErrorMessage("An unexpected error occurred. Please try again later.");
      }
    } catch {
      // Even if network error occurs in dev, show confirmation
      setIsSubmitted(true);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f4f7fe] flex flex-col items-center py-12 px-4">
      {/* Logo */}
      <div className="mb-10">
        <Logo />
      </div>

      {/* Card */}
      <div className="w-full max-w-lg bg-[#f4f7fe] rounded-xl overflow-hidden">
        <div className="bg-white rounded-xl shadow-sm border border-[#c3c6d7] px-12 py-10">
          {!isSubmitted ? (
            <>
              {/* Heading */}
              <div className="text-center mb-8">
                <h1 className="text-3xl font-bold text-[#141b2b] mb-2">Forgot Password</h1>
                <p className="text-sm text-[#555f6d]">
                  Enter your email address and we will send you a secure link to reset your
                  password.
                </p>
              </div>

              {errorMessage && (
                <div className="mb-6 p-4 rounded-lg bg-[#fef2f2] border border-[#fecaca] text-[#dc2626] text-sm font-medium">
                  {errorMessage}
                </div>
              )}

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-[#141b2b] mb-2">
                    Email Address
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your registered email address"
                    className="w-full h-12 px-4 bg-[#f9f9ff] border border-[#c3c6d7] rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#2563eb] focus:border-transparent"
                  />
                </div>

                <div className="flex justify-center pt-2">
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full flex items-center justify-center bg-[#2563eb] hover:bg-[#1d4ed8] disabled:opacity-50 text-white font-medium text-base h-12 rounded-lg shadow-md transition-colors"
                  >
                    {isLoading ? "Sending..." : "Send Reset Instructions"}
                  </button>
                </div>
              </form>
            </>
          ) : (
            <div className="text-center py-4">
              <div className="w-14 h-14 bg-[#ecfdf5] border border-[#a7f3d0] rounded-full flex items-center justify-center mx-auto mb-4 text-[#059669] text-2xl">
                ✓
              </div>
              <h2 className="text-2xl font-bold text-[#141b2b] mb-2">Check Your Email</h2>
              <p className="text-sm text-[#555f6d] mb-6 leading-relaxed">
                If an account exists for <span className="font-semibold text-[#141b2b]">{email}</span>,
                you will receive password reset instructions shortly.
              </p>
              <button
                type="button"
                onClick={() => {
                  setIsSubmitted(false);
                  setEmail("");
                }}
                className="text-sm text-[#004ac6] hover:underline font-medium"
              >
                Did not receive the email? Try another address
              </button>
            </div>
          )}

          {/* Back to Login Link */}
          <div className="text-center mt-8 pt-6 border-t border-[#c3c6d7]">
            <Link
              href="/login"
              className="text-sm text-[#004ac6] hover:underline font-semibold inline-flex items-center gap-1.5"
            >
              ← Back to Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
