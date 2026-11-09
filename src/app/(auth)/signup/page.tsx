"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Logo from "@/components/Logo";
import apiClient from "@/lib/apiClient";

interface FieldErrors {
  email?: string;
  password?: string;
  confirmPassword?: string;
  [key: string]: string | undefined;
}

interface ParsedSignupError {
  generalError: string | null;
  fieldErrors: FieldErrors;
}

function parseSignupError(err: unknown): ParsedSignupError {
  const result: ParsedSignupError = {
    generalError: null,
    fieldErrors: {},
  };

  if (!err || typeof err !== "object") {
    result.generalError = "Unable to create account. Please try again.";
    return result;
  }

  const axiosErr = err as {
    code?: string;
    message?: string;
    response?: {
      status?: number;
      data?: unknown;
    };
  };

  // Case 1: Network / connection failure (backend unreachable)
  if (!axiosErr.response) {
    if (axiosErr.code === "ERR_NETWORK" || axiosErr.message === "Network Error") {
      result.generalError =
        "Unable to connect to authentication server. Please check your network connection.";
    } else if (axiosErr.message) {
      result.generalError = axiosErr.message;
    } else {
      result.generalError = "Network error: Unable to contact server. Please try again.";
    }
    return result;
  }

  const { status, data } = axiosErr.response;

  // Case 2: Server errors (5xx)
  if (status && status >= 500) {
    if (typeof data === "string" && data.includes("OperationalError")) {
      result.generalError =
        "Database service is temporarily unavailable. Please try again shortly.";
    } else if (
      typeof data === "string" &&
      (data.includes("<!DOCTYPE") || data.includes("<html"))
    ) {
      result.generalError = `Server error (${status}). The server encountered an issue. Please try again later.`;
    } else if (
      data &&
      typeof data === "object" &&
      "detail" in data &&
      typeof (data as { detail: unknown }).detail === "string"
    ) {
      result.generalError = (data as { detail: string }).detail;
    } else {
      result.generalError = `Server error (${status}). Please try again later.`;
    }
    return result;
  }

  // Case 3: Client errors with string payload
  if (typeof data === "string") {
    result.generalError = data || "Unable to create account. Please try again.";
    return result;
  }

  // Case 4: Client errors (4xx) with JSON object payload
  if (data && typeof data === "object") {
    const errorObj = data as Record<string, unknown>;

    // Non-field errors or top-level detail / message / error
    if (typeof errorObj.detail === "string") {
      result.generalError = errorObj.detail;
    } else if (Array.isArray(errorObj.detail) && errorObj.detail.length > 0) {
      result.generalError = errorObj.detail.map(String).join(" ");
    }

    if (Array.isArray(errorObj.non_field_errors) && errorObj.non_field_errors.length > 0) {
      result.generalError = errorObj.non_field_errors.map(String).join(" ");
    } else if (typeof errorObj.non_field_errors === "string") {
      result.generalError = errorObj.non_field_errors;
    }

    if (!result.generalError) {
      if (typeof errorObj.message === "string") {
        result.generalError = errorObj.message;
      } else if (typeof errorObj.error === "string") {
        result.generalError = errorObj.error;
      }
    }

    // Field-specific errors (email, password, etc.)
    for (const [key, value] of Object.entries(errorObj)) {
      if (
        key === "detail" ||
        key === "non_field_errors" ||
        key === "error" ||
        key === "message"
      ) {
        continue;
      }

      if (Array.isArray(value) && value.length > 0) {
        result.fieldErrors[key] = value.map(String).join(" ");
      } else if (typeof value === "string") {
        result.fieldErrors[key] = value;
      }
    }

    // If there were only unknown field errors (e.g. phone_number), surface in generalError too
    const unknownFieldKeys = Object.keys(result.fieldErrors).filter(
      (k) => !["email", "password", "confirmPassword"].includes(k)
    );
    if (unknownFieldKeys.length > 0 && !result.generalError) {
      result.generalError = unknownFieldKeys
        .map((k) => `${k.replace("_", " ")}: ${result.fieldErrors[k]}`)
        .join("; ");
    }

    if (!result.generalError && Object.keys(result.fieldErrors).length === 0) {
      result.generalError = "Unable to create account. Please try again.";
    }

    return result;
  }

  result.generalError = "Unable to create account. Please try again.";
  return result;
}

export default function SignUpPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const errorMessage = generalError;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setGeneralError(null);
    setFieldErrors({});

    const trimmedEmail = email.trim();
    const newFieldErrors: FieldErrors = {};

    if (!trimmedEmail) {
      newFieldErrors.email = "Email address is required.";
    }

    if (!password) {
      newFieldErrors.password = "Password is required.";
    } else if (password.length < 8) {
      newFieldErrors.password = "Password must be at least 8 characters long.";
    }

    if (!confirmPassword) {
      newFieldErrors.confirmPassword = "Confirm password is required.";
    } else if (password && password !== confirmPassword) {
      newFieldErrors.confirmPassword = "Passwords do not match.";
    }

    if (Object.keys(newFieldErrors).length > 0) {
      setFieldErrors(newFieldErrors);
      return;
    }

    setIsLoading(true);

    try {
      // 1. Fetch CSRF token cookie
      try {
        await apiClient.get("/api/v1/auth/csrf/");
      } catch {
        // Continue
      }

      // 2. Register account and establish JWT cookie session
      await apiClient.post("/api/v1/auth/register/", {
        email: trimmedEmail,
        password,
      });

      // 3. Navigate to onboarding wizard
      router.push("/onboarding");
    } catch (err: unknown) {
      const parsed = parseSignupError(err);
      setGeneralError(parsed.generalError);
      setFieldErrors(parsed.fieldErrors);
    } finally {
      setIsLoading(false);
    }
  };

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

  return (
    <div className="min-h-screen bg-[#f4f7fe] flex flex-col items-center py-12 px-4">
      {/* Logo */}
      <div className="mb-10">
        <Logo />
      </div>

      {/* Card */}
      <div className="w-full max-w-lg">
        <div className="bg-white rounded-xl shadow-sm border border-[#c3c6d7] px-12 py-10">
          {/* Heading */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-[#141b2b] mb-2">Sign Up</h1>
            <p className="text-sm text-[#555f6d]">
              Sign Up for a Mage account
            </p>
          </div>

          {errorMessage && (
            <div className="mb-6 p-4 rounded-lg bg-[#fef2f2] border border-[#fecaca] text-[#dc2626] text-sm font-medium">
              {errorMessage}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Email */}
            <div>
              <label className="block text-sm text-[#141b2b] mb-2" htmlFor="signup-email">
                Email Address
              </label>
              <input
                id="signup-email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (fieldErrors.email) {
                    setFieldErrors((prev) => ({ ...prev, email: undefined }));
                  }
                  if (generalError) {
                    setGeneralError(null);
                  }
                }}
                placeholder="Enter your email address"
                aria-invalid={!!fieldErrors.email}
                aria-describedby={fieldErrors.email ? "email-error" : undefined}
                className={`w-full h-12 px-4 bg-[#f9f9ff] border rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:border-transparent ${
                  fieldErrors.email
                    ? "border-[#ef4444] focus:ring-[#ef4444]"
                    : "border-[#c3c6d7] focus:ring-[#2563eb]"
                }`}
              />
              {fieldErrors.email && (
                <p className="mt-1 text-xs text-[#ef4444] font-medium" id="email-error">
                  {fieldErrors.email}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm text-[#141b2b] mb-2" htmlFor="signup-password">
                Password
              </label>
              <div className="relative">
                <input
                  id="signup-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (fieldErrors.password) {
                      setFieldErrors((prev) => ({ ...prev, password: undefined }));
                    }
                    if (generalError) {
                      setGeneralError(null);
                    }
                  }}
                  placeholder="Enter your password (min. 8 characters)"
                  aria-invalid={!!fieldErrors.password}
                  aria-describedby={fieldErrors.password ? "password-error" : undefined}
                  className={`w-full h-12 px-4 bg-[#f9f9ff] border rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:border-transparent ${
                    fieldErrors.password
                      ? "border-[#ef4444] focus:ring-[#ef4444]"
                      : "border-[#c3c6d7] focus:ring-[#2563eb]"
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-[#6b7280] hover:text-[#141b2b]"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {eyeIcon(showPassword)}
                </button>
              </div>
              {fieldErrors.password && (
                <p className="mt-1 text-xs text-[#ef4444] font-medium" id="password-error">
                  {fieldErrors.password}
                </p>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-sm text-[#141b2b] mb-2" htmlFor="signup-confirm-password">
                Confirm Password
              </label>
              <div className="relative">
                <input
                  id="signup-confirm-password"
                  type={showConfirm ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (fieldErrors.confirmPassword) {
                      setFieldErrors((prev) => ({ ...prev, confirmPassword: undefined }));
                    }
                    if (generalError) {
                      setGeneralError(null);
                    }
                  }}
                  placeholder="Re-enter your password"
                  aria-invalid={!!fieldErrors.confirmPassword}
                  aria-describedby={fieldErrors.confirmPassword ? "confirm-password-error" : undefined}
                  className={`w-full h-12 px-4 bg-[#f9f9ff] border rounded-lg text-base text-[#141b2b] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:border-transparent ${
                    fieldErrors.confirmPassword
                      ? "border-[#ef4444] focus:ring-[#ef4444]"
                      : "border-[#c3c6d7] focus:ring-[#2563eb]"
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-[#6b7280] hover:text-[#141b2b]"
                  aria-label={showConfirm ? "Hide password" : "Show password"}
                >
                  {eyeIcon(showConfirm)}
                </button>
              </div>
              {fieldErrors.confirmPassword && (
                <p className="mt-1 text-xs text-[#ef4444] font-medium" id="confirm-password-error">
                  {fieldErrors.confirmPassword}
                </p>
              )}
            </div>

            {/* Continue button */}
            <div className="flex justify-center pt-2">
              <button
                type="submit"
                disabled={isLoading}
                className="flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] disabled:opacity-50 text-white font-medium text-base px-10 h-12 rounded-lg shadow-md transition-colors"
              >
                {isLoading ? "Creating Account..." : "Continue"}
              </button>
            </div>
          </form>

          {/* Login link */}
          <p className="text-center mt-8 text-base text-[#141b2b]">
            Already Have an Account?{" "}
            <Link
              href="/login"
              className="text-[#004ac6] hover:underline font-medium"
            >
              Login here
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
