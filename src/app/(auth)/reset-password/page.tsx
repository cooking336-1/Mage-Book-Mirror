"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import Logo from "@/components/Logo";
import apiClient from "@/lib/apiClient";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ password?: string; confirmPassword?: string }>({});

  const eyeIcon = (visible: boolean) =>
    visible ? (
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
    );

  // Missing or corrupted reset token guard
  if (!uid || !token) {
    return (
      <div className="text-center py-6">
        <div className="w-14 h-14 bg-[#fef2f2] border border-[#fecaca] rounded-full flex items-center justify-center mx-auto mb-4 text-[#dc2626] text-2xl">
          ⚠
        </div>
        <h2 className="text-2xl font-bold text-[#141b2b] mb-2">Invalid Reset Link</h2>
        <p className="text-sm text-[#555f6d] mb-6 leading-relaxed">
          This password reset link is invalid, incomplete, or has expired. Please request a new link.
        </p>
        <Link
          href="/forgot-password"
          className="inline-flex items-center justify-center bg-[#2563eb] hover:bg-[#1d4ed8] text-white font-medium text-base h-12 px-6 rounded-lg shadow-md transition-colors"
        >
          Request New Link
        </Link>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setFieldErrors({});

    const errors: { password?: string; confirmPassword?: string } = {};

    if (!password) {
      errors.password = "Password is required.";
    } else if (password.length < 8) {
      errors.password = "Password must be at least 8 characters long.";
    }

    if (!confirmPassword) {
      errors.confirmPassword = "Confirm password is required.";
    } else if (password && password !== confirmPassword) {
      errors.confirmPassword = "Passwords do not match.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setIsLoading(true);

    try {
      await apiClient.post("/api/v1/auth/password-reset/confirm/", {
        uid,
        token,
        new_password: password,
        confirm_password: confirmPassword,
      });

      setIsSuccess(true);
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: {
          data?: {
            detail?: string;
            token?: string[];
            new_password?: string[];
            confirm_password?: string[];
            non_field_errors?: string[];
          };
        };
      };

      const data = axiosErr.response?.data;
      if (data?.token?.[0]) {
        setErrorMessage(data.token[0]);
      } else if (data?.new_password?.[0]) {
        setFieldErrors({ password: data.new_password[0] });
      } else if (data?.confirm_password?.[0]) {
        setFieldErrors({ confirmPassword: data.confirm_password[0] });
      } else if (data?.detail) {
        setErrorMessage(data.detail);
      } else if (data?.non_field_errors?.[0]) {
        setErrorMessage(data.non_field_errors[0]);
      } else {
        setErrorMessage("Unable to reset password. The link may have expired. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="text-center py-6">
        <div className="w-14 h-14 bg-[#ecfdf5] border border-[#a7f3d0] rounded-full flex items-center justify-center mx-auto mb-4 text-[#059669] text-2xl">
          ✓
        </div>
        <h2 className="text-2xl font-bold text-[#141b2b] mb-2">Password Reset Complete</h2>
        <p className="text-sm text-[#555f6d] mb-8 leading-relaxed">
          Your password has been securely updated and all previous sessions signed out. You can now
          log in with your new credentials.
        </p>
        <button
          type="button"
          onClick={() => router.push("/login")}
          className="w-full flex items-center justify-center bg-[#2563eb] hover:bg-[#1d4ed8] text-white font-medium text-base h-12 rounded-lg shadow-md transition-colors"
        >
          Sign In to Your Account
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-[#141b2b] mb-2">Set New Password</h1>
        <p className="text-sm text-[#555f6d]">
          Enter your new password below. Ensure it is at least 8 characters long.
        </p>
      </div>

      {errorMessage && (
        <div className="mb-6 p-4 rounded-lg bg-[#fef2f2] border border-[#fecaca] text-[#dc2626] text-sm font-medium">
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* New Password */}
        <div>
          <label className="block text-sm font-medium text-[#141b2b] mb-2">
            New Password
          </label>
          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              required
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (fieldErrors.password) setFieldErrors((prev) => ({ ...prev, password: undefined }));
              }}
              placeholder="Enter new password (min. 8 characters)"
              className={`w-full h-12 px-4 pr-12 bg-[#f9f9ff] border ${
                fieldErrors.password ? "border-[#dc2626]" : "border-[#c3c6d7]"
              } rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#2563eb] focus:border-transparent`}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-[#555f6d] hover:text-[#141b2b]"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {eyeIcon(showPassword)}
            </button>
          </div>
          {fieldErrors.password && (
            <p className="text-[#dc2626] text-xs mt-1.5 font-medium">{fieldErrors.password}</p>
          )}
        </div>

        {/* Confirm Password */}
        <div>
          <label className="block text-sm font-medium text-[#141b2b] mb-2">
            Confirm New Password
          </label>
          <div className="relative">
            <input
              type={showConfirm ? "text" : "password"}
              required
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                if (fieldErrors.confirmPassword) {
                  setFieldErrors((prev) => ({ ...prev, confirmPassword: undefined }));
                }
              }}
              placeholder="Confirm your new password"
              className={`w-full h-12 px-4 pr-12 bg-[#f9f9ff] border ${
                fieldErrors.confirmPassword ? "border-[#dc2626]" : "border-[#c3c6d7]"
              } rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#2563eb] focus:border-transparent`}
            />
            <button
              type="button"
              onClick={() => setShowConfirm(!showConfirm)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-[#555f6d] hover:text-[#141b2b]"
              aria-label={showConfirm ? "Hide password" : "Show password"}
            >
              {eyeIcon(showConfirm)}
            </button>
          </div>
          {fieldErrors.confirmPassword && (
            <p className="text-[#dc2626] text-xs mt-1.5 font-medium">{fieldErrors.confirmPassword}</p>
          )}
        </div>

        <div className="flex justify-center pt-2">
          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center bg-[#2563eb] hover:bg-[#1d4ed8] disabled:opacity-50 text-white font-medium text-base h-12 rounded-lg shadow-md transition-colors"
          >
            {isLoading ? "Updating Password..." : "Reset Password"}
          </button>
        </div>
      </form>
    </>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-[#f4f7fe] flex flex-col items-center py-12 px-4">
      {/* Logo */}
      <div className="mb-10">
        <Logo />
      </div>

      {/* Card */}
      <div className="w-full max-w-lg bg-[#f4f7fe] rounded-xl overflow-hidden">
        <div className="bg-white rounded-xl shadow-sm border border-[#c3c6d7] px-12 py-10">
          <Suspense
            fallback={
              <div className="text-center py-8 text-[#555f6d]">
                Loading password reset...
              </div>
            }
          >
            <ResetPasswordForm />
          </Suspense>

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
