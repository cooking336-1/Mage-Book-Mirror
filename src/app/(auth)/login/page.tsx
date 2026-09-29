"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Logo from "@/components/Logo";
import apiClient, { setActiveTenantId } from "@/lib/apiClient";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!email.trim() || !password) {
      setErrorMessage("Please enter both email/phone and password.");
      return;
    }

    setIsLoading(true);

    try {
      // 1. Fetch CSRF token cookie
      try {
        await apiClient.get("/api/v1/auth/csrf/");
      } catch {
        // Continue if csrf endpoint unavailable or pre-set
      }

      // 2. Submit credentials
      await apiClient.post("/api/v1/auth/login/", {
        email: email.trim(),
        password,
      });

      // 3. Resolve tenant organization membership
      try {
        const orgsRes = await apiClient.get("/api/v1/tenancy/organizations/");
        const orgs = Array.isArray(orgsRes.data)
          ? orgsRes.data
          : orgsRes.data.results || [];
        if (orgs.length > 0) {
          setActiveTenantId(orgs[0].id);
          router.push("/dashboard");
        } else {
          router.push("/onboarding");
        }
      } catch {
        router.push("/onboarding");
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string; non_field_errors?: string[] } } };
      const detail =
        axiosErr.response?.data?.detail ||
        axiosErr.response?.data?.non_field_errors?.[0] ||
        "Unable to log in. Please check your credentials.";
      setErrorMessage(detail);
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
          {/* Heading */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-[#141b2b] mb-2">Login</h1>
            <p className="text-sm text-[#555f6d]">
              Enter your account details to continue to Mage Books
            </p>
          </div>

          {errorMessage && (
            <div className="mb-6 p-4 rounded-lg bg-[#fef2f2] border border-[#fecaca] text-[#dc2626] text-sm font-medium">
              {errorMessage}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Email/Phone */}
            <div>
              <label className="block text-sm text-[#141b2b] mb-2">
                Email/Phone Number
              </label>
              <input
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email or phone number"
                className="w-full h-12 px-4 bg-[#f9f9ff] border border-[#c3c6d7] rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#2563eb] focus:border-transparent"
              />
            </div>

            {/* Password */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-[#141b2b]">Password</label>
                <Link
                  href="/forgot-password"
                  className="text-sm text-[#004ac6] hover:underline"
                >
                  Forgot Password?
                </Link>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full h-12 px-4 bg-[#f9f9ff] border border-[#c3c6d7] rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#2563eb] focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-[#6b7280] hover:text-[#141b2b]"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" />
                      <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Login button */}
            <div className="flex justify-center pt-2">
              <button
                type="submit"
                disabled={isLoading}
                className="flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] disabled:opacity-50 text-white font-medium text-base px-10 h-12 rounded-lg shadow-md transition-colors"
              >
                {isLoading ? "Logging in..." : "Login"}
              </button>
            </div>
          </form>

          {/* Sign up link */}
          <p className="text-center mt-8 text-base text-[#141b2b]">
            New To Mage?{" "}
            <Link
              href="/signup"
              className="text-[#004ac6] hover:underline font-medium"
            >
              Sign up here
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
